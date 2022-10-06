#!/usr/bin/env python
# Format Networks table
import sys, os

this_folder =  os.path.dirname(__file__)
sys.path.append(os.path.join(this_folder, "..", "..", ".."))

from libinsitu import parseCSV, getStationsInfo, getNetworksInfo
from csv import DictWriter

OUT = os.path.join(this_folder, "..", "networks.csv")

def transform(row) :
    res = dict()

    res["id"] = "[%s](%s)" % (row["ID"], row["DescriptionURL"])
    res["name"] = row["LongName"]

    res["vars"] = ", ".join(row["AvailableData"].split(","))

    stations = getStationsInfo(row["ID"])
    res["nb stations"] = len(stations)

    if row["TdsName"] :
        res["data"] = "[TDS](http://tds.webservice-energy.org/thredds/catalog/%s/catalog.html)" % row["TdsName"]
        if row["IsOpenData"] != "Yes" :
            res["data"] += "🔒"

    return  res


def main() :
    csv = getNetworksInfo().values()
    out_csv = [transform(row) for row in csv]

    with open(OUT, "w") as f :
        writer = DictWriter(f, out_csv[0].keys())
        writer.writeheader()
        for row in out_csv:
            writer.writerow(row)

if __name__ == '__main__':
    main()




