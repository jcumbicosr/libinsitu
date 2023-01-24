from unittest.mock import patch

import pytest
import sys
from os import path, chdir
from tempfile import mkdtemp
from pandas import read_csv
from pandas._testing import assert_frame_equal

from libinsitu.cli import transform, cat


CURR_DIR = path.dirname(__file__)

def generic_test(network, station) :

    tmp_dir = mkdtemp()
    outfile = path.join(tmp_dir, "out.nc")
    outcsv = path.join(tmp_dir, "out.csv")
    inputdir = path.join(CURR_DIR, "data", "in", network)
    expected_csv = path.join(CURR_DIR, "data", "expected", network + ".csv")

    # Change current folder
    project_dir = path.join(CURR_DIR, "..", "..")
    chdir(project_dir)

    # Transform input to NetCDF
    with patch("sys.argv", ["transform.py", "-n",  network, "-s", station, outfile, inputdir]):
        transform.main()

    # Cat as CSV
    with patch("sys.argv", ["cat.py", "-s", "-t", "csv", "-o", outcsv, outfile]):
        cat.main()

    # Read and compare CSV files
    expected_df = read_csv(expected_csv, parse_dates=["time"])
    actual_df = read_csv(outcsv, parse_dates=["time"])

    assert_frame_equal(expected_df, actual_df)

def test_ABOM() :
    generic_test("ABOM", "ADE")



if __name__ == '__main__':
    pytest.main(sys.argv)


