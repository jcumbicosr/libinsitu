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

MIN_STEP=0
MAX_STEP=1000

def check_time(nc_file) :
    nc = Dataset(nc_file, mode='r')
    time_int = nc.variables[TIME_VAR]

    from_date = int2date(nc, np.min(time_int))
    to_date = int2date(nc, np.max(time_int))

    steps = time_int[1:] - time_int[0:len(time_int)-1]
    unique, counts = np.unique(steps, return_counts=True)

    filtered_unique = unique[(unique > MIN_STEP) & (unique < MAX_STEP)]
    filtered_counts = counts[(unique > MIN_STEP) & (unique < MAX_STEP)]

    indices = np.argsort(-filtered_counts)[:3]
    dic = dict((filtered_unique[idx], filtered_counts[idx]) for idx in indices)

    print("%s: min=%s max=%s periods=%s" % (nc.StationInfo_Abbreviation, from_date, to_date, dic))



if __name__ == '__main__':
    for file in sys.argv[1:] :
        check_time(nc_file=file)

    sys.exit()
    f1, f2 = sys.argv[1:]
    df1 = file2df(f1)
    df2 = file2df(f2)

    df1 = df1.replace(-999.0, np.nan)
    df2 = df2.replace(-999.0, np.nan)

    diff = df1.compare(df2)

    print(diff)