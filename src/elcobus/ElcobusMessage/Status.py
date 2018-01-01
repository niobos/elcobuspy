import attr
import structattr
from structattr.types import Enum, UInt

from ._registry import register


@register({
    0x3034: 'status'
})
@structattr.add_methods
@attr.s(slots=True, auto_attribs=True)
class Status:
    class Zero(Enum(8)):
        Zero = 0
    flag: Zero = Zero.Zero

    class Status(UInt(8)):
        known_statuses = {
            0: 'idle',
            10: 'active on central heating',
            11: 'active on tap water',
        }

        def __repr__(self):
            try:
                return f"{self.known_statuses[self]} ({self})"
            except KeyError:
                return f"{self}"
    status: Status = 0


@register({
    0x07a1: 'tap water status',
    0x07a3: 'heating group 1',
    0x07a5: 'heating group 2',
    0x07a9: 'boiler',
    0x07ad: 'solar',
})
@structattr.add_methods
@attr.s(slots=True, auto_attribs=True)
class GroupStatus:
    class Status(UInt(8)):
        known_statuses = {
            0: '--',
            0x60: 'Laden, gew waarde',
            0x63: 'Geladen legio. temperatuur',
            0x66: 'Vloerverw functie actief',
            0x72: 'Verw. bedrijf comfort mod.',
            0x73: 'Uitschakeloptimalisering',
            0x7a: 'Ruimtetemp. begrensd',
        }

        def __repr__(self):
            try:
                return f"{self.known_statuses[self]} ({self})"
            except KeyError:
                return f"{self}"
    status: Status = 0
