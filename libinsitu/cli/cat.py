import os, sys
from collections import defaultdict

from dateutil.relativedelta import relativedelta
import argparse
import numpy as np
from numpy import datetime64
from pandas import Series
from rich.console import Console
from rich.table import Table
from datetime import datetime

from libinsitu import qc_masks, find_qc_vars
from libinsitu.log import debug
from libinsitu.common import netcdf_to_dataframe, CHUNK_SIZE, df_to_csv, QC_FLAGS_VAR

QC_NONE = "none"
QC_MASK = "masks"
QC_NAMES = "names"
QC_EXPAND = "expand"

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

def print_meta(df, out=sys.stdout) :

    def print_dict(dic, indent=0) :
        for key, val in dic.items() :
            if isinstance(val, dict) :
                print("#%s %s:" % (" " * indent, key), file=out)
                print_dict(val, indent+2)
            else:
                print("#%s %s = %s" % (" " * indent, key, str(val)), file=out)

    print_dict(df.attrs)


def float_to_str(nb_digits) :
    format = "%." + str(nb_digits) + "f"

    def format_f(floatval) :
        return format % floatval

    return format_f

def build_formatters(df) :
    res = dict()
    for varname in df.columns :
        if not varname in df.attrs["variables"] :
            continue
        var_attrs = df.attrs["variables"][varname]
        if "least_significant_digit" in var_attrs :
            res[varname] = float_to_str(var_attrs["least_significant_digit"])
    return res


def parser() :

    parser = argparse.ArgumentParser(description='Dump content of NetCDF insitu data (CF compliant)')
    parser.add_argument('filename', metavar='<file.nc> or <http://opendap-url/.nc>', type=str, help='Input file or URL')
    parser.add_argument('--type', '-t', choices=["csv", "text"], help='Output type', default="text")
    parser.add_argument('--output', '-o', help='Output file. stdout if no set (default)', default=None)
    parser.add_argument('--skip-na', '-s', action='store_true', help="Skip lines with only NA values", default=False)
    parser.add_argument(
        '--skip-qc', '-sq', metavar="[True | False | flag1,flag2,flag3 | !flag1]",
        help="Skip lines with bad QC. Can be True (skip any QC flag), False (no filter, default), "
             "or comma separated list of QC flag names (skip only those failing test), "
             "possibly prefixed with '!' (consider all flags but those ones)",
             default=False)
    parser.add_argument(
        '--filter', '-f',
        metavar="<time-filter>",
        help="Time filter : <time> or <from_time>~<to-time>, with any sub part of 'YYYY-mm-ddTHH:MM:SS'")
    parser.add_argument(
        '--qc-format', '-qf',
        metavar="<format>",
        choices=[QC_NONE, QC_MASK, QC_NAMES, QC_EXPAND],
        help="Format for QC flags [none (default), mask, names or expand]",
        default=QC_NONE)
    parser.add_argument('--stats', '-z', action="store_true", default=False, help="Performs statistics. Don't print data")
    parser.add_argument('--header', '-hd', action="store_true", default=False, help="Dump global and var meta data as header")
    parser.add_argument('--no-data', '-n', action="store_true", default=False, help="Don't print data. Use with --header to print meta data only")
    parser.add_argument('--cols', '-c', metavar="<col1>,<col2> ..", help="Selection of columns. All by default")
    parser.add_argument('--user', '-u', help='User login (or TDS_USER env var), for URL',
                        default=os.environ.get("TDS_USER", None))
    parser.add_argument('--password', '-p', help='User password (or TDS_PASS env var), for URL',
                        default=os.environ.get("TDS_PASS", None))
    parser.add_argument('--steps', '-st', help='Downsampling', type=int, default=1)
    parser.add_argument('--chunk_size', '-cs', help='Size of chunks', type=int, default=CHUNK_SIZE)
    return parser

def main() :

    args = parser().parse_args()
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

    if args.qc_format is None :
        if args.type == "csv" :
            args.qc_format = QC_EXPAND
        else :
            args.qc_format = QC_NAMES

    # Parse skip_qc
    skip_qc = args.skip_qc
    if skip_qc != False :
        if skip_qc.lower() in ["1", "true"] :
            skip_qc = True
        else:
            skip_qc = args.skip_qc.split(",")


    expand_qc = (args.qc_format == QC_EXPAND) or args.stats

    chunks = netcdf_to_dataframe(
        args.filename,
        fromTime, toTime,
        user=args.user, password=args.password,
        drop_duplicates=True,
        skip_na=args.skip_na,
        skip_qc=skip_qc,
        vars=cols,
        chunked=True,
        steps=args.steps,
        expand_qc=expand_qc,
        chunk_size=args.chunk_size)

    if args.output is not None:
        out = open(args.output, 'w')
    else:
        out = sys.stdout

    if args.stats :
        show_stats(chunks, out=out)

    else:
        print_data(chunks, args, out=out)

def print_data(chunks, args, out=sys.stdout) :

    header = True
    formatters = None
    for chunk in chunks:

        if len(chunk) == 0:
            continue

        chunk = format_QC(chunk, args.qc_format)

        if header and args.header:
            print_meta(chunk, out=out)

        if formatters is None:
            formatters = build_formatters(chunk)

        if args.no_data:
            break

        if args.type == "text" :
            chunk.to_string(out, justify="left", header=header, formatters=formatters)
            print("", file=out)
        elif args.type == "csv" :
            df_to_csv(chunk, index_label="time", header=header, out=out)

        header = False

def show_stats(chunks, out=sys.stdout) :

    console = Console(file=out)

    stats = defaultdict(lambda : Stat())
    for chunk in chunks :
        for col in chunk.columns :
            series = chunk[col]
            stats[col].accumulate(series)

    # Data vars stats
    table = Table("column", "count", "min", "max", "mean")

    has_qc = False

    for colname, stat in stats.items() :

        if colname.startswith(QC_FLAGS_VAR) :
            has_qc = True
            continue

        table.add_row(
            colname,
            "%d" % stat.count,
            "%.05g" % stat.min,
            "%.05g" % stat.max,
            "%.05g" % (stat.sum / stat.count))

    console.print(table)

    if has_qc :

        table = Table("QC flag", "fail", "%")
        for colname, stat in stats.items() :

            if not colname.startswith(QC_FLAGS_VAR) :
                continue

            table.add_row(
                colname.strip(QC_FLAGS_VAR + "."),
                "%d" % stat.sum,
                "%.02f" % (stat.sum / stat.count * 100))

        console.print(table)

    # QC stats



def format_QC(df, qc_format) :

    qc_varname, qc_run_varname = find_qc_vars(df)

    if qc_varname is None or qc_format == QC_EXPAND :
        return df

    qc_vals = df[qc_varname]

    qc_run_vals = None
    if qc_run_varname is not None :
        qc_run_vals = df[qc_run_varname]

    masks_dict = qc_masks(df, qc_varname)

    if qc_format == QC_MASK :
        res = Series(data="", index = df.index, dtype=str)
        col_names = []

        # Loop on flags
        for idx, (flag, mask) in enumerate(masks_dict.items()) :

            # One letter for each flag
            flag_letter = chr(97+idx)
            col_names.append("%s:%s" % (flag, flag_letter))

            # Single letter
            letters = np.where(qc_vals.values & mask != 0, flag_letter, ".")

            # QC run flag avaialable : output '?' in case it did not run
            if qc_run_vals is not None :
                letters = np.where(qc_run_vals & mask == 0, "?", letters)

            # Append it to the column
            res += letters



        df[qc_varname] = res

        # Rename column to provide details
        col_name = "%s[%s]" % (qc_varname, ";".join(col_names))
        df = df.rename(columns={qc_varname: col_name})

        # Delte QC run column
        if qc_run_varname is not None:
            del df[qc_run_varname]


    elif qc_format == QC_EXPAND :

        # Done before via the "expand" param of netcdf_to_dataframe
        pass

    elif qc_format == QC_NAMES :
        res = Series(data="", index=df.index, dtype=np.object)
        for flag, mask in masks_dict.items():
            res += np.where(
                qc_vals & mask == 0,
                "",
                np.where(
                    res == "",
                    flag ,
                    ";" + flag))
        df[qc_varname] = res

    elif qc_format == QC_NONE :
        del df[qc_varname]

        if qc_run_varname is not None:
            del df[qc_run_varname]

    else:
        raise Exception("Unkown QC format : %s" % qc_format)

    return df

if __name__ == '__main__':
    main()