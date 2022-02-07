#!/usr/bin/env python
import datetime
import glob
import os.path
import sys
from datetime import datetime
from os.path import basename, dirname
from netCDF4 import Dataset
from lib.cdl import parse_cdl, cdl2netcdf
from lib.common import *
from lib.handlers import HANDLERS
from lib.log import debug, info, warning, logger, LogContext
import argparse


CDL_PATH = "res/cdl/base.cdl"
DONE_SUFFIX = '.done'
ERR_SUFFIX = '.err'
EPSILON = 0.001

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
    """Check boundaries of a variable"""
    for bound_name, sense in dict(Range_LowerBoundary=-1, Range_UpperBoundary=1).items() :
        if bound_name in var.ncattrs():
            bound = parse_value(var.__dict__[bound_name])
            idx = data < bound if sense == -1 else data > bound
            if np.any(idx) :
                warning("Boundary check : %d items of %s are %s %f: [%f:%f]",
                    np.sum(idx),
                    var.name,
                    "<" if sense == -1 else ">",
                    bound,
                    np.min(data[idx]),
                    np.max(data[idx]))

def main(network, station_id, out_filename, in_files, args) :

    # Sort input files
    in_files = sort_files(in_files)

    # Get properties for this station
    properties = getStationInfo(network, station_id)
    properties["CurrentTime"] = datetime.now().isoformat()

    handler = HANDLERS[network]

    # Open or create netCDF file
    new = False
    if not os.path.exists(out_filename) :
        info("File '%s' was not there. Initalizing it.", out_filename)
        ncfile = Dataset(out_filename, mode="w")
        init_nc(ncfile, properties)
        new=True
    else:
        ncfile = Dataset(out_filename, mode="a")
        start_time = get_start_time(ncfile)
        # If start time changed, the whole file should be processed again
        if len(ncfile.variables[TIME_VAR]) > 0 :
            expected_time = datetime.strptime(properties["StartDate"], DATE_FORMAT)
            if start_time != expected_time :
                raise(Exception("Start time of output file (%s) is different from start time in station info (%s). Please delete output file and process it completely" % (
                    start_time,
                    expected_time)))


    # Loop on input files
    for infile in in_files :

        # Icremental mode : check status files
        status_folder = args.status_folder or dirname(infile)
        status_file = os.path.join(status_folder, basename(infile) + DONE_SUFFIX)
        err_file = os.path.join(status_folder, basename(infile) + ERR_SUFFIX)

        # Incremental mode : if output was already there, don't proess input files having a more recent .done file
        if not new and args.incremental and os.path.exists(status_file) and older_than(infile, status_file):
            info("File %s is older than status file %s : Skipping", infile, status_file)
            continue

        with LogContext(file=os.path.basename(infile)):

            # Safe execution : do not stop on error
            try:
                process_chunck(handler, infile, ncfile, args)

                # Incremental mode : touch status file
                if args.incremental:
                    touch(status_file)

                    # err file was present : delete it
                    if os.path.exists(err_file) :
                        os.remove(err_file)

            # Don't intercept Ctrl-C : cancel the whole process
            except KeyboardInterrupt as e :
                raise e

            except Exception as e :

                # Write .err file
                if args.incremental:
                    touch(os.path.join(status_folder, basename(infile) + ERR_SUFFIX))

                # Do not fail : just log and process the next file
                logger.exception(e)

def check_and_assign(ncfile, data, time_idx, size_before, args) :

    # Check once for all if new chunk overlaps
    overlapping_mask = time_idx < size_before
    is_overlapping = np.any(overlapping_mask)
    overlapping_indices = time_idx[overlapping_mask]

    for varname in DATA_VARS:
        var = ncfile.variables[varname]
        new_values = data[[varname]].values.flatten()

        check_boundaries(var, new_values)

        if not is_overlapping or not args.check:
            # No need for check
            write_mask = np.ones(new_values.shape, dtype=bool)

        else :
            debug("Possible overlap, checking ...")

            if np.all(np.isnan(var[overlapping_indices])) :

                debug("All nans : don't check further")
                write_mask = np.ones(new_values.shape, dtype=bool)

            else:
                # We won't override existing values with nans
                nan_mask = np.isnan(new_values)

                nna_overlapping_mask = overlapping_mask & ~nan_mask
                overlapping_idx = time_idx[nna_overlapping_mask]
                overlapping_values = new_values[nna_overlapping_mask]
                overlapped_values = var[overlapping_idx]

                conflicting_indices = ~np.isnan(overlapped_values) & ~np.isclose(overlapping_values, overlapped_values)

                if np.any(conflicting_indices) :

                    conflicting_overlapped =  overlapped_values[conflicting_indices]
                    conflicting_overlapping = overlapping_values[conflicting_indices]

                    warning("%d conflicting values for %s. Overriding [%f:%f] -> [%f:%f]",
                            np.sum(conflicting_indices),
                            varname,
                            np.nanmin(conflicting_overlapped), np.nanmin(conflicting_overlapped),
                            np.nanmin(conflicting_overlapping), np.nanmin(conflicting_overlapping))

                # Write NaN if they do not overlap with existing data (this extends the dimension)
                write_mask = nan_mask | ~overlapping_mask

        var[time_idx[write_mask]] = new_values[write_mask]

def process_chunck(handler, infile, ncfile, args):

    info("processing chunk : %s", infile)

    # Read data
    data = handler.read_chunk(infile)

    start_time = get_start_time(ncfile)

    # Time resolution, in seconds
    resolution_s = getTimeResolution(ncfile)

    # Transform time to seconds since start date and time idx
    chunk_dates = data.index.values

    times_int = datetime64_to_int(ncfile, chunk_dates)
    time_idx = times_int // resolution_s

    # Ensure all timestamps fall into resolution
    exact = ((times_int % resolution_s) == 0).all()
    if not exact:
        wrong_times_int = times_int[times_int % resolution_s != 0]
        wrong_times_str = ",".join(str(date) for date in int_to_datetime64(ncfile, wrong_times_int))
        raise Exception("Timestamps do not fit timeresolution of %d seconds : %s" % (resolution_s, wrong_times_str))

    next_time_int = 0 if len(ncfile.variables[TIME_VAR]) == 0 else ncfile.variables[TIME_VAR][-1] + resolution_s
    chunk_start = min(chunk_dates)
    chunk_end = max(chunk_dates)
    chunk_end_int = datetime64_to_int(ncfile, chunk_end)

    info("chunck range: %s to %s. samples:%d", chunk_start, chunk_end, len(data.index))

    # Error if chunk starts before start time
    if chunk_start < start_time:
        raise Exception("Chunk start (%s) is before output start time (%s). Skipping" % (chunk_start, start_time))

    # Warning if resolution seems different
    # Error if scrictREsolution is set
    if len(times_int) >= 2:
        actual_resolution = times_int[1] - times_int[0]
        if actual_resolution != resolution_s:
            message = "Resolution of input chunk (%d sec) differs from resolution of output (%d sec)" % (actual_resolution, resolution_s)
            if args.strict_resolution :
                raise Exception(message)
            else:
                warning(message)

    # Fill time variable with proper values
    size_before = len(ncfile.variables[TIME_VAR])
    new_times_int = np.arange(next_time_int, chunk_end_int + resolution_s, resolution_s)
    ncfile.variables[TIME_VAR][next_time_int // resolution_s: chunk_end_int // resolution_s + 1] = new_times_int

    # Store data values
    check_and_assign(ncfile, data, time_idx, size_before, args)


def sort_files(files) :
    """ Sort filenames named like xxxMMYY*"""
    def yearmonth(path):
        file = basename(path)
        year = file[5:7]
        month = file[3:5]
        if year.isnumeric() :
            year_num = int(year)
            year_num += 1900 if year_num > 70 else 2000
            year = str(year_num)
        res =  year + '-' + month + '-' + file[7:]
        return res

    return sorted(files, key=yearmonth)

def dir_path(path):
    if os.path.isdir(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} is not a valid folder")


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Transform In-Situ data into NetCDF files')
    parser.add_argument('out', metavar='<out.nc>', type=str, help='Output file')
    parser.add_argument('infiles', metavar='<file|dir>', nargs='+', help='Input files or folders')
    parser.add_argument('--network', '-n', metavar='<NETWORK>', help='Network name', required=True)
    parser.add_argument('--station_id', '-s', metavar='<SID>', help='Station ID', required=True)
    parser.add_argument('--incremental', '-i',  default=False, action='store_true', help="Incremental mode, skipping input files having a '.done' status files")
    parser.add_argument('--strict-resolution', '-sr', default=False, action='store_true', help="Skip chunks having a different resulution")
    parser.add_argument('--check', '-c', default=False, action='store_true', help="Check potential override of data")
    parser.add_argument('--status-folder', '-f', metavar='<folder>', type=dir_path, help='Separate folder for .done/.err files')
    args = parser.parse_args()

    network = args.network
    station_id  = args.station_id.upper()

    handler = HANDLERS[network]

    with LogContext(network=network, station_id=station_id):

        files = []
        for file_or_dir in args.infiles :
            if os.path.isdir(file_or_dir) :
                files += list(glob.glob(file_or_dir + "/" + handler.pattern()))
            else:
                files.append(file_or_dir)

        if len(files) == 0:
            warning("No input file found")
            sys.exit(0)

        main(network, station_id, args.out, files, args)