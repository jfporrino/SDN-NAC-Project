from pox.core import core
import pox.openflow.libopenflow_01 as of
import pox.lib.packet as pkt

from pox.lib.addresses import IPAddr, EthAddr, parse_cidr
from pox.lib.addresses import IP_BROADCAST, IP_ANY
from pox.lib.revent import *
from pox.lib.util import dpid_to_str
import requests
import socketio
import time

log = core.getLogger()

_flood_delay = 0

class NAC(EventMixin):
    sio = socketio.Client()
    _eventMixin_events = set([])
    _servers = []

    def __init__(self, api_ip):
        self.api_ip = api_ip
        self.unauth_dics = []

        self.macToPort = {}
        self.transparent = False
        self.hold_down_expired = _flood_delay == 0

        core.openflow.addListeners(self)
        core.addListeners(self)

    def _handle_ComponentRegistered(self, event):
        if event.name == "DHCPD":
            core.DHCPD.addListeners(self)

    def _handle_ConnectionUp(self, event):
        self.con = event.connection
        #LearningSwitch(event.connection, False)

    def setup(self):
        self.call_backs()
        self.sio.connect(self.api_ip, wait_timeout=10)

    def call_backs(self):
        @self.sio.event
        def connect():
            self.sio.emit('subscribe', 'room')
            print('connection established')

        @self.sio.on("update")
        def raw_data(data):
            log.info(f"\nData Received:\n{data}")

            auth_mac = data['data']['mac']

            previous_flows = filter(lambda x: x["src_mac"] == auth_mac, self.unauth_dics)
            remaining_flows = filter(lambda x: x["src_mac"] != auth_mac, self.unauth_dics)

            self._remove_unauth_flows(auth_mac)
            log.info("\nRemove previous Dics:\n")
            for i in previous_flows:
                log.info(f"{i}")
                self._remove_mask_flows(i)
            log.info('\n')

            self.unauth_dics = remaining_flows


        @self.sio.event
        def disconnect():
            print('disconnected from server')

    def run(self):
        self.setup()

    def _handle_DHCPLease(self, event):
        body = {'mac': event.host_mac.toStr(), 'current_ip': event.ip.toStr()}
        
        r = requests.post(self.api_ip + '/isAuth', json = body)
        if r.status_code != 200:
            return None

        entry = r.json()
        auth = entry['is_auth']
        
        if auth is False:
            self._add_unauth_flows(entry['mac'], entry['current_ip'])
            self.unauth_dics.append({"src_mac": entry['mac']})

    def _remove_unauth_flows(self, mac):
        controller_http_msg = of.ofp_flow_mod()
        controller_http_msg.match = of.ofp_match()
        controller_http_msg.match.tp_dst = 80
        controller_http_msg.match.dl_src = EthAddr(mac)
        controller_http_msg.match.dl_type = pkt.ethernet.IP_TYPE
        controller_http_msg.match.nw_proto = pkt.ipv4.TCP_PROTOCOL
        controller_http_msg.command = of.OFPFC_DELETE

        controller_https_msg = of.ofp_flow_mod()
        controller_https_msg.match = of.ofp_match()
        controller_https_msg.match.tp_dst = 443
        controller_https_msg.match.dl_src = EthAddr(mac)
        controller_https_msg.match.dl_type = pkt.ethernet.IP_TYPE
        controller_https_msg.match.nw_proto = pkt.ipv4.TCP_PROTOCOL
        controller_https_msg.command = of.OFPFC_DELETE

        self.con.send(controller_http_msg)
        self.con.send(controller_https_msg)

    def _add_unauth_flows(self, mac, ip):
        controller_http_msg = of.ofp_flow_mod()
        controller_http_msg.match = of.ofp_match()
        controller_http_msg.match.tp_dst = 80
        controller_http_msg.match.dl_src = EthAddr(mac)
        controller_http_msg.match.dl_type = pkt.ethernet.IP_TYPE
        controller_http_msg.match.nw_proto = pkt.ipv4.TCP_PROTOCOL
        controller_http_msg.priority = 10
        controller_http_msg.actions.append(of.ofp_action_output(port=of.OFPP_CONTROLLER))

        controller_https_msg = of.ofp_flow_mod()
        controller_https_msg.match = of.ofp_match()
        controller_https_msg.match.tp_dst = 443
        controller_https_msg.match.dl_src = EthAddr(mac)
        controller_https_msg.match.dl_type = pkt.ethernet.IP_TYPE
        controller_https_msg.match.nw_proto = pkt.ipv4.TCP_PROTOCOL
        controller_https_msg.priority = 10
        controller_https_msg.actions.append(of.ofp_action_output(port=of.OFPP_CONTROLLER))

        self.con.send(controller_http_msg)
        self.con.send(controller_https_msg)

    def _handle_PacketIn(self, event):
        packet = event.parsed
        ethp = packet.find('ethernet')
        if not ethp or not ethp.parsed:
            return

        src_mac = ethp.src

        ipp = packet.find('ipv4')
        if not ipp or not ipp.parsed:
            self._normal_routing_rules(event)
            return

        tcpp = packet.find('tcp')
        if not tcpp or not tcpp.parsed:
            self._normal_routing_rules(event)
            return

        dst_port = tcpp.dstport

        found = next((item for item in self.unauth_dics if item["src_mac"] == src_mac), None)

        if found is not None and (dst_port == 80 or dst_port == 443):
            self._mask_connection(event)
            
            msg = of.ofp_packet_out()
            msg.buffer_id = event.ofp.buffer_id
            msg.in_port = event.port
            self.con.send(msg)
        else:
            self._normal_routing_rules(event)

    def _remove_mask_flows(self, unauth_dic):
        if ("src_mac" not in unauth_dic or
            "dst_ip" not in unauth_dic or
            "src_port" not in unauth_dic or
            "src_ip" not in unauth_dic):
        return

        in_mask_msg = of.ofp_flow_mod()
        in_mask_msg.command = of.OFPFC_DELETE
        in_mask_msg.match = of.ofp_match()
        in_mask_msg.match.tp_src = unauth_dic["src_port"]
        in_mask_msg.match.tp_dst = unauth_dic["dst_port"]
        in_mask_msg.match.dl_src = EthAddr(unauth_dic["src_mac"])
        in_mask_msg.match.nw_dst = IPAddr(unauth_dic["dst_ip"])
        in_mask_msg.match.dl_type = pkt.ethernet.IP_TYPE
        in_mask_msg.match.nw_proto = pkt.ipv4.TCP_PROTOCOL


        out_mask_msg = of.ofp_flow_mod()
        out_mask_msg.command = of.OFPFC_DELETE
        out_mask_msg.match = of.ofp_match()
        out_mask_msg.match.tp_dst = unauth_dic["src_port"]
        out_mask_msg.match.dl_src = EthAddr("00:00:00:00:00:04")
        out_mask_msg.match.dl_dst = EthAddr(unauth_dic["src_mac"])
        out_mask_msg.match.nw_src = IPAddr("10.0.0.1")
        out_mask_msg.match.nw_dst = IPAddr(unauth_dic["src_ip"])
        out_mask_msg.match.dl_type = pkt.ethernet.IP_TYPE

        self.con.send(in_mask_msg)
        self.con.send(out_mask_msg)

    def _mask_connection(self, event):
        packet = event.parsed
        ethp = packet.find('ethernet')
        ipp = packet.find('ipv4')
        tcpp = packet.find('tcp')

        src_mac = ethp.src
        dst_mac = ethp.dst
        src_ip = ipp.srcip
        dst_ip = ipp.dstip
        src_port = tcpp.srcport
        dst_port = tcpp.dstport

        const newDic = {
            "src_mac": src_mac, 
            "dst_mac": dst_mac, 
            "src_ip": src_ip, 
            "dst_ip": dst_ip, 
            "src_port": src_port, 
            "dst_port": dst_port
        }
        self.unauth_dics.append(newDic)

        server_port = 3000

        if dst_port == 443:
            server_port = 3001

        in_mask_msg = of.ofp_flow_mod()
        in_mask_msg.priority = 20
        in_mask_msg.match = of.ofp_match()
        in_mask_msg.match.tp_src = src_port
        in_mask_msg.match.tp_dst = dst_port
        in_mask_msg.match.dl_src = EthAddr(src_mac)
        in_mask_msg.match.nw_dst = IPAddr(dst_ip)
        in_mask_msg.match.dl_type = pkt.ethernet.IP_TYPE
        in_mask_msg.match.nw_proto = pkt.ipv4.TCP_PROTOCOL
        in_mask_msg.actions.append(of.ofp_action_dl_addr.set_dst(EthAddr("00:00:00:00:00:04")))
        in_mask_msg.actions.append(of.ofp_action_nw_addr.set_dst(IPAddr("10.0.0.1")))
        in_mask_msg.actions.append(of.ofp_action_tp_port.set_dst(server_port))
        in_mask_msg.actions.append(of.ofp_action_output(port=of.OFPP_NORMAL))

        out_mask_msg = of.ofp_flow_mod()
        out_mask_msg.priority = 20
        out_mask_msg.match = of.ofp_match()
        out_mask_msg.match.tp_dst = src_port
        out_mask_msg.match.dl_src = EthAddr("00:00:00:00:00:04")
        out_mask_msg.match.dl_dst = EthAddr(src_mac)
        out_mask_msg.match.nw_src = IPAddr("10.0.0.1")
        out_mask_msg.match.nw_dst = IPAddr(src_ip)
        out_mask_msg.match.dl_type = pkt.ethernet.IP_TYPE
        out_mask_msg.match.nw_proto = pkt.ipv4.TCP_PROTOCOL
        out_mask_msg.actions.append(of.ofp_action_dl_addr.set_src(EthAddr(dst_mac)))
        out_mask_msg.actions.append(of.ofp_action_nw_addr.set_src(IPAddr(dst_ip)))
        out_mask_msg.actions.append(of.ofp_action_tp_port.set_src(dst_port))
        out_mask_msg.actions.append(of.ofp_action_output(port=of.OFPP_NORMAL))

        self.con.send(in_mask_msg)
        self.con.send(out_mask_msg)


    def _normal_routing_rules(self, event):
        packet = event.parsed

        def flood(message=None):
            """ Floods the packet """
            msg = of.ofp_packet_out()
            if time.time() - self.con.connect_time >= _flood_delay:
                # Only flood if we've been connected for a little while...

                if self.hold_down_expired is False:
                    # Oh yes it is!
                    self.hold_down_expired = True
                    log.info("%s: Flood hold-down expired -- flooding",
                             dpid_to_str(event.dpid))

                if message is not None: log.debug(message)
                # log.debug("%i: flood %s -> %s", event.dpid,packet.src,packet.dst)
                # OFPP_FLOOD is optional; on some switches you may need to change
                # this to OFPP_ALL.
                msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
            else:
                pass
                # log.info("Holding down flood for %s", dpid_to_str(event.dpid))
            msg.data = event.ofp
            msg.in_port = event.port
            self.con.send(msg)

        def drop(duration=None):
            """
            Drops this packet and optionally installs a flow to continue
            dropping similar ones for a while
            """
            if duration is not None:
                if not isinstance(duration, tuple):
                    duration = (duration, duration)
                msg = of.ofp_flow_mod()
                msg.match = of.ofp_match.from_packet(packet)
                msg.idle_timeout = duration[0]
                msg.hard_timeout = duration[1]
                msg.buffer_id = event.ofp.buffer_id
                self.con.send(msg)
            elif event.ofp.buffer_id is not None:
                msg = of.ofp_packet_out()
                msg.buffer_id = event.ofp.buffer_id
                msg.in_port = event.port
                self.con.send(msg)

        self.macToPort[packet.src] = event.port  # 1

        if not self.transparent:  # 2
            if packet.type == packet.LLDP_TYPE or packet.dst.isBridgeFiltered():
                drop()  # 2a
                return

        if packet.dst.is_multicast:
            flood()  # 3a
        else:
            if packet.dst not in self.macToPort:  # 4
                flood("Port for %s unknown -- flooding" % (packet.dst,))  # 4a
            else:
                port = self.macToPort[packet.dst]
                if port == event.port:  # 5
                    # 5a
                    log.warning("Same port for packet from %s -> %s on %s.%s.  Drop."
                                % (packet.src, packet.dst, dpid_to_str(event.dpid), port))
                    drop(10)
                    return
                # 6
                log.debug("installing flow for %s.%i -> %s.%i" %
                          (packet.src, event.port, packet.dst, port))
                msg = of.ofp_flow_mod()
                msg.match = of.ofp_match.from_packet(packet, event.port)
                msg.idle_timeout = 10
                msg.hard_timeout = 30
                msg.actions.append(of.ofp_action_output(port=port))
                msg.data = event.ofp  # 6a
                self.con.send(msg)


def launch(api_ip):
    inst = NAC(api_ip)
    inst.run()

    core.register(inst)

    log.debug("NAC serving")
