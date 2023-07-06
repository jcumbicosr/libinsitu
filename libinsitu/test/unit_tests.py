from datetime import datetime, timedelta
from unittest.mock import patch

import numpy as np
from netCDF4 import Dataset
from numpy.ma.testutils import assert_array_equal
from numpy.testing import assert_array_equal

from libinsitu import match_pattern, to_range, flagData, QCFlag, write_flags, dataframe_to_netcdf, compute_qc_level
from libinsitu.common import is_uniform, parse_value, parseTimezone
import pytest
import sys

from libinsitu.test.utils import mk_timeseries, tmp_filename, patch_flags


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
    flag = QCFlag(
        bit=1,
        name ="f1",
        condition="GHI > DIF",
        domain="GHI > 0",
        components=["GHI", "DHI"])

    meas_df = mk_timeseries(
        GHI = [0, 10, 10, 10, np.nan],
        DHI = [0, 5, 15, np.nan, 10],
        BNI = 0)

    sp_df = mk_timeseries(
        TOA = [1, 1, 1, 1, 1],
        TOANI = 1,
        GAMMA_S0 = 0,
        THETA_Z = 0)

    with patch_flags([flag]) :

        flag_vals = flagData(meas_df, sp_df)

        assert_array_equal(
            flag_vals.f1,
            [-1, 0, 1, -1, -1])

def test_write_flags():

    # Static flags as if they came from CSV file
    flags = [
        QCFlag(bit=1, name="f1", components=[]),
        QCFlag(bit=2, name="f2", components=[])]

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

    with patch_flags(flags):


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


def test_qc_level() :

    flag_defs = [
        # 1C flags
        QCFlag(name="qa", components=["a"], level=10),
        QCFlag(name="qa2", components=["a"], level=10),
        QCFlag(name="qb", components=["b"], level=10),
        QCFlag(name="qc", components=["c"], level=10),

        QCFlag(name="xx", components=["a"], level=None), # Should be ignored

        # 2C flags
        QCFlag(name="qab", components=["a", "b"], level=21, group_level=24),
        QCFlag(name="qac", components=["a", "c"], level=22, group_level=24),

        # 3c flags
        QCFlag(name="qabc", components=["a", "b", "c"], level=30),
    ]

    def compute_values(a=1, b=1, c=1, sza=40, **flags):
        """Generate timeseries with single sample and correspoding QC flags and run computation of level"""
        meas_df = mk_timeseries(a=[a], b=[b], c=[c])
        sp_df = mk_timeseries(SZA=[sza])

        # By default all tests are passing
        flag_vals = {flag.name:[0] for flag in flag_defs}
        for key, val in flags.items():
            if not key in flag_vals :
                raise Exception("Bad flag %s" % key)
            flag_vals[key] = [val]

        flags_df = mk_timeseries(**flag_vals)

        with patch_flags(flag_defs) :
            res = compute_qc_level(flags_df, meas_df, sp_df)

        # Return unique row as dict
        return res.to_dict(orient="records")[0]

    # By default (all test passing
    assert compute_values() == dict(a=30, b=30, c=30)

    # Night ? ==> all -5
    assert compute_values(sza=95) == dict(a=-5, b=-5, c=-5)

    # Missing value ? -1 for components,
    # Would imply -1 for any 2C / 3C test including it.
    # others are stuck as out of domain for 2C tests(15)
    assert compute_values(
        a=np.nan,
        qa=-1,qa2=-1, qab=-1, qac=-1, qabc=-1) == dict(a=-1, b=15, c=15)

    # One of 2C test failing (ab). ac is ok and raise a and b to level 22 (but not higher)
    assert compute_values(qab=1) == dict(a=22, b=10, c=22)

    # One of 2C test failing (ac). ab is ok and raise a and c to level 21 (but not higher)
    assert compute_values(qac=1) == dict(a=21, b=21, c=10)

    # 3C test failing => all 2C test are ok and should raised them all to the group level 24
    assert compute_values(qabc=1) == dict(a=24, b=24, c=24)

    # 3C test out of domain => all 2C test are ok and should raised them all to the group level 25
    assert compute_values(qabc=-1) == dict(a=25, b=25, c=25)


if __name__ == '__main__':
    pytest.main(sys.argv)
