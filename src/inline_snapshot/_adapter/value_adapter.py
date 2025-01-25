from __future__ import annotations

import ast
import warnings

from .._change import Replace
from .._code_repr import value_code_repr
from .._sentinels import undefined
from .._unmanaged import Unmanaged
from .._unmanaged import update_allowed
from .._utils import value_to_token
from ..syntax_warnings import InlineSnapshotInfo
from .adapter import Adapter


class ValueAdapter(Adapter):

    @classmethod
    def repr(cls, value):
        return value_code_repr(value)

    @classmethod
    def map(cls, value, map_function):
        return map_function(value)

    def assign(self, old_value, old_node, new_value):
        # generic fallback

        # because IsStr() != IsStr()
        if isinstance(old_value, Unmanaged):
            return old_value

        if old_node is None:
            new_token = []
        else:
            new_token = value_to_token(new_value)

        if isinstance(old_node, ast.JoinedStr) and isinstance(new_value, str):
            if not old_value == new_value:
                warnings.warn_explicit(
                    f"inline-snapshot will be able to fix f-strings in the future.\nThe current string value is:\n   {new_value!r}",
                    filename=self.context.file._source.filename,
                    lineno=old_node.lineno,
                    category=InlineSnapshotInfo,
                )
            return old_value

        if not old_value == new_value:
            if old_value is undefined:
                flag = "create"
            else:
                flag = "fix"
        elif (
            old_node is not None
            and update_allowed(old_value)
            and self.context.file._token_of_node(old_node) != new_token
        ):
            flag = "update"
        else:
            # equal and equal repr
            return old_value

        new_code = self.context.file._token_to_code(new_token)

        yield Replace(
            node=old_node,
            file=self.context.file._source,
            new_code=new_code,
            flag=flag,
            old_value=old_value,
            new_value=new_value,
        )

        return new_value
