#!/usr/bin/env python
import os.path
import sys
from urllib.request import urlretrieve

from dateutil.relativedelta import relativedelta

from lib.common import getStationsInfo, DATE_FORMAT, parse_value
from datetime import datetime

from lib.log import info

URL_PATTERN = "http://reg.bom.gov.au/cgi-bin/climate/oneminsolar/getFile.cgi?stn_num={UID:06d}&year={YYYY}&month={MM}"
PATH_PATTERN = "{ID:}/{ID}-{YYYY}-{MM}.zip"


def list_downloads(network, out) :

    res = dict()
    stations = getStationsInfo(network)

    for id, properties in stations.items():

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

            path = os.path.join(out, path)

            res[url] = path


    return res

def do_download(url_paths) :

    for url, path in url_paths.items() :

        if os.path.exists(path) :
            continue

        folder = os.path.dirname(path)
        if not os.path.exists(folder):
            os.makedirs(folder)

        info("Downloading %s -> %s", url, path)
        urlretrieve(url, path)

def main(network, out) :
    url_paths = list_downloads(network, out)
    do_download(url_paths)


if __name__ == '__main__':

    network, out = sys.argv[1:]

    main(network, out)



