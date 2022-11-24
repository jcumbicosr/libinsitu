# -*- coding: utf-8 -*-
"""
Created on Thu Jun 23 10:09:54 2022

@author: y-m.saint-drenan
"""
from urllib.request import urlopen

import sg2
from appdirs import user_cache_dir
from matplotlib.pyplot import gca
from pandas import DataFrame

from libinsitu import CLIMATE_ATTRS, STATION_COUNTRY_ATTRS, NETWORK_NAME_ATTRS, STATION_ID_ATTRS, CDL_PATH, read_res, \
    DefaultDict, datetime64_to_sec, seconds_to_idx, getTimeVar, QC_FLAGS_VAR
from libinsitu.cdl import parse_cdl, initVar
from libinsitu.log import info, warning
from libinsitu.qc.graphs import FONT_SIZE, COLORMAP_DENSITY, COLORMAP_SHADING, MC_CLEAR_COLOR, plot_qc_flags
import os

from matplotlib.gridspec import GridSpec
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import datetime as dt
import pvlib


from libinsitu.common import LATITUDE_VAR, LONGITUDE_VAR, ELEVATION_VAR, STATION_NAME_VAR, GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR, GLOBAL_TIME_RESOLUTION_ATTR
from diskcache import Cache

from libinsitu.qc.graphs import plot_heatmap_timeseries, plot_ratio_heatmap

cachedir = user_cache_dir("libinsitu")
cache = Cache(cachedir)

MIN_VAL = -100.0
MAX_VAL = 5000.0

CAMS_EMAIL_ENV = "CAMS_EMAIL"


def _get_meta(df, keys) :
    """Try several keys to get Meta data"""
    for key in keys :
        if key in df.attrs :
            return df.attrs[key]
    return "-"

def get_version() :
    # TODO
    #return metadata.metadata('libinsitu')['Version']
    return "1.2"




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
        ShowFlag=-1) :
    """
     ShowFlag=-1     : only show non-flagged data
     ShowFlag=0      : show all data without filtering nor tagging flagged data
     ShowFlag=1      : show all data and highlight flagged data in red
    """

    CodeInfo = {
        "project": "CAMS2-73",
        "author": 'ARMINES, DLR',
        "name": 'libinsitu - Visual plausibility control',
        "vers": get_version()}

    # Get meta data
    latitude = meas_df.attrs[LATITUDE_VAR]
    longitude = meas_df.attrs[LONGITUDE_VAR]
    elevation = meas_df.attrs[ELEVATION_VAR]
    climate = _get_meta(meas_df, CLIMATE_ATTRS)
    country = _get_meta(meas_df, STATION_COUNTRY_ATTRS)
    source = _get_meta(meas_df, NETWORK_NAME_ATTRS)
    station_id = _get_meta(meas_df, STATION_ID_ATTRS)
    station = meas_df.attrs.get(STATION_NAME_VAR, "-")

    # Aliases
    index = meas_df.index
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

    NbDays = len(index[GHI > 0].normalize().unique())
    AvgGHI = sum(GHI[GHI > 0]) * 1 / 60 / NbDays * 365 / 1000
    AvgDHI = sum(DIF[DIF > 0]) * 1 / 60 / NbDays * 365 / 1000
    AvgDNI = sum(DNI[DNI > 0]) * 1 / 60 / NbDays * 365 / 1000
    AvailGHI = sum((GHI > -2) & (TOA > 0)) / sum((TOA > 0)) * 100
    AvailDHI = sum((DIF > -2) & (TOA > 0)) / sum(TOA > 0) * 100
    AvailDNI = sum((DNI > -2) & (TOA > 0)) / sum(TOA > 0) * 100

    DateStrStart = index[GHI > 0][0].strftime("%Y-%m-%d")
    DateStrEnd = index[GHI > 0][-1].strftime("%Y-%m-%d")

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
    def plot_ts(row_idx, label, data, xmax):
        plt.subplot(grid[row_idx, 0])
        plot_timeseries(label, data, TOA, xmax, ShowFlag, QCfinal)

    plot_ts(0, "GHI", GHI, 1400)
    plot_ts(1, "DNI", DNI, 1400)
    plot_ts(2, "DIF", DIF, 1000)

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

    gs2 = GridSpec(4, 2)
    gs2.update(
        left=0.33, right=0.66,
        bottom=0.03, top=0.98,
        hspace=0.2, wspace=0.05)

    Stat_Test = qc_stats(meas_df, sp_df, flag_df)

    PrmXi = [TOA, TOA, TOA]
    PrmXilbl = ['Top of atmosphere (TOA)', 'Top of atmosphere (TOA)', 'Top of atmosphere (TOA)']
    Prm_Vars = [GHI, DNI, DIF]
    PrmYi = ["GHI", "DNI", "DIF"]
    BSRN_PPL_Ks = [[1.5, 1.2, 100], [1, 0, 0], [0.95, 1.2, 50]]
    BSRN_ERL_Ks = [[1.2, 1.2, 50], [0.95, 0.2, 10], [0.75, 1.2, 30]]

    def mk_1c_legend(component_name) :
        return 'BSRN 1C ' + component_name + ": {:.2f}% / {:.2f}%".format(
            Stat_Test['T1C_ppl_' + component_name],
            Stat_Test['T1C_erl_' + component_name])

    def bsrn_1c(row, component, component_name, limits) :
        gs2.subplot(gs2[row, 0])
        plot_qc_flags(
            x=TOA, xlabel='Top of atmosphere (TOA) (W/m2)',
            y=component,
            ylabel=component_name + "(W/m2)",
            legend=mk_1c_legend(component_name),
            ShowFlag=ShowFlag, TOA=TOA, TOANI=TOANI, GAMMA_S0=GAMMA_S0, QCfinal=QCfinal, limits=limits)


    bsrn_1c(0, GHI, "GHI", [[1.5, 1.2, 100], [1.2, 1.2, 50]])
    bsrn_1c(1, DNI, "DNI", [[1, 0, 0], [0.95, 0.2, 10]])
    bsrn_1c(2, DIF, "DIF", [[0.95, 1.2, 50],[0.75, 1.2, 30]])


    # =====================================================================
    # % % Part5: BSRN 2C, 3C,SERI-QC tests
    # -> BSRN 2C
    # =====================================================================
    print(str(dt.datetime.now()) + ": --> QC: BSRN 2C ")
    ax22 = plt.subplot(gs2[0, 0])
    plt.text(12, 1.3, 'BSRN-2C' + ": {:.2f}% ".format(Stat_Test['T2C_bsrn_kt']))
    if ShowFlag == -1:
        idxPlot = (GHI > 50) & (SZA < 90) & (flag_df.QCfinal == 0)
    else:
        idxPlot = (GHI > 50) & (SZA < 90)

    hist, xedges, yedges = np.histogram2d(x=SZA[idxPlot], y=flag_df.K[idxPlot], bins=[200, 200],
                                          range=[[10, 95], [0, 1.25]])
    yedges, xedges = np.meshgrid(0.5 * (yedges[:-1] + yedges[1:]), 0.5 * (xedges[:-1] + xedges[1:]))
    im00 = plt.scatter(xedges[hist > 0], yedges[hist > 0], s=1, c=hist[hist > 0], cmap=COLORMAP_DENSITY)
    im00.set_clim(0, 0.8 * max(hist.flatten()))
    if ShowFlag == 1:
        plt.plot(SZA[flag_df.T2C_bsrn_kt], flag_df.K[flag_df.T2C_bsrn_kt], 'rs', markersize=1,
                 alpha=0.5, label='bsrn2C')
        ax22.legend(loc='lower left')
    # plt.plot(SZA[T2C_bsrn_kd],KT[T2C_bsrn_kd],'r.',markersize=1,label="Flagged data")
    plt.plot([0, 75, 75, 100], [1.05, 1.05, 1.1, 1.1], 'k--', alpha=0.4, linewidth=0.8)
    plt.xlabel('Solar zenith angle (°)', fontsize=FONT_SIZE)
    plt.ylabel('DIF/GHI (-)', fontsize=FONT_SIZE)
    plt.xlim((10, 95))
    plt.ylim((0, 1.4))

    # =====================================================================
    # % % -> SERI-Kn
    # =====================================================================
    print(str(dt.datetime.now()) + ": --> QC: SERI-Kn ")
    ax24 = plt.subplot(gs2[1, 1])
    plt.text(0.025, 0.92, 'SERI-kn' + ": {:.2f}% ".format(Stat_Test['T2C_seri_knkt']))
    if ShowFlag == -1:
        idxPlot = (DNI > 0) & (GHI > 0) & (SZA < 90) & (flag_df.QCfinal == 0)
    else:
        idxPlot = (DNI > 0) & (GHI > 0) & (SZA < 90)
    hist, xedges, yedges = np.histogram2d(x=flag_df.KT[idxPlot], y=flag_df.Kn[idxPlot], bins=[200, 200],
                                          range=[[0, 1.25], [0, 1]])
    yedges, xedges = np.meshgrid(0.5 * (yedges[:-1] + yedges[1:]), 0.5 * (xedges[:-1] + xedges[1:]))
    im00 = plt.scatter(xedges[hist > 0], yedges[hist > 0], s=1, c=hist[hist > 0], cmap=COLORMAP_DENSITY)
    im00.set_clim(0, 0.1 * max(hist.flatten()))
    plt.plot([0, 0.8, 1.35, 1.35], [0, 0.8, 0.8, 0], 'k--', alpha=0.4, linewidth=0.8)
    if ShowFlag == 1:
        plt.plot(flag_df.KT[flag_df.T2C_seri_kn_kt], flag_df.Kn[flag_df.T2C_seri_kn_kt], 'r.',
                 markersize=0.9, label='SERI-kn')
        ax24.legend(loc='upper right')
    plt.xlabel('GHI/TOA (-)', fontsize=FONT_SIZE)
    plt.ylabel('DNI/TOANI (-)', fontsize=FONT_SIZE)
    plt.xlim((0, 1.5))
    plt.ylim((0, 1.))

    # -> SERI-K
    print(str(dt.datetime.now()) + ": --> QC: SERI-K ")
    ax26 = plt.subplot(gs2[2, 1])
    plt.text(0.025, 1.3, 'SERI-K' + ": {:.2f}% ".format(Stat_Test['T2C_seri_kkt']))
    if ShowFlag == -1:
        idxPlot = (DIF > 0) & (GHI > 0) & (SZA < 90) & (flag_df.QCfinal == 0)
    else:
        idxPlot = (DIF > 0) & (GHI > 0) & (SZA < 90)
    hist, xedges, yedges = np.histogram2d(x=flag_df.KT[idxPlot], y=flag_df.K[idxPlot], bins=[200, 200],
                                          range=[[0, 1.2], [0, 1.2]])
    yedges, xedges = np.meshgrid(0.5 * (yedges[:-1] + yedges[1:]), 0.5 * (xedges[:-1] + xedges[1:]))
    im00 = plt.scatter(xedges[hist > 0], yedges[hist > 0], s=1, c=hist[hist > 0], cmap=COLORMAP_DENSITY)
    im00.set_clim(0, 0.1 * max(hist.flatten()))
    plt.plot([0, 0.6, 0.6, 1.35, 1.35], [1.1, 1.1, 0.95, 0.95, 0], 'k--', alpha=0.4, linewidth=0.8)
    if ShowFlag == 1:
        plt.plot(flag_df.KT[flag_df.T2C_seri_k_kt], flag_df.K[flag_df.T2C_seri_k_kt], 'r.',
                 markersize=0.9, label='seri-kkt')
        ax26.legend(loc='upper right')
    plt.xlabel('GHI/TOA (-)', fontsize=FONT_SIZE)
    plt.ylabel('DIF/GHI (-)', fontsize=FONT_SIZE)
    plt.xlim((0, 1.5))
    plt.ylim((0, 1.45))

    print(str(dt.datetime.now()) + ": --> QC: BSRN closure ymeas=f(yest)")
    ax27 = plt.subplot(gs2[3, 0])
    plt.text(30, 1300, 'BSRN closure' + ": {:.2f}% ".format(Stat_Test['T3C_bsrn']))
    if ShowFlag == -1:
        idxPlot = (DIF > 0) & (GHI > 50) & (SZA < 90) & (flag_df.QCfinal == 0)
    else:
        idxPlot = (DIF > 0) & (GHI > 50) & (SZA < 90)
    hist, xedges, yedges = np.histogram2d(x=GHI[idxPlot], y=GHI_est[idxPlot], bins=[500, 500],
                                          range=[[0, 1500], [0, 1500]])
    yedges, xedges = np.meshgrid(0.5 * (yedges[:-1] + yedges[1:]), 0.5 * (xedges[:-1] + xedges[1:]))
    im00 = plt.scatter(xedges[hist > 0], yedges[hist > 0], s=1, c=hist[hist > 0], cmap=COLORMAP_DENSITY)
    im00.set_clim(0, 0.1 * max(hist.flatten()))
    if ShowFlag == 1:
        ax27.plot(GHI[flag_df.T3C_bsrn_3cmp], GHI_est[flag_df.T3C_bsrn_3cmp], 'r.',
                  markersize=1, label='closure', alpha=0.1)
        ax27.legend(loc='lower right')
    ax27.plot(np.array([0, 1400]), 0.85 * np.array([0, 1400]), 'k-.', alpha=0.4, linewidth=1.0)
    plt.plot(np.array([0, 1400]), 0.92 * np.array([0, 1400]), 'k--', alpha=0.4, linewidth=0.8)
    plt.plot(np.array([0, 1400]), 1.08 * np.array([0, 1400]), 'k--', alpha=0.4, linewidth=0.8)
    plt.plot(np.array([0, 1400]), 1.15 * np.array([0, 1400]), 'k-.', alpha=0.4, linewidth=1.0)
    plt.xlabel('GHI (W/m2)', fontsize=FONT_SIZE)
    plt.ylabel('DIF+DNI*CSZA (W/m2)', fontsize=FONT_SIZE)
    plt.ylim((0, 1400))
    plt.xlim((0, 1400))

    print(str(dt.datetime.now()) + ": --> QC: BSRN closure ratio=f(SZA)")
    ax28 = plt.subplot(gs2[3, 0])
    plt.text(8, 0.52, "BSRN closure: {:.2f}% ".format(Stat_Test['T3C_bsrn']))
    if ShowFlag == -1:
        idxPlot = (DIF > 0) & (GHI > 50) & (SZA < 90) & (flag_df.QCfinal == 0)
    else:
        idxPlot = (DIF > 0) & (GHI > 50) & (SZA < 90)
    hist, xedges, yedges = np.histogram2d(x=SZA[idxPlot], y=GHI[idxPlot] / GHI_est[idxPlot],
                                          bins=[200, 200], range=[[0, 90], [0, 2]])
    yedges, xedges = np.meshgrid(0.5 * (yedges[:-1] + yedges[1:]), 0.5 * (xedges[:-1] + xedges[1:]))
    im00 = plt.scatter(xedges[hist > 0], yedges[hist > 0], s=1, c=hist[hist > 0], cmap=COLORMAP_DENSITY)
    im00.set_clim(0, 0.5 * max(hist.flatten()))
    if ShowFlag == 1:
        plt.plot(SZA[flag_df.T3C_bsrn_3cmp],
                 GHI[flag_df.T3C_bsrn_3cmp] / GHI_est[flag_df.T3C_bsrn_3cmp], 'r.',
                 markersize=1, label='closure', alpha=0.1)
        ax28.legend(loc='lower right')
    plt.plot([10, 75, 75, 90, 90, 75, 75, 10], [1.08, 1.08, 1.15, 1.15, 0.85, 0.85, 0.92, 0.92], 'k--', alpha=0.4,
             linewidth=0.8)
    ax28.set_xlabel('Solar zenith angle (°)', fontsize=FONT_SIZE)
    ax28.set_ylabel('GHI/(DIF+DNI*CSZA) (-)', fontsize=FONT_SIZE)
    ax28.set_yticks(np.arange(0.2, 2, 0.2))
    ax28.set_ylim((0.5, 1.5))

    cb_ax = fig.add_axes([0.38, 0.04, 0.28, 0.01])
    cbar = fig.colorbar(im00, cax=cb_ax, orientation='horizontal', label='point density (-)')
    cbar.set_ticks([])

    # **************************** Third column *******************************
    print(str(dt.datetime.now()) + ": --> QC: print general infos")

    Y0 = 0.90
    dY = 0.15
    gs0 = GridSpec(9, 12)
    gs0.update(left=0.015, right=0.99, bottom=0.05, top=0.99, hspace=0.01, wspace=0.05)

    ax01 = plt.subplot(gs0[0, 8])
    ax01.text(0.01, Y0 - 0 * dY, 'Source: ' + source, size=FONT_SIZE)
    ax01.text(0.01, Y0 - 1 * dY, station_id + ': ' + station, size=FONT_SIZE)  # 'ID/ Station'
    ax01.text(0.01, Y0 - 2 * dY, "latitude: {:.2f}°".format(latitude), size=FONT_SIZE)
    ax01.text(0.01, Y0 - 3 * dY, "longitude: {:.2f}°".format(longitude), size=FONT_SIZE)
    ax01.text(0.01, Y0 - 4 * dY, "altitude: {:.0f}m".format(elevation), size=FONT_SIZE)
    ax01.text(0.01, Y0 - 5 * dY, "country: {} ".format(country), size=FONT_SIZE)
    ax01.text(0.01, Y0 - 6 * dY, "Köppen-Geiger climate: {}".format(climate), size=FONT_SIZE)
    ax01.axis('off')

    ax02 = plt.subplot(gs0[0, 10])
    ax02.text(0.01, Y0 - 1 * dY, '.         Period:  {} - {}'.format(DateStrStart, DateStrEnd), size=FONT_SIZE)
    ax02.text(0.01, Y0 - 2 * dY, '  Annual sums:', size=FONT_SIZE)
    ax02.text(0.01, Y0 - 3 * dY, 'GHI:   {0:.0f} kWh/m2'.format(AvgGHI), size=FONT_SIZE)
    ax02.text(0.01, Y0 - 4 * dY, 'DIF:   {0:.0f} kWh/m2'.format(AvgDHI), size=FONT_SIZE)
    ax02.text(0.01, Y0 - 5 * dY, 'DNI:   {0:.0f} kWh/m2'.format(AvgDNI), size=FONT_SIZE)
    ax02.text(0.01, Y0 - 6 * dY, CodeInfo["name"] + ' ' + CodeInfo["vers"] + '', size=FONT_SIZE)
    ax02.axis('off')

    ax03 = plt.subplot(gs0[0, 11])
    ax03.text(0.01, Y0 - 2 * dY, '        Days of data: {}'.format(NbDays), size=FONT_SIZE)
    # ax03.text(0.01,Y0-2*dY,'# Flagged: {0:.1f}% '.format(Stat_FlaggedQCFinal),size=FONT_SIZE)
    ax03.text(0.01, Y0 - 3 * dY, '      ({0:.1f}% availability)'.format(AvailGHI), size=FONT_SIZE)
    ax03.text(0.01, Y0 - 4 * dY, '      ({0:.1f}% availability)'.format(AvailDHI), size=FONT_SIZE)
    ax03.text(0.01, Y0 - 5 * dY, '      ({0:.1f}% availability)'.format(AvailDNI), size=FONT_SIZE)
    ax03.axis('off')

    # ax2XXX = plt.axes([0.75, 0.88, 0.08, 0.07])
    # img = plt.imread('./libCAMS_ymsd/CAMSlogo.png')
    # ax2XXX .imshow(img)
    # plt.axis('off')

    print(str(dt.datetime.now()) + ": --> QC: histograms of K, Kn & KT")
    gs3b = GridSpec(9, 9)
    gs3b.update(left=0.075, right=0.98, bottom=0.001, top=0.97, hspace=0.025, wspace=0.00)

    ax31a = plt.subplot(gs3b[1:3, 6])
    # TODO: replace flag_df.QCfinal par flag_df.QCGHI
    idxPlot_qc = (GHI > 5) & (SZA < 90) & (flag_df.QCfinal == 0)
    idxPlot_all = (GHI > 5) & (SZA < 90)
    hist_qc, xedges = np.histogram(flag_df.KT[idxPlot_qc], bins=500, range=[0, 1.2])
    hist_all, xedges = np.histogram(flag_df.KT[idxPlot_all], bins=500, range=[0, 1.2])
    xval = (xedges[1:] + xedges[:-1]) / 2
    ax31a.fill_between(xval, 0 * xval, hist_all, color=[204 / 255, 0 / 255, 0 / 255], label='flagged dara')
    ax31a.fill_between(xval, 0 * xval, hist_qc, color=[102 / 255, 178 / 255, 255 / 255], label='valid data')
    # ax31a.legend(loc='upper right')
    ax31a.set_ylabel('count')
    ax31a.set_xlim([0, 1.1])
    ax31a.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax31a.set_xticklabels([0, 0.2, 0.4, 0.6, 0.8, 1])
    ax31a.set_xlabel('GHI/TOA')
    ax31a.set_yticks([])

    ax31b = plt.subplot(gs3b[1:3, 7])
    # TODO: replace flag_df.QCfinal par flag_df.QCDNI
    idxPlot_qc = (DNI > 5) & (SZA < 90) & (flag_df.QCfinal == 0)
    idxPlot_all = (DNI > 5) & (SZA < 90)
    hist_qc, xedges = np.histogram(flag_df.Kn[idxPlot_qc], bins=500, range=[0, 1.2])
    hist_all, xedges = np.histogram(flag_df.Kn[idxPlot_all], bins=500, range=[0, 1.2])
    xval = (xedges[1:] + xedges[:-1]) / 2
    ax31b.fill_between(xval, 0 * xval, hist_all, color=[204 / 255, 0 / 255, 0 / 255], label='flagged dara')
    ax31b.fill_between(xval, 0 * xval, hist_qc, color=[102 / 255, 178 / 255, 255 / 255], label='valid data')
    # ax31b.legend(loc='upper right')
    ax31b.set_xlabel('DNI/TOANI')
    ax31b.set_xlim([0, 1.1])
    ax31b.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax31b.set_xticklabels([0, 0.2, 0.4, 0.6, 0.8, 1])
    ax31b.set_yticks([])

    ax31c = plt.subplot(gs3b[1:3, 8])
    # TODO: replace flag_df.QCfinal par flag_df.QCDIF
    idxPlot_qc = (DIF > 5) & (SZA < 90) & (flag_df.QCfinal == 0)
    idxPlot_all = (DIF > 5) & (SZA < 90)
    hist_qc, xedges = np.histogram(flag_df.K[idxPlot_qc], bins=500, range=[0, 1.2])
    hist_all, xedges = np.histogram(flag_df.K[idxPlot_all], bins=500, range=[0, 1.2])
    xval = (xedges[1:] + xedges[:-1]) / 2
    ax31c.fill_between(xval, 0 * xval, hist_all, color=[204 / 255, 0 / 255, 0 / 255], label='flagged dara')
    ax31c.fill_between(xval, 0 * xval, hist_qc, color=[102 / 255, 178 / 255, 255 / 255], label='valid data')
    ax31c.legend(loc='upper left')
    ax31c.set_xlim([0, 1.1])
    ax31c.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax31c.set_xticklabels([0, 0.2, 0.4, 0.6, 0.8, 1])
    ax31c.set_xlabel('DIF/GHI')
    ax31c.set_yticks([])


    if cams_df is None :
        gs3 = GridSpec(7, 3)
        shadow_row = 3
    else:
        gs3 = GridSpec(9, 3)
        shadow_row = 5

    gs3.update(left=0.0, right=0.99, bottom=0.05, top=0.875, hspace=0.1, wspace=0.2)

    # print(str(dt.datetime.now())+": --> QC: planarity check")

    if cams_df is not None :

        print(str(dt.datetime.now()) + ": --> QC: Verification of the pyranometer tilt angle")
        # NB: the calculation can be optimized to run faster

        # Aliases
        CLEAR_SKY_GHI = cams_df.CLEAR_SKY_GHI
        CLEAR_SKY_DNI = cams_df.CLEAR_SKY_DNI


        isClearSky = pvlib.clearsky.detect_clearsky(GHI, CLEAR_SKY_GHI)
        ax31 = plt.subplot(gs3[3:5, 2])
        YYL = [0.8, 1.2]
        if ShowFlag == -1:
            idxPlot = isClearSky & (DIF > 0) & (GHI > 100) & (SZA < 90) & (flag_df.QCfinal == 0) & \
                      (CLEAR_SKY_GHI.values > 50) & (GHI.values > 50) & (CLEAR_SKY_DNI.values > 0)
        else:
            idxPlot = isClearSky & (DIF > 0) & (GHI > 100) & (SZA < 90) & \
                      (CLEAR_SKY_GHI.values > 50) & (GHI.values > 50) & (CLEAR_SKY_DNI.values > 0)
        vSAA = ALPHA_S.values
        if latitude < 0:
            vSAA[vSAA * 180 / np.pi > 180] = vSAA[vSAA * 180 / np.pi > 180] - 2 * np.pi

        xPlot = vSAA * 180 / np.pi
        yPlot = np.zeros(DNI.shape)
        # yPlot[QC_df.CLEAR_SKY_DNI.values>0]=QC_df.GHI.values[QC_df.CLEAR_SKY_DNI.values>0]/QC_df.CLEAR_SKY_GHI.values[QC_df.CLEAR_SKY_DNI.values>0]

        if (latitude < 0):
            angle_filter = np.abs(vSAA * 180 / np.pi) < 60
        else:
            angle_filter = np.abs(vSAA * 180 / np.pi - 180) < 60

        kc = GHI[idxPlot & angle_filter & (CLEAR_SKY_DNI.values > 0)] / \
             CLEAR_SKY_GHI[idxPlot & angle_filter & (CLEAR_SKY_DNI.values > 0)]

        S = kc.resample('1D', label='left').sum()
        C = kc.resample('1D', label='left').count()
        Dailydata = pd.DataFrame({'Avgkc': S[C > 30] / C[C > 30]}, index=C.index)
        data4plot = pd.DataFrame(
            {'kc': GHI[idxPlot] / CLEAR_SKY_GHI[idxPlot], \
             'SAA': vSAA[idxPlot] * 180 / np.pi, \
             'day': meas_df[idxPlot].index.floor(freq='D')}, \
            index=meas_df[idxPlot].index)
        data4plot = data4plot.join(Dailydata, on='day', how='left')
        ix = data4plot.Avgkc > 0
        xPlot = data4plot.SAA[ix].values
        yPlot = data4plot.kc[ix].values / data4plot.Avgkc[ix].values

        if latitude >= 0:
            dxx = 0
        else:
            dxx = 180
        hist, xedges, yedges = np.histogram2d(x=xPlot, y=yPlot, bins=[180, 100], range=[[0 - dxx, 360 - dxx], YYL])
        plt.plot([0 - dxx, 360 - dxx], [1, 1], 'r--', alpha=0.4, linewidth=0.8)
        plt.xlim((0 - dxx, 360 - dxx))
        ax31.text(5 - dxx, 0.97 * YYL[1], 'Test of the horizontality of the GHI sensor')
        yedges, xedges = np.meshgrid(0.5 * (yedges[:-1] + yedges[1:]), 0.5 * (xedges[:-1] + xedges[1:]))
        im00 = plt.scatter(xedges[hist > 0], yedges[hist > 0], s=3, c=hist[hist > 0], cmap=COLORMAP_DENSITY)
        im00.set_clim(0, 0.7 * max(hist.flatten()))
        plt.ylabel('kc/kc_daily (-)', fontsize=FONT_SIZE)
        plt.xlabel('Solar azimuth angle (°)', fontsize=FONT_SIZE)
        ax31.set_ylim(YYL)
        plt.colorbar(im00, label='point density (-)')



    print(str(dt.datetime.now()) + ": --> QC: Shadow analysis (GHI)")
    idxSC = (GAMMA_S0 > 1 / 50) & (flag_df.QCfinal == 0)
    vSEA =  GAMMA_S0[idxSC]
    vSAA = ALPHA_S[idxSC]
    if latitude < 0:
        vSAA[vSAA * 180 / np.pi > 180] = vSAA[vSAA * 180 / np.pi > 180] - 2 * np.pi

    SELMax = 45

    ax32 = plt.subplot(gs3[shadow_row:shadow_row+2, 2])
    vKT = GHI[idxSC] / TOA[idxSC]
    idx_sort = np.argsort(vKT.values)
    im32 = plt.scatter(vSAA[idx_sort] * 180 / np.pi, vSEA[idx_sort] * 180 / np.pi, s=1, c=vKT[idx_sort], cmap=COLORMAP_SHADING,
                       marker='s', alpha=.5)
    plt.ylabel('Solar elevation angle [°]', fontsize=FONT_SIZE)
    plt.xlabel('Solar azimuth angle [°]', fontsize=FONT_SIZE)
    if horizons is not None:
        plt.plot(horizons.AZIMUT, horizons.ELEVATION, '-', linewidth=1, alpha=0.6, c='red')
        plt.plot(horizons.AZIMUT - 360, horizons.ELEVATION, '-', linewidth=1, alpha=0.6, c='red')
    if latitude < 0:
        dxx = 180
    else:
        dxx = 0
    plt.xlim((45 - dxx, 315 - dxx))
    ax32.text(50 - dxx, 0.92 * SELMax, 'shadow analysis')
    im32.set_clim(0, 0.85)
    plt.ylim((0, SELMax))
    plt.colorbar(im32, label='GHI/TOA (-)')

    print(str(dt.datetime.now()) + ": --> QC: Shadow analysis (DNI)")
    ax33 = plt.subplot(gs3[shadow_row+2:shadow_row+4, 2])
    vKN = DNI[idxSC] / TOANI[idxSC]
    idx_sort = np.argsort(vKN.values)
    im33 = plt.scatter(vSAA[idx_sort] * 180 / np.pi, vSEA[idx_sort] * 180 / np.pi, s=1, c=vKN[idx_sort], cmap=COLORMAP_SHADING,
                       marker='s', alpha=.5)
    plt.ylabel('Solar elevation angle [°]', fontsize=FONT_SIZE)
    plt.xlabel('Solar azimuth angle [°]', fontsize=FONT_SIZE)
    if horizons is not None :
        plt.plot(horizons.AZIMUT, horizons.ELEVATION, '-', linewidth=1, alpha=0.6, c='red')
        plt.plot(horizons.AZIMUT - 360, horizons.ELEVATION, '-', linewidth=1, alpha=0.6, c='red')
    if latitude < 0:
        dxx = 180
    else:
        dxx = 0
    plt.xlim((45 - dxx, 315 - dxx))
    ax33.text(50 - dxx, 0.92 * SELMax, 'shadow analysis')
    im33.set_clim(0, 0.65)
    plt.ylim((0, SELMax))
    plt.colorbar(im33, label='DNI/TOANI (-)')


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
    #CLEAR_SKY_GHI = sp_df.CLEAR_SKY_GHI
    #CLEAR_SKY_DNI = sp_df.CLEAR_SKY_DNI

    GHI_est = DIF + DNI * np.cos(sp_df.THETA_Z)
    SZA = sp_df.THETA_Z * 180 / np.pi

    size = len(meas_df.GHI)

    KT = np.zeros(size)
    KT[TOA >= 1] = GHI[TOA >= 1] / TOA[TOA >= 1]

    Kn = np.zeros(size)
    Kn[TOANI >= 1] = DNI[TOANI >= 1] / TOANI[TOANI >= 1]

    K = np.zeros(size)
    K[GHI >= 1] = DIF[GHI >= 1] / GHI[GHI >= 1]

    #kc = np.zeros(shape)
    #kc[CLEAR_SKY_GHI >= 1] = GHI[CLEAR_SKY_GHI >= 1] / CLEAR_SKY_GHI[CLEAR_SKY_GHI >= 1]

    #kbc = np.zeros(shape)
    #kbc[CLEAR_SKY_DNI >= 1] = DNI[CLEAR_SKY_DNI >= 1] / CLEAR_SKY_DNI[CLEAR_SKY_DNI >= 1]

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
    #flag_df["kc"] = kc
    #flag_df["kbc"] = kbc
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

def compute_sun_pos(df) :
    """Call sg2 on data"""

    # Get meta data
    lat = float(df.attrs[LATITUDE_VAR])
    lon = float(df.attrs[LONGITUDE_VAR])
    alt = float(df.attrs[ELEVATION_VAR])

    # Compute geom & theoretical irradiance
    sp_df = sun_position(
        lat, lon, alt,
        df.index.min(),
        df.index.max(),
        freq=pd.infer_freq(df.index))

    return sp_df

def visual_qc(df, with_horizons=False, with_mc_clear=False):
    """
    Generates matplotlib graphs for visual QC

    :param df: Dataframe of input irradiance (GHI, DHI, BNI), obtained with netcdf_to_dataframe(... rename_cols=True)
    :param with_horizons: True to compute horizons (requires network)
    :param with_mc_clear: True to compute mc_clear from SODA (requires credentials and network).
      Requires to register to SODA (https://www.soda-pro.com/web-services/radiation/cams-radiation-service)
      and provides email in CAMS_EMAIL env var

    """
    # Resample to the minute to produce graph
    resolution_sec = 60

    # Clean data
    df = cleanup_data(df, resolution_sec)

    # Get meta data
    lat = float(df.attrs[LATITUDE_VAR])
    lon = float(df.attrs[LONGITUDE_VAR])
    alt = float(df.attrs[ELEVATION_VAR])

    # Compute geom & theoretical irradiance
    sp_df = compute_sun_pos(df)

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
        df,
        sp_df,
        flags_df,
        cams_df,
        horizons,
        ShowFlag=0)

