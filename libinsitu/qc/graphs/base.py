import enum
import os.path
import urllib
from enum import IntEnum
from logging import info
from urllib.request import urlopen

from pandas import DataFrame
from strenum import StrEnum
from typing import List

from matplotlib import dates as mdates, pyplot as plt
from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec
from matplotlib.pyplot import gca
import copy
from libinsitu import info, CLIMATE_ATTRS, STATION_COUNTRY_ATTRS, NETWORK_ID_ATTRS
from matplotlib import cm
import numpy as np
from matplotlib.colors import ListedColormap
from hashlib import md5
from libinsitu._version import __version__ as libinsitu_version
from os import path
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

from libinsitu.log import error

NB_MIN_IN_DAY = 24 * 60
FONT_SIZE = "medium"
TEXT_ANNOTATION_SIZE="small"
LEGEND_FONT_SIZE=8

MC_CLEAR_COLOR = 'mediumseagreen'

GOOGLE_URL_PATTERN = "https://maps.googleapis.com/maps/api/staticmap?center={lat},{lon}&zoom={zoom}&size={width}x{height}&maptype={maptype}"
KEY_PATTERN="&key={api_key}"
CACHE_FOLDER = path.expanduser("~/.cache/libinsitu/google_images/")

class FlagLevel(IntEnum) :
    NIGHT = -5
    MISSING = -1
    OUT_2C_DOMAIN = 15


class GraphId(StrEnum) :

    # Info panel


    INFO = enum.auto()

    # Timeseries heatmaps
    HEATMAP_GHI = enum.auto()
    HEATMAP_DNI = enum.auto()
    HEATMAP_DIF = enum.auto()
    ALL_HEATMAPS = enum.auto()

    # Ratio graphs
    DIF_GHI_RATIO = enum.auto()
    GHI_GHI_EST_RATIO = enum.auto()
    GHI_CLEAR_SKY_RATIO = enum.auto()
    ALL_RATIOS = enum.auto()

    # QC levels
    QC_LEVELS = enum.auto()

    # T1C tests
    UL_1C_GHI = enum.auto()
    UL_1C_DNI = enum.auto()
    UL_1C_DIF = enum.auto()

    # T2C tests
    T2C_K_SZA = enum.auto()
    T2C_KN_KT_ENVELOPE = enum.auto()
    T2C_KD_KT_ENVELOPE = enum.auto()

    # T3C graphs
    T3C_CLOSURE_RATIO = enum.auto()
    T3C_CLOSURE_DELTA = enum.auto()

    # Histograms
    CLOSURE_RESIDUAL_HIST = enum.auto()

    LEVEL_TEST = enum.auto()
    KS_DISTRIB = enum.auto()


# Filled automatically by the individual_graph decorator
INDIVIDUAL_PLOTS = dict()

# Decorator to flag individual hraph metjhod with their names
def individual_graph(graph_id) :
    def decorator(method) :
        INDIVIDUAL_PLOTS[graph_id] = method
        def wrapper(*args, **kwargs) :
            return method(*args, **kwargs)
        return wrapper
    return decorator

def makeCustomColormap(NWhite=2, ColorGrey=0.8, NGrey=25, cmColor='viridis', NColor=100):

    cmpGrey = ColorGrey * np.ones((1, 3))
    cmpColor = cm.get_cmap(cmColor, 256)(np.linspace(0, 1, NColor + 10))[10:, :]
    M0 = np.hstack((np.ones((NGrey, 1)) @ cmpGrey + (np.expand_dims((np.linspace(0, 1, NGrey)), axis=0).T) @ (
                cmpColor[0, 0:3] - cmpGrey), np.ones((NGrey, 1))))
    cmWGC = ListedColormap(np.vstack((np.ones((NWhite, 4)), M0, cmpColor)), name='jet_ymsd')
    return cmWGC

COLORMAP_PLOTS = makeCustomColormap(NWhite=2, ColorGrey=0.8, NGrey=25, cmColor='cividis', NColor=100)
COLORMAP_DENSITY = makeCustomColormap(NWhite=1, ColorGrey=0.8, NGrey=50, cmColor='viridis', NColor=200)
COLORMAP_SHADING = makeCustomColormap(NWhite=2, ColorGrey=0.8, NGrey=25, cmColor='cividis', NColor=100)
QC_LEVEL_COLORS = plt.cm.RdYlGn(np.linspace(0, 1, 31))

def conv2(v1, v2, m, mode='same'):
    tmp = np.apply_along_axis(np.convolve, 0, m, v1, mode)
    return np.apply_along_axis(np.convolve, 1, tmp, v2, mode)


class Limit :
    """Define lines as limits to be displayed, possibly with associated QC flag"""

    def __init__(self, xs, ys, reference=None, color="black", flag=None, flag_name=None, text_x=None, text_y=None, text_rotation=0):
        self.text_rotation = text_rotation
        self.text_y = text_y
        self.text_x = text_x
        self.flag = flag
        self.flag_name = flag_name
        self.color = color
        self.reference = reference
        self.ys = ys
        self.xs = xs




class Text :
    def __init__(self, text, x, y, rotation=0, size=TEXT_ANNOTATION_SIZE):
        self.text = text
        self.x = x
        self.y = y
        self.rotation = rotation
        self.size = size


class BaseGraphs:
    """ Base class holding source data to compute graph. Implementations inherit from it """

    def __init__(self,
            meas_df = None,
            sp_df = None,
            flag_df = None,
            cams_df = None,
            qc_level = None,
            stat_test = None,
            horizons = None,
            latitude = None,
            longitude = None,
            elevation = None,
            station_id="-",
            station_name="-",
            station_longname = "-",
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

        self.show_flag = show_flag
        self.cams_df = cams_df
        self.stat_test = stat_test
        self.horizons = horizons
        self.latitude = latitude
        self.longitude = longitude
        self.elevation = elevation
        self.station_id = station_id
        self.station_name = station_name
        self.station_longname = station_longname

        self.climate = None
        self.country = None
        self.source = None

        self.qc_level = qc_level

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
        self.source = _get_meta(meas_df, NETWORK_ID_ATTRS)

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

        # Computed
        self.GHI_est = self.DIF + self.DNI * np.cos(self.THETA_Z)
        self.Kt = self.GHI / self.TOA
        self.Kn = self.DNI / self.TOANI
        self.K = self.DIF / self.GHI


        self.within_main_layout = False

    def plot_timeseries(self, label, data, ymax) :

        info("plotting timeseries for %s" % label)

        idxPlot = (self.TOA > 0) & (data.values > -50)

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

        axe.set_ylabel(label + " (W/m2)")
        plt.setp(axe.get_xticklabels(), visible=False)

    def plot_heatmap_timeseries(self, label, data, cmax, show_x=True):

        info("plotting heatmap timeseries for %s " % label)

        index = data.index
        axe = gca()

        nb_days = np.int64(len(index) / NB_MIN_IN_DAY)
        values = copy.deepcopy(data.values)
        M2D = np.reshape(values, (nb_days, NB_MIN_IN_DAY)).T
        deltaT = int(np.round(self.longitude / 360 * 24 * 60))
        M2D2 = np.roll(M2D, deltaT, axis=0)
        M2D2[M2D2 < -100] = np.nan

        x_min, x_max = mdates.date2num([index[0].date(), index[-1].date()])

        im00 = axe.imshow(
            M2D2,
            extent=[x_min, x_max, 24, 0],
            aspect='auto', cmap=COLORMAP_PLOTS, alpha=1)

        axe.xaxis_date()

        # Show / hide dx date axis
        set_date_axis(axe, show_x)

        axe.set_yticks(np.arange(0, 23, 6))
        axe.set_ylabel('Time', fontsize=FONT_SIZE)

        # Plot sunrise and sunset
        def plot_limit(limit) :
            h_lt = limit + float(deltaT) / 60
            h_lt[h_lt > 24] = h_lt[h_lt > 24] - 24
            h_lt[h_lt < 0] = h_lt[h_lt < 0] + 24
            axe.plot(mdates.date2num(index), h_lt, 'k--', linewidth=0.75, alpha=0.8)

        plot_limit(self.SR_h) # Sunrise
        plot_limit(self.SS_h) # Sunset

        im00.set_clim(0, cmax)
        axe.text(mdates.date2num(index)[0] + 5, 21, label + "(W/m²)", weight="bold")

        plt.xlim((index.values[0], index.values[-1]))
        plt.ylim((0, 24))

        # Add color bar
        cbaxes = inset_axes(plt.gca(), width="30%", height="3%", loc=1, bbox_to_anchor=(0, 0.01, 1, 1),
                            bbox_transform=plt.gca().transAxes)
        cbar = plt.colorbar(im00, cax=cbaxes, orientation='horizontal')
        cbar.ax.tick_params(labelsize=5 if self.within_main_layout else 7)


        if self.show_flag == 1:

            timeLMT = index.values + np.timedelta64(int(self.longitude / 360 * 24 * 60 * 60), 's')
            day = timeLMT.astype('datetime64[D]').astype(index.values.dtype)
            TOD = 1 + (timeLMT - day).astype('timedelta64[s]').astype('double') / 60 / 60

            plt.plot(day[self.QCfinal], TOD[self.QCfinal], 'rs', markersize=1, alpha=0.8, label='flag')

            axe.legend(loc='lower right')


    def plot_ratio_heatmap(self, ratios, filter, h1, h2, ylimit, title, y_label, Ratio4C=0.5, bg_color=None, hlines=[], show_x_labels=True) :

        axe = gca()
        axe.set_yticks(np.arange(0.2, 2, 0.1))
        set_date_axis(axe, show_x_labels)

        index = ratios.index

        Filteridx = filter & (ratios.values > 0) & (ratios.values < 100) & (self.TOA > 0)

        x = mdates.date2num(ratios.index[Filteridx])
        y = ratios.values[Filteridx]

        if len(x) == 0 :
            return

        hist, xedges, yedges = np.histogram2d(x, y, bins=[int((x[-1] - x[0])), 400],
                                              range=[[x[0], x[-1]], [0.25, 1.75]])
        if int((x[-1] - x[0])) > 10 * len(h2):
            hist = conv2(h1, h2, hist)
        yedges, xedges = np.meshgrid(0.5 * (yedges[:-1] + yedges[1:]), 0.5 * (xedges[:-1] + xedges[1:]))
        im00 = plt.scatter(xedges.flatten(), yedges.flatten(), s=3, c=hist.flatten(), cmap=COLORMAP_DENSITY)
        im00.set_clim(0, Ratio4C * max(hist.flatten()))

        plt.plot(ratios.index, np.ones(len(ratios)), 'r--', alpha=0.5)

        plt.ylim((1 - ylimit, 1 + ylimit))

        axe.set_ylabel(y_label, fontsize=FONT_SIZE)
        plt.xlim((index.values[0], index.values[-1]))

        for (delta_y, width) in hlines :
            plt.plot([ratios.index[0], ratios.index[-1]], [1-delta_y, 1-delta_y], 'k-.', alpha=0.4, linewidth=width)
            plt.plot([ratios.index[0], ratios.index[-1]], [1+delta_y, 1+delta_y], 'k-.', alpha=0.4, linewidth=width)

        if self.show_flag == 1:
            plt.plot(mdates.date2num(ratios.index[self.QCfinal]),
                     ratios.values[self.QCfinal], 'rs', markersize=1, alpha=0.8, label='flag')
            axe.legend(loc='lower right')

        if bg_color:

            axe.xaxis.label.set_color(bg_color)  # setting up X-axis label color to yellow
            axe.yaxis.label.set_color(bg_color)  # setting up Y-axis label color to blue

            axe.tick_params(axis='y', colors=bg_color)  # setting up Y-axis tick color to black

            axe.spines['left'].set_color(bg_color)  # setting up Y-axis tick color to red
            axe.spines['right'].set_color(bg_color)
            axe.spines['top'].set_color(bg_color)  # setting up above X-axis tick color to red
            axe.spines['bottom'].set_color(bg_color)
            axe.text(mdates.date2num(index.values[0]) + 10, 1 + ylimit * 0.75, title, color=bg_color)

        else:
            axe.text(mdates.date2num(index.values[0]) + 10, 1 + ylimit * 0.75, title)

        return axe


    def generic_qc_graph(
            self,
            x, y,
            xlabel, ylabel,
            xrange, yrange,
            legend,
            limits=List[Limit],
            clim_ratio=0.25,
            legend_pos="center right"):

        """ Generic function to display QC heat map with limits """

        info("Plotting QC test: %s" % legend)

        draw_title(legend)

        hist, xedges, yedges = np.histogram2d(
            x=x,
            y=y,
            bins=[200, 200],
            range=[xrange, yrange])

        yedges, xedges = np.meshgrid(
            0.5 * (yedges[:-1] + yedges[1:]),
            0.5 * (xedges[:-1] + xedges[1:]))

        im = plt.scatter(
            xedges.flatten(),
            yedges.flatten(), s=3,
            c=hist.flatten(),
            cmap=COLORMAP_DENSITY)

        im.set_clim(0, clim_ratio * max(hist.flatten()))

        # Plot lines and text
        seen_ref= set()
        for limit in limits :

            # In main layout, only show limit for flags, and show text with pct
            if self.within_main_layout :

                if limit.flag :
                    flag_name = limit.flag_name or limit.flag

                    # Show name of flag and percentage
                    label = "%s (%.2f %%)" % (flag_name, self.stat_test[limit.flag])

                    plt.text(
                        limit.text_x,
                        limit.text_y,
                        label,
                        size=TEXT_ANNOTATION_SIZE,
                        rotation=limit.text_rotation,
                        horizontalalignment='left',
                        verticalalignment='bottom',
                        rotation_mode='anchor')
                else:
                    # skip this limit
                    continue

            if limit.reference is None and not self.within_main_layout :
                continue

            color = "black" if self.within_main_layout else limit.color

            plt.plot(limit.xs, limit.ys, color=color, alpha=0.4, linewidth=3)

            # Prevent duplicate legends
            label = limit.reference if limit.reference and not limit.reference in seen_ref else None
            plt.plot(limit.xs, limit.ys, linestyle='dashed', color=color, alpha=0.6, linewidth=1, label=label)

            # Avoid double legend
            seen_ref.add(limit.reference)


        if not self.within_main_layout :
            plt.legend(loc=legend_pos, fontsize=LEGEND_FONT_SIZE)

        plt.xlabel(xlabel)
        plt.ylabel(ylabel)

        plt.xlim(xrange)
        plt.ylim(yrange)

        return im

    def plot_ul_1c(self, component, component_name, abcs, texts, ymax=1500) :

        legend = component_name + " range test"

        # XXX should be done beforehand
        filter = (self.TOA > 0) & (component > 0) & (component < 2000) & (self.TOA > 0) & (self.TOA < 2000)

        x = self.TOA[filter]
        y = component[filter]

        TOANI = self.TOANI[filter]
        GAMMA_S0 = self.GAMMA_S0[filter]

        # Transform text and
        limits = []

        for text, (a, b, c) in zip(texts, abcs):

            yy = a * TOANI * np.sin(GAMMA_S0) ** b + c

            if len(x) == 0:
                continue

            # Poly approximation
            tx = np.arange(min(x), max(x), 100)
            fpoly = np.poly1d(np.polyfit(x, yy, 5))

            flag_key = text.text
            # Shorter flag name
            flag_name = flag_key[4:7]

            limits.append(Limit(
                xs=tx,
                ys=fpoly(tx),
                flag=flag_key,
                flag_name=flag_name,
                text_x=text.x,
                text_y=text.y,
                text_rotation=text.rotation))

        return self.generic_qc_graph(
            x=x, y=y,
            xlabel='Top of atmosphere (TOAHI) (W/m2)',
            ylabel=component_name + " (W/m2)",
            xrange=[1, 1300],
            yrange=[0, ymax],
            legend=legend,
            limits=limits,
            clim_ratio=0.25)

    @individual_graph(GraphId.T2C_K_SZA)
    def plot_2c_k_sza(self):

        filter = (self.GHI > 50) & (self.SZA < 90)

        limit = Limit(
            xs = [0, 75, 75, 100],
            ys= [1.05, 1.05, 1.1, 1.1],
            flag="K_UL_SZA",
            reference="Long and Dutton (2002)",
            text_x=40, text_y=1.1)

        return self.generic_qc_graph(
            legend="K/SZA upper limit",
            x=self.SZA[filter], xlabel='Solar Zenith Angle (°)', xrange=[10, 95],
            y=self.K[filter], ylabel='K=DIF/GHI (-)', yrange = [0, 1.4],
            limits=[limit],
            clim_ratio=0.8)

    @individual_graph(GraphId.T2C_KN_KT_ENVELOPE)
    def plot_2c_kn_kt_envelope(self) :

        filter = (self.DNI > 0) & (self.GHI > 0) & (self.SZA < 90)

        forstinger_ll= Limit(
            xs=[0.533,0.533,1.5],
            ys=[0,0.0171,0.0171],
            flag="Kn_LL_KT",
            text_x=0.75, text_y=0.03,
            reference="Forstinger et al. (2022)", color="red")

        forstinger_ul = Limit(
            xs=[0,1.5],
            ys=[0.8,0.8],
            reference="Forstinger et al. (2022)", color="red")

        maxwell = Limit(
            xs=[0, 1.5],
            ys=[0, 1.5],
            reference="Maxwell at al. (1993)", color="blue",
            flag="Kn_UL_KT",
            text_x=0.3, text_y=0.35, text_rotation=55)

        return self.generic_qc_graph(
            legend = "Kn/Kt envelope",
            x=self.Kt[filter], xlabel='Kt=GHI/TOA (-)', xrange=(0, 1.5),
            y=self.Kn[filter], ylabel='Kn=DNI/TOANI (-)', yrange=(0, 0.8),
            limits=[forstinger_ll, forstinger_ul, maxwell],
            clim_ratio=0.1)


    @individual_graph(GraphId.T2C_KD_KT_ENVELOPE)
    def plot_2c_kd_kt_envelope(self) :

        filter = (self.DIF > 0) & (self.GHI > 0) & (self.SZA < 90)

        long_dutton1 = Limit(
            xs=[0,1.5],
            ys=[1.05,1.05],
            reference="Long and Dutton (2002)", color="red")

        # XXX FIXME @ym : Why there are two parellel limits for Long and Dutton ?
        long_dutton2 = Limit(
            xs=[0, 1.5],
            ys=[1.1, 1.1],
            reference="Long and Dutton (2002)", color="red")

        perez = Limit(
            xs=[0,0.2,0.2],
            ys=[0.9,0.9,0],
            reference="Perez-Astudillos et al. (2018)", color="green")

        perez2 = Limit(
            xs=[0.5,0.5,1.5],
            ys=[1.2,0.8,0.8],
            reference="Perez-Astudillos et al. (2018)", color="green")

        geuder = Limit(
            xs=[0.6,0.6,1.5],
            ys=[1.2,0.96,0.96],
            flag="K_UL_KT",
            text_x=0.8, text_y=0.97,
            reference="Geuder et al. (2015)", color="lightblue")

        long_shi = Limit(
            xs=[0.85, 0.85, 1.5],
            ys=[1.2, 0.85, 0.85],
            reference="Long and Shi (2008)", color="blue")

        nollas = Limit(
            xs=[1.4,1.4],
            ys=[0.0,1.2],
            reference="Nollas et al. (2023)")

        return self.generic_qc_graph(
            legend="K/Kt envelope",
            x=self.Kt[filter], xlabel='Kt=GHI/TOAHI (-)', xrange=(0, 1.5),
            y=self.K[filter], ylabel='K=DIF/GHI (-)', yrange=(0, 1.4),
            limits=[long_dutton1, long_dutton2, perez, perez2, geuder, long_shi, nollas],
            clim_ratio=0.1,
            legend_pos="lower right")

    @individual_graph(GraphId.CLOSURE_RESIDUAL_HIST)
    def plot_closure_residual_hist(self):

        draw_title("Closure residual")

        ax = plt.gca()

        xref = np.arange(-50, 50, 0.5)
        filt_ghi = (self.GHI > 50) & (self.DIF > 0)
        filt_ghi_dni = filt_ghi & (self.DNI < 5)
        diff = self.GHI - self.GHI_est

        plt.hist(
            diff[filt_ghi],
            bins=xref,
            alpha=0.5, lw=3,
            color='blue',
            label='GHI>50 W/m$^2$')

        plt.hist(
            diff[filt_ghi_dni],
            bins=xref,
            alpha=0.5, lw=3,
            color='red',
            label='& DNI<5W$^2$')

        ax.set_yticklabels('')
        plt.legend(loc="upper right", fontsize=LEGEND_FONT_SIZE-1)

        plt.xlabel('GHI-GHI* (W/m$^2$)')
        plt.ylabel('count (-)')
        plt.xlim([-25, 25])


    @individual_graph(GraphId.T3C_CLOSURE_RATIO)
    def plot_closure_ratio(self) :

        filter = (self.DIF > 0) & (self.GHI > 50) & (self.SZA < 90)

        limit = Limit(
            xs=[10, 75, 75, 90, 90, 75, 75, 10],
            ys=[1.08, 1.08, 1.15, 1.15, 0.85, 0.85, 0.92, 0.92],
            flag="ClosureRatio_tol_SZA",
            reference="Long and Dutton 2002",
            color="red",
            text_x= 2,
            text_y= 1.1)

        return self.generic_qc_graph(
            legend="Closure ratio",
            x=self.SZA[filter], xlabel='Solar zenith angle (°)', xrange=(0, 100),
            y=self.GHI[filter] / self.GHI_est[filter], ylabel='GHI/GHI* (-)', yrange=(0.6, 1.4),
            limits=[limit],
            clim_ratio=0.5, legend_pos="lower left")

    @individual_graph(GraphId.T3C_CLOSURE_DELTA)
    def plot_closure_diff(self):

        filter = (self.DIF > 0) & (self.GHI > 50) & (self.SZA < 90)

        perez_astudillo = Limit(
            [0,1400],[50,50],
            reference="Perez-Astudillo (2018)",
            color="blue")

        perez_astudillo_neg = Limit(
            [0, 1400], [-50, -50],
            reference="Perez-Astudillo (2018)",
            color="blue")

        maxwell = Limit(
            [0, 1400], [0, 1400 * 0.03],
            reference='Maxwell et al. (1993)',
            color="red")

        maxwell_neg = Limit(
            [0, 1400], [0, -1400 * 0.03],
            reference='Maxwell et al. (1993)',
            color="red")

        # FIXME XXX @ym : Why flag limit is not related to any one in litterature ?
        x_break = 250
        flag_limit = Limit(
            [0, x_break, 1400], [x_break * 0.03, x_break * 0.03, 1400 * 0.03],
            flag="ClosureDelta_tol_TOAHI",
            text_x=350,
            text_y=15,
            text_rotation=10)

        flag_limit_neg = Limit(
            [0, x_break, 1400], [-x_break * 0.03, -x_break * 0.03, -1400 * 0.03],
            flag="ClosureDelta_tol_TOAHI",
            text_x=350,
            text_y=15,
            text_rotation=10)

        return self.generic_qc_graph(
            legend="Closure difference",
            x=self.TOA[filter], xlabel='TOAHI (W/m2)', xrange=(0, 1450),
            y=(self.GHI - self.GHI_est)[filter], ylabel='GHI - GHI* (W/m2)', yrange=(-90, 90),
            limits=[perez_astudillo, perez_astudillo_neg, maxwell, maxwell_neg, flag_limit, flag_limit_neg],
            clim_ratio=0.5, legend_pos="lower left")

    @individual_graph(GraphId.INFO)
    def plot_info(self, parent_gs = None) :

        #ax = gca()

        posTOA = self.TOA > 0
        nPosTOA = sum(posTOA)
        timePosGHI = self.time[self.GHI > 0]

        NbDays = len(timePosGHI.normalize().unique())
        AvgGHI = np.nan if NbDays == 0 else sum(self.GHI[self.GHI > 0]) * 1 / 60 / NbDays * 365 / 1000
        AvgDHI = np.nan if NbDays == 0 else sum(self.DIF[self.DIF > 0]) * 1 / 60 / NbDays * 365 / 1000
        AvgDNI = np.nan if NbDays == 0 else sum(self.DNI[self.DNI > 0]) * 1 / 60 / NbDays * 365 / 1000
        AvailGHI = np.nan if nPosTOA == 0 else sum((self.GHI > -2) & posTOA) / nPosTOA * 100
        AvailDHI = np.nan if nPosTOA == 0 else sum((self.DIF > -2) & posTOA) / nPosTOA * 100
        AvailDNI = np.nan if nPosTOA == 0 else sum((self.DNI > -2) & posTOA) / nPosTOA * 100

        DateStrStart = "" if NbDays == 0 else timePosGHI[0].strftime("%Y-%m-%d")
        DateStrEnd = "" if NbDays == 0 else timePosGHI[-1].strftime("%Y-%m-%d")

        # Split the grid
        gs = sub_grid(parent_gs, 2, 4, wspace=0.1, hspace=0.05)

        # XXX factorize this ?
        if not parent_gs :
            gs.update(left=0.02, right=0.92, bottom=0.02, top=0.98)

        ax_table1 = plt.subplot(gs[1, 0:2])
        draw_table(ax_table1, {
            "Network" : self.source,
            "Station" : "%s (%s)" % (self.station_id, self.station_longname),
            "Latitude" : "%.5f°" % self.latitude,
            "Longitude": "%.5f°" % self.longitude,
            "Elevation": "%.2fm" % self.elevation,
            "Country": self.country,
            "KG climate": self.climate}, width=0.4)


        ax_table2 = plt.subplot(gs[1, 2:4])

        format_sum = "%.0f kWh/m2 (%.1f%% avail)"
        draw_table(ax_table2, {
            "Period": "%s - %s" % (DateStrStart, DateStrEnd),
            "Annual sums": "",
            "GHI" : format_sum % (AvgGHI, AvailGHI),
            "DIF": format_sum % (AvgDHI, AvailDHI),
            "DNI": format_sum % (AvgDNI, AvailDNI),
            "Software" : "libinsitu %s" % libinsitu_version
        })

        # Draw satelite images
        ax_world_map = plt.subplot(gs[0, :2])
        draw_satelite_image(
            ax_world_map, self.latitude, self.longitude,
            width=500, height=200, zoom=1,
            maptype="road",
            marker=True)

        ax_medium_zoom = plt.subplot(gs[0, 2])
        draw_satelite_image(
            ax_medium_zoom, self.latitude, self.longitude, zoom=16,
            marker=True)

        ax_close_zoom = plt.subplot(gs[0, 3])
        draw_satelite_image(
            ax_close_zoom, self.latitude, self.longitude, zoom=20)


        # Manually update positions
        update_pos(ax_table1, diff_bottom=-0.05)
        update_pos(ax_table2, diff_bottom=-0.05)
        update_pos(ax_close_zoom, diff_bottom=-0.05)
        update_pos(ax_medium_zoom, diff_bottom=-0.05)
        update_pos(ax_world_map, diff_bottom=-0.05)

        update_pos(ax_close_zoom, diff_height=0.05)
        update_pos(ax_medium_zoom, diff_height=0.05)
        update_pos(ax_world_map, diff_height=0.05)

    @individual_graph(GraphId.QC_LEVELS)
    def plot_qc_level(self, parent_grid=None):

        fig = plt.gcf()

        # Split into a sub grid
        gs = sub_grid(parent_grid, nrows=3, ncols=1, hspace=0)

        # Rolling sum
        nb_days = 10



        start = self.qc_level.index[0]


        def plot_component(ax, comp, show_x_labels=True):

            # Group by value and resample
            grouped = self.qc_level[comp].groupby(self.qc_level[comp]).resample("%dD" % nb_days, origin=start).count().unstack(level=0) / nb_days

            colors = {
                "night": "grey",
                "n/a": "white"
            }
            for i in grouped.columns :
                if i >= 0 :
                    colors[i] = QC_LEVEL_COLORS[i, :3]

            # Rename flags
            grouped= grouped.rename(columns={
                FlagLevel.NIGHT:'night',
                FlagLevel.MISSING:'n/a'})

            grouped.plot.area(color=colors, ax=ax)
            ax.set_ylabel('samples/day')
            ax.set_ylim([0, 1440])

            set_date_axis(ax, show_x_labels)

            ax.legend(
                ncol=len(grouped.columns),
                loc="lower right",
                fontsize=LEGEND_FONT_SIZE-1,
                columnspacing=0.3,
                handlelength=1,
                markerscale=0.5)


        ghi_ax = fig.add_subplot(gs[0, 0])
        plot_component(ghi_ax, "GHI", False)

        dhi_ax = fig.add_subplot(gs[1, 0], sharex=ghi_ax)
        plot_component(dhi_ax, "DHI", False)

        bni_ax = fig.add_subplot(gs[2, 0], sharex=ghi_ax)
        plot_component(bni_ax, "BNI", True)



    @individual_graph(GraphId.KS_DISTRIB)
    def plot_ks_distrib(self, parent_grid=None) :
        info("QC: histograms of K, Kn & KT")

        fig = plt.gcf()

        gs = sub_grid(parent_grid, nrows=1, ncols=3, hspace=0, wspace=0)

        def plot_distrib(ax, comp, y, title, show_y_label=False, show_legend=False) :

            qc_level = self.qc_level[comp]

            for level in [0, 10, 15, 21, 22, 25, 30]:

                color = QC_LEVEL_COLORS[level, :3]

                # Filter for this qc level
                filter = (self.GHI > 0) & (self.SZA < 90) & (qc_level >= level)


                hist_cfl, xedges = np.histogram(y[filter], bins=500, range=[0, 1.2])
                xval = (xedges[1:] + xedges[:-1]) / 2

                # @YM XXX Looks lieka bug : was this intentional ?
                ax.fill_between(xval, 0, hist_cfl, color=color, label=str(level))

                if level == 0 :
                    ymax = 1.1 * max(hist_cfl[10:])

            ax.set_xlim([0, 1.1])
            ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
            ax.set_xticklabels([0, 0.2, 0.4, 0.6, 0.8, 1])
            ax.set_xlabel(title)
            ax.set_yticklabels('')
            ax.set_ylim([0, ymax])
            ax.grid(axis="x")

            if show_y_label:
                ax.set_ylabel('count')

            if show_legend:
                ax.legend(
                    loc='upper left',
                    ncol=3,
                    columnspacing=0.3,
                    fontsize=LEGEND_FONT_SIZE - 1,
                    handlelength=1,
                    markerscale=0.5)

        ax1 = fig.add_subplot(gs[0, 0])
        plot_distrib(
            ax=ax1,
            comp="GHI",
            y=self.GHI / self.TOA,
            title="KT=GHI/TOA",
            show_y_label=True, show_legend=True)

        plot_distrib(
            ax=fig.add_subplot(gs[0, 1], sharey=ax1),
            comp="BNI",
            y=self.DNI / self.TOANI,
            title="Kn=DNI/TOANI")

        plot_distrib(
            ax=fig.add_subplot(gs[0, 2], sharey=ax1),
            comp="DHI",
            y=self.DIF / self.GHI,
            title="K=DIF/GHI")



    @individual_graph(GraphId.LEVEL_TEST)
    def plot_level_test(self):

        diff = self.GHI - self.GHI_est

        SolElev = np.maximum(0, self.GAMMA_S0 * 180 / np.pi)
        SolAzim = self.ALPHA_S * 180 / np.pi

        resAzim, resElev = 1, 0.1

        ixSunPos = np.round(SolAzim / resAzim) * 1000000 + np.round(SolElev / resElev)

        ixAnalysis = np.where((self.GHI > 0) & (SolElev > 0))[0]

        dfSunPos = DataFrame({'ixSunPos': ixSunPos[ixAnalysis],
                                 'SolElev': SolElev[ixAnalysis],
                                 'SolAzim': SolAzim[ixAnalysis],
                                 'deltaG_Closure': diff[ixAnalysis],
                                 'count': np.ones(ixAnalysis.shape)})

        dfSunPosAvg = dfSunPos.groupby(['ixSunPos']).mean()
        dfSunPosAvg2 = dfSunPos.groupby(['ixSunPos']).sum()
        dfSunPosAvg['count'] = dfSunPosAvg2['count']

        idx = (dfSunPosAvg['count'] > 10)

        ax = plt.gca()

        scat = ax.scatter(dfSunPosAvg.SolElev.values[idx], dfSunPosAvg.deltaG_Closure[idx],
                        c=dfSunPosAvg.SolAzim.values[idx],
                        alpha=0.1, s=2, vmin=180 - 90, vmax=180 + 90)

        # Inner color bar
        label_font_size = 5 if self.within_main_layout else 7
        cbaxes = inset_axes(
            ax, width="50%", height="3%", loc="upper center",
            bbox_transform=ax.transAxes)
        cbar = plt.colorbar(scat, cax=cbaxes, orientation='horizontal')
        cbar.solids.set(alpha=1)
        cbar.ax.set_xlabel("Azimuth (°)", fontsize=label_font_size)
        cbar.ax.tick_params(labelsize=label_font_size)


        ax.set_ylim([-50, 50])
        ax.grid()
        ax.set_xlabel('Solar elevation angle (deg)')
        ax.set_ylabel('AG-G* (W/m2)')

        plt.text(-2, 41, "Leveling-induced error test",
                 horizontalalignment='left', verticalalignment='bottom',
                 rotation_mode='anchor', weight='bold')

    def histo_qc(self, comp, x, x_label, legend_pos=None, y_label=False) :

        axe = gca()

        idxPlot_qc = (comp > 5) & (self.SZA < 90) & (self.QCfinal == 0)
        idxPlot_all = (comp > 5) & (self.SZA < 90)
        hist_qc, xedges = np.histogram(x[idxPlot_qc], bins=500, range=[0, 1.2])
        hist_all, xedges = np.histogram(x[idxPlot_all], bins=500, range=[0, 1.2])
        xval = (xedges[1:] + xedges[:-1]) / 2
        axe.fill_between(xval, 0 * xval, hist_all, color=[204 / 255, 0 / 255, 0 / 255], label='flagged data')
        axe.fill_between(xval, 0 * xval, hist_qc, color=[102 / 255, 178 / 255, 255 / 255], label='valid data')

        if legend_pos :
            axe.legend(loc=legend_pos)

        if y_label :
            axe.set_ylabel('count')

        axe.set_xlim([0, 1.1])
        axe.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
        axe.set_xticklabels([0, 0.2, 0.4, 0.6, 0.8, 1])
        axe.set_xlabel(x_label)
        axe.set_yticks([])


    def shadow_analysis(self, label, comp, ref, cmax) :

        info("Shadow analysis")

        axe = gca()

        idxSC = (self.GAMMA_S0 > 1 / 50)
        vSEA = self.GAMMA_S0[idxSC]
        vSAA = self.ALPHA_S[idxSC]
        if self.latitude < 0:
            vSAA[vSAA * 180 / np.pi > 180] = vSAA[vSAA * 180 / np.pi > 180] - 2 * np.pi

        SELMax = 45

        vK = comp[idxSC] / ref[idxSC]
        idx_sort = np.argsort(vK.values)

        # Prevent crash when empty data
        if len(vK) > np.sum(vK.isna()):
            x = vSAA[idx_sort] * 180 / np.pi
            y = vSEA[idx_sort] * 180 / np.pi
            c = vK[idx_sort]
        else:
            x = []
            y = []
            c = []

        im = plt.scatter(x, y,
            s=1, c=c,
            cmap=COLORMAP_SHADING,
            marker='s', alpha=.5)

        plt.ylabel('Solar elevation angle [°]', fontsize=FONT_SIZE)
        plt.xlabel('Solar azimuth angle [°]', fontsize=FONT_SIZE)

        if self.horizons is not None:
            plt.plot(self.horizons.AZIMUT, self.horizons.ELEVATION, '-', linewidth=1, alpha=0.6, c='red')
            plt.plot(self.horizons.AZIMUT - 360, self.horizons.ELEVATION, '-', linewidth=1, alpha=0.6, c='red')
        if self.latitude < 0:
            dxx = 180
        else:
            dxx = 0

        plt.xlim((45 - dxx, 315 - dxx))
        axe.text(50 - dxx, 0.92 * SELMax, 'shadow analysis', weight="bold")
        im.set_clim(0, cmax)
        plt.ylim((0, SELMax))
        plt.colorbar(im, label=label)


def _get_meta(df, keys) :
    """Try several keys to get Meta data"""
    for key in keys :
        if key in df.attrs :
            return df.attrs[key]
    return "-"


def draw_satelite_image(ax, lat, lon, zoom, maptype='satellite', width=400, height=400, marker=False) :
    ax.axis(False)

    url = GOOGLE_URL_PATTERN.format(
        lat=lat,
        lon=lon,
        zoom=zoom,
        maptype=maptype,
        width=width,
        height=height)

    url_hash = md5(url.encode()).hexdigest()

    os.makedirs(CACHE_FOLDER, exist_ok=True)

    cache_file = path.join(CACHE_FOLDER, url_hash)

    if not path.exists(cache_file) :

        info("Calling google API : %s", url)

        if not "GOOGLE_API_KEY" in os.environ :
            error("Image was not in cache and env var GOOGLE_API_KEY not set")
            return

        # Append API KEY
        api_key = os.environ["GOOGLE_API_KEY"]
        url = url + KEY_PATTERN.format(api_key=api_key)

        # Save it to cache
        with open(cache_file, "wb") as f:
            f.write(urlopen(url).read())

    ax.imshow(plt.imread(cache_file))

    if marker :
        ax.scatter(width/2, height/2, marker="+", s=150, linewidths=2, color="red")

def draw_title(title, x=0.01, y=0.94, ax=None):

    if ax is None:
        ax = plt.gca()

    title = plt.text(x, y, title, transform=ax.transAxes, weight="bold")
    title.set_bbox(dict(facecolor='white', alpha=0.7, edgecolor='white'))


def draw_table(ax, keys_values, x=0.01, y=0.95, height=0.15, width=0.3) :

    ax.axis("off")

    # Display labels
    for i, text in enumerate(keys_values.keys()) :
        ax.text(x, y-i*height, text, weight="bold")


    # Display values
    for i, text in enumerate(keys_values.values()) :
        ax.text(x + width, y-i*height, text)

def set_date_axis(ax=None, show=True) :
    if ax is None :
        ax = plt.gca()

    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

    if show:
        plt.setp(ax.get_xticklabels(), visible=True)
    else:
        plt.setp(ax.get_xticklabels(), visible=False)


def sub_grid(parent_grid, nrows=1, ncols=1, wspace=None, hspace=None, return_cells=False) :

    extra_args = dict()
    if wspace is not None :
        extra_args["wspace"] = wspace
    if hspace is not None :
        extra_args["hspace"] = hspace

    if parent_grid is None :
        gs = GridSpec(nrows, ncols, **extra_args)
    else:
        gs = GridSpecFromSubplotSpec(nrows, ncols, subplot_spec=parent_grid, **extra_args)

    if not return_cells :
        return gs
    else:
        if nrows == 1 :
            return list(gs[0, col] for col in range(ncols))
        elif ncols == 1:
            return list(gs[row, 0] for row in range(nrows))
        else:
            raise Exception("Can only split cells for grid spec of single column or single line")


def update_pos(ax, diff_bottom=None, diff_left=None, diff_width=None, diff_height=None) :
    fig = plt.gcf()
    left, bottom, width, height = ax.get_position(fig).bounds

    if diff_bottom is not None:
        bottom += diff_bottom
    if diff_left is not None:
        left += diff_left
    if diff_width is not None:
        width += diff_width
    if diff_height is not None:
        height += diff_height

    ax.set_position([left, bottom, width, height])