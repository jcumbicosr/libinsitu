import logging
from csv import DictReader
import numpy as np
from cftime import num2date, date2num
from numpy import timedelta64
from pandas import DataFrame

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

def getStationsInfo(network) :
    """REad station info from CSV"""
    csv_file = STATION_INFO_PATTERN % network
    res = dict()
    with open(csv_file) as f:
        rows = DictReader(f)
        for row in rows:
            res[row["ID"]] = row
    return res


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

def date2int(ncfile, dates) :
    return date2num(dates, ncfile.variables[TIME_VAR].units, ncfile.variables[TIME_VAR].calendar)

def int2date(ncfile, ints) :
    return num2date(ints, ncfile.variables[TIME_VAR].units, ncfile.variables[TIME_VAR].calendar)


def parse_value(val) :
    """Parse string value, trying first int, then float. return str value if none are correct"""
    if val is None or val == "":
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
    time0 = int2date(ncfile, 0)
    time0_64 = np.datetime64(time0)
    second = timedelta64(1, 's')
    times = time0_64 + second * ncfile.variables[TIME_VAR]
    df = DataFrame(
        dict((var, ncfile.variables[var][:]) for var in DATA_VARS if var in ncfile.variables),
        index=times)

    return df



