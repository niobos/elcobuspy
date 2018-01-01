import asyncio
import concurrent
import inspect
import logging
from typing import Set

from .ElcobusMessage.ElcobusFrame import ElcobusFrame, UnknownFrame, ElcobusMessage

logger = logging.getLogger(__name__)


def format_sockaddr(sockaddr):
    if len(sockaddr) == 4:  # IPv6
        return "[{h}]:{p}".format(
            h=sockaddr[0],
            p=sockaddr[1],
        )
    elif len(sockaddr) == 2:  # IPv4
        return "{h}:{p}".format(
            h=sockaddr[0],
            p=sockaddr[1],
        )
    else:
        raise TypeError("Unknown sockaddr format: {}".format(sockaddr))


class ElcobusProtocol(asyncio.Protocol):
    serial_client: 'ElcobusProtocol' = None
    tcp_clients: 'Set[ElcobusProtocol]' = set()
    listeners = set()

    def connection_made(self, transport):
        self.transport = transport
        self.rx_buf = bytearray()
        logger.info("{p} : new connection".format(
            p=self.client_id
        ))

    def connection_lost(self, exc):
        logger.info("{cid} : connection closed{dr}".format(
            cid=self.client_id,
            dr=" with {} bytes unparsed".format(len(self.rx_buf)) if self.rx_buf else "",
        ))

    def data_received(self, data: bytearray):
        logger.debug("{cid} : Buf=[{b}], Rx=[{d}]".format(
            cid=self.client_id,
            b=' '.join(["{:02x}".format(b) for b in self.rx_buf]),
            d=' '.join(["{:02x}".format(b) for b in data])
        ))
        self.rx_buf.extend(data)
        self.try_decode()

    def try_decode(self):
        while self.rx_buf:
            try:
                ebm = ElcobusFrame.from_bytes(self.rx_buf)

                self.process_message(ebm)

            except BufferError:
                break

            except ValueError as e:
                logger.warning("{cid} : Invalid message, discarding 1 byte (0x{b:02x}): {e}".format(
                    cid=self.client_id, b=self.rx_buf[0],
                    e=e,
                ))
                del self.rx_buf[0:1]
                continue

    def process_message(self, ebm: ElcobusFrame):
        """
        Process a single message from this connection.
        This should usually relay the message, but you can filter messages here
        """
        logger.info("{cid} : EBM: [{m}]".format(
            cid=self.client_id,
            m=' '.join(['{:02x}'.format(b) for b in ebm.to_bytes()]),
        ))
        logger.debug("%s : EBM: %r", self.client_id, ebm)
        # ^^ don't use ''.format()
        # This allows the repr(ebm) call to be omitted if the message is discarded

        if self != ElcobusProtocol.serial_client and isinstance(ebm, UnknownFrame):
            pass  # don't relay unknown messages from TCP. Just to be safe
        else:
            return self.relay_message(ebm)

    def relay_message(self, ebm: ElcobusFrame):
        data = ebm.to_bytes()

        # Order of relaying logic:
        #  - Serial first. Serial is the slowest output. Send there first
        #    so by the time that the rest is sent, Serial is hopefully done by then
        #  - TCP next
        #  - listeners (potentially even async)

        if ElcobusProtocol.serial_client != self:  # don't loop back
            ElcobusProtocol.serial_client.transport.write(data)

        for c in ElcobusProtocol.tcp_clients:
            if c != self:  # Don't loop back
                c.transport.write(data)

        for l in ElcobusProtocol.listeners:
            _ = l(ebm)
            if inspect.isawaitable(_):
                asyncio.ensure_future(_)

    async def query(
        self,
        ebm_question: ElcobusMessage,
        timeout: int = 2,
    ) -> ElcobusMessage:
        """
        Send a message on the bus and expect an answer

        :param ebm_question: message to send
        :param timeout: Timeout in seconds
        :return: The Message
        :raises: TimeoutError
        :raises: ValueError if the message is not a questien
        """
        if ebm_question.message_type not in (
            ElcobusMessage.MessageType.Set,
            ElcobusMessage.MessageType.Get,
        ):
            raise ValueError("Question is not Set or Get")

        reply = asyncio.get_event_loop().create_future()

        def message_filter(ebm: ElcobusFrame):
            if not isinstance(ebm, ElcobusMessage):
                return
            if ebm.source_address != ebm_question.destination_address or \
                    ebm.destination_address != ebm_question.source_address:
                return

            if ebm_question.message_type == ElcobusMessage.MessageType.Set and \
                    ebm.message_type != ElcobusMessage.MessageType.Ack:
                return
            if ebm_question.message_type == ElcobusMessage.MessageType.Get and \
                    ebm.message_type != ElcobusMessage.MessageType.Ret:
                return

            if ebm_question.field != ebm.field:
                return

            reply.set_result(ebm)

        self.listeners.add(message_filter)

        self.process_message(ebm_question)

        try:
            await asyncio.wait_for(reply, timeout)
            return reply.result()
        except concurrent.futures._base.TimeoutError:
            raise TimeoutError
        finally:
            self.listeners.remove(message_filter)


class ElcobusTcpProtocol(ElcobusProtocol):
    def connection_made(self, transport):
        self.client_id = "TCP:" + format_sockaddr(transport.get_extra_info('peername'))
        super().connection_made(transport)
        ElcobusProtocol.tcp_clients.add(self)

    def connection_lost(self, exc):
        super().connection_lost(exc)
        ElcobusProtocol.tcp_clients.remove(self)

    def pause_writing(self):
        logger.warning("{} : buffer full, dropping connection".format(
            self.client_id,
        ))
        self.transport.abort()


class ElcobusSerialProtocol(ElcobusProtocol):
    def connection_made(self, transport):
        ElcobusProtocol.serial_client = self
        self.client_id = "SERIAL"
        super().connection_made(transport)

    def connection_lost(self, exc):
        super().connection_lost(exc)
        ElcobusProtocol.serial_client = None
        asyncio.get_event_loop().stop()


class ElcobusHttpProtocol(ElcobusProtocol):
    def __init__(self, request):
        self.client_id = "HTTP:{ip}:{port}{path}".format(
            ip=request.ip,
            port=request.port,
            path=request.path
        )
