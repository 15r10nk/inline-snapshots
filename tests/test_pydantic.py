from inline_snapshot import snapshot
from inline_snapshot.testing import Example


def test_pydantic_create_snapshot():

    Example(
        """
from pydantic import BaseModel
from inline_snapshot import snapshot

class M(BaseModel):
    size:int
    name:str
    age:int=4

def test_pydantic():
    m=M(size=5,name="Tom")
    assert m==snapshot()
    assert m.dict()==snapshot()

    """
    ).run_pytest(
        ["--inline-snapshot=create"],
        changed_files=snapshot(
            {
                "test_something.py": """\

from pydantic import BaseModel
from inline_snapshot import snapshot

class M(BaseModel):
    size:int
    name:str
    age:int=4

def test_pydantic():
    m=M(size=5,name="Tom")
    assert m==snapshot(M(size=5, name="Tom"))
    assert m.dict()==snapshot({"size": 5, "name": "Tom", "age": 4})

    \
"""
            }
        ),
    ).run_pytest(
        ["--inline-snapshot=disable"]
    )


def test_pydantic_field_repr():

    Example(
        """\
from inline_snapshot import snapshot
from pydantic import BaseModel,Field

class container(BaseModel):
    a: int
    b: int = Field(default=5,repr=False)

def test():
    assert container(a=1,b=5) == snapshot()
"""
    ).run_pytest(
        ["--inline-snapshot=create"],
        changed_files=snapshot(
            {
                "test_something.py": """\
from inline_snapshot import snapshot
from pydantic import BaseModel,Field

class container(BaseModel):
    a: int
    b: int = Field(default=5,repr=False)

def test():
    assert container(a=1,b=5) == snapshot(container(a=1))
"""
            }
        ),
    ).run_pytest(
        ["--inline-snapshot=disable"]
    )


def test_pydantic_default_value():
    Example(
        """\
from inline_snapshot import snapshot,Is
from dataclasses import dataclass,field
from pydantic import BaseModel,Field

class A(BaseModel):
    a:int
    b:int=2
    c:list=Field(default_factory=list)

def test_something():
    assert A(a=1) == snapshot(A(a=1,b=2,c=[]))
"""
    ).run_pytest(
        ["--inline-snapshot=update"],
        changed_files=snapshot(
            {
                "test_something.py": """\
from inline_snapshot import snapshot,Is
from dataclasses import dataclass,field
from pydantic import BaseModel,Field

class A(BaseModel):
    a:int
    b:int=2
    c:list=Field(default_factory=list)

def test_something():
    assert A(a=1) == snapshot(A(a=1))
"""
            }
        ),
    )


def test_pydantic_evaluate_twice():
    Example(
        """\
from inline_snapshot import snapshot
from pydantic import BaseModel

class A(BaseModel):
    a:int

def test_something():
    for _ in [1,2]:
        assert A(a=1) == snapshot(A(a=1))
"""
    ).run_pytest(
        changed_files=snapshot({}),
    )


def test_pydantic_factory_method():
    Example(
        """\
from inline_snapshot import snapshot
from pydantic import BaseModel

class A(BaseModel):
    a:int

    @classmethod
    def from_str(cls,s):
        return cls(a=int(s))

def test_something():
    for a in [1,2]:
        assert A(a=2) == snapshot(A.from_str("1"))
"""
    ).run_pytest(
        ["--inline-snapshot=fix"],
        changed_files=snapshot(
            {
                "test_something.py": """\
from inline_snapshot import snapshot
from pydantic import BaseModel

class A(BaseModel):
    a:int

    @classmethod
    def from_str(cls,s):
        return cls(a=int(s))

def test_something():
    for a in [1,2]:
        assert A(a=2) == snapshot(A(a=2))
"""
            }
        ),
    )
