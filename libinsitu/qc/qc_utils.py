# -*- coding: utf-8 -*-
"""
Created on Thu Jun 23 10:09:54 2022

@author: y-m.saint-drenan
"""
from enum import IntEnum
import os
from collections import defaultdict
from enum import Enum
from functools import reduce
from operator import or_
from urllib.request import urlopen

import numpy as np
import pandas as pd
import pvlib
import sg2
from appdirs import user_cache_dir
from diskcache import Cache
from pandas import DataFrame

from libinsitu import STATION_LONG_NAME_VAR, QC_LEVEL_VAR
from libinsitu.cdl import initVar, get_cdl
from libinsitu.common import LATITUDE_VAR, LONGITUDE_VAR, ELEVATION_VAR, GLOBAL_VAR, \
    DIFFUSE_VAR, DIRECT_VAR, parseCSV, ALTERNATE_COMP_NAMES_INV, get_df_resolution, \
    getTimeVar, QC_FLAGS_VAR, seconds_to_idx, datetime64_to_sec, STATION_NAME_VAR, STATION_ID_ATTRS, QC_RUN_VAR, netcdf_to_dataframe
from libinsitu.log import warning, info
from libinsitu.qc.graphs import Graphs
from libinsitu.qc.graphs.base import _get_meta, FlagLevel
from libinsitu.qc.graphs.main_layout import GraphId

cachedir = user_cache_dir("libinsitu")
cache = Cache(cachedir)

MIN_VAL = -100.0
MAX_VAL = 5000.0

CAMS_EMAIL_ENV = "CAMS_EMAIL"

QC_TESTS_FILE = "qc-tests.csv"

# Cache to description of flags
_FLAGS = None


class QCFlag :
    def __init__(self, name, components, bit=-1, condition=None, domain=None, source=None, level=None, group_level=None):
        self.name = name
        self.bit = bit
        self.components = components
        self.condition = condition
        self.domain = domain
        self.source = source
        self.level = level
        self.group_level = group_level

    def mask(self):
        return 2 ** (self.bit-1)


def get_flags() :
    global _FLAGS


    if _FLAGS is None :
        _FLAGS = parseCSV(QC_TESTS_FILE, key="name")
        for name, flag in _FLAGS.items() :
            flag["components"] = flag["components"].split(",")

            # Replace alternative component names with canonical ones
            flag["components"] = [ALTERNATE_COMP_NAMES_INV.get(comp, comp) for comp in flag["components"]]
            flag["level"] = int(flag["level"]) if flag["level"] else None
            flag["group_level"] = int(flag["group_level"]) if flag["group_level"] else None

        # TRansform to flag object
        _FLAGS = {name:QCFlag(**flag) for name, flag  in _FLAGS.items()}

    return _FLAGS



def flagData(meas_df, sp_df):
    """
    :param meas_df: In situ measurements
    :param sp_df: Sun pos / theoretical measurements
    :return: QC flags. -1: no processed. 0: processed and ok. 1: Processed and failed
    """

    # Setup alias as local variables for evualuation of the flags
    GHI = meas_df.GHI
    DHI = meas_df.DHI
    DIF = DHI # Alias
    BNI = meas_df.BNI
    DNI = BNI # Alias

    TOA = sp_df.TOA
    TOANI = sp_df.TOANI
    THETA_Z = sp_df.THETA_Z

    GHI_est = DHI + BNI * np.cos(THETA_Z)
    SZA = sp_df.THETA_Z * 180 / np.pi

    size = len(meas_df.GHI)

    Kt = GHI / TOA
    Kn = BNI / TOANI
    K = DIF / GHI

    flag_df = DataFrame(index=meas_df.index)

    cache = dict()

    def eval_formula(formula, _locals) :
        formula = formula.replace("^", "**").replace("≤", " <= ").replace("≥", " >= ")

        # Add all numpy function to local scope
        _locals = _locals.copy()
        _locals.update(np.__dict__)

        if not formula in cache :
            try:
                cache[formula] = eval(formula, dict(), _locals)
            except Exception as e :
                raise Exception("Error while evaluating '%s'" % formula) from e

        return cache[formula]

    # Loop on flags definition
    for name, flag_def in get_flags().items() :

        # Evaluate the expression
        test_ok = eval_formula(
            flag_def.condition,
            locals())

        domain_ok = eval_formula(
            flag_def.domain,
            locals())

        # Mark NA flags as outside of the domain
        for comp in flag_def.components :
            domain_ok = domain_ok & (~meas_df[comp].isna())

        # Combina the two in a condition
        flag_df[name] = np.select(
            [~domain_ok, ~test_ok],
            [-1, 1],
            default=0)

    return flag_df


def _combine_flags(flags_list) :
    """Combine several series of flags into one
    -1 in one of the flag in -1
    1 if one of the flags is 1, 0 otherwize"""

    if len(flags_list) == 1:
        return flags_list[0]

    conds = []
    res = []
    for flags in flags_list :
        conds.insert(0, flags == -1)
        conds.append(flags == 1)
        res.insert(0, -1)
        res.append(1)
    return np.select(conds, res, 0)


def _group_flags() :
    """Build a  Dict of Component => Number of component (1, 2, 3) => level => [tests]"""
    flags = get_flags()

    # Dict of Component => Number of component (1, 2, 3) => level => [tests]
    flags_dict = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(list)))

    # Dict of group_level = [flags]
    groups = defaultdict(list)

    for flag in flags.values():
        nb_comp = len(flag.components)

        # Skip flags to be ignored in level
        if flag.level == -1 or flag.level is None:
            continue

        for component in flag.components:
            flags_dict[component][nb_comp][flag.level].append(flag)

        if flag.group_level is not None:
            groups[flag.group_level].append(flag)

    # Add group flags to all its components
    for level, flags in groups.items():

        # All components
        components = reduce(or_, [set(flag.components) for flag in flags])

        for comp in components :
            for flag in flags:
                flags_dict[comp][len(flag.components)][level].append(flag)


    return flags_dict




def _compute_grouped_flag_values(flag_groups, flags_df) :
    """Compute combined values for each group of flags <component, nb_comp, level>"""

    return {
        comp: {
            nb_comp: {
                level : _combine_flags([flags_df[flag.name] for flag in flags])
                for level, flags in flags_per_level.items()
            } for nb_comp, flags_per_level in flags_per_comp.items()
        } for comp, flags_per_comp in flag_groups.items()
    }

def _compute_levels_per_nb_comp(
        flag_values,
        out_domain_value,
        fallback_values,
        mask=None) :
    """
    Compute flag values for a given number of components (1C, 2C, 3C) :
    returns either the hightest matching level, or (10*nb_comp -5) if one out of domain (-1) value is found.
    """

    # Sort flag values by descending levels
    flag_values = dict(sorted(flag_values.items(), reverse=True))

    condlist = []
    choicelist = []

    # Loop on flags by descending order
    for level, flags in flag_values.items():

        if mask is not None:
            flags = flags[mask]

        # Out of domain => out of domain value
        condlist.append(flags == -1)
        choicelist.append(out_domain_value)

        condlist.append(flags == 0)
        choicelist.append(level)

    return np.select(
        condlist,
        choicelist,
        fallback_values)

def _highest_level(flags_per_level) :
    return max(flags_per_level.keys())

def _compute_levels_per_comp(
        comp_flags_values,
        comp_values,
        sza) :

    flags_1C = comp_flags_values[1]
    flags_2C = comp_flags_values[2]
    flags_3C = comp_flags_values[3]

    # Starting levels : -5 for night. -1 for missing values
    levels = np.select(
        [sza > 90, comp_values.isna()], [FlagLevel.NIGHT, FlagLevel.MISSING])

    #for nb_comp, flags in comp_flags_values.items()

    # Process 1C - Only process samples having level >= 0
    levels[levels == 0] = _compute_levels_per_nb_comp(
        flags_1C,
        out_domain_value=5,
        fallback_values=0,
        mask=(levels==0))

    # Process 2C - Only process samples having level >= highest_1c (10 usually)
    highest_1c = _highest_level(flags_1C)
    levels[levels == highest_1c] = _compute_levels_per_nb_comp(
        flags_2C,
        out_domain_value=15,
        fallback_values=highest_1c,
        mask=(levels==highest_1c))

    # Process 2C - Only process samples having level >= highest_2c (24 usually)
    highest_2c = _highest_level(flags_2C)
    levels[levels == highest_2c] = _compute_levels_per_nb_comp(
        flags_3C,
        out_domain_value=25,
        fallback_values=highest_2c,
        mask=(levels == highest_2c))

    return levels

def compute_qc_level(flags_df, meas_df, sp_df) :

    # Get flags per component => nb component and level
    flag_groups = _group_flags()

    grouped_flag_values = _compute_grouped_flag_values(flag_groups, flags_df)

    res_df = DataFrame(index=meas_df.index)

    # Loop on components
    for comp, comp_flags_values in grouped_flag_values.items() :

        res_df[comp] = _compute_levels_per_comp(
            comp_flags_values,
            meas_df[comp],
            sp_df.SZA)

    return res_df


def qc_stats(flag_df) :

    def percent(component) :

        flag_values = flag_df[component]

        filter = (flag_values != -1)
        tot_nb = sum(filter)

        if tot_nb == 0 :
            return np.nan
        else:
            return sum(flag_values == 1) / tot_nb * 100

    return {col : percent(col) for col in flag_df.columns}




def cleanup_data(df, freq=None):
    """Cleanup and resample data"""

    # Default resolution : take the one from the source
    if freq is None:
        freq = get_df_resolution(df)

    # Not UTC ?
    if df.index.tz is not None:
        df.index = df.index.tz_convert('UTC').tz_localize(None)

    # Fill out of range values with NAN
    # XXX use "range" QC check instead
    for varname in [GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR] :
        if varname in df :
            var = df[varname]
            df.loc[var > MAX_VAL, varname] = np.nan
            df.loc[var < MIN_VAL, varname] = np.nan
        else:
            warning("Missing var %s, adding NaNs" % varname)
            df[varname] = np.nan

    freq_s = str(freq) + "S"

    df = df.resample(freq_s).ffill()
    df = df.asfreq(freq_s)

    start_date = df.index.min().normalize()
    end_date = df.index.max().normalize() + np.timedelta64(24 * 60 - 1, "m")

    df = df.reindex(pd.date_range(start_date, end_date, freq=freq_s))

    return df

#@cache.memoize()
def sun_position(lat, lon, alt, start_time, end_time, freq="60S") :

    if alt == np.nan:
        alt = 0

    times = pd.date_range(start_time, end_time, freq=freq)

    sun_rise = sg2.sun_rise(
        [[lon, lat, alt]],
        times)

    sun_pos = sg2.sun_position(
        [[lon, lat, alt]],
        times,
        ["topoc.alpha_S", "topoc.gamma_S0", "topoc.toa_hi", "topoc.toa_ni"])

    SR = np.squeeze(sun_rise[:, 0, 0])
    SR_Day = SR.astype('datetime64[D]').astype(SR.dtype)
    SR_TOD = (SR - SR_Day).astype(float) / 1000 / 60 / 60

    SS = np.squeeze(sun_rise[:, 0, 2])
    SS_Day = SS.astype('datetime64[D]').astype(SS.dtype)
    SS_TOD = (SS - SS_Day).astype(float) / 1000 / 60 / 60

    df = pd.DataFrame(index=times)

    # Add extra columns from SG2 to dataframe
    df['THETA_Z'] = np.pi / 2 - np.squeeze(sun_pos.topoc.gamma_S0)
    df['GAMMA_S0'] = np.squeeze(sun_pos.topoc.gamma_S0)
    df['ALPHA_S'] = np.squeeze(sun_pos.topoc.alpha_S)
    df['SZA'] = 90 - 180 / np.pi * np.squeeze(sun_pos.topoc.gamma_S0)
    df['TOA'] = np.squeeze(sun_pos.topoc.toa_hi)
    df['TOANI'] = np.squeeze(sun_pos.topoc.toa_ni)
    df['SR_h'] = SR_TOD
    df['SS_h'] = SS_TOD

    return df


@cache.memoize()
def get_cams(start_date, end_date, lat, lon, altitude, time_step="1min") :

    info("Calling CAMS")

    if CAMS_EMAIL_ENV in os.environ:
        cams_email = os.environ[CAMS_EMAIL_ENV]
    else:
        raise Exception("Cams emails not found. Please set the env variable %s or use a .env file" % CAMS_EMAIL_ENV)

    CAMS_DF, _ =  pvlib.iotools.get_cams(
                start=start_date,
                end=end_date,
                latitude=lat, longitude=lon,
                email=cams_email,
                identifier='mcclear',
                altitude=altitude, time_step=time_step, time_ref='UT', verbose=False,
                integrated=False, label='right', map_variables=True,
                server='www.soda-is.com', timeout=180)

    res = pd.DataFrame({
        'CLEAR_SKY_GHI': CAMS_DF.ghi_clear.values,
        'CLEAR_SKY_DNI': CAMS_DF.dni_clear.values,
        'CLEAR_SKY_DIF': CAMS_DF.dhi_clear.values},
        index=CAMS_DF.index.values)

    info("End calling CAMS")

    return res

@cache.memoize()
def wps_Horizon_SRTM(lat, lon, altitude):
    if np.abs(lat) < 60 :
        return None

    info("Fetching horizons from WPS")

    str_wps = 'http://toolbox.webservice-energy.org/service/wps?service=WPS&request=Execute&identifier=compute_horizon_srtm&version=1.0.0&DataInputs='
    datainputs_wps = 'latitude={:.6f};longitude={:.6f};altitude={:.1f}'.format(lat, lon, altitude)

    response = urlopen('{}{}'.format(str_wps, datainputs_wps))

    HZ = pd.read_csv(response, delimiter=';', comment='#', header=None, skiprows=17, nrows=360,
                         names=['AZIMUT', 'ELEVATION'])

    info("Horizons fetched")

    return HZ

def write_qc_levels(ncfile, qc_levels_df) :

    cdl = get_cdl(init=True)

    for comp in [GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR] :

        qc_varname = QC_LEVEL_VAR % comp
        levels = qc_levels_df[comp]

        if qc_varname in ncfile.variables :
            warning("%s was already present, updating it :" % qc_varname)
        initVar(ncfile, cdl.variables[qc_varname])

        write_values(ncfile, qc_varname, levels.index.values, levels.values)


def write_flags(ncfile, flags_df):
    """Update flags in NetCDF file"""

    # Get default CDL : XXX support for custom one ?
    cdl = get_cdl(init=True)

    flags = get_flags()

    # Create var if not present yet
    for var in [QC_FLAGS_VAR, QC_RUN_VAR] :
        if var in ncfile.variables :
            warning("%s was already present, updating it :" % var)
        initVar(ncfile, cdl.variables[var])

        ncvar = ncfile.variables[var]
        ncvar.setncattr("flag_meanings", " ".join(flags.keys()))
        ncvar.setncattr("flag_masks", [flag.mask() for flag in flags.values()])

        # Update meanings and flags

    # Build a dictionary of masks
    flag_masks = {flag.name: flag.mask() for flag in flags.values()}

    # Output
    def write_flags(varname, values_df) :

        values_df = values_df.astype(int)
        out_masks = np.zeros(len(values_df), dtype=int)

        # Build mask from all flag columns
        for colname in values_df.columns :
            if not colname in flag_masks :
                warning("Flag %s not found in QC flags DSL. Skipping" % colname)
                continue

            out_masks += values_df[colname].values * flag_masks[colname]

        # Write final mask to file
        write_values(ncfile, varname, values_df.index.values, out_masks)


    # Flags for failing tests
    write_flags(
        QC_FLAGS_VAR,
        flags_df == 1)

    # Flags for run tests
    write_flags(
        QC_RUN_VAR,
        flags_df != -1)


def write_values(ncfile, varname, dates, values) :

    """Write time serie to ncfile taking care of truncating """

    # Compute time idx
    times_sec = datetime64_to_sec(ncfile, dates)
    time_idx = seconds_to_idx(ncfile, times_sec)

    time_var = getTimeVar(ncfile)

    max_time = len(time_var)

    out_idx = time_idx > max_time - 1
    if np.any(out_idx):
        warning("Index of of time range. Truncating %d values" % np.sum(out_idx))
        time_idx = time_idx[~out_idx]
        values = values[~out_idx]

    var = ncfile.variables[varname]
    var[time_idx] = values

def compute_sun_pos(df, lat=None, lon=None, alt=None) :
    """Call sg2 on data"""

    lat = lat if lat is not None else float(df.attrs[LATITUDE_VAR])
    lon = lon if lon is not None else  float(df.attrs[LONGITUDE_VAR])
    alt = alt if alt is not None else  float(df.attrs[ELEVATION_VAR])

    # Compute geom & theoretical irradiance
    sp_df = sun_position(
        lat, lon, alt,
        df.index.min(),
        df.index.max(),
        freq=pd.infer_freq(df.index))

    return sp_df

class ShowFlag(Enum):
    HIDE="hide" # Hide data with errors
    SHOW="show" # Show all data
    FLAG="flag" # Flag errors in red


def _compute_qc_final(flags_df) :
    """Ads QcFinal to tests"""
    QCfinal = np.zeros(len(flags_df), dtype=int)
    for comp in flags_df.columns :
        data = flags_df[comp]
        QCfinal = QCfinal | (data == 1)
    flags_df["QCfinal"] = QCfinal

def visual_qc(
        df,
        latitude = None,
        longitude = None,
        elevation = None,
        station_id = None,
        station_name = None,
        with_horizons = False,
        with_mc_clear = False,
        show_flag=ShowFlag.SHOW,
        graph_id:GraphId=None):

    """
    Generates matplotlib graphs for visual QC


    :param df: Dataframe of input irradiance. It should have a time index and 3 columns : GHI, DHI, BNI).
               This dataframe can typically be obtained with netcdf_to_dataframe(... rename_cols=True)
    :param latitude: Latitude of the station. Can also be passed as meta data (.attrs) of the Dataframe
    :param longitude: Longitude of the station. Can also be passed as meta data (.attrs) of the Dataframe
    :param elevation: elevation of the station. Can also be passed as meta data (.attrs) of the Dataframe
    :param station_id: Id of the station (optional). Can also be passed as meta data (.attrs) of the Dataframe
    :param station_id: Name of the station (optional). Can also be passed as meta data (.attrs) of the Dataframe
    :param with_horizons: True to compute horizons (requires network)
    :param with_mc_clear: True to compute mc_clear from SODA (requires SODA credentials and network access)
    :param graph_id: If not None, only display a specific graph
    """

    # Resample to the minute to produce graph
    resolution_sec = 60

    # Clean data
    df = cleanup_data(df, resolution_sec)

    # Get meta data from parameters or from attributes attached to the Dataframe
    lat = latitude if latitude else  float(df.attrs[LATITUDE_VAR])
    lon = longitude if longitude else float(df.attrs[LONGITUDE_VAR])
    alt = elevation if elevation else float(df.attrs[ELEVATION_VAR])
    station_id = station_id if station_id else _get_meta(df, STATION_ID_ATTRS)
    station_name = station_name if station_name else _get_meta(df, STATION_NAME_VAR)
    station_longname = _get_meta(df, STATION_LONG_NAME_VAR) or station_name

    # Compute geom & theoretical irradiance
    sp_df = compute_sun_pos(df, lat , lon, alt)

    # Compute QC flags
    flags_df = flagData(df, sp_df)

    # Fetch horizons
    if with_horizons:
        horizons = wps_Horizon_SRTM(lat, lon, alt)
    else:
        horizons = None

    if with_mc_clear:
        cams_df = get_cams(
            start_date=df.index.min(),
            end_date=df.index.max(),
            lat=lat, lon=lon,
            altitude=alt)
        cams_df = cams_df.reindex(df.index)
    else:
        cams_df = None

    # Transform flag
    # TODO : refactor main_layout to use Enum too
    flag = {
        ShowFlag.SHOW : 0,
        ShowFlag.HIDE : -1,
        ShowFlag.FLAG : 1
    }[show_flag]

    # XXX remove and replace by QCLevels ?
    _compute_qc_final(flags_df)


    # Statistics on QC flags
    stat_test = qc_stats(flags_df)

    # Compute QC level
    qc_level = compute_qc_level(
        flags_df=flags_df,
        meas_df=df,
        sp_df=sp_df)

    # Draw figures
    graph = Graphs(
        meas_df=df,
        sp_df=sp_df,
        flag_df=flags_df,
        qc_level = qc_level,
        cams_df=cams_df,
        horizons=horizons,
        stat_test=stat_test,
        latitude=lat,
        longitude=lon,
        elevation=alt,
        station_id=station_id,
        station_name=station_name,
        station_longname=station_longname,
        show_flag=flag)

    if graph_id is None :
        return graph.main_layout()
    else:
        return graph.plot_individual(graph_id)


def update_qc_flags(ncfile, start_time=None, end_time=None) :

    """ Compute and update QC flags on NCFile """

    meas_df = netcdf_to_dataframe(ncfile, start_time=start_time, end_time=end_time, rename_cols=True)

    # Compute sun pos with sg2
    sp_df = compute_sun_pos(meas_df)

    # Update QC flags
    flags_df = compute_qc_flags(meas_df=meas_df, sp_df=sp_df)
    write_flags(ncfile, flags_df)

    # Update QC levels
    qc_levels = compute_qc_level(flags_df=flags_df, meas_df=meas_df, sp_df=sp_df)
    write_qc_levels(ncfile, qc_levels)


def compute_qc_flags(meas_df, lat=None, lon=None, alt=None, sp_df=None):
    """
    :param meas_df: Dataframe of irradiance
    :param lat: Latitude (or passed in df.attrs)
    :param lon: Longitude (or passed in df.attrs)
    :param alt: Altitude (or passed in df.attrs)
    :return: New dataframe of QC flags. This dataframe may contain additional timestamps to fill complete days.
    """

    # Update NetCDF file with QC
    if sp_df is None:
        sp_df = compute_sun_pos(meas_df, lat=lat, lon=lon, alt=alt)

    return flagData(meas_df, sp_df)