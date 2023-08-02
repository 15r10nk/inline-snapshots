import os.path


def pre_mutation(context):
    line = context.current_source_line.strip()
    if line.startswith(("assert False", "@overload")):
        context.skip = True

    if "= TypeVar" in line:
        context.skip = True

    return
    """Extract the coverage contexts if possible and only run the tests
    matching this data."""
    if not context.config.coverage_data:
        # mutmut was run without ``--use-coverage``
        return
    fname = os.path.abspath(context.filename)
    contexts_for_file = context.config.coverage_data.get(fname, {})
    contexts_for_line = contexts_for_file.get(context.current_line_index, [])
    print(line)
    print(contexts_for_line)

    context.config.test_command += " ".join(
        repr(arg) for arg in contexts_for_line if arg
    )
    print(context.config.test_command)
