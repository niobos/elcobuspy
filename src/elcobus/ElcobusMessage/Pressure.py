import attr
import structattr
from structattr.types import Enum, FixedPointSInt

from ._registry import register


@register({
    0x3063: 'pressure',
})
@structattr.add_methods
@attr.s(slots=True, auto_attribs=True)
class Pressure:
    class Zero(Enum(8)):
        Zero = 0
    flag: Zero = Zero.Zero

    pressure: FixedPointSInt(total_bits=16, scale_factor=0.1) = 0
