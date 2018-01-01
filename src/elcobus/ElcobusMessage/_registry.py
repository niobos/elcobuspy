from typing import Dict, Union

import attr


field_registry = {}


@attr.s(slots=True, auto_attribs=True, str=False, repr=False)
class Item:
    field: int
    name: str
    value_type: type

    def __int__(self) -> int:
        return self.field

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<{self.name}: 0x{self.field:04x}>"


def register(field_values: Dict[int, str]):
    """
    Decorator
    """
    def register_(value_type: type):
        for field_value, name in field_values.items():
            field_registry[field_value] = Item(field=field_value, name=name, value_type=value_type)
        return value_type
    return register_


def find_field(description: str) -> Union[int, None]:
    for field in field_registry.keys():
        if field_registry[field].name == description:
            return field_registry[field]
    raise ValueError(f"field `{description}` not found")
