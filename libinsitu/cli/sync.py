#!/usr/bin/env python
import os.path
import shutil
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError
from urllib.request import urlretrieve
import gzip
import subprocess
import pytz
from dateutil.relativedelta import relativedelta
import requests
import jmespath
import re

from libinsitu import STATION_PREFIX, touch
from libinsitu.common import getStationsInfo, DATE_FORMAT, parse_value, getNetworksInfo, parse_bool
from datetime import datetime, timedelta
from dotenv import load_dotenv
from libinsitu.log import info, warning, LogContext, IgnoreAndLogExceptions
import argparse

SOURCE_URL_ATTR="SourceURL"
RAW_PATH_ATTR="RawDataPath"
COMPRESS_ATTR="Compress"

ERROR_SUFFIX = ".error"
EMPTY_SUFFIX = ".empty"
MISSING_SUFFIX = ".missing"
ONE_MONTH = relativedelta(months=1)
ONE_YEAR = relativedelta(years=1)
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
        **date_dict(date+ONE_MONTH, "_end")}

def prepare_properties(network, properties) :
    """ Adds prefix Station_ adds env variables (more user/passord)"""

    properties = dict((STATION_PREFIX + key, parse_value(val)) for key, val in properties.items())
    properties["station_id"] = properties["Station_ID"].lower()

    # Add environment variable prefixed by the network
    for key, val in os.environ.items() :
        if key.startswith(network) :
            key = key.replace(network + "_", "")
            properties[key] = val

    return properties

def get_pattern_period(path_pattern) :
    """Check if pattern is 'monthly' or 'yearly"""
    placeholders = re.findall(r"{(\w*)}", path_pattern)
    if "MM" in placeholders :
        return "monthly"
    elif "YYYY" in placeholders :
        return "yearly"
    else:
        raise("No time pattern found in %s" % path_pattern)

def list_urls_for_one_station(properties, url_pattern, path_pattern, start_date=None, end_date=None) :

    """Return a dict of input_path => output """
    urls = dict()
    end_dates = dict()

    # No end date ? => until last month
    if not end_date :
        end_date_str = properties.get("Station_EndDate", None)
        if end_date_str :
            end_date = datetime.strptime(end_date_str, DATE_FORMAT)
        else:
            # End date is now
            end_date = datetime.now()

    # By default, start of station
    if not start_date :
        start_date =  datetime.strptime(properties["Station_StartDate"], DATE_FORMAT)

    period = get_pattern_period(path_pattern)

    # Start at begin of period (month or year)
    if period == "monthly" :
        start_date = start_date.replace(day=1)
    elif period == "yearly":
        start_date = start_date.replace(month=1, day=1)
    else:
        raise Exception("Unsupported period : %s" % period)

    # Loop on months
    def process_all_months(pattern) :

        # Start first of the month
        date = start_date.replace(day=1)

        while date <= end_date:

            # Build placeholders for current date
            date_dict = date_placeholders(date)

            # format input URL
            url = pattern.format(**properties, **date_dict)

            if '*' in path_pattern :
                # Wildcard in output file pattern ? take the end of the url as filename
                path = os.path.basename(url)
            else:
                # Format output file pattern
                path = path_pattern.format(**properties, **date_dict)


            # Split '!' in case a sub path is provided inside Zip file
            if "!" in path :
                path  = path.split("!")[0]

            urls[url] = path

            # Next date
            if period == "monthly" :
                date += ONE_MONTH
            elif period == "yearly" :
                date += ONE_YEAR
            else:
                raise Exception("Unsupported period : %s" % period)

            # Save it at the last date for this URL
            if not url in end_dates or date > end_dates[url] :
                end_dates[url] = date


    if "[" in url_pattern :

        # There is an alternative [one,two] in the pattern
        reg = re.compile(r'.*(\[.*\]).*')
        match = reg.match(url_pattern)
        options = match.group(1).replace("[", "").replace("]", "").split(",")

        # Replace the options by a placeholder
        pattern = re.sub('\[.*\]', '{i}', url_pattern)

        # Loop on options
        for option in options :
            properties["i"] = option
            process_all_months(pattern)

    else :
        # No "[one,two]" in url pattern : simple case
        process_all_months(url_pattern)

    return urls, end_dates

def zip_file(inf, outf) :
    with open(inf, 'rb') as f_in:
        with gzip.open(outf, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

def file_mtime(path) :
    """Get modification time of a file"""
    return datetime.fromtimestamp(os.path.getmtime(path))

def utc(dt) :
    return dt.astimezone(pytz.utc).replace(tzinfo=None)

def modified_time(url) :
    """Get last-modified from header"""
    headers = requests.head(url).headers
    return utc(parsedate_to_datetime(headers["last-modified"]))


def ftp_get(url, out_path, dry_run=False) :
    """Sync FTP to out_path"""

    url = url.replace("ftp://", "")
    domain, uri = url.split("/", 1)
    user=None
    password=None
    if "@" in domain :
        credentials, domain = domain.split("@")
        user, password = credentials.split(":")
    print("Ftp :", domain, user, password, uri, out_path)

    user_pass = "" if not user else "-u %s,%s" % (user, password)

    if uri == "" :
        uri = "./"

    ftp_command = """
        set ftps:initial-prot ""; 
        set ftp:ssl-force true; 
        set ftp:ssl-protect-data true; 
        set ssl:verify-certificate no; 
        open ftp://{domain} {user_pass}; mirror --verbose --ignore-time --no-perms {dry_run} {src} {dest}
    """.format(
        user_pass=user_pass,
        domain=domain,
        src=uri,
        dest=out_path,
        dry_run="" if not dry_run else "--dry-run")


    args = ["lftp", "-c", ftp_command]
    info("Ftp command : %s" % str(args))

    # Call lftp
    subprocess.run(
        ["lftp", "-c", ftp_command],
        check=True)


def http_get(url, end_date, out_path, check_time=False, dry_run=False, compress=False) :

    with LogContext(file=out_path), IgnoreAndLogExceptions():

        # Skip file if already present, unless it is "recent"
        for path in [out_path, out_path + ERROR_SUFFIX, out_path + EMPTY_SUFFIX, out_path + MISSING_SUFFIX]:
            if os.path.exists(path):

                if check_time:

                    # Check modification date HTTP header
                    if file_mtime(path) > modified_time(url):
                        info("Local file %s is more recent than remote URL %s. Skipping" % (path, url))
                        return
                    else:
                        warning("Remote url %s is more recent than local file URL %s" % (url, path))

                elif end_date is not None and end_date > file_mtime(path) :
                    info("File is present but its modification time (%s) is before potential end date of data (%s). Retrying" % (file_mtime(path), end_date))

                else:
                    info("File %s is already present. Skipping", path)
                    return

        # Create folders
        folder = os.path.dirname(out_path)
        if not os.path.exists(folder) and not dry_run:
            os.makedirs(folder, exist_ok=True)

        # Do download
        with NamedTemporaryFile() as tmpFile:

            if dry_run:
                info("Would have downloaded %s -> %s " + ("[compressed]" if compress else ""), url, out_path)
                return

            try:
                info("Downloading %s -> %s", url, out_path)
                urlretrieve(url, tmpFile.name)
            except HTTPError as http_error:
                if http_error.code == 404:
                    info("Missing file : %s", url)
                    touch(out_path + MISSING_SUFFIX)
                    return
                else:
                    raise

            if os.path.getsize(tmpFile.name) < EMPTY_LIMIT:
                info("Output file is < %d bytes : considered empty" % EMPTY_LIMIT)
                touch(out_path + EMPTY_SUFFIX)
                return

            if compress:
                zip_file(tmpFile.name, out_path)
            else:

                # File exists with same size ? => Skipping
                if os.path.exists(out_path) and os.path.getsize(tmpFile.name) == os.path.getsize(out_path) :
                    info("Files have same size (%s) : considered identical. Do not update" % out_path)
                else:
                    shutil.copy(tmpFile.name, out_path)


def do_download(
        url_paths, url_end_dates,
        out,
        dry_run=False, compress=False, parallel=True, check_time=False) :

    def process_one_path(args):

        url, path = args
        end_date = url_end_dates.get(url, None)
        out_path = os.path.join(out, path)

        if url.startswith("http") :
            http_get(url, end_date, out_path, check_time=check_time, dry_run=dry_run, compress=compress)
        elif url.startswith("ftp") :
            ftp_get(url, out_path, dry_run=dry_run)
        else:
            raise Exception("Unsupported protocol : %s" % url)

    # Parallel execution : wait for all executions to finish
    if parallel :
        with ThreadPoolExecutor(max_workers=NB_WORKERS) as executor:
            executor.map(process_one_path, url_paths.items())
    else:
        for args in url_paths.items() :
            process_one_path(args)


def parse_date(s):
    return datetime.strptime(s, '%Y-%m-%d')

def http_list(network, stations_info, url_pattern, path_pattern, start_date, end_date) :

    url_paths = dict()
    url_end_dates = dict()

    for id, properties in stations_info.items():

        properties = prepare_properties(network, properties)

        with LogContext(network=network, station_id=id):

            paths, end_dates = list_urls_for_one_station(
                properties,
                url_pattern, path_pattern,
                start_date, end_date)

            url_paths.update(paths)
            url_end_dates.update(end_dates)

    return url_paths, url_end_dates

def http_json_list(url_pattern) :

    url, jsme_filter = url_pattern.split("|")
    url = url.replace("+json", "")

    # Get JSON
    js = requests.get(url).json()

    # Apply JMSE filter
    urls = jmespath.search(jsme_filter, js)

    return {url: os.path.basename(url) for url in urls}

def ftp_list(network, stations_info, url_pattern) :
    url_paths = dict()
    for id, properties in stations_info.items():

        properties = prepare_properties(network, properties)

        with LogContext(network=network, station_id=id):

            url = url_pattern.format(**properties)
            url_paths[url] = "./"

    return url_paths

def main() :

    networks_info = getNetworksInfo()

    epilog = "FTP user and passord should be passed via envvariables (or .env file) as <NETWORK>_FTP_USER and <NETWORK>_FTP_PASS"

    parser = argparse.ArgumentParser(description='Get raw data files from HTTP/FTP APIs', epilog=epilog)
    parser.add_argument('network', metavar='<network>', choices=list(networks_info.keys()), help='Network')
    parser.add_argument('out_folder', metavar='<dir>', type=str, help='Output folder')
    parser.add_argument('--ids', metavar='station_id1,station_id2', type=str, help='Optional IDs', default=None)
    parser.add_argument('--start-date', metavar='yyyy-mm-dd', type=parse_date, help='Start date, optional (start of station by default)', default=None)
    parser.add_argument('--end-date', metavar='yyyy-mm-dd', type=parse_date, help='End date, optional (end of station by default)', default=None)
    parser.add_argument('--dry-run', '-n', action='store_true', help='Do not download anything. Only print what would be downloaded')
    parser.add_argument('--sequential', '-seq', action='store_true', help='Disable parallel download')
    parser.add_argument('--check-time', '-t', action='store_true', help='Check modification time to override existing file')
    args = parser.parse_args()

    load_dotenv()

    network_info = networks_info[args.network]
    compress = parse_bool(network_info[COMPRESS_ATTR])

    url_pattern = network_info[SOURCE_URL_ATTR]
    path_pattern = network_info[RAW_PATH_ATTR]
    station_ids = None if args.ids is None else args.ids.split(",")

    stations_info = getStationsInfo(args.network)

    # Filter stations on requested ones
    if station_ids :
        stations_info = {id:val for id, val in stations_info.items() if id in station_ids}

    if not url_pattern:
        raise Exception("'SourceURL' not defined for network %s" % args.network)


    url_end_dates = dict()

    if "+json" in url_pattern :
        # Use http+json parsing
        url_paths = http_json_list(url_pattern=url_pattern)

    elif url_pattern.startswith("http") :

        # Use http syncing
        url_paths, url_end_dates = http_list(
            network=args.network,
            stations_info=stations_info,
            url_pattern=url_pattern,
            path_pattern=path_pattern,
            start_date=args.start_date,
            end_date=args.end_date)
    elif url_pattern.startswith("ftp") :

        # Use FTP
        url_paths = ftp_list(
            network=args.network,
            stations_info=stations_info,
            url_pattern=url_pattern)

    else:
        raise Exception("Unsupported URL : %s" % url_pattern)

    do_download(
        url_paths = url_paths,
        url_end_dates = url_end_dates,
        out=args.out_folder,
        dry_run=args.dry_run,
        compress=compress,
        parallel=not args.sequential,
        check_time=args.check_time)

if __name__ == '__main__':
    main()



