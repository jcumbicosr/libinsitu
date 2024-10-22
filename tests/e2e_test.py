from unittest.mock import patch

import pandas as pd
import pytest
import sys
from os import path, chdir
from tempfile import mkdtemp, mktemp

from numpy.ma.testutils import assert_array_equal
from pandas import read_csv
from pandas._testing import assert_frame_equal, assert_series_equal
import filecmp
import numpy as np

from libinsitu import dataframe_to_netcdf, netcdf_to_dataframe, ELEVATION_VAR, LATITUDE_VAR, LONGITUDE_VAR, \
    STATION_NAME_VAR, write_flags
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

# Dummy values used in tests
latitude = 42.0
longitude = 7.0
elevation = 100
station_id = "station_1"
network_id = "my_network"


#region -- Util functions

def init_dirs(network) :

    global outfile, outcsv, inputdir, expected_dir, tmp_dir
    tmp_dir = mkdtemp()
    outfile = path.join(tmp_dir, "out.nc")
    outcsv = path.join(tmp_dir, "out.csv")
    inputdir = path.join(CURR_DIR, "data", network)
    expected_dir = inputdir

    print("Temp dir : ", tmp_dir)

    # Change current folder
    project_dir = path.join(CURR_DIR, "..", "..")
    chdir(project_dir)

def run_main(main_f, args, options=None) :

    if options is not None:
        for opt, val in options.items():
            args += [opt] if val is None else [opt, val]

    with patch("sys.argv", ["command"] + args):
        print(f"running {str(main_f)} with args {' '.join(args)}]")
        main_f()

def input_to_nc(network, station, station_folder=False, extra_options=None):

    if extra_options is None:
        extra_options = dict()

    # Either pass network dir or station dir
    dir = path.join(inputdir, station) if station_folder else inputdir

    extra_options["--network"] =  network
    extra_options["--station-id"] = station

    args = [outfile, dir]

    run_main(transform.main, args, options=extra_options)

def round_trip_test(network, station, filter=None, extra_transform_options=None, station_folder=False) :

    init_dirs(network)

    # Transform input to NetCDF
    input_to_nc(network, station, extra_options=extra_transform_options, station_folder=station_folder)

    check_output(filter=filter)

def check_output(filter=None) :
    # Cat as CSV
    args = [outfile]
    options = {
        "-s": None,
        "-t": "csv",
        "-o": outcsv,
    }

    if filter :
        options["-f"] = filter

    run_main(cat.main, args, options)

    # Read and compare CSV files
    expected_csv = path.join(expected_dir, "expected.csv")
    expected_df = read_csv(expected_csv, parse_dates=["time"])
    actual_df = read_csv(outcsv, parse_dates=["time"])

    assert_frame_equal(expected_df, actual_df)

def generic_round_trip_test(network, station, filter=None):
    """Round trip test using generic CSV with extra options """

    input_dir = path.join(CURR_DIR, "data", network)

    extra_options ={
        "--no-qc": None,
        "--station-metadata": path.join(input_dir, "stations.csv"),
        "--mapping": path.join(input_dir, "mapping.json")
    }

    schema_file = path.join(input_dir, "schema.cdl")
    if path.exists(schema_file):
        extra_options["--cdl"] = schema_file


    round_trip_test(network, station, filter, extra_transform_options=extra_options, station_folder=True)

def time_str_to_dt64(time_str) :
    return np.datetime64(BASE_DATE + " " + time_str, 'ns')

def mk_timeseries(rows) :
    """Create pandas dataset from dict of time_str => {col:val, col2:val2} """
    data = {time_str_to_dt64(time) : values for time, values in rows.items()}
    return pd.DataFrame.from_dict(data, orient="index")

#endregion


#region -- Actual tests

def test_ABOM() :
    round_trip_test("ABOM", "ADE")

def test_BSRN() :
    round_trip_test("BSRN", "ILO", filter="1994-06-01T06")

def test_excel_encoding() :
    generic_round_trip_test("encode_excel", "ABJ")

def test_csv_encoding() :
    generic_round_trip_test("encode_csv", "ABJ")

def test_lat_lon_encoding() :
    generic_round_trip_test("encode_lat_lon", "ABJ")

def test_minimalistic() :

    init_dirs("minimalistic")

    extra_options = {
        "--no-qc": None,
        "--station-metadata": path.join(inputdir, "stations.csv"),
        "--station-id" : "AAA",
        "--mapping": path.join(inputdir, "mapping.yaml"),
        "--network" : "NetworkName",
        "--cdl" : path.join(inputdir, "schema.cdl")
    }


    run_main(
        transform.main,
        [outfile, path.join(inputdir, "input.csv")],
        extra_options)

    check_output()


def test_qc_graph() :
    init_dirs("BSRN")

    # Transform input to NetCDF
    input_to_nc("BSRN", "ILO")

    out_png = path.join(tmp_dir, "out.png")

    # Generate QC graph
    run_main(qc.main, ["-o", out_png, outfile])

    expected_png = path.join(expected_dir, "BSRN-ILO-qc.png")
    assert filecmp.cmp(out_png, expected_png)


def test_encoding_decoding_round_trip() :

    ncfilename = mktemp()

    # Sub minutes period
    df = mk_timeseries({
        "00:01:00" : dict(GHI=1400.0, BNI=1400.0, DHI=1300.0),
        "00:01:10": dict(GHI=1350.0, BNI=1000.0, DHI=np.nan),
    })

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
    assert out_df.attrs["time_coverage_end"] == '2021-01-01T00:01:10'
    assert out_df.attrs["time_coverage_resolution"] == 10


def test_qc_filters():

    ncfilename = mktemp()

    # Data
    df = mk_timeseries({
        "00:00": dict(GHI=1400.0, BNI=1400.0, DHI=1300.0),
        "00:01": dict(GHI=1350.0, BNI=1000.0, DHI=np.nan),
        "00:02": dict(GHI=1350.0, BNI=1000.0, DHI=np.nan),
    })

    # QC flags
    flags = mk_timeseries({
        "00:00": dict(GHI_PPL_UL_TOANI_SZA=0, GHI_ERL_UL_TOANI_SZA=-1),
        "00:01": dict(GHI_PPL_UL_TOANI_SZA=1, GHI_ERL_UL_TOANI_SZA=0),
        "00:02": dict(GHI_PPL_UL_TOANI_SZA=0, GHI_ERL_UL_TOANI_SZA=1),
    })

    ncfile = dataframe_to_netcdf(
        df, ncfilename,
        station_name=station_id, network_name=network_id,
        latitude=latitude, longitude=longitude, elevation=elevation,
        close=False, process_qc=False)

    # Manually write QC flags
    write_flags(ncfile, flags)

    # Reload NetCDF file as Dataframe
    out_df = netcdf_to_dataframe(
        ncfile,
        skip_na=True,
        expand_qc=True)

    # Check flags are the same
    assert_series_equal(out_df["QC.GHI_PPL_UL_TOANI_SZA"], flags.GHI_PPL_UL_TOANI_SZA, check_names=False)
    assert_series_equal(out_df["QC.GHI_ERL_UL_TOANI_SZA"], flags.GHI_ERL_UL_TOANI_SZA, check_names=False)

    def check_filtering(skip_qc, expected_times) :
        out_df = netcdf_to_dataframe(
            ncfile,
            skip_na=True,
            skip_qc=skip_qc)

        times = np.array(list(time_str_to_dt64(time) for time in expected_times))

        assert_array_equal(out_df.index.values, times)

    # Not filtering
    check_filtering(False, ["00:00", "00:01", "00:02"])

    # Filter any flag
    check_filtering(True, ["00:00"])

    # Filter only one flag
    check_filtering(["GHI_PPL_UL_TOANI_SZA"], ["00:00", "00:02"])

    # Filter all but one flag
    check_filtering(["!GHI_PPL_UL_TOANI_SZA"], ["00:00", "00:01"])

    # Should fail for non existing flags
    with pytest.raises(Exception) as e:
        check_filtering(["foo"], [])
    assert e.type == KeyError


if __name__ == '__main__':
    pytest.main(sys.argv)


