import argparse
import os.path
from datetime import datetime
from logging import info

import matplotlib.pyplot as plt
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

from libinsitu import openNetCDF, getNetworkId, readShortname, info, older_than, update_qc_flags
from libinsitu.common import netcdf_to_dataframe
from libinsitu.log import set_log_context
from libinsitu.qc.qc_utils import visual_qc


def parser() :

    parser = argparse.ArgumentParser(description='Perform QC analysis on input file. It can fill QC flags in it and / or generate visual QC image')
    parser.add_argument('input', metavar='<file.nc|odap_url>', type=str, help='Input local file or URL')
    parser.add_argument('--output', '-o', metavar='<out.png>', type=str, help='Output image')
    parser.add_argument('--incremental', '-i', action="store_true", help='If true, do not run if output exists and is more recent', default=False)
    parser.add_argument('--update', '-u', action="store_true", help='Update QC flags on input file', default=False)
    parser.add_argument('--from-date', '-f', metavar='<yyyy-mm-dd>', type=datetime.fromisoformat, help='Start date on analysis (last 5 years of data by default for graph output)', default=None)
    parser.add_argument('--to-date', '-t', metavar='<yyyy-mm-dd>', type=datetime.fromisoformat, help='End date of analysis', default=None)
    parser.add_argument('--with-mc-clear', '-wmc', action="store_true", help='Enable display of mcClear', default=False)
    parser.add_argument('--with-horizons', '-wh', action="store_true", help='Enable display of horizons', default=False)
    return parser

def main() :

    # Required to load CAMS email
    load_dotenv()

    args = parser().parse_args()

    set_log_context(file=args.input)

    # Open in read or update mode
    mode = 'a' if args.update else 'r'
    ncfile = openNetCDF(args.input, mode=mode)

    # try to read network and station id from file
    network_id = getNetworkId(ncfile)
    station_id = readShortname(ncfile)

    set_log_context(network=network_id, station_id=station_id)

    info("Start of QC")

    params = dict(
        start_time=args.from_date,
        end_time=args.to_date,
        rename_cols=True)

    if args.from_date is None and args.output is not None :
        # By default, show 5 years of data in graph ouptput
        params["rel_start_time"] = relativedelta(years=-5)

    # Incremental mode : skip if more recent
    if args.incremental and args.output and os.path.exists(args.output) and older_than(args.input, args.output) :
        info("Incremental mode : Output file %s is already present and more recent. Skipping" % args.output)
        return

    # Load NetCDF timeseries as pandas Dataframe


    if args.output :

        df = netcdf_to_dataframe(ncfile, **params)

        visual_qc(
            df,
            with_horizons=args.with_horizons,
            with_mc_clear=args.with_mc_clear)

        # Save to output file
        plt.savefig(args.output)
        plt.close()

    if args.update :

        update_qc_flags(
            ncfile,
            start_time=args.from_date,
            end_time=args.to_date)




