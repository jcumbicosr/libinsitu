import logging
from csv import DictReader
from datetime import datetime
from typing import List

import numpy as np
from cftime import num2date
from netCDF4 import Dataset
from numpy import timedelta64, datetime64
from numpy.typing import NDArray
from pandas import DataFrame
from pkgutil import get_data
import os

TIME_DIM = 'time'
TIME_VAR = "Time"
GLOBAL_VAR = "GHI"
DIFFUSE_VAR = "DHI"
DIRECT_VAR = "BNI"
TEMP_VAR = "T2"
HUMIDITY_VAR = "RH"
PRESSURE_VAR = "P"

LATITUDE_VAR = "latitude"
LONGITUDE_VAR = "longitude"
ELEVATION_VAR = "elevation"
STATION_NAME_VAR= "station_name"

STATION_NAME_DIM = "ncshort"

DATA_VARS = [GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR]

STATION_INFO_PATTERN = "station-info/%s.csv"
NETWORK_INFO_FILE = "networks.csv"

DATE_FORMAT = '%Y-%m-%d'
SECOND = timedelta64(1, 's')

def parseCSV(res_path, key = "ID") :
    """Generic parser """
    res = dict()
    rows = DictReader(read_res(res_path))
    for row in rows:
        res[row[key]] = {key: parse_value(val) for key, val in row.items()}
    return res

def getStationsInfo(network) :
    """Read station info from CSV"""
    return parseCSV(STATION_INFO_PATTERN % network)

def getNetworksInfo() :
    return parseCSV(NETWORK_INFO_FILE)


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

def getNetworkInfo(network) :
    networks = getNetworksInfo()
    if not network in networks :
        raise Exception("Network %s not found in Network infp of %s" % network)
    return networks[network]

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

def read_res(path, encoding="utf8") :
    """Read package resources and returns a fie like object (splitted lines)
    path should be relative to ./res/
    """
    return get_data(__name__, os.path.join("..", "res", path)).decode(encoding).splitlines()

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

def getTimeResolution(ncfile) :
    """Returns time resolution, in seconds, as saved in meta data"""

    val = ncfile.variables[TIME_VAR].resolution
    val, unit = val.split()
    val = int(val)
    if "min" in unit :
        return val * 60
    elif "sec" in unit:
        return val
    else:
        raise Exception("Unknown unit for time resolution : '%s'" % unit)


def nc2df(ncfile, drop_duplicates=True, start_idx=None, end_idx=None) :
    """Read netCDF file into Dataframe, indexed by time"""
    times = int_to_datetime64(ncfile, ncfile.variables[TIME_VAR][start_idx:end_idx])

    # List of VArs (along time)
    data_vars = []
    for varname, var in ncfile.variables.items() :
        if TIME_DIM in var.dimensions and varname != TIME_VAR :
            data_vars.append(varname)

    df = DataFrame(
        dict((var, ncfile.variables[var][start_idx:end_idx]) for var in data_vars),
        index=times)

    # Set global attributes in DataFrame
    attrs = dict((key, getattr(ncfile, key)) for key in ncfile.ncattrs())
    df.attrs.update(attrs)

    # Drop duplicated : only keep last
    if drop_duplicates :
        df = df[~df.index.duplicated(keep="last")]

    return df

def file2df(filename):
    nc = Dataset(filename, mode='r')
    df = nc2df(nc)
    nc.close()
    return df

def date_str(val) :
    """Format date to the minute """
    if val is None :
        return ""
    if isinstance(val, datetime64) :
        return np.datetime_as_string(val, unit='m')
    elif isinstance(val, datetime) :
        return val.strftime("'%Y-%m-%d %H:%M'")

    raise Exception("Unknown date type : " + type(val))

MIN_STEP=0
MAX_STEP=1000

def get_periods(time_s) :
    """Compute list of periods, by occurrence. Return list of (period, count)"""

    steps = time_s[1:] - time_s[0:len(time_s) - 1]
    unique, counts = np.unique(steps, return_counts=True)

    filtered_unique = unique[(unique > MIN_STEP) & (unique < MAX_STEP)]
    filtered_counts = counts[(unique > MIN_STEP) & (unique < MAX_STEP)]

    indices = np.argsort(-filtered_counts)[:3]
    periods_dic =  dict((filtered_unique[idx], filtered_counts[idx]) for idx in indices)
    return list((int(period), count) for period, count in periods_dic.items())



