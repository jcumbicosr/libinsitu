from strenum import StrEnum

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec

from libinsitu import info
from libinsitu.qc.graphs.base import BaseGraphs, MC_CLEAR_COLOR, Text, GraphId, INDIVIDUAL_PLOTS, individual_graph, sub_grid

STANDALONE_FONT_SIZE = 12
LAYOUT_FONT_SIZE = 8

class Graphs(BaseGraphs):

    def __init__(self, *args, **kargs):
        BaseGraphs.__init__(self, *args, **kargs)

    def main_layout(self) :
        """ Render main layout """
        self.within_main_layout = True

        info("QC: visual plot preparation")
        fig = plt.figure(figsize=(19.2, 9.93))

        # Main grid : 3 columns
        main_grid = GridSpec(
            1, 3,
            left=0.04, right=0.99, bottom=0.05, top=0.99,
            wspace=0.13)

        #main_grid.tight_layout(fig)

        # =====================================================================
        # First column : time series + heatmaps + ratios
        # =====================================================================

        # Sub grid
        col1 = GridSpecFromSubplotSpec(
            8 if self.cams_df is None else 9, 1,
            main_grid[0, 0],
            hspace=0.3)

        # Plot all heatmaps time series
        self.plot_all_daily_heatmaps(col1[0:3, 0])

        # Plot ratios
        self.plot_all_ratios(col1[3:5, 0])

        # Qc levels
        self.plot_qc_level(col1[5:8, 0])

        # GHI / Clear sky
        if self.cams_df is not None:
            self.plot_ghi_clear_sky_ratio()


        # =====================================================================
        # Second column QC flags
        # =====================================================================

        # Sub grid
        col2 = GridSpecFromSubplotSpec(
            4, 2,
            main_grid[0, 1],
            hspace=0.25, wspace=0.25)

        plt.subplot(col2[0, 0])
        self.plot_ul_1c_ghi()

        plt.subplot(col2[1, 0])
        self.plot_ul_1c_dni()

        plt.subplot(col2[2, 0])
        self.plot_ul_1c_dif()

        # BSRN 2C
        plt.subplot(col2[0, 1])
        self.plot_2c_k_sza()

        # SERI-Kn
        plt.subplot(col2[1, 1])
        self.plot_2c_kn_kt_envelope()

        # SERI-K
        plt.subplot(col2[2, 1])
        self.plot_2c_kd_kt_envelope()

        # BRSN Closure ratio
        plt.subplot(col2[3, 0])
        self.plot_closure_ratio()

        # BSRN Closure
        plt.subplot(col2[3, 1])
        self.plot_closure_diff()



        # =====================================================================
        # Third column
        # =====================================================================
        col3 = GridSpecFromSubplotSpec(
            4, 1,
            main_grid[0, 2],
            hspace=0.28, wspace=0.01)

        # Row 1: Plot text & satelite images
        self.plot_info(col3[0, 0])

        # -- Row 2 : QC histograms
        self.plot_ks_distrib(col3[1, 0])

        # -- Row 3 : Histogram & level test

        # Split row in two

        col3_row3 = GridSpecFromSubplotSpec(
            1, 2,
            col3[2, 0], wspace=0.25)

        # Histogram of GHI diff residual
        plt.subplot(col3_row3[0, 0])
        self.plot_closure_residual_hist()

        # Level test
        plt.subplot(col3_row3[0, 1])
        self.plot_level_test()

        # -- Row 4: Shadow analysis
        plt.subplot(col3[3, 0])
        self.shadow_analysis('DNI/TOANI (-)', self.DNI, self.TOANI, 0.65)

        return fig


    @individual_graph(GraphId.ALL_HEATMAPS)
    def plot_all_daily_heatmaps(self, parent_grid=None):
        """Plot 3 components on a single graph with shared axis"""

        # 3 rows
        ghi_gs, dni_gs, dif_gs = sub_grid(parent_grid, nrows=3, hspace=0, wspace=0)

        ghi_ax = plt.subplot(ghi_gs)
        self.plot_heatmap_ghi(show_x=False)

        plt.subplot(dni_gs, sharex=ghi_ax)
        self.plot_heatmap_dni(show_x=False)

        plt.subplot(dif_gs, sharex=ghi_ax)
        self.plot_heatmap_dif()

    @individual_graph(GraphId.ALL_RATIOS)
    def plot_all_ratios(self, parent_grid=None):
        """Plot 3 components on a single graph with shared axis"""

        # 3 rows
        dif_ghi_cell, ghi_ghi_est_cell = sub_grid(parent_grid, nrows=2, hspace=0, wspace=0)

        # DIF / GHI
        dif_ghi_ax= plt.subplot(dif_ghi_cell)
        self.plot_dif_ghi_ratio(show_x=False)

        # GHI / estimated GHI
        plt.subplot(ghi_ghi_est_cell, sharex=dif_ghi_ax)
        self.plot_ghi_ghi_est_ratio()




    def plot_individual(self, graph_id:GraphId) :
        if not graph_id in INDIVIDUAL_PLOTS :
            raise Exception("Graph %s not found. List of valid graphs : %s" % (graph_id, str(list(INDIVIDUAL_PLOTS.keys()))))

        graph_method = INDIVIDUAL_PLOTS[graph_id]

        # Standalone individual graph ?
        font_size = LAYOUT_FONT_SIZE if self.within_main_layout else STANDALONE_FONT_SIZE

        # Set default font size temporarly
        with plt.rc_context({
            "font.size": font_size,
            "xtick.labelsize": font_size-2,
            "ytick.labelsize": font_size-2}) :

            graph_method(self)


    #
    # -- List of individual plots
    #

    @individual_graph(GraphId.DIF_GHI_RATIO)
    def plot_dif_ghi_ratio(self, show_x=True):

        h1, h2 = self.compute_h1_h2()

        self.plot_ratio_heatmap(
            ratios=self.DIF / self.GHI,
            filter=(self.DIF > 0) & (self.DNI > 0) & (self.GHI > 0),
            y_label='DIF/GHI (-)', title='Comparison of DIF and GHI for DNI<10W/m2. Should be close to 1.',
            ylimit=0.25, h1=h1, h2=h2, show_x_labels=show_x)


    @individual_graph(GraphId.GHI_GHI_EST_RATIO)
    def plot_ghi_ghi_est_ratio(self, show_x=True):

        h1, h2 = self.compute_h1_h2()

        self.plot_ratio_heatmap(
            ratios=self.GHI / self.GHI_est,
            filter=(self.DNI > 0) & (self.GHI > 0) & (self.DNI < 5),
            y_label='GHI/GHI* (-)',
            title='Ratio of global to the sum of its components. Should be close to 1.',
            hlines=[(0.08, 0.8), (0.15, 1.0)],  # (position relative to 1, linewidth)
            ylimit=0.25, h1=h1, h2=h2, show_x_labels=show_x)

    @individual_graph(GraphId.GHI_CLEAR_SKY_RATIO)
    def plot_ghi_clear_sky_ratio(self):

        h1, h2 = self.compute_h1_h2()

        self.plot_ratio_heatmap(
            ratios=self.GHI / self.cams_df.CLEAR_SKY_GHI,
            filter=(self.DNI > 0) & (self.GHI > 0),
            y_label='GHI/GHIcs (-)',
            title='Evaluation of McClear(*): Ratio of GHI to clear-sky GHI (GHIcs).',
            ylimit=0.75, bg_color=MC_CLEAR_COLOR,
            h1=h1, h2=h2)

        plt.annotate(
            '(*) not a plausibility control: the scatter points represent the joint effect of McClear and measurement errors.',
            (5, 2), xycoords='figure pixels',
            fontsize=6, fontstyle='italic', color=MC_CLEAR_COLOR)

    @individual_graph(GraphId.UL_1C_GHI)
    def plot_ul_1c_ghi(self):
        return self.plot_ul_1c(
            self.GHI, "GHI",
            abcs=[[1.5, 1.2, 100], [1.2, 1.2, 50]],
            texts=[
                Text("GHI_PPL_UL_TOANI_SZA", 600, 885, 45),
                Text("GHI_ERL_UL_TOANI_SZA", 700, 800, 40)])

    @individual_graph(GraphId.UL_1C_DNI)
    def plot_ul_1c_dni(self):
        return self.plot_ul_1c(
            self.DNI, "DNI", ymax=1700,
            abcs=[[1, 0, 0], [0.95, 0.2, 10]],
            texts=[
                Text("DNI_PPL_UL_TOANI", 450, 1420, -2),
                Text("DNI_ERL_UL_TOANI_SZA", 300, 1020, 12)])

    @individual_graph(GraphId.UL_1C_DIF)
    def plot_ul_1c_dif(self):
        return self.plot_ul_1c(
            self.DIF, "DIF", ymax=1200,
            abcs=[[0.95, 1.2, 50], [0.75, 1.2, 30]],
            texts=[
                Text("DIF_PPL_UL_TOANI_SZA", 750, 700, 40),
                Text("DIF_ERL_UL_TOANI_SZA", 700, 490, 35)])

    @individual_graph(GraphId.HEATMAP_GHI)
    def plot_heatmap_ghi(self, show_x=True):
        self.plot_heatmap_timeseries("GHI", self.GHI, 700, show_x=show_x)

    @individual_graph(GraphId.HEATMAP_DNI)
    def plot_heatmap_dni(self, show_x=True):
        self.plot_heatmap_timeseries("DNI", self.DNI, 700, show_x=show_x)

    @individual_graph(GraphId.HEATMAP_DIF)
    def plot_heatmap_dif(self, show_x=True):
        self.plot_heatmap_timeseries("DIF", self.DIF, 700, show_x=show_x)



    def compute_h1_h2(self):
        """@ym : What is the purpose of this ?? """
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

        return h1, h2



