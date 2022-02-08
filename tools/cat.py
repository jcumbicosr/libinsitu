#!/usr/bin/env python
import os, sys
this_folder =  os.path.dirname(__file__)
sys.path.append(os.path.join(this_folder, ".."))

from lib.common import file2df

CHUNK_SIZE=100

filename = sys.argv[1]
df = file2df(filename)

for i in range(0,df.shape[0],CHUNK_SIZE) :
    chunk = df[i:i+CHUNK_SIZE]
    chunk.to_string(sys.stdout, justify="left")