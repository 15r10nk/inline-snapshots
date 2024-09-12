import os
import platform
import re
import shutil
import sys
import textwrap
import traceback
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from types import SimpleNamespace
from typing import Set
from unittest import mock

import black
import executing
import inline_snapshot._external
import pytest
from inline_snapshot import _inline_snapshot
from inline_snapshot._change import apply_all
from inline_snapshot._format import format_code
from inline_snapshot._inline_snapshot import Flags
from inline_snapshot._rewrite_code import ChangeRecorder
from inline_snapshot._types import Category
from inline_snapshot.testing._example import snapshot_env

pytest_plugins = "pytester"


pytest.register_assert_rewrite("tests.example")

black.files.find_project_root = black.files.find_project_root.__wrapped__  # type: ignore


@pytest.fixture(autouse=True)
def check_pypy(request):
    implementation = sys.implementation.name
    node = request.node

    if implementation != "cpython" and node.get_closest_marker("no_rewriting") is None:
        pytest.skip(f"{implementation} is not supported")

    yield


@pytest.fixture()
def check_update(source):
    def w(source_code, *, flags="", reported_flags=None, number=1):
        s = source(source_code)
        flags = {*flags.split(",")} - {""}

        if reported_flags is None:
            reported_flags = flags
        else:
            reported_flags = {*reported_flags.split(",")} - {""}

        assert s.flags == reported_flags
        assert s.number_snapshots == number
        assert s.error == ("fix" in s.flags)

        s2 = s.run(*flags)

        return s2.source

    return w


@pytest.fixture()
def source(tmp_path: Path):
    filecount = 1

    @dataclass
    class Source:
        source: str
        flags: Set[str] = field(default_factory=set)
        error: bool = False
        number_snapshots: int = 0
        number_changes: int = 0

        def run(self, *flags_arg: Category):
            flags = Flags({*flags_arg})

            nonlocal filecount
            filename: Path = tmp_path / f"test_{filecount}.py"
            filecount += 1

            prefix = """\"\"\"
PYTEST_DONT_REWRITE
\"\"\"
# äöß 🐍
from inline_snapshot import snapshot
from inline_snapshot import external
from inline_snapshot import outsource

"""
            source = prefix + textwrap.dedent(self.source)

            filename.write_text(source, "utf-8")

            print()
            print("input:")
            print(textwrap.indent(source, " |", lambda line: True).rstrip())

            with snapshot_env():
                with ChangeRecorder().activate() as recorder:
                    _inline_snapshot._update_flags = flags
                    inline_snapshot._external.storage = (
                        inline_snapshot._external.HashStorage(tmp_path / ".storage")
                    )

                    error = False

                    try:
                        exec(compile(filename.read_text("utf-8"), filename, "exec"), {})
                    except AssertionError:
                        traceback.print_exc()
                        error = True
                    finally:
                        _inline_snapshot._active = False

                    number_snapshots = len(_inline_snapshot.snapshots)

                    changes = []
                    for snapshot in _inline_snapshot.snapshots.values():
                        changes += snapshot._changes()

                    snapshot_flags = {change.flag for change in changes}

                    apply_all(
                        [
                            change
                            for change in changes
                            if change.flag in _inline_snapshot._update_flags.to_set()
                        ]
                    )

                    recorder.fix_all()

            source = filename.read_text("utf-8")[len(prefix) :]
            print("reported_flags:", snapshot_flags)
            print(
                f"run: pytest" + f' --inline-snapshot={",".join(flags.to_set())}'
                if flags
                else ""
            )
            print("output:")
            print(textwrap.indent(source, " |", lambda line: True).rstrip())

            return Source(
                source=source,
                flags=snapshot_flags,
                error=error,
                number_snapshots=number_snapshots,
                number_changes=len(changes),
            )

    def w(source):
        return Source(source=source).run()

    return w


ansi_escape = re.compile(
    r"""
    \x1B  # ESC
    (?:   # 7-bit C1 Fe (except CSI)
        [@-Z\\-_]
    |     # or [ for CSI, followed by a control sequence
        \[
        [0-?]*  # Parameter bytes
        [ -/]*  # Intermediate bytes
        [@-~]   # Final byte
    )
""",
    re.VERBOSE,
)


class RunResult:
    def __init__(self, result):
        self._result = result

    def __getattr__(self, name):
        return getattr(self._result, name)

    @staticmethod
    def _join_lines(lines):
        text = "\n".join(lines).rstrip()

        if "\n" in text:
            return text + "\n"
        else:
            return text

    @property
    def report(self):
        result = []
        record = False
        for line in self._result.stdout.lines:
            line = line.strip()
            if line.startswith("===="):
                record = False

            if record and line:
                result.append(line)

            if line.startswith("====") and "inline snapshot" in line:
                record = True

        result = self._join_lines(result)

        result = ansi_escape.sub("", result)

        # fix windows problems
        result = result.replace("\u2500", "-")
        result = result.replace("\r", "")
        result = result.replace(" \n", " ⏎\n")

        return result

    @property
    def errors(self):
        result = []
        record = False
        for line in self._result.stdout.lines:
            line = line.strip()

            if line.startswith("====") and "ERRORS" in line:
                record = True
            if record and line:
                result.append(line)
        result = self._join_lines(result)
        result = result.replace(" \n", " ⏎\n")

        result = re.sub(r"\d+\.\d+s", "<time>", result)
        return result

    def errorLines(self):
        result = self._join_lines(
            [line for line in self.stdout.lines if line and line[:2] in ("> ", "E ")]
        )
        result = result.replace(" \n", " ⏎\n")
        return result


@pytest.fixture
def project(pytester):
    class Project:

        def __init__(self):
            self.term_columns = 80

        def setup(self, source: str, add_header=True):
            if add_header:
                self.header = """\
# äöß 🐍
from inline_snapshot import snapshot
from inline_snapshot import outsource
"""
                if "# no imports" in source:
                    self.header = """\
# äöß 🐍
"""
                else:
                    self.header = """\
# äöß 🐍
from inline_snapshot import snapshot
from inline_snapshot import outsource
"""
            else:
                self.header = ""

            header = self.header
            if not source.startswith(("import ", "from ")):
                header += "\n\n"

            source = header + source
            print("write code:")
            print(source)
            self._filename.write_text(source, "utf-8")

            (pytester.path / "conftest.py").write_text(
                """
import datetime
import pytest
from freezegun.api import FakeDatetime,FakeDate
from inline_snapshot import customize_repr

@customize_repr
def _(value:FakeDatetime):
    return value.__repr__().replace("FakeDatetime","datetime.datetime")

@customize_repr
def _(value:FakeDate):
    return value.__repr__().replace("FakeDate","datetime.date")


@pytest.fixture(autouse=True)
def set_time(freezer):
        freezer.move_to(datetime.datetime(2024, 3, 14, 0, 0, 0, 0))
        yield
"""
            )

        @property
        def _filename(self):
            return pytester.path / "test_file.py"

        def is_formatted(self):
            code = self._filename.read_text("utf-8")
            return code == format_code(code, self._filename)

        def format(self):
            self._filename.write_text(
                format_code(self._filename.read_text("utf-8"), self._filename), "utf-8"
            )

        def pyproject(self, source):
            self.write_file("pyproject.toml", source)

        def write_file(self, filename, content):
            (pytester.path / filename).write_text(content, "utf-8")

        def storage(self):
            dir = pytester.path / ".inline-snapshot" / "external"

            if not dir.exists():
                return []

            return sorted(p.name for p in dir.iterdir() if p.name != ".gitignore")

        @property
        def source(self):
            assert self._filename.read_text("utf-8")[: len(self.header)] == self.header
            return self._filename.read_text("utf-8")[len(self.header) :].lstrip()

        def run(self, *args, stdin=""):
            cache = pytester.path / "__pycache__"
            if cache.exists():
                shutil.rmtree(cache)

            # pytest adds -v if it detects some github CI variable
            old_environ = dict(os.environ)
            if "CI" in os.environ:
                del os.environ["CI"]  # pragma: no cover

            try:
                with mock.patch.dict(
                    os.environ,
                    {
                        "TERM": "unknown",
                        "COLUMNS": str(
                            self.term_columns + 1
                            if platform.system() == "Windows"
                            else self.term_columns
                        ),
                    },
                ):

                    if stdin:
                        result = pytester.run("pytest", *args, stdin=stdin)
                    else:
                        result = pytester.run("pytest", *args)
            finally:
                os.environ.update(old_environ)

            return RunResult(result)

    return Project()


@pytest.fixture(params=[True, False], ids=["executing", "without-executing"])
def executing_used(request, monkeypatch):
    used = request.param
    if used:
        yield used
    else:

        def fake_executing(frame):
            return SimpleNamespace(node=None)

        monkeypatch.setattr(executing.Source, "executing", fake_executing)
        yield used
