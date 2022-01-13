import datetime
import os.path
import sys
import glob
import pytz
from logging import debug, info
from netCDF4 import Dataset    # Note: python is case-sensitive!
import numpy as np
from csv import DictReader
import pandas as pd


import logging

from pandas import DataFrame

from brsn_reader import read_bsrn

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)


STATION_INFO_PATTERN = "res/%s_StationInfo.csv"
TIME_VAR = "Time"
GHI_VAR = "GHI"
DIF_VAR = "DIF"
DIR_VAR = "DIR"
TEMP_VAR = "T2"
HUMIDITY_VAR = "RH"
PRESSURE_VAR = "P"
DATA_VARS = [GHI_VAR, DIF_VAR, DIR_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR]

TIME_ORIGIN = "2000-01-01 00:00:00"

def getStationInfo(network, station_id) :
    csv_file = STATION_INFO_PATTERN % network
    with open(csv_file) as f :
        rows = DictReader(f)
        for row in rows :
            if row["ID"] == station_id :
                return row
    raise Exception("Station not found in %s" % csv_file)

def init_nc(ncfile) :

    info("Initializing file : %s", ncfile)

    ncfile.createDimension('time', None)

    # Create time
    ncfile.createVariable(TIME_VAR, int, ('time',), zlib=True)

    def createFloatVar(varname) :
        ncfile.createVariable(varname, np.float32, ('time',),
                              zlib=True)
                              #least_significant_digit=1)

    for var in DATA_VARS :
        createFloatVar(var)

def read_chunck(filename) :

    data, metadata = read_bsrn(filename)

    mappping = dict(
        ghi = GHI_VAR,
        dni = DIR_VAR,
        dhi = DIF_VAR,
        temp_air = TEMP_VAR,
        relative_humidity = HUMIDITY_VAR,
        pressure = PRESSURE_VAR,
    )

    data = data[list(mappping.keys())]

    return data.rename(columns = mappping)

def main(network, station_id, out_filename, in_files) :

    properties = getStationInfo(network, station_id)
    resolution = int(properties["TimeResolution"])
    start_date = datetime.datetime.strptime(properties["StartDate"], '%Y-%m-%d')
    start_date64 = np.datetime64(start_date)

    debug("Timezone : %s, %s", start_date, start_date.tzname())
    debug("start data 64 : %s", start_date64)

    ncfile = Dataset(out_filename, mode='w')

    if not TIME_VAR in ncfile.variables :
        init_nc(ncfile)

    for infile in in_files :

        info("Processing chunk : %s", infile)

        data = read_chunck(infile)

        # Transform time to seconds since start date and time idx
        time_seconds = pd.Series(data.index.values - start_date64).dt.total_seconds().values.astype(int)
        time_idx = time_seconds // (60 * resolution)

        info("Type time_index : %s", time_seconds.dtype)

        # Store time values
        ncfile.variables[TIME_VAR][time_idx] = time_seconds

        # Store data values
        for var in DATA_VARS :
            ncfile.variables[var][time_idx] = data[[ var ]]

if __name__ == '__main__':
    # TODO Use arg instead
    NETWORK = "BSRN"
    STATION_ID = "BUD"

    out_filename = sys.argv[1]
    dir = sys.argv[2]

    in_files = glob.glob(dir  + "/*.gz")

    debug(in_files)

    main(NETWORK, STATION_ID, out_filename, in_files)