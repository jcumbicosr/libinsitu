#!/usr/bin/env python
# Temp file for merging input XLS file with CSV files

import sys, os
import xlrd
import csv


sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from lib.log import error

FIRST_ROW = 1
FIRST_COL = 1

COL_SUBS = {
    "StationID" : "ID",
    "RawTimeZone" : "Timezone"
}

def idTransformer(value) :
    return value.upper()

def latlonTransform(value) :
    value = value.replace(",", ".")
    if len(value) > 0 :
        tstfloat = float(value)

TRANSFORMERS = {
    "ID" : idTransformer,
    "Latitude" : latlonTransform,
    "Longitude" : latlonTransform
}




def cleanColName(col) :
    col = col.replace("Station_", "")
    if col in COL_SUBS :
        col = COL_SUBS[col]
    col = col[0].upper() + col[1:]
    return col

def read_sheet_raw(sheet) :
    """Read raw sheet into a list of dict"""
    cols = list(sheet.cell_value(FIRST_ROW, col) for col in range(FIRST_COL, sheet.ncols))
    cols = list(cleanColName(col) for col in cols if len(col) > 0)
    res = []

    def clean_val(value) :
        return str(value).strip()

    for row_idx in range(FIRST_ROW+1, sheet.nrows) :
        row = dict((col, clean_val(sheet.cell_value(row_idx, FIRST_COL + col_idx)))
                   for col_idx, col in enumerate(cols))
        res.append(row)
    return res

def read_network(network, sheet) :
    print(network, sheet.ncols, sheet.nrows)
    rows = read_sheet_raw(sheet)

    # Transform values if needed
    for row_idx, row in enumerate(rows) :
        for key, transformer in TRANSFORMERS.items() :
            try:
                if key in row :
                    row[key] = transformer(row[key])
            except Exception as e :
                error("Happened in %s: line %d, col:%s" % (network, row_idx, key))
                raise e

    # Filter non null IDS
    rows = list(row for row in rows if len(row["ID"]) > 0)
    return rows

def read_networks(workbook):

    networks = set(workbook.sheet_names())
    res = dict()

    for network in networks:
        network = network.strip()
        if network == "OverviewNetworks":
            continue

        res[network] = read_network(network, workbook.sheet_by_name(network))

    return res


def main(xls_file, out_folder) :
    wb = xlrd.open_workbook(xls_file)
    networks = read_networks(wb)

    for network, rows in networks.items() :
        with open(os.path.join(out_folder, "%s.csv" % network), "w") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=",")
            writer.writeheader()
            for row in rows :
                writer.writerow(row)




if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])