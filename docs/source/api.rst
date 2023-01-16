Python API
==========

The usage of Python API is demonstrated in an example Notebook_

netcdf_to_dataframe
-------------------

This function queries a local or remote (via OpenDAP) NetCDF file and transform it into pandas DataFrame.

.. autofunction:: libinsitu.common.netcdf_to_dataframe

visual_qc
---------

This function applies QC checks on an irradiance Dataframe and output visual graphs.

.. autofunction:: libinsitu.qc.qc_utils.visual_qc

.. _Notebook: https://git.sophia.mines-paristech.fr/oie/libinsitu/-/blob/notebooks/visual-quality-check.ipynb
