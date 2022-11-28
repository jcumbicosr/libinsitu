import copy

import matplotlib as mpl
import numpy as np
from matplotlib import dates as mdates, pyplot as plt
from matplotlib.pyplot import gca
from libinsitu import info
from matplotlib import cm

NB_MIN_IN_DAY = 24 * 60
FONT_SIZE = 8

MC_CLEAR_COLOR = 'mediumseagreen'


def makeCustomColormap(NWhite=2, ColorGrey=0.8, NGrey=25, cmColor='viridis', NColor=100):
    import numpy as np
    from matplotlib.colors import ListedColormap
    cmpGrey = ColorGrey * np.ones((1, 3))
    cmpColor = cm.get_cmap(cmColor, 256)(np.linspace(0, 1, NColor + 10))[10:, :]
    M0 = np.hstack((np.ones((NGrey, 1)) @ cmpGrey + (np.expand_dims((np.linspace(0, 1, NGrey)), axis=0).T) @ (
                cmpColor[0, 0:3] - cmpGrey), np.ones((NGrey, 1))))
    cmWGC = ListedColormap(np.vstack((np.ones((NWhite, 4)), M0, cmpColor)), name='jet_ymsd')
    return cmWGC

COLORMAP_PLOTS = makeCustomColormap(NWhite=2, ColorGrey=0.8, NGrey=25, cmColor='cividis', NColor=100)
COLORMAP_DENSITY = makeCustomColormap(NWhite=1, ColorGrey=0.8, NGrey=50, cmColor='viridis', NColor=200)
COLORMAP_SHADING = makeCustomColormap(NWhite=2, ColorGrey=0.8, NGrey=25, cmColor='cividis', NColor=100)

def conv2(v1, v2, m, mode='same'):
    tmp = np.apply_along_axis(np.convolve, 0, m, v1, mode)
    return np.apply_along_axis(np.convolve, 1, tmp, v2, mode)

def plot_heatmap_timeseries(label, data, sunrise, sunset, cmax, longitude, ShowFlag, QCFinal):

    info("plotting heatmap timeseries for %s " % label)

    index = data.index
    axe = gca()

    nb_days = np.int64(len(index) / NB_MIN_IN_DAY)
    values = copy.deepcopy(data.values)
    M2D = np.reshape(values, (nb_days, NB_MIN_IN_DAY)).T
    deltaT = int(np.round(longitude / 360 * 24 * 60))
    M2D2 = np.roll(M2D, deltaT, axis=0)
    M2D2[M2D2 < -100] = np.nan

    x_min, x_max = mdates.date2num([index[0].date(), index[-1].date()])

    im00 = axe.imshow(
        M2D2,
        extent=[x_min, x_max, 24, 0],
        aspect='auto', cmap=COLORMAP_PLOTS, alpha=1)

    axe.xaxis_date()

    plt.setp(axe.get_xticklabels(), visible=False)
    axe.set_yticks(np.arange(0, 23, 6))
    axe.set_ylabel('Time of the day', fontsize=FONT_SIZE)

    # Plot sunrise and sunset
    def plot_limit(limit) :
        h_lt = limit + float(deltaT) / 60
        h_lt[h_lt > 24] = h_lt[h_lt > 24] - 24
        h_lt[h_lt < 0] = h_lt[h_lt < 0] + 24
        axe.plot(mdates.date2num(index), h_lt, 'k--', linewidth=0.75, alpha=0.8)

    plot_limit(sunrise)
    plot_limit(sunset)

    im00.set_clim(0, cmax)
    axe.text(mdates.date2num(index)[0] + 5, 21, label, size=10)

    mpl.rcParams['ytick.labelsize'] = FONT_SIZE
    plt.xlim((index.values[0], index.values[-1]))
    plt.ylim((0, 24))

    if ShowFlag == 1:

        timeLMT = index.values + np.timedelta64(int(longitude / 360 * 24 * 60 * 60), 's')
        day = timeLMT.astype('datetime64[D]').astype(index.values.dtype)
        TOD = 1 + (timeLMT - day).astype('timedelta64[s]').astype('double') / 60 / 60

        plt.plot(day[QCFinal], TOD[QCFinal], 'rs', markersize=1, alpha=0.8, label='flag')

        axe.legend(loc='lower right')


def plot_ratio_heatmap(ratios, filter, h1, h2, TOA, ylimit, title, y_label, ShowFlag, QCfinal, Ratio4C=0.5, bgColor=None, hlines=[]) :

    axe = gca()
    axe.set_yticks(np.arange(0.2, 2, 0.1))

    index = ratios.index

    if ShowFlag == -1:
        Filteridx = filter & (ratios.values > 0) & (ratios.values < 100) & (TOA > 0) & (
                QCfinal == 0)
    else:
        Filteridx = filter & (ratios.values > 0) & (ratios.values < 100) & (TOA > 0)

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
    mpl.rcParams['xtick.labelsize'] = FONT_SIZE
    mpl.rcParams['ytick.labelsize'] = FONT_SIZE
    axe.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    axe.xaxis_date()

    for (delta_y, width) in hlines :
        plt.plot([ratios.index[0], ratios.index[-1]], [1-delta_y, 1-delta_y], 'k-.', alpha=0.4, linewidth=width)
        plt.plot([ratios.index[0], ratios.index[-1]], [1+delta_y, 1+delta_y], 'k-.', alpha=0.4, linewidth=width)

    if ShowFlag == 1:
        plt.plot(mdates.date2num(ratios.index[QCfinal]),
                 ratios.values[QCfinal], 'rs', markersize=1, alpha=0.8, label='flag')
        axe.legend(loc='lower right')

    if bgColor:

        axe.xaxis.label.set_color(bgColor)  # setting up X-axis label color to yellow
        axe.yaxis.label.set_color(bgColor)  # setting up Y-axis label color to blue

        axe.tick_params(axis='y', colors=bgColor)  # setting up Y-axis tick color to black

        axe.spines['left'].set_color(bgColor)  # setting up Y-axis tick color to red
        axe.spines['right'].set_color(bgColor)
        axe.spines['top'].set_color(bgColor)  # setting up above X-axis tick color to red
        axe.spines['bottom'].set_color(bgColor)
        axe.text(mdates.date2num(index.values[0]) + 10, 1 + ylimit * 0.75, title, color=bgColor)

    else:
        axe.text(mdates.date2num(index.values[0]) + 10, 1 + ylimit * 0.75, title)

    return axe


def generic_qc_graph(x, y, xlabel, ylabel, xrange, yrange, legend, lines, clim_ratio=0.25) :
    """ Generic function to display QC heat map with limits """

    info("Plotting QC test: %s" % legend)

    ax = plt.gca()
    plt.text(0.01, 0.9, legend, transform=ax.transAxes)

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

    for x, y in lines :
        plt.plot(x, y, 'k--', alpha=0.4, linewidth=0.8)

    plt.xlabel(xlabel, fontsize=FONT_SIZE)
    plt.ylabel(ylabel, fontsize=FONT_SIZE)

    plt.xlim(xrange)
    plt.ylim([
        yrange[0],
        yrange[1] * 1.2])

    return im

def plot_bsrn_1c(TOA, component, component_name, Stat_Test, limits, TOANI, GAMMA_S0, ShowFlag, QCfinal) :

    legend= 'BSRN 1C ' + component_name + ": {:.2f}% / {:.2f}%".format(
        Stat_Test['T1C_ppl_' + component_name],
        Stat_Test['T1C_erl_' + component_name])

    # XXX should be done beforehand
    filter = (TOA > 0) & (component > 0) & (component < 2000) & (TOA > 0) & (TOA < 2000)

    if ShowFlag == -1:
        filter = filter & (QCfinal == 0)

    x = TOA[filter]
    y = component[filter]

    TOANI = TOANI[filter]
    GAMMA_S0 = GAMMA_S0[filter]

    # Draw limits
    limits_xy = []
    for a, b, c in limits:
        yy = a * TOANI * np.sin(GAMMA_S0) ** b + c

        # Poly appromimation
        tx = np.arange(min(x), max(x), 100)
        fpoly = np.poly1d(np.polyfit(x, yy, 5))

        limits_xy.append([tx, fpoly(tx)])

    generic_qc_graph(
        x=x, y=y,
        xlabel='Top of atmosphere (TOA) (W/m2)',
        ylabel=component_name + "W/m2",
        xrange=[1, 1300],
        yrange=[0, 1400],
        legend=legend,
        lines=limits_xy,
        clim_ratio=0.25)

    #if ShowFlag == 1:
    #    plt.plot(x[flag_df['T1C_erl_' + PrmYi[jj]]], y[flag_df['T1C_erl_' + PrmYi[jj]]], 'rs',
    #             markersize=1, alpha=0.5)
    #    plt.plot(x[flag_df['T1C_ppl_' + PrmYi[jj]]], y[flag_df['T1C_ppl_' + PrmYi[jj]]], 'rs',
    #             markersize=1, alpha=0.5, label='erl')
    #    plt.legend(loc='lower right')

def bsrn_2c(GHI, SZA, K, Stat_Test, ShowFlag, QCfinal):

    filter = (GHI > 50) & (SZA < 90)

    if ShowFlag == -1:
        filter = filter & (QCfinal == 0)

    line = [
        [0, 75, 75, 100],
        [1.05, 1.05, 1.1, 1.1]]

    return generic_qc_graph(
        legend="BSRN-2C : {:.2f}% ".format(Stat_Test['T2C_bsrn_kt']),
        x=SZA[filter], xlabel='Solar zenith angle (°)', xrange=[10, 95],
        y=K[filter], ylabel='DIF/GHI (-)', yrange = [0, 1.25],
        lines=[line],
        clim_ratio=0.8)

def seri_kn(DNI, GHI, SZA, KT, Kn, Stat_Test, ShowFlag, QCfinal) :

    filter = (DNI > 0) & (GHI > 0) & (SZA < 90)
    if ShowFlag == -1 :
        filter = filter & (QCfinal == 0)

    line = [
        [0, 0.8, 1.35, 1.35],
        [0, 0.8, 0.8, 0]]

    return generic_qc_graph(
        legend = "SERI-kn : {:.2f}% ".format(Stat_Test['T2C_seri_knkt']),
        x=KT[filter], xlabel='GHI/TOA (-)', xrange=(0, 1.5),
        y=Kn[filter], ylabel='DNI/TOANI (-)', yrange=(0, 0.8),
        lines=[line], clim_ratio=0.1)

def seri_k(DIF, GHI, SZA, KT, K, ShowFlag, QCfinal, Stat_Test) :

    filter = (DIF > 0) & (GHI > 0) & (SZA < 90)

    if ShowFlag == -1:
        filter = filter & (QCfinal == 0)

    line = (
        [0, 0.6, 0.6, 1.35, 1.35],
        [1.1, 1.1, 0.95, 0.95, 0])

    return generic_qc_graph(
        legend="SERI-K : {:.2f}% ".format(Stat_Test['T2C_seri_kkt']),
        x=KT[filter], xlabel='GHI/TOA (-)', xrange=(0, 1.5),
        y=K[filter], ylabel='DIF/GHI (-)', yrange=(0, 1.4),
        lines=[line],
        clim_ratio=0.1)

def bsrn_closure(GHI, DIF, SZA, GHI_est, Stat_Test, ShowFlag, QCfinal) :

    filter = (DIF > 0) & (GHI > 50) & (SZA < 90)

    if ShowFlag == -1:
        filter = filter & (QCfinal == 0)

    # 4 diagonal lines
    lines = []
    for r in [0.85, 0.92, 1.08, 1.15] :
        lines.append([
            [0.0, 1400.0],
            [0.0, 1400.0 *r]
        ])

    return generic_qc_graph(
        legend="BSRN closure : {:.2f}% ".format(Stat_Test['T3C_bsrn']),
        x=GHI[filter], xlabel='GHI (W/m2)', xrange=(0, 1400),
        y=GHI_est[filter], ylabel='DIF+DNI*CSZA (W/m2)', yrange=(0, 1300),
        lines=lines,
        clim_ratio=0.1)

def bsrn_closure_ratio(DIF, GHI, SZA, GHI_est, Stat_Test, ShowFlag, QCfinal) :

    filter = (DIF > 0) & (GHI > 50) & (SZA < 90)
    if ShowFlag == -1:
        filter = filter & (QCfinal == 0)

    line = [
        [10, 75, 75, 90, 90, 75, 75, 10],
        [1.08, 1.08, 1.15, 1.15, 0.85, 0.85, 0.92, 0.92]]

    return generic_qc_graph(
        legend="BSRN closure: {:.2f}% ".format(Stat_Test['T3C_bsrn']),
        x=SZA[filter], xlabel='Solar zenith angle (°)', xrange=(0, 100),
        y=GHI[filter] / GHI_est[filter], ylabel='GHI/(DIF+DNI*CSZA) (-)', yrange=(0.6, 1.2),
        lines=[line],
        clim_ratio=0.5)

def print_info() :
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