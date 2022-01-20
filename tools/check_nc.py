#!/usr/bin/env python

# Performs various checks
from netCDF4 import Dataset
import os, sys

this_folder =  os.path.dirname(__file__)
sys.path.append(os.path.join(this_folder, ".."))

from lib.common import is_uniform, nc2df, date2int
from lib.log import *
import numpy as np
import pandas as pd

pd.set_option("display.max_rows", None, "display.max_columns", None)

def file2df(filename) :
    nc = Dataset(filename, mode='r')
    df = nc2df(nc)
    nc.close()
    return df

def check_file(nc_file) :
    info("processing file : %s" % nc_file)

    nc = Dataset(nc_file, mode='r')
    df = nc2df(nc)

    print(df.head())

    timeint = date2int(nc, df.index.values)

    info("Time range : %s - %s", min(df.index), max(df.index))
    info("Nb samples : %d", len(df.index))
    info("Uniform time ? : %s", is_uniform(timeint))

    nc.close()


if __name__ == '__main__':
    # for file in sys.argv[1:] :
    #    check_file(nc_file=file)

    f1, f2 = sys.argv[1:]
    df1 = file2df(f1)
    df2 = file2df(f2)

    df1 = df1.replace(-999.0, np.nan)
    df2 = df2.replace(-999.0, np.nan)

    diff = df1.compare(df2)

    print(diff)

