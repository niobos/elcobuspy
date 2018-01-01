import argparse
import logging
import signal
import time
import asyncio

import serial
import serial_asyncio
import sanic

from .ElcobusMessage._registry import field_registry
from .ElcobusProtocol import ElcobusSerialProtocol, ElcobusTcpProtocol, format_sockaddr
from . import HttpApi

parser = argparse.ArgumentParser(description='Elcobus communication daemon')
parser.add_argument('--tcp-port', help="TCP port to listen on", type=int, default=8446)
parser.add_argument('--http-port', help="TCP port to bind webserver to", type=int, default=8081)
parser.add_argument('--logfile', help="Log to the given file", type=str)
parser.add_argument('--debug', help="Enable debug mode", action='store_true')
parser.add_argument('serial_port', help="Serial port to open")

args = parser.parse_args()

logging.getLogger(None).setLevel(logging.INFO)
logging.Formatter.converter = time.gmtime

if args.debug:
    # load all decoders
    __import__('ElcobusMessage', globals(), level=1, fromlist=['*'])

    logging.getLogger(None).setLevel(logging.DEBUG)

if args.logfile:
    log_file_handler = logging.FileHandler(args.logfile)
else:
    log_file_handler = logging.StreamHandler()
log_file_handler.setFormatter(logging.Formatter(
    fmt="%(asctime)sZ [%(name)s %(levelname)s] %(message)s"
))
logging.getLogger(None).addHandler(log_file_handler)


logger = logging.getLogger(__name__)


# Print loaded modules
logger.info("Loaded ElcobusMessage decoder for:")
for field_value in sorted(field_registry.keys()):
    field = field_registry[field_value]
    logger.info(f" - 0x{field.field:04x} {field.value_type.__name__} {field.name} ")

loop = asyncio.get_event_loop()

def handle_sighup():
    logger.info("Received SIGHUP, reopening log file")
    log_file_handler.close()
    logger.info("Received SIGHUP, log file reopened")

loop.add_signal_handler(signal.SIGHUP, handle_sighup)

# Connect to serial port
serial_server = loop.run_until_complete(
    serial_asyncio.create_serial_connection(
        loop, ElcobusSerialProtocol, args.serial_port,
        baudrate=9600,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
    ))

# Start up TCP server
tcpserver = loop.run_until_complete(
    loop.create_server(ElcobusTcpProtocol, None, args.tcp_port, reuse_port=True))
logger.info("Listening for TCP on {}".format(
    format_sockaddr(tcpserver.sockets[0].getsockname())))


# Start up Web server
app = sanic.Sanic(__name__, log_config={})
app.config.LOGO = None
httpserver = app.create_server(host="0.0.0.0", port=args.http_port)
asyncio.ensure_future(httpserver)


#logger.info("Serving /static from {}".format(args.static_dir))
#app.static('/static', args.static_dir)


@app.exception(TimeoutError)
def timeout(request, exception):
    return sanic.response.text("timeout waiting for response\r\n",
                               status=504)


HttpApi.add_routes(app=app)


# Run loop
try:
    loop.run_forever()
except KeyboardInterrupt:
    logger.warning("SIGINT received, closing...")
    pass

tcpserver.close()
loop.run_until_complete(tcpserver.wait_closed())
loop.close()
