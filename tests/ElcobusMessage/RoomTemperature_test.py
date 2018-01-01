import pytest
from elcobus.ElcobusMessage.ElcobusFrame import ElcobusFrame, ElcobusMessage
from elcobus.ElcobusMessage.Pressure import Pressure


def test_decode():
    d = b'\xdc\x86\x00\x0e\x02\x3d\x2d\x02\x15\x05\x78\x00\x93\xef'
    f = ElcobusFrame.from_bytes(d)
    assert d == f.to_bytes()
    assert f.message_type == ElcobusMessage.MessageType.Info
    assert f.data.temperature == 21.875
