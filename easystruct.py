import struct
from array import array
from collections.abc import Callable, Collection, Iterable
from typing import NamedTuple

__all__ = ["StructDefItem", "EasyStruct"]


class StructDefItem(NamedTuple):
    name: str
    type_code: str  # whatever struct.pack supports
    value: object
    write_modifier: Callable[[float | int], int] | None
    read_modifier: Callable[[int], float | int] | None


class EasyStruct:
    def __init__(
        self,
        structdef: Collection[StructDefItem],
        buf: array | bytes | bytearray | Iterable[int] | None = None,
        **kwargs: int,
    ) -> None:
        # Create dynamically the attribs, the format string, and fill it
        # with the default values

        self.structdef: Collection[StructDefItem] = structdef

        self.fmt: str = "="

        for attr, tp, defv, _mod, _mod1 in structdef:
            if not hasattr(self, attr):
                raise ValueError("Unknown arguments given", attr)
            setattr(self, attr, defv)
            self.fmt += tp

        if buf is not None:
            # if a buf is given, use its values to fill the structure
            assert kwargs == {}, "if kwargs are given, buf must be None"
            self.read_bytes(buf)
        else:
            # fill the values from kwargs, only the values that belong to the new class
            # do not create new arguments
            for key in kwargs:
                if hasattr(self, key):
                    setattr(self, key, kwargs[key])
                else:
                    raise ValueError("Unknown arguments given", key)

    def read_bytes(self, buf: array | bytes | bytearray | Iterable[int]) -> None:
        """Fill the attributes using the values given in buf."""
        if isinstance(buf, tuple):
            buf = array("B", buf)
        upk = struct.unpack(self.fmt, buf)

        for val, attr in zip(upk, self.structdef, strict=True):
            a, tp, defv, mod, mod1 = attr
            if not hasattr(self, attr.name):
                raise ValueError("Unknown arguments given", a)
            if mod1 is None:
                setattr(self, a, val)
            else:
                setattr(self, a, mod1(val))

    def to_bytes(self) -> bytes:
        bl: list[int] = []
        for attr in self.structdef:
            if attr.write_modifier is None:
                bl.append(getattr(self, attr.name))
            else:
                bl.append(attr.write_modifier(getattr(self, attr.name)))

        return struct.pack(self.fmt, *bl)

    def __repr__(self) -> str:
        props: list[str] = []
        for attr in self.structdef:
            props.append(f"{attr.name}={getattr(self, attr.name)!r}")
        return self.__class__.__name__ + "(" + ", ".join(props) + ")"
