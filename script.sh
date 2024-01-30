y=$1
x=$(ip addr show server-eth0 | grep -Po 'inet \K[\d.]+')
concurrently "npm --prefix ./Documents/NAC-App/NAC-Server/ run start -- --host-ip=${x} --api-ip=${y}" \
"REACT_APP_HOST_IP='${x}' npm --prefix ./Documents/NAC-App/nac-capture-portal/ run start"
