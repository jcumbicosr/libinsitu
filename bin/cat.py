#!/usr/bin/env python
import os, sys

this_folder =  os.path.dirname(__file__)
sys.path.append(os.path.join(this_folder, ".."))

from dateutil.relativedelta import relativedelta
from netCDF4 import Dataset
import argparse
import numpy as np
from numpy import datetime64

from six import StringIO
from datetime import datetime

from lib.log import debug

this_folder =  os.path.dirname(__file__)
sys.path.append(os.path.join(this_folder, ".."))

from lib.common import file2df, nc2df, TIME_VAR, datetime64_to_int, getTimeResolution, DATA_VARS

CHUNK_SIZE=1000
DATE_FORMATS_PARTS = [
    ("%Y", 4, "years"),
    ("-%m", 3, "months"),
    ("-%d", 3, "days"),
    ("T%H", 3, "hours"),
    (":%M", 3, "seconds")]

DATE_FORMATS = dict()
full_size=0
full_format=""
for part, size, name in DATE_FORMATS_PARTS :
    full_size += size
    full_format += part
    DATE_FORMATS[full_size] = (full_format, name)


def parse_date_filter(strval) -> (datetime64, datetime64):
    """Parse partial date to from/to datetimes"""
    length = len(strval)
    if not length in DATE_FORMATS :
        raise Exception('Invalid date time filter. THe following format are supported : %s' % ', '.join(format for format, name in DATE_FORMATS.values()))
    format, name = DATE_FORMATS[length]

    start = datetime.strptime(strval, format)
    end = start + relativedelta(**{name:1})

    debug(format, name, start, end)

    return np.datetime64(start), np.datetime64(end)

def date_to_timeidx(nc, date) :
    time_int = datetime64_to_int(nc, date)
    return int(time_int / getTimeResolution(nc))

def main() :

    parser = argparse.ArgumentParser(description='Dump content of NetCDF insitu data (CF compliant)')
    parser.add_argument('filename', metavar='<file.nc>', type=str, help='Input file')
    parser.add_argument('--type', '-t', choices=["csv", "text"], help='Output type', default="text")
    parser.add_argument('--skip-na', '-s', action='store_true', help="Skip lines with only NA values", default=False)
    parser.add_argument('--filter', '-f', metavar="'<time> or <from_time>~<to-time>, with any sub part of 'YYYY-mm-ddTHH:MM:SS'", help="Time filter")
    parser.add_argument('--cols', '-c', metavar="<col1>,<col2> ..", help="Selection of columns. All by default")
    args = parser.parse_args()
    cols = args.cols.split(",") if args.cols else None

    nc = Dataset(args.filename, mode='r')


    size = len(nc.variables[TIME_VAR])
    start_idx = 0
    end_idx = size

    if args.filter :
        if "~" in args.filter :
            filter1, filter2 = args.filter.split("~")
            fromTime, _ = parse_date_filter(filter1)
            _, toTime = parse_date_filter(filter2)
        else :
            fromTime, toTime = parse_date_filter(args.filter)

        start_idx = max(0, date_to_timeidx(nc, fromTime))
        end_idx = min(date_to_timeidx(nc, toTime), size)

    header = True

    for idx in range(start_idx, end_idx, CHUNK_SIZE) :

        chunk = nc2df(nc, start_idx=idx, end_idx=min(idx+CHUNK_SIZE, end_idx))

        if cols :
            chunk = chunk[cols]

        if args.skip_na :
            chunk = chunk.dropna(axis=0, how='all')

        if len(chunk) == 0 :
            continue

        if args.type == "text" :
            chunk.to_string(sys.stdout, justify="left", header=header)
            print("")
        elif args.type == "csv" :
            output = StringIO()
            chunk.to_csv(output, index_label="time", header=header)
            output.seek(0)
            sys.stdout.write(output.read())

        header = False


if __name__ == '__main__':
    main()
