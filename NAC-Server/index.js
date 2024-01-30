const express = require('express');
var fs = require('fs');
var http = require('http');
var https = require('https');
const querystring = require('querystring');
const argv = require('yargs').argv;
var _ = require('lodash');
var crypto = require('crypto');
var cors = require('cors');
const axios = require("axios");

const password = 'nacapp';
const resizedIV = Buffer.allocUnsafe(16);
const iv = crypto.createHash('sha256').update('myHashedIV').digest();
iv.copy(resizedIV);
const key = crypto.createHash('sha256').update(password).digest();

const ipRegex = /(\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b)/g;

var privateKey  = fs.readFileSync('sslcert/server.key', 'utf8');
var certificate = fs.readFileSync('sslcert/server.crt', 'utf8');

var credentials = {key: privateKey, cert: certificate};

const app = express()
const httpPort = 3000
const httpsPort = 3001

app.set('trust proxy', true)
app.use(express.json());
app.use(cors())

app.get('/ping', (req, res) => {
  res.send('PONG');
});

app.get('/', (req, res) => {
  const ip = req.headers['x-real-ip'] || req.connection.remoteAddress;
  const matchIp = ip.match(ipRegex);
  const parsedIp = _.get(matchIp, '[0]', null);

  if(!matchIp || !parsedIp){
    return res.status(404).send();
  }
  const cipher = crypto.createCipheriv('aes256', key, resizedIV);
  const encryptedIP = cipher.update(parsedIp, 'utf8', 'hex') + cipher.final('hex');

  const query = querystring.stringify({
    "ip": encryptedIP,
  });
  res.redirect(`http://${argv['host-ip'] || '127.0.0.1'}:3006/?` + query);
})

app.post('/submit', async (req, res) => {
  const body = req.body;
  
  if(body.ip && body.mail) {
    const decipher = crypto.createDecipheriv('aes256', key, resizedIV);
    let unencryptedIP;
    try{
      unencryptedIP = decipher.update(body.ip, 'hex', 'utf8') + decipher.final('utf8');
    } catch {
      return res.status(400).send()
    }
    const isIPValid = RegExp(ipRegex).test(unencryptedIP);
    
    if(isIPValid){
      try{
        const response = await axios.post(`${argv['api-ip']}/auth`, {current_ip: unencryptedIP, user_id: body.mail})
        return res.send();
      } catch {
        console.log('req failed')
        return res.status(400).send();
      }
    } else {
      console.log('invalid ip')
      return res.status(400).send();
    }
  } else {
    console.log('wrong body')
    return res.status(400).send();
  }
})

var httpServer = http.createServer(app);
var httpsServer = https.createServer(credentials, app);

httpServer.listen(httpPort);
httpsServer.listen(httpsPort);
