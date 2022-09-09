# -*- coding: utf-8 -*-
"""
Created on Thu Sep  8 18:22:13 2022

@author: y-m.saint-drenan


"""
ListStations={'tng00001':{'name':'Wendlingen','latitude':48.667,'longitude':9.399,'altitude':276},
'tng00002':{'name':'Stuttgart','latitude':48.830,'longitude':9.196,'altitude':294},
'tng00003':{'name':'St. Leon-Rot','latitude':49.245,'longitude':8.641,'altitude':108},
'tng00004':{'name':'Ketsch','latitude':49.356,'longitude':8.532,'altitude':102},
'tng00005':{'name':'Freiburg','latitude':48.009,'longitude':7.835,'altitude':256},
'tng00006':{'name':'Mahlberg','latitude':48.280,'longitude':7.787,'altitude':170},
'tng00007':{'name':'Murr','latitude':48.968,'longitude':9.263,'altitude':212},
'tng00008':{'name':'Fünfstetten','latitude':48.837,'longitude':10.773,'altitude':504},
'tng00009':{'name':'Freudenstadt','latitude':48.459,'longitude':8.425,'altitude':669},
'tng00010':{'name':'Karlsruhe','latitude':49.008,'longitude':8.344,'altitude':115},
'tng00011':{'name':'Oberndorf','latitude':48.298,'longitude':8.552,'altitude':667},
'tng00012':{'name':'Ulm','latitude':48.422,'longitude':10.006,'altitude':552},
'tng00013':{'name':'Bad Rappenau','latitude':49.268,'longitude':9.059,'altitude':288},
'tng00014':{'name':'Offenburg','latitude':48.473,'longitude':7.939,'altitude':151},
'tng00015':{'name':'Grünstadt','latitude':49.562,'longitude':8.188,'altitude':157},
'tng00016':{'name':'Löffingen','latitude':47.885,'longitude':8.400,'altitude':745},
'tng00017':{'name':'Aitrach','latitude':47.927,'longitude':10.090,'altitude':601},
'tng00018':{'name':'Neusass','latitude':49.612,'longitude':9.350,'altitude':441},
'tng00019':{'name':'Tuttlingen','latitude':47.957,'longitude':8.780,'altitude':649},
'tng00020':{'name':'Hechingen','latitude':48.360,'longitude':8.966,'altitude':490},
'tng00021':{'name':'Leutkirch','latitude':47.836,'longitude':9.988,'altitude':648},
'tng00022':{'name':'Königsbronn','latitude':48.751,'longitude':10.169,'altitude':637},
'tng00023':{'name':'Lörrach','latitude':47.613,'longitude':7.655,'altitude':284},
'tng00024':{'name':'Ingoldingen','latitude':47.996,'longitude':9.699,'altitude':573},
'tng00025':{'name':'Eberbach','latitude':49.465,'longitude':8.987,'altitude':137},
'tng00026':{'name':'Zwiefaltendorf','latitude':48.207,'longitude':9.513,'altitude':523},
'tng00027':{'name':'Krautheim','latitude':49.396,'longitude':9.605,'altitude':382},
'tng00028':{'name':'Pforzheim','latitude':48.899,'longitude':8.746,'altitude':312},
'tng00029':{'name':'Weikersheim','latitude':49.457,'longitude':9.889,'altitude':370},
'tng00030':{'name':'Konstanz','latitude':47.674,'longitude':9.163,'altitude':402},
'tng00031':{'name':'Leibertingen','latitude':48.064,'longitude':9.068,'altitude':763},
'tng00032':{'name':'Crailsheim','latitude':49.132,'longitude':10.054,'altitude':416},
'tng00033':{'name':'Ravensburg','latitude':47.786,'longitude':9.608,'altitude':432},
'tng00034':{'name':'Herdwangen-Schönach','latitude':47.854,'longitude':9.137,'altitude':660},
'tng00035':{'name':'Schwäbisch Hall','latitude':49.117,'longitude':9.774,'altitude':399},
'tng00036':{'name':'Baden-Baden','latitude':48.787,'longitude':8.189,'altitude':127},
'tng00037':{'name':'Neubulach','latitude':48.649,'longitude':8.654,'altitude':621},
'tng00038':{'name':'Waldshut-Tiengen','latitude':47.624,'longitude':8.255,'altitude':345},
'tng00039':{'name':'Schwäbisch Gmünd','latitude':48.803,'longitude':9.800,'altitude':326},
'tng00040':{'name':'Berghülen','latitude':48.455,'longitude':9.778,'altitude':667}}
    

import os
import shutil
import copy
import pandas as pd
from zipfile import ZipFile

pathIN='V://IN_SITU_data//RawData//ISE_PVLive//'
pathOUT='.//'
wd=os.getcwd()

# Name of the station to extract
StatID='tng00040'

# list of the zip files 
ziplist=os.listdir(pathIN)

# for loop to collect the data of the station in each zip file
for izip,vzip in enumerate(ziplist):
    print(vzip)
    
    # unzip  an archive
    PathUnZip='tmp_unzipped_'+vzip.replace("-", "_").replace(".", "_")
    zipObj=ZipFile(pathIN+vzip, 'r')
    zipObj.extractall(PathUnZip)
    
    # move to the directory containing the data and read the data
    os.chdir(PathUnZip)
    dirlist=os.listdir('./')
    os.chdir(dirlist[0])
    filelist=os.listdir('./')
    filelist=[x for x in filelist if StatID in x]
    if len(filelist)>0:
        df=pd.read_csv(filelist[0],sep='\t',parse_dates=['datetime'],index_col=0)
        df=df[['Gg_pyr']]
        df=df.rename(columns = {'Gg_pyr':'GHI'})
    
    # remove the unzipped data
    os.chdir(wd)
    shutil.rmtree(PathUnZip)
    
    # concatenate the extracted data
    if izip==0:
        df_ISE_PVlive=copy.deepcopy(df)
    else:
        df_ISE_PVlive=pd.concat([df_ISE_PVlive,df])
        
# prepare xarray with metadata and write the netcdf
xr_ISE_PVlive=df_ISE_PVlive.to_xarray()
xr_ISE_PVlive.attrs['Station_ID']=StatID
xr_ISE_PVlive.attrs['operator']='Fraunhofer ISE (Germany)'
xr_ISE_PVlive.attrs['location']=ListStations[StatID]['name']
xr_ISE_PVlive.attrs['latitude']=ListStations[StatID]['latitude']
xr_ISE_PVlive.attrs['longitude']=ListStations[StatID]['longitude']
xr_ISE_PVlive.attrs['altitude']=ListStations[StatID]['altitude']
xr_ISE_PVlive.to_netcdf(pathOUT+"ISE_PVlive_{}.nc".format(StatID))
