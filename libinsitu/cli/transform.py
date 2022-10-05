#!/usr/bin/env python
import datetime
import numpy as np
import os.path
import sys
from os.path import basename, dirname

from libinsitu.common import *
from libinsitu.cdl import *
from libinsitu.handlers import HANDLERS, InSituHandler, listNetworks
from libinsitu.log import debug, info, warning, logger, LogContext, error
import argparse


DONE_SUFFIX = '.done'
ERR_SUFFIX = '.err'

BOUNDARY_TOLERANCE_PCT = 5

def check_boundaries(var, data) :
    """Check boundaries of a variable"""
    if not hasattr(var, VALID_MIN_ATTR) :
        return

    debug("Checking boundaries for %s" % var)

    minv = parse_value(getattr(var, VALID_MIN_ATTR))
    maxv = parse_value(getattr(var, VALID_MAX_ATTR))

    range = maxv - minv

    # Add tolerance
    minv = minv - range * BOUNDARY_TOLERANCE_PCT / 100
    maxv = maxv + range * BOUNDARY_TOLERANCE_PCT / 100

    def warn_boundary(idx, sign, bound) :
        if np.any(idx):
            warning("Boundary check : %d items of %s are %s %f: [%f:%f]",
                    np.sum(idx),
                    var.name,
                    sign,
                    bound,
                    np.min(data[idx]),
                    np.max(data[idx]))

    warn_boundary(data < minv, "<", minv)
    warn_boundary(data > maxv, ">", maxv)


def list_files(in_files, handler) :

    # Gather and sort files with pattern
    files = []
    for file_or_dir in in_files:
        if os.path.isdir(file_or_dir):
            files += handler.list_files(file_or_dir)
        else:
            files.append(file_or_dir)

    # Sort input files
    in_files = handler.sort_files(files)

    if len(in_files) == 0:
        warning("No input file found")
        sys.exit(0)

    return in_files


def process_network(network, station_id, out_filename, args) :

    # Get properties for this station
    properties = getProperties(network, station_id)

    now = datetime.now().isoformat()

    properties["UpdateTime"] = now
    properties["CreationTime"] = now

    handler : InSituHandler = HANDLERS[network](properties)

    in_files = list_files(args.in_files, handler)

    new = not os.path.exists(out_filename)
    mode = "w" if new else "a"
    ncfile = Dataset(out_filename, mode=mode)

    if  new :
        # Nc File does not exist ==> create it
        info("File '%s' was not there. Initializing it.", out_filename)
        init_nc(ncfile, properties, [])

    # Loop on input files
    for infile in in_files :

        # Incremental mode : check status files
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
                process_chunck(handler, infile, ncfile, args, properties)

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



def idx2slice(idx) :
    """If indices are regular, transform it into a slice : much faster for writing"""

    if len(idx) < 2 :
        return idx

    step = idx[1] - idx[0]

    if np.all(np.diff(idx) == step) :
        debug("Idx was slice")
        return slice(idx[0], idx[-1] + step, step)

    return idx

def check_and_assign(ncfile, data, times_idx, size_before, args) :

    # Check once for all if new chunk overlaps
    overlapping_mask = times_idx < size_before
    overlapping_indices = times_idx[overlapping_mask]

    for varname in data.columns:

        var = ncfile.variables[varname]
        new_values = data[[varname]].values.flatten()

        check_boundaries(var, new_values)

        # Overcoming this bug ; https://github.com/scipy/scipy/issues/6097
        if np.issubdtype(var.dtype, np.integer) :
            fill_value = getattr(var, FILL_VALUE_ATTR, DEFAULT_FILL_VALUE)
            new_values[np.isnan(new_values)] = fill_value

        if not np.any(overlapping_mask) or not args.check:
            # No overlap with previous data ? no need for check
            var[idx2slice(times_idx)] = new_values

        else :
            debug("Possible overlap, checking ...")

            if np.all(np.isnan(var[overlapping_indices])) :

                # All nans ? don't check further"
                write_mask = np.ones(new_values.shape, dtype=bool)

            else:
                # We won't override existing values with nans
                nan_mask = np.isnan(new_values)

                nna_overlapping_mask = overlapping_mask & ~nan_mask
                overlapping_idx = times_idx[nna_overlapping_mask]
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

            var[idx2slice(times_idx[write_mask])] = new_values[write_mask]



def process_chunck(handler, infile, ncfile, args, properties):

    info("processing chunk : %s", infile)

    # Read data
    data = handler.read_chunk(infile)

    if data is None or len(data) == 0 :
        warning("Chunk is empty")
        return

    # Time resolution, in seconds
    resolution_s = getTimeResolution(ncfile)

    # Drop duplicates
    data = data[~data.index.duplicated(keep="last")]

    # Reshape : regular time is faster to write in NetCDF (as slice)
    data = data.asfreq("%dS" % resolution_s)

    # Transform time to seconds since start date and time idx
    chunk_dates = data.index.values

    times_sec = datetime64_to_sec(ncfile, chunk_dates)

    columns = list(data.columns)

    # Create vars if not present yet
    missing_vars = list(col for col in columns if not col in ncfile.variables)
    if len(missing_vars) > 0:
        info("Adding missing vars : %s", missing_vars)
        init_nc(ncfile, properties, missing_vars)

    # Ensure all timestamps fall into resolution
    exact_idx = (times_sec % resolution_s) == 0
    nb_not_exact_times = len(times_sec) - np.sum(exact_idx)
    if nb_not_exact_times > 0:

        # Remove lines with wrong times
        data = data[exact_idx]
        times_sec = times_sec[exact_idx]

        warning("%d rows had timings not fitting the time resolution : skipping them" % nb_not_exact_times)


    # Seconds to time index, as per start date and resolution
    time_idx = seconds_to_idx(ncfile, times_sec)

    chunk_start = min(chunk_dates)
    chunk_end = max(chunk_dates)
    chunk_end_int = datetime64_to_sec(ncfile, chunk_end)

    info("chunck range: %s to %s. samples:%d", time2str(chunk_start), time2str(chunk_end), len(data.index))

    # Error if chunk starts before start time
    if sum(time_idx < 0) > 0 :
        raise Exception("Chunk start (%s) is before output start time. Skipping" % (time2str(chunk_start)))

    # Warning if resolution seems different
    # Error if scrictREsolution is set
    if len(times_sec) >= 2:

        periods = get_periods(times_sec)
        if len(periods) >= 1 :
            actual_resolution, count = periods[0]

            if actual_resolution != resolution_s:
                warning("Resolution of input chunk (%d sec) differs from resolution of output (%d sec)" % (actual_resolution, resolution_s))
                if args.strict_resolution :
                    warning("Strict resolution requested : skipping")
                    return

    # Fill time variable with proper values
    size_before = len(ncfile.variables[TIME_VAR]) # Remember the size of TIME before it is extended

    # Fill Time variable
    if len(ncfile.variables[TIME_VAR]) == 0 :
        next_time_sec =  datetime64_to_sec(ncfile, start_date64(ncfile))
    else:
        next_time_sec = ncfile.variables[TIME_VAR][-1] + resolution_s

    end_time_sec = chunk_end_int + resolution_s
    new_times_sec = np.arange(next_time_sec, end_time_sec, resolution_s)
    next_time_idx = seconds_to_idx(ncfile, next_time_sec)
    end_time_idx = seconds_to_idx(ncfile, end_time_sec)
    ncfile.variables[TIME_VAR][next_time_idx: end_time_idx] = new_times_sec

    # Store data values
    check_and_assign(ncfile, data, time_idx, size_before, args)

    info("Chunk processed successfully")


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


def parser() :
    parser = argparse.ArgumentParser(description='Transforms In-Situ data into NetCDF files')
    parser.add_argument('out', metavar='<out.nc>', type=str, help='Output file')
    parser.add_argument('in_files', metavar='<file|dir>', nargs='+', help='Input files or folders')
    parser.add_argument('--network', '-n', help='Network name', required=True, choices=listNetworks())
    parser.add_argument('--station-id', '-s', metavar='<SID>', help='Station ID', required=True)
    parser.add_argument('--incremental', '-i', default=False, action='store_true',
                        help="Incremental mode, skipping input files having a '.done' status files")
    parser.add_argument('--strict-resolution', '-sr', default=False, action='store_true',
                        help="Skip chunks having a different resulution")
    parser.add_argument('--check', '-c', default=False, action='store_true', help="Check potential override of data")
    parser.add_argument('--status-folder', '-f', metavar='<folder>', type=dir_path,
                        help='Separate folder for .done/.err files')
    return parser

def main():

    args = parser().parse_args()

    network = args.network
    station_id  = args.station_id

    with LogContext(network=network, station_id=station_id):
        process_network(network, station_id, args.out, args)

if __name__ == '__main__':
    main()