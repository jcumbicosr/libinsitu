#!/usr/bin/env python
# Temp file for merging input XLS file with CSV files
import argparse
import re
import  os
from collections import defaultdict
from csv import DictReader
import numpy as np
import netCDF4
import pytz
import requests
from timezonefinder import TimezoneFinder

import csv
from unidecode import unidecode
from datetime import datetime
from libinsitu import VALID_COLS

FIRST_ROW = 2
FIRST_COL = 2

DATE_FORMAT="%Y-%m-%d"
ALTERNATE_FORMAT="%d/%m/%Y"

COL_SUBS = {
    "StationID" : "ID",
    "FullName" : "Name",
    "RawTimeZone" : "Timezone",
    "KoeppenGeigerClimate" : "Climate",
    "DNI" : "DNI_Col",
    "DHI" : "DHI_Col",
    "GHI" : "GHI_Col",
    "Type" : "QualityStandard"
}



GEOLOC = {
    "Country" : ["country"],
    "Region" : ["region", "state", "territory"],
    "Address": ["house_name", "house_number", "road"],
    "City" : ["municipality", "city", "town", "village"]
}

LOCKED_COLS = ["StartDate", "EndDate", "TimeResolution"]

# For ID generation
FULLNAME_REPL = {
    "ST." : "",
    "SCHWABISCH" : "SCH"
}

def idTransformer(value) :
    return value.upper()

TRANSFORMERS = {
    "ID" : idTransformer,
}

colCounter = defaultdict(lambda : 0)


def cleanColName(col) :
    col = col.replace("Station_", "")
    if col in COL_SUBS :
        col = COL_SUBS[col]
    col = col[0].upper() + col[1:]
    return col

COMMA_NUMBER = r"^[0-9,]*$"


def str2val(val) :
    try:
        date = datetime.strptime(ALTERNATE_FORMAT, val)
        return date.strftime(DATE_FORMAT)
    except:
        pass

    if re.match(COMMA_NUMBER, val):
        val = val.replace(",", ".")
    try:
        return int(val)
    except:
        try:
            fval = float(val)
            if fval.is_integer():
                return int(fval)
            else:
                return fval
        except:
            return val





def generate_id(row) :

    if "ID" not in row or row["ID"] == "" :
        fullname = row["Name"]
        fullname = unidecode(fullname).upper()
        for key, repl in FULLNAME_REPL.items():
            fullname = fullname.replace(key, repl).strip()
        fullname = fullname.replace(' ', "")

        id = fullname[0:4]
        print("Generate ID: '%s' -> '%s'" % (fullname, id))

        row["ID"] = id

def count_cols(rows) :
    for row in rows :
        for key, val in row.items() :
            if val is not None and val != "" :
                colCounter[key] +=1
            else:
                colCounter[key] += 0



def load_csv(path) :
    if not os.path.exists(path) :
        return []
    with open(path, 'r') as f :
        reader = DictReader(f)
        return list(reader)

def redorder_cols(rows) :
    cols = list(rows[0].keys())
    sorted_cols = sorted(cols, key=lambda col : VALID_COLS.index(col))

    res = []
    for row in rows :
        res.append({col: row[col] for col in sorted_cols})
    return res

def save_csv(path, rows) :
    with open(path, "w") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=",", lineterminator=os.linesep)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

def merge(initial_rows, updated_rows) :

    initial_by_id = dict((row["ID"], row) for row in initial_rows)

    for row in updated_rows :
        id = row["ID"]
        if not id in initial_by_id :
            initial_by_id[id] = row
        else:
            initial_row = initial_by_id[id]

            for col, val in row.items() :
                if not col in initial_row :
                    initial_row[col] = val
                else:
                    initial_val = initial_row[col]
                    if str2val(initial_val) != val and col not in LOCKED_COLS :
                        print("Updating %s#%s : %s => %s " % (id, col, initial_val, val))
                        initial_row[col] = val

    print("Cols after merge", initial_rows[0].keys())

    return list(initial_by_id.values())



def save(networks, out_folder) :
    """Update existing CSV or create one"""
    for network, rows in networks.items() :

        print("Processing network %s" % network)

        path = os.path.join(out_folder, network + ".csv")

        initial = load_csv(path)

        merged = merge(initial, rows)

        save_csv(path, merged)

def get_loc(id, lat, lon) :
    url ="https://nominatim.openstreetmap.org/reverse?lat=%f&lon=%f&format=json&accept-language=en" % (lat, lon)
    return requests.get(url).json()


def enrich_address(row, lat, lon) :

    if row.get("Address", None) :
        print(f"Address already present for {row['ID']}, skipping")
        return

    loc = get_loc(row["ID"], lat, lon)

    if "error" in loc:
        print("Error for : %s/%s : %s" % (row["ID"], loc["error"]))
        return

    address = loc["address"]

    for col, keys in GEOLOC.items():
        val = ", ".join(address[key] for key in keys if key in address)
        row[col] = val

def enrich_climate(nc, row, lat, lon) :
    climate = get_KG_ClimZone(nc, lat, lon)
    row["Climate"] = climate

def enrich_timezone(tzFinder, row, lat, lon) :
    tzname = tzFinder.timezone_at(lng=lon, lat=lat)
    tz = pytz.timezone(tzname)
    now = datetime.now(tz)

    offset_min = now.utcoffset().total_seconds() / 60

    sign="+"
    if offset_min < 0 :
        sign = "-"
        offset_min = - offset_min

    row["Timezone"] = "UTC%s%02d:%02d" % (sign, offset_min / 60, offset_min % 60)




def get_KG_ClimZone(ds, lat, lon):
    vlat = ds['lat'][:]
    dlat = np.abs(vlat - lat)
    ilat = np.where(dlat == min(dlat))[0][0]

    if (lon > 180):
        lon += -360
    vlon = ds['lon'][:]
    dlon = np.abs(vlon - lon)
    ilon = np.where(dlon == min(dlon))[0][0]

    ID = np.minimum(30, ds['Band1'][ilat, ilon].data.astype(int))
    if (ID == 0):
        return
    else:
        return ds.getncattr(str(ID))

def process_file(args):

    rows = load_csv(args.input_file)

    # Open climate file if present
    nc_climate = netCDF4.Dataset(args.climate) if args.climate else None

    tzFinder = TimezoneFinder()

    for i, row in enumerate(rows):

        lat = str2val(row["Latitude"])
        lon = str2val(row["Longitude"])

        print(f"Processing ID {row['ID']}. {i}/{len(rows)}")

        print("Enriching address")
        enrich_address(row, lat, lon)

        if nc_climate:
            print("Enriching  climate")
            enrich_climate(nc_climate, row, lat, lon)

        print("Enrich  timezone")
        enrich_timezone(tzFinder, row, lat, lon)

    save_csv(args.out_file, rows)

def main() :

    global CACHE_FOLDER

    parser = argparse.ArgumentParser(description='Enrich CSV files of stations')
    parser.add_argument('input_file', metavar='<in.csv>', type=str, help='Input csv')
    parser.add_argument('out_file', metavar='<out.csv>', type=str, help='Output file')
    parser.add_argument("--cache", "-c", metavar="<tmp_dir>", type=str, help="Cache folder", default="/tmp")
    parser.add_argument("--climate", "-cli", metavar="<climate.nc>", type=str, help="NetCDF climate file")
    args = parser.parse_args()

    process_file(args)




if __name__ == '__main__':
    main()