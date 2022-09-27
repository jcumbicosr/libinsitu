import matplotlib.pyplot as plt
import argparse
from datetime import datetime, date

from libinsitu.common import nc2df
from libinsitu.qc_utils import enrich_data, SolarRadVisualControl, flagData
from dotenv import load_dotenv

def main() :

    # Required to load CAMS email
    load_dotenv()

    parser = argparse.ArgumentParser(description='Perform QC anaylis on input file and generates visual control image')
    parser.add_argument('input', metavar='<file.nc>', type=str, help='Input local file or URL')
    parser.add_argument('output', metavar='<out.png>', type=str, help='Output image')
    parser.add_argument('--from-date', '-f', metavar='<yyyy-mm-dd>', type=datetime.fromisoformat, help='Start date on analysis', default='2015-01-01')
    parser.add_argument('--to-date', '-t', metavar='<yyyy-mm-dd>', type=datetime.fromisoformat, help='End date of analysis', default=datetime.now())
    parser.add_argument('--with-mc-clear', '-c', action="store_true", help='Fetch mc clear data', default=False)

    args = parser.parse_args()

    df = nc2df(
        args.input,
        start_time=args.from_date,
        end_time=args.to_date,
        rename=True)

    # Add SG2 , Cams and horizon data
    df = enrich_data(df, includeCAMS=True)

    Stat_Test, flag_df = flagData(df)

    SolarRadVisualControl(df, Stat_Test, flag_df,
            ShowFlag=0,
            ShowMcClear=args.with_mc_clear)

    # Save to output file
    plt.savefig(args.output)
    plt.close()
