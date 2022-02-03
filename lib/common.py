import logging
from csv import DictReader
from typing import List

import numpy as np
from cftime import num2date
from numpy import timedelta64, datetime64
from numpy.typing import NDArray
from pandas import DataFrame
import os

TIME_DIM = 'time'
TIME_VAR = "Time"
GHI_VAR = "GHI"
DIF_VAR = "DIF"
DIR_VAR = "DIR"
TEMP_VAR = "T2"
HUMIDITY_VAR = "RH"
PRESSURE_VAR = "P"

LATITUDE_VAR = "latitude"
LONGITUDE_VAR = "longitude"
ELEVATION_VAR = "elevation"
STATION_NAME_VAR= "station_name"

DATA_VARS = [GHI_VAR, DIF_VAR, DIR_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR]

STATION_INFO_PATTERN = "res/station-info/%s.csv"

DATE_FORMAT = '%Y-%m-%d'
SECOND = timedelta64(1, 's')

def getStationsInfo(network) :
    """REad station info from CSV"""
    csv_file = STATION_INFO_PATTERN % network
    res = dict()
    with open(csv_file) as f:
        rows = DictReader(f)
        for row in rows:
            res[row["ID"]] = {key: parse_value(val) for key, val in row.items()}
    return res

def older_than(file1, file2) :
    """Return True if file1 is older than file2"""
    return os.stat(file1).st_mtime < os.stat(file2).st_mtime

def touch(filename):
    """ creates or update the time of a file """
    if os.path.exists(filename):
        os.utime(filename)
    else:
        with open(filename,'a') as f:
            pass

def getStationInfo(network, station_id) :
    stations = getStationsInfo(network)
    if not station_id in stations :
        raise Exception("Station %s not found in Station Info of %s" % (station_id, network))
    return stations[station_id]

def is_uniform(vector) :

    if type(vector) == list :
        vector = np.array(vector)

    if len(vector) <=1 :
        return True
    step = vector[1] - vector[0]
    ref = np.arange(vector[0], vector[-1] + step, step)
    return np.array_equal(ref, vector)

def get_start_time(ncfile) -> datetime64 :
    start_time = num2date(0, ncfile.variables[TIME_VAR].units, ncfile.variables[TIME_VAR].calendar)
    return np.datetime64(start_time)

def datetime64_to_int(ncfile, dates : NDArray[datetime64]) -> NDArray[int] :
    start_time64 = get_start_time(ncfile)
    return ((dates - start_time64) / SECOND).astype(int)

def int_to_datetime64(ncfile, times_int: NDArray[int]) ->  NDArray[datetime64]:
    start_time64 = get_start_time(ncfile)
    return start_time64 + SECOND * times_int


def parse_value(val) :
    """Parse string value, trying first int, then float. return str value if none are correct"""
    if not isinstance(val, str) :
        return val
    elif val is None or val == "":
        return None
    try :
        return int(val)
    except:
        try:
            return float(val)
        except:
            if val.startswith('"') :
                val = val.strip('"')
            return val

def nc2df(ncfile) :
    """Read netCDF file into Dataframe, indexed by time"""
    times = int_to_datetime64(ncfile, ncfile.variables[TIME_VAR])

    df = DataFrame(
        dict((var, ncfile.variables[var][:]) for var in DATA_VARS if var in ncfile.variables),
        index=times)

    # Set global attributes in DataFrame
    attrs = dict((key, getattr(ncfile, key)) for key in ncfile.ncattrs())
    df.attrs.update(attrs)

    return df



