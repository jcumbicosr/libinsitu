# Introduction

This repository holds python code/tools to transform in-situ irradiation data to NetCDF and load / manipulate 
the result files locally or other the OpenDAP protocol.

# Installation 

This code is available as a PIP package :

    pip install libinsitu

The pip setup provides access to each script in `./bin/` as a `ins-<script>`  command

# Structure 

* **bin** : This folder contain CLI utils. The main ones are : 
  * **transform.py** (ins-transform): Transform raw in situ data files to NetCDF
  * **dump.py** (ins-dump) : Extract / filter data from NetCDF (local or OpenDAP) to CSV
  * **ls.py** (ins-ls): Explore the content of a TDS (Thredds) catalog.
  * ...
  
* **libinsitu** : Main files of the library
  * **res** : Resource files
    * base.cdl : Base CDL 
    * **station-info** : Meta data for each network
      * **[network].csv**
  
  * **cli** : Code for CLI entry points
  * **test** : Test suite
  * **handlers** : Data readers for each network

# Manual

## CLI 

Documentation of the main scripts in `./bin`. Each script is made available by pip as `ins-<script>` command

### transform.py (ins-transform)

Transforms raw input files into NetCDF output file (or update it), following the CF convention.

#### Usage 

    ins-transform. [-h] --network {BSRN,enerMENA,ABOM,SAURAN} --station-id <SID> [--incremental]
                        [--strict-resolution] [--check] [--status-folder <folder>]
                        <out.nc> <file|dir> [<file|dir> ...]

    positional arguments:
      <out.nc>              Output file
      <file|dir>            Input files or folders
    
    optional arguments:
      -h, --help            show this help message and exit
      --network {BSRN,enerMENA,ABOM,SAURAN}, -n {BSRN,enerMENA,ABOM,SAURAN}
                            Network name
      --station-id <SID>, -s <SID>
                            Station ID
      --incremental, -i     Incremental mode, skipping input files having a '.done' status file
      --strict-resolution, -sr
                            Skip chunks having a different resolution
      --check, -c           Check potential override of data
      --status-folder <folder>, -f <folder> Separate folder for .done/.err files

#### Example 

    > ins-transform -n BSRN -s ENA  -i  ENA.nc data/ena/

The resulting NetCDF file will be created following [the CDL schema](./libinsitu/res/base.cdl).
The Network and station ID should be described in [networks.csv](./libinsitu/res/networks.csv) 
and the corresponding [station-info/{network}.csv](libinsitu/res/station-info).


### dump.py [ins-dump]

Query / filter in-situ data from local or remote (over OpenDap) NetCDF files.

#### Usage

    ins-dump [-h] [--type {csv,text}] [--skip-na]
                   [--filter '<time> or <from_time>~<to-time>, with any sub part of 'YYYY-mm-ddTHH:MM:SS']
                   [--cols <col1>,<col2> ..] [--user USER] [--password PASSWORD] [--steps STEPS]
                   [--chunk_size CHUNK_SIZE]
                   <file.nc> or <url.nc>

    positional arguments:
      <file.nc> or <url.nc> Input file or URL
    
    optional arguments:
      -h, --help            show this help message and exit
      --type {csv,text}, -t {csv,text} 
                            Output type
      --skip-na, -s         Skip lines with only NA values
      --filter, -f '<time> or <from_time>~<to-time>, with any sub part of 'YYYY-mm-ddTHH:MM:SS' 
                            Time filter
      --cols, -c <col1>,<col2> ..
                            Selection of columns. All by default
      --user, -u USER  User login (or TDS_USER env var), for URL
      --password, -p PASSWORD
                            User password (or TDS_PASS env var), for URL
      --steps, -st STEPS
                            Downsampling (default = 1 : no downsampling)
      --chunk_size, -cs CHUNK_SIZE
                            Size of chunks (5000 by default)

#### Example 

Extract GHI data from XIA station, for january 2005, over OpenDAP :

    > export TDS_USER=<user> 
    > export TDS_PASS=<pass>
    > ins-dump http://tds.webservice-energy.org/thredds/dodsC/bsrn-stations/BSRN-XIA.nc -c GHI -s --filter 2005-01 -t csv


### ls.py [ins-ls]

Lists contents of a remote TDS (Thredds) server.

#### Usage 

    ins-ls [-h] [--user USER] [--password PASSWORD] <http://host/catalog.xml>
    
    positional arguments:
      <http://host/catalog.xml> Start URL (catalog.xml)
    
    optional arguments:
      -h, --help            show this help message and exit
      --user USER, -u USER  User login (or TDS_USER env var)
      --password PASSWORD, -p PASSWORD
                            User password (or TDS_PASS env var)

#### Example 

List all in-situ networks

    > ins-ls http://tds.webservice-energy.org/thredds/in-situ.xml

## Python API

This section documents the main functions of the library.

### nc2df(...)

Load a NetCDF in-situ file (or part of it) into a panda Dataframe, with time as index.

**module** : ```libinsitu.common```

#### Signature

    nc2df(
          ncfile : Union[Dataset, str],
          start_time: Union[datetime, datetime64]=None, end_time:Union[datetime, datetime64]=None,
          drop_duplicates=True,
          skip_na=False,
          vars=None,
          user=None,
          password=None,
          chunked=False,
          chunk_size=CHUNK_SIZE,
          steps=1)
    

* **ncfile**: NetCDF Dataset or filename, or URL
* **drop_duplicates**: If true (default), duplicate rows with same time are droppped
* **skip_na** : If True, drop rows containing only nan values
* **start_time**: Start time (first one by default) : Datetime or datetime64 
* **end_time**: End time (last one by default) : Datetile or datetime64 
* **vars**: List of columns names to  convert (all by default)
* **user**: Optional login for URL
* **password**: Optional password for URL
* **chunk_size** : Size of chunks for chunked data
* **steps** Downsampling (1 by default)


#### Example 

```python 
from libinsitu.common import nc2df

df = nc2df("data/station.nc")
```

### fetch_catalog(...)

Feth and parse XML catalog from a TDS (Thredds) server.

**module** : ```libinsitu.catalog```

#### Signature 

    fetch_catalog(url, session, recursive=True)

* **url** : URL of catalog.xml
* **session** : HTTP session (possibily with user/password)
* **recursive** : Fetch sub catalogs ?

#### Example

```python
session = Session()
session.auth = ("user", "password")
catalog = fetch_catalog(args.url, session, recursive=False)
```

## Adding  a new Network

To support a new Network, one should :
- Add a station info CSV file in [res/station-info/{network}.csv](./libinsitu/res/station-info) 
- Add an implementation in [libinsitu/handlers/<network>.py](./libinsitu/handlers) and register it in `libinsitu/handlers/__init_.py`
  
The handler should extend the method `read_chunk(filename)` from the abstract class [InSituHandler](./libinsitu/handlers/base_handler.py) : 
It should take a filename as input and return a *panda* Dataframe with the following (optional) columns :

| Name         | Type     | Unit           | Role                         |
|--------------|----------|----------------|------------------------------|
| Time (index) | Datetime | UTC time       | Time                         |
| GHI          | float    | W.m^-2         | Global Horizontal Irradiance |
| DHI          | float    | W.m^-2         | Diffuse radiation            |
| DNI          | float    | W.m^-2         | Direct radiation             |
| T2           | float    | K              | Temperature                  |
| RH           | float    | ratio: 0.0-1.0 | Relative humidity            |
| P            | float    | Pa             | Pressure                     |


## CDL

Each new NetCDF file is created using the CDL template [res/cdl/base.cdl](./libinsitu/res/base.cdl).
It contains placeholders that are replaced by the values found in the corresponding station info file in `libinsitu/res/station-info/{network}.csv`


