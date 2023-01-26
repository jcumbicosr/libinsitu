from unittest.mock import patch

import pytest
import sys
from os import path, chdir
from tempfile import mkdtemp
from pandas import read_csv
from pandas._testing import assert_frame_equal
import filecmp

from libinsitu.cli import transform, cat, qc


CURR_DIR = path.dirname(__file__)

# Global var set by setup
outfile = None
outcsv = None
inputdir = None
expected_dir = None
tmp_dir = None


# -- Util functions

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

# -- Actual tests


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

if __name__ == '__main__':
    pytest.main(sys.argv)


