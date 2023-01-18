1.3.1 :
* Removed support for plotly for now : dependencies were broken
* Embed current version in __version__ automatically
* Update Qc within "transform" flow

1.3 :
* Fixed bug splitting meta data with "," to lists
* Added CLI utils ins-update-meta, to only update metadata for NetCDF files without recomputing data
* Fixed CDL to be better compliant with cf conventions
* Extracted visual QC in a proper Python function

1.2 :
* Fixed bug in date filtering of nc2df with start date different from origin date
* Migrated to new conventions
* Added QC flags and ins-qc (cli) to generate visual QC images and add flags in NetCDF files
* Added handler for IEA_PVPS, ESMAP, SKYNET, ISE_PVLIVE
* Added CLI ins-info to dump CSV meta data
* Added stats and header to cat.py (formely dump.py)

1.1 :
* Separate start date from date-origin
* Set date origin to a fixed value : 1970-01-01 UTC

1.0 :
* First release on PyPI