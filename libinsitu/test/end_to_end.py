from unittest.mock import patch

import pandas as pd
import pytest
import sys
from os import path, chdir
from tempfile import mkdtemp, mktemp
from pandas import read_csv
from pandas._testing import assert_frame_equal
import filecmp
import numpy as np

from libinsitu import dataframe_to_netcdf, netcdf_to_dataframe, ELEVATION_VAR, LATITUDE_VAR, LONGITUDE_VAR, \
    STATION_NAME_VAR
from libinsitu.cli import transform, cat, qc


CURR_DIR = path.dirname(__file__)
print("Current folder : %s" % CURR_DIR)

BASE_DATE = "2021-01-01"

# Global var set by setup
outfile = None
outcsv = None
inputdir = None
expected_dir = None
tmp_dir = None


#region -- Util functions

def init_dirs(network) :

    global outfile, outcsv, inputdir, expected_dir, tmp_dir
    tmp_dir = mkdtemp()
    outfile = path.join(tmp_dir, "out.nc")
    outcsv = path.join(tmp_dir, "out.csv")
    inputdir = path.join(CURR_DIR, "data", "in", network)
    expected_dir = path.join(CURR_DIR, "data", "expected")

    # Change current folder
    project_dir = path.join(CURR_DIR, "..", "..")
    chdir(project_dir)

def run_main(main_f, args) :
    with patch("sys.argv", ["command"] + args):
        main_f()

def input_to_nc(network, station) :
    run_main(transform.main, ["-n",  network, "-s", station, outfile, inputdir])

def generic_test(network, station, filter=None) :

    init_dirs(network)

    # Transform input to NetCDF
    input_to_nc(network, station)

    # Cat as CSV
    args = ["-s", "-t", "csv", "-o", outcsv, outfile]
    if filter :
        args += ["-f", filter]
    run_main(cat.main, args)

    # Read and compare CSV files
    expected_csv = path.join(expected_dir, "%s.csv" % network)
    expected_df = read_csv(expected_csv, parse_dates=["time"])
    actual_df = read_csv(outcsv, parse_dates=["time"])

    assert_frame_equal(expected_df, actual_df)


def mk_timeseries(rows) :
    """Create pandas dataset from dict of time_str => {col:val, col2:val2} """
    data = {np.datetime64(BASE_DATE + " " + k) : v for k, v in rows.items()}
    return pd.DataFrame.from_dict(data, orient="index")

#endregion


#region -- Actual tests

def test_ABOM() :
    generic_test("ABOM", "ADE")

def test_qc_graph() :
    init_dirs("BSRN")

    # Transform input to NetCDF
    input_to_nc("BSRN", "ILO")

    out_png = path.join(tmp_dir, "out.png")

    # Generate QC graph
    run_main(qc.main, ["-o", out_png, outfile])

    expected_png = path.join(expected_dir, "BSRN-ILO-qc.png")
    assert filecmp.cmp(out_png, expected_png)

def test_BSRN() :
    generic_test("BSRN", "ILO", filter="1994-06-01T06")

def test_encoding_decoding_round_trip() :

    ncfilename = mktemp()

    df = mk_timeseries({
        "00:01" : dict(GHI=1400.0, BNI=1400.0, DHI=1300.0),
        "00:02": dict(GHI=1350.0, BNI=1000.0, DHI=np.nan),
    })

    latitude  = 42.0
    longitude = 7.0
    elevation = 100
    station_id = "station_1"
    network_id = "my_network"

    # Transform to NetCDF
    dataframe_to_netcdf(
        df, ncfilename,
        station_name=station_id, network_name=network_id,
        latitude=latitude, longitude=longitude, elevation=elevation,
        process_qc=False)

    # Read it back
    out_df = netcdf_to_dataframe(
        ncfilename,
        skip_na=True)

    # Check the same data is there
    assert_frame_equal(df, out_df, check_like=True, check_dtype=False)

    # Check metadata is correct :
    assert float(out_df.attrs[ELEVATION_VAR]) == elevation
    assert float(out_df.attrs[LATITUDE_VAR]) == latitude
    assert float(out_df.attrs[LONGITUDE_VAR]) == longitude
    assert out_df.attrs[STATION_NAME_VAR] == station_id
    assert out_df.attrs["time_coverage_start"] == '2021-01-01T00:00:00'
    assert out_df.attrs["time_coverage_end"] == '2021-01-01T00:02:00'


#endregion


if __name__ == '__main__':
    pytest.main(sys.argv)


