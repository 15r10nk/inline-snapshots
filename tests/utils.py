import contextlib
import sys
from contextlib import contextmanager

import inline_snapshot._config as _config
import inline_snapshot._external as external
import pytest
from inline_snapshot._rewrite_code import ChangeRecorder
from inline_snapshot.testing._example import snapshot_env


__all__ = ("snapshot_env",)

pytest_compatible = sys.version_info >= (3, 11) and pytest.version_tuple >= (8, 3, 4)


@contextlib.contextmanager
def config(**args):
    current_config = _config.config
    _config.config = _config.Config(**args)
    try:
        yield
    finally:
        _config.config = current_config


@contextlib.contextmanager
def apply_changes():
    with ChangeRecorder().activate() as recorder:
        yield

        recorder.fix_all()


@contextmanager
def useStorage(storage):
    old_storage = external.storage
    external.storage = storage
    yield
    external.storage = old_storage


@pytest.fixture()
def storage(tmp_path):
    storage = external.HashStorage(tmp_path / ".storage")
    with useStorage(storage):
        yield storage
