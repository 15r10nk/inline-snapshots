from inline_snapshot import snapshot
from inline_snapshot.testing._example import Example


def test_ci():
    Example(
        """
from inline_snapshot import snapshot
def test_something():
    assert type(snapshot(5)) is int

    """
    ).run_pytest(
        env={"CI": "true"},
        report=snapshot(
            """\
INFO: CI run was detected because environment variable "CI" was defined.
INFO: inline-snapshot runs with --inline-snapshot=disabled by default in CI.\
"""
        ),
    ).run_pytest(
        ["--inline-snapshot=disable"],
        env={"CI": "true"},
        report=snapshot(""),
    )
