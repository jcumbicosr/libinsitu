#!/usr/bin/env python
import os.path
import shutil
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError
from urllib.request import urlretrieve
import gzip
from dateutil.relativedelta import relativedelta
import requests
import jmespath

from libinsitu import STATION_PREFIX, touch
from libinsitu.common import getStationsInfo, DATE_FORMAT, parse_value, getNetworksInfo, parse_bool
from datetime import datetime, timedelta

from libinsitu.log import info, LogContext, IgnoreAndLogExceptions
import argparse

SOURCE_URL_ATTR="SourceURL"
RAW_PATH_ATTR="RawDataPath"
COMPRESS_ATTR="Compress"

ERROR_SUFFIX = ".error"
EMPTY_SUFFIX = ".empty"
MISSING_SUFFIX = ".missing"
ONE_MONTH = relativedelta(months=1)
NB_WORKERS = 10
EMPTY_LIMIT = 50


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
    """Return a dict of input_path => output """
    res = dict()

    properties = dict((STATION_PREFIX + key, parse_value(val)) for key, val in properties.items())

    # No end date ? => until last month
    if not end_date :
        end_date_str = properties.get("Station_EndDate", None)
        if end_date_str :
            end_date = datetime.strptime(end_date_str, DATE_FORMAT)
        else:
            end_date = datetime.now() + relativedelta(days=-32)


    # Loop on months
    if not start_date :
        start_date =  datetime.strptime(properties["Station_StartDate"], DATE_FORMAT)

    # Start first of the month
    date =  start_date.replace(day=1)

    while date <= end_date:

        date_dict = date_placeholders(date)

        url = url_pattern.format(**properties, **date_dict)
        path = path_pattern.format(**properties, **date_dict)

        # Split '!' in case a sub path is provided inside Zip file
        if "!" in path :
            path  = path.split("!")[0]

        res[url] = path

        date += ONE_MONTH

    return res

def zip_file(inf, outf) :
    with open(inf, 'rb') as f_in:
        with gzip.open(outf, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)



def do_download(url_paths, out, dry_run=False, compress=False) :

    def process_one(args):
        url, path = args

        out_path = os.path.join(out, path)

        with LogContext(file=out_path), IgnoreAndLogExceptions():

            # Skip file if already present, unless it is "recent"
            if os.path.exists(out_path) \
                    or os.path.exists(out_path + ERROR_SUFFIX) \
                    or os.path.exists(out_path + EMPTY_SUFFIX) \
                    or os.path.exists(out_path + MISSING_SUFFIX):

                info("File %s is already present. Skipping", out_path)
                return

            folder = os.path.dirname(out_path)
            if not os.path.exists(folder) and not dry_run:
                os.makedirs(folder)

            with NamedTemporaryFile() as tmpFile:

                if dry_run:
                    info("Would have downloaded %s -> %s " + ("[compressed]" if compress else ""), url, out_path)
                else:
                    info("Downloading %s -> %s", url, out_path)

                    try:
                        urlretrieve(url, tmpFile.name)
                    except HTTPError as http_error :
                        if http_error.code == 404 :
                            info("Missing file : %s", url)
                            touch(out_path + MISSING_SUFFIX)
                            return
                        else:
                            raise

                    if compress:
                        zip_file(tmpFile.name, out_path)
                    elif os.path.exists(out_path) and os.path.getsize(out_path) == os.path.getsize(tmpFile.name):
                        info("File {} was already present with same size => skipping")
                    elif os.path.getsize(tmpFile.name) < EMPTY_LIMIT :
                        info("Output file is < %d bytes : considered empty" % EMPTY_LIMIT)
                        touch(out_path + EMPTY_SUFFIX)
                    else:
                        shutil.copy(tmpFile.name, out_path)

    # Parallel execution : wait for all executions to finish
    #with ThreadPoolExecutor(max_workers=NB_WORKERS) as executor:
    #    executor.map(process_one, url_paths.items())
    for args in url_paths.items() :
        process_one(args)


def parse_date(s):
    return datetime.strptime(s, '%Y-%m-%d')

def http_list(network, stations_info, url_pattern, path_pattern, start_date, end_date) :

    url_paths = dict()
    for id, properties in stations_info.items():

        with LogContext(network=network, station_id=id):

            url_paths.update(list_downloads(properties, url_pattern, path_pattern, start_date, end_date))

    return url_paths

def http_json_list(network, stations_info, url_pattern, path_pattern, start_date, end_date) :

    url, jsme_filter = url_pattern.split("|")

    # Get JSON
    js = requests.get(url).json()

    # Apply JMSE filter
    urls = jmespath.search(jsme_filter, js)

    return {url: os.path.basename(url) for url in urls}


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

    network_info = networks_info[args.network]
    compress = parse_bool(network_info[COMPRESS_ATTR])

    url_pattern = network_info[SOURCE_URL_ATTR]
    path_pattern = network_info[RAW_PATH_ATTR]
    station_ids = None if args.ids is None else args.ids.split(",")

    stations_info = getStationsInfo(args.network)

    # Filter stations on requested ones
    if station_ids :
        station_ids = {id:val for id, val in stations_info.items() if id in station_ids}

    if not url_pattern:
        raise Exception("'SourceURL' not defined for network %s" % args.network)

    if "|" in url_pattern :
        # http+json
        list_func = http_json_list
    elif url_pattern.startswith("http") :
        list_func = http_list
    else:
        raise Exception("Unsupported URL : %s" % url_pattern)

    url_paths = list_func(args.network, stations_info, url_pattern, path_pattern, args.start_date, args.end_date)

    do_download(url_paths, args.out_folder, args.dry_run, compress)

if __name__ == '__main__':
    main()



