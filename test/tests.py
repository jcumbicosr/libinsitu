import numpy as np

from lib.common import is_uniform, parse_value
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

if __name__ == '__main__':
    pytest.main(sys.argv)
