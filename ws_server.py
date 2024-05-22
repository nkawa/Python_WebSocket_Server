
import asyncio
from autobahn.asyncio.websocket import WebSocketServerProtocol, WebSocketServerFactory
import sys
import traceback
import ssl
import random
from paho.mqtt import client as mqtt_client
import datetime


"""
 WebSocket で受け取って MQTTに変換するだけ

"""

class DebugPrinter:
	def __init__(self, debug = False):
		self.debug = debug

	def print_debug(self, msg):
		if self.debug:
			print(msg)

class Client:
	def __init__(self, handle):
		self.handle = handle
		self.closeHandler = None

	def close(self):
		try:
			self.handle.sendClose(code=WebSocketClientProtocol.CLOSE_STATUS_CODE_NORMAL)
		except:
			pass

		if self.closeHandler:
			self.closeHandler()

	def sendMessage(self, msg, isBinary):
		self.handle.sendMessage(msg, isBinary)

	def sendTextMsg(self, msg, encoding='utf-8'):
		self.sendMessage(msg.encode(encoding), False)

	def sendBinaryMsg(self, msg):
		self.sendMessage(msg, True)

	def setCloseHandler(self, callback):
		self.closeHandler = callback


class Server(DebugPrinter):

	def __init__(self, port = 9000, useSsl = True, sslCert = "server.crt", sslKey= "server.key", debug = True):
		DebugPrinter.__init__(self, debug)
		self.clients = []
		self.knownClients = {}
		self.broadcastRate = 10
		self.broadcastMsg = None
		self.throttle = False
		self.encodeMsg = False
		self.debug = debug
		self.port = port
		self.sslcert = sslCert
		self.sslkey = sslKey
		self.ssl = useSsl

	def registerClient(self, client):
		self.clients.append(Client(client))

	def hasClients(self):
		return len(self.clients)

	def client(self, client_handle):
		for c in self.clients:
			if c.handle == client_handle:
				return c

	def broadcast(self, msg, isBinary = False):
		try:
			if self.throttle:
				self.broadcastMsg = msg
			else:
				if self.encodeMsg:
					msg = base64.b64encode(self.msg)
				for c in self.clients:
					if isBinary:
						c.sendBinaryMsg(msg)
					else:
						c.sendTextMsg(msg)
		except:
			self.print_debug("exception while broadcast()")
			exc_type, exc_value, exc_traceback = sys.exc_info()
			traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
			traceback.print_exception(exc_type, exc_value, exc_traceback,
                          limit=6, file=sys.stdout)


	def unregisterClient(self, client):
		if isinstance(client, Client):
			client = client.handle

		for c in self.clients:
			if c.handle == client:
				c.close()
				self.clients.remove(c)
				return True

	def setBinaryHandler(self, binaryHandlerCallback):
		self.onBinaryMessage = binaryHandlerCallback

	def setTextHandler(self, textHandlerCallback):
		self.onMessage = textHandlerCallback

	def onBinaryMessage(self, msg, fromClient):
		pass

	def onMessage(self, msg, fromClient):
		"override this in subclass"
		pass

	def start(self):
		self.print_debug("start() called... debug = {}".format(self.debug))
		ws = "ws"

		sslcontext = None
		if self.ssl:
			try:
				sslcontext = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
				sslcontext.load_cert_chain(self.sslcert, self.sslkey)
				self.print_debug("using ssl")
			except Exception as ex:
				sslcontext = None
				self.print_debug("failed to use ssl")
				raise Exception("failed to use ssl: {}".format(ex))

			ws = "wss"	

		ResourceProtocol.server = self

		factory = WebSocketServerFactory(u"{0}://127.0.0.1:{1}".format(ws, self.port))
		factory.protocol = ResourceProtocol

		loop = asyncio.get_event_loop()

		coro = loop.create_server(factory, '', self.port, ssl=sslcontext)
		self.server = loop.run_until_complete(coro)

		self.print_debug("server should be started now")

	def startTwisted(self):
		from twisted.python import log
		log.startLogging(open("wssserver.log", "w"))

		self.print_debug("startTwisted() started")
		ws = "ws"

		ResourceProtocol.server = self

		sslcontext = None
		if self.ssl:
			self.print_debug("using wss... and ssl")
			sslcontext = ssl.DefaultOpenSSLContextFactory(self.sslkey, self.sslcert)
			ws = "wss"

		factory = WebSocketServerFactory(u"{}://127.0.0.1:{}".format(ws, self.port))
		factory.protocol = ResourceProtocol

		listenWS(factory, sslcontext)

		reactor.run()

class ResourceProtocol(WebSocketServerProtocol):
	server = None

	def onConnect(self, request):
		ResourceProtocol.server.print_debug("Client connecting: {0}".format(request.peer))

	def onOpen(self):
		ResourceProtocol.server.print_debug("WebSocket connection open.")
		ResourceProtocol.server.registerClient(self)

	def onMessage(self, payload, isBinary):
		try:
			if isBinary:
				ResourceProtocol.server.onBinaryMessage(payload, ResourceProtocol.server.client(self))
			else:
				ResourceProtocol.server.onMessage(payload, ResourceProtocol.server.client(self))
		except:
			exc_type, exc_value, exc_traceback = sys.exc_info()
			traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
			traceback.print_exception(exc_type, exc_value, exc_traceback,
                          limit=6, file=sys.stdout)

	def onClose(self, wasClean, code, reason):
		try:
			ResourceProtocol.server.print_debug("WebSocket connection closed: {0}".format(reason))
			ResourceProtocol.server.unregisterClient(self)
		except:
			exc_type, exc_value, exc_traceback = sys.exc_info()
			traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
			traceback.print_exception(exc_type, exc_value, exc_traceback,
                          limit=2, file=sys.stdout)


client_id = f'python_mqtt{random.randint(0,1000)}'
print("client_id",client_id)

def connect_mqtt(cid):
	def on_connect(client, userdata, flags, rc):
		if rc==0:
			print("Connected to MQTT broker")
		else:
			print("MQTT Connection failed! %d\n",rc)

	client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION1,cid)
	client.on_connect = on_connect
	client.connect("sora2.uclab.jp",1883)
	return client


loop = asyncio.get_event_loop()

server =  Server(port=9001, useSsl=True, sslCert="fullchain.pem", sslKey="privkey.pem")

#import socket
#sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

mqclt = connect_mqtt(client_id)
msgct  =0

def onTextMessage(msg, client):
	global msgct
	if msgct% 100== 0:	
		now = datetime.datetime.now()
		print(now,msgct/100,msg)
	msgct+=1
	mqclt.publish('webxr/pose', msg)


# sock.sendto(msg, ('192.168.207.183',12345))
        
def onBinaryMessage(msg, client):
	print("got binary message",len(msg))

server.setTextHandler(onTextMessage)
server.setBinaryHandler(onBinaryMessage)


def sendData():
	while True:
		try:
			print("trying to broadcast...")
			server.broadcast("{'hello' : 'world'# }")
		except:
			exc_type, exc_value, exc_traceback = sys.exc_info()
			traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
			traceback.print_exception(exc_type, exc_value, exc_traceback,
                          limit=2, file=sys.stdout)

		yield from asyncio.sleep(30)


server.start()
loop.run_forever()
