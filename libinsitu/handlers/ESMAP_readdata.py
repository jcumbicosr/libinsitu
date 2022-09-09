# -*- coding: utf-8 -*-
"""
Created on Fri Sep  9 09:10:39 2022

@author: y-m.saint-drenan
"""
import os
import shutil
import pandas as pd
import csv
from zipfile import ZipFile

pathIN='V:\\IN_SITU_data\\RawData\\ESMAP\\'
pathOUT='.//'
wd=os.getcwd()

listFiles=os.listdir(pathIN)
listMeta=[x for x in listFiles if 'metadata' in x ]

iStation=0

# read the metadata
reader = csv.reader(open(pathIN+listMeta[iStation], 'r'))
dictmeta = {}
for row in reader:
   k, v = row
   dictmeta[k] = v

# extract the zipped archive
DataArchive=listMeta[iStation].replace('metadata','data').replace('csv','zip')
PathUnZip='tmp_unzipped_'+DataArchive.replace("-", "_").replace(".", "_")
zipObj=ZipFile(pathIN+DataArchive, 'r')
zipObj.extractall(PathUnZip)

# read the unzipped archive
os.chdir(PathUnZip)
filelist=os.listdir('./')
df=pd.read_csv(filelist[0],header=1,parse_dates=['TMSTAMP'],index_col=0)

# remove the unzipped data
os.chdir(wd)
shutil.rmtree(PathUnZip)

# prepare xarray with metadata and write the netcdf
xr_ESMAP=df.to_xarray()
xr_ESMAP.attrs['Network']='ESMAP'
for xx in dictmeta:
    xr_ESMAP.attrs[xx]=dictmeta[xx]
xr_ESMAP.to_netcdf(pathOUT+"ESMAP_{}.nc".format(dictmeta['Site Name']))
