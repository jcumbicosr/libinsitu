# ins-cat

```{argparse}
---
module: libinsitu.cli.cat
func: parser
prog: ins-cat
---
```

## Examples

### Show data from remote URL

The following command shows one year of data from a remote openDAP url, with metadata in header (-hd) and skipping NaN rows (-s) 

```sh
> ins-cat -s -hd -f 2020-01~2021-01  http://tds.webservice-energy.org/thredds/dodsC/nrelmidc-stations/NREL_MIDC-BMS.nc
```

Output :
```
# id = NREL_MIDC-BMS
# title = Timeseries of Measurement and Instrumentation Data Center (MIDC) (NREL_MIDC). Station : NREL Solar Radiation Research Laboratory - Baseline Measurement System
# summary = Archive of solar radiation networks worldwide provided by the Webservice-Energy initiative supported by MINES Paris PSL. Files are provided as NetCDF file format with the support of a Thredds Data Server.
# keywords = meteorology, station, time, Earth Science > Atmosphere > Atmospheric Radiation > Incoming Solar Radiation, Earth Science > Atmosphere > Atmospheric Temperature > Surface Temperature > Air Temperature, Earth Science > Atmosphere > Atmospheric Pressure > Sea Level Pressure
# keywords_vocabulary = GCMD Science Keywords
# keywords_vocabulary_url = https://gcmd.earthdata.nasa.gov/static/kms/
# record = Basic measurements (global irradiance, direct irradiance, diffuse irradiance, air temperature, relative humidity, pressure)
# featureType = timeSeries
# cdm_data_type = timeSeries
# product_version = libinsitu 1.4.dev20+gb630aa0
# [...]
                    BNI   RH    T2    WS    GHI   DHI  
2020-01-01 07:00:00   1.1 0.323 280.4  6.45  -0.9  -0.8
2020-01-01 07:01:00   1.2 0.324 280.4  6.52  -0.9  -0.8
2020-01-01 07:02:00   1.0 0.325 280.4  5.65  -0.9  -0.8
2020-01-01 07:03:00   0.7 0.319 280.4  5.67  -0.9  -0.8
2020-01-01 07:04:00   0.7 0.317 280.5  5.31  -0.9  -0.8
2020-01-01 07:05:00   0.6 0.324 280.4  5.58  -0.9  -0.8
2020-01-01 07:06:00   0.5 0.322 280.4  6.40  -0.9  -0.7
...

```

### Export data to CSV 

The following command exports only GHI, BNI and DHI columns (-c) in CSV format (-t), skipping empty rows (-s)

```sh
> ins-cat -o BMS.csv -t csv -c GHI,DHI,BNI -s -f 2020-01~2021-01 NREL_MIDC-BMS.nc
```

Result file :
```
time,BNI,GHI,DHI
2020-01-01 07:00:00,1.0625,-0.9375,-0.8125
2020-01-01 07:01:00,1.1875,-0.9375,-0.8125
2020-01-01 07:02:00,1.0,-0.9375,-0.8125
2020-01-01 07:03:00,0.6875,-0.9375,-0.75
2020-01-01 07:04:00,0.6875,-0.9375,-0.75
2020-01-01 07:05:00,0.5625,-0.9375,-0.75
2020-01-01 07:06:00,0.5,-0.9375,-0.6875
2020-01-01 07:07:00,0.625,-0.875,-0.75
...
```

### Compute statistics 

The following command processes statistics on data and Qc flags and shows the result.
```sh
> ins-cat --stats -f 2020-01~2021-01 NREL_MIDC-BMS.nc
```


Output :
```
┏━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┓
┃ column ┃ count  ┃ min      ┃ max    ┃ mean    ┃
┡━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━┩
│ BNI    │ 611580 │ -58.438  │ 1078.8 │ 237.2   │
│ RH     │ 611580 │ 0.041992 │ 1.001  │ 0.41612 │
│ T2     │ 611548 │ 249.94   │ 309.5  │ 283.35  │
│ WS     │ 611580 │ 0        │ 17.711 │ 1.9873  │
│ GHI    │ 611580 │ -4.8125  │ 1438.3 │ 188.85  │
│ DHI    │ 611580 │ -4.8125  │ 833.25 │ 62.038  │
└────────┴────────┴──────────┴────────┴─────────┘
┏━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━┓
┃ QC flag        ┃ fail ┃ %    ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━┩
│ T1C_ppl_GHI    │ 0    │ 0.00 │
│ T1C_erl_GHI    │ 78   │ 0.01 │
│ T1C_ppl_DIF    │ 12   │ 0.00 │
│ T1C_erl_DIF    │ 193  │ 0.03 │
│ T1C_ppl_DNI    │ 2372 │ 0.39 │
│ T1C_erl_DNI    │ 7806 │ 1.28 │
│ T2C_bsrn_kt    │ 870  │ 0.14 │
│ T2C_seri_kn_kt │ 1129 │ 0.18 │
│ T2C_seri_k_kt  │ 5764 │ 0.94 │
│ T3C_bsrn_3cmp  │ 2321 │ 0.38 │
│ tracker_off    │ 206  │ 0.03 │
└────────────────┴──────┴──────┘
```

### Show QC flags

The following command shows QC flags as bitmaps (-qf masks)
```sh
> ins-cat -qf masks -f 2020-01~2021-02 NREL_MIDC-BMS.nc
```

Output :
```
                      BNI   RH    T2    WS    GHI   DHI   QC[T1C_ppl_GHI:a;T1C_erl_GHI:b;T1C_ppl_DIF:c;T1C_erl_DIF:d;T1C_ppl_DNI:e;T1C_erl_DNI:f;T2C_bsrn_kt:g;T2C_seri_kn_kt:h;T2C_seri_k_kt:i;T3C_bsrn_3cmp:j;track
er_off:k]
...
2020-02-04 18:46:00    6.9 0.916 266.6  0.83 454.7 443.3  ..........k
2020-02-04 18:47:00   13.5 0.919 266.6  0.96 504.6 471.9  ...........
2020-02-04 18:48:00   13.6 0.922 266.8  0.94 528.0 496.4  ...........
2020-02-04 18:49:00   33.4 0.921 266.9  0.80 652.8 549.4  ...d.....j.
2020-02-04 18:50:00   63.2 0.932 267.1  0.72 834.9 611.5  ...d.....j.
2020-02-04 18:51:00   81.7 0.944 267.6  0.95 956.6 668.2  .b.d.....j.
2020-02-04 18:52:00   59.6 0.955 268.0  0.96 885.0 696.6  .b.d.....j.
2020-02-04 18:53:00   41.1 0.961 268.4  0.81 771.9 661.8  ...d.....j.
2020-02-04 18:54:00   26.4 0.962 268.8  0.79 628.2 581.8  ...d.......
2020-02-04 18:55:00    9.6 0.953 269.0  1.33 453.4 461.9  ..........k
...
...
```

The following command exports QC flags as separate columns (-qf expand)

```sh
> ins-cat -o BMS.csv -c GHI,DHI,BNI -t csv -qf expand -f 2020-01~2021-02 NREL_MIDC-BMS.nc
```

Result file :
```
time,BNI,GHI,DHI,QC.T1C_ppl_GHI,QC.T1C_erl_GHI,QC.T1C_ppl_DIF,QC.T1C_erl_DIF,QC.T1C_ppl_DNI,QC.T1C_erl_DNI,QC.T2C_bsrn_kt,QC.T2C_seri_kn_kt,QC.T2C_seri_k_kt,QC.T3C_bsrn_3cmp,QC.tracker_off
[...]
2020-01-01 07:00:00,1.0625,-0.9375,-0.8125,0,0,0,0,0,0,0,0,0,0,0
2020-01-01 07:01:00,1.1875,-0.9375,-0.8125,0,0,0,0,0,0,0,0,0,0,0
2020-01-01 07:02:00,1.0,-0.9375,-0.8125,0,0,0,0,0,0,0,0,0,0,0
2020-01-01 07:03:00,0.6875,-0.9375,-0.75,0,0,0,0,0,0,0,0,0,0,0
2020-01-01 07:04:00,0.6875,-0.9375,-0.75,0,0,0,0,0,0,0,0,0,0,0
2020-01-01 07:05:00,0.5625,-0.9375,-0.75,0,0,0,0,0,0,0,0,0,0,0
2020-01-01 07:06:00,0.5,-0.9375,-0.6875,0,0,0,0,0,0,0,0,0,0,0
2020-01-01 07:07:00,0.625,-0.875,-0.75,0,0,0,0,0,0,0,0,0,0,0
2020-01-01 07:08:00,0.4375,-0.875,-0.6875,0,0,0,0,0,0,0,0,0,0,0
2020-01-01 07:09:00,0.375,-0.875,-0.6875,0,0,0,0,0,0,0,0,0,0,0
2020-01-01 07:10:00,0.375,-0.9375,-0.6875,0,0,0,0,0,0,0,0,0,0,0
2020-01-01 07:11:00,0.375,-0.9375,-0.6875,0,0,0,0,0,0,0,0,0,0,0
2020-01-01 07:12:00,0.6875,-0.9375,-0.75,0,0,0,0,0,0,0,0,0,0,0
2020-01-01 07:13:00,0.375,-0.9375,-0.75,0,0,0,0,0,0,0,0,0,0,0
2020-01-01 07:14:00,0.25,-0.9375,-0.75,0,0,0,0,0,0,0,0,0,0,0
2020-01-01 07:15:00,0.5625,-0.9375,-0.8125,0,0,0,0,0,0,0,0,0,0,0
```

### Filter data on QC flags

You can filter out rows with QC flags set to 1 (=failing Qc test).

The following command skips rows having any QC flag set to 1 :

```sh
> ins-cat -sq true NREL_MIDC-BMS.nc
```

The following command skips any row having the flags `tracker_off` or `T1C_erl_DNI` set to one :

```sh
> ins-cat -sq tracker_off,T1C_erl_DNI NREL_MIDC-BMS.nc
```

The following command skips any row having any flags but `tracker_off` set to one (it ignores `tracker_off`) :

```sh
> ins-cat -sq '!tracker_off' NREL_MIDC-BMS.nc
```