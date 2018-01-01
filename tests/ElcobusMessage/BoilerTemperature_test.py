import pytest
from elcobus.ElcobusMessage.ElcobusFrame import ElcobusFrame
from elcobus.ElcobusMessage.Temperature import Temperature


def test_decode():
    d = b'\xdc\x80\x0a\x0e\x07\x0d\x3d\x05\x19\x00\x0d\xf6\x46\x0e'
    f = ElcobusFrame.from_bytes(d)
    assert d == f.to_bytes()
    assert f.data.temperature == 55.84375
