import matplotlib.pyplot as plt
import argparse
from datetime import datetime

from libinsitu import LATITUDE_VAR, LONGITUDE_VAR, ELEVATION_VAR, openNetCDF, GLOBAL_TIME_RESOLUTION_ATTR
from libinsitu.common import nc2df
from libinsitu.qc_utils import SolarRadVisualControl, flagData, wps_Horizon_SRTM, sun_position, get_cams, \
    write_flags, cleanup_data
from dotenv import load_dotenv

def main() :

    # Required to load CAMS email
    load_dotenv()

    parser = argparse.ArgumentParser(description='Perform QC analysis on input file. It can fill QC flags in it and / or generate visual QC image')
    parser.add_argument('input', metavar='<file.nc|odap_url>', type=str, help='Input local file or URL')
    parser.add_argument('--output', '-o', metavar='<out.png>', type=str, help='Output image')
    parser.add_argument('--update', '-u', action="store_true", help='Update QC flags on input file', default=False)
    parser.add_argument('--from-date', '-f', metavar='<yyyy-mm-dd>', type=datetime.fromisoformat, help='Start date on analysis', default=None)
    parser.add_argument('--to-date', '-t', metavar='<yyyy-mm-dd>', type=datetime.fromisoformat, help='End date of analysis', default=None)
    parser.add_argument('--no-mc-clear', '-nc', action="store_true", help='Disable mcClear', default=False)
    parser.add_argument('--no-horizons', '-nh', action="store_true", help='Disable horizons', default=False)

    args = parser.parse_args()

    # Open in read or update mode
    mode = 'a' if args.update else 'r'
    ncfile = openNetCDF(args.input, mode=mode)

    # Load NetCDF timeseries as pandas Dataframe
    df = nc2df(
        ncfile,
        start_time=args.from_date,
        end_time=args.to_date,
        rename_cols=True)

    lat = float(df.attrs[LATITUDE_VAR])
    lon = float(df.attrs[LONGITUDE_VAR])
    alt = float(df.attrs[ELEVATION_VAR])

    resolution_sec = df.attrs[GLOBAL_TIME_RESOLUTION_ATTR]

    if args.output :
        # Resample to the minute to produce graph
        resolution_sec = 60

    # Clean data
    df = cleanup_data(df, resolution_sec)

    # Compute geom & theoretical irradiance
    sp_df = sun_position(lat, lon, alt, df.index.min(), df.index.max(), freq_sec=resolution_sec)

    # Compute QC flags
    flag_df = flagData(df, sp_df)

    if args.update :
        write_flags(ncfile, flag_df)

    if args.output :

        # Fetch horizons
        if args.no_horizons :
            horizons = None
        else:
            horizons = wps_Horizon_SRTM(lat, lon, alt)

        if  args.no_mc_clear :
            cams_df = None
        else:
            cams_df = get_cams(
                start_date=df.index.min(),
                end_date=df.index.max(),
                lat=lat, lon=lon,
                altitude=alt)
            cams_df = cams_df.reindex(df.index)

        # Draw figures
        SolarRadVisualControl(
            df,
            sp_df,
            flag_df,
            cams_df,
            horizons,
            ShowFlag=0)

        # Save to output file
        plt.savefig(args.output)
        plt.close()
