import numpy as np

from libinsitu import CLIMATE_ATTRS, STATION_COUNTRY_ATTRS, NETWORK_NAME_ATTRS


class BaseGraphs:
    """ Base class holding source data to compute graph. Implementations inherit from it """

    def __init__(self,
            meas_df = None,
            sp_df = None,
            flag_df = None,
            cams_df = None,
            stat_test = None,
            horizons = None,
            latitude = None,
            longitude = None,
            elevation = None,
            station_id="-",
            station_name="-",
            show_flag=-1):

        """
         ShowFlag=-1     : only show non-flagged data
         ShowFlag=0      : show all data without filtering nor tagging flagged data
         ShowFlag=1      : show all data and highlight flagged data in red
        """


        self.time = None
        self.GHI = None
        self.DIF = None
        self.DNI = None
        self.flags = None
        self.SS_h = None
        self.SR_h = None
        self.TOA = None
        self.TOANI = None
        self.GAMMA_S0 = None
        self.THETA_Z = None
        self.ALPHA_S = None
        self.SZA = None
        self.QCfinal = None

        self.show_flag=show_flag
        self.cams_df = cams_df
        self.stat_test = stat_test
        self.horizons = horizons
        self.latitude = latitude
        self.longitude = longitude
        self.elevation = elevation
        self.station_id = station_id
        self.station_name = station_name

        self.climate = None
        self.country = None
        self.source = None

        if meas_df is None:
            return

        if show_flag == -1:
            # Hide all data with having at least one QC error
            meas_df.loc[
                flag_df.QCfinal != 0,
                ["GHI", "DHI", "BNI"]] = np.nan

        # Aliases
        self.time = meas_df.index
        self.GHI = meas_df.GHI
        self.DIF = meas_df.DHI
        self.DNI = meas_df.BNI

        self.climate = _get_meta(meas_df, CLIMATE_ATTRS)
        self.country = _get_meta(meas_df, STATION_COUNTRY_ATTRS)
        self.source = _get_meta(meas_df, NETWORK_NAME_ATTRS)

        self.TOA = sp_df.TOA
        self.TOANI = sp_df.TOANI
        self.GAMMA_S0 = sp_df.GAMMA_S0
        self.THETA_Z = sp_df.THETA_Z
        self.ALPHA_S = sp_df.ALPHA_S
        self.SZA = sp_df.SZA
        self.flags = flag_df
        self.SS_h = sp_df.SS_h
        self.SR_h = sp_df.SR_h
        self.QCfinal = flag_df.QCfinal

        self.GHI_est = self.DIF + self.DNI * np.cos(self.THETA_Z)

def _get_meta(df, keys) :
    """Try several keys to get Meta data"""
    for key in keys :
        if key in df.attrs :
            return df.attrs[key]
    return "-"