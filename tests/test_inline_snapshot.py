import contextlib
import itertools
import warnings
from collections import namedtuple
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Union

import pytest

from inline_snapshot import snapshot
from inline_snapshot._flags import Flags
from inline_snapshot.testing import Example
from inline_snapshot.testing._example import snapshot_env


@pytest.mark.no_rewriting
def test_snapshot_eq():
    with snapshot_env():
        assert 1 == snapshot(1)
        assert snapshot(1) == 1


@pytest.mark.no_rewriting
def test_disabled():
    with snapshot_env() as state:
        state.active = False
        with pytest.raises(AssertionError) as excinfo:
            assert 2 == snapshot()

    assert str(excinfo.value) == snapshot(
        "your snapshot is missing a value run pytest with --inline-snapshot=create"
    )


operation = namedtuple("operation", "value,op,svalue,fvalue,flag")
operations = [
    # compare
    operation("4", "==", "", "4", "create"),
    operation("4", "==", "5", "4", "fix"),
    operation("4", "==", "2+2", "4", "update"),
    # leq
    operation("4", "<=", "", "4", "create"),
    operation("4", "<=", "5", "4", "trim"),
    operation("5", "<=", "4", "5", "fix"),
    operation("5", "<=", "3+2", "5", "update"),
    # geq
    operation("5", ">=", "", "5", "create"),
    operation("5", ">=", "4", "5", "trim"),
    operation("4", ">=", "5", "4", "fix"),
    operation("5", ">=", "3+2", "5", "update"),
    # contains
    operation("5", "in", "", "[5]", "create"),
    operation("5", "in", "[4, 5]", "[5]", "trim"),
    operation("5", "in", "[]", "[5]", "fix"),
    operation("5", "in", "[3+2]", "[5]", "update"),
]


def test_generic(source, subtests, executing_used):
    codes = []

    for op in operations:
        codes.append((f"assert {op.value} {op.op} snapshot({op.svalue})", op.flag))
        if op.svalue:
            codes.append(
                (
                    f"assert {op.value} {op.op} snapshot({{0: {op.svalue}}})[0]",
                    op.flag,
                )
            )
        else:
            codes.append((f"assert {op.value} {op.op} snapshot({{}})[0]", op.flag))

    all_flags = ["trim", "fix", "create", "update"]

    for code, reported_flag in codes:
        with subtests.test(code):
            s = source(code)
            print("source:", code)

            if not executing_used and reported_flag == "update":
                assert not s.flags
            else:
                assert list(s.flags) == [reported_flag]

            assert (reported_flag == "fix") == s.error

            for flag in all_flags:
                if flag == reported_flag:
                    continue
                print("use flag:", flag)
                s2 = s.run(flag)
                assert s2.source == s.source

            if not executing_used:
                continue

            s2 = s.run(reported_flag)
            assert s2.flags == {reported_flag}

            s3 = s2.run(*all_flags)
            assert s3.flags == set()
            assert s3.source == s2.source


@pytest.mark.parametrize(
    "ops",
    [
        pytest.param(ops, id=" ".join(f"{op.flag}({op.op})" for op in ops))
        for ops in itertools.combinations(operations, 2)
    ],
)
def test_generic_multi(source, subtests, ops, executing_used):

    def gen_code(ops, fixed, old_keys):
        keys = old_keys + [k for k in range(len(ops)) if k not in old_keys]
        new_keys = []

        args = []
        print(keys)
        for k in keys:
            op = ops[k]
            value = op.fvalue if op.flag in fixed else op.svalue
            if value:
                args.append(f'"k_{k}": {value}')
                new_keys.append(k)
        args = ", ".join(args)

        code = "s = snapshot({" + args + "})\n"

        for k, op in enumerate(ops):
            code += f'print({op.value} {op.op} s["k_{k}"]) # {op.flag} {op.svalue or "<undef>"} -> {op.fvalue}\n'

        return code, new_keys

    all_flags = {op.flag for op in ops}

    keys = []
    code, keys = gen_code(ops, {}, keys)
    s = source(code)

    assert s.flags == all_flags - ({"update"} if not executing_used else set())

    if executing_used:
        for flags in itertools.permutations(all_flags):
            with subtests.test(" ".join(flags)):
                s2 = s
                fixed_flags = set()
                for flag in flags:

                    s2 = s2.run(flag)
                    fixed_flags.add(flag)
                    code, keys = gen_code(ops, fixed_flags, keys)
                    assert s2.source == code

                    s2 = s2.run()
                    assert s2.flags == all_flags - fixed_flags

    for flag in {"update", "fix", "trim", "create"} - all_flags:
        with subtests.test(f"ignore {flag}"):
            s2 = s.run(flag)
            assert s2.source == s.source


def test_mutable_values(check_update):
    assert (
        check_update(
            """
l=[1,2]
assert l==snapshot()
l.append(3)
assert l==snapshot()
    """,
            flags="create",
            number=2,
        )
        == snapshot(
            """\

l=[1,2]
assert l==snapshot([1, 2])
l.append(3)
assert l==snapshot([1, 2, 3])
"""
        )
    )

    assert (
        check_update(
            """
l=[1,2]
assert l<=snapshot()
l.append(3)
assert l<=snapshot()
    """,
            flags="create",
            number=2,
        )
        == snapshot(
            """\

l=[1,2]
assert l<=snapshot([1, 2])
l.append(3)
assert l<=snapshot([1, 2, 3])
"""
        )
    )

    assert (
        check_update(
            """
l=[1,2]
assert l>=snapshot()
l.append(3)
assert l>=snapshot()
    """,
            flags="create",
            number=2,
        )
        == snapshot(
            """\

l=[1,2]
assert l>=snapshot([1, 2])
l.append(3)
assert l>=snapshot([1, 2, 3])
"""
        )
    )

    assert (
        check_update(
            """
l=[1,2]
assert l in snapshot()
l.append(3)
assert l in snapshot()
    """,
            flags="create",
            number=2,
        )
        == snapshot(
            """\

l=[1,2]
assert l in snapshot([[1, 2]])
l.append(3)
assert l in snapshot([[1, 2, 3]])
"""
        )
    )


def test_comparison(check_update):
    assert check_update("assert 5==snapshot()", flags="create") == snapshot(
        "assert 5==snapshot(5)"
    )

    assert check_update("assert 5==snapshot(9)", flags="fix") == snapshot(
        "assert 5==snapshot(5)"
    )

    assert check_update('assert "a"==snapshot("""a""")', flags="update") == snapshot(
        'assert "a"==snapshot("a")'
    )

    assert check_update(
        'assert "a"==snapshot("""a""")', reported_flags="update", flags="fix"
    ) == snapshot('assert "a"==snapshot("""a""")')

    assert (
        check_update(
            """
            for a in [1,1,1]:
                assert a==snapshot()
            """,
            flags="create",
        )
        == snapshot(
            """\

for a in [1,1,1]:
    assert a==snapshot(1)
"""
        )
    )

    assert (
        check_update(
            """
            for a in [1,1,1]:
                assert a==snapshot(2)
            """,
            flags="fix",
        )
        == snapshot(
            """\

for a in [1,1,1]:
    assert a==snapshot(1)
"""
        )
    )


def test_ge(check_update):
    assert check_update("assert 5<=snapshot()", flags="create") == snapshot(
        "assert 5<=snapshot(5)"
    )

    assert check_update("assert 5<=snapshot()", reported_flags="create") == snapshot(
        "assert 5<=snapshot()"
    )

    assert (
        check_update(
            """
s=snapshot({"v": 7, "q": 4})
assert 5<=s["v"]
assert 5==s["q"]
""",
            flags="fix",
            reported_flags="fix,trim",
        )
        == snapshot(
            """\

s=snapshot({"v": 7, "q": 5})
assert 5<=s["v"]
assert 5==s["q"]
"""
        )
    )

    assert (
        check_update(
            """
s=snapshot({"q": 4})
assert 5<=s["v"]
assert 5==s["q"]
""",
            flags="fix",
            reported_flags="fix,create",
        )
        == snapshot(
            """\

s=snapshot({"q": 5})
assert 5<=s["v"]
assert 5==s["q"]
"""
        )
    )

    assert check_update("assert 5<=snapshot(9)", flags="trim") == snapshot(
        "assert 5<=snapshot(5)"
    )

    assert check_update("assert 5<=snapshot(3)", flags="fix") == snapshot(
        "assert 5<=snapshot(5)"
    )

    assert check_update("assert snapshot(3) >= 5", flags="fix") == snapshot(
        "assert snapshot(5) >= 5"
    )

    assert check_update("assert 5<=snapshot(5)") == snapshot("assert 5<=snapshot(5)")

    assert check_update(
        "for i in range(5): assert i <=snapshot(2)", flags="fix"
    ) == snapshot("for i in range(5): assert i <=snapshot(4)")

    assert check_update(
        "for i in range(5): assert i <=snapshot(10)", flags="trim"
    ) == snapshot("for i in range(5): assert i <=snapshot(4)")


def test_le(check_update):
    assert check_update("assert 5>=snapshot()", flags="create") == snapshot(
        "assert 5>=snapshot(5)"
    )

    assert (
        check_update(
            """
s=snapshot({"v": 3, "q": 4})
assert 5>=s["v"]
assert 5==s["q"]
""",
            flags="fix",
            reported_flags="fix,trim",
        )
        == snapshot(
            """\

s=snapshot({"v": 3, "q": 5})
assert 5>=s["v"]
assert 5==s["q"]
"""
        )
    )

    assert (
        check_update(
            """
s=snapshot({"q": 4})
assert 5>=s["v"]
assert 5==s["q"]
""",
            flags="fix",
            reported_flags="fix,create",
        )
        == snapshot(
            """\

s=snapshot({"q": 5})
assert 5>=s["v"]
assert 5==s["q"]
"""
        )
    )

    assert check_update("assert 5>=snapshot(2)", flags="trim") == snapshot(
        "assert 5>=snapshot(5)"
    )

    assert check_update("assert 5>=snapshot(8)", flags="fix") == snapshot(
        "assert 5>=snapshot(5)"
    )

    assert check_update("assert snapshot(8) <= 5", flags="fix") == snapshot(
        "assert snapshot(5) <= 5"
    )

    assert check_update("assert 5>=snapshot(5)") == snapshot("assert 5>=snapshot(5)")

    assert check_update(
        "for i in range(5): assert i >=snapshot(2)", flags="fix"
    ) == snapshot("for i in range(5): assert i >=snapshot(0)")

    assert check_update(
        "for i in range(5): assert i >=snapshot(-10)", flags="trim"
    ) == snapshot("for i in range(5): assert i >=snapshot(0)")


def test_contains(check_update):
    assert check_update("assert 5 in snapshot()", flags="create") == snapshot(
        "assert 5 in snapshot([5])"
    )

    assert check_update("assert 5 in snapshot([])", flags="fix") == snapshot(
        "assert 5 in snapshot([5])"
    )

    assert check_update("assert 5 in snapshot([2])", flags="fix,trim") == snapshot(
        "assert 5 in snapshot([5])"
    )

    assert check_update("assert 5 in snapshot([2,5])", flags="trim") == snapshot(
        "assert 5 in snapshot([5])"
    )

    assert check_update(
        "for i in range(5): assert i in snapshot([0,1,2,3,4,5,6])", flags="trim"
    ) == snapshot("for i in range(5): assert i in snapshot([0,1,2,3,4])")

    assert (
        check_update(
            """
s=snapshot()
assert 4 in s
assert 5 in s
assert 5 in s
""",
            flags="create",
        )
        == snapshot(
            """\

s=snapshot([4, 5])
assert 4 in s
assert 5 in s
assert 5 in s
"""
        )
    )


def test_getitem(check_update):
    assert check_update('assert 5 == snapshot()["test"]', flags="create") == snapshot(
        'assert 5 == snapshot({"test": 5})["test"]'
    )

    assert check_update(
        "for i in range(3): assert i in snapshot()[str(i)]", flags="create"
    ) == snapshot(
        'for i in range(3): assert i in snapshot({"0": [0], "1": [1], "2": [2]})[str(i)]'
    )

    assert check_update(
        'for i in range(3): assert i in snapshot({"0": [0], "1": [1], "2": [2]})[str(i)]'
    ) == snapshot(
        'for i in range(3): assert i in snapshot({"0": [0], "1": [1], "2": [2]})[str(i)]'
    )

    assert check_update(
        'for i in range(2): assert i in snapshot({"0": [0], "1": [1], "2": [2]})[str(i)]',
        flags="trim",
    ) == snapshot(
        'for i in range(2): assert i in snapshot({"0": [0], "1": [1]})[str(i)]'
    )

    assert check_update(
        'for i in range(3): assert i in snapshot({"0": [0], "1": [1,2], "2": [4]})[str(i)]',
        flags="fix,trim",
    ) == snapshot(
        'for i in range(3): assert i in snapshot({"0": [0], "1": [1], "2": [2]})[str(i)]'
    )

    assert check_update(
        'for i in range(3): assert i in snapshot({"0": [0], "1": [1,2], "2": [4]})[str(i)]',
        flags="fix",
        reported_flags="fix,trim",
    ) == snapshot(
        'for i in range(3): assert i in snapshot({"0": [0], "1": [1,2], "2": [4, 2]})[str(i)]'
    )

    assert check_update(
        'for i in range(3): assert i in snapshot({"0": [0], "1": [1,2], "2": [2]})[str(i)]',
        flags="trim",
    ) == snapshot(
        'for i in range(3): assert i in snapshot({"0": [0], "1": [1], "2": [2]})[str(i)]'
    )

    assert check_update(
        "assert 4 in snapshot({2:[4],3:[]})[2]", flags="trim"
    ) == snapshot("assert 4 in snapshot({2:[4]})[2]")

    assert check_update(
        "assert 5 in snapshot({2:[4],3:[]})[2]", flags="fix", reported_flags="fix,trim"
    ) == snapshot("assert 5 in snapshot({2:[4, 5],3:[]})[2]")

    assert check_update(
        "assert 5 in snapshot({2:[4],3:[]})[2]", flags="fix,trim"
    ) == snapshot("assert 5 in snapshot({2:[5]})[2]")

    assert check_update(
        "assert 5 in snapshot({3:[1]})[2]", flags="create", reported_flags="create,trim"
    ) == snapshot("assert 5 in snapshot({3:[1], 2: [5]})[2]")

    assert (
        check_update(
            """
s=snapshot()
assert 5 == s["q"]
assert 5 == s["q"]
        """,
            flags="create",
        )
        == snapshot(
            """\

s=snapshot({"q": 5})
assert 5 == s["q"]
assert 5 == s["q"]
"""
        )
    )


def test_assert(check_update):
    assert check_update("assert 2 == snapshot(5)", reported_flags="fix")


def test_plain(check_update, executing_used):
    assert check_update("s = snapshot(5)", flags="") == snapshot("s = snapshot(5)")

    assert check_update("s = snapshot()", flags="") == snapshot("s = snapshot()")


def test_flags_repr():
    assert repr(Flags({"update"})) == "Flags({'update'})"


def test_format_file(check_update):
    assert check_update(
        'assert ["aaaaaaaaaaaaaaaaa"] * 5 == snapshot()\n', flags="create"
    ) == snapshot(
        """\
assert ["aaaaaaaaaaaaaaaaa"] * 5 == snapshot([
    "aaaaaaaaaaaaaaaaa",
    "aaaaaaaaaaaaaaaaa",
    "aaaaaaaaaaaaaaaaa",
    "aaaaaaaaaaaaaaaaa",
    "aaaaaaaaaaaaaaaaa",
])
"""
    )


def test_format_value(check_update):
    assert check_update(
        'assert ["aaaaaaaaaaaaaaaaa"] * 5==  snapshot()\n', flags="create"
    ) == snapshot(
        """\
assert ["aaaaaaaaaaaaaaaaa"] * 5==  snapshot([
    "aaaaaaaaaaaaaaaaa",
    "aaaaaaaaaaaaaaaaa",
    "aaaaaaaaaaaaaaaaa",
    "aaaaaaaaaaaaaaaaa",
    "aaaaaaaaaaaaaaaaa",
])
"""
    )


def test_unused_snapshot(check_update):
    assert (
        check_update("snapshot()\n", flags="create", reported_flags="")
        == "snapshot()\n"
    )


def test_type_error(check_update):
    tests = ["5 == s", "5 <= s", "5 >= s", "5 in s", "5 == s[0]"]

    for test1, test2 in itertools.product(tests, tests):
        with pytest.raises(TypeError) if test1 != test2 else nullcontext() as error:
            check_update(
                f"""
s = snapshot()
assert {test1}
assert {test2}
        """,
                reported_flags="create",
            )
        if error is not None:
            assert "This snapshot cannot be use with" in str(error.value)
        else:
            assert test1 == test2


def test_sub_snapshot_create(check_update):

    assert (
        check_update(
            """\
s=snapshot({})

s["keya"]

assert s["keyb"]==5
""",
            flags="create",
        )
        == snapshot(
            """\
s=snapshot({"keyb": 5})

s["keya"]

assert s["keyb"]==5
"""
        )
    )

    assert (
        check_update(
            """\
s=snapshot()

s["keya"]

assert s["keyb"]==5
""",
            flags="create",
        )
        == snapshot(
            """\
s=snapshot({"keyb": 5})

s["keya"]

assert s["keyb"]==5
"""
        )
    )


def test_different_snapshot_name(check_update):

    assert (
        check_update(
            """\
from inline_snapshot import snapshot as s
assert 4==s()

""",
            flags="create",
        )
        == snapshot(
            """\
from inline_snapshot import snapshot as s
assert 4==s(4)

"""
        )
    )

    assert (
        check_update(
            """\
import inline_snapshot
assert 4==inline_snapshot.snapshot()
""",
            flags="create",
        )
        == snapshot(
            """\
import inline_snapshot
assert 4==inline_snapshot.snapshot(4)
"""
        )
    )


def test_quoting_change_is_no_update(source):

    s = source(
        """\
from inline_snapshot import external,snapshot

class X:
    def __init__(self,a):
        self.a=a
        pass

    def __repr__(self):
        return f'X("{self.a}")'

    def __eq__(self,other):
        if not hasattr(other,"a"):
            return NotImplemented
        return other.a==self.a

assert X("a") == snapshot()
"""
    )
    assert s.flags == snapshot({"create"})

    s = s.run("create")

    assert s.source == snapshot(
        """\
from inline_snapshot import external,snapshot

class X:
    def __init__(self,a):
        self.a=a
        pass

    def __repr__(self):
        return f'X("{self.a}")'

    def __eq__(self,other):
        if not hasattr(other,"a"):
            return NotImplemented
        return other.a==self.a

assert X("a") == snapshot(X("a"))
"""
    )

    assert s.flags == snapshot({"create"})
    s = s.run()
    assert s.flags == snapshot(set())


def test_trailing_comma(project):

    project.setup(
        """\
from inline_snapshot import external, snapshot

class X:
    def __init__(self, *args):
        self.args = args

    def __repr__(self):
        return f"X({', '.join(map(repr,self.args))})"

    def __eq__(self,other):
        if not isinstance(other,X):
            return NotImplemented

        return self.args == other.args

def test_thing():
    assert X("a" * 40, "a" * 40) == snapshot()
"""
    )

    project.format()

    result = project.run("--inline-snapshot=create")

    assert result.report == snapshot(
        """\
------------------------------- Create snapshots -------------------------------
+-------------------------------- test_file.py --------------------------------+
| @@ -19,4 +19,9 @@                                                            |
|                                                                              |
|                                                                              |
|                                                                              |
|  def test_thing():                                                           |
| -    assert X("a" * 40, "a" * 40) == snapshot()                              |
| +    assert X("a" * 40, "a" * 40) == snapshot(                               |
| +        X(                                                                  |
| +            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",                     |
| +            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",                     |
| +        )                                                                   |
| +    )                                                                       |
+------------------------------------------------------------------------------+
These changes will be applied, because you used --inline-snapshot=create
"""
    )

    result = project.run("--inline-snapshot=report")

    assert result.report == snapshot("")


@dataclass
class Warning:
    message: str
    filename: Union[str, None] = None
    line: Union[int, None] = None


@contextlib.contextmanager
def warns(expected_warnings=[], include_line=False, include_file=False):
    with warnings.catch_warnings(record=True) as result:
        warnings.simplefilter("always")
        yield

    assert [
        Warning(
            message=f"{w.category.__name__}: {w.message}",
            line=w.lineno if include_line else None,
            filename=w.filename if include_file else None,
        )
        for w in result
    ] == expected_warnings


def test_starred_warns_list():

    with warns(
        snapshot(
            [
                Warning(
                    message="InlineSnapshotSyntaxWarning: star-expressions are not supported inside snapshots",
                    line=4,
                )
            ]
        ),
        include_line=True,
    ):
        Example(
            """
from inline_snapshot import snapshot

assert [5] == snapshot([*[5]])
"""
        ).run_inline(["--inline-snapshot=fix"])


def test_starred_warns_dict():
    with warns(
        snapshot(
            [
                Warning(
                    message="InlineSnapshotSyntaxWarning: star-expressions are not supported inside snapshots",
                    line=4,
                )
            ]
        ),
        include_line=True,
    ):
        Example(
            """
from inline_snapshot import snapshot

assert {1:3} == snapshot({**{1:3}})
"""
        ).run_inline(["--inline-snapshot=fix"])


def test_is():

    Example(
        """
from inline_snapshot import snapshot,Is

def test_Is():
    for i in range(3):
        assert ["hello",i] == snapshot(["hi",Is(i)])
        assert ["hello",i] == snapshot({1:["hi",Is(i)]})[i]
"""
    ).run_inline(
        ["--inline-snapshot=create"],
        changed_files=snapshot(
            {
                "test_something.py": """\

from inline_snapshot import snapshot,Is

def test_Is():
    for i in range(3):
        assert ["hello",i] == snapshot(["hi",Is(i)])
        assert ["hello",i] == snapshot({1:["hi",Is(i)], 0: ["hello", 0], 2: ["hello", 2]})[i]
"""
            }
        ),
    ).run_inline(
        ["--inline-snapshot=fix"],
        changed_files=snapshot(
            {
                "test_something.py": """\

from inline_snapshot import snapshot,Is

def test_Is():
    for i in range(3):
        assert ["hello",i] == snapshot(["hello",Is(i)])
        assert ["hello",i] == snapshot({1:["hello",Is(i)], 0: ["hello", 0], 2: ["hello", 2]})[i]
"""
            }
        ),
    )


def test_create_elipsis():
    Example(
        """\
from inline_snapshot import snapshot

def test_a():
    assert 1+1==snapshot(...)
    assert [1,2,8] == snapshot([1,2,...])
        """
    ).run_inline(
        ["--inline-snapshot=create"],
        changed_files=snapshot(
            {
                "test_something.py": """\
from inline_snapshot import snapshot

def test_a():
    assert 1+1==snapshot(2)
    assert [1,2,8] == snapshot([1,2,8])
        \
"""
            }
        ),
    )
