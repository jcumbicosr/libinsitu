# -*- coding: utf-8 -*-
"""
Created on Fri Sep  9 11:00:43 2022

@author: y-m.saint-drenan
"""
ListStations={
'94002':{'Name':'Portland DEQ, OR','abbrev':'P1'},
'94003':{'Name':'Milwaukie MES, OR','abbrev':'PL'},
'94005':{'Name':'Gladstone, OR','abbrev':'GL'},
'94007':{'Name':'Scoggins Creek, OR','abbrev':'SC'},
'94008':{'Name':'Forest Grove, OR','abbrev':'FG'},
'94019':{'Name':'Aprovecho, OR','abbrev':'AP'},
'94040':{'Name':'Ashland, OR','abbrev':'AS'},
'94101':{'Name':'Green River, WY','abbrev':'GR'},
'94102':{'Name':'Moab, UT','abbrev':'MO'},
'94145':{'Name':'Dillon, MT','abbrev':'DI'},
'94158':{'Name':'Cheney, WA','abbrev':'CY'},
'94166':{'Name':'Klamath Falls, OR','abbrev':'KF'},
'94167':{'Name':'Whitehorse Ranch, OR','abbrev':'WH'},
'94168':{'Name':'La Grande, OR','abbrev':'LG'},
'94169':{'Name':'Hermiston, OR','abbrev':'HE'},
'94170':{'Name':'Burns, OR','abbrev':'BU'},
'94171':{'Name':'Twin Falls (Kimberly), ID','abbrev':'TF'},
'94172':{'Name':'Picabo, ID','abbrev':'PI'},
'94173':{'Name':'Parma, ID','abbrev':'PA'},
'94174':{'Name':'Aberdeen, ID','abbrev':'AB'},
'94181':{'Name':'Coeur d Alene, ID','abbrev':'CD'},
'94182':{'Name':'Boise, ID','abbrev':'BO'},
'94185':{'Name':'Challis, ID','abbrev':'BO'},
'94249':{'Name':'Silver Lake, OR','abbrev':'SL'},
'94250':{'Name':'Klamath Falls, OR','abbrev':'KF'},
'94251':{'Name':'Christmas Valley, OR','abbrev':'CH'},
'94252':{'Name':'Madras, OR','abbrev':'MA'},
'94253':{'Name':'Corvallis, OR','abbrev':'CV'},
'94254':{'Name':'Willamette High School, Eugene, OR','abbrev':'WI'},
'94255':{'Name':'Eugene, OR','abbrev':'EU'},
'94256':{'Name':'Bend, OR','abbrev':'BE'},
'94257':{'Name':'Coos Bay, OR','abbrev':'CB'},
'94258':{'Name':'Portland, OR','abbrev':'PT'},
'94277':{'Name':'Hood River, OR','abbrev':'HR'},
'94278':{'Name':'West Hood River, OR','abbrev':'WR'},
'94279':{'Name':'Parkdale, OR','abbrev':'PD'}}

import os
import pandas as pd
import numpy as np
import copy

pathIN='V:\\IN_SITU_data\\RawData\\UniOregon\\'
pathOUT='.//'

# List the available stations
listFiles=os.listdir(pathIN)
listStat=list(set([xx[17:-11] for xx in listFiles]))

# rank of the station to read
iStation=0

# list the data available for the current station
listFiles=os.listdir(pathIN)
listFiles=[xx for xx in listFiles if listStat[iStation] in xx]

# for-loop on the different data corresponding to the station
for iFile,yyy in enumerate(listFiles):
    
    #read the archive
    df=pd.read_csv(pathIN+listFiles[iFile],sep='\t')
    col=df.columns
    StatNr=col[0]
    df_year=col[1]
    df=df.rename(columns = {col[0]:'doy',col[1]:'MilitaryTime'})
    col2=df.columns
    col2=[xx for xx in col2 if xx[0]!='0' ]
    df=df[col2]
    
    # decode the time format
    df_hours=(np.floor(df['MilitaryTime']/100)).astype(int)
    df_minutes=df['MilitaryTime']-df_hours*100
    doy_sec=df['doy'].values*24*60*60+df_hours*60*60+df_minutes*60
    df['time']=pd.to_datetime([np.datetime64(str(col[1])+'-01-01')+ np.timedelta64(x,'s') for x in doy_sec])
    df=df.set_index('time')
    df=df.drop(columns=['doy','MilitaryTime'])
    
    # Decode the name of the columns
    #http://solardat.uoregon.edu/DataElementNumbers.html
    col=df.columns
    DictIDs={'GHI':'100','DNI':'201','DIF':'300','PRES':'917',\
             'WD':'920','WS':'921','Ta':'930','Td':'931','RH':'933'}
    for prm in DictIDs:
        cnt=0
        for ii in range(10):
            ID='{}{}'.format(DictIDs[prm],ii)
            if ID in col:
                if cnt==0:
                    df=df.rename(columns = {ID:prm})
                else:
                    df=df.rename(columns = {ID:prm+'_'+str(cnt)})
                cnt+=1
                        
    
    # concatenate the extracted data
    if iFile==0:
        df_UniOregon=copy.deepcopy(df)
    else:
        df_UniOregon=pd.concat([df_UniOregon,df])


# compile the metadata
metadata={'StationID':listStat[iStation],'StationNr':StatNr,'Name':ListStations[str(StatNr)]['Name'],'Abbrev':ListStations[str(StatNr)]['abbrev']}

# prepare xarray with metadata and write the netcdf
xr_UniOregon=df_UniOregon.to_xarray()
xr_UniOregon.attrs['Network']='University of Oregon'
for xx in metadata:
    xr_UniOregon.attrs[xx]=metadata[xx]
xr_UniOregon.to_netcdf(pathOUT+"UniOregon_{}.nc".format(metadata['StationID']))
