#!/usr/bin/env python

# Performs various checks
from netCDF4 import Dataset
import os, sys

this_folder =  os.path.dirname(__file__)
sys.path.append(os.path.join(this_folder, ".."))

from lib.common import TIME_VAR, is_uniform
from lib.log import *

def check_file(nc_file) :
    info("processing file : %s" % nc_file)

    ds = Dataset(nc_file, mode='r')

    time = ds.variables[TIME_VAR]

    info("Uniform time ? : %s", is_uniform(time))
    ds.close()


if __name__ == '__main__':
    for file in sys.argv[1:] :
        check_file(nc_file=file)