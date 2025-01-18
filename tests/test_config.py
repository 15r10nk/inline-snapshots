from inline_snapshot import snapshot
from inline_snapshot.testing import Example

file_to_trim = {
    "test_a.py": """\
from inline_snapshot import snapshot

def test_a():
    assert 1 <= snapshot(5)
    assert 1 == snapshot(2)
""",
}

trimmed_files = snapshot(
    {
        "test_a.py": """\
from inline_snapshot import snapshot

def test_a():
    assert 1 <= snapshot(1)
    assert 1 == snapshot(2)
"""
    }
)


def test_config_pyproject():

    Example(
        {
            **file_to_trim,
            "pyproject.toml": """
[tool.inline-snapshot]
default-flags = ["trim"]
            """,
        }
    ).run_pytest(changed_files=trimmed_files, returncode=snapshot(1))


def test_config_env():
    Example(file_to_trim).run_pytest(
        env={"INLINE_SNAPSHOT_DEFAULT_FLAGS": "trim"},
        changed_files=trimmed_files,
        returncode=snapshot(1),
    )


def test_shortcuts():

    Example(
        {
            **file_to_trim,
            "pyproject.toml": """
[tool.inline-snapshot.shortcuts]
strim=["trim"]
            """,
        }
    ).run_pytest(["--strim"], changed_files=trimmed_files, returncode=snapshot(1))


def test_default_shortcuts():

    Example(
        {
            **file_to_trim,
            "pyproject.toml": """
            """,
        }
    ).run_pytest(
        ["--fix"],
        changed_files=snapshot(
            {
                "test_a.py": """\
from inline_snapshot import snapshot

def test_a():
    assert 1 <= snapshot(5)
    assert 1 == snapshot(1)
"""
            }
        ),
    )
