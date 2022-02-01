#!/usr/bin/env python

# Performs various checks
from netCDF4 import Dataset
import os, sys


this_folder =  os.path.dirname(__file__)
sys.path.append(os.path.join(this_folder, ".."))

from lib.common import is_uniform, nc2df, date2int, TIME_VAR, int2date
from lib.log import *
import numpy as np

NAN_VALUES = [-999.0, -9.99, -99.9, -0.999, 173.25]

def file2df(filename) :
    nc = Dataset(filename, mode='r')
    df = nc2df(nc)
    nc.close()
    return df


def diff(df1, df2) :

    identical = True

    for col in df1.columns :
        with LogContext(file=col) :

            data1 = df1[col]
            data2 = df2[col]

            # Check missing values
            for this, other, this_name, other_name in [(data1, data2, "data1", "data2"), (data2, data1, "data2", "data1")] :

                missing_idx = this.isna() & ~other.isna()
                missing_nb = sum(missing_idx)
                if missing_nb > 0:
                    missing_vals = other[missing_idx]
                    min_missing = min(missing_vals)
                    max_missing = max(missing_vals)

                    identical = False
                    warning("%d NA values in %s only. Data values in %s : [%f:%f]",
                            missing_nb,
                            this_name,
                            other_name,
                            min_missing,
                            max_missing)


            # Check different values
            rmse = np.sqrt(np.mean((data1 - data2) ** 2))
            if rmse > 0 :
                identical = False
                warning("rmse:%f", rmse)

            nonna = ~data1.isna() & ~data2.isna()
            diff_nb = sum(data1[nonna] != data2[nonna])

            if diff_nb > 0 :
                identical = False
                warning("Different values in data1 and data2 : %d", diff_nb)

    if identical :
        info("The two datasets are identical")


if __name__ == '__main__':

    f1, f2 = sys.argv[1:]
    df1 = file2df(f1)
    df2 = file2df(f2)

    for nan_value in NAN_VALUES :
        df1 = df1.replace(nan_value, np.nan)
        df2 = df2.replace(nan_value, np.nan)

    station_id = df1.attrs["StationInfo_Abbreviation"]
    network = df1.attrs["source"]

    with LogContext(network=network, station_id=station_id):
        diff(df1, df2)

