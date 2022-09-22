# -*- coding: utf-8 -*-
"""
Created on Thu Jun 23 10:09:54 2022

@author: y-m.saint-drenan
"""
import hashlib
from logging import warn
from urllib.request import urlopen

import sg2
from appdirs import user_cache_dir

from libinsitu.log import info, warning
import os

from matplotlib.gridspec import GridSpec
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import datetime as dt
import matplotlib.dates as mdates
import copy
import matplotlib as mpl
import pvlib
from matplotlib import cm

from libinsitu.common import LATITUDE_VAR, LONGITUDE_VAR, ELEVATION_VAR, CLIMATE_ATTR, STATION_NAME_VAR, \
    STATION_ID_ATTR, NETWORK_NAME_ATTR, STATION_COUNTRY_ATTR, GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR, TIME_RESOLUTION_ATTR
from diskcache import Cache

cachedir = user_cache_dir("libinsitu")
info("Cache folder : %s", cachedir)
cache = Cache(cachedir)

HORIZON_ATTR = "HZ"
MIN_VAL = -100.0
MAX_VAL = 5000.0

CAMS_EMAIL_ENV = "CAMS_EMAIL"



def SolarRadVisualControl(QC_df, Stat_Test, flag_df, ShowFlag=-1, ShowMcClear=False):
    """
     ShowFlag=-1     : only show non-flagged data
     ShowFlag=0      : show all data without filtering nor tagging flagged data
     ShowFlag=1      : show all data and highlight flagged data in red
    """

    CodeInfo = {
        "project": "CAMS2-73",
        "author": 'ARMINES, DLR',
        "name": 'Visual plausibility control',
        "vers": 'v0.5 (2022-08-05)'}

    # Get meta data
    latitude = QC_df.attrs[LATITUDE_VAR]
    longitude = QC_df.attrs[LONGITUDE_VAR]
    elevation = QC_df.attrs[ELEVATION_VAR]
    climate = QC_df.attrs.get(CLIMATE_ATTR, "-")
    country = QC_df.attrs.get(STATION_COUNTRY_ATTR, "-")
    source = QC_df.attrs.get(NETWORK_NAME_ATTR, "-")
    station_id = QC_df.attrs.get(STATION_ID_ATTR, "-")
    station = QC_df.attrs.get(STATION_NAME_VAR, "-")

    horizons = QC_df.attrs[HORIZON_ATTR]
    #resolution_min = QC_df.attrs[TIME_RESOLUTION_ATTR] // 60

    def makeCustomColormap(NWhite=2, ColorGrey=0.8, NGrey=25, cmColor='viridis', NColor=100):
        import numpy as np
        from matplotlib.colors import ListedColormap
        cmpGrey = ColorGrey * np.ones((1, 3))
        cmpColor = cm.get_cmap(cmColor, 256)(np.linspace(0, 1, NColor + 10))[10:, :]
        M0 = np.hstack((np.ones((NGrey, 1)) @ cmpGrey + (np.expand_dims((np.linspace(0, 1, NGrey)), axis=0).T) @ (
                    cmpColor[0, 0:3] - cmpGrey), np.ones((NGrey, 1))))
        cmWGC = ListedColormap(np.vstack((np.ones((NWhite, 4)), M0, cmpColor)), name='jet_ymsd')
        return cmWGC

    def conv2(v1, v2, m, mode='same'):
        import numpy as np
        tmp = np.apply_along_axis(np.convolve, 0, m, v1, mode)
        return np.apply_along_axis(np.convolve, 1, tmp, v2, mode)

    FSZ = 8

    cm2DPlots = makeCustomColormap(NWhite=2, ColorGrey=0.8, NGrey=25, cmColor='cividis', NColor=100)
    cmDensity = makeCustomColormap(NWhite=1, ColorGrey=0.8, NGrey=50, cmColor='viridis', NColor=200)
    cmShading = makeCustomColormap(NWhite=2, ColorGrey=0.8, NGrey=25, cmColor='cividis', NColor=100)

    print(str(dt.datetime.now()) + ": --> QC: visual plot preparation")
    NbDays = len(QC_df.index[QC_df.GHI > 0].normalize().unique())
    AvgGHI = sum(QC_df.GHI[QC_df.GHI > 0]) * 1 / 60 / NbDays * 365 / 1000
    AvgDHI = sum(QC_df.DIF[QC_df.DIF > 0]) * 1 / 60 / NbDays * 365 / 1000
    AvgDNI = sum(QC_df.DNI[QC_df.DNI > 0]) * 1 / 60 / NbDays * 365 / 1000
    AvailGHI = sum((QC_df.GHI > -2) & (QC_df.TOA > 0)) / sum((QC_df.TOA > 0)) * 100
    AvailDHI = sum((QC_df.DIF > -2) & (QC_df.TOA > 0)) / sum(QC_df.TOA > 0) * 100
    AvailDNI = sum((QC_df.DNI > -2) & (QC_df.TOA > 0)) / sum(QC_df.TOA > 0) * 100
    DateStrStart = QC_df.index[QC_df.GHI > 0][0].strftime("%Y-%m-%d")
    DateStrEnd = QC_df.index[QC_df.GHI > 0][-1].strftime("%Y-%m-%d")

    QC_df["GHI_est"] = QC_df.DIF + QC_df.DNI * np.cos(QC_df.THETA_Z)

    fig = plt.figure(figsize=(19.2, 9.93))

    # % % Part 1 (column 1): time series and 2D plots of the three different components
    if ShowMcClear:
        gs1a = GridSpec(9, 6)
    else:
        gs1a = GridSpec(8, 6)

    gs1a.update(left=0.035, right=0.97, bottom=0.03, top=0.98, hspace=0.02, wspace=0.05)

    x_lims = mdates.date2num([QC_df.index[0].date(), QC_df.index[-1].date()])
    y_lims = [0, 24]
    nb_min = 24 * 60
    nb_days = np.int64(QC_df.shape[0] / nb_min)
    PrmCell = ['GHI', 'DNI', 'DIF']

    # =====================================================================
    # plot of the times series of GHI, DNI and DIF
    # =====================================================================

    YlimMax = [1400, 1400, 1000]
    for ii, Prm in enumerate(PrmCell):
        # ax_2Di = plt.subplot(gs1a[2*ii, 0:2])
        ax_2Di = plt.subplot(gs1a[ii, 0:2])
        if ShowFlag == -1:
            idxPlot = (QC_df.TOA > 0) & (QC_df[Prm].values > -50 & (flag_df.QCfinal == 0))
        else:
            idxPlot = (QC_df.TOA > 0) & (QC_df[Prm].values > -50)

        ax_2Di.plot(QC_df[Prm].index[idxPlot], QC_df[Prm].values[idxPlot], color='b', alpha=0.8, label='meas.', lw=0.2)

        plt.ylim((0, YlimMax[ii]))
        plt.xlim((QC_df.index.values[0], QC_df.index.values[-1]))
        ax_2Di.set_ylabel(Prm + " (W/m2)", size=8)
        plt.setp(ax_2Di.get_xticklabels(), visible=False)

        if ShowFlag == 1:
            timeLMT = QC_df.index.values + np.timedelta64(int(longitude / 360 * 24 * 60 * 60), 's')
            day = timeLMT.astype('datetime64[D]').astype(QC_df.index.values.dtype)
            TOD = 1 + (timeLMT - day).astype('timedelta64[s]').astype('double') / 60 / 60

            plt.plot(day[flag_df['QCfinal']], TOD[flag_df['QCfinal']], 'rs', markersize=1, alpha=0.8, label='flag')
            plt.setp(ax_2Di.get_xticklabels(), visible=False)

        # ax_2Di.text(mdates.date2num(QC_df.index)[0]+5,0.8*YlimMax[ii],Prm,size=10)

    # plot of the 2D heatmaps of GHI, DNI and DIF
    ClimMax = [700, 900, 700]
    for ii, Prm in enumerate(PrmCell):

        print(str(dt.datetime.now()) + ": --> QC: 2D plot" + Prm)
        # ax_2Di = plt.subplot(gs1a[2*ii+1, 0:2])
        ax_2Di = plt.subplot(gs1a[3 + ii, 0:2])

        if ShowFlag == -1:
            idxPlot = (QC_df.TOA > 0) & (flag_df.QCfinal == 0)
        else:
            idxPlot = (QC_df.TOA > 0)

        Val4Plot = copy.deepcopy(QC_df[Prm].values)
        # Val4Plot[idxPlot==0]=np.nan
        M2D = np.reshape(Val4Plot, (nb_days, nb_min)).T
        deltaT = int(np.round(longitude / 360 * 24 * 60))
        M2D2 = np.roll(M2D, deltaT, axis=0)
        M2D2[M2D2 < -100] = np.nan

        im00 = ax_2Di.imshow(M2D2,
                             extent=[x_lims[0], x_lims[1], y_lims[1], y_lims[0]],
                             aspect='auto', cmap=cm2DPlots, alpha=1)
        ax_2Di.xaxis_date()
        plt.setp(ax_2Di.get_xticklabels(), visible=False)
        ax_2Di.set_yticks(np.arange(0, 23, 6))
        ax_2Di.set_ylabel('Time of the day', fontsize=FSZ)
        SR_h_lt = QC_df.SR_h + float(deltaT) / 60
        SR_h_lt[SR_h_lt > 24] = SR_h_lt[SR_h_lt > 24] - 24
        SR_h_lt[SR_h_lt < 0] = SR_h_lt[SR_h_lt < 0] + 24
        SS_h_lt = QC_df.SS_h + float(deltaT) / 60
        SS_h_lt[SS_h_lt > 24] = SS_h_lt[SS_h_lt > 24] - 24
        SS_h_lt[SS_h_lt < 0] = SS_h_lt[SS_h_lt < 0] + 24

        ax_2Di.plot(mdates.date2num(QC_df.index), SR_h_lt, 'k--', linewidth=0.75, alpha=0.8)
        ax_2Di.plot(mdates.date2num(QC_df.index), SS_h_lt, 'k--', linewidth=0.75, alpha=0.8)
        im00.set_clim(0, ClimMax[ii])
        ax_2Di.text(mdates.date2num(QC_df.index)[0] + 5, 21, Prm, size=10)

        mpl.rcParams['ytick.labelsize'] = FSZ
        plt.xlim((QC_df.index.values[0], QC_df.index.values[-1]))
        plt.ylim((0, 24))
        # plt.gca().invert_yaxis()

        if ShowFlag == 1:
            timeLMT = QC_df.index.values + np.timedelta64(int(longitude / 360 * 24 * 60 * 60), 's')
            day = timeLMT.astype('datetime64[D]').astype(QC_df.index.values.dtype)
            TOD = 1 + (timeLMT - day).astype('timedelta64[s]').astype('double') / 60 / 60

            plt.plot(day[flag_df['QCfinal']], TOD[flag_df['QCfinal']], 'rs', markersize=1, alpha=0.8, label='flag')
            ax_2Di.legend(loc='lower right')

    # =====================================================================
    # % % Part3 (column 1): time series of ratios for verifying sensors' calibration
    # =====================================================================
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

    MVal = [QC_df.DIF / QC_df.GHI, \
            QC_df.GHI / QC_df.GHI_est, \
            QC_df.GHI / QC_df.CLEAR_SKY_GHI]
    MIX = [(QC_df.DIF > 0) & (QC_df.DNI > 0) & (QC_df.GHI > 0), \
           (QC_df.DNI > 0) & (QC_df.GHI > 0) & (QC_df.DNI < 5), \
           (QC_df.DNI > 0) & (QC_df.GHI > 0)]
    TitleCell = ['Comparison of DIF and GHI for DNI<10W/m2. Should be close to 1.', \
                 'Ratio of global to the sum of its components. Should be close to 1.', \
                 'Evaluation of McClear(*): Ratio of GHI to clear-sky GHI (GHIcs).']
    YLBLCell = ['DIF/GHI (-)', \
                'GHI/(DNI*cSZA+DIF) (-)', \
                'GHI/GHIcs (-)']
    Ratio4C = [0.5, 0.5, 0.5]  # [0.7,0.7,0.7]
    dYL = [0.25, 0.25, 0.75]
    ChangeBackground = [False, False, True]

    if ShowMcClear == False:
        TitleCell = TitleCell[:-1]

    for ii, ttl in enumerate(TitleCell):

        print(str(dt.datetime.now()) + ": --> QC: TS calibration check - " + ttl)

        axClbi = plt.subplot(gs1a[6 + ii, 0:2])

        axClbi.set_yticks(np.arange(0.2, 2, 0.1))

        if ShowFlag == -1:
            Filteridx = MIX[ii] & (MVal[ii].values > 0) & (MVal[ii].values < 100) & (QC_df.TOA > 0) & (
                        flag_df.QCfinal == 0)
        else:
            Filteridx = MIX[ii] & (MVal[ii].values > 0) & (MVal[ii].values < 100) & (QC_df.TOA > 0)

        x = mdates.date2num(MVal[ii].index[Filteridx])
        y = MVal[ii].values[Filteridx]
        hist, xedges, yedges = np.histogram2d(x, y, bins=[int((x[-1] - x[0])), 400],
                                              range=[[x[0], x[-1]], [0.25, 1.75]])
        if int((x[-1] - x[0])) > 10 * len(h2):
            hist = conv2(h1, h2, hist)
        yedges, xedges = np.meshgrid(0.5 * (yedges[:-1] + yedges[1:]), 0.5 * (xedges[:-1] + xedges[1:]))
        im00 = plt.scatter(xedges.flatten(), yedges.flatten(), s=3, c=hist.flatten(), cmap=cmDensity)
        im00.set_clim(0, Ratio4C[ii] * max(hist.flatten()))
        plt.plot(QC_df[Prm].index, np.ones(QC_df[Prm].values.shape), 'r--', alpha=0.5)

        plt.ylim((1 - dYL[ii], 1 + dYL[ii]))
        axClbi.set_ylabel(YLBLCell[ii], fontsize=FSZ)
        plt.xlim((QC_df.index.values[0], QC_df.index.values[-1]))
        mpl.rcParams['xtick.labelsize'] = FSZ
        mpl.rcParams['ytick.labelsize'] = FSZ
        axClbi.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        axClbi.xaxis_date()

        if (ii < len(TitleCell) - 1):
            plt.setp(axClbi.get_xticklabels(), visible=False)
        if ii == 1:
            plt.plot([MVal[ii].index[0], MVal[ii].index[-1]], np.dot((1 - 0.15), [1, 1]), 'k-.', alpha=0.4,
                     linewidth=1.0)
            plt.plot([MVal[ii].index[0], MVal[ii].index[-1]], np.dot((1 - 0.08), [1, 1]), 'k--', alpha=0.4,
                     linewidth=0.8)
            plt.plot([MVal[ii].index[0], MVal[ii].index[-1]], [1, 1], 'k--', alpha=0.4, linewidth=0.8)
            plt.plot([MVal[ii].index[0], MVal[ii].index[-1]], np.dot((1 + 0.08), [1, 1]), 'k--', alpha=0.4,
                     linewidth=0.8)
            plt.plot([MVal[ii].index[0], MVal[ii].index[-1]], np.dot((1 + 0.15), [1, 1]), 'k-.', alpha=0.4,
                     linewidth=1.0)
        if (ii == 1) & (ShowFlag == 1):
            plt.plot(mdates.date2num(MVal[ii].index[flag_df.QCfinal]), \
                     MVal[ii].values[flag_df.QCfinal], 'rs', markersize=1, alpha=0.8, label='flag')
            axClbi.legend(loc='lower right')

        if ChangeBackground[ii]:
            McClearcolor = 'mediumblue'
            McClearcolor = 'mediumseagreen'
            axClbi.xaxis.label.set_color(McClearcolor)  # setting up X-axis label color to yellow
            axClbi.yaxis.label.set_color(McClearcolor)  # setting up Y-axis label color to blue

            axClbi.tick_params(axis='y', colors=McClearcolor)  # setting up Y-axis tick color to black

            axClbi.spines['left'].set_color(McClearcolor)  # setting up Y-axis tick color to red
            axClbi.spines['right'].set_color(McClearcolor)
            axClbi.spines['top'].set_color(McClearcolor)  # setting up above X-axis tick color to red
            axClbi.spines['bottom'].set_color(McClearcolor)
            axClbi.text(mdates.date2num(QC_df.index.values[0]) + 10, 1 + dYL[ii] * 0.75, ttl, color=McClearcolor)

        else:
            axClbi.text(mdates.date2num(QC_df.index.values[0]) + 10, 1 + dYL[ii] * 0.75, ttl)

    if ShowMcClear:
        plt.annotate(
            '(*) not a plausibility control: the scatter points represent the joint effect of McClear and measurement errors.', \
            (5, 2), xycoords='figure pixels', \
            fontsize=6, fontstyle='italic', color=McClearcolor)
        axClbi.set_facecolor((0.90, 0.95, 0.95))

    # ********************** Second column ***********************************

    gs2 = GridSpec(4, 6)
    gs2.update(left=0.07, right=0.97, bottom=0.1, top=0.98, hspace=0.25, wspace=0.25)

    # =====================================================================
    # % % Part4: ERL& PPL tests
    # =====================================================================

    PrmXi = ['TOA', 'TOA', 'TOA']
    PrmXilbl = ['Top of atmosphere (TOA)', 'Top of atmosphere (TOA)', 'Top of atmosphere (TOA)']
    PrmYi = ['GHI', 'DNI', 'DIF']
    BSRN_PPL_Ks = [[1.5, 1.2, 100], [1, 0, 0], [0.95, 1.2, 50]]
    BSRN_ERL_Ks = [[1.2, 1.2, 50], [0.95, 0.2, 10], [0.75, 1.2, 30]]
    for jj in range(3):

        print(str(dt.datetime.now()) + ": --> QC: BSRN 1C - " + PrmYi[jj])

        ax21 = plt.subplot(gs2[jj, 2])
        plt.text(30, 1475, 'BSRN 1C ' + PrmYi[jj] + ": {:.2f}% / {:.2f}%".format(Stat_Test['T1C_ppl_' + PrmYi[jj]],
                                                                                 Stat_Test['T1C_erl_' + PrmYi[jj]]))

        x = QC_df[PrmXi[jj]].values
        y = QC_df[PrmYi[jj]].values
        if ShowFlag == -1:
            Filteridx = (QC_df.TOA > 0) & (y > 0) & (y < 2000) & (x > 0) & (x < 2000) & (flag_df.QCfinal == 0)
        else:
            Filteridx = (QC_df.TOA > 0) & (y > 0) & (y < 2000) & (x > 0) & (x < 2000)
        hist, xedges, yedges = np.histogram2d(x=x[Filteridx], y=y[Filteridx], bins=[200, 200],
                                              range=[[0, 1500], [0, 1500]])
        yedges, xedges = np.meshgrid(0.5 * (yedges[:-1] + yedges[1:]), 0.5 * (xedges[:-1] + xedges[1:]))
        im00 = plt.scatter(xedges.flatten(), yedges.flatten(), s=3, c=hist.flatten(), cmap=cmDensity)
        im00.set_clim(0, 0.25 * max(hist[(xedges > 5) & (yedges > 5)]))

        idx0 = (QC_df.TOA > 0)
        idxSrtLim = np.argsort(x[idx0])

        xx = x[idx0][idxSrtLim]
        tx = np.arange(min(xx), max(xx), 100)
        yy1 = BSRN_ERL_Ks[jj][0] * QC_df.TOANI[idx0][idxSrtLim] * np.sin(QC_df.GAMMA_S0[idx0][idxSrtLim]) ** \
              BSRN_ERL_Ks[jj][1] + BSRN_ERL_Ks[jj][2]
        yy2 = BSRN_PPL_Ks[jj][0] * QC_df.TOANI[idx0][idxSrtLim] * np.sin(QC_df.GAMMA_S0[idx0][idxSrtLim]) ** \
              BSRN_PPL_Ks[jj][1] + BSRN_PPL_Ks[jj][2]
        fpoly1 = np.poly1d(np.polyfit(xx, yy1, 5))
        fpoly2 = np.poly1d(np.polyfit(xx, yy2, 5))
        plt.plot(xx, yy1, '-', color=[0.8, 0.8, 0.8])
        plt.plot(xx, yy2, '-', color=[0.8, 0.8, 0.8])
        plt.plot(tx, fpoly1(tx), 'k--', alpha=0.4, linewidth=0.8)
        plt.plot(tx, fpoly2(tx), 'k--', alpha=0.4, linewidth=0.8)

        if ShowFlag == 1:
            plt.plot(x[flag_df['QCFlag_Test1C_erl_' + PrmYi[jj]]], y[flag_df['QCFlag_Test1C_erl_' + PrmYi[jj]]], 'rs',
                     markersize=1, alpha=0.5)
            plt.plot(x[flag_df['QCFlag_Test1C_ppl_' + PrmYi[jj]]], y[flag_df['QCFlag_Test1C_ppl_' + PrmYi[jj]]], 'rs',
                     markersize=1, alpha=0.5, label='erl')
            ax21.legend(loc='lower right')

        plt.ylim((0, 1600))
        plt.xlim((0, 1400))
        plt.xlabel(PrmXilbl[jj] + " (W/m2)", fontsize=FSZ)
        plt.ylabel(PrmYi[jj] + " (W/m2)", fontsize=FSZ)
        # mpl.rcParams['xtick.labelsize'] = FSZ-1
        # mpl.rcParams['ytick.labelsize'] = FSZ-1

    # =====================================================================
    # % % Part5: BSRN 2C, 3C,SERI-QC tests
    # -> BSRN 2C
    # =====================================================================
    print(str(dt.datetime.now()) + ": --> QC: BSRN 2C ")
    ax22 = plt.subplot(gs2[0, 3])
    plt.text(12, 1.3, 'BSRN-2C' + ": {:.2f}% ".format(Stat_Test['T2C_bsrn_kt']))
    if ShowFlag == -1:
        idxPlot = (QC_df.GHI > 50) & (QC_df.SZA < 90) & (flag_df.QCfinal == 0)
    else:
        idxPlot = (QC_df.GHI > 50) & (QC_df.SZA < 90)

    hist, xedges, yedges = np.histogram2d(x=QC_df.SZA[idxPlot], y=flag_df.K[idxPlot], bins=[200, 200],
                                          range=[[10, 95], [0, 1.25]])
    yedges, xedges = np.meshgrid(0.5 * (yedges[:-1] + yedges[1:]), 0.5 * (xedges[:-1] + xedges[1:]))
    im00 = plt.scatter(xedges[hist > 0], yedges[hist > 0], s=1, c=hist[hist > 0], cmap=cmDensity)
    im00.set_clim(0, 0.8 * max(hist.flatten()))
    if ShowFlag == 1:
        plt.plot(QC_df.SZA[flag_df.QCFlag_Test2C_bsrn_kt], flag_df.K[flag_df.QCFlag_Test2C_bsrn_kt], 'rs', markersize=1,
                 alpha=0.5, label='bsrn2C')
        ax22.legend(loc='lower left')
    # plt.plot(SZA[QCFlag_Test2C_bsrn_kd],KT[QCFlag_Test2C_bsrn_kd],'r.',markersize=1,label="Flagged data")
    plt.plot([0, 75, 75, 100], [1.05, 1.05, 1.1, 1.1], 'k--', alpha=0.4, linewidth=0.8)
    plt.xlabel('Solar zenith angle (°)', fontsize=FSZ)
    plt.ylabel('DIF/GHI (-)', fontsize=FSZ)
    plt.xlim((10, 95))
    plt.ylim((0, 1.4))

    # =====================================================================
    # % % -> SERI-Kn
    # =====================================================================
    print(str(dt.datetime.now()) + ": --> QC: SERI-Kn ")
    ax24 = plt.subplot(gs2[1, 3])
    plt.text(0.025, 0.92, 'SERI-kn' + ": {:.2f}% ".format(Stat_Test['T2C_seri_knkt']))
    if ShowFlag == -1:
        idxPlot = (QC_df.DNI > 0) & (QC_df.GHI > 0) & (QC_df.SZA < 90) & (flag_df.QCfinal == 0)
    else:
        idxPlot = (QC_df.DNI > 0) & (QC_df.GHI > 0) & (QC_df.SZA < 90)
    hist, xedges, yedges = np.histogram2d(x=flag_df.KT[idxPlot], y=flag_df.Kn[idxPlot], bins=[200, 200],
                                          range=[[0, 1.25], [0, 1]])
    yedges, xedges = np.meshgrid(0.5 * (yedges[:-1] + yedges[1:]), 0.5 * (xedges[:-1] + xedges[1:]))
    im00 = plt.scatter(xedges[hist > 0], yedges[hist > 0], s=1, c=hist[hist > 0], cmap=cmDensity)
    im00.set_clim(0, 0.1 * max(hist.flatten()))
    plt.plot([0, 0.8, 1.35, 1.35], [0, 0.8, 0.8, 0], 'k--', alpha=0.4, linewidth=0.8)
    if ShowFlag == 1:
        plt.plot(flag_df.KT[flag_df.QCFlag_Test2C_seri_kn_kt], flag_df.Kn[flag_df.QCFlag_Test2C_seri_kn_kt], 'r.',
                 markersize=0.9, label='SERI-kn')
        ax24.legend(loc='upper right')
    plt.xlabel('GHI/TOA (-)', fontsize=FSZ)
    plt.ylabel('DNI/TOANI (-)', fontsize=FSZ)
    plt.xlim((0, 1.5))
    plt.ylim((0, 1.))

    # -> SERI-K
    print(str(dt.datetime.now()) + ": --> QC: SERI-K ")
    ax26 = plt.subplot(gs2[2, 3])
    plt.text(0.025, 1.3, 'SERI-K' + ": {:.2f}% ".format(Stat_Test['T2C_seri_kkt']))
    if ShowFlag == -1:
        idxPlot = (QC_df.DIF > 0) & (QC_df.GHI > 0) & (QC_df.SZA < 90) & (flag_df.QCfinal == 0)
    else:
        idxPlot = (QC_df.DIF > 0) & (QC_df.GHI > 0) & (QC_df.SZA < 90)
    hist, xedges, yedges = np.histogram2d(x=flag_df.KT[idxPlot], y=flag_df.K[idxPlot], bins=[200, 200],
                                          range=[[0, 1.2], [0, 1.2]])
    yedges, xedges = np.meshgrid(0.5 * (yedges[:-1] + yedges[1:]), 0.5 * (xedges[:-1] + xedges[1:]))
    im00 = plt.scatter(xedges[hist > 0], yedges[hist > 0], s=1, c=hist[hist > 0], cmap=cmDensity)
    im00.set_clim(0, 0.1 * max(hist.flatten()))
    plt.plot([0, 0.6, 0.6, 1.35, 1.35], [1.1, 1.1, 0.95, 0.95, 0], 'k--', alpha=0.4, linewidth=0.8)
    if ShowFlag == 1:
        plt.plot(flag_df.KT[flag_df.QCFlag_Test2C_seri_k_kt], flag_df.K[flag_df.QCFlag_Test2C_seri_k_kt], 'r.',
                 markersize=0.9, label='seri-kkt')
        ax26.legend(loc='upper right')
    plt.xlabel('GHI/TOA (-)', fontsize=FSZ)
    plt.ylabel('DIF/GHI (-)', fontsize=FSZ)
    plt.xlim((0, 1.5))
    plt.ylim((0, 1.45))

    print(str(dt.datetime.now()) + ": --> QC: BSRN closure ymeas=f(yest)")
    ax27 = plt.subplot(gs2[3, 2])
    plt.text(30, 1300, 'BSRN closure' + ": {:.2f}% ".format(Stat_Test['T3C_bsrn']))
    if ShowFlag == -1:
        idxPlot = (QC_df.DIF > 0) & (QC_df.GHI > 50) & (QC_df.SZA < 90) & (flag_df.QCfinal == 0)
    else:
        idxPlot = (QC_df.DIF > 0) & (QC_df.GHI > 50) & (QC_df.SZA < 90)
    hist, xedges, yedges = np.histogram2d(x=QC_df.GHI[idxPlot], y=QC_df.GHI_est[idxPlot], bins=[500, 500],
                                          range=[[0, 1500], [0, 1500]])
    yedges, xedges = np.meshgrid(0.5 * (yedges[:-1] + yedges[1:]), 0.5 * (xedges[:-1] + xedges[1:]))
    im00 = plt.scatter(xedges[hist > 0], yedges[hist > 0], s=1, c=hist[hist > 0], cmap=cmDensity)
    im00.set_clim(0, 0.1 * max(hist.flatten()))
    if ShowFlag == 1:
        ax27.plot(QC_df.GHI[flag_df.QCFlag_Test3C_bsrn_3cmp], QC_df.GHI_est[flag_df.QCFlag_Test3C_bsrn_3cmp], 'r.',
                  markersize=1, label='closure', alpha=0.1)
        ax27.legend(loc='lower right')
    ax27.plot(np.array([0, 1400]), 0.85 * np.array([0, 1400]), 'k-.', alpha=0.4, linewidth=1.0)
    plt.plot(np.array([0, 1400]), 0.92 * np.array([0, 1400]), 'k--', alpha=0.4, linewidth=0.8)
    plt.plot(np.array([0, 1400]), 1.08 * np.array([0, 1400]), 'k--', alpha=0.4, linewidth=0.8)
    plt.plot(np.array([0, 1400]), 1.15 * np.array([0, 1400]), 'k-.', alpha=0.4, linewidth=1.0)
    plt.xlabel('GHI (W/m2)', fontsize=FSZ)
    plt.ylabel('DIF+DNI*CSZA (W/m2)', fontsize=FSZ)
    plt.ylim((0, 1400))
    plt.xlim((0, 1400))

    print(str(dt.datetime.now()) + ": --> QC: BSRN closure ratio=f(SZA)")
    ax28 = plt.subplot(gs2[3, 3])
    plt.text(8, 0.52, "BSRN closure: {:.2f}% ".format(Stat_Test['T3C_bsrn']))
    if ShowFlag == -1:
        idxPlot = (QC_df.DIF > 0) & (QC_df.GHI > 50) & (QC_df.SZA < 90) & (flag_df.QCfinal == 0)
    else:
        idxPlot = (QC_df.DIF > 0) & (QC_df.GHI > 50) & (QC_df.SZA < 90)
    hist, xedges, yedges = np.histogram2d(x=QC_df.SZA[idxPlot], y=QC_df.GHI[idxPlot] / QC_df.GHI_est[idxPlot],
                                          bins=[200, 200], range=[[0, 90], [0, 2]])
    yedges, xedges = np.meshgrid(0.5 * (yedges[:-1] + yedges[1:]), 0.5 * (xedges[:-1] + xedges[1:]))
    im00 = plt.scatter(xedges[hist > 0], yedges[hist > 0], s=1, c=hist[hist > 0], cmap=cmDensity)
    im00.set_clim(0, 0.5 * max(hist.flatten()))
    if ShowFlag == 1:
        plt.plot(QC_df.SZA[flag_df.QCFlag_Test3C_bsrn_3cmp],
                 QC_df.GHI[flag_df.QCFlag_Test3C_bsrn_3cmp] / QC_df.GHI_est[flag_df.QCFlag_Test3C_bsrn_3cmp], 'r.',
                 markersize=1, label='closure', alpha=0.1)
        ax28.legend(loc='lower right')
    plt.plot([10, 75, 75, 90, 90, 75, 75, 10], [1.08, 1.08, 1.15, 1.15, 0.85, 0.85, 0.92, 0.92], 'k--', alpha=0.4,
             linewidth=0.8)
    ax28.set_xlabel('Solar zenith angle (°)', fontsize=FSZ)
    ax28.set_ylabel('GHI/(DIF+DNI*CSZA) (-)', fontsize=FSZ)
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
    ax01.text(0.01, Y0 - 0 * dY, 'Source: ' + source, size=FSZ)
    ax01.text(0.01, Y0 - 1 * dY, station_id + ': ' + station, size=FSZ)  # 'ID/ Station'
    ax01.text(0.01, Y0 - 2 * dY, "latitude: {:.2f}°".format(latitude), size=FSZ)
    ax01.text(0.01, Y0 - 3 * dY, "longitude: {:.2f}°".format(longitude), size=FSZ)
    ax01.text(0.01, Y0 - 4 * dY, "altitude: {:.0f}m".format(elevation), size=FSZ)
    ax01.text(0.01, Y0 - 5 * dY, "country: {} ".format(country), size=FSZ)
    ax01.text(0.01, Y0 - 6 * dY, "Köppen-Geiger climate: {}".format(climate), size=FSZ)
    ax01.axis('off')

    ax02 = plt.subplot(gs0[0, 10])
    ax02.text(0.01, Y0 - 1 * dY, '.         Period:  {} - {}'.format(DateStrStart, DateStrEnd), size=FSZ)
    ax02.text(0.01, Y0 - 2 * dY, '  Annual sums:', size=FSZ)
    ax02.text(0.01, Y0 - 3 * dY, 'GHI:   {0:.0f} kWh/m2'.format(AvgGHI), size=FSZ)
    ax02.text(0.01, Y0 - 4 * dY, 'DIF:   {0:.0f} kWh/m2'.format(AvgDHI), size=FSZ)
    ax02.text(0.01, Y0 - 5 * dY, 'DNI:   {0:.0f} kWh/m2'.format(AvgDNI), size=FSZ)
    ax02.text(0.01, Y0 - 6 * dY, CodeInfo["name"] + ' ' + CodeInfo["vers"] + '', size=FSZ)
    ax02.axis('off')

    ax03 = plt.subplot(gs0[0, 11])
    ax03.text(0.01, Y0 - 2 * dY, '        Days of data: {}'.format(NbDays), size=FSZ)
    # ax03.text(0.01,Y0-2*dY,'# Flagged: {0:.1f}% '.format(Stat_FlaggedQCFinal),size=FSZ)
    ax03.text(0.01, Y0 - 3 * dY, '      ({0:.1f}% availability)'.format(AvailGHI), size=FSZ)
    ax03.text(0.01, Y0 - 4 * dY, '      ({0:.1f}% availability)'.format(AvailDHI), size=FSZ)
    ax03.text(0.01, Y0 - 5 * dY, '      ({0:.1f}% availability)'.format(AvailDNI), size=FSZ)
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
    idxPlot_qc = (QC_df.GHI > 5) & (QC_df.SZA < 90) & (flag_df.QCfinal == 0)
    idxPlot_all = (QC_df.GHI > 5) & (QC_df.SZA < 90)
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
    idxPlot_qc = (QC_df.DNI > 5) & (QC_df.SZA < 90) & (flag_df.QCfinal == 0)
    idxPlot_all = (QC_df.DNI > 5) & (QC_df.SZA < 90)
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
    idxPlot_qc = (QC_df.DIF > 5) & (QC_df.SZA < 90) & (flag_df.QCfinal == 0)
    idxPlot_all = (QC_df.DIF > 5) & (QC_df.SZA < 90)
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

    gs3 = GridSpec(9, 3)
    gs3.update(left=0.0, right=0.99, bottom=0.05, top=0.875, hspace=0.1, wspace=0.2)

    # print(str(dt.datetime.now())+": --> QC: planarity check")

    print(str(dt.datetime.now()) + ": --> QC: Verification of the pyranometer tilt angle")
    # NB: the calculation can be optimized to run faster

    isClearSky = pvlib.clearsky.detect_clearsky(QC_df.GHI, QC_df.CLEAR_SKY_GHI)
    ax31 = plt.subplot(gs3[3:5, 2])
    YYL = [0.8, 1.2]
    if ShowFlag == -1:
        idxPlot = isClearSky & (QC_df.DIF > 0) & (QC_df.GHI > 100) & (QC_df.SZA < 90) & (flag_df.QCfinal == 0) & \
                  (QC_df.CLEAR_SKY_GHI.values > 50) & (QC_df.GHI.values > 50) & (QC_df.CLEAR_SKY_DNI.values > 0)
    else:
        idxPlot = isClearSky & (QC_df.DIF > 0) & (QC_df.GHI > 100) & (QC_df.SZA < 90) & \
                  (QC_df.CLEAR_SKY_GHI.values > 50) & (QC_df.GHI.values > 50) & (QC_df.CLEAR_SKY_DNI.values > 0)
    vSAA = QC_df['ALPHA_S'].values
    if latitude < 0:
        vSAA[vSAA * 180 / np.pi > 180] = vSAA[vSAA * 180 / np.pi > 180] - 2 * np.pi

    xPlot = vSAA * 180 / np.pi
    yPlot = np.zeros(QC_df.DNI.shape)
    # yPlot[QC_df.CLEAR_SKY_DNI.values>0]=QC_df.GHI.values[QC_df.CLEAR_SKY_DNI.values>0]/QC_df.CLEAR_SKY_GHI.values[QC_df.CLEAR_SKY_DNI.values>0]

    if (latitude < 0):
        kc = QC_df[idxPlot & (np.abs(vSAA * 180 / np.pi) < 60) & (QC_df.CLEAR_SKY_DNI.values > 0)].GHI / QC_df[
            idxPlot & (np.abs(vSAA * 180 / np.pi) < 60) & (QC_df.CLEAR_SKY_DNI.values > 0)].CLEAR_SKY_GHI
    else:
        kc = QC_df[idxPlot & (np.abs(vSAA * 180 / np.pi - 180) < 60) & (QC_df.CLEAR_SKY_DNI.values > 0)].GHI / QC_df[
            idxPlot & (np.abs(vSAA * 180 / np.pi - 180) < 60) & (QC_df.CLEAR_SKY_DNI.values > 0)].CLEAR_SKY_GHI

    S = kc.resample('1D', label='left').sum()
    C = kc.resample('1D', label='left').count()
    Dailydata = pd.DataFrame({'Avgkc': S[C > 30] / C[C > 30]}, index=C.index)
    data4plot = pd.DataFrame( \
        {'kc': QC_df[idxPlot].GHI.values / QC_df[idxPlot].CLEAR_SKY_GHI.values, \
         'SAA': vSAA[idxPlot] * 180 / np.pi, \
         'day': QC_df[idxPlot].index.floor(freq='D')}, \
        index=QC_df[idxPlot].index)
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
    im00 = plt.scatter(xedges[hist > 0], yedges[hist > 0], s=3, c=hist[hist > 0], cmap=cmDensity)
    im00.set_clim(0, 0.7 * max(hist.flatten()))
    plt.ylabel('kc/kc_daily (-)', fontsize=FSZ)
    plt.xlabel('Solar azimuth angle (°)', fontsize=FSZ)
    ax31.set_ylim(YYL)
    plt.colorbar(im00, label='point density (-)')

    print(str(dt.datetime.now()) + ": --> QC: Shadow analysis (GHI)")
    idxSC = (QC_df.GAMMA_S0 > 1 / 50) & (flag_df.QCfinal == 0)
    vSEA = QC_df.loc[idxSC, 'GAMMA_S0']
    vSAA = QC_df.loc[idxSC, 'ALPHA_S']
    if latitude < 0:
        vSAA[vSAA * 180 / np.pi > 180] = vSAA[vSAA * 180 / np.pi > 180] - 2 * np.pi

    SELMax = 45

    ax32 = plt.subplot(gs3[5:7, 2])
    vKT = QC_df.loc[idxSC, 'GHI'] / QC_df.loc[idxSC, 'TOA']
    idx_sort = np.argsort(vKT.values)
    im32 = plt.scatter(vSAA[idx_sort] * 180 / np.pi, vSEA[idx_sort] * 180 / np.pi, s=1, c=vKT[idx_sort], cmap=cmShading,
                       marker='s', alpha=.5)
    plt.ylabel('Solar elevation angle [°]', fontsize=FSZ)
    plt.xlabel('Solar azimuth angle [°]', fontsize=FSZ)
    if (np.abs(latitude) < 60):
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
    ax33 = plt.subplot(gs3[7:9, 2])
    vKN = QC_df.loc[idxSC, 'DNI'] / QC_df.loc[idxSC, 'TOANI']
    idx_sort = np.argsort(vKN.values)
    im33 = plt.scatter(vSAA[idx_sort] * 180 / np.pi, vSEA[idx_sort] * 180 / np.pi, s=1, c=vKN[idx_sort], cmap=cmShading,
                       marker='s', alpha=.5)
    plt.ylabel('Solar elevation angle [°]', fontsize=FSZ)
    plt.xlabel('Solar azimuth angle [°]', fontsize=FSZ)
    if (np.abs(latitude) < 60):
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


def flagData(QC_df):
    import numpy as np
    import copy

    MinDailyShareFlag = 0.2

    GHI = QC_df.GHI
    GHI_est = QC_df.DIF + QC_df.DNI * np.cos(QC_df.THETA_Z)

    SZA = QC_df.THETA_Z * 180 / np.pi

    KT = np.zeros(QC_df.GHI.shape)
    KT[QC_df.TOA >= 1] = QC_df.GHI[QC_df.TOA >= 1] / QC_df.TOA[QC_df.TOA >= 1]

    Kn = np.zeros(QC_df.GHI.shape)
    Kn[QC_df.TOANI >= 1] = QC_df.DNI[QC_df.TOANI >= 1] / QC_df.TOANI[QC_df.TOANI >= 1]

    K = np.zeros(QC_df.GHI.shape)
    K[QC_df.GHI >= 1] = QC_df.DIF[QC_df.GHI >= 1] / QC_df.GHI[QC_df.GHI >= 1]

    kc = np.zeros(QC_df.GHI.shape)
    kc[QC_df.CLEAR_SKY_GHI >= 1] = QC_df.GHI[QC_df.CLEAR_SKY_GHI >= 1] / QC_df.CLEAR_SKY_GHI[QC_df.CLEAR_SKY_GHI >= 1]

    kbc = np.zeros(QC_df.GHI.shape)
    kbc[QC_df.CLEAR_SKY_DNI >= 1] = QC_df.DNI[QC_df.CLEAR_SKY_DNI >= 1] / QC_df.CLEAR_SKY_DNI[QC_df.CLEAR_SKY_DNI >= 1]

    # % % -----------   Calculation of the individual QC flags -----------------
    # BSRN one-component test
    flag_df = copy.deepcopy(QC_df[['GHI', 'DIF', 'DNI']])
    flag_df["QCFlag_Test1C_ppl_GHI"] = (QC_df.TOA > 0) & (
                (QC_df.GHI <= -4) | (QC_df.GHI > 1.5 * QC_df.TOANI * np.sin(QC_df.GAMMA_S0) ** 1.2 + 100))
    flag_df["QCFlag_Test1C_erl_GHI"] = (QC_df.TOA > 0) & (
                (QC_df.GHI <= -2) | (QC_df.GHI > 1.2 * QC_df.TOANI * np.sin(QC_df.GAMMA_S0) ** 1.2 + 50))
    flag_df["QCFlag_Test1C_ppl_DIF"] = (QC_df.TOA > 0) & (
                (QC_df.DIF <= -4) | (QC_df.DIF > 0.95 * QC_df.TOANI * np.sin(QC_df.GAMMA_S0) ** 1.2 + 50))
    flag_df["QCFlag_Test1C_erl_DIF"] = (QC_df.TOA > 0) & (
                (QC_df.DIF <= -2) | (QC_df.DIF > 0.75 * QC_df.TOANI * np.sin(QC_df.GAMMA_S0) ** 1.2 + 30))
    flag_df["QCFlag_Test1C_ppl_DNI"] = (QC_df.TOA > 0) & ((QC_df.DNI <= -4) | (QC_df.DNI > QC_df.TOANI))
    flag_df["QCFlag_Test1C_erl_DNI"] = (QC_df.TOA > 0) & (
                (QC_df.DNI <= -2) | (QC_df.DNI > 0.95 * QC_df.TOANI * np.sin(QC_df.GAMMA_S0) ** 0.2 + 10))

    flag_df["Kn"] = Kn
    flag_df["K"] = K
    flag_df["kc"] = kc
    flag_df["kbc"] = kbc
    flag_df["KT"] = KT

    # BSRN two-component test
    flag_df["QCFlag_Test2C_bsrn_kt"] = ((QC_df.TOA > 0) & (QC_df.GHI > 50)) & ( \
                ((SZA < 75) & (K > 1.05)) | \
                ((SZA >= 75) & (K > 1.1)))

    # SERI-QC two-component test
    flag_df["QCFlag_Test2C_seri_kn_kt"] = (QC_df.TOA > 0) & ((Kn > KT) | (Kn > 0.8) | (KT > 1.35))
    flag_df["QCFlag_Test2C_seri_k_kt"] = (QC_df.TOA > 0) & (
                ((KT < 0.6) & (K > 1.1)) | ((KT >= 0.6) & (K > 0.95)) | (KT > 1.35))

    # BSRN three-component test
    flag_df["QCFlag_Test3C_bsrn_3cmp"] = (QC_df.TOA > 0) & (
                ((SZA <= 75) & (GHI > 50) & (np.abs(GHI / GHI_est - 1) > 0.08)) | (
                    (SZA > 75) & (GHI > 50) & (np.abs(GHI / GHI_est - 1) > 0.15)))

    # Tracker off test
    GHI_measured = QC_df.GHI
    DNI_measured = QC_df.DNI
    GHI_clear = 0.8 * QC_df.TOA
    DIF_clear = 0.165 * GHI_clear
    DNI_clear = GHI_clear - DIF_clear

    flag_df["QCFlag_TrackerOff"] = ((SZA <= 85) & \
                                    ((GHI_clear - GHI_measured) / (GHI_clear + GHI_measured) < 0.2) & \
                                    ((DNI_clear - DNI_measured) / (DNI_clear + DNI_measured) > 0.95))
    # % % Combination of individual QC tests

    # if at least one of the test is positive, we flag all data (to be eventually refined)
    flag_df["QCtot"] = flag_df["QCFlag_Test1C_erl_GHI"] | flag_df["QCFlag_Test1C_erl_DIF"] | \
                       flag_df["QCFlag_Test1C_erl_DNI"] | flag_df["QCFlag_Test2C_bsrn_kt"] | \
                       flag_df["QCFlag_Test2C_seri_kn_kt"] | flag_df["QCFlag_Test2C_seri_k_kt"] | \
                       flag_df["QCFlag_Test3C_bsrn_3cmp"] | flag_df["QCFlag_TrackerOff"]

    # Evalue the share of flag data per day
    DailyFlagStat = flag_df["QCtot"].resample('D').sum() / (QC_df.TOA > 0).resample('D').sum()

    # filter if at least on test fail or the number of flag per day exceeds the minimal share
    flag_df["QCfinal"] = flag_df["QCtot"] | np.in1d(flag_df.index.normalize(),
                                                    DailyFlagStat[DailyFlagStat > MinDailyShareFlag].index.normalize())

    # % %  -------------------  Statistics on the data  -----------------------
    Stat_Test = { \
        'T1C_erl_GHI': sum(flag_df.QCFlag_Test1C_erl_GHI & (QC_df.TOA > 0) & (QC_df.GHI > -2)) / sum(
            (QC_df.TOA > 0) & (QC_df.GHI > -2)) * 100, \
        'T1C_ppl_GHI': sum(flag_df.QCFlag_Test1C_ppl_GHI & (QC_df.TOA > 0) & (QC_df.GHI > -2)) / sum(
            (QC_df.TOA > 0) & (QC_df.GHI > -2)) * 100, \
        'T1C_erl_DIF': sum(flag_df.QCFlag_Test1C_erl_DIF & (QC_df.TOA > 0) & (QC_df.DIF > -2)) / sum(
            (QC_df.TOA > 0) & (QC_df.DIF > -2)) * 100, \
        'T1C_ppl_DIF': sum(flag_df.QCFlag_Test1C_ppl_DIF & (QC_df.TOA > 0) & (QC_df.DIF > -2)) / sum(
            (QC_df.TOA > 0) & (QC_df.DIF > -2)) * 100, \
        'T1C_erl_DNI': sum(flag_df.QCFlag_Test1C_erl_DNI & (QC_df.TOA > 0) & (QC_df.DNI > -2)) / sum(
            (QC_df.TOA > 0) & (QC_df.DNI > -2)) * 100, \
        'T1C_ppl_DNI': sum(flag_df.QCFlag_Test1C_ppl_DNI & (QC_df.TOA > 0) & (QC_df.DNI > -2)) / sum(
            (QC_df.TOA > 0) & (QC_df.DNI > -2)) * 100, \
        'T2C_bsrn_kt': sum(flag_df.QCFlag_Test2C_bsrn_kt & (QC_df.TOA > 0) & (QC_df.GHI > -2)) / sum(
            (QC_df.TOA > 0) & (QC_df.GHI > -2)) * 100, \
        'T2C_seri_knkt': sum(
            flag_df.QCFlag_Test2C_seri_kn_kt & (QC_df.TOA > 0) & (QC_df.DNI > -2) & (QC_df.GHI > -2)) / sum(
            (QC_df.TOA > 0) & (QC_df.DNI > -2) & (QC_df.GHI > -2)) * 100, \
        'T2C_seri_kkt': sum(
            flag_df.QCFlag_Test2C_seri_k_kt & (QC_df.TOA > 0) & (QC_df.DIF > -2) & (QC_df.GHI > -2)) / sum(
            (QC_df.TOA > 0) & (QC_df.DIF > -2) & (QC_df.GHI > -2)) * 100, \
        'T3C_bsrn': sum(flag_df.QCFlag_Test3C_bsrn_3cmp & (QC_df.TOA > 0) & (QC_df.GHI > -2) & (QC_df.DIF > -2) & (
                    QC_df.DNI > -2)) / sum(
            (QC_df.TOA > 0) & (QC_df.GHI > -2) & (QC_df.DIF > -2) & (QC_df.DNI > -2)) * 100}
    # Stat_FlaggedQCFinal=sum((QC_df.QCfinal)&(QC_df.TOA>0))/sum((QC_df.TOA>0))*100

    return Stat_Test, flag_df


def enrich_data(df, includeCAMS=True):
    """Adds sg2, cams and horizon data"""

    # Get horizon and adds it to metadata
    lat = float(df.attrs[LATITUDE_VAR])
    lon = float(df.attrs[LONGITUDE_VAR])
    alt = float(df.attrs[ELEVATION_VAR])

    # Fetch horizon from WPS
    if (np.abs(lat) < 60):
        horizon = wps_Horizon_SRTM(lat, lon, alt)
    else:
        horizon = pd.DataFrame([])

    df.attrs[HORIZON_ATTR] = horizon

    for varname in [GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR] :
        var = df[varname]
        var[var > MAX_VAL] = np.nan
        var[var < MIN_VAL] = np.nan

    # Rename
    df = df.rename(columns=dict(
        DHI='DIF',
        BNI='DNI'))


    # Resample ?
    resolution_min = df.attrs[TIME_RESOLUTION_ATTR] // 60
    if resolution_min != 1 :
        warning("Input resolution is %d minutes, resampling to 1 min" % resolution_min)
        df = df.resample("1Min").ffill()

    sr, sp = sun_position(lat, lon, alt, df.index)

    SR = np.squeeze(sr[:, 0, 0])
    SR_Day = SR.astype('datetime64[D]').astype(SR.dtype)
    SR_TOD = (SR - SR_Day).astype(float) / 1000 / 60 / 60

    SS = np.squeeze(sr[:, 0, 2])
    SS_Day = SS.astype('datetime64[D]').astype(SS.dtype)
    SS_TOD = (SS - SS_Day).astype(float) / 1000 / 60 / 60

    # Add extra columns from SG2 to dataframe
    df['THETA_Z'] = np.pi / 2 - np.squeeze(sp.topoc.gamma_S0)
    df['GAMMA_S0'] = np.squeeze(sp.topoc.gamma_S0)
    df['ALPHA_S'] = np.squeeze(sp.topoc.alpha_S)
    df['SZA'] = 90 - 180 / np.pi * np.squeeze(sp.topoc.gamma_S0)
    df['TOA'] = np.squeeze(sp.topoc.toa_hi)
    df['TOANI'] = np.squeeze(sp.topoc.toa_ni)
    df['SR_h'] = SR_TOD
    df['SS_h'] = SS_TOD

    if includeCAMS:

        if CAMS_EMAIL_ENV in os.environ :
            cams_email = os.environ[CAMS_EMAIL_ENV]
        else:
            raise Exception("Cams emails not found. Please set the env variable %s or use a .env file" % CAMS_EMAIL_ENV)


        CAMS_DF, CAMSmetada = get_cams(
            start_date=df.index[0],
            end_date=df.index[-1],
            lat=lat, lon=lon,
            cams_email=cams_email,
            altitude=alt)

        CAMS_DF2 = pd.DataFrame({
            'CLEAR_SKY_GHI': CAMS_DF.ghi_clear.values,
            'CLEAR_SKY_DNI': CAMS_DF.dni_clear.values,
            'CLEAR_SKY_DIF': CAMS_DF.dhi_clear.values}, index=CAMS_DF.index.values)

        attrs = df.attrs
        # df = df.merge(CAMS_DF2, how='left', left_index=True, right_index=True)
        df = CAMS_DF2.merge(df, how='left', left_index=True, right_index=True)
        df.attrs.update(attrs)

    return df

@cache.memoize()
def sun_position(lat, lon, alt, times) :
    info("Computing sun position")
    if alt == np.nan:
        alt = 0

    sun_rise = sg2.sun_rise(
        [[lon, lat, alt]],
        times)

    sun_pos = sg2.sun_position(
        [[lon, lat, alt]],
        times,
        ["topoc.alpha_S", "topoc.gamma_S0", "topoc.toa_hi", "topoc.toa_ni"])


    info("end of sun position")
    return sun_rise, sun_pos

@cache.memoize()
def get_cams(start_date, end_date, lat, lon, cams_email, altitude, time_step="1min") :
    info("Calling CAMS")
    res =  pvlib.iotools.get_cams(
                start=start_date,
                end=end_date,
                latitude=lat, longitude=lon,
                email=cams_email,
                identifier='mcclear',
                altitude=altitude, time_step=time_step, time_ref='UT', verbose=False,
                integrated=False, label='right', map_variables=True,
                server='www.soda-is.com', timeout=180)
    info("End calling CAMS")
    return res

@cache.memoize()
def wps_Horizon_SRTM(lat, lon, altitude):

    info("Fetching horizons from WPS")

    str_wps = 'http://toolbox.webservice-energy.org/service/wps?service=WPS&request=Execute&identifier=compute_horizon_srtm&version=1.0.0&DataInputs='
    datainputs_wps = 'latitude={:.6f};longitude={:.6f};altitude={:.1f}'.format(lat, lon, altitude);

    print(datainputs_wps)
    print('{}{}'.format(str_wps, datainputs_wps))
    response = urlopen('{}{}'.format(str_wps, datainputs_wps))
    HZ = pd.read_csv(response, delimiter=';', comment='#', header=None, skiprows=17, nrows=360,
                         names=['AZIMUT', 'ELEVATION'])

    info("Horizons fetched")

    return HZ




