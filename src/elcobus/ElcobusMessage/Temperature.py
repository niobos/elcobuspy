import attr
import structattr
from structattr.types import Enum, FixedPointSInt

from ._registry import register


@register({
    0x0519: 'boiler temperature',
    0x0923: 'boiler set temperature',
    0x051a: 'boiler return temperature',
    0x0521: 'outdoor temperature',
    0x052f: 'tap water temperature',
    0x074b: 'tap water set temperature',
})
@structattr.add_methods
@attr.s(slots=True, auto_attribs=True)
class Temperature:
    class Zero(Enum(8)):
        Zero = 0
    flag: Zero = Zero.Zero

    temperature: FixedPointSInt(total_bits=16, fractional_bits=6) = 0


@register({
    0x0215: 'room status',
})
@structattr.add_methods
@attr.s(slots=True, auto_attribs=True)
class RoomStatus:
    temperature: FixedPointSInt(total_bits=16, fractional_bits=6) = 0
    class Zero(Enum(8)):
        Zero = 0
    _unkn1: Zero = Zero.Zero
