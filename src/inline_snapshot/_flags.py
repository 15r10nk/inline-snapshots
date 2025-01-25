from __future__ import annotations

from typing import Set
from typing import cast

from ._types import Category


class Flags:
    """
    fix: the value needs to be changed to pass the tests
    update: the value should be updated because the token-stream has changed
    create: the snapshot is empty `snapshot()`
    trim: the snapshot contains more values than neccessary. 1 could be trimmed in `5 in snapshot([1,5])`.
    """

    def __init__(self, flags: set[Category] = set()):
        self.create = "create" in flags
        self.fix = "fix" in flags
        self.trim = "trim" in flags
        self.update = "update" in flags

    def to_set(self) -> set[Category]:
        return cast(Set[Category], {k for k, v in self.__dict__.items() if v})

    def __iter__(self):
        return (k for k, v in self.__dict__.items() if v)

    def __repr__(self):
        return f"Flags({self.to_set()})"

    @staticmethod
    def all() -> Flags:
        return Flags({"fix", "create", "update", "trim"})
