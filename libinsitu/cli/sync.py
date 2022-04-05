#!/usr/bin/env python
import os.path
import shutil
import sys
from collections import defaultdict
from tempfile import NamedTemporaryFile
from urllib.request import urlretrieve

from dateutil.relativedelta import relativedelta

from libinsitu.common import getStationsInfo, DATE_FORMAT, parse_value
from datetime import datetime, timedelta

from libinsitu.log import info, LogContext, IgnoreAndLogExceptions

URL_PATTERN = "http://reg.bom.gov.au/cgi-bin/climate/oneminsolar/getFile.cgi?stn_num={UID:06d}&year={YYYY}&month={MM}"
PATH_PATTERN = "{ID}/{ID}-{YYYY}-{MM}.zip"

ERROR_SUFFIX = ".error"
RECENT_DAYS = 40


class PathInfo :
    def __init__(self):
        self.path = None
        self.recent = False

def list_downloads(properties) :

    res = defaultdict(lambda : PathInfo())

    properties = dict((key, parse_value(val)) for key, val in properties.items())

    # No end date ? => until now
    end_date_str = properties.get("EndDate", None)
    end_date = datetime.now() if end_date_str is None else datetime.strptime(end_date_str, DATE_FORMAT)

    # Loop on months
    date = datetime.strptime(properties["StartDate"], DATE_FORMAT)

    while date <= end_date:
        date += relativedelta(months=1)

        year = date.strftime("%Y")
        month = date.strftime("%m")

        url = URL_PATTERN.format(**properties, YYYY=year, MM=month)
        path = PATH_PATTERN.format(**properties, YYYY=year, MM=month)

        res[url].path = path

        # "Recent" chunk ?
        if datetime.now() - date < timedelta(days=RECENT_DAYS) :
            res[url].recent = True

    return res

def do_download(url_paths, out) :

    for url, pathInfo in url_paths.items() :

        path = os.path.join(out, pathInfo.path)

        with LogContext(file=path), IgnoreAndLogExceptions() :

            # Skip file if already present, unless it is "recent"
            if os.path.exists(path) or os.path.exists(path + ERROR_SUFFIX):

                if pathInfo.recent :
                    info("File %s is already present but recent. Check if newer version exists", path)
                else :
                    info("File %s is already present. Skipping", path)
                    continue

            folder = os.path.dirname(path)
            if not os.path.exists(folder):
                os.makedirs(folder)

            with NamedTemporaryFile() as tmpFile :

                info("Downloading %s -> %s", url, path)
                urlretrieve(url, tmpFile.name)

                # Files already exists ? Only update if size are different
                if os.path.exists(path) and os.path.getsize(path) == os.path.getsize(tmpFile.name) :
                    info("File {} was already present with same size => skipping")
                else:
                    shutil.copy(tmpFile.name, path)

def main() :

    network, out = sys.argv[1:]

    stations = getStationsInfo(network)

    for id, properties in stations.items():
        with LogContext(network=network, station_id=id) :

            url_paths = list_downloads(properties)
            do_download(url_paths, out)

if __name__ == '__main__':
    main()



