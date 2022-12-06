# -*- coding: utf-8 -*-
"""
Created on Thu Jun 23 10:09:54 2022

@author: y-m.saint-drenan
"""
from urllib.request import urlopen

import sg2
from appdirs import user_cache_dir

from libinsitu import CDL_PATH, read_res, DefaultDict, datetime64_to_sec, seconds_to_idx, getTimeVar, QC_FLAGS_VAR, \
    STATION_ID_ATTRS, STATION_NAME_VAR
from libinsitu.cdl import parse_cdl, initVar
from libinsitu.log import info, warning
from libinsitu.qc.graphs import *
import os

from matplotlib.gridspec import GridSpec
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import pvlib


from libinsitu.common import LATITUDE_VAR, LONGITUDE_VAR, ELEVATION_VAR, GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR, GLOBAL_TIME_RESOLUTION_ATTR
from diskcache import Cache

from libinsitu.qc.graphs import plot_heatmap_timeseries, plot_ratio_heatmap, histo_qc, _get_meta

cachedir = user_cache_dir("libinsitu")
cache = Cache(cachedir)

MIN_VAL = -100.0
MAX_VAL = 5000.0

CAMS_EMAIL_ENV = "CAMS_EMAIL"

def plot_timeseries(label, data, TOA, ymax, ShowFlag, QCfinal) :

    info("plotting timeseries for %s" % label)

    if ShowFlag == -1:
        idxPlot = (TOA > 0) & (data.values > -50 & (QCfinal == 0))
    else:
        idxPlot = (TOA > 0) & (data.values > -50)

    index = data.index
    axe = gca()

    axe.plot(
        data.index[idxPlot],
        data.values[idxPlot],
        color='b',
        alpha=0.8,
        label='meas.',
        lw=0.2)

    plt.ylim((0, ymax))
    plt.xlim((
        index.values[0],
        index.values[-1]))

    axe.set_ylabel(label + " (W/m2)", size=8)
    plt.setp(axe.get_xticklabels(), visible=False)


def SolarRadVisualControl(
        meas_df,
        sp_df,
        flag_df,
        cams_df,
        horizons,
        latitude,
        longitude,
        elevation,
        station_id="-",
        station_name="-",
        ShowFlag=-1) :
    """
     ShowFlag=-1     : only show non-flagged data
     ShowFlag=0      : show all data without filtering nor tagging flagged data
     ShowFlag=1      : show all data and highlight flagged data in red
    """

    # Aliases
    GHI = meas_df.GHI
    DIF = meas_df.DHI
    DNI = meas_df.BNI

    TOA = sp_df.TOA
    TOANI = sp_df.TOANI
    GAMMA_S0 = sp_df.GAMMA_S0
    THETA_Z = sp_df.THETA_Z
    ALPHA_S = sp_df.ALPHA_S
    SZA = sp_df.SZA

    QCfinal = flag_df.QCfinal

    GHI_est = DIF + DNI * np.cos(THETA_Z)

    info("QC: visual plot preparation")

    fig = plt.figure(figsize=(19.2, 9.93))

    # =====================================================================
    # First column : time series + heatmaps + ratios
    # =====================================================================

    # Draw grid
    grid = GridSpec(8 if cams_df is None else 9, 1)
    grid.update(
        left=0.035, right=0.32,
        bottom=0.03, top=0.98,
        hspace=0.02, wspace=0.05)

    # -- Plot time series

    # GHI
    def timeseries(row_idx, label, data, xmax):
        plt.subplot(grid[row_idx, 0])
        plot_timeseries(label, data, TOA, xmax, ShowFlag, QCfinal)

    timeseries(0, "GHI", GHI, 1400)
    timeseries(1, "DNI", DNI, 1400)
    timeseries(2, "DIF", DIF, 1000)

    # -- Plot Heatmaps

    def plot_heatmap(row_idx, label, data, xcmax):
        plt.subplot(grid[row_idx, 0])
        plot_heatmap_timeseries(label, data, sp_df.SR_h, sp_df.SS_h, xcmax, longitude, ShowFlag, QCfinal)

    plot_heatmap(3, "GHI", GHI, 700)
    plot_heatmap(4, "DNI", DNI, 900)
    plot_heatmap(5, "DIF", DIF, 700)

    # -- Plot ratios

    # XXX ? What does this do ?
    Smth = [1, 1]
    if Smth[0] < 1:
        xx = 0
        h1 = 1
    else:
        xx = np.linspace(-np.ceil(3 * Smth[0]), np.ceil(3 * Smth[0]), 2 * 3 * Smth[0] + 1)
        h1 = np.exp(-0.5 * (xx / Smth[0]) ** 2)
        h1 = h1 / sum(h1)
    if Smth[1] < 1:
        xx = 0
        h2 = 1
    else:
        xx = np.linspace(-3 * np.ceil(Smth[1]), np.ceil(3 * Smth[1]), 2 * 3 * Smth[1] + 1)
        h2 = np.exp(-0.5 * (xx / Smth[1]) ** 2)
        h2 = h2 / sum(h2)

    # Helper for factorizinf calls to the function
    def plot_ratio(row_idx, ratios, filter, y_label, title, ylimit=0.25, bg_color=None, hlines=[]) :
        plt.subplot(grid[row_idx, 0])
        plot_ratio_heatmap(y_label=y_label, ratios=ratios, filter=filter, title=title, ylimit=ylimit, bgColor=bg_color,
                           QCfinal=QCfinal, TOA=TOA, h1=h1, h2=h2, ShowFlag=ShowFlag, hlines=hlines)

    # DIF / GHI
    plot_ratio(
        row_idx=6, ratios=DIF / GHI,
        filter=(DIF > 0) & (DNI > 0) & (GHI > 0),
        y_label='DIF/GHI (-)', title='Comparison of DIF and GHI for DNI<10W/m2. Should be close to 1.')

    # GHI / estimated GHI
    plot_ratio(
        row_idx=7, ratios=GHI / GHI_est,
        filter=(DNI > 0) & (GHI > 0) & (DNI < 5),
        y_label='GHI/(DNI*cSZA+DIF) (-)',
        title='Ratio of global to the sum of its components. Should be close to 1.',
    hlines=[(0.08, 0.8), (0.15, 1.0)]) # (position relative to 1, linewidth)

    # GHI / Clear sky
    if cams_df is not None:

        plot_ratio(
            row_idx=8, ratios=GHI / cams_df.CLEAR_SKY_GHI,
            filter=(DNI > 0) & (GHI > 0),
            y_label='GHI/GHIcs (-)',
            title='Evaluation of McClear(*): Ratio of GHI to clear-sky GHI (GHIcs).',
            ylimit=0.75, bg_color=MC_CLEAR_COLOR)

        plt.annotate(
            '(*) not a plausibility control: the scatter points represent the joint effect of McClear and measurement errors.',
            (5, 2), xycoords='figure pixels',
            fontsize=6, fontstyle='italic', color=MC_CLEAR_COLOR)


    # =====================================================================
    # % % Part4: ERL& PPL tests
    # =====================================================================

    gs2 = GridSpec(4, 6)
    gs2.update(
        left=0.07, right=0.97,
        bottom=0.1, top=0.98,
        hspace=0.25, wspace=0.25)

    Stat_Test = qc_stats(meas_df, sp_df, flag_df)

    def bsrn_1c(row, component, component_name, limits) :
        plt.subplot(gs2[row, 2])
        plot_bsrn_1c(
            TOA=TOA,
            component=component,
            component_name=component_name,
            ShowFlag=ShowFlag,
            TOANI=TOANI,
            GAMMA_S0=GAMMA_S0,
            QCfinal=QCfinal,
            limits=limits,
            Stat_Test=Stat_Test)

    bsrn_1c(0, GHI, "GHI", [[1.5, 1.2, 100], [1.2, 1.2, 50]])
    bsrn_1c(1, DNI, "DNI", [[1, 0, 0], [0.95, 0.2, 10]])
    bsrn_1c(2, DIF, "DIF", [[0.95, 1.2, 50],[0.75, 1.2, 30]])


    # BSRN 2C
    plt.subplot(gs2[0, 3])
    bsrn_2c(GHI, SZA, flag_df.K, Stat_Test, ShowFlag, QCfinal)

    # SERI-Kn
    plt.subplot(gs2[1, 3])
    seri_kn(DNI, GHI, SZA, flag_df.KT, flag_df.Kn, Stat_Test, ShowFlag, QCfinal)

    # SERI-K
    plt.subplot(gs2[2, 3])
    seri_k(DIF, GHI, SZA, flag_df.KT, flag_df.K, ShowFlag, QCfinal, Stat_Test)

    # BSRN Closure
    plt.subplot(gs2[3, 2])
    bsrn_closure(GHI, DIF, SZA, GHI_est, Stat_Test, ShowFlag, QCfinal)

    # BRSN Closure ratio
    plt.subplot(gs2[3, 3])
    im = bsrn_closure_ratio(DIF, GHI, SZA, GHI_est, Stat_Test, ShowFlag, QCfinal)

    # Color legend
    cb_ax = fig.add_axes([0.38, 0.04, 0.28, 0.01])
    cbar = fig.colorbar(im, cax=cb_ax, orientation='horizontal', label='point density (-)')
    cbar.set_ticks([])

    # -- Third column

    # -- Text info
    print_info(
        meas_df,
        GHI, DIF, DNI, TOA,
        latitude, longitude, elevation,
        station_id, station_name)

    # -- QC histograms
    info("QC: histograms of K, Kn & KT")

    gs3b = GridSpec(9, 9)
    gs3b.update(
        left=0.075,
        right=0.98,
        bottom=0.001,
        top=0.97,
        hspace=0.025,
        wspace=0.00)

    plt.subplot(gs3b[1:3, 6])
    histo_qc(GHI, flag_df.KT, 'GHI/TOA', SZA, flag_df.QCfinal, y_label=True)

    plt.subplot(gs3b[1:3, 7])
    histo_qc(DNI, flag_df.Kn, 'DNI/TOANI', SZA, flag_df.QCfinal)

    plt.subplot(gs3b[1:3, 8])
    histo_qc(DIF, flag_df.K, 'DIF/GHI', SZA, flag_df.QCfinal, legend_pos='upper left')


    if cams_df is None :
        gs3 = GridSpec(7, 3)
        shadow_row = 3
    else:
        gs3 = GridSpec(9, 3)
        shadow_row = 5

    gs3.update(left=0.0, right=0.99, bottom=0.05, top=0.875, hspace=0.1, wspace=0.2)

    # -- Horizontality graph
    if cams_df is not None:

        info("Horizontality test")
        plt.subplot(gs3[3:5, 2])

        horizontality_graph(cams_df, meas_df, GHI, DIF, SZA, ALPHA_S, flag_df, latitude, ShowFlag)


    # -- Shadow analysis
    info("Shadow analysis (GHI)")

    plt.subplot(gs3[shadow_row:shadow_row+2, 2])
    shadow_analysis('GHI/TOA (-)', GHI, TOA, 0.85, GAMMA_S0, ALPHA_S, latitude, horizons, QCfinal)

    plt.subplot(gs3[shadow_row + 2:shadow_row + 4, 2])
    shadow_analysis('DNI/TOANI (-)', DNI, TOANI, 0.65, GAMMA_S0, ALPHA_S, latitude, horizons, QCfinal)


def flagData(meas_df, sp_df):
    """
    :param meas_df: In situ measurements
    :param sp_df: Sun pos / theoretical measurements
    :return: QC flags. -1: no processed. 0: processed and ok. 1: Processed and failed
    """

    MinDailyShareFlag = 0.2

    # Aliases
    GHI = meas_df.GHI
    DIF = meas_df.DHI
    DNI = meas_df.BNI

    TOA = sp_df.TOA
    TOANI = sp_df.TOANI
    GAMMA_S0 = sp_df.GAMMA_S0

    GHI_est = DIF + DNI * np.cos(sp_df.THETA_Z)
    SZA = sp_df.THETA_Z * 180 / np.pi

    size = len(meas_df.GHI)

    KT = np.zeros(size)
    KT[TOA >= 1] = GHI[TOA >= 1] / TOA[TOA >= 1]

    Kn = np.zeros(size)
    Kn[TOANI >= 1] = DNI[TOANI >= 1] / TOANI[TOANI >= 1]

    K = np.zeros(size)
    K[GHI >= 1] = DIF[GHI >= 1] / GHI[GHI >= 1]

    # % % -----------   Calculation of the individual QC flags -----------------
    # BSRN one-component test
    flag_df = DataFrame(index=meas_df.index)
    flag_df["T1C_ppl_GHI"] = (TOA > 0) & (
            (GHI <= -4) | (GHI > 1.5 * TOANI * np.sin(GAMMA_S0) ** 1.2 + 100))
    flag_df["T1C_erl_GHI"] = (TOA > 0) & (
            (GHI <= -2) | (GHI > 1.2 * TOANI * np.sin(GAMMA_S0) ** 1.2 + 50))
    flag_df["T1C_ppl_DIF"] = (TOA > 0) & (
            (DIF <= -4) | (DIF > 0.95 * TOANI * np.sin(GAMMA_S0) ** 1.2 + 50))
    flag_df["T1C_erl_DIF"] = (TOA > 0) & (
            (DIF <= -2) | (DIF > 0.75 * TOANI * np.sin(GAMMA_S0) ** 1.2 + 30))
    flag_df["T1C_ppl_DNI"] = (TOA > 0) & ((DNI <= -4) | (DNI > TOANI))
    flag_df["T1C_erl_DNI"] = (TOA > 0) & (
            (DNI <= -2) | (DNI > 0.95 * TOANI * np.sin(GAMMA_S0) ** 0.2 + 10))

    flag_df["Kn"] = Kn
    flag_df["K"] = K
    flag_df["KT"] = KT

    # BSRN two-component test
    flag_df["T2C_bsrn_kt"] = ((TOA > 0) & (GHI > 50)) & (
                ((SZA < 75) & (K > 1.05)) |
                ((SZA >= 75) & (K > 1.1)))

    # SERI-QC two-component test
    flag_df["T2C_seri_kn_kt"] = (TOA > 0) & ((Kn > KT) | (Kn > 0.8) | (KT > 1.35))
    flag_df["T2C_seri_k_kt"] = (TOA > 0) & (
                ((KT < 0.6) & (K > 1.1)) | ((KT >= 0.6) & (K > 0.95)) | (KT > 1.35))

    # BSRN three-component test
    flag_df["T3C_bsrn_3cmp"] = (TOA > 0) & (
                ((SZA <= 75) & (GHI > 50) & (np.abs(GHI / GHI_est - 1) > 0.08)) | (
                    (SZA > 75) & (GHI > 50) & (np.abs(GHI / GHI_est - 1) > 0.15)))

    # Tracker off test
    GHI_clear = 0.8 * TOA
    DIF_clear = 0.165 * GHI_clear
    DNI_clear = GHI_clear - DIF_clear

    flag_df["tracker_off"] = ((SZA <= 85) &
                                    ((GHI_clear - GHI) / (GHI_clear + GHI) < 0.2) &
                                    ((DNI_clear - DNI) / (DNI_clear + DNI) > 0.95))
    # % % Combination of individual QC tests

    # if at least one of the test is positive, we flag all data (to be eventually refined)
    flag_df["QCtot"] = flag_df["T1C_erl_GHI"] | flag_df["T1C_erl_DIF"] | \
                       flag_df["T1C_erl_DNI"] | flag_df["T2C_bsrn_kt"] | \
                       flag_df["T2C_seri_kn_kt"] | flag_df["T2C_seri_k_kt"] | \
                       flag_df["T3C_bsrn_3cmp"] | flag_df["tracker_off"]

    # Evalue the share of flag data per day
    DailyFlagStat = flag_df["QCtot"].resample('D').sum() / (TOA > 0).resample('D').sum()

    # filter if at least on test fail or the number of flag per day exceeds the minimal share
    flag_df["QCfinal"] = flag_df["QCtot"] | np.in1d(flag_df.index.normalize(),
                                                    DailyFlagStat[DailyFlagStat > MinDailyShareFlag].index.normalize())

    return flag_df


def qc_stats(meas_df, sp_df, flag_df) :

    GHI = meas_df.GHI
    DIF = meas_df.DHI
    DNI = meas_df.BNI

    TOA = sp_df.TOA

    def percent(flags, *components) :
        filt = TOA > 0
        for component in components :
            filt = filt & (component > -2)

        tot = sum(filt)
        if tot == 0 :
            return np.nan
        else:
            return sum(flags & filt) / tot * 100

    return  {
        'T1C_erl_GHI': percent(flag_df.T1C_erl_GHI, GHI),
        'T1C_ppl_GHI': percent(flag_df.T1C_ppl_GHI, GHI),
        'T1C_erl_DIF': percent(flag_df.T1C_erl_DIF, DIF),
        'T1C_ppl_DIF': percent(flag_df.T1C_ppl_DIF, DIF),
        'T1C_erl_DNI': percent(flag_df.T1C_erl_DNI, DNI),
        'T1C_ppl_DNI': percent(flag_df.T1C_ppl_DNI, DNI),
        'T2C_bsrn_kt': percent(flag_df.T2C_bsrn_kt, GHI),
        'T2C_seri_knkt': percent(flag_df.T2C_seri_kn_kt, DNI, GHI),
        'T2C_seri_kkt': percent(flag_df.T2C_seri_k_kt, DIF, GHI),
        'T3C_bsrn': percent(flag_df.T3C_bsrn_3cmp, GHI, DIF, DNI)}


def cleanup_data(df, freq=None):
    """Cleanup and resample data"""

    # Default resolution : take the one from the source
    if freq is None:
        freq = df.attrs[GLOBAL_TIME_RESOLUTION_ATTR]

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



def write_flags(ncfile, flags_df) :

    # Parse CDL : use defaultdict to avoid warning
    # XXX try to not parse it twice and get it from above
    cdl = parse_cdl(read_res(CDL_PATH), attributes=DefaultDict(lambda : "-"))

    # Create var if not present yet
    if not QC_FLAGS_VAR in ncfile.variables :
        initVar(ncfile, cdl.variables[QC_FLAGS_VAR])

    qc_var = ncfile.variables[QC_FLAGS_VAR]

    # Build a dictionary of masks
    flag_masks = dict((flag, mask) for flag, mask in zip(qc_var.flag_meanings.split(), qc_var.flag_masks))

    info("Flag masks  : %s" % flag_masks)

    # Output
    out_masks = np.zeros(len(flags_df))

    for colname in flags_df.columns :
        if not colname in flag_masks :
            warning("Flag %s not found in QC flags DSL. Skipping" % colname)
            continue

        colvalues = flags_df[colname]

        out_masks += colvalues.values * flag_masks[colname]

    # Compute IDX
    dates = flags_df.index.values
    times_sec = datetime64_to_sec(ncfile, dates)
    time_idx = seconds_to_idx(ncfile, times_sec)

    # Assign flags
    time_var = getTimeVar(ncfile)
    max_time = len(time_var)

    out_idx = time_idx > max_time -1
    if np.any(out_idx) :
        warning("Index of of time range. Truncating %d values" % np.sum(out_idx))
        time_idx = time_idx[~out_idx]
        out_masks = out_masks[~out_idx]

    qc_var[time_idx] = out_masks

def compute_sun_pos(df, lat, lon, alt) :
    """Call sg2 on data"""

    # Compute geom & theoretical irradiance
    sp_df = sun_position(
        lat, lon, alt,
        df.index.min(),
        df.index.max(),
        freq=pd.infer_freq(df.index))

    return sp_df

def visual_qc(
        df,
        latitude = None,
        longitude = None,
        elevation = None,
        station_id = None,
        station_name = None,
        with_horizons = False,
        with_mc_clear = False):
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

    # Draw figures
    SolarRadVisualControl(
        meas_df=df,
        sp_df=sp_df,
        flag_df=flags_df,
        cams_df=cams_df,
        horizons=horizons,
        latitude=lat, longitude=lon, elevation=alt,
        station_id=station_id, station_name=station_name,
        ShowFlag=0)

