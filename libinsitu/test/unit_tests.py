from datetime import datetime, timedelta

import numpy as np

from libinsitu import match_pattern, to_range
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

if __name__ == '__main__':
    pytest.main(sys.argv)
