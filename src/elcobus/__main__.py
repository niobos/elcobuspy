import argparse
import dataclasses
import logging
import random
import re
import signal
import time
import asyncio
import typing

from paho.mqtt import client as mqtt

from .ElcobusMessage.ElcobusFrame import ElcobusFrame
from .ElcobusMessage.ElcobusFrame import ElcobusMessage
from .ElcobusMessage._registry import field_registry, find_field
from .ElcobusMessage.Temperature import Temperature
from .ElcobusMessage.Percent import Percent
from .ElcobusMessage.Pressure import Pressure
from .ElcobusMessage.Status import Status

_ = [Temperature, Percent, Pressure, Status]  # "Use" these somewhere to avoid "optimizing" them out

parser = argparse.ArgumentParser(description='Elcobus communication daemon')
parser.add_argument('--mqtt-topic-prefix', help="output topic prefix", type=str, default="elcobus")
parser.add_argument('--logfile', help="Log to the given file", type=str)
parser.add_argument('--debug', help="Enable debug mode", action='store_true')
parser.add_argument('mqtt_uri', help="mqtt://host/topic/prefix url to communicate on")

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


# MQTT stuff
@dataclasses.dataclass()
class MqttConnectionDetails:
    protocol: str
    username: typing.Optional[str]
    password: typing.Optional[str]
    host: str
    port: int
    topic: str

    @classmethod
    def from_uri(cls, uri: str) -> "MqttConnectionDetails":
        mqtt_component_match = re.fullmatch(r'(?P<protocol>mqtt)://'
                                            r'((?P<username>[^:@]+)(:(?P<password>[^@]*)?@))?'
                                            r'(?P<host>[^/:]+)'
                                            r'(:(?P<port>\d+))?'
                                            r'(/(?P<topic>.*))?', uri)
        mqtt_component = mqtt_component_match.groupdict()

        if mqtt_component['port'] is None:
            mqtt_component['port'] = 1883
        else:
            mqtt_component['port'] = int(mqtt_component['port'])

        ret = cls(**mqtt_component)
        logger.debug("Parsed MQTT URI as: " + repr(ret))
        return ret


mqtt_connection_details = MqttConnectionDetails.from_uri(args.mqtt_uri)


class PahoMqttAsyncioHelper:
    def __init__(self, client, loop):
        self.client = client
        self.client.on_socket_open = self.on_socket_open
        self.client.on_socket_close = self.on_socket_close
        self.client.on_socket_register_write = self.on_socket_register_write
        self.client.on_socket_unregister_write = self.on_socket_unregister_write
        self.loop = loop

    def on_socket_open(self, client, userdata, sock):
        logger.info("MQTT Socket opened")

        def cb():
            # print("Socket is readable, calling loop_read")
            client.loop_read()

        self.loop.add_reader(sock, cb)
        self.misc = self.loop.create_task(self.misc_loop())

    def on_socket_close(self, client, userdata, sock):
        logger.info("MQTT Socket closed")
        self.loop.remove_reader(sock)
        self.misc.cancel()

    def on_socket_register_write(self, client, userdata, sock):
        # print("Watching socket for writability.")

        def cb():
            # print("Socket is writable, calling loop_write")
            client.loop_write()

        self.loop.add_writer(sock, cb)

    def on_socket_unregister_write(self, client, userdata, sock):
        # print("Stop watching socket for writability.")
        self.loop.remove_writer(sock)

    async def misc_loop(self):
        # print("misc_loop started")
        while self.client.loop_misc() == mqtt.MQTT_ERR_SUCCESS:
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
        # print("misc_loop finished")


class MqttClient:
    def __init__(
            self,
            mqtt_connection_details: MqttConnectionDetails,
            loop: asyncio.AbstractEventLoop = None,
    ):
        self.connection_details = mqtt_connection_details

        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop

        self.client = None
        self.aio_helper = None

    def _connect(self) -> None:
        if self.client is not None and self.client.is_connected():
            self.client.disconnect()

        self.client = mqtt.Client()
        self.aio_helper = PahoMqttAsyncioHelper(self.client, self.loop)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        if self.connection_details.username is not None:
            self.client.username_pw_set(
                username=self.connection_details.username,
                password=self.connection_details.password,
            )
        self.client.connect(
            host=self.connection_details.host,
            port=self.connection_details.port
        )

    def get_mqtt_client(self):
        return self.client

    async def main(self):
        self._connect()

        while True:
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break

    def on_connect(self, client: mqtt.Client, user_data, flags, rc):
        rx_topic = self.connection_details.topic + '/bus_rx'
        client.subscribe(rx_topic, 2)

    def on_disconnect(self, client: mqtt.Client, user_data, rc):
        self.loop.call_soon(self.attempt_reconnect)  # Will deadlock if called from here

    def attempt_reconnect(self):
        try:
            logger.info("Attempting reconnect...")
            self._connect()
        except (ConnectionRefusedError, OSError):
            timeout = 1
            logger.warning(f"Reconnect failed, retrying in {timeout} seconds")
            self.loop.call_later(delay=timeout, callback=self.attempt_reconnect)

    def on_message(self, client: mqtt.Client, user_data, msg: mqtt.MQTTMessage):
        try:
            ebm = ElcobusFrame.from_bytes(msg.payload)
            logger.info(f"Rx: [{' '.join(['{:02x}'.format(b) for b in ebm.to_bytes()])}]")
            logger.debug("Rx:  %r", ebm)
            # ^^ don't use ''.format()
            # This allows the repr(ebm) call to be omitted if the message is discarded

        except BufferError:
            logger.warning("Invalid message: too short?")
            return

        except ValueError as e:
            logger.warning("Invalid message: {e}".format(
                e=e,
            ))
            return

        process_frame(ebm)


def process_frame(ebm: ElcobusFrame):
    if not isinstance(ebm, ElcobusMessage):
        return
    if ebm.message_type not in {
            ElcobusMessage.MessageType.Info,
            ElcobusMessage.MessageType.Ret,
    }:
        return

    if ebm.field.name in {'boiler temperature', 'boiler set temperature', 'boiler return temperature',
                          'outdoor temperature',
                          'tap water temperature', 'tap water set temperature'}:
        mqtt_client.client.publish(args.mqtt_topic_prefix + '/' + ebm.field.name, ebm.data.temperature, qos=1)
    elif ebm.field.name in {'actual temperature', 'target temperature'}:
        circuit = ebm.logical_source - 32  # 33 => 1, 34 => 2
        mqtt_client.client.publish(args.mqtt_topic_prefix + '/' + ebm.field.name + f" {circuit}", ebm.data.temperature,
                                   qos=1)
    elif ebm.field.name in {'pump modulation', 'burner modulation'}:
        mqtt_client.client.publish(args.mqtt_topic_prefix + '/' + ebm.field.name, ebm.data.percent, qos=1)
    elif ebm.field.name == 'pressure':
        mqtt_client.client.publish(args.mqtt_topic_prefix + '/' + ebm.field.name, ebm.data.pressure, qos=1)
    elif ebm.field.name == 'status':
        mqtt_client.client.publish(args.mqtt_topic_prefix + '/' + ebm.field.name, ebm.data.status, qos=1)


async def poll_every(interval_secs: int, ebm: ElcobusMessage):
    await asyncio.sleep(random.randint(0, interval_secs))  # stagger the calls
    while True:
        await asyncio.sleep(interval_secs)
        mqtt_client.client.publish(mqtt_connection_details.topic + '/bus_tx', ebm.to_bytes(), qos=2)
        # Reply is automatically processed in process_frame, even if it is unsollicited

my_source = 0x01

# Do not poll boiler temperature: it is polled by the display of the boiler itself
loop.create_task(poll_every(
    60,
    ElcobusMessage(
        source_address=my_source, destination_address=0x00,
        message_type=ElcobusMessage.MessageType.Get,
        logical_source=0x3d, logical_destination=0x0d,
        field=find_field('boiler set temperature'),
    )
))
loop.create_task(poll_every(
    60,
    ElcobusMessage(
        source_address=my_source, destination_address=0x00,
        message_type=ElcobusMessage.MessageType.Get,
        logical_source=0x3d, logical_destination=0x11,
        field=find_field('boiler return temperature'),
    )
))
loop.create_task(poll_every(
    60,
    ElcobusMessage(
        source_address=my_source, destination_address=0x00,
        message_type=ElcobusMessage.MessageType.Get,
        logical_source=0x3d, logical_destination=0x05,
        field=find_field('outdoor temperature'),
    )
))
loop.create_task(poll_every(
    60,
    ElcobusMessage(
        source_address=my_source, destination_address=0x00,
        message_type=ElcobusMessage.MessageType.Get,
        logical_source=0x3d, logical_destination=0x31,
        field=find_field('tap water temperature'),
    )
))
loop.create_task(poll_every(
    60,
    ElcobusMessage(
        source_address=my_source, destination_address=0x00,
        message_type=ElcobusMessage.MessageType.Get,
        logical_source=0x3d, logical_destination=0x31,
        field=find_field('tap water set temperature'),
    )
))
loop.create_task(poll_every(
    60,
    ElcobusMessage(
        source_address=my_source, destination_address=0x00,
        message_type=ElcobusMessage.MessageType.Get,
        logical_source=0x3d, logical_destination=0x11,
        field=find_field('burner modulation'),
    )
))
loop.create_task(poll_every(
    60,
    ElcobusMessage(
        source_address=my_source, destination_address=0x00,
        message_type=ElcobusMessage.MessageType.Get,
        logical_source=0x3d, logical_destination=0x05,
        field=find_field('pump modulation'),
    )
))
loop.create_task(poll_every(
    600,  # pressure changes slowly
    ElcobusMessage(
        source_address=my_source, destination_address=0x00,
        message_type=ElcobusMessage.MessageType.Get,
        logical_source=0x3d, logical_destination=0x11,
        field=find_field('pressure'),
    )
))
loop.create_task(poll_every(
    60,
    ElcobusMessage(
        source_address=my_source, destination_address=0x00,
        message_type=ElcobusMessage.MessageType.Get,
        logical_source=0x3d, logical_destination=0x09,
        field=find_field('status'),
    )
))

for circuit in (1, 2):
    loop.create_task(poll_every(
        60,
        ElcobusMessage(
            source_address=my_source, destination_address=0x00,
            message_type=ElcobusMessage.MessageType.Get,
            logical_source=0x3d, logical_destination=0x20 + circuit,
            field=find_field('actual temperature'),
        )
    ))
    loop.create_task(poll_every(
        60,
        ElcobusMessage(
            source_address=my_source, destination_address=0x00,
            message_type=ElcobusMessage.MessageType.Get,
            logical_source=0x3d, logical_destination=0x20 + circuit,
            field=find_field('target temperature'),
        )
    ))


mqtt_client = MqttClient(mqtt_connection_details)
loop.run_until_complete(mqtt_client.main())
