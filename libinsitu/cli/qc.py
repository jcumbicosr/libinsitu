import argparse
from datetime import datetime

import matplotlib.pyplot as plt
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

from libinsitu import openNetCDF, getNetworkId, readShortname, info, LATITUDE_VAR, LONGITUDE_VAR, ELEVATION_VAR
from libinsitu.common import netcdf_to_dataframe
from libinsitu.log import LogContext
from libinsitu.qc.qc_utils import flagData, write_flags, cleanup_data, visual_qc, compute_sun_pos


def parser() :
    parser = argparse.ArgumentParser(description='Perform QC analysis on input file. It can fill QC flags in it and / or generate visual QC image')
    parser.add_argument('input', metavar='<file.nc|odap_url>', type=str, help='Input local file or URL')
    parser.add_argument('--output', '-o', metavar='<out.png>', type=str, help='Output image')
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

    # Open in read or update mode
    mode = 'a' if args.update else 'r'
    ncfile = openNetCDF(args.input, mode=mode)

    # try to read network and station id from file
    network_id = getNetworkId(ncfile)
    station_id = readShortname(ncfile)

    with LogContext(network=network_id, station_id=station_id, file=args.input) :

        info("Start of QC")

        params = dict(
            start_time=args.from_date,
            end_time=args.to_date,
            rename_cols=True)

        if args.from_date is None and args.output is not None :
            # By default, show 5 years of data in graph ouptput
            params["rel_start_time"] = relativedelta(years=-5)

        # Load NetCDF timeseries as pandas Dataframe
        df = netcdf_to_dataframe(ncfile, **params)

        if args.output :

            visual_qc(
                df,
                with_horizons=args.with_horizons,
                with_mc_clear=args.with_mc_clear)

            # Save to output file
            plt.savefig(args.output)
            plt.close()

        if args.update :

            lat = float(df.attrs[LATITUDE_VAR])
            lon = float(df.attrs[LONGITUDE_VAR])
            alt = float(df.attrs[ELEVATION_VAR])


            # Update NetCDF file with QC
            df = cleanup_data(df)
            sp_df = compute_sun_pos(df, lat, lon, alt)
            flags_df = flagData(df, sp_df)


            write_flags(ncfile, flags_df)




