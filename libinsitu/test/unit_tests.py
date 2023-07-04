from datetime import datetime, timedelta
from unittest.mock import patch

import numpy as np
from netCDF4 import Dataset
from numpy.ma.testutils import assert_array_equal
from numpy.testing import assert_array_equal

from libinsitu import match_pattern, to_range, flagData, QCFlag, write_flags, dataframe_to_netcdf
from libinsitu.common import is_uniform, parse_value, parseTimezone
import pytest
import sys

from libinsitu.test.utils import mk_timeseries, tmp_filename


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

    # Static flags as if they came from CSV file
    flags = dict(f1=QCFlag(
        bit=1, name ="f1", condition="GHI > DIF", domain="GHI > 0", components=["GHI", "DHI"]))

    meas_df = mk_timeseries(
        GHI = [0, 10, 10, 10, np.nan],
        DHI = [0, 5, 15, np.nan, 10],
        BNI = 0)

    sp_df = mk_timeseries(
        TOA = [1, 1, 1, 1, 1],
        TOANI = 1,
        GAMMA_S0 = 0,
        THETA_Z = 0)

    with patch("libinsitu.qc.qc_utils.get_flags", return_value=flags) :

        flags = flagData(meas_df, sp_df)

        assert_array_equal(
            flags.f1,
            [-1, 0, 1, -1, -1])

def test_write_flags():

    # Static flags as if they came from CSV file
    flags = dict(
        f1=QCFlag(bit=1, name="f1", components=[]),
        f2=QCFlag(bit=2, name="f2", components=[]))

    data_df = mk_timeseries(DHI=[1, 2, 3])

    flags_df = mk_timeseries(
        f1=[0, 1, -1],
        f2=[1, 0, -1])

    tmp_file = tmp_filename()

    print("temp file", tmp_file)

    nc = dataframe_to_netcdf(
        data_df,
        station_name="FOO",
        network_name="BAR",
        out_filename=tmp_file,
        process_qc=False,
        close=False)

    with patch("libinsitu.qc.qc_utils.get_flags", return_value=flags):


        write_flags(nc, flags_df)

        qc_var = nc.variables["QC"]
        qc_run_var = nc.variables["QC_run"]

        print(qc_var.flag_masks)

        # Check meta data are correctly filled
        assert qc_var.flag_meanings == "f1 f2"
        assert_array_equal(qc_var.flag_masks, [1, 2])

        assert qc_run_var.flag_meanings == "f1 f2"
        assert_array_equal(qc_run_var.flag_masks, [1, 2])

        # Check masks are correctly computed
        assert_array_equal(qc_var[:], [2, 1, 0]) # error flags
        assert_array_equal(qc_run_var[:], [3, 3, 0])  # Qc computed flags





if __name__ == '__main__':
    pytest.main(sys.argv)
