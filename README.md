# Servidor de Autenticación
## Iniciar Servidor de Autenticación (app.py)
```
gunicorn -w 1 --threads 100 app:app
```

## Iniciar túnel ngrok
```
ngrok http 8000
```

## Revisar DB
```
start phpmyadmin
go to localhost/phpmyadmin
user root password
```

# Red emulada
## Iniciar topo mininet (nac-topo.py)
```
sudo mn --custom ~/mininet/examples/nac-topo.py --topo=nac_topo --controller=remote,ip=127.0.0.1,port=6633 --switch=ovsk --nat
```

## Correr portal de captura en server
```
sh script.sh {{ngrok-output}}
```

## Correr cliente dhcp en host
```
sudo dhclient h1-eth0 && route add default gw 10.0.0.3
./palemoon/palemoon --private-window
```

## Revisar tablas de flow
```
sudo ovs-ofctl dump-flows s1
```

# Aplicación NAC
## Iniciar controlador (nac.py)
```
sudo python3.10 ./MurphyMc/pox/pox.py proto.nac --api_ip={{ngrok-output}} proto.dhcpd --network=10.0.0.0/8 --first=4 --ip=10.255.255.254
```