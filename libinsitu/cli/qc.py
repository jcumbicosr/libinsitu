import matplotlib.pyplot as plt
import argparse
from datetime import datetime, date

from libinsitu import LATITUDE_VAR, LONGITUDE_VAR, ELEVATION_VAR, info
from libinsitu.common import nc2df
from libinsitu.log import debug
from libinsitu.qc_utils import prepare_data, SolarRadVisualControl, flagData, wps_Horizon_SRTM, sun_position, get_cams
from dotenv import load_dotenv
import numpy as np

def main() :

    # Required to load CAMS email
    load_dotenv()

    parser = argparse.ArgumentParser(description='Perform QC anaylis on input file and generates visual control image')
    parser.add_argument('input', metavar='<file.nc>', type=str, help='Input local file or URL')
    parser.add_argument('output', metavar='<out.png>', type=str, help='Output image')
    parser.add_argument('--from-date', '-f', metavar='<yyyy-mm-dd>', type=datetime.fromisoformat, help='Start date on analysis', default='2015-01-01')
    parser.add_argument('--to-date', '-t', metavar='<yyyy-mm-dd>', type=datetime.fromisoformat, help='End date of analysis', default=datetime.now())
    parser.add_argument('--no-mc-clear', '-c', action="store_true", help='Disable McClear', default=False)

    args = parser.parse_args()

    df = nc2df(
        args.input,
        start_time=args.from_date,
        end_time=args.to_date,
        rename=True)

    lat = float(df.attrs[LATITUDE_VAR])
    lon = float(df.attrs[LONGITUDE_VAR])
    alt = float(df.attrs[ELEVATION_VAR])

    # Clean data
    df = prepare_data(df)

    # Compute geom & theoretical irradiance
    sp_df = sun_position(lat, lon, alt, df.index.min(), df.index.max())

    # Fetch horizons
    # TODO : Make it optional
    horizons = wps_Horizon_SRTM(lat, lon, alt)


    flag_df = flagData(df, sp_df)

    if not args.no_mc_clear :
        cams_df = get_cams(
            start_date=df.index.min(),
            end_date=df.index.max(),
            lat=lat, lon=lon,
            altitude=alt)

        cams_df = cams_df.reindex(df.index)
        info("Cams from %s to %s" % (cams_df.index.min(), cams_df.index.max()))


    else:
        cams_df = None

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
