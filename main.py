#!/usr/bin/env python
import datetime
import os.path
import sys
import glob
from datetime import timedelta
from os.path import basename

from lib.cdl import parse_cdl, cdl2netcdf, updateAttributes
from lib.log import debug, info, warning
from netCDF4 import Dataset
import numpy as np
from csv import DictReader
import pandas as pd

from lib.brsn_reader import read_bsrn
from lib.common import *

CDL_PATH = "res/cdl/base.cdl"

def read_chunck(filename) :

    data, metadata = read_bsrn(filename)

    mapping = dict(
        ghi = GHI_VAR,
        dni = DIR_VAR,
        dhi = DIF_VAR,
        temp_air = TEMP_VAR,
        relative_humidity = HUMIDITY_VAR,
        pressure = PRESSURE_VAR)

    data = data[list(mapping.keys())]
    return data.rename(columns = mapping)

def get_cdl(properties) :
    with open(CDL_PATH, "r") as f :
        return parse_cdl(f, properties)

def init_nc(ncfile, properties) :
    cdl = get_cdl(properties)
    cdl2netcdf(ncfile,cdl)

def update_nc(netcdf, properties) :

    cdl = get_cdl(properties)

    updateAttributes(netcdf, cdl)

    netcdf.variables[LONGITUDE_VAR][0] = properties["Longitude"]
    netcdf.variables[LATITUDE_VAR][0] = properties["Latitude"]
    netcdf.variables[ELEVATION_VAR][0] = properties["Elevation"]
    netcdf.variables[STATION_NAME_VAR][:] = properties["ID"]


def main(network, station_id, out_filename, in_files) :

    # Get properties for this station
    properties = getStationInfo(network, station_id)
    resolution = int(properties["TimeResolution"])
    start_date = datetime.datetime.strptime(properties["StartDate"], '%Y-%m-%d')
    start_date64 = np.datetime64(start_date)

    # Open or create netCDF file
    mode = 'a' if os.path.exists(out_filename) else 'w'
    ncfile = Dataset(out_filename, mode=mode)

    if not TIME_VAR in ncfile.variables :
        info("%s was not there. Creating it", ncfile)
        init_nc(ncfile, properties)

    # Update attributes of file
    update_nc(ncfile, properties)

    # Sort input files
    in_files = sort_files(in_files)

    # Loop on input files
    for infile in in_files :

        info("Processing chunk : %s", infile)

        data = read_chunck(infile)

        # Transform time to seconds since start date and time idx
        time_seconds = pd.Series(data.index.values - start_date64).dt.total_seconds().values.astype(int)
        time_idx = time_seconds // (60 * resolution)

        # Warning if data not adjacent to previous one
        ntime = len(ncfile.dimensions[TIME_DIM])
        previous_end_time = start_date + timedelta(minutes=resolution) * ntime
        chunck_start_time = start_date + timedelta(minutes=resolution) * min(time_idx)

        debug("Startime: %s. Preivous end: %s", chunck_start_time, previous_end_time)

        if chunck_start_time > previous_end_time :
            warning("New chunk not adjacent to previous data. Missing data between '%s' and '%s'. Will be replaced with NaN.",
                    previous_end_time,
                    chunck_start_time)

        elif chunck_start_time < previous_end_time :
            warning(
                "Data was already present between %s and %s. Overriding.",
                previous_end_time,
                chunck_start_time)

        # Store time values
        ncfile.variables[TIME_VAR][time_idx] = time_seconds

        # Store data values
        for var in DATA_VARS :
            ncfile.variables[var][time_idx] = data[[ var ]]

def sort_files(files) :
    """ Sort filenames named like xxxMMYY*"""
    def yearmonth(path):
        file = basename(path)
        res =  file[5:7] + '' + file[3:5]
        print(file, res)
        return res

    return sorted(files, key=yearmonth)

if __name__ == '__main__':

    # TODO Use arg instead
    NETWORK = "BSRN"
    STATION_ID = "BUD"

    out_filename = sys.argv[1]
    dir = sys.argv[2]

    if os.path.isdir(dir) :
        files = glob.glob(dir + "/*.gz")
    else :
        files = sys.argv[2:]



    main(NETWORK, STATION_ID, out_filename, files)