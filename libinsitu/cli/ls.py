#!/usr/bin/env python
import csv
import json
import os, sys

import argparse
from rich.console import Console
from rich.table import Table

from libinsitu.catalog import *
from libinsitu.log import console


def printCatalog(catalog, rec=False) :

    console = Console()

    if len(catalog.catalogs) > 0 :

        print("Sub catalogs : ")

        table = Table(show_header=True)
        table.add_column("Name", style="dim", width=12)
        table.add_column("url")

        for key, cat in catalog.catalogs.items() :
            table.add_row(
                cat.name,
                cat.url)

        console.print(table)

    if len(catalog.datasets) > 0 :

        print("Datasets : ")

        table = Table(show_header=True, show_lines=True)
        table.add_column("Name", style="dim", width=12)
        table.add_column("Protocol", style="dim", width=12)
        table.add_column("url")

        for key, dataset in catalog.datasets.items():
            table.add_row(
                dataset.name,
                "\n".join(dataset.services.keys()),
                "\n".join(dataset.services.values()))

        console.print(table)

    if rec :
        for sub_cat in catalog.catalogs.values() :
            printCatalog(sub_cat)

def filter_services(catalog, services) :
    for ds in catalog.datasets.values() :
        ds.services = {serv : url for serv, url in ds.services.items() if serv in services}
    for cat in catalog.catalogs.values() :
        filter_services(cat, services)

def flatten_ds(cat) :

    def list_ds(cat) :
        res = {}
        res.update(cat.datasets)
        for subcat in cat.catalogs.values() :
            res.update(list_ds(subcat))
        return res

    cat.datasets = list_ds(cat)
    cat.catalogs = {}

def output_csv(catalog) :
    writer = csv.DictWriter(sys.stdout, ["id", "name", "protocol", "url"])
    writer.writeheader()
    def dump_services(catalog) :
        for ds in catalog.datasets.values() :
            for protocol, url in ds.services.items() :
                writer.writerow(dict(
                    id = ds.id,
                    name = ds.name,
                    protocol = protocol,
                    url = url
                ))
        for cat in catalog.catalogs.values() :
            dump_services(cat)

    dump_services(catalog)


def main():

    # Put logs to stderr
    console.file = sys.stderr

    parser = argparse.ArgumentParser(description='Browse a TDS (THREDDS) catalog')
    parser.add_argument('url', metavar='<http://host/catalog.xml>', type=str, help='Start URL')
    parser.add_argument('--user', '-u', help='User login (or TDS_USER env var)',
                        default=os.environ.get("TDS_USER", None))
    parser.add_argument('--password', '-p', help='User password (or TDS_PASS env var)',
                        default=os.environ.get("TDS_PASS", None))
    parser.add_argument('--recursive', '-r', action="store_true", help="Fetch recursively")
    parser.add_argument('--output-format', '-of', choices=["display", "json", "csv"], help="Output format", default="display")
    parser.add_argument('--flatten', '-fl', action="store_true", help="Flatten datasets")
    parser.add_argument('--services', '-s', metavar="serv1,serv2, ...", help="Filter on list of services.")

    args = parser.parse_args()

    session = Session()
    if args.user:
        session.auth = (args.user, args.password)

    catalog = fetch_catalog(args.url, session, recursive=args.recursive)

    if args.services :
        # Filter only some services
        filter_services(catalog, args.services.split(","))

    if args.flatten :
        flatten_ds(catalog)

    if args.output_format == "json" :
        json.dump(
            catalog, sys.stdout,
            default=lambda d: {k : v for k, v in d.__dict__.items()},
            indent=2)
    elif args.output_format == "display" :
        printCatalog(catalog, rec=args.recursive)
    elif args.output_format == "csv" :
        output_csv(catalog)
    else:
        raise Exception("Format not supported : %s" % args.output_format)


if __name__ == '__main__':
    main()
