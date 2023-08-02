pytest_plugins = "pytester"

import pytest
import coverage

import os

ctx_key = "COVERAGE_CONTEXT"


@pytest.fixture(autouse=True)
def coverage_context(request):
    ctx = request.node.nodeid
    coverage.Coverage.current().switch_context(request.node.nodeid)

    os.environ[ctx_key] = ctx

    yield

    coverage.Coverage.current().switch_context("")
