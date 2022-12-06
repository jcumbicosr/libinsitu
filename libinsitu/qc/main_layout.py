import numpy as np
from matplotlib import pyplot as plt
from matplotlib.gridspec import GridSpec

from libinsitu import info
from libinsitu.qc.graphs import plot_heatmap_timeseries, plot_ratio_heatmap, MC_CLEAR_COLOR, plot_bsrn_1c, bsrn_2c, \
    seri_kn, seri_k, bsrn_closure, bsrn_closure_ratio, print_info, histo_qc, horizontality_graph, shadow_analysis
from libinsitu.qc.qc_utils import plot_timeseries, qc_stats


def main_layout(
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
