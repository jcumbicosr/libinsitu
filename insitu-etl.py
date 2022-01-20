#!/usr/bin/env python
import datetime
import glob
import os.path
import sys
from datetime import datetime
from os.path import basename
from netCDF4 import Dataset
from lib.cdl import parse_cdl, cdl2netcdf
from lib.common import *
from lib.handlers import HANDLERS
from lib.log import debug, info, warning, logger, LogContext
import argparse

DATE_FORMAT = '%Y-%m-%d'
CDL_PATH = "res/cdl/base.cdl"

def init_nc(netcdf, properties) :

    with open(CDL_PATH, "r") as f:
        cdl =  parse_cdl(f, properties)

    cdl2netcdf(netcdf, cdl)

    # Init scalar vars
    netcdf.variables[LONGITUDE_VAR][0] = properties["Longitude"]
    netcdf.variables[LATITUDE_VAR][0] = properties["Latitude"]
    netcdf.variables[ELEVATION_VAR][0] = properties["Elevation"]
    netcdf.variables[STATION_NAME_VAR][:] = properties["ID"]

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

def check_boundaries(var, data) :
    for bound_name, sense in dict(Range_LowerBoundary=-1, Range_UpperBoundary=1).items() :
        if bound_name in var.ncattrs():
            bound = parse_value(var.__dict__[bound_name])
            idx = data < bound if sense == -1 else data > bound
            if idx.any() :
                warning("%d items of %s are %s than boundary : %f",
                        idx.sum(),
                        var.name,
                        "<" if sense == -1 else ">",
                        bound)

def main(network, station_id, out_filename, in_files) :

    # Sort input files
    in_files = sort_files(in_files)

    # Get properties for this station
    properties = getStationInfo(network, station_id)
    properties["CurrentTime"] = datetime.now().isoformat()

    # Open or create netCDF file
    if not os.path.exists(out_filename) :
        info("File '%s' was not there. Initalizing it.", out_filename)
        ncfile = Dataset(out_filename, mode="w")
        init_nc(ncfile, properties)
    else:
        ncfile = Dataset(out_filename, mode="a")

    # Loop on input files
    for infile in in_files :

        # Safe execution : do not stop on error
        try:
            with LogContext(file=os.path.basename(infile)):
                process_chunck(network, station_id, infile, ncfile)
        except Exception as e :

            # Do not fail : just log and process the next file
            logger.exception(e)



def process_chunck(network, station_id, infile, ncfile):
    info("processing chunk : %s", infile)

    # Get proper handler for this network
    handler = HANDLERS[network]

    # Read data
    data = handler.read_chunk(infile)

    # Time resolution, in seconds
    resolution_s = getTimeResolution(ncfile)


    # Transform time to seconds since start date and time idx
    chunk_dates = data.index.to_pydatetime()
    debug(chunk_dates=chunk_dates)
    times_int = date2int(ncfile, chunk_dates)
    time_idx = times_int // resolution_s

    # Ensure all timestamps fall into resolution
    exact = ((times_int % resolution_s) == 0).all()
    if not exact:
        wrong_times_int = times_int[times_int % resolution_s != 0]
        wrong_times_str = ",".join(str(date) for date in int2date(ncfile, wrong_times_int))
        raise Exception("Timestamps do not fit timeresolution of %d seconds : %s" % (resolution_s, wrong_times_str))

    # Warning if data not adjacent to previous one
    next_time_int = 0 if len(ncfile.variables[TIME_VAR]) == 0 else ncfile.variables[TIME_VAR][-1] + resolution_s
    next_time = int2date(ncfile, next_time_int)
    chunk_start = min(chunk_dates)
    chunk_end = max(chunk_dates)
    chunk_end_int = date2int(ncfile, chunk_end)

    info("Chunck range %s to %s", chunk_start, chunk_end)

    if chunk_start > next_time:
        warning(
            "New chunk not adjacent to previous data. Missing data between '%s' and '%s'. Values will be filled with NaN.",
            next_time,
            chunk_start)

    elif chunk_start < next_time:
        warning(
            "Data was already present between %s and %s. Overriding data.",
            chunk_start,
            next_time)

    # Warning if resolution seems different
    if len(times_int) >= 2:
        actual_resolution = times_int[1] - times_int[0]
        if actual_resolution != resolution_s:
            warning("Resolution of input chunk (%d sec) differs from resolution of output (%d sec)",
                    actual_resolution,
                    resolution_s)

    # Fill time variable with proper values
    new_times_int = np.arange(next_time_int, chunk_end_int + resolution_s, resolution_s)
    ncfile.variables[TIME_VAR][next_time_int // resolution_s: chunk_end_int // resolution_s + 1] = new_times_int

    # Store data values
    for varname in DATA_VARS:
        var = ncfile.variables[varname]
        samples = data[[varname]].values

        check_boundaries(var, samples)

        var[time_idx] = samples


def sort_files(files) :
    """ Sort filenames named like xxxMMYY*"""
    def yearmonth(path):
        file = basename(path)
        res =  file[5:7] + '' + file[3:5]
        return res

    return sorted(files, key=yearmonth)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Transform In-Situ data into NetCDF files')
    parser.add_argument('out', metavar='<out.nc>', type=str, help='Output file')
    parser.add_argument('infiles', metavar='<file|dir>', nargs='+', help='Input files or folders')
    parser.add_argument('--network', '-n', metavar='<NETWORK>', help='Network name', required=True)
    parser.add_argument('--station_id', '-s', metavar='<SID>', help='Station ID', required=True)
    args = parser.parse_args()

    network = args.network.upper()
    station_id  = args.station_id.upper()

    files = []
    for file_or_dir in args.infiles :
        if os.path.isdir(file_or_dir) :
            files += list(glob.glob(file_or_dir + "/*.gz"))
        else:
            files.append(file_or_dir)

    with LogContext(network=network, station_id=station_id) :
        main(network, station_id, args.out, files)