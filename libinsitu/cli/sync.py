#!/usr/bin/env python
import os.path
import shutil
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from tempfile import NamedTemporaryFile
from urllib.request import urlretrieve
import gzip
from dateutil.relativedelta import relativedelta

from libinsitu.common import getStationsInfo, DATE_FORMAT, parse_value, getNetworksInfo, parse_bool
from datetime import datetime, timedelta

from libinsitu.log import info, LogContext, IgnoreAndLogExceptions
import argparse

SOURCE_URL_ATTR="SourceURL"
RAW_PATH_ATTR="RawDataPath"
COMPRESS_ATTR="Compress"

ERROR_SUFFIX = ".error"
RECENT_DAYS = 40
ONE_MONTH = relativedelta(months=1)
NB_WORKERS=10

class PathInfo :
    def __init__(self):
        self.path = None
        self.recent = False

def date_placeholders(date) :
    """ Generate a dict of placeholder for start / end dates : YYYY MM DD / YYYYe MMe DDe """

    def date_dict(date, suffix = "") :
        return {
            "YYYY" + suffix : date.strftime("%Y"),
            "MM" + suffix : date.strftime("%m"),
            "DD" + suffix : date.strftime("%d")}

    return {
        **date_dict(date),
        **date_dict(date+ONE_MONTH, "e")}

def list_downloads(properties, url_pattern, path_pattern, start_date=None, end_date=None) :

    res = defaultdict(lambda : PathInfo())

    properties = dict((key, parse_value(val)) for key, val in properties.items())

    # No end date ? => until now
    if not end_date :
        end_date_str = properties.get("EndDate", None)
        end_date = datetime.now() if end_date_str is None else datetime.strptime(end_date_str, DATE_FORMAT)


    # Loop on months
    if not start_date :
        start_date =  datetime.strptime(properties["StartDate"], DATE_FORMAT)

    # Start first of the month
    date =  start_date.replace(day=1)

    while date <= end_date:

        date_dict = date_placeholders(date)

        url = url_pattern.format(**properties, **date_dict)
        path = path_pattern.format(**properties, **date_dict)

        res[url].path = path

        # "Recent" chunk ?
        if datetime.now() - date < timedelta(days=RECENT_DAYS) :
            res[url].recent = True

        date += ONE_MONTH

    return res

def zip_file(inf, outf) :
    with open(inf, 'rb') as f_in:
        with gzip.open(outf, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)



def do_download(url_paths, out, dry_run=False, compress=False) :

    def process_one(args):
        url, pathInfo = args

        out_path = os.path.join(out, pathInfo.path)

        with LogContext(file=out_path), IgnoreAndLogExceptions():

            # Skip file if already present, unless it is "recent"
            if os.path.exists(out_path) or os.path.exists(out_path + ERROR_SUFFIX):

                if pathInfo.recent:
                    info("File %s is already present but recent. Check if newer version exists", out_path)
                else:
                    info("File %s is already present. Skipping", out_path)
                    return

            folder = os.path.dirname(out_path)
            if not os.path.exists(folder):
                os.makedirs(folder)

            with NamedTemporaryFile() as tmpFile:

                if dry_run:
                    info("Would have downloaded %s -> %s " + ("[compressed]" if compress else ""), url, out_path)
                else:
                    info("Downloading %s -> %s", url, out_path)
                    urlretrieve(url, tmpFile.name)

                    if compress:
                        zip_file(tmpFile.name, out_path)
                    else:
                        # Files already exists ? Only update if size are different
                        if os.path.exists(out_path) and os.path.getsize(out_path) == os.path.getsize(tmpFile.name):
                            info("File {} was already present with same size => skipping")
                        else:
                            shutil.copy(tmpFile.name, out_path)

    # Parallel execution : wait for all executions to finish
    with ThreadPoolExecutor(max_workers=NB_WORKERS) as executor:
        executor.map(process_one, url_paths.items())



def parse_date(s):
    return datetime.strptime(s, '%Y-%m-%d')

def main() :

    networks_info = getNetworksInfo()

    parser = argparse.ArgumentParser(description='Get raw data files from HTTP APIs')
    parser.add_argument('network', metavar='<network>', choices=list(networks_info.keys()), help='Network')
    parser.add_argument('out_folder', metavar='<dir>', type=str, help='Output folder')
    parser.add_argument('--ids', metavar='station_id1,station_id2', type=str, help='Optional IDs', default=None)
    parser.add_argument('--start-date', metavar='yyyy-mm-dd', type=parse_date, help='Start date, optional (start of station by default)', default=None)
    parser.add_argument('--end-date', metavar='yyyy-mm-dd', type=parse_date, help='End date, optional (end of station by default)', default=None)
    parser.add_argument('--dry-run', '-n', action='store_true', help='Do not download anything. Only print what would be downloaded')
    args = parser.parse_args()

    stations = getStationsInfo(args.network)

    network_info = networks_info[args.network]
    url_pattern = network_info[SOURCE_URL_ATTR]
    path_pattern = network_info[RAW_PATH_ATTR]
    compress = parse_bool(network_info[COMPRESS_ATTR])

    if not url_pattern :
        raise Exception("'SourceURL' not defined for network %s" % args.network)

    station_ids = None if args.ids is None else args.ids.split(",")

    for id, properties in stations.items():

        if station_ids and not id in station_ids :
            continue

        with LogContext(network=args.network, station_id=id) :

            url_paths = list_downloads(properties, url_pattern, path_pattern, args.start_date, args.end_date)
            do_download(url_paths, args.out_folder, args.dry_run, compress)

if __name__ == '__main__':
    main()



