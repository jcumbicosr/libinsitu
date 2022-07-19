# Data format convention for in situ measurements of solar irradiance

This document is a proposed convention for the formatting and distribution of in situ solar radiation measurement data. 
The goal is to apply best practices for standardizing data and improve interoperability. 
This allows to develop generic tools such as vizualization, QC, statistics, ... 

This convention is implemented in the python library [**libinsitu**](../README.md), which provides : 
* A workflow for transforming in situ measurements from various networks into standardized datasets
* Python functions and command line (CLI) tools to explore and extract data from files following this convention

This libraries embeds a [Common Data Langage (CDL) template](../libinsitu/res/base.cdl), describing a NetCDF file format, 
filled at runtime with metadata gathered for several [networks](../libinsitu/res/networks.csv) and [their stations](../libinsitu/res/station-info). 

# File format 

We propose to format the data into [**NetCDF** files](https://www.unidata.ucar.edu/software/netcdf/).

**NetCDF** is a widespread file format for numerical data. 
It has several benefits :
- **Compact** : NetCDF is very efficient for storing large amount of data. It supports lossless and lossy compression.
- **Well supported** : Most languages and tools (Python, R, Matlab, ...) have libraries for reading and writing NetCDF files.
- **Self descriptive** : *NetCDF* stores metadata to describe the data (bound, units, ...) and the context (station caracteristics).

The present convention is based on two other conventions :
* [CF conventions](https://cfconventions.org/) & [Standard names](https://cfconventions.org/Data/cf-standard-names/79/build/cf-standard-name-table.html): Convention of meta data from Climate and Forecast community.
* [Attribute Convention for Data Discovery](https://wiki.esipfed.org/Attribute_Convention_for_Data_Discovery_1-3)

We advise to use version 4 of NetCDF and to activate compression. 

# Data granularity 

We recommend to distribute one file per station of measurements. 

Providers can split the data into yearly or monthly subsets but should also provide aggregated datasets for easier requesting / subsetting. 

# Dimensions

Each file should have only two dimensions :
- Unlimited dimension for time, named **time**
- A fixed dimension of 20 or more, for the station name, named freely.


# Variables

We propose to include a subset of [standard CF variables](https://cfconventions.org/Data/cf-standard-names/79/build/cf-standard-name-table.html).

We suggest names for these variables but we only enforce :
* Their **standard_name** attribute, as per CF conventions
* Their units

## Time

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

## Station name and coordinates

Following the CF conventions, some station metadata are stored as separate variables :
* The name of the station, as a string of chars, along its dedicated dimension (number of characters) 
* The coordinates of the station should be provided as three separate float variables with no dimensions (single point)

| Name         | Standard name | Unit |
|--------------|---------------|---|
| station_name | platform_name       |               |
| latitude     | latitude      | degrees_north |
| longitude    | longitude     | degrees_east |
| elevation    |   height_above_mean_sea_level | m |

Here is the corresponding CDL :

```
char station_name(station_name) ;
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

## CRS

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

## Data variables

Data variables should be one dimensional along the **time** axis. Their type should be *float* or *double*.

They should declare the following CF attributes :
* **standard_name** (mandatory) : Used to identify them
* **units** (mandatory)  : Unit
* **grid_mapping**  (mandatory)  : Set to "crs" defined above
* **long name** (optional) : for display
* **valid_min** (optional): Float attribute value for expected minimum (used for QC)
* **valid_max** (optional): Float attribute value for expected maximum (used for QC)

We propose to include the following subset of [CF data variables](https://cfconventions.org/Data/cf-standard-names/79/build/cf-standard-name-table.html), 
depending of their availability.

The variable names is a suggestion. The standard name and units should be respected.

| Name | standard_name                      | unit        |
|------|------------------------------------|-------------|
| GHI  | surface_downwelling_shortwave_flux_in_air | W m-2       |
| DHI  | surface_diffuse_downwelling_shortwave_flux_in_air | W m-2       |
| BNI  | direct_downwelling_shortwave_flux_in_air | W m-2       |
| T2   | air_temperature                    | K           |
| RH   | relative_humidity                  | "1" (ratio) |
| P     |  air_pressure                                  | Pa            |
| WS   | wind_speed                         | m s-1            |
| WD   | wind_direction                     | degrees                 |

This translates into the following DSL :

```
float GHI(time) ;
    GHI:long_name = "Global Horizontal Irradiance" ;
    GHI:standard_name = "surface_downwelling_shortwave_flux_in_air" ;
    GHI:abbreviation = "SWD" ;
    GHI:units = "W m-2" ;
    GHI:valid_min=0.0 ;
    GHI:valid_max=3000 ;
    GHI:grid_mapping = "crs" ;
    // GHI:least_significant_digit=1;
    // GHI:significant_digits=4;

float DHI(time) ;
    DHI:long_name = "Diffuse horizontal radiation" ;
    DHI:standard_name = "surface_diffuse_downwelling_shortwave_flux_in_air" ;
    DHI:abbreviation = "DHI" ;
    DHI:units = "W m-2" ;
    DHI:valid_min=0.0 ;
    DHI:valid_max=3000 ;
    DHI:grid_mapping = "crs" ;
    // DHI:least_significant_digit=1;
    // DHI:significant_digits=4;

float BNI(time) ;
    BNI:long_name = "Beam (or direct) normal radiation" ;
    BNI:standard_name = "direct_downwelling_shortwave_flux_in_air" ;
    BNI:abbreviation = "BNI" ;
    BNI:units = "W m-2" ;
    BNI:valid_min=0.0 ;
    BNI:valid_max=3000 ;
    BNI:grid_mapping = "crs" ;

float T2(time) ;
    T2:long_name = "Air temperature at 2 m height" ;
    T2:standard_name = "air_temperature" ;
    T2:abbreviation = "T2" ;
    T2:units = "K" ;
    T2:valid_min=123.0 ;
    T2:valid_max=372.9 ;
    T2:grid_mapping = "crs" ;

float RH(time) ;

    RH:long_name = "Relative humidity" ;
    RH:standard_name = "relative_humidity" ;
    RH:abbreviation = "RH" ;
    RH:units = "1" ;
    RH:valid_min=0.0 ;
    RH:valid_max=1.0 ;
    RH:grid_mapping = "crs" ;

float WS(time) ;

    WS:long_name = "Wind speed" ;
    WS:standard_name = "wind_speed" ;
    WS:abbreviation = "windspd" ;
    WS:units = "m s-1" ;
    WS:valid_min=0.0;
    WS:grid_mapping = "crs" ;

float WD(time) ;

    WD:long_name = "Wind direction, clockwise from north" ;
    WD:standard_name = "wind_direction" ;
    WD:abbreviation = "winddir" ;
    WD:units = "degrees";
    WD:valid_min=0.0;
    WD:valid_max=360.0;
    WD:grid_mapping = "crs" ;

float P(time) ;
    P:parameter = "Station pressure" ;
    P:long_name = "air pressure at station height" ;
    P:standard_name = "air_pressure" ;

    P:units = "Pa" ;
    P:valid_min=0.0 ;
    P:valid_max=120000.0;
    P:grid_mapping = "crs";

```


# Global attributes 

Here, we propose a list of recommended global metadata providing additional information of the data and the station.

TODO

# Distribution of files

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


