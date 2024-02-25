import ast
import itertools
from collections import namedtuple
from contextlib import nullcontext

import pytest
from hypothesis import given
from hypothesis.strategies import text

from .utils import snapshot_env
from inline_snapshot import _inline_snapshot
from inline_snapshot import snapshot
from inline_snapshot._inline_snapshot import Flags
from inline_snapshot._inline_snapshot import triple_quote


def test_snapshot_eq():
    with snapshot_env():
        assert 1 == snapshot(1)
        assert snapshot(1) == 1


def test_disabled():
    with snapshot_env():
        _inline_snapshot._active = False
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


def test_generic(source, subtests):
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

            assert list(s.flags) == [reported_flag]

            assert (reported_flag == "fix") == s.error

            for flag in all_flags:
                if flag == reported_flag:
                    continue
                print("use flag:", flag)
                s2 = s.run(flag)
                assert s2.source == s.source

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
def test_generic_multi(source, subtests, ops):
    def gen_code(ops, fixed):
        args = ", ".join(
            f'"k_{k}": {value}'
            for k, value in [
                (k, (op.fvalue if op.flag in fixed else op.svalue))
                for k, op in enumerate(ops)
            ]
            if value
        )
        code = "s = snapshot({" + args + "})\n"

        for k, op in enumerate(ops):
            code += f'print({op.value} {op.op} s["k_{k}"]) # {op.flag} {op.svalue or "<undef>"} -> {op.fvalue}\n'

        return code

    all_flags = {op.flag for op in ops}

    s = source(gen_code(ops, {}))

    assert s.flags == all_flags

    for flags in itertools.permutations(all_flags):
        with subtests.test(" ".join(flags)):
            s2 = s
            fixed_flags = set()
            for flag in flags:
                if flag in {"create", "fix", "trim"}:
                    fixed_flags.add("update")

                s2 = s2.run(flag)
                fixed_flags.add(flag)
                assert s2.source == gen_code(ops, fixed_flags)

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
            """
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
            """
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
            """
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
            """
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
            """
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
            """
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
            """
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
            """
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
            """
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
            """
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
    ) == snapshot("for i in range(5): assert i in snapshot([0, 1, 2, 3, 4])")

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
            """
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
        'for i in range(3): assert i in snapshot({"0": [0], "1": [1, 2], "2": [4, 2]})[str(i)]'
    )

    assert check_update(
        'for i in range(3): assert i in snapshot({"0": [0], "1": [1,2], "2": [2]})[str(i)]',
        flags="trim",
    ) == snapshot(
        'for i in range(3): assert i in snapshot({"0": [0], "1": [1], "2": [2]})[str(i)]'
    )

    assert check_update(
        "assert 4 in snapshot({2:[4],3:[]})[2]", flags="trim"
    ) == snapshot("assert 4 in snapshot({2: [4]})[2]")

    assert check_update(
        "assert 5 in snapshot({2:[4],3:[]})[2]", flags="fix", reported_flags="fix,trim"
    ) == snapshot("assert 5 in snapshot({2: [4, 5], 3: []})[2]")

    assert check_update(
        "assert 5 in snapshot({2:[4],3:[]})[2]", flags="fix,trim"
    ) == snapshot("assert 5 in snapshot({2: [5]})[2]")

    assert check_update(
        "assert 5 in snapshot({3:[1]})[2]", flags="create", reported_flags="create,trim"
    ) == snapshot("assert 5 in snapshot({2: [5], 3: [1]})[2]")

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
            """
s=snapshot({"q": 5})
assert 5 == s["q"]
assert 5 == s["q"]
"""
        )
    )


def test_assert(check_update):
    assert check_update("assert 2 == snapshot(5)", reported_flags="fix")


def test_plain(check_update):
    assert check_update("s = snapshot(5)", flags="") == snapshot("s = snapshot(5)")

    assert check_update(
        "s = snapshot()", flags="", reported_flags="create"
    ) == snapshot("s = snapshot()")


def test_string_update(check_update):
    # black --preview wraps strings to keep the line length.
    # string concatenation should produce updates.
    assert (
        check_update(
            'assert "ab" == snapshot("a" "b")', reported_flags="", flags="update"
        )
        == 'assert "ab" == snapshot("a" "b")'
    )

    assert (
        check_update(
            'assert "ab" == snapshot("a"\n "b")', reported_flags="", flags="update"
        )
        == 'assert "ab" == snapshot("a"\n "b")'
    )

    assert check_update(
        'assert "ab\\nc" == snapshot("a"\n "b\\nc")', flags="update"
    ) == snapshot(
        '''\
assert "ab\\nc" == snapshot("""\\
ab
c\\
""")\
'''
    )

    assert (
        check_update(
            'assert b"ab" == snapshot(b"a"\n b"b")', reported_flags="", flags="update"
        )
        == 'assert b"ab" == snapshot(b"a"\n b"b")'
    )


def test_string_newline(check_update):
    assert check_update('s = snapshot("a\\nb")', flags="update") == snapshot(
        '''\
s = snapshot("""\\
a
b\\
""")\
'''
    )

    assert check_update('s = snapshot("a\\"\\"\\"\\nb")', flags="update") == snapshot(
        """\
s = snapshot('''\\
a\"\"\"
b\\
''')\
"""
    )

    assert check_update(
        's = snapshot("a\\"\\"\\"\\n\\\'\\\'\\\'b")', flags="update"
    ) == snapshot(
        '''\
s = snapshot("""\\
a\\"\\"\\"
\'\'\'b\\
""")\
'''
    )

    assert check_update('s = snapshot(b"a\\nb")') == snapshot('s = snapshot(b"a\\nb")')

    assert check_update('s = snapshot("\\n\\\'")', flags="update") == snapshot(
        '''\
s = snapshot("""\\

'\\
""")\
'''
    )

    assert check_update('s = snapshot("\\n\\"")', flags="update") == snapshot(
        '''\
s = snapshot("""\\

"\\
""")\
'''
    )

    assert check_update("s = snapshot(\"'''\\n\\\"\")", flags="update") == snapshot(
        '''\
s = snapshot("""\\
\'\'\'
\\"\\
""")\
'''
    )

    assert check_update('s = snapshot("\\n\b")', flags="update") == snapshot(
        '''\
s = snapshot("""\\

\\x08\\
""")\
'''
    )


def test_string_quote_choice(check_update):
    assert check_update(
        "s = snapshot(\" \\'\\'\\' \\'\\'\\' \\\"\\\"\\\"\\n\")", flags="update"
    ) == snapshot(
        '''\
s = snapshot("""\\
 \'\'\' \'\'\' \\"\\"\\"
""")\
'''
    )

    assert check_update(
        's = snapshot(" \\\'\\\'\\\' \\"\\"\\" \\"\\"\\"\\n")', flags="update"
    ) == snapshot(
        """\
s = snapshot('''\\
 \\'\\'\\' \"\"\" \"\"\"
''')\
"""
    )

    assert check_update('s = snapshot("\\n\\"")', flags="update") == snapshot(
        '''\
s = snapshot("""\\

"\\
""")\
'''
    )


@given(s=text())
def test_string_convert(s):
    print(s)
    assert ast.literal_eval(triple_quote(s)) == s


def test_flags_repr():
    assert repr(Flags({"update"})) == "Flags({'update'})"


def test_format_file(check_update):
    assert check_update(
        'assert ["aaaaaaaaaaaaaaaaa"] * 5 == snapshot()\n', flags="create"
    ) == snapshot(
        """\
assert ["aaaaaaaaaaaaaaaaa"] * 5 == snapshot(
    [
        "aaaaaaaaaaaaaaaaa",
        "aaaaaaaaaaaaaaaaa",
        "aaaaaaaaaaaaaaaaa",
        "aaaaaaaaaaaaaaaaa",
        "aaaaaaaaaaaaaaaaa",
    ]
)
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
    assert check_update("snapshot()\n", flags="create") == "snapshot()\n"


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


def test_invalid_repr(check_update):
    assert (
        check_update(
            """\
class Thing:
    def __repr__(self):
        return "+++"

assert Thing() == snapshot()
""",
            flags="create",
        )
        == snapshot(
            """\
class Thing:
    def __repr__(self):
        return "+++"

assert Thing() == snapshot()
"""
        )
    )


def test_preserve(check_update):
    assert (
        check_update(
            """\
left = {
    "a": 1,
    "b": {
        "c": 2,
        "d": [
            3,
            4,
            5,
        ]
    },
    "e": (
        {
            "f": 6,
            "g": 7,
        },
    )
}
assert left == snapshot({
    "a": 10,
    "b": {
        "c": 2 * 1 + 0,
        "d": [
            int(3),
            40,
            5,
        ],
        "h": 8,
    },
    "e": (
        {
            "f": 3 + 3,
        },
        9,
    )
})
""",
            reported_flags="update,fix",
            flags="fix",
        )
        == snapshot(
            """\
left = {
    "a": 1,
    "b": {
        "c": 2,
        "d": [
            3,
            4,
            5,
        ]
    },
    "e": (
        {
            "f": 6,
            "g": 7,
        },
    )
}
assert left == snapshot({"a": 1, "b": {"c": 2 * 1 + 0, "d": [int(3), 4, 5]}, "e": ({"f": 3 + 3, "g": 7},)})
"""
        )
    )
