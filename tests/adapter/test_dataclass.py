from inline_snapshot import snapshot
from inline_snapshot.extra import warns
from inline_snapshot.testing._example import Example


def test_unmanaged():

    Example(
        """\
from inline_snapshot import snapshot,Is
from dataclasses import dataclass

@dataclass
class A:
    a:int
    b:int

def test_something():
    assert A(a=2,b=4) == snapshot(A(a=1,b=Is(1))), "not equal"
"""
    ).run_inline(
        ["--inline-snapshot=fix"],
        changed_files=snapshot(
            {
                "test_something.py": """\
from inline_snapshot import snapshot,Is
from dataclasses import dataclass

@dataclass
class A:
    a:int
    b:int

def test_something():
    assert A(a=2,b=4) == snapshot(A(a=2,b=Is(1))), "not equal"
"""
            }
        ),
        raises=snapshot(
            """\
AssertionError:
not equal\
"""
        ),
    )


def test_reeval():
    Example(
        """\
from inline_snapshot import snapshot,Is
from dataclasses import dataclass

@dataclass
class A:
    a:int
    b:int

def test_something():
    for c in "ab":
        assert A(a=1,b=c) == snapshot(A(a=2,b=Is(c)))
"""
    ).run_inline(
        ["--inline-snapshot=fix"],
        changed_files=snapshot(
            {
                "test_something.py": """\
from inline_snapshot import snapshot,Is
from dataclasses import dataclass

@dataclass
class A:
    a:int
    b:int

def test_something():
    for c in "ab":
        assert A(a=1,b=c) == snapshot(A(a=1,b=Is(c)))
"""
            }
        ),
    )


def test_dataclass_default_value():
    Example(
        """\
from inline_snapshot import snapshot,Is
from dataclasses import dataclass,field

@dataclass
class A:
    a:int
    b:int=2
    c:list=field(default_factory=list)

def test_something():
    for _ in [1,2]:
        assert A(a=1) == snapshot(A(a=1,b=2,c=[]))
"""
    ).run_inline(
        ["--inline-snapshot=update"],
        changed_files=snapshot(
            {
                "test_something.py": """\
from inline_snapshot import snapshot,Is
from dataclasses import dataclass,field

@dataclass
class A:
    a:int
    b:int=2
    c:list=field(default_factory=list)

def test_something():
    for _ in [1,2]:
        assert A(a=1) == snapshot(A(a=1))
"""
            }
        ),
    )


def test_dataclass_positional_arguments():
    Example(
        """\
from inline_snapshot import snapshot,Is
from dataclasses import dataclass,field

@dataclass
class A:
    a:int
    b:int=2
    c:list=field(default_factory=list)

def test_something():
    for _ in [1,2]:
        assert A(a=1) == snapshot(A(1,2,c=[]))
"""
    ).run_inline(
        ["--inline-snapshot=update"],
        changed_files=snapshot(
            {
                "test_something.py": """\
from inline_snapshot import snapshot,Is
from dataclasses import dataclass,field

@dataclass
class A:
    a:int
    b:int=2
    c:list=field(default_factory=list)

def test_something():
    for _ in [1,2]:
        assert A(a=1) == snapshot(A(1,2))
"""
            }
        ),
    )


def test_attrs_default_value():
    Example(
        """\
from inline_snapshot import snapshot,Is
import attrs

@attrs.define
class A:
    a:int
    b:int=2
    c:list=attrs.field(factory=list)
    d:int=attrs.field(default=attrs.Factory(lambda self:self.a+10,takes_self=True))

def test_something():
    assert A(a=1) == snapshot(A(a=1,b=2,c=[],d=11))
    assert A(a=2,b=3) == snapshot(A(a=1,b=2,c=[],d=11))
"""
    ).run_pytest(
        ["--inline-snapshot=fix"],
        changed_files=snapshot(
            {
                "test_something.py": """\
from inline_snapshot import snapshot,Is
import attrs

@attrs.define
class A:
    a:int
    b:int=2
    c:list=attrs.field(factory=list)
    d:int=attrs.field(default=attrs.Factory(lambda self:self.a+10,takes_self=True))

def test_something():
    assert A(a=1) == snapshot(A(a=1,b=2,c=[],d=11))
    assert A(a=2,b=3) == snapshot(A(a=2,b=3,c=[],d=11))
"""
            }
        ),
    ).run_pytest(
        ["--inline-snapshot=update"],
        changed_files=snapshot(
            {
                "test_something.py": """\
from inline_snapshot import snapshot,Is
import attrs

@attrs.define
class A:
    a:int
    b:int=2
    c:list=attrs.field(factory=list)
    d:int=attrs.field(default=attrs.Factory(lambda self:self.a+10,takes_self=True))

def test_something():
    assert A(a=1) == snapshot(A(a=1))
    assert A(a=2,b=3) == snapshot(A(a=2,b=3))
"""
            }
        ),
    )


def test_attrs_field_repr():

    Example(
        """\
from inline_snapshot import snapshot
import attrs

@attrs.define
class container:
    a: int
    b: int = attrs.field(default=5,repr=False)

def test():
    assert container(a=1,b=5) == snapshot()
"""
    ).run_pytest(
        ["--inline-snapshot=create"],
        changed_files=snapshot(
            {
                "test_something.py": """\
from inline_snapshot import snapshot
import attrs

@attrs.define
class container:
    a: int
    b: int = attrs.field(default=5,repr=False)

def test():
    assert container(a=1,b=5) == snapshot(container(a=1))
"""
            }
        ),
    ).run_pytest()


def test_attrs_unmanaged():
    Example(
        """\
import datetime as dt
import uuid

import attrs

from dirty_equals import IsDatetime
from inline_snapshot import Is, snapshot


@attrs.define
class Attrs:
    ts: dt.datetime
    id: uuid.UUID

def test():
    id = uuid.uuid4()

    assert snapshot(Attrs(ts=IsDatetime(), id=Is(id))) == Attrs(
        dt.datetime.now(), id
    )
"""
    ).run_pytest(
        ["--inline-snapshot=create,fix"],
        changed_files=snapshot({}),
    ).run_pytest()


def test_disabled(executing_used):
    Example(
        """\
from inline_snapshot import snapshot
from dataclasses import dataclass

@dataclass
class A:
    a:int

def test_something():
    assert A(a=3) == snapshot(A(a=5)),"not equal"
"""
    ).run_inline(
        changed_files=snapshot({}),
        raises=snapshot(
            """\
AssertionError:
not equal\
"""
        ),
    )


def test_starred_warns():
    with warns(
        snapshot(
            [
                (
                    10,
                    "InlineSnapshotSyntaxWarning: star-expressions are not supported inside snapshots",
                )
            ]
        ),
        include_line=True,
    ):
        Example(
            """
from inline_snapshot import snapshot
from dataclasses import dataclass

@dataclass
class A:
    a:int

def test_something():
    assert A(a=3) == snapshot(A(**{"a":5})),"not equal"
"""
        ).run_inline(
            ["--inline-snapshot=fix"],
            raises=snapshot(
                """\
AssertionError:
not equal\
"""
            ),
        )


def test_add_argument():
    Example(
        """\
from inline_snapshot import snapshot
from dataclasses import dataclass

@dataclass
class A:
    a:int=0
    b:int=0
    c:int=0

def test_something():
    assert A(a=3,b=3,c=3) == snapshot(A(b=3)),"not equal"
"""
    ).run_inline(
        ["--inline-snapshot=fix"],
        changed_files=snapshot(
            {
                "test_something.py": """\
from inline_snapshot import snapshot
from dataclasses import dataclass

@dataclass
class A:
    a:int=0
    b:int=0
    c:int=0

def test_something():
    assert A(a=3,b=3,c=3) == snapshot(A(a = 3, b=3, c = 3)),"not equal"
"""
            }
        ),
        raises=snapshot(None),
    )


def test_positional_star_args():

    with warns(
        snapshot(
            [
                "InlineSnapshotSyntaxWarning: star-expressions are not supported inside snapshots"
            ]
        )
    ):
        Example(
            """\
from inline_snapshot import snapshot
from dataclasses import dataclass

@dataclass
class A:
    a:int

def test_something():
    assert A(a=3) == snapshot(A(*[],a=3)),"not equal"
"""
        ).run_inline(
            ["--inline-snapshot=report"],
        )


def test_remove_positional_argument():
    Example(
        """\
from inline_snapshot import snapshot

from inline_snapshot._adapter.generic_call_adapter import GenericCallAdapter,Argument


class L:
    def __init__(self,*l):
        self.l=l

    def __eq__(self,other):
        if not isinstance(other,L):
            return NotImplemented
        return other.l==self.l

class LAdapter(GenericCallAdapter):
    @classmethod
    def check_type(cls, typ):
        return issubclass(typ,L)

    @classmethod
    def arguments(cls, value):
        return ([Argument(x) for x in value.l],{})

    @classmethod
    def argument(cls, value, pos_or_name):
        assert isinstance(pos_or_name,int)
        return value.l[pos_or_name]

def test_L1():
    for _ in [1,2]:
        assert L(1,2) == snapshot(L(1)), "not equal"

def test_L2():
    for _ in [1,2]:
        assert L(1,2) == snapshot(L(1, 2, 3)), "not equal"

def test_L3():
    for _ in [1,2]:
        assert L(1,2) == snapshot(L(1, 2)), "not equal"
"""
    ).run_pytest(returncode=snapshot(1)).run_pytest(
        ["--inline-snapshot=fix"],
        changed_files=snapshot(
            {
                "test_something.py": """\
from inline_snapshot import snapshot

from inline_snapshot._adapter.generic_call_adapter import GenericCallAdapter,Argument


class L:
    def __init__(self,*l):
        self.l=l

    def __eq__(self,other):
        if not isinstance(other,L):
            return NotImplemented
        return other.l==self.l

class LAdapter(GenericCallAdapter):
    @classmethod
    def check_type(cls, typ):
        return issubclass(typ,L)

    @classmethod
    def arguments(cls, value):
        return ([Argument(x) for x in value.l],{})

    @classmethod
    def argument(cls, value, pos_or_name):
        assert isinstance(pos_or_name,int)
        return value.l[pos_or_name]

def test_L1():
    for _ in [1,2]:
        assert L(1,2) == snapshot(L(1, 2)), "not equal"

def test_L2():
    for _ in [1,2]:
        assert L(1,2) == snapshot(L(1, 2)), "not equal"

def test_L3():
    for _ in [1,2]:
        assert L(1,2) == snapshot(L(1, 2)), "not equal"
"""
            }
        ),
        returncode=snapshot(1),
    )


def test_namedtuple():
    Example(
        """\
from inline_snapshot import snapshot
from collections import namedtuple

T=namedtuple("T","a,b")

def test_tuple():
    assert T(a=1,b=2) == snapshot(T(a=1, b=3)), "not equal"
"""
    ).run_pytest(
        ["--inline-snapshot=fix"],
        changed_files=snapshot(
            {
                "test_something.py": """\
from inline_snapshot import snapshot
from collections import namedtuple

T=namedtuple("T","a,b")

def test_tuple():
    assert T(a=1,b=2) == snapshot(T(a=1, b=2)), "not equal"
"""
            }
        ),
    )


def test_defaultdict():
    Example(
        """\
from inline_snapshot import snapshot
from collections import defaultdict


def test_tuple():
    d=defaultdict(list)
    d[1].append(2)
    assert d == snapshot(defaultdict(list, {1: [3]})), "not equal"
"""
    ).run_pytest(
        ["--inline-snapshot=fix"],
        changed_files=snapshot(
            {
                "test_something.py": """\
from inline_snapshot import snapshot
from collections import defaultdict


def test_tuple():
    d=defaultdict(list)
    d[1].append(2)
    assert d == snapshot(defaultdict(list, {1: [2]})), "not equal"
"""
            }
        ),
    )


def test_dataclass_field_repr():

    Example(
        """\
from inline_snapshot import snapshot
from dataclasses import dataclass,field

@dataclass
class container:
    a: int
    b: int = field(default=5,repr=False)

assert container(a=1,b=5) == snapshot()
"""
    ).run_inline(
        ["--inline-snapshot=create"],
        changed_files=snapshot(
            {
                "test_something.py": """\
from inline_snapshot import snapshot
from dataclasses import dataclass,field

@dataclass
class container:
    a: int
    b: int = field(default=5,repr=False)

assert container(a=1,b=5) == snapshot(container(a=1))
"""
            }
        ),
    ).run_inline()


def test_dataclass_var():

    Example(
        """\
from inline_snapshot import snapshot,Is
from dataclasses import dataclass,field

@dataclass
class container:
    a: int

def test_list():
    l=container(5)
    assert l == snapshot(l), "not equal"
"""
    ).run_inline(
        ["--inline-snapshot=update"],
        changed_files=snapshot(
            {
                "test_something.py": """\
from inline_snapshot import snapshot,Is
from dataclasses import dataclass,field

@dataclass
class container:
    a: int

def test_list():
    l=container(5)
    assert l == snapshot(container(a=5)), "not equal"
"""
            }
        ),
    )
