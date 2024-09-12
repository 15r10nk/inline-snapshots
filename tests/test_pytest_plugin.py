import pytest
from inline_snapshot import snapshot
from inline_snapshot.testing import Example

from .utils import pytest_compatible


def test_help_message(testdir):
    result = testdir.runpytest_subprocess("--help")
    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines(["inline-snapshot:", "*--inline-snapshot*"])


def test_create(project):
    project.setup(
        """\
def test_a():
    assert 5==snapshot()
"""
    )

    result = project.run()

    result.assert_outcomes(errors=1, passed=1)

    assert result.report == snapshot(
        """\
Error: one snapshot is missing a value (--inline-snapshot=create)
You can also use --inline-snapshot=review to approve the changes interactively
"""
    )

    result = project.run("--inline-snapshot=create")

    result.assert_outcomes(passed=1)

    assert result.report == snapshot(
        """\
------------------------------- Create snapshots -------------------------------
+-------------------------------- test_file.py --------------------------------+
| @@ -4,4 +4,4 @@                                                              |
|                                                                              |
|                                                                              |
|                                                                              |
|  def test_a():                                                               |
| -    assert 5==snapshot()                                                    |
| +    assert 5==snapshot(5)                                                   |
+------------------------------------------------------------------------------+
These changes will be applied, because you used --inline-snapshot=create
"""
    )

    assert project.source == snapshot(
        """\
def test_a():
    assert 5==snapshot(5)
"""
    )


def test_fix(project):
    project.setup(
        """\
def test_a():
    assert 5==snapshot(4)
"""
    )

    result = project.run()

    result.assert_outcomes(failed=1, errors=1)

    assert result.report == snapshot(
        """\
Error: one snapshot has incorrect values (--inline-snapshot=fix)
You can also use --inline-snapshot=review to approve the changes interactively
"""
    )

    result = project.run("--inline-snapshot=fix")

    result.assert_outcomes(passed=1)

    assert result.report == snapshot(
        """\
-------------------------------- Fix snapshots ---------------------------------
+-------------------------------- test_file.py --------------------------------+
| @@ -4,4 +4,4 @@                                                              |
|                                                                              |
|                                                                              |
|                                                                              |
|  def test_a():                                                               |
| -    assert 5==snapshot(4)                                                   |
| +    assert 5==snapshot(5)                                                   |
+------------------------------------------------------------------------------+
These changes will be applied, because you used --inline-snapshot=fix
"""
    )

    assert project.source == snapshot(
        """\
def test_a():
    assert 5==snapshot(5)
"""
    )


def test_update(project):
    project.setup(
        """\
def test_a():
    assert "5" == snapshot('''5''')
"""
    )

    result = project.run()

    result.assert_outcomes(passed=1)

    assert result.report == (
        snapshot(
            """\
Info: one snapshot changed its representation (--inline-snapshot=update)
You can also use --inline-snapshot=review to approve the changes interactively
"""
        )
        if pytest_compatible
        else snapshot("")
    )

    result = project.run("--inline-snapshot=update")

    assert result.report == snapshot(
        """\
------------------------------- Update snapshots -------------------------------
+-------------------------------- test_file.py --------------------------------+
| @@ -4,4 +4,4 @@                                                              |
|                                                                              |
|                                                                              |
|                                                                              |
|  def test_a():                                                               |
| -    assert "5" == snapshot('''5''')                                         |
| +    assert "5" == snapshot("5")                                             |
+------------------------------------------------------------------------------+
These changes will be applied, because you used --inline-snapshot=update
"""
    )

    assert project.source == snapshot(
        """\
def test_a():
    assert "5" == snapshot("5")
"""
    )


def test_trim(project):
    project.setup(
        """\
def test_a():
    assert 5 in snapshot([4,5])
"""
    )

    result = project.run()

    result.assert_outcomes(passed=1)

    assert result.report == snapshot(
        """\
Info: one snapshot can be trimmed (--inline-snapshot=trim)
You can also use --inline-snapshot=review to approve the changes interactively
"""
    )

    result = project.run("--inline-snapshot=trim")

    assert result.report == snapshot(
        """\
-------------------------------- Trim snapshots --------------------------------
+-------------------------------- test_file.py --------------------------------+
| @@ -4,4 +4,4 @@                                                              |
|                                                                              |
|                                                                              |
|                                                                              |
|  def test_a():                                                               |
| -    assert 5 in snapshot([4,5])                                             |
| +    assert 5 in snapshot([5])                                               |
+------------------------------------------------------------------------------+
These changes will be applied, because you used --inline-snapshot=trim
"""
    )

    assert project.source == snapshot(
        """\
def test_a():
    assert 5 in snapshot([5])
"""
    )


def test_multiple(project):
    project.setup(
        """\
def test_a():
    assert "5" == snapshot('''5''')
    assert 5 <= snapshot(8)
    assert 5 == snapshot(4)
"""
    )

    result = project.run()

    result.assert_outcomes(failed=1, errors=1)

    assert result.report == (
        snapshot(
            """\
Error: one snapshot has incorrect values (--inline-snapshot=fix)
Info: one snapshot can be trimmed (--inline-snapshot=trim)
Info: one snapshot changed its representation (--inline-snapshot=update)
You can also use --inline-snapshot=review to approve the changes interactively
"""
        )
        if pytest_compatible
        else snapshot(
            """\
Error: one snapshot has incorrect values (--inline-snapshot=fix)
Info: one snapshot can be trimmed (--inline-snapshot=trim)
You can also use --inline-snapshot=review to approve the changes interactively
"""
        )
    )

    result = project.run("--inline-snapshot=trim,fix")

    assert result.report == snapshot(
        """\
-------------------------------- Fix snapshots ---------------------------------
+-------------------------------- test_file.py --------------------------------+
| @@ -6,4 +6,4 @@                                                              |
|                                                                              |
|  def test_a():                                                               |
|      assert "5" == snapshot('''5''')                                         |
|      assert 5 <= snapshot(8)                                                 |
| -    assert 5 == snapshot(4)                                                 |
| +    assert 5 == snapshot(5)                                                 |
+------------------------------------------------------------------------------+
These changes will be applied, because you used --inline-snapshot=fix
-------------------------------- Trim snapshots --------------------------------
+-------------------------------- test_file.py --------------------------------+
| @@ -5,5 +5,5 @@                                                              |
|                                                                              |
|                                                                              |
|  def test_a():                                                               |
|      assert "5" == snapshot('''5''')                                         |
| -    assert 5 <= snapshot(8)                                                 |
| +    assert 5 <= snapshot(5)                                                 |
|      assert 5 == snapshot(5)                                                 |
+------------------------------------------------------------------------------+
These changes will be applied, because you used --inline-snapshot=trim
"""
    )

    assert project.source == snapshot(
        """\
def test_a():
    assert "5" == snapshot('''5''')
    assert 5 <= snapshot(5)
    assert 5 == snapshot(5)
"""
    )


@pytest.mark.no_rewriting
def test_disable_option(project):
    project.setup(
        """\
def test_a():
    pass
"""
    )

    result = project.run("--inline-snapshot=disable,fix")
    assert result.stderr.str().strip() == snapshot(
        "ERROR: --inline-snapshot=disable can not be combined with other flags (fix)"
    )

    result = project.run("--inline-snapshot=disable,review")
    assert result.stderr.str().strip() == snapshot(
        "ERROR: --inline-snapshot=disable can not be combined with other flags (review)"
    )


def test_multiple_report(project):
    project.setup(
        """\
def test_a():
    assert "5" == snapshot('''5''')
    assert 5 <= snapshot(8)
    assert 5 == snapshot(4)
"""
    )

    result = project.run("--inline-snapshot=trim,report")

    assert result.report == snapshot(
        """\
-------------------------------- Fix snapshots ---------------------------------
+-------------------------------- test_file.py --------------------------------+
| @@ -6,4 +6,4 @@                                                              |
|                                                                              |
|  def test_a():                                                               |
|      assert "5" == snapshot('''5''')                                         |
|      assert 5 <= snapshot(8)                                                 |
| -    assert 5 == snapshot(4)                                                 |
| +    assert 5 == snapshot(5)                                                 |
+------------------------------------------------------------------------------+
These changes are not applied.
Use --inline-snapshot=fix to apply them, or use the interactive mode with
--inline-snapshot=review
-------------------------------- Trim snapshots --------------------------------
+-------------------------------- test_file.py --------------------------------+
| @@ -5,5 +5,5 @@                                                              |
|                                                                              |
|                                                                              |
|  def test_a():                                                               |
|      assert "5" == snapshot('''5''')                                         |
| -    assert 5 <= snapshot(8)                                                 |
| +    assert 5 <= snapshot(5)                                                 |
|      assert 5 == snapshot(4)                                                 |
+------------------------------------------------------------------------------+
These changes will be applied, because you used --inline-snapshot=trim
------------------------------- Update snapshots -------------------------------
+-------------------------------- test_file.py --------------------------------+
| @@ -4,6 +4,6 @@                                                              |
|                                                                              |
|                                                                              |
|                                                                              |
|  def test_a():                                                               |
| -    assert "5" == snapshot('''5''')                                         |
| +    assert "5" == snapshot("5")                                             |
|      assert 5 <= snapshot(5)                                                 |
|      assert 5 == snapshot(4)                                                 |
+------------------------------------------------------------------------------+
These changes are not applied.
Use --inline-snapshot=update to apply them, or use the interactive mode with
--inline-snapshot=review
"""
    )

    assert project.source == snapshot(
        """\
def test_a():
    assert "5" == snapshot('''5''')
    assert 5 <= snapshot(5)
    assert 5 == snapshot(4)
"""
    )


def test_black_config(project):
    project.setup(
        """\
def test_a():
    assert list(range(10)) == snapshot([])
"""
    )

    project.format()

    assert project.is_formatted()

    project.pyproject(
        """
[tool.black]
line-length=50
"""
    )

    assert project.is_formatted()

    project.run("--inline-snapshot=fix")

    assert project.source == snapshot(
        """\
def test_a():
    assert list(range(10)) == snapshot(
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    )
"""
    )

    assert project.is_formatted()


def test_disabled(project):
    project.setup(
        """\
def test_a():
    assert 4==snapshot(5)
"""
    )

    result = project.run("--inline-snapshot=disable")
    result.assert_outcomes(failed=1)

    result = project.run("--inline-snapshot=fix")
    assert project.source == snapshot(
        """\
def test_a():
    assert 4==snapshot(4)
"""
    )

    result = project.run("--inline-snapshot=disable")
    result.assert_outcomes(passed=1)


def test_compare(project):
    project.setup(
        """\
def test_a():
    assert "a"==snapshot("b")
"""
    )

    result = project.run()
    assert result.errorLines() == snapshot(
        """\
>       assert "a"==snapshot("b")
E       AssertionError: assert 'a' == 'b'
E         ⏎
E         - b
E         + a
"""
    )

    project.setup(
        """\
def test_a():
    assert snapshot("b")=="a"
"""
    )

    result = project.run()
    assert result.errorLines() == snapshot(
        """\
>       assert snapshot("b")=="a"
E       AssertionError: assert 'b' == 'a'
E         ⏎
E         - a
E         + b
"""
    )


def test_assertion_error_loop(project):
    project.setup(
        """\
for e in (1, 2):
    assert e == snapshot()
"""
    )
    result = project.run()
    assert result.errorLines() == snapshot(
        """\
E   assert 2 == 1
E    +  where 1 = snapshot()
"""
    )


def test_assertion_error_multiple(project):
    project.setup(
        """\
for e in (1, 2):
    assert e == snapshot(1)
"""
    )
    result = project.run()
    assert result.errorLines() == snapshot(
        """\
E   assert 2 == 1
E    +  where 1 = snapshot(1)
"""
    )


def test_assertion_error(project):
    project.setup("assert 2 == snapshot(1)")
    result = project.run()
    assert result.errorLines() == snapshot(
        """\
E   assert 2 == 1
E    +  where 1 = snapshot(1)
"""
    )


@pytest.mark.no_rewriting
def test_run_without_pytest(pytester):
    # snapshots are deactivated by default
    pytester.makepyfile(
        test_file="""
from inline_snapshot import snapshot
s=snapshot([1,2])
assert isinstance(s,list)
assert s==[1,2]
"""
    )

    result = pytester.runpython("test_file.py")

    assert result.ret == 0


def test_pytest_inlinesnapshot_auto(project):
    project.setup(
        """\
def test_something():
    assert 2 == snapshot(1)
"""
    )
    result = project.run("--inline-snapshot=review", stdin=b"y\n")
    assert result.errorLines() == snapshot("")

    assert result.report == snapshot(
        """\
-------------------------------- Fix snapshots ---------------------------------
+-------------------------------- test_file.py --------------------------------+
| @@ -4,4 +4,4 @@                                                              |
|                                                                              |
|                                                                              |
|                                                                              |
|  def test_something():                                                       |
| -    assert 2 == snapshot(1)                                                 |
| +    assert 2 == snapshot(2)                                                 |
+------------------------------------------------------------------------------+
do you want to fix these snapshots? [y/n] (n):
"""
    )

    assert project.source == snapshot(
        """\
def test_something():
    assert 2 == snapshot(2)
"""
    )


def test_empty_sub_snapshot(project):

    project.setup(
        """\

def test_sub_snapshot():
    assert 1==snapshot({})["key"]
"""
    )

    project.term_columns = 160

    result = project.run()

    assert result.ret == 1

    assert result.errors == snapshot(
        """\
============================================================================ ERRORS ============================================================================
____________________________________________________________ ERROR at teardown of test_sub_snapshot ____________________________________________________________
your snapshot is missing one value.
======================================================================= inline snapshot ========================================================================
Error: one snapshot is missing a value (--inline-snapshot=create)
You can also use --inline-snapshot=review to approve the changes interactively
=================================================================== short test summary info ====================================================================
ERROR test_file.py::test_sub_snapshot - Failed: your snapshot is missing one value.
================================================================== 1 passed, 1 error in <time> ==================================================================
"""
    )


def test_persist_unknown_external(project):
    project.setup(
        """\
from inline_snapshot import external, snapshot

def test_sub_snapshot():
    external("hash:123*.png")
    assert 1==snapshot(2)
"""
    )

    result = project.run("--inline-snapshot=fix")

    assert project.source == snapshot(
        """\
from inline_snapshot import external, snapshot

def test_sub_snapshot():
    external("hash:123*.png")
    assert 1==snapshot(1)
"""
    )

    assert result.ret == 0


def test_diff_multiple_files():

    Example(
        {
            "test_a.py": """
from inline_snapshot import snapshot

def test_a():
    assert 1==snapshot(2)
    """,
            "test_b.py": """
from inline_snapshot import snapshot

def test_b():
    assert 1==snapshot()
    """,
        }
    ).run_pytest(
        ["--inline-snapshot=create,fix"],
        changed_files=snapshot(
            {
                "test_b.py": """\

from inline_snapshot import snapshot

def test_b():
    assert 1==snapshot(1)
    \
""",
                "test_a.py": """\

from inline_snapshot import snapshot

def test_a():
    assert 1==snapshot(1)
    \
""",
            }
        ),
        report=snapshot(
            """\
------------------------------- Create snapshots -------------------------------
+--------------------------------- test_b.py ----------------------------------+
| @@ -2,5 +2,5 @@                                                              |
|                                                                              |
|  from inline_snapshot import snapshot                                        |
|                                                                              |
|  def test_b():                                                               |
| -    assert 1==snapshot()                                                    |
| +    assert 1==snapshot(1)                                                   |
+------------------------------------------------------------------------------+
These changes will be applied, because you used --inline-snapshot=create
-------------------------------- Fix snapshots ---------------------------------
+--------------------------------- test_a.py ----------------------------------+
| @@ -2,5 +2,5 @@                                                              |
|                                                                              |
|  from inline_snapshot import snapshot                                        |
|                                                                              |
|  def test_a():                                                               |
| -    assert 1==snapshot(2)                                                   |
| +    assert 1==snapshot(1)                                                   |
+------------------------------------------------------------------------------+
These changes will be applied, because you used --inline-snapshot=fix\
"""
        ),
    )


def test_equal_check():

    Example(
        {
            "test_a.py": """
from inline_snapshot import snapshot

class Thing:
    def __repr__(self):
        return "Thing()"

def test_a():
    assert Thing()==snapshot()
    """,
        }
    ).run_inline(
        ["--inline-snapshot=create"],
        changed_files=snapshot({}),
        raises=snapshot(
            """\
UsageError:
inline-snapshot uses `copy.deepcopy` to copy objects,
but the copied object is not equal to the original one:

original: Thing()
copied:   Thing()

Please fix the way your object is copied or your __eq__ implementation.
"""
        ),
    )


def test_unknown_flag():

    Example(
        """\
def test_a():
    assert 1==1
"""
    ).run_pytest(
        ["--inline-snapshot=creaigflen"],
        report=snapshot(""),
        returncode=snapshot(4),
        stderr=snapshot(
            """\
ERROR: --inline-snapshot=creaigflen is a unknown flag

"""
        ),
    )
