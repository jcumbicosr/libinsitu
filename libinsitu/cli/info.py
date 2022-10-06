import argparse

from pandas import DataFrame

from libinsitu import getProperties, getNetworksInfo, getStationInfo, getStationsInfo, VALID_COLS, df_to_csv, df_to_json
from libinsitu.handlers import listNetworks
import sys

def parser() :
    parser = argparse.ArgumentParser(description='Prints / export meta data about networks and stations')
    parser.add_argument('--format', '-f', metavar='<format>', help="Output format", choices=["txt", "csv", "json"], default="txt")
    parser.add_argument('--no-header', '-nh', action="store_true", help="Disable printing of header for txt and csv output", default=False)
    parser.add_argument('--columns', '-c', metavar='<col1>,<col2>,...', help="Columns to show. All by default.")

    sub_parsers = parser.add_subparsers(dest="command", required=True)
    parser_networks = sub_parsers.add_parser("networks", help="Show networks meta-data")

    parser_stations = sub_parsers.add_parser("stations", help="Show networks meta-data")
    parser_stations.add_argument('--network', '-n', metavar='<network-id>', help="Only show stations for the selected network")
    return parser


def main() :


    args = parser().parse_args()

    if args.command == "networks" :
        data = getNetworksInfo().values()
    else :

        if args.network :
            data = [attrs for attrs in getStationsInfo(args.network).values()]
        else:
            data = []
            for network in listNetworks():
                data += [dict(network=network, **val) for val in getStationsInfo(network).values()]


    df = DataFrame(data, dtype=str).fillna("")

    if args.columns :
        columns = args.columns.split(",")
        df = df[columns]

    # Reorder columns
    if args.command == "stations" :
        df = df[[col for col in ["network"] + VALID_COLS if col in df.columns]]

    if args.format == "txt" :
        df.to_string(sys.stdout, index=False, header=not args.no_header)
        print()
    elif args.format == "csv" :
        df_to_csv(df, index=False, header=not args.no_header)
    else:
        df_to_json(df, orient="records", indent=2)

