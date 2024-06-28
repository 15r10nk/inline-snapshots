import ast
import copy
import inspect
import tokenize
from collections import defaultdict
from pathlib import Path
from typing import Any
from typing import Dict  # noqa
from typing import Iterator
from typing import Set
from typing import Tuple  # noqa
from typing import TypeVar

from executing import Source

from ._align import add_x
from ._align import align
from ._change import apply_all
from ._change import CallArg
from ._change import Change
from ._change import Delete
from ._change import DictInsert
from ._change import ListInsert
from ._change import Replace
from ._format import format_code
from ._sentinels import undefined
from ._utils import ignore_tokens
from ._utils import normalize
from ._utils import simple_token
from ._utils import value_to_token


class NotImplementedYet(Exception):
    pass


snapshots = {}  # type: Dict[Tuple[int, int], Snapshot]

_active = False

_files_with_snapshots: Set[str] = set()

_missing_values = 0


class Flags:
    """
    fix: the value needs to be changed to pass the tests
    update: the value should be updated because the token-stream has changed
    create: the snapshot is empty `snapshot()`
    trim: the snapshot contains more values than neccessary. 1 could be trimmed in `5 in snapshot([1,5])`.
    """

    def __init__(self, flags=set()):
        self.fix = "fix" in flags
        self.update = "update" in flags
        self.create = "create" in flags
        self.trim = "trim" in flags

    def to_set(self):
        return {k for k, v in self.__dict__.items() if v}

    def __repr__(self):
        return f"Flags({self.to_set()})"


_update_flags = Flags()


def ignore_old_value():
    return _update_flags.fix or _update_flags.update


class GenericValue:
    _new_value: Any
    _old_value: Any
    _current_op = "undefined"
    _ast_node: ast.Expr
    _source: Source

    def _token_of_node(self, node):

        return list(
            normalize(
                [
                    simple_token(t.type, t.string)
                    for t in self._source.asttokens().get_tokens(node)
                    if t.type not in ignore_tokens
                ]
            )
        )

    def _format(self, text):
        if self._source is None:
            return text
        else:
            return format_code(text, Path(self._source.filename))

    def _token_to_code(self, tokens):
        return self._format(tokenize.untokenize(tokens)).strip()

    def _value_to_code(self, value):
        return self._token_to_code(value_to_token(value))

    def _ignore_old(self):
        return (
            _update_flags.fix
            or _update_flags.update
            or _update_flags.create
            or self._old_value is undefined
        )

    def _visible_value(self):
        if self._ignore_old():
            return self._new_value
        else:
            return self._old_value

    def _get_changes(self) -> Iterator[Change]:
        raise NotImplementedYet()

    def _new_code(self):
        raise NotImplementedYet()

    def __repr__(self):
        return repr(self._visible_value())

    def _type_error(self, op):
        __tracebackhide__ = True
        raise TypeError(
            f"This snapshot cannot be use with `{op}`, because it was previously used with `{self._current_op}`"
        )

    def __eq__(self, _other):
        __tracebackhide__ = True
        self._type_error("==")

    def __le__(self, _other):
        __tracebackhide__ = True
        self._type_error("<=")

    def __ge__(self, _other):
        __tracebackhide__ = True
        self._type_error(">=")

    def __contains__(self, _other):
        __tracebackhide__ = True
        self._type_error("in")

    def __getitem__(self, _item):
        __tracebackhide__ = True
        self._type_error("snapshot[key]")


class UndecidedValue(GenericValue):
    def __init__(self, old_value, ast_node, source):
        self._old_value = old_value
        self._new_value = undefined
        self._ast_node = ast_node
        self._source = source

    def _change(self, cls):
        self.__class__ = cls

    def _new_code(self):
        return ""

    def _get_changes(self) -> Iterator[Change]:
        # generic fallback
        new_token = value_to_token(self._old_value)

        if (
            self._ast_node is not None
            and self._token_of_node(self._ast_node) != new_token
        ):
            flag = "update"
        else:
            return

        new_code = self._token_to_code(new_token)

        yield Replace(
            node=self._ast_node,
            source=self._source,
            new_code=new_code,
            flag=flag,
            old_value=self._old_value,
            new_value=self._old_value,
        )

    # functions which determine the type

    def __eq__(self, other):
        self._change(EqValue)
        return self == other

    def __le__(self, other):
        self._change(MinValue)
        return self <= other

    def __ge__(self, other):
        self._change(MaxValue)
        return self >= other

    def __contains__(self, other):
        self._change(CollectionValue)
        return other in self

    def __getitem__(self, item):
        self._change(DictValue)
        return self[item]


try:
    import dirty_equals  # type: ignore
except ImportError:  # pragma: no cover

    def update_allowed(value):
        return True

else:

    def update_allowed(value):
        return not isinstance(value, dirty_equals.DirtyEquals)


class EqValue(GenericValue):
    _current_op = "x == snapshot"

    def __eq__(self, other):
        global _missing_values
        if self._old_value is undefined:
            _missing_values += 1

        other = copy.deepcopy(other)

        if self._new_value is undefined:
            self._new_value = other

        return other == self._visible_value()

    def _new_code(self):
        return self._value_to_code(self._new_value)

    def _get_changes(self) -> Iterator[Change]:

        assert self._old_value is not undefined

        def check(old_value, old_node, new_value):

            if (
                isinstance(old_node, ast.List)
                and isinstance(new_value, list)
                and isinstance(old_value, list)
                or isinstance(old_node, ast.Tuple)
                and isinstance(new_value, tuple)
                and isinstance(old_value, tuple)
            ):
                diff = add_x(align(old_value, new_value))
                old = zip(old_value, old_node.elts)
                new = iter(new_value)
                old_position = 0
                to_insert = defaultdict(list)
                for c in diff:
                    if c in "mx":
                        old_value_element, old_node_element = next(old)
                        new_value_element = next(new)
                        yield from check(
                            old_value_element, old_node_element, new_value_element
                        )
                        old_position += 1
                    elif c == "i":
                        new_value_element = next(new)
                        new_code = self._value_to_code(new_value_element)
                        to_insert[old_position].append((new_code, new_value_element))
                    elif c == "d":
                        old_value_element, old_node_element = next(old)
                        yield Delete(
                            "fix", self._source, old_node_element, old_value_element
                        )
                        old_position += 1
                    else:
                        assert False

                for position, code_values in to_insert.items():
                    yield ListInsert(
                        "fix", self._source, old_node, position, *zip(*code_values)
                    )

                return

            elif (
                isinstance(old_node, ast.Dict)
                and isinstance(new_value, dict)
                and isinstance(old_value, dict)
                and len(old_value) == len(old_node.keys)
            ):
                for value, node in zip(old_value.keys(), old_node.keys):
                    assert node is not None

                    try:
                        # this is just a sanity check, dicts should be ordered
                        node_value = ast.literal_eval(node)
                    except:
                        continue
                    assert node_value == value

                for key, node in zip(old_value.keys(), old_node.values):
                    if key in new_value:
                        # check values with same keys
                        yield from check(old_value[key], node, new_value[key])
                    else:
                        # delete entries
                        yield Delete("fix", self._source, node, old_value[key])

                to_insert = []
                insert_pos = 0
                for key, new_value_element in new_value.items():
                    if key not in old_value:
                        # add new values
                        to_insert.append((key, new_value_element))
                    else:
                        if to_insert:
                            new_code = [
                                (self._value_to_code(k), self._value_to_code(v))
                                for k, v in to_insert
                            ]
                            yield DictInsert(
                                "fix",
                                self._source,
                                old_node,
                                insert_pos,
                                new_code,
                                to_insert,
                            )
                            to_insert = []
                        insert_pos += 1

                if to_insert:
                    new_code = [
                        (self._value_to_code(k), self._value_to_code(v))
                        for k, v in to_insert
                    ]
                    yield DictInsert(
                        "fix",
                        self._source,
                        old_node,
                        len(old_node.values),
                        new_code,
                        to_insert,
                    )

                return

            # generic fallback
            new_token = value_to_token(new_value)

            if not new_value == old_value:
                flag = "fix"
            elif (
                self._ast_node is not None
                and self._token_of_node(old_node) != new_token
                and update_allowed(old_value)
            ):
                flag = "update"
            else:
                return

            new_code = self._token_to_code(new_token)

            yield Replace(
                node=old_node,
                source=self._source,
                new_code=new_code,
                flag=flag,
                old_value=old_value,
                new_value=new_value,
            )

        yield from check(self._old_value, self._ast_node, self._new_value)


class MinMaxValue(GenericValue):
    """Generic implementation for <=, >="""

    @staticmethod
    def cmp(a, b):
        raise NotImplemented

    def _generic_cmp(self, other):
        global _missing_values
        if self._old_value is undefined:
            _missing_values += 1
        other = copy.deepcopy(other)

        if self._new_value is undefined:
            self._new_value = other
        else:
            self._new_value = (
                self._new_value if self.cmp(self._new_value, other) else other
            )

        return self.cmp(self._visible_value(), other)

    def _new_code(self):
        return self._value_to_code(self._new_value)

    def _get_changes(self) -> Iterator[Change]:
        new_token = value_to_token(self._new_value)
        if not self.cmp(self._old_value, self._new_value):
            flag = "fix"
        elif not self.cmp(self._new_value, self._old_value):
            flag = "trim"
        elif (
            self._ast_node is not None
            and self._token_of_node(self._ast_node) != new_token
        ):
            flag = "update"
        else:
            return

        new_code = self._token_to_code(new_token)

        yield Replace(
            node=self._ast_node,
            source=self._source,
            new_code=new_code,
            flag=flag,
            old_value=self._old_value,
            new_value=self._new_value,
        )


class MinValue(MinMaxValue):
    """
    handles:

    >>> snapshot(5) <= 6
    True

    >>> 6 >= snapshot(5)
    True

    """

    _current_op = "x >= snapshot"

    @staticmethod
    def cmp(a, b):
        return a <= b

    __le__ = MinMaxValue._generic_cmp


class MaxValue(MinMaxValue):
    """
    handles:

    >>> snapshot(5) >= 4
    True

    >>> 4 <= snapshot(5)
    True

    """

    _current_op = "x <= snapshot"

    @staticmethod
    def cmp(a, b):
        return a >= b

    __ge__ = MinMaxValue._generic_cmp


class CollectionValue(GenericValue):
    _current_op = "x in snapshot"

    def __contains__(self, item):
        global _missing_values
        if self._old_value is undefined:
            _missing_values += 1

        item = copy.deepcopy(item)

        if self._new_value is undefined:
            self._new_value = [item]
        else:
            if item not in self._new_value:
                self._new_value.append(item)

        if ignore_old_value() or self._old_value is undefined:
            return True
        else:
            return item in self._old_value

    def _new_code(self):
        return self._value_to_code(self._new_value)

    def _get_changes(self) -> Iterator[Change]:

        if self._ast_node is None:
            elements = [None] * len(self._old_value)
        else:
            assert isinstance(self._ast_node, ast.List)
            elements = self._ast_node.elts

        for old_value, old_node in zip(self._old_value, elements):
            if old_value not in self._new_value:
                yield Delete(
                    flag="trim", source=self._source, node=old_node, old_value=old_value
                )
                continue

            # check for update
            new_token = value_to_token(old_value)

            if old_node is not None and self._token_of_node(old_node) != new_token:
                new_code = self._token_to_code(new_token)

                yield Replace(
                    node=old_node,
                    source=self._source,
                    new_code=new_code,
                    flag="update",
                    old_value=old_value,
                    new_value=old_value,
                )

        new_values = [v for v in self._new_value if v not in self._old_value]
        if new_values:
            yield ListInsert(
                flag="fix",
                source=self._source,
                node=self._ast_node,
                position=len(self._old_value),
                new_code=[self._value_to_code(v) for v in new_values],
                new_values=new_values,
            )


class DictValue(GenericValue):
    _current_op = "snapshot[key]"

    def __getitem__(self, index):
        global _missing_values

        if self._new_value is undefined:
            self._new_value = {}

        old_value = self._old_value
        if old_value is undefined:
            _missing_values += 1
            old_value = {}

        child_node = None
        if self._ast_node is not None:
            assert isinstance(self._ast_node, ast.Dict)
            if index in old_value:
                pos = list(old_value.keys()).index(index)
                child_node = self._ast_node.values[pos]

        if index not in self._new_value:
            self._new_value[index] = UndecidedValue(
                old_value.get(index, undefined), child_node, self._source
            )

        return self._new_value[index]

    def _new_code(self):
        return (
            "{"
            + ", ".join(
                [
                    f"{self._value_to_code(k)}: {v._new_code()}"
                    for k, v in self._new_value.items()
                    if not isinstance(v, UndecidedValue)
                ]
            )
            + "}"
        )

    def _get_changes(self) -> Iterator[Change]:

        assert self._old_value is not undefined

        if self._ast_node is None:
            values = [None] * len(self._old_value)
        else:
            assert isinstance(self._ast_node, ast.Dict)
            values = self._ast_node.values

        for key, node in zip(self._old_value.keys(), values):
            if key in self._new_value:
                # check values with same keys
                yield from self._new_value[key]._get_changes()
            else:
                # delete entries
                yield Delete("trim", self._source, node, self._old_value[key])

        to_insert = []
        for key, new_value_element in self._new_value.items():
            if key not in self._old_value and not isinstance(
                new_value_element, UndecidedValue
            ):
                # add new values
                to_insert.append((key, new_value_element._new_code()))

        if to_insert:
            new_code = [(self._value_to_code(k), v) for k, v in to_insert]
            yield DictInsert(
                "create",
                self._source,
                self._ast_node,
                len(self._old_value),
                new_code,
                to_insert,
            )


T = TypeVar("T")


class ReprWrapper:
    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def __repr__(self):
        return self.func.__name__


_T = TypeVar("_T")


def repr_wrapper(func: _T) -> _T:
    return ReprWrapper(func)  # type: ignore


@repr_wrapper
def snapshot(obj: Any = undefined) -> Any:
    """`snapshot()` is a placeholder for some value.

    `pytest --inline-snapshot=create` will create the value which matches your conditions.

    >>> assert 5 == snapshot()
    >>> assert 5 <= snapshot()
    >>> assert 5 >= snapshot()
    >>> assert 5 in snapshot()

    `snapshot()[key]` can be used to create sub-snapshots.

    The generated value will be inserted as argument to `snapshot()`

    >>> assert 5 == snapshot(5)

    `snapshot(value)` has general the semantic of an noop which returns `value`.
    """
    if not _active:
        if obj is undefined:
            raise AssertionError(
                "your snapshot is missing a value run pytest with --inline-snapshot=create"
            )
        else:
            return obj

    frame = inspect.currentframe()
    assert frame is not None
    frame = frame.f_back
    assert frame is not None
    frame = frame.f_back
    assert frame is not None

    expr = Source.executing(frame)

    module = inspect.getmodule(frame)
    if module is not None and module.__file__ is not None:
        _files_with_snapshots.add(module.__file__)

    key = id(frame.f_code), frame.f_lasti

    if key not in snapshots:
        node = expr.node
        if node is None:
            # we can run without knowing of the calling expression but we will not be able to fix code
            snapshots[key] = Snapshot(obj, None)
        else:
            assert isinstance(node, ast.Call)
            snapshots[key] = Snapshot(obj, expr)

    return snapshots[key]._value


def used_externals(tree):
    return [
        n.args[0].value
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "external"
        and n.args
        and isinstance(n.args[0], ast.Constant)
    ]


class Snapshot:
    def __init__(self, value, expr):
        self._expr = expr
        node = expr.node.args[0] if expr is not None and expr.node.args else None
        source = expr.source if expr is not None else None
        self._value = UndecidedValue(value, node, source)
        self._uses_externals = []

    def _changes(self):
        if self._value._old_value is undefined:
            new_code = self._value._new_code()
            try:
                ast.parse(new_code)
            except:
                return

            yield CallArg(
                "create",
                self._value._source,
                self._expr.node if self._expr is not None else None,
                0,
                None,
                new_code,
                self._value._old_value,
                self._value._new_value,
            )

        else:

            yield from self._value._get_changes()

    def _change(self):
        changes = list(self._changes())
        apply_all(
            [change for change in changes if change.flag in _update_flags.to_set()]
        )

    @property
    def _flags(self):

        if self._value._old_value is undefined:
            return {"create"}

        changes = self._value._get_changes()
        return {change.flag for change in changes}
