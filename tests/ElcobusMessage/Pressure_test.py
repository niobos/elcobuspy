import pytest
from elcobus.ElcobusMessage.ElcobusFrame import ElcobusFrame
from elcobus.ElcobusMessage.Pressure import Pressure


def test_decode():
    d = b'\xdc\x80\x01\x0e\x07\x11\x3d\x30\x63\x00\x00\x0a\x85\x32'
    f = ElcobusFrame.from_bytes(d)
    assert d == f.to_bytes()
    assert isinstance(f.data, Pressure)
    assert f.data.pressure == 1.0
