import itertools
import platform
import re
import sys
import textwrap
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest
from executing import is_pytest_compatible

from inline_snapshot import snapshot
from inline_snapshot._flags import Flags
from inline_snapshot._global_state import state
from inline_snapshot.extra import raises


@dataclass
class Block:
    code: str
    code_header: Optional[str]
    block_options: str
    line: int


def map_code_blocks(file, func, fix=False):

    block_start = re.compile("( *)``` *python(.*)")
    block_end = re.compile("```.*")

    header = re.compile("<!--(.*)-->")

    current_code = file.read_text("utf-8")
    new_lines = []
    block_lines = []
    is_block = False
    code = None
    indent = ""
    block_start_linenum = None
    block_options = None
    code_header = None
    header_line = ""

    for linenumber, line in enumerate(current_code.splitlines(), start=1):
        m = block_start.fullmatch(line)
        if m and not is_block:
            # ``` python
            block_start_linenum = linenumber
            indent = m[1]
            block_options = m[2]
            block_lines = []
            is_block = True
            continue

        if block_end.fullmatch(line.strip()) and is_block:
            # ```
            is_block = False

            code = "\n".join(block_lines) + "\n"
            code = textwrap.dedent(code)
            if file.suffix == ".py":
                code = code.replace("\\\\", "\\")

            try:
                new_block = func(
                    Block(
                        code=code,
                        code_header=code_header,
                        block_options=block_options,
                        line=block_start_linenum,
                    )
                )
            except Exception:
                print(f"error at block at line {block_start_linenum}")
                print(f"{code_header=}")
                print(f"{block_options=}")
                print(code)
                raise

            if new_block.code_header is not None:
                new_lines.append(f"{indent}<!-- {new_block.code_header.strip()} -->")

            new_lines.append(
                f"{indent}``` {('python '+new_block.block_options.strip()).strip()}"
            )

            new_code = new_block.code.rstrip()
            if file.suffix == ".py":
                new_code = new_code.replace("\\", "\\\\")
            new_code = textwrap.indent(new_code, indent)

            new_lines.append(new_code)

            new_lines.append(f"{indent}```")

            header_line = ""
            code_header = None

            continue

        if is_block:
            block_lines.append(line)
            continue

        m = header.fullmatch(line.strip())
        if m:
            # comment <!-- ... -->
            header_line = line
            code_header = m[1].strip()
            continue
        else:
            if header_line:
                new_lines.append(header_line)
                code_header = None
                header_line = ""

        new_lines.append(line)

    new_code = "\n".join(new_lines) + "\n"

    if fix:
        file.write_text(new_code)
    else:
        assert current_code.splitlines() == new_code.splitlines()
        assert current_code == new_code


def test_map_code_blocks(tmp_path):

    file = tmp_path / "example.md"

    def test_doc(
        markdown_code,
        handle_block=lambda block: exec(block.code),
        blocks=[],
        exception="<no exception>",
        new_markdown_code=None,
    ):

        file.write_text(markdown_code)

        recorded_blocks = []

        with raises(exception):

            def test_block(block):
                handle_block(block)
                recorded_blocks.append(block)
                return block

            map_code_blocks(file, test_block, True)
            assert recorded_blocks == blocks
            map_code_blocks(file, test_block, False)

        recorded_markdown_code = file.read_text()
        if recorded_markdown_code != markdown_code:
            assert new_markdown_code == recorded_markdown_code
        else:
            assert new_markdown_code is None

    test_doc(
        """
``` python
1 / 0
```
""",
        exception=snapshot("ZeroDivisionError: division by zero"),
    )

    test_doc(
        """\
text
``` python
print(1 + 1)
```
text
<!-- inline-snapshot: create test -->
``` python hl_lines="1 2 3"
print(1 - 1)
```
text
""",
        blocks=snapshot(
            [
                Block(
                    code="print(1 + 1)\n", code_header=None, block_options="", line=2
                ),
                Block(
                    code="print(1 - 1)\n",
                    code_header="inline-snapshot: create test",
                    block_options=' hl_lines="1 2 3"',
                    line=7,
                ),
            ]
        ),
    )

    def change_block(block):
        block.code = "# removed"
        block.code_header = "header"
        block.block_options = "option a b c"

    test_doc(
        """\
text
``` python
print(1 + 1)
```
""",
        handle_block=change_block,
        blocks=snapshot(
            [
                Block(
                    code="# removed",
                    code_header="header",
                    block_options="option a b c",
                    line=2,
                )
            ]
        ),
        new_markdown_code=snapshot(
            """\
text
<!-- header -->
``` python option a b c
# removed
```
"""
        ),
    )


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="\\r in stdout can cause problems in snapshot strings",
)
@pytest.mark.skipif(
    sys.version_info[:2] != (3, 12),
    reason="there is no reason to test the doc with different python versions",
)
@pytest.mark.parametrize(
    "file",
    [
        pytest.param(file, id=file.name)
        for file in [
            *(Path(__file__).parent.parent / "docs").rglob("*.md"),
            *(Path(__file__).parent.parent).glob("*.md"),
            *(Path(__file__).parent.parent / "src").rglob("*.py"),
        ]
    ],
)
def test_docs(project, file, subtests):
    """Test code blocks with the header <!-- inline-snapshot: options ... -->

    where options can be:
        * flags passed to --inline-snapshot=...
        * `first_block` to specify that the input source code should be the current block and not the last
        * `outcome-passed=2` to check for the pytest test outcome
    """

    last_code = None

    project.pyproject(
        """
[tool.black]
line-length=80
"""
    )

    extra_files = defaultdict(list)

    def test_block(block: Block):
        if block.code_header is None:
            return block

        if block.code_header.startswith("inline-snapshot-lib:"):
            extra_files[block.code_header.split()[1]].append(block.code)
            return block

        if block.code_header.startswith("todo-inline-snapshot:"):
            return block

        nonlocal last_code
        with subtests.test(line=block.line):

            code = block.code

            options = set(block.code_header.split())

            if "requires_assert" in options and not is_pytest_compatible():
                return block

            flags = options & Flags.all().to_set()

            args = ["--inline-snapshot", ",".join(flags)] if flags else []

            if flags and "first_block" not in options:
                project.setup(last_code, add_header=False)
            else:
                project.setup(code, add_header=False)

            if extra_files:
                all_files = [
                    [(key, file) for file in files]
                    for key, files in extra_files.items()
                ]
                for files in itertools.product(*all_files):
                    for filename, content in files:
                        project.write_file(filename, content)
                        result = project.run(*args)

            else:

                result = project.run(*args)

            print("flags:", flags, repr(block.block_options))

            new_code = code
            if flags:
                new_code = project.source

            if "show_error" in options:
                new_code = new_code.split("# Error:")[0]
                new_code += "# Error:\n" + textwrap.indent(result.errorLines(), "# ")

            print("new code:")
            print(new_code)
            print("expected code:")
            print(code)

            block.code_header = "inline-snapshot: " + " ".join(
                sorted(flags)
                + sorted(options & {"first_block", "show_error", "requires_assert"})
                + [
                    f"outcome-{k}={v}"
                    for k, v in result.parseoutcomes().items()
                    if k in ("failed", "errors", "passed")
                ]
            )

            from inline_snapshot._align import align

            linenum = 1
            hl_lines = ""
            if last_code is not None and "first_block" not in options:
                changed_lines = []
                alignment = align(last_code.split("\n"), new_code.split("\n"))
                for c in alignment:
                    if c == "d":
                        continue
                    elif c == "m":
                        linenum += 1
                    else:
                        changed_lines.append(str(linenum))
                        linenum += 1
                if changed_lines:
                    hl_lines = f'hl_lines="{" ".join(changed_lines)}"'
                else:
                    assert False, "no lines changed"
            block.block_options = hl_lines

            block.code = new_code

            if flags - {"create"}:
                assert result.ret == 0

            last_code = code
        return block

    map_code_blocks(file, test_block, state().update_flags.fix)
