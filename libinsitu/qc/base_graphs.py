import numpy as np

class BaseGraphs :
    """ Base class holding source data to compute graph. Implementations inherit from it """

    def __init__(self,
            meas_df,
            sp_df,
            flag_df,
            cams_df,
            stat_test,
            horizons,
            latitude,
            longitude,
            elevation,
            station_id="-",
            station_name="-",
            show_flag=-1):

        """
         ShowFlag=-1     : only show non-flagged data
         ShowFlag=0      : show all data without filtering nor tagging flagged data
         ShowFlag=1      : show all data and highlight flagged data in red
        """

        self.meas_df = meas_df
        self.sp_df = sp_df
        self.show_flag=show_flag
        self.cams_df = cams_df
        self.stat_test = stat_test
        self.horizons = horizons
        self.latitude = latitude
        self.longitude = longitude
        self.elevation = elevation
        self.station_id = station_id
        self.show_flag = show_flag
        self.station_name = station_name

        if show_flag == -1:
            # Hide all data with having at least one QC error
            meas_df.loc[
                flag_df.QCfinal != 0,
                ["GHI", "DHI", "BNI"]] = np.nan

        # Aliases
        self.GHI = meas_df.GHI
        self.DIF = meas_df.DHI
        self.DNI = meas_df.BNI

        self.TOA = sp_df.TOA
        self.TOANI = sp_df.TOANI
        self.GAMMA_S0 = sp_df.GAMMA_S0
        self.THETA_Z = sp_df.THETA_Z
        self.ALPHA_S = sp_df.ALPHA_S
        self.SZA = sp_df.SZA
        self.flag_df = flag_df
        self.QCfinal = flag_df.QCfinal

        self.GHI_est = self.DIF + self.DNI * np.cos(self.THETA_Z)