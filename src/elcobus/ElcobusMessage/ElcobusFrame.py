import enum

import attr
import bitstruct
import crcmod
import structattr
from structattr.types import UInt, Enum, Bool, Zero, One, FixedPointSInt
from typing import Union


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

        # skip length

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

        try:
            msg.field = Field(msg.field)
        except ValueError:
            pass

        if msg.message_type in (
            ElcobusMessage.MessageType.Info,
            ElcobusMessage.MessageType.Set,
            ElcobusMessage.MessageType.Ret
        ):
            msg.data = frame[9:]

            try:
                candidate = msg.field.data_type
                msg.data = candidate.from_bytes(msg.data)
            except (AttributeError, ValueError):
                pass
        else:
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


@structattr.add_methods
@attr.s(slots=True, auto_attribs=True)
class Temperature:
    class Zero(Enum(8)):
        Zero = 0
    flag: Zero = Zero.Zero

    temperature: FixedPointSInt(total_bits=16, fractional_bits=6) = 0


@structattr.add_methods
@attr.s(slots=True, auto_attribs=True)
class RoomStatus:
    temperature: FixedPointSInt(total_bits=16, fractional_bits=6) = 0
    class Zero(Enum(8)):
        Zero = 0
    _unkn1: Zero = Zero.Zero


@structattr.add_methods
@attr.s(slots=True, auto_attribs=True)
class Pressure:
    class Zero(Enum(8)):
        Zero = 0
    flag: Zero = Zero.Zero

    pressure: FixedPointSInt(total_bits=16, scale_factor=0.1) = 0


@structattr.add_methods
@attr.s(slots=True, auto_attribs=True)
class Percent:
    class Zero(Enum(8)):
        Zero = 0
    flag: Zero = Zero.Zero

    percent: UInt(8) = 0


@structattr.add_methods
@attr.s(slots=True, auto_attribs=True)
class Status:
    class Zero(Enum(8)):
        Zero = 0
    flag: Zero = Zero.Zero
    status: UInt(8) = 0


class Field(int, enum.Enum):
    def __new__(cls, value: int, data_type: type):
        o = int.__new__(cls, value)
        o._value_ = value
        o.data_type = data_type
        return o

    RoomStatus = (0x0215, RoomStatus)
    OutdoorTemperature = (0x0521, Temperature)
    BoilerTemperature = (0x0519, Temperature)
    BoilerSetTemperature = (0x0923, Temperature)
    BoilerReturnTemperature = (0x051a, Temperature)
    TapWaterTemperature = (0x052f, Temperature)
    TapWaterSetTemperature = (0x074b, Temperature)
    HeatingCircuitTemperature = (0x0518, Temperature)  # note: logical address denote circuits: 0x20 + circuit number
    HeatingCircuitSetTemperature = (0x0667, Temperature)  # note: logical address denote circuits: 0x20 + circuit number
    Pressure = (0x3063, Pressure)
    BurnerMoludation = (0x305f, Percent)
    PumpModulation = (0x04a2, Percent)
    Status = (0x3034, Status)
