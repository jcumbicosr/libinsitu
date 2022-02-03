#!/usr/bin/env python

import os
import sys

# Performs various checks
from netCDF4 import Dataset

this_folder =  os.path.dirname(__file__)
sys.path.append(os.path.join(this_folder, ".."))

from lib.common import nc2df, GHI_VAR, DIF_VAR, DIR_VAR, PRESSURE_VAR, \
    HUMIDITY_VAR, TEMP_VAR
from lib.log import *
import numpy as np

NAN_VALUES = {
    GHI_VAR : -999.0,
    DIF_VAR : -999.0,
    DIR_VAR : -999.0,
    TEMP_VAR : 173.25,
    HUMIDITY_VAR : -0.999,
    PRESSURE_VAR: -99900.0
}

def file2df(filename) :
    nc = Dataset(filename, mode='r')
    df = nc2df(nc)
    nc.close()
    return df


def diff(df1, df2) :

    identical = True

    if len(df1.index) != len(df2.index) or not np.all(df1.index == df2.index) :
        identical = False
        warning("Timing differ : [%s|%s|%d] <-> [%s|%s|%d]",
                df1.index.min(), df1.index.max(), len(df1.index),
                df2.index.min(), df2.index.max(), len(df2.index))

    join = df1.join(df2, lsuffix="1", rsuffix="2", how="inner")

    for col in df1.columns :
        with LogContext(file=col) :

            data1 = join[col + "1"]
            data2 = join[col + "2"]

            # Check missing values
            for this, other, this_name, other_name in [(data1, data2, "data1", "data2"), (data2, data1, "data2", "data1")] :

                missing_idx = this.isna() & ~other.isna()
                missing_nb = sum(missing_idx)
                if missing_nb > 0:
                    missing_vals = other[missing_idx]
                    min_missing = min(missing_vals)
                    max_missing = max(missing_vals)

                    identical = False

                    missing_dates = join.index[missing_idx]

                    warning("%d NA values in %s only. Data values in %s : [%f:%f] from %s to %s",
                            missing_nb,
                            this_name,
                            other_name,
                            min_missing,
                            max_missing,
                            np.min(missing_dates),
                            np.max(missing_dates))


            # Check different values
            rmse = np.sqrt(np.mean((data1 - data2) ** 2))
            if rmse > 0 :
                identical = False
                warning("rmse:%f", rmse)

                nonna = ~data1.isna() & ~data2.isna()
                non_equal = nonna & ~np.isclose(data1, data2)
                diff_nb = sum(non_equal)

                if diff_nb > 0 :
                    identical = False

                    dates = join.index[non_equal]

                    warning("Different values in data1 and data2 : %d. From %s to %s",
                            diff_nb,
                            np.min(dates),
                            np.max(dates))

    if identical :
        info("The two datasets are identical")


if __name__ == '__main__':

    f1, f2 = sys.argv[1:]
    df1 = file2df(f1)
    df2 = file2df(f2)

    # Replace nan values for df2
    for col, na_val in NAN_VALUES.items():
        vals = df2[col]
        idx = np.isclose(vals, na_val)
        df2[col][idx] = np.nan

    station_id = df1.attrs["StationInfo_Abbreviation"]
    network = df1.attrs["source"]

    with LogContext(network=network, station_id=station_id, file="%s:%s" % (f1, f2)):
        diff(df1, df2)

