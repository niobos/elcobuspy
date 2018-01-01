import attr
import bitstruct
import crcmod
import structattr
from structattr.types import UInt, Enum, Bool, Zero, One
from typing import Union

from ._registry import field_registry


crc_func = crcmod.mkCrcFun(0x11021, initCrc=0, xorOut=0, rev=False)


class ElcobusFrame:
    __slots__ = ()

    @classmethod
    def from_bytes(cls, frame: Union[bytes, bytearray]) -> Union['ElcobusMessage', 'UnknownFrame']:
        """
        Attempts to parse the given `frame`

        if `frame` supports item deletion (`del frame[0:5]`), the parsed bytes
        are removed from `frame`.

        :param frame: byte sequence to parse
        :raises BufferError when the message is incomplete
        :raises ValueError when the message is invalid
        :return: The decoded ElcobusMessage, or UnknownFrame
        """
        if len(frame) < 4:
            raise BufferError("Not enough data to decode message")

        dlen = frame[3]
        if dlen < 4+2:
            raise ValueError("Invalid message: length can't be < 6")
        if dlen > 32:  # largest seen is 27
            raise ValueError("Invalid message: length > 32")

        if len(frame) < dlen:
            raise BufferError("Not enough data to decode message")

        crc_actual, = bitstruct.unpack(">u16", frame[(dlen-2):dlen])
        crc_should = crc_func(frame[0:(dlen-2)])

        if crc_actual != crc_should:
            raise ValueError(f"CRC mismatch, got 0x{crc_actual:04x}, expected 0x{crc_should:04x}")

        this_frame = frame[0:(dlen-2)]
        try:
            del frame[0:dlen]
        except TypeError:
            # message is bytes, not bytearray. ignore
            pass

        try:
            return ElcobusMessage.from_bytes(this_frame)
        except ValueError as e:
            return UnknownFrame(header=this_frame[0:3], data=this_frame[4:])


@attr.s(slots=True)
class ElcobusMessage(ElcobusFrame):
    class StartOfFrame(Enum(6)):
        StartOfFrame = 0xdc >> 2
    _start_of_frame = attr.ib(type=StartOfFrame, default=StartOfFrame.StartOfFrame)
    _unkn1 = attr.ib(type=Bool, default=False)
    _const1 = attr.ib(type=Zero, default=Zero.Zero)

    _const2 = attr.ib(type=One, default=One.One)
    source_address = attr.ib(type=UInt(7), default=0)

    _const3 = attr.ib(type=Zero, default=Zero.Zero)
    destination_address = attr.ib(type=UInt(7), default=0)

    # length, implicit

    class MessageType(Enum(8)):
        Info = 2
        Set = 3
        Ack = 4
        Get = 6
        Ret = 7
    message_type = attr.ib(type=MessageType, default=MessageType.Info)

    logical_source = attr.ib(type=UInt(8), default=0)
    logical_destination = attr.ib(type=UInt(8), default=0)

    field = attr.ib(type=UInt(16), default=0)

    data = attr.ib(default=None)

    # crc, implicit

    @classmethod
    def from_bytes(cls, frame: bytes) -> 'ElcobusMessage':
        attributes = attr.fields(cls)

        bitstruct_info = structattr.BitStructInfo()
        for attribute in attributes[0:7]:
            bitstruct_info.add_attr(attribute)

        header_fields = structattr.deserialize(
            frame[0:3],
            bitstruct_info
        )

        bitstruct_info = structattr.BitStructInfo()
        for attribute in attributes[7:11]:
            bitstruct_info.add_attr(attribute)

        body_fields = structattr.deserialize(
            frame[4:9],
            bitstruct_info,
        )

        structattr.strip_leading_underscore(header_fields)
        structattr.strip_leading_underscore(body_fields)

        msg = cls(**header_fields, **body_fields)

        if msg.message_type in (
            ElcobusMessage.MessageType.Info,
            ElcobusMessage.MessageType.Set,
            ElcobusMessage.MessageType.Ret
        ):
            msg.data = frame[9:]

            try:
                candidate = field_registry[msg.field]
                msg.data = candidate.value_type.from_bytes(msg.data)
                msg.field = candidate
            except (KeyError, ValueError):
                pass
        else:
            try:
                msg.field = field_registry[msg.field]
            except KeyError:
                pass
            if len(frame) > 9:
                raise ValueError("Data found on Ack or Get packet")

        return msg

    def to_bytes(self) -> bytes:
        attributes = attr.fields(self.__class__)

        bitstruct_info = structattr.BitStructInfo()
        header_fields = []
        for attribute in attributes[0:7]:
            bitstruct_info.add_attr(attribute)
            header_fields.append(getattr(self, attribute.name))

        header_fields = structattr.serialize(
            header_fields,
            bitstruct_info
        )

        bitstruct_info = structattr.BitStructInfo()
        body_fields = []
        for attribute in attributes[7:11]:
            bitstruct_info.add_attr(attribute)
            body_fields.append(getattr(self, attribute.name))

        body_fields = structattr.serialize(
            body_fields,
            bitstruct_info
        )

        data = bytearray()
        data += header_fields

        dlen = len(header_fields) + 1 + len(body_fields) + 2
        if self.data is not None:
            dlen += len(self.data)
        data += bytes([dlen])

        data += body_fields

        if self.data is None:
            pass
        elif isinstance(self.data, bytes) or isinstance(self.data, bytearray):
            data += self.data
        else:
            data += self.data.to_bytes()

        crc = crc_func(data)
        data += bitstruct.pack(">u16", crc)

        return data


@attr.s(slots=True, auto_attribs=True)
class UnknownFrame(ElcobusFrame):
    header: bytes
    data: bytes

    def to_bytes(self) -> bytes:
        result = bytearray()
        result += self.header
        result += bytes([len(self.header) + 1 + len(self.data) + 2])
        result += self.data
        crc = crc_func(result)
        result += bitstruct.pack(">u16", crc)
        return result
