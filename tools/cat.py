#!/usr/bin/env python
import os, sys

from netCDF4 import Dataset

this_folder =  os.path.dirname(__file__)
sys.path.append(os.path.join(this_folder, ".."))

from lib.common import file2df, nc2df, TIME_VAR

CHUNK_SIZE=100

filename = sys.argv[1]
df = file2df(filename)

nc = Dataset(filename, mode='r')

size = len(nc.variables[TIME_VAR])
for i in range(0, size, CHUNK_SIZE) :
    chunk = nc2df(nc, start_idx=i, end_idx=i+CHUNK_SIZE)
    chunk.to_string(sys.stdout, justify="left")