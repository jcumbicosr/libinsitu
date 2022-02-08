#!/usr/bin/env python

# Performs various checks
from netCDF4 import Dataset
import os, sys

this_folder =  os.path.dirname(__file__)
sys.path.append(os.path.join(this_folder, ".."))

from lib.common import nc2df
from lib.log import *
import numpy as np

MIN_STEP=0
MAX_STEP=1000

def file2df(filename):
    nc = Dataset(filename, mode='r')
    df = nc2df(nc)
    nc.close()
    return df

def check_time(filename) :

    df = file2df(filename)
    station_id = df.attrs["StationInfo_Abbreviation"]
    network = df.attrs["source"]
    if " " in network :
        network = network.split(" ")[0]

    with LogContext(station_id=station_id, network=network, file=filename) :

        from_date = min(df.index)
        to_date = max(df.index)
        nb_samples = len(df.index)

        time_s = df.index.values.astype(np.int64) / 1000000000
        steps = time_s[1:] - time_s[0:len(time_s)-1]
        unique, counts = np.unique(steps, return_counts=True)

        filtered_unique = unique[(unique > MIN_STEP) & (unique < MAX_STEP)]
        filtered_counts = counts[(unique > MIN_STEP) & (unique < MAX_STEP)]

        indices = np.argsort(-filtered_counts)[:3]
        periods_dic = dict((filtered_unique[idx], filtered_counts[idx]) for idx in indices)

        # Filter periods present more than 10 times
        periods = {int(k): v for k,  v in periods_dic.items() if v > 10}

        if len(periods) > 1 :
            warning("Found several periods periods=%s", periods_dic)
        else:
            periods = list(periods.keys())[0]
        info("from:%s, to:%s, %d samples, period:%s", from_date, to_date, nb_samples, periods)



if __name__ == '__main__':
    for file in sys.argv[1:] :
        with IgnoreAndLogExceptions() :
            check_time(filename=file)
