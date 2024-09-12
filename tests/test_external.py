import ast

from inline_snapshot import external
from inline_snapshot import outsource
from inline_snapshot import snapshot
from inline_snapshot.extra import raises
from inline_snapshot.testing import Example

from tests.utils import config


def test_basic(check_update):
    assert check_update(
        "assert outsource('text') == snapshot()", flags="create"
    ) == snapshot(
        "assert outsource('text') == snapshot(external(\"hash:982d9e3eb996*.txt\"))"
    )


# def test_external():
#     assert repr(external("11111111112222222222.txt")) == snapshot(
#         'external("111111111122*.txt")'
#     )


def test_max_hash():
    with config(hash_length=64):
        assert repr(external("hash:" + "1" * 64 + ".txt")) == snapshot(
            'external("hash:1111111111111111111111111111111111111111111111111111111111111111.txt")'
        )


def test_outsource(storage):
    assert outsource("test") == snapshot(external("hash:9f86d081884c*.txt"))

    assert outsource("test", suffix=".log") == snapshot(
        external("hash:9f86d081884c*.log")
    )

    assert outsource(b"test") == snapshot(external("hash:9f86d081884c*.bin"))

    assert outsource(b"test", suffix=".png") == snapshot(
        external("hash:9f86d081884c*.png")
    )

    assert outsource("test")._load_value() == snapshot(b"test")


def test_diskstorage(storage):
    assert outsource("test4") == snapshot(external("hash:a4e624d686e0*.txt"))
    assert outsource("test5") == snapshot(external("hash:a140c0c1eda2*.txt"))
    assert outsource("test6") == snapshot(external("hash:ed0cb90bdfa4*.txt"))

    with raises(
        snapshot(
            "HashError: hash collision files=['a140c0c1eda2def2b830363ba362aa4d7d255c262960544821f556e16661b6ff-new.txt', 'a4e624d686e03ed2767c0abd85c14426b0b1157d2ce81d27bb4fe4f6f01d688a-new.txt']"
        )
    ):
        external("hash:a*.txt")._load_value()

    with raises(
        snapshot("HashError: hash 'bbbbb*.txt' is not found in the DiscStorage")
    ):
        external("hash:bbbbb*.txt")._load_value()


def test_update_legacy_external_names(project):
    (
        Example(
            """\
from inline_snapshot import outsource,snapshot

def test_something():
    assert outsource("foo") == snapshot()
"""
        )
        .run_pytest(
            ["--inline-snapshot=create"],
            changed_files=snapshot(
                {
                    "test_something.py": """\
from inline_snapshot import outsource,snapshot

from inline_snapshot import external

def test_something():
    assert outsource("foo") == snapshot(external("hash:2c26b46b68ff*.txt"))
"""
                }
            ),
        )
        .change_code(lambda code: code.replace("hash:", ""))
        .run_inline(reported_categories=snapshot(["update"]))
        .run_inline(
            ["--inline-snapshot=update"],
            reported_categories=snapshot(["update"]),
            changed_files=snapshot(
                {
                    "test_something.py": """\
from inline_snapshot import outsource,snapshot

from inline_snapshot import external

def test_something():
    assert outsource("foo") == snapshot(external("hash:2c26b46b68ff*.txt"))
"""
                }
            ),
        )
    )


def test_persist(project):

    project.setup(
        """\
from inline_snapshot import external

def test_something():
    assert "hello" == snapshot(external("hash:bbbbb*.txt"))
    assert 2 == snapshot(1+1)
"""
    )

    result = project.run("--inline-snapshot=update")

    assert project.storage() == snapshot([])

    assert project.source == snapshot(
        """\
from inline_snapshot import external

def test_something():
    assert "hello" == snapshot(external("hash:bbbbb*.txt"))
    assert 2 == snapshot(2)
"""
    )

    assert result.report == snapshot(
        """\
------------------------------- Update snapshots -------------------------------
+-------------------------------- test_file.py --------------------------------+
| @@ -5,4 +5,4 @@                                                              |
|                                                                              |
|                                                                              |
|  def test_something():                                                       |
|      assert "hello" == snapshot(external("hash:bbbbb*.txt"))                 |
| -    assert 2 == snapshot(1+1)                                               |
| +    assert 2 == snapshot(2)                                                 |
+------------------------------------------------------------------------------+
These changes will be applied, because you used --inline-snapshot=update
"""
    )


def test_pytest_compare_external(project):
    project.setup(
        """\
from inline_snapshot import external

def test_a():
    assert outsource("test") == snapshot(
        external("hash:9f86d081884c*.txt")
    )

    assert outsource("test2") == snapshot(
        external("hash:9f86d081884c*.txt")
    )
        """
    )

    result = project.run()

    assert result.errorLines() == snapshot(
        """\
>       assert outsource("test2") == snapshot(
E       AssertionError: assert 'test2' == 'test'
E         ⏎
E         - test
E         + test2
E         ?     +
"""
    )


def test_pytest_compare_external_bytes(project):
    project.setup(
        """\
from inline_snapshot import external

def test_a():
    assert outsource(b"test") == snapshot(
        external("hash:9f86d081884c*.bin")
    )

    assert outsource(b"test2") == snapshot(
        external("hash:9f86d081884c*.bin")
    )
        """
    )

    result = project.run()

    assert result.errorLines() == snapshot(
        """\
>       assert outsource(b"test2") == snapshot(
E       AssertionError: assert b'test2' == b'test'
E         ⏎
E         Use -v to get more diff
"""
    )


def test_pytest_existing_external_import(project):
    project.setup(
        """\
from inline_snapshot import external

def test_a():
    assert outsource("test") == snapshot()
"""
    )

    result = project.run("--inline-snapshot=create")

    assert project.source == snapshot(
        """\
from inline_snapshot import external

def test_a():
    assert outsource("test") == snapshot(external("hash:9f86d081884c*.txt"))
"""
    )


def test_pytest_trim_external(project):
    project.setup(
        """\
def test_a():
    assert outsource("test") == snapshot()

    # split

    assert outsource("test2") == snapshot()
        """
    )

    project.run("--inline-snapshot=create")

    assert project.storage() == snapshot(
        [
            "60303ae22b998861bce3b28f33eec1be758a213c86c93c076dbe9f558c11c752.txt",
            "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08.txt",
        ]
    )

    assert project.source == snapshot(
        """\
from inline_snapshot import external


def test_a():
    assert outsource("test") == snapshot(external("hash:9f86d081884c*.txt"))

    # split

    assert outsource("test2") == snapshot(external("hash:60303ae22b99*.txt"))
        \
"""
    )

    project.setup(project.source.split("# split")[0])
    result = project.run()

    assert project.storage() == snapshot(
        [
            "60303ae22b998861bce3b28f33eec1be758a213c86c93c076dbe9f558c11c752.txt",
            "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08.txt",
        ]
    )

    assert result.report == snapshot("")

    result = project.run("--inline-snapshot=trim")

    assert project.storage() == snapshot([])


def test_pytest_new_external(project):
    project.setup(
        """\
def test_a():
    assert outsource("test") == snapshot()
"""
    )
    project.run()

    assert project.storage() == snapshot(
        ["9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08-new.txt"]
    )

    project.run("--inline-snapshot=create")

    assert project.storage() == snapshot(
        ["9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08.txt"]
    )


def test_pytest_config_hash_length(project):
    project.setup(
        """\
def test_a():
    assert outsource("test") == snapshot()
"""
    )
    project.run("--inline-snapshot=create")
    default_result = project.source

    # default config
    project.pyproject(
        """
[tool.inline-snapshot]
    """
    )
    project.run("--inline-snapshot=create")
    assert default_result == project.source

    # set hash_length
    project.pyproject(
        """
[tool.inline-snapshot]
hash-length=5
    """
    )
    project.run("--inline-snapshot=create")
    assert project.source == snapshot(
        """\
from inline_snapshot import external


def test_a():
    assert outsource("test") == snapshot(external("hash:9f86d081884c*.txt"))
"""
    )


def test_errors():
    with raises(snapshot("ValueError: suffix has to start with a '.' like '.png'")):
        outsource("test", suffix="blub")

    with raises(snapshot("TypeError: data has to be of type bytes | str")):
        outsource(5)

    with raises(
        snapshot(
            "ValueError: path has to be of the form <hash>.<suffix> or <partial_hash>*.<suffix>"
        )
    ):
        external("invalid")

    # assert external("123*.txt") == external("12*.txt")
    # assert external("123*.txt") != external("124*.txt")
    # assert external("123*.txt") != external("123*.bin")


from inline_snapshot import _inline_snapshot


def test_uses_external():
    assert _inline_snapshot.used_externals(ast.parse("[external('hash:111*.txt')]"))
    assert not _inline_snapshot.used_externals(ast.parse("[external()]"))
    assert not _inline_snapshot.used_externals(ast.parse("[external]"))


def test_no_imports(project):
    project.setup(
        """\
# no imports

def test_something():
    from inline_snapshot import outsource,snapshot
    assert outsource("test") == snapshot()
test_something()
    """
    )

    result = project.run("--inline-snapshot=create")

    result.assert_outcomes(passed=1)

    assert project.source == snapshot(
        """\
# no imports


from inline_snapshot import external
def test_something():
    from inline_snapshot import outsource,snapshot
    assert outsource("test") == snapshot(external("hash:9f86d081884c*.txt"))
test_something()
    \
"""
    )


from inline_snapshot._find_external import ensure_import

from .utils import apply_changes


def test_ensure_imports(tmp_path):
    file = tmp_path / "file.py"
    file.write_text(
        """\
from os import environ
from os import getcwd
""",
        "utf-8",
    )

    with apply_changes():
        ensure_import(file, {"os": ["chdir", "environ"]})

    assert file.read_text("utf-8") == snapshot(
        """\
from os import environ
from os import getcwd

from os import chdir
"""
    )


def test_ensure_imports_with_comment(tmp_path):
    file = tmp_path / "file.py"
    file.write_text(
        """\
from os import environ # comment
""",
        "utf-8",
    )

    with apply_changes():
        ensure_import(file, {"os": ["chdir"]})

    assert file.read_text("utf-8") == snapshot(
        """\
from os import environ # comment

from os import chdir
"""
    )


def test_new_externals(project):
    project.setup(
        """

def test_something():
    outsource("blub")

    assert outsource("foo") == snapshot()

    """
    )

    project.run("--inline-snapshot=create")

    assert project.storage() == snapshot(
        [
            "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae.txt",
            "8dc140e6fe831481a2005ae152ffe32a9974aa92a260dfbac780d6a87154bb0b-new.txt",
        ]
    )

    assert project.source == snapshot(
        """\
from inline_snapshot import external




def test_something():
    outsource("blub")

    assert outsource("foo") == snapshot(external("hash:2c26b46b68ff*.txt"))

    \
"""
    )

    project.run()

    assert project.storage() == snapshot(
        [
            "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae.txt",
            "8dc140e6fe831481a2005ae152ffe32a9974aa92a260dfbac780d6a87154bb0b-new.txt",
        ]
    )
