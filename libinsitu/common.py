from csv import DictReader
from datetime import datetime
from typing import Union
from urllib.parse import urlsplit, quote_plus

import numpy as np
from netCDF4 import *
from numpy import timedelta64, datetime64
from numpy.ma import is_masked
from numpy.typing import NDArray
from pandas import DataFrame
import pandas as pd
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

WIND_SPEED_VAR = "WS"
WIND_DIRECTION_VAR = "WD"

LATITUDE_VAR = "latitude"
LONGITUDE_VAR = "longitude"
ELEVATION_VAR = "elevation"
STATION_NAME_VAR= "station_name"

STATION_NAME_DIM = "ncshort"

STATION_PREFIX = "Station_"
NETWORK_PREFIX = "Network_"

NA_VALUES=[-999.0, -99.9, -10.0, -9999.0, -99999.0]

CHUNK_SIZE=5000


DATA_VARS = [GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR, WIND_SPEED_VAR, WIND_DIRECTION_VAR]

STATION_INFO_PATTERN = "station-info/%s.csv"
NETWORK_INFO_FILE = "networks.csv"

DATE_FORMAT = '%Y-%m-%d'
TIME_FORMAT_MIN= '%Y-%m-%dT%H:%M'
TIME_FORMAT_SEC= '%Y-%m-%dT%H:%M:%S'
SECOND = timedelta64(1, 's')

CDL_PATH = "base.cdl"

FIRST_DATA_ATT = "FirstData"
LAST_DATA_ATT = "LastData"

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

def get_origin_time(ncfile) -> datetime64 :
    start_time = num2date(0, ncfile.variables[TIME_VAR].units, ncfile.variables[TIME_VAR].calendar)
    return np.datetime64(start_time)

def to_int(vals) :
    """Transform single val or array to int """
    if isinstance(vals, np.ndarray):
        return vals.astype(int)
    else:
        return int(vals)

def datetime64_to_sec(ncfile, dates : NDArray[datetime64]) -> NDArray[int] :
    """Transform datetime64 to number of seconds since origin date """
    origin = get_origin_time(ncfile)
    return to_int((dates - origin) / SECOND)

def str_to_date64(datestr) :
    return np.datetime64(datetime.strptime(datestr, DATE_FORMAT))

def start_date64(ncfile) :
    return str_to_date64(ncfile.Station_DataBegin)

def seconds_to_idx(ncfile, dates : NDArray[int], ) -> NDArray[int] :
    """Transform seconds since origin to time idx, taking into account resolution and start date"""
    resolution_s = getTimeResolution(ncfile)
    start_sec = datetime64_to_sec(ncfile, start_date64(ncfile))
    return to_int((dates - start_sec) / resolution_s)

def sec_to_datetime64(ncfile, times_s: NDArray[int]) ->  NDArray[datetime64]:
    """Transform number of seconds since start time into datetime64 """
    start_time64 = get_origin_time(ncfile)
    return start_time64 + SECOND * times_s

def read_res(path, encoding="utf8") :
    """Read package resources and returns a fie like object (splitted lines)
    path should be relative to ./res/
    """
    return get_data(__name__, os.path.join("res", path)).decode(encoding).splitlines()

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

def openNetCDF(filename, mode='r', user=None, password=None) :
    """ Open either a filename or OpenDAP URL with user /password"""
    if '://' in filename :
        if user :
            filename = with_auth(filename, user, password)
        filename = "[FillMismatch]" + filename
    return Dataset(filename, mode=mode)

def date_to_timeidx(nc, date) :
    """Transform date to NetCDF index along Time dimension"""
    if isinstance(date, datetime) :
        date = datetime64(date)
    time_int = datetime64_to_sec(nc, date)
    return int(time_int / getTimeResolution(nc))


def nc2df(
        ncfile : Union[Dataset, str],
        start_time: Union[datetime, datetime64]=None, end_time:Union[datetime, datetime64]=None,
        drop_duplicates=True,
        skip_na=False,
        vars=None,
        user=None,
        password=None,
        chunked=False,
        chunk_size=CHUNK_SIZE,
        steps=1) :
    """
        Load NETCDF in-situ file (or part of it) into a panda Dataframe, with time as index

        :param ncfile: NetCDF Dataset or filename, or URL
        :param drop_duplicates: If true (default), duplicate rows with same time are droppped
        :param skip_na : If True, drop rows containing only nan values
        :param start_time: Start time (first one by default) : Datetime or datetime64
        :param end_time: End time (last one by default) : Datetile or datetime64
        :param vars: List of columns names to  convert (all by default)
        :param user: Optional login for URL
        :param password: Optional password for URL
        :param chunk_size Size of chunks for chunked data
        :param steps Downsampling (1 by default)
        :return: Dataframe or Iterator (yield) of Dataframes
        """

    chunks = __nc2df(
        ncfile, start_time, end_time,
        drop_duplicates, skip_na, vars, user, password, chunked, chunk_size, steps)

    # Hadling either single result or chunked generator
    if not chunked :
        for result in chunks:
            return result
    else :
        return chunks

def __nc2df(
        ncfile : Union[Dataset, str],
        start_time: Union[datetime, datetime64]=None, end_time:Union[datetime, datetime64]=None,
        drop_duplicates=True,
        skip_na=False,
        vars=None,
        user=None,
        password=None,
        chunked=False,
        chunk_size=CHUNK_SIZE,
        steps=1) :
    """Private generator use by nc2df """

    if isinstance(ncfile, str) :
        ncfile = openNetCDF(ncfile, mode='r', user=user, password=password)

    size = len(ncfile.variables[TIME_VAR])

    start_idx = max(0, date_to_timeidx(ncfile, start_time)) if start_time else 0
    end_idx = min(date_to_timeidx(ncfile, end_time), size) if end_time else size

    # List of vars (along time)
    data_vars = []
    for varname, var in ncfile.variables.items() :
        if TIME_DIM in var.dimensions and varname != TIME_VAR :
            if vars is None or varname in vars :
                data_vars.append(varname)


    def to_df(start_idx, end_idx) :

        times = sec_to_datetime64(ncfile, ncfile.variables[TIME_VAR][start_idx:end_idx:steps])

        df = DataFrame(
            dict((var, ncfile.variables[var][start_idx:end_idx:steps]) for var in data_vars),
            index=times)

        # Set global attributes in DataFrame
        attrs = dict((key, getattr(ncfile, key)) for key in ncfile.ncattrs())
        df.attrs.update(attrs)

        # Drop duplicated : only keep last
        if drop_duplicates :
            df = df[~df.index.duplicated(keep="last")]

        if skip_na :
            df = df.dropna(axis=0, how='all')

        return df

    if chunked :
        chunk_size = chunk_size * steps
        for idx in range(start_idx, end_idx, chunk_size):
            yield to_df(start_idx=idx, end_idx=min(idx + chunk_size, end_idx))
    else :
        yield to_df(start_idx, end_idx)

def time2str(val) :
    """Format date to the minute """
    if val is None :
        return ""
    if isinstance(val, datetime64) :
        return np.datetime_as_string(val, unit='m')
    elif isinstance(val, datetime) :
        return val.strftime(TIME_FORMAT_MIN)

    raise Exception("Unknown date type : " + type(val))

def str2time64(val) :
    if val is None or val == "":
        return None
    return np.datetime64(val)


MIN_STEP=0
MAX_STEP=7200

def get_periods(time_s) :
    """Compute list of periods, by occurrence. Return list of (period, count)"""

    steps = time_s[1:] - time_s[0:len(time_s) - 1]
    unique, counts = np.unique(steps, return_counts=True)

    filtered_unique = unique[(unique > MIN_STEP) & (unique < MAX_STEP)]
    filtered_counts = counts[(unique > MIN_STEP) & (unique < MAX_STEP)]

    indices = np.argsort(-filtered_counts)[:3]
    periods_dic =  dict((filtered_unique[idx], filtered_counts[idx]) for idx in indices)
    return list((int(period), count) for period, count in periods_dic.items())


def parseTimezone(val) :
    """Parse timezone UTC+HH:MM to timedelta"""
    val = val.strip("UTC")
    hh, mm = val.split(":")
    hh= int(hh)
    mm = int(mm)

    if hh < 0 :
        mm = -mm

    return pd.to_timedelta(60*hh+mm, "min")

def with_auth(url, user, password) :
    parts = urlsplit(url)
    return "%s://%s:%s@%s/%s" % (parts.scheme, quote_plus(user), quote_plus(password), parts.netloc, parts.path)


def fillShortName(nc, shortname) :
    size = nc.dimensions[STATION_NAME_DIM].size

    # Transform to null terminated fixed length array of chars
    shortname_ = stringtochar(np.array(shortname, 'S%d' % size))
    nc.variables[STATION_NAME_VAR][:] = shortname_

def readShortname(nc) :
    char_array = nc.variables[STATION_NAME_VAR][:]

    # This is a 0D (no dimension) array !
    string_array = chartostring(char_array)

    return string_array[()]




def getProperties(network_id, station_id) :
    """Gather Network_ and Station_ properties """

    # Get properties for this station
    properties = {STATION_PREFIX + k : v for k, v in getStationInfo(network_id, station_id).items()}

    # Add properties of this network
    for key, val in getNetworkInfo(network_id).items():
        properties[NETWORK_PREFIX + key] = val

    return properties

def getMinMaxTimes(ncfile, data, times_idx, varname=None) :

    # For masked array => replace with nan
    if is_masked(data) :
        data = data.filled(np.nan)

    notnan_mask = ~np.isnan(data)
    if np.any(notnan_mask):

        resolution = getTimeResolution(ncfile)
        times_s = resolution * times_idx
        notnan_time_s = times_s[notnan_mask]

        min_time = sec_to_datetime64(ncfile, np.min(notnan_time_s))
        max_time = sec_to_datetime64(ncfile, np.max(notnan_time_s))

        return {
            FIRST_DATA_ATT : min_time,
            LAST_DATA_ATT : max_time}
    else :
        return {FIRST_DATA_ATT: None, LAST_DATA_ATT: None}


def parse_bool(value) :
    return value in ["true", "True", "1", "yes", "Yes"]