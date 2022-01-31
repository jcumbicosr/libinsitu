#!/usr/bin/env python

# Performs various checks
from netCDF4 import Dataset
import os, sys

this_folder =  os.path.dirname(__file__)
sys.path.append(os.path.join(this_folder, ".."))

from lib.common import is_uniform, nc2df, date2int, TIME_VAR, int2date
from lib.log import *
import numpy as np
import pandas as pd

pd.set_option("display.max_rows", None, "display.max_columns", None)

def file2df(filename) :
    nc = Dataset(filename, mode='r')
    df = nc2df(nc)
    nc.close()
    return df


def diff(df1, df2) :

    for col in df1.columns :

        with LogContext(network=col) :

            data1 = df1[col]
            data2 = df2[col]

            # Check missing values
            missing1 = sum(data1.isna() & ~data2.isna())
            missing2 = sum(data2.isna() & ~data1.isna())
            if missing1 > 0 :
                warning("NA values in data2 (and not in data1) : %d", missing1)
            if missing2 > 0:
                warning("NA values in data1 (and not in data2) : %d", missing2)

            # Check different values
            rmse = np.sqrt(np.mean((data1 - data2) ** 2))
            info("mrse:%f", rmse)

            nonna = ~data1.isna() & ~data2.isna()
            diff_nb = sum(data1[nonna] != data2[nonna])

            if diff_nb > 0 :
                warning("Different values in data1 and data2 : %d", diff_nb)


if __name__ == '__main__':

    f1, f2 = sys.argv[1:]
    df1 = file2df(f1)
    df2 = file2df(f2)

    df1 = df1.replace(-999.0, np.nan)
    df2 = df2.replace(-999.0, np.nan)

    diff(df1, df2)

