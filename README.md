# Introduction

This repository holds python code/tools to manage in-situ data and transform them into NetCDF files.

# Structure 

* **bin** : Main entry points
  * process.py : Transform raw input files to NETCDF
  * cat.py : Extract data from NetCDF to CSV, JSON, ...  
  * main.sh : Bash script for processing whole Network
  * diff.py : Diff of two NetCDF files
  * diff.sh : Bash script for comparing output of whole networks
  * http_sync.py : Generic script for fetching / scrapping data from http URL patterns 


* **res** : Resource files
  * cdl/base.cdl : Base CDL 
  * **station-info** : Meta data for each network
    * **[network].csv**
    
* **src** 
    * **lib** : common code
    * **test** : test suites

# Usage

Usage for main entry points :

## _bin/process.py_ 

The main command in insitu-etl.py. It transforms a bunch of input files into netCDF.

    ./bin/process.py [-h] --network <NETWORK> --station_id <SID> [--incremental]
                     [--status-folder <folder>]
                     <out.nc> <file|dir> [<file|dir> ...]


**positional arguments**
  
 * <out.nc>              Output file
 * <file|dir>            Input files or folder

**options**

 * --network <NETWORK>, -n <NETWORK> Network name, **mandatory**
 * --station_id <SID>, -s <SID> Station ID, **mandatory**
 * --incremental, -i     Incremental mode, skipping input files having an associated `.done` status file
 * --status-folder <folder>, -f <folder> Use a separate folder for `.done`/`.err` files

# Examples 

    ./process.py -n BSRN -s ENA  -i  ENA.nc data/ena/

Takes all *.gz files in the folder `data/ena` and write them into ENA.nc.
The input files having a more recent `.done` will be skipped (incremental mode) 

# How to add new Network

To support a new Network you should :
- Add a station info CSV file in `res/station-info/{network}.csv` 
- Add an implementation in `lib/handlers/<network>.py` and register it in `lib/handlers/__init_.py`
  
The handler should extend the method `read_chunk(filename)` from the abstract class [InSituHandler](lib/handlers/base_handler.py) : 
It should take a filename as input and return a *panda* Dataframe with the following columns :


| Name | Type     | Unit           | Role                         |
|------|----------|----------------|------------------------------|
| Time | Datetime | UTC time       | Time                         |
| GHI  | float    | W.m^-2         | Global Horizontal Irradiance |
| DHI  | float    | W.m^-2         | Diffuse radiation            |
| DNI  | float    | W.m^-2         | Direct radiation             |
| T2   | float    | K              | Temperature                  |
| RH   | float    | ratio: 0.0-1.0 | Relative humidity            |
| P    | float    | Pa             | Pressure                     |



# CDL

Each new NetCDF file is created using the CDL template [res/cdl/base.cdl](res/cdl/base.cdl).
It contains placeholders that are replaced by the values found in the corresponding station info file in `res/station-info/{network}.csv`

# Comments NetworkDescription 

ID < 4 letters : ISE_PVLive & NREL_MIDC


