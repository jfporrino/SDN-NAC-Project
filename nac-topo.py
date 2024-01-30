from mininet.topo import Topo

class NACTopo( Topo ):
    "Simple topology example."

    def build( self ):
        "Create custom topo."

        # Add hosts and switches
        s1 = self.addSwitch('s1', listenPort=6634, mac='00:00:00:00:00:01')
        h1 = self.addHost('h1', mac='00:00:00:00:00:03', ip='no ip defined/8')
        server = self.addHost('server', mac='00:00:00:00:00:04', ip='10.0.0.1/8')

        # Add links
        self.addLink( h1, s1 )
        self.addLink( server, s1 )


topos = { 'nac_topo': ( lambda: NACTopo() ) }
