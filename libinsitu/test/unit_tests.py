from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from numpy.testing import assert_array_equal

from pandas import DataFrame

from libinsitu import match_pattern, to_range, flagData
from libinsitu.common import is_uniform, parse_value, parseTimezone
import pytest
import sys

def test_is_uniform() :

    assert is_uniform(np.array([])) is True

    assert is_uniform(np.array([1, 2, 3])) is True

    assert is_uniform(np.array([1, 2])) is True

    assert is_uniform(np.array([1])) is True

    assert is_uniform(np.array([1, 2, 4])) is False

    # With python lists
    assert is_uniform([1, 2, 3]) is True
    assert is_uniform([1, 2, 4]) is False

def test_parse_value() :

    assert parse_value("12.0") == 12.0
    assert parse_value("12.1") == 12.1
    assert parse_value("12") == 12
    assert parse_value("12A") == "12A"
    assert parse_value('"12A"') == "12A"
    assert parse_value('') is None

def test_parse_timezone() :

    assert parseTimezone("UTC-03:30") == timedelta(minutes=-(60*3+30))
    assert parseTimezone("UTC+02:00") == timedelta(minutes=2*60)


def test_match() :
    assert match_pattern("{FOO}_{BAR}", "A_B", dict(FOO="A")) == dict(BAR="B")
    assert match_pattern("{FOO}_{BAR}", "A_B", dict(FOO="C")) is False
    assert match_pattern("{YYYY}-{M}", "2000-01") == dict(year=2000, month=1)
    assert match_pattern("{YY}-{MM}", "89-02") == dict(year=1989, month=2)
    assert match_pattern("{YY}-{MM}", "2000-01") is False

def test_torange() :
    assert to_range(2000) == (datetime(2000, 1, 1), datetime(2001, 1, 1))
    assert to_range(2000, 1) == (datetime(2000, 1, 1), datetime(2000, 2, 1))

def test_flag_data():

    FLAGS = dict(f1=SimpleNamespace(
        bit=1, name ="f1", condition="GHI > DIF", domain="GHI > 0", components=["GHI", "DNI"]
    ))

    meas_df = mk_timeseries(
        GHI = [0, 10, 10, 10, np.nan],
        DHI = [0, 5, 15, np.nan, 10],
        BNI = 0)

    sp_df = mk_timeseries(
        TOA = [1, 1, 1, 1, 1],
        TOANI = 1,
        GAMMA_S0 = 0,
        THETA_Z = 0)

    with patch("libinsitu.qc.qc_utils.get_flags", return_value=FLAGS) :
        flags = flagData(meas_df, sp_df)

        assert_array_equal(
            flags.f1,
            [-1, 0, 1, 1, -1])

def mk_timeseries(**dic):
    """Creates a time series Dataframe from a dict of values """
    nb = len(list(dic.values())[0])

    # Expand single value
    for name, vals in dic.items() :
        if not isinstance(vals, list) :
            dic[name] = [vals] * nb

    dic["times"] = [datetime(2000, 1, 1, h, 0, 0) for h in range(0, nb)]
    df = DataFrame.from_dict(dic)
    return df.set_index("times")

if __name__ == '__main__':
    pytest.main(sys.argv)
