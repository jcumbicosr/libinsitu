import logging
from csv import DictReader
import numpy as np

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
TIME_ORIGIN = "2000-01-01 00:00:00"



def getStationInfo(network, station_id) :

    """REad station info from CSV"""
    csv_file = STATION_INFO_PATTERN % network
    with open(csv_file) as f :
        rows = DictReader(f)
        for row in rows :
            if row["ID"] == station_id :
                return dict((key, parse_value(val)) for key, val in row.items())
    raise Exception("Station not found in %s" % csv_file)

def is_uniform(vector) :

    if type(vector) == list :
        vector = np.array(vector)

    if len(vector) <=1 :
        return True
    step = vector[1] - vector[0]
    ref = np.arange(vector[0], vector[-1] + step, step)
    return np.array_equal(ref, vector)



def parse_value(val) :
    """Parse string value, trying first int, then float. return str value if none are correct"""
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
    time = ncfile.variables[TIME_VAR]

