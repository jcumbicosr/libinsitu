#!/usr/bin/env python
import os, sys

from requests import Session
import argparse
from rich.console import Console
from rich.table import Table

from libinsitu.catalog import *


def printCatalog(catalog) :

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


def main():

    parser = argparse.ArgumentParser(description='Browse a TDS (THREDDS) catalog')
    parser.add_argument('url', metavar='<http://host/catalog.xml>', type=str, help='Start URL')
    parser.add_argument('--user', '-u', help='User login (or TDS_USER env var)',
                        default=os.environ.get("TDS_USER", None))
    parser.add_argument('--password', '-p', help='User password (or TDS_PASS env var)',
                        default=os.environ.get("TDS_PASS", None))

    args = parser.parse_args()

    session = Session()
    if args.user:
        session.auth = (args.user, args.password)

    catalog = fetch_catalog(args.url, session, recursive=False)

    printCatalog(catalog)

if __name__ == '__main__':
    main()
