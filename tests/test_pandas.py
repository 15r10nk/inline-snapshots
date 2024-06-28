import sys

import pytest

if sys.version_info >= (3, 9):
    from pandas import DataFrame
    from pandas import Index
    from pandas import Series

    from inline_snapshot import snapshot
    from inline_snapshot._pandas import assert_frame_equal
    from inline_snapshot._pandas import assert_index_equal
    from inline_snapshot._pandas import assert_series_equal


@pytest.mark.skipif(sys.version_info < (3, 9), reason="no pandas for 3.9")
def test_df():
    df = DataFrame({"col0": [1, 2], "col1": [1, 5j], "col3": ["a", "b"]})

    # the second argument can be a snapshot
    assert_frame_equal(
        df,
        snapshot(
            DataFrame(
                [
                    {"col0": 1, "col1": (1 + 0j), "col3": "a"},
                    {"col0": 2, "col1": 5j, "col3": "b"},
                ]
            )
        ),
    )

    # and can also be used without a snapshot
    assert_frame_equal(df, df)

    # for Index
    index = Index(range(5))
    assert_index_equal(index, snapshot(Index([0, 1, 2, 3, 4])))

    # for Series
    index = Series({1: 8, 5: 4})
    assert_series_equal(index, snapshot(Series({1: 8, 5: 4})))
