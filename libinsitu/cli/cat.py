import os, sys
from collections import defaultdict

from dateutil.relativedelta import relativedelta
import argparse
import numpy as np
from numpy import datetime64
from rich.console import Console
from rich.table import Table
from six import StringIO
from datetime import datetime

from libinsitu.log import debug
from libinsitu.common import nc2df, CHUNK_SIZE

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

class Stat() :
    def __init__(self):
        self.min = np.nan
        self.max = np.nan
        self.sum = 0.0
        self.count = 0

    def accumulate(self, series):
        minval = series.min()
        if minval is not np.nan :
            self.min = np.nanmin([self.min, minval])

        maxval = series.max()
        if maxval is not np.nan:
            self.max = np.nanmax([self.max, maxval])


        self.sum += series.sum()
        self.count += series.count()

def main() :

    parser = argparse.ArgumentParser(description='Dump content of NetCDF insitu data (CF compliant)')
    parser.add_argument('filename', metavar='<file.nc> or <http://opendap-url/.nc>', type=str, help='Input file or URL')
    parser.add_argument('--type', '-t', choices=["csv", "text"], help='Output type', default="text")
    parser.add_argument('--skip-na', '-s', action='store_true', help="Skip lines with only NA values", default=False)
    parser.add_argument('--filter', '-f', metavar="'<time> or <from_time>~<to-time>, with any sub part of 'YYYY-mm-ddTHH:MM:SS'", help="Time filter")
    parser.add_argument('--stats', '-z', action="store_true", default=False, help="Performs statistics. Don't print data")
    parser.add_argument('--cols', '-c', metavar="<col1>,<col2> ..", help="Selection of columns. All by default")
    parser.add_argument('--user', '-u', help='User login (or TDS_USER env var), for URL',
                        default=os.environ.get("TDS_USER", None))
    parser.add_argument('--password', '-p', help='User password (or TDS_PASS env var), for URL',
                        default=os.environ.get("TDS_PASS", None))
    parser.add_argument('--steps', '-st', help='Downsampling', type=int, default=1)
    parser.add_argument('--chunk_size', '-cs', help='Size of chunks', type=int, default=CHUNK_SIZE)
    args = parser.parse_args()
    cols = args.cols.split(",") if args.cols else None

    fromTime=None
    toTime=None
    if args.filter :
        if "~" in args.filter :
            filter1, filter2 = args.filter.split("~")
            fromTime, _ = parse_date_filter(filter1)
            _, toTime = parse_date_filter(filter2)
        else :
            fromTime, toTime = parse_date_filter(args.filter)



    chunks = nc2df(
        args.filename,
        fromTime, toTime,
        user=args.user, password=args.password,
        drop_duplicates=True, skip_na=args.skip_na, vars=cols, chunked=True,
        steps=args.steps, chunk_size=args.chunk_size)

    if args.stats :

        stats = defaultdict(lambda : Stat())
        for chunk in chunks :
            for col in chunk.columns :
                series = chunk[col]
                stats[col].accumulate(series)

        table = Table()
        for name in ["column", "count", "min", "max", "mean"] :
            table.add_column(name)

        for colname, stat in stats.items() :
            table.add_row(
                colname,
                "%d" % stat.count,
                "%.05g" % stat.min,
                "%.05g" % stat.max,
                "%.05g" % (stat.sum / stat.count))

        console = Console()
        console.print(table)

    else:
        header = True
        for chunk in chunks :

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