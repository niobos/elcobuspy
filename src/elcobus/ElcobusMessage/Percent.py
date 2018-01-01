import attr
import structattr
from structattr.types import Enum, UInt

from ._registry import register


@register({
    0x305f: 'burner modulation',
    0x04a2: 'pump modulation',
})
@structattr.add_methods
@attr.s(slots=True, auto_attribs=True)
class Percent:
    class Zero(Enum(8)):
        Zero = 0
    flag: Zero = Zero.Zero

    percent: UInt(8) = 0
