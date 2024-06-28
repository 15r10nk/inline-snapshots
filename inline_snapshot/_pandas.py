from functools import wraps
from typing import Optional


def make_assert_equal(data_type, assert_equal, repr_function):

    class Wrapper:
        def __init__(self, df, cmp):
            self.df = df
            self.cmp = cmp

        def __repr__(self):
            return f"{data_type.__name__}({repr(repr_function(self.df))})"

        def __eq__(self, other):
            if not isinstance(other, data_type):
                return NotImplemented
            return self.cmp(self.df, other)

    @wraps(assert_equal)
    def result(df, df_snapshot, *args, **kargs):
        error: Optional[AssertionError] = None

        def cmp(a, b):
            nonlocal error
            try:
                assert_equal(a, b, *args, **kargs)
            except AssertionError as e:
                error = e
                return False
            return True

        if not Wrapper(df, cmp) == df_snapshot:
            assert error is not None
            raise error

    return result


try:
    import pandas
except:
    pass
else:
    from pandas.testing import assert_frame_equal
    from pandas.testing import assert_index_equal
    from pandas.testing import assert_series_equal

    assert_frame_equal = make_assert_equal(
        pandas.DataFrame, assert_frame_equal, lambda df: df.to_dict("records")
    )
    assert_series_equal = make_assert_equal(
        pandas.Series, assert_series_equal, lambda df: df.to_dict()
    )
    assert_index_equal = make_assert_equal(
        pandas.Index, assert_index_equal, lambda df: df.to_list()
    )
