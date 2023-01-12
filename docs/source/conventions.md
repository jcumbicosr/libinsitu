# NetCDF Conventions

This document is a proposed convention for the formatting and distribution of in situ solar radiation measurement data. 
The goal is to apply best practices for standardizing data and improve interoperability. 
This allows to develop generic tools such as vizualization, QC, statistics, ... 

It should be considered as a **DRAFT**, [open for discussions](https://groupes.minesparis.psl.eu/wws/info/solar-insitu).

This convention is implemented `libinsitu` which provides Python and CLI tools to :  
* Transform in situ measurements from various networks into standardized datasets
* Explore and extract data from files following this convention
* Apply quality checks on NetCDF files and embed resulting flags 

*libinsitu* embeds a {gitref}`Common Data Langage (CDL) template <libinsitu/res/base.cdl>`, describing a NetCDF file format, 
filled at runtime with metadata gathered for several {gitref}`networks <libinsitu/res/networks.csv>` and {gitref}`their stations <libinsitu/res/station-info>`.



---
## File format 

We propose to format the data into [**NetCDF** files](https://www.unidata.ucar.edu/software/netcdf/).

**NetCDF** is a widespread file format for numerical data. 
It has several benefits :
- **Compact** : NetCDF is very efficient for storing large amount of data. It supports lossless and lossy compression.
- **Well supported** : Most languages and tools (Python, R, Matlab, ...) have libraries for reading and writing NetCDF files.
- **Self descriptive** : *NetCDF* stores metadata to describe the data (bound, units, ...) and the context (station caracteristics).

The present convention is based on two other conventions :
* [CF conventions](https://cfconventions.org/) & [Standard names](https://cfconventions.org/Data/cf-standard-names/79/build/cf-standard-name-table.html): Convention of meta data from Climate and Forecast community.
* [Attribute Convention for Data Discovery](https://wiki.esipfed.org/Attribute_Convention_for_Data_Discovery_1-3)

We advise to use version 4 or above of NetCDF.

---

## Data granularity 

We recommend to distribute one file per station of measurements. 

Providers can split the data into yearly or monthly subsets but should also provide aggregated datasets for easier requesting / subsetting.

---
## Compression  

We recommend to activate lossless [zlib compression](https://unidata.github.io/netcdf4-python/#efficient-compression-of-netcdf-variables).

Optionally we recommend of use lossly compression by truncating data values to proper significant digits. 
For this purpose we use the attribute **least_significant_digit** supported by the Python driver of **NetCDF**.  

---
## Dimensions

Each file should have only one dimension  :
- Unlimited dimension for time, named **time**

---
## Variables

We propose to include a subset of [standard CF variables](https://cfconventions.org/Data/cf-standard-names/79/build/cf-standard-name-table.html).

We suggest names for these variables but we only enforce :
* Their **standard_name** attribute, as per CF conventions
* Their units

### Time

Each NetCDF file should have a single time variable, with *standard_name* **"time"**, along the **time** dimension. 
This time should be expressed as seconds since first january 1970. Hence, following the CF conventions, the units of 
this variable should be **"seconds since 1970-01-01T00:00:00"**. The data type of the time variable 
can be either *double* or *int* (preferred, more compact).

The time should be uniform :
- No hole or duplicate values from start to end
- Same regular time resolution for the whole time span, described with the global attribute **time_coverage_resolution**

The timezone should be in UTC. The specific local time zone can optionally be specified in the global attribute **local_time_zone**

Here is an example of a CDL of a Time variable :

```
int Time(time) ;
    Time:long_name = "Time of measurement" ;
    Time:standard_name = "time" ;
    Time:units = "seconds since 1970-01-01 00:00:00";
    Time:axis = "T" ;
    Time:calendar = "gregorian" ;
```

### Station name and coordinates

Following the CF conventions, some station metadata are stored as separate variables :
* The name of the station, as a string
* The coordinates of the station should be provided as three separate float variables with no dimensions (single point)

| Name         | Standard name | Unit |
|--------------|---------------|---|
| station_name | platform_name       |               |
| latitude     | latitude      | degrees_north |
| longitude    | longitude     | degrees_east |
| elevation    |   height_above_mean_sea_level | m |

Here is the corresponding CDL :

```
string station_name ;
      station_name:standard_name = "platform_name"
      station_name:long_name = "station name" ;
      station_name:cf_role = "timeseries_id" ;

float latitude ;
    latitude:long_name = "station latitude" ;
    latitude:standard_name = "latitude" ;
    latitude:units = "degrees_north" ;
    latitude:axis = "Y" ;

float longitude ;
    longitude:long_name = "station longitude" ;
    longitude:standard_name = "longitude" ;
    longitude:units = "degrees_east" ;
    longitude:axis = "X" ;

float elevation;
    elevation:long_name = "Elevation above mean seal level" ;
    elevation:standard_name = "height_above_mean_sea_level" ;
    elevation:units = "m" ;
    elevation:axis = "Z" ;
```

### CRS

An empty variable named **crs** should be created to store information about the coordinate system.
It should be referenced by any data varaible via the attribute **grid_mapping**.

```
double crs ;
    crs:grid_mapping_name = "latitude_longitude" ;
    crs:longitude_of_prime_meridian = "0.0" ;
    crs:semi_major_axis = "6378137.0" ;
    crs:inverse_flattening = "298.257223563" ;
    crs:epsg_code = "EPSG:4326";
```

### Data variables

Data variables should be one dimensional along the **time** axis. Their type should be *float* or *double*.

They should declare the following CF attributes :
* **standard_name** (mandatory) : Used to identify them.
* **units** (mandatory) : Unit. SI unit is preferred.
* **grid_mapping**  (mandatory) : Set to "crs" defined above.
* **long name** (optional) : Name used for display.
* **valid_min_, valid_max_** (optional) : Float attribute value for expected minimum and maximum (used for QC). 
  Note that we don't use directly the CF convention **valid_min, valid_max** here, since some drivers remove values outside of this range.
  We want to keep full control upon data here, and only use this meta data for flagging some values. 
* **least_significant_digit** (optional) : Number of significant digits. Used by *Python* driver at creation time for lossy compression.
* **_FillValue** : This is better to set an explicit fill value. We use **-999.0**, which is a common value. 

We propose to include the following subset of [CF data variables](https://cfconventions.org/Data/cf-standard-names/79/build/cf-standard-name-table.html), 
depending of their availability.

The variable names is a suggestion.
The standard name and units should be respected.
We propose to use SI units when possible.

| Name | standard_name                      | unit        |
|------|------------------------------------|-------------|
| GHI  | surface_downwelling_shortwave_flux_in_air | W m-2       |
| DHI  | surface_diffuse_downwelling_shortwave_flux_in_air | W m-2       |
| BNI  | direct_downwelling_shortwave_flux_in_air | W m-2       |
| T2   | air_temperature                    | K           |
| RH   | relative_humidity                  | "1" (ratio) |
| P    |  air_pressure                      | Pa          |
| WS   | wind_speed                         | m s-1       |
| WD   | wind_direction                     | degrees     |

This translates into the following CDL :

```
float GHI(time) ;
    GHI:long_name = "Global Horizontal Irradiance" ;
    GHI:standard_name = "surface_downwelling_shortwave_flux_in_air" ;
    GHI:abbreviation = "SWD" ;
    GHI:units = "W m-2" ;
    GHI:valid_min_=0.0 ;
    GHI:valid_max_=3000 ;
    GHI:grid_mapping = "crs" ;
    GHI:least_significant_digit = 1;
    GHI:_FillValue = -999.0;
    
float DHI(time) ;
    DHI:long_name = "Diffuse horizontal radiation" ;
    DHI:standard_name = "surface_diffuse_downwelling_shortwave_flux_in_air" ;
    DHI:abbreviation = "DHI" ;
    DHI:units = "W m-2" ;
    DHI:valid_min_=0.0 ;
    DHI:valid_max_=3000 ;
    DHI:grid_mapping = "crs" ;
    DHI:least_significant_digit = 1;
    DHI:_FillValue = -999.0;

float BNI(time) ;
    BNI:long_name = "Beam (or direct) normal radiation" ;
    BNI:standard_name = "direct_downwelling_shortwave_flux_in_air" ;
    BNI:abbreviation = "BNI" ;
    BNI:units = "W m-2" ;
    BNI:valid_min_=0.0 ;
    BNI:valid_max_=3000 ;
    BNI:grid_mapping = "crs" ;
    BNI:least_significant_digit = 1;
    BNI:_FillValue = -999.0;

float T2(time) ;
    T2:long_name = "Air temperature at 2 m height" ;
    T2:standard_name = "air_temperature" ;
    T2:abbreviation = "T2" ;
    T2:units = "K" ;
    T2:valid_min_=123.0 ;
    T2:valid_max_=372.9 ;
    T2:grid_mapping = "crs" ;
    T2:least_significant_digit = 1;
    T2:_FillValue = -999.0;

float RH(time) ;

    RH:long_name = "Relative humidity" ;
    RH:standard_name = "relative_humidity" ;
    RH:abbreviation = "RH" ;
    RH:units = "1" ;
    RH:valid_min_=0.0 ;
    RH:valid_max_=1.0 ;
    RH:grid_mapping = "crs" ;
    RH:least_significant_digit = 3;
    RH:_FillValue = -999.0;

float WS(time) ;

    WS:long_name = "Wind speed" ;
    WS:standard_name = "wind_speed" ;
    WS:abbreviation = "windspd" ;
    WS:units = "m s-1" ;
    WS:_valid_min_=0.0;
    WS:_valid_max_=100.0;
    WS:grid_mapping = "crs" ;
    WS:least_significant_digit = 2;
    WS:_FillValue = -999.0;

float WD(time) ;

    WD:long_name = "Wind direction, clockwise from north" ;
    WD:standard_name = "wind_direction" ;
    WD:abbreviation = "winddir" ;
    WD:units = "degrees";
    WD:_valid_min_=0.0;
    WD:_valid_max_=360.0;
    WD:grid_mapping = "crs" ;
    WD:least_significant_digit = 1;
    WD:_FillValue = -999.0;

float P(time) ;
    P:parameter = "Station pressure" ;
    P:long_name = "air pressure at station height" ;
    P:standard_name = "air_pressure" ;

    P:units = "Pa" ;
    P:valid_min_=0.0 ;
    P:valid_max_=120000.0;
    P:grid_mapping = "crs";
    P:least_significant_digit = 0;
    P:_FillValue = -999.0;

```


## Global attributes 

Here, we propose a list of recommended global metadata providing additional information of the data and the station.

We try to stick as much as possible to the existing CF and ACDD conventions.

Some of those attributes may seem redondant with the contents of some variables. 
They are useful anyway as it is simpler to fetch all global attributes than to dig into the values of the variables, espcecially for remote access (ODAP) 

### Main info

| Name                | Content                 | Example                                                                                                                                                                                                                                                                           |
|---------------------|-------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id                  | {NetWorkId}-{StationID} | "BSRN-CAP"                                                                                                                                                                                                                                                                        |
| title               | Title of the timeseries | "Timeseries of Baseline Surface Radiation Network (BSRN). Station : Cape Baranova"                                                                                                                                                                                                |
| summary             | Short description       | "Archive of solar radiation networks worldwide provided by the Webservice-Energy initiative supported by MINES Paris PSL. Files are provided as NetCDF file format with the support of a Thredds Data Server"                                                                     |
| keywords            | List of keywords        | "meteorology, station, time, Earth Science > Atmosphere > Atmospheric Radiation > Incoming Solar Radiation, Earth Science > Atmosphere > Atmospheric Temperature > Surface Temperature > Air Temperature, Earth Science > Atmosphere > Atmospheric Pressure > Sea Level Pressure" |
| keywords_vocabulary | "GCMD Science Keywords" |  "GCMD Science Keywords"                                                                                                                                                                                                                                                                     |
| featureType         | "timeSeries"            | "timeSeries"                                                                                                                                                                                                                                                                              |
| Conventions         | List of conventions     | "CF-1.9,ACDD-1.3"                                                                                                                                                                                                                                                                         |

### Publisher info

| Name                  |          Name of the publisher                     | Example                                                                                                                                    |
|-----------------------|-------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|
| publisher_name        | Content                       |   "Lionel MENARD, Raphael JOLIVET, Yves-Marie SAINT-DRENAN, Philippe BLANC"                                               |
| publisher_email       | Email of publisher            | "lionel.menard@mines-paristech.fr, raphael.jolivet@mines-paristech.fr, saint-drenan@mines-paristech.fr, philippe.blanc@mines-paristech.fr" |
| publisher_url         | URL of institution            | "https://www.oie.minesparis.psl.eu/"                                                                                                       |
| publisher_institution | Name of publisher institution | "Mines Paristech - PSL"                                                                                                                    |


### Creator info

Info on the creator of data.
It may or may not be the same as publisher

| Name        | Content                      | Example                                              |
|-------------|------------------------------|------------------------------------------------------|
| creator_name | Name of maintener of data / station | "Olga Sidorova (olsid@aari.ru)"                      |
| institution | Instituton of creator        | NOAA                                                 |
| creator_url | URL of Creator / Network     | https://bsrn.awi.de/                                 |
| references  | Academic references for data | "https://doi.org/10.5194/essd-10-1491-2018."         |
| license     | Link to license of data      | "https://bsrn.awi.de/data/conditions-of-data-release/" |


#### Station info

The station info are mappend into ACDD attributes.

| Name                  | Content                                       | Example                              |
|-----------------------|-----------------------------------------------|--------------------------------------|
| project               | Full Name of Network                          | "Baseline Surface Radiation Network" |
| platform              | Full Name of station                          | "Cape Baranova"                      |
| geospatial_lat_min    | latitude (float , not str)                    | 79.27                                |
| geospatial_lon_min    | longtitude (float , not str)                  | 101.75                               |
| geospatial_lat_max    | latitude (float , not str)                    | 79.27                                |
| geospatial_lon_max    | longtitude (float , not str)                  | 101.75                               |
| geospatial_bounds     | POINT({Station_Latitude} {Station_Longitude}) | "POINT(79.27 101.75)"                |
| geospatial_bounds_crs | Projection                                    | "EPSG:4326"                          |

### Time information

| Name                     | Content                                                     | Example               |
|--------------------------|-------------------------------------------------------------|-----------------------|
| time_coverage_start      | First timestamp of data (in ISO 8601 format)                | "2016-01-01T00:00:00" |
| time_coverage_end        | Last timestamp of data (in ISO 8601 format)                 | "2016-12-31T23:59:00" |
| time_coverage_resolution | Resolution in ISO 8601:2004 duration format : "P{minutes}M" | "P1M"                 |
| local_time_zone          | Local time zone offset                                      | "UTC+07:00"           |
| date_created             | Creation time                                               | "2021-01-01T00:00:00" |
| date_modified            | Modification time                                           | "2021-01-01T00:00:00" |

### Custom IN Situ metadata

The followig attributes are not part of CF or ACDD conventions. 

They are additional metadata recommended for this specific use case.

#### IDs

Unique Ids usefull for identifying network and station.


| Name           | Content                                                                | Example |
|----------------|------------------------------------------------------------------------|---------|
| network_id     | Short Id for network                                                   | BSRN    |
| station_id     | Short Id for station. Same as the content of **station_name** variable | CAP     |
| station_uid    | Numeric ID of the station, if any                                      | 102     |
| station_wmo_id | WMO ID of the station, if any                                          |         |

#### Surface 

Description of the surface around the station

| Name            | Content                                        | Example    |
|-----------------|------------------------------------------------|------------|
| surface_type    | rock, gress, concrete, cultivated, ...         | "concrete" |
| topography_type | flat, hilly, moutain valley, mountain top, ... |            |
| rural_urban     | "rural" or "urban"                             | "rural"    |

#### Station location

| Name            | Content                 | Example                  |
|-----------------|-------------------------|--------------------------|
| network_region  | Region of the network   | "Global"                 |
| station_country | Country of the station  | "France"                 |
| station_address | Address of the station  | "100, Erfurterweg (123)" |
| station_city    | City of the station     | "Carpentras"             |

#### Misc

| Name             | Content                                | Example  |
|------------------|----------------------------------------|----------|
| climate          | Climate at the station (KeoppenGeiger) | "EF"     |
| operation_status | 'active', 'inactive' or 'closed'         | "closed" |

## Distribution of files

We advise to distribute the NetCDF files with [THREDDS data server (TDS)](https://github.com/Unidata/tds). 

The server should be configured to provide at least the following services :
* **File server** : HTTP download
* **OpenDAP** : Remote data request

The files should be organized in a regular hierarchy and grouped by Network. We advise to serve one file per station and to group them by network :

* **NetworkA/**
  * **NetworkA-station1.nc**
  * **NetworkA-station2.nc**
  * ...

Alternatively, the data can by split into monthly or yearly NetCDF files. In that case, we advise to also serve aggregated data for easier requesting over OpenDAP :

* **NetworkA/**
  * **Station1/**
    * **station1-aggregaged.nc**
    * **2018/**
      * **station1-2018-01.nc**
      * **station1-2018-02.nc**
      * ...
    * **2019/**
    * ...


