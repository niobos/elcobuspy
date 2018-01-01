import pytest
from elcobus.ElcobusMessage.ElcobusFrame import ElcobusFrame, ElcobusMessage, UnknownFrame
from elcobus.ElcobusMessage._registry import find_field


def test_decode():
    d = b'\xdc\x80\x01\x0e\x07\x31\x3d\x07\x4b\x00\x0d\xc0\x3c\x29'
    f = ElcobusFrame.from_bytes(d)
    assert isinstance(f, ElcobusMessage)
    assert d == f.to_bytes()

def test_decode_too_long():
    d = b'\xdc\x80\x01\x0e\x07\x31\x3d\x07\x4b\x00\x0d\xc0\x3c\x29'
    f = ElcobusFrame.from_bytes(d)
    d2 = b'\xdc\x80\x01\x0e\x07\x31\x3d\x07\x4b\x00\x0d\xc0\x3c\x29\x00\x00'
    f2 = ElcobusFrame.from_bytes(d2)
    assert f == f2


def test_decode_invalid_crc():
    d = b'\xdc\x80\x01\x0e\x07\x31\x3d\x07\x4b\x00\x0d\xc0\x3c\x28'
    with pytest.raises(ValueError):
        f = ElcobusFrame.from_bytes(d)


def test_decode_too_short():
    d = b'\xdc\x80\x01\x0e\x07\x31\x3d\x07\x4b\x00\x0d\xc0\x3c'
    with pytest.raises(BufferError):
        f = ElcobusFrame.from_bytes(d)


def test_decode_way_too_short():
    d = b'\xdc'
    with pytest.raises(BufferError):
        f = ElcobusFrame.from_bytes(d)


def test_decode_data_too_short():
    d = b'\xdc\x80\x01\x05\x3c\x29'
    with pytest.raises(ValueError):
        f = ElcobusFrame.from_bytes(d)


def test_decode_unkn_type():
    d = b'\xdc\x80\x01\x0e\x0a\x31\x3d\x07\x4b\x00\x0d\xc0\x6a\x4d'
    f = ElcobusFrame.from_bytes(d)
    assert isinstance(f, UnknownFrame)
    assert d == f.to_bytes()


def test_encode():
    m = ElcobusMessage(
        source_address=0x01, destination_address=0x00,
        message_type=ElcobusMessage.MessageType.Get,
        logical_source=0x3d, logical_destination=0x0d,
        field=find_field('boiler temperature'),
    )
    assert m.to_bytes()
