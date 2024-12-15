from __future__ import annotations

import os
import platform
import re
import subprocess as sp
import sys
import traceback
from argparse import ArgumentParser
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from rich.console import Console

import inline_snapshot._external
from inline_snapshot._problems import report_problems

from .._change import apply_all
from .._flags import Flags
from .._global_state import snapshot_env
from .._rewrite_code import ChangeRecorder
from .._types import Category
from .._types import Snapshot

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


def normalize(text):
    text = ansi_escape.sub("", text)

    # fix windows problems
    text = text.replace("\u2500", "-")
    text = text.replace("\r", "")
    text = text.replace(" \n", " ⏎\n")
    return text


class Example:
    def __init__(self, files: str | dict[str, str]):
        """
        Parameters:
            files: a collecton of files where inline-snapshot opperates on,
                   or just a string which will be saved as *test_something.py*.
        """
        if isinstance(files, str):
            files = {"test_something.py": files}

        self.files = files

        self.dump_files()

    def dump_files(self):
        for name, content in self.files.items():
            print(f"file: {name}")
            print(content)
            print()

    def _write_files(self, dir: Path):
        for name, content in self.files.items():
            filename = dir / name
            filename.parent.mkdir(exist_ok=True, parents=True)
            filename.write_text(content)

    def _read_files(self, dir: Path):
        return {
            str(p.relative_to(dir)): p.read_text()
            for p in [*dir.iterdir(), *dir.rglob("*.py")]
            if p.is_file()
        }

    def run_inline(
        self,
        args: list[str] = [],
        *,
        reported_categories: Snapshot[list[Category]] | None = None,
        changed_files: Snapshot[dict[str, str]] | None = None,
        report: Snapshot[str] | None = None,
        raises: Snapshot[str] | None = None,
    ) -> Example:
        """Execute the example files in process and run every `test_*`
        function.

        This is useful for fast test execution.

        Parameters:
            args: inline-snapshot arguments (supports only "--inline-snapshot=fix|create|..." ).
            reported_categories: snapshot of categories which inline-snapshot thinks could be applied.
            changed_files: snapshot of files which are changed by this run.
            raises: snapshot of the exception which is raised during the test execution.
                    It is required if your code raises an exception.

        Returns:
            A new Example instance which contains the changed files.
        """

        parser = ArgumentParser()

        parser.add_argument(
            "--inline-snapshot",
            metavar="(disable,short-report,report,review,create,update,trim,fix)*",
            dest="inline_snapshot",
            help="update specific snapshot values:\n"
            "disable: disable the snapshot logic\n"
            "short-report: show a short report\n"
            "report: show a longer report with a diff report\n"
            "review: allow to approve the changes interactive\n"
            "create: creates snapshots which are currently not defined\n"
            "update: update snapshots even if they are defined\n"
            "trim: changes the snapshot in a way which will make the snapshot more precise.\n"
            "fix: change snapshots which currently break your tests\n",
        )
        parsed_args = parser.parse_args(args)
        flags = (parsed_args.inline_snapshot or "").split(",")

        with TemporaryDirectory() as dir:
            tmp_path = Path(dir)

            self._write_files(tmp_path)

            raised_exception = None
            with snapshot_env() as state:
                with ChangeRecorder().activate() as recorder:
                    state.update_flags = Flags({*flags})
                    inline_snapshot._external.storage = (
                        inline_snapshot._external.DiscStorage(tmp_path / ".storage")
                    )

                    try:
                        for filename in tmp_path.glob("*.py"):
                            globals: dict[str, Any] = {}
                            print("run> pytest", filename)
                            exec(
                                compile(filename.read_text("utf-8"), filename, "exec"),
                                globals,
                            )

                            # run all test_* functions
                            for k, v in globals.items():
                                if k.startswith("test_") and callable(v):
                                    v()
                    except Exception as e:
                        traceback.print_exc()
                        raised_exception = e

                    finally:
                        state.active = False

                    changes = []
                    for snapshot in state.snapshots.values():
                        changes += snapshot._changes()

                    snapshot_flags = {change.flag for change in changes}

                    apply_all(
                        [
                            change
                            for change in changes
                            if change.flag in state.update_flags.to_set()
                        ]
                    )
                recorder.fix_all()

                report_output = StringIO()
                console = Console(file=report_output)

                # TODO: add all the report output here
                report_problems(console)

            if reported_categories is not None:
                assert sorted(snapshot_flags) == reported_categories

            if raised_exception is not None:
                assert raises == f"{type(raised_exception).__name__}:\n" + str(
                    raised_exception
                )
            else:
                assert raises == None

            if changed_files is not None:
                current_files = {}

                for name, content in sorted(self._read_files(tmp_path).items()):
                    if name not in self.files or self.files[name] != content:
                        current_files[name] = content
                assert changed_files == current_files

            if report is not None:
                assert report == normalize(report_output.getvalue())

            return Example(self._read_files(tmp_path))

    def run_pytest(
        self,
        args: list[str] = [],
        *,
        term_columns=80,
        env: dict[str, str] = {},
        changed_files: Snapshot[dict[str, str]] | None = None,
        report: Snapshot[str] | None = None,
        stderr: Snapshot[str] | None = None,
        returncode: Snapshot[int] | None = 0,
    ) -> Example:
        """Run pytest with the given args and env variables in an seperate
        process.

        It can be used to test the interaction between your code and pytest, but it is a bit slower than `run_inline`

        Parameters:
            args: pytest arguments like "--inline-snapshot=fix"
            env: dict of environment variables
            changed_files: snapshot of files which are changed by this run.
            report: snapshot of the report at the end of the pytest run.
            stderr: pytest stderr output
            returncode: snapshot of the pytest returncode.

        Returns:
            A new Example instance which contains the changed files.
        """

        with TemporaryDirectory() as dir:
            tmp_path = Path(dir)
            self._write_files(tmp_path)

            cmd = [sys.executable, "-m", "pytest", *args]

            command_env = dict(os.environ)
            command_env["TERM"] = "unknown"
            command_env["COLUMNS"] = str(
                term_columns + 1 if platform.system() == "Windows" else term_columns
            )
            command_env.pop("CI", None)
            command_env.pop("GITHUB_ACTIONS", None)

            command_env.update(env)

            result = sp.run(cmd, cwd=tmp_path, capture_output=True, env=command_env)

            print("run>", *cmd)
            print("stdout:")
            print(result.stdout.decode())
            print("stderr:")
            print(result.stderr.decode())

            assert result.returncode == returncode

            if stderr is not None:
                assert result.stderr.decode() == stderr

            if report is not None:

                report_list = []
                record = False
                for line in result.stdout.decode().splitlines():
                    line = line.strip()
                    if line.startswith("===="):
                        record = False

                    if record and line:
                        report_list.append(line)

                    if line.startswith("====") and "inline snapshot" in line:
                        record = True

                report_str = "\n".join(report_list)

                assert normalize(report_str) == report, repr(report_str)

            if changed_files is not None:
                current_files = {}

                for name, content in sorted(self._read_files(tmp_path).items()):
                    if name not in self.files or self.files[name] != content:
                        current_files[name] = content
                assert changed_files == current_files

            return Example(self._read_files(tmp_path))
