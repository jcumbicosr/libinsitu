# -*- coding: utf-8 -*-
"""
Created on Thu Sep  8 12:59:01 2022

@author: y-m.saint-drenan
"""
import os
import pandas as pd
import copy
import numpy as np

listMeas=['cm21_global_','ch1_direct_']
listStation={'chiba':{\
                      'TZ':9,\
                      'location':'Fukue Jima',\
                      'latitude':35.63,\
                      'longitude':140.10,\
                      'operator':'CEReS, Chiba University'},\
             'fukue':{\
                      'TZ':9,\
                      'location':'Fukue Jima',\
                      'latitude':32.75,\
                      'longitude':128.68,\
                      'operator':'CEReS, Chiba University'},\
             'miyako':{\
                      'TZ':9,\
                      'location':'Miyako Jima',\
                      'latitude':24.737,\
                      'longitude':125.327,\
                      'operator':'CEReS, Chiba University'},\
             'phimai':{\
                      'TZ':7,\
                      'location':'Phimai',\
                      'latitude':15.184,\
                      'longitude':102.565,\
                      'operator':'CEReS, Chiba University'},\
             'sendai':{\
                      'TZ':9,\
                      'location':'Sendai',\
                      'latitude':38.258,\
                      'longitude':140.837,\
                      'operator':'CEReS, Chiba University'},\
             'seoul':{\
                      'TZ':9,\
                      'location':'Seoul',\
                      'latitude':37.460,\
                      'longitude':126.949,\
                      'operator':'CEReS, Chiba University'}}

pathIN='//mnt/v1//IN_SITU_data//RawData//SKYNET//'
pathOUT='./'

ld0=os.listdir(pathIN)

for iStat,Stat in enumerate(listStation):
    
    print(Stat)
    
    for iMeas,Meas in enumerate(listMeas):
        
        ld=[x for x in ld0 if Stat  in x if listMeas[iMeas] in x]
        
        for ific,fic in enumerate(ld):
            
            yyyy=int(fic[-12:-8])
            print(fic,yyyy)
            
            df = pd.read_csv(pathIN+fic,sep=' ',compression='zip',header=15)
            df['Year']=yyyy
            df['datetime'] = pd.to_datetime(df[['Year', 'Month', 'Day','Hour']])-np.timedelta64(listStation[Stat]['TZ']*60*60,'s')
            df2=df[['datetime','Irradiance(W/m2)']]
            
            df3_cnt=df2.groupby([df2.datetime.dt.floor('min')]).count()
            df3_avg=df2.groupby([df2.datetime.dt.floor('min')]).mean()
            df3=df3_avg[df3_cnt.datetime.values>=1]
            
            if ific==0:
                df_1C=copy.deepcopy(df3)
            else:
                df_1C=pd.concat([df_1C,df3])
        
        if iMeas==0:
            df_GHI=copy.deepcopy(df_1C)
            df_GHI=df_GHI.rename(columns = {'Irradiance(W/m2)':'GHI'})
        else:
            df_DNI=copy.deepcopy(df_1C)
            df_DNI=df_DNI.rename(columns = {'Irradiance(W/m2)':'DNI'})
        
    df_solar=df_GHI.join(df_DNI)
    xr_solar=df_solar.to_xarray()
    xr_solar.attrs['location']=listStation[Stat]['location']
    xr_solar.attrs['operator']=listStation[Stat]['operator']
    xr_solar.attrs['latitude']=listStation[Stat]['latitude']
    xr_solar.attrs['longitude']=listStation[Stat]['longitude']
    xr_solar.attrs['TZ']=listStation[Stat]['TZ']
    
    xr_solar.to_netcdf(pathOUT+"Skynet_{}.nc".format(Stat))