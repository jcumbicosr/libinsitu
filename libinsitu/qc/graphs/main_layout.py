from strenum import StrEnum

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec

from libinsitu import info
from libinsitu.qc.graphs.base import BaseGraphs, MC_CLEAR_COLOR, Text, GraphId, INDIVIDUAL_PLOTS, individual_graph
import enum



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
        plt.tight_layout()

        # Main grid : 3 columns
        main_grid = GridSpec(
            1, 3,
            left=0.03, right=1, bottom=0.05, top=0.99)

        # =====================================================================
        # First column : time series + heatmaps + ratios
        # =====================================================================

        # Sub grid
        col1 = GridSpecFromSubplotSpec(
            8 if self.cams_df is None else 9, 1,
            main_grid[0, 0],
            hspace=0.02, wspace=0.02)

        # Plot all heatmaps time series
        plt.subplot(col1[3, 0])
        self.plot_heatmap_ghi()

        plt.subplot(col1[4, 0])
        self.plot_heatmap_dni()

        plt.subplot(col1[5, 0])
        self.plot_heatmap_dif()

        # -- Plot ratios

        # DIF / GHI
        plt.subplot(col1[6, 0])
        self.plot_dif_ghi_ratio()

        # GHI / estimated GHI
        plt.subplot(col1[7, 0])
        self.plot_ghi_ghi_est_ratio()


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
            hspace=0.25, wspace=0.15)

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
            hspace=0.25, wspace=0.01)

        # Plot text & satelite images
        self.plot_info(col3[0, 0])

        # -- QC histograms
        info("QC: histograms of K, Kn & KT")
        #plt.subplot(gs3b[1:3, 6])
        #self.histo_qc(self.GHI, self.flags.KT, 'GHI/TOA', y_label=True)

        #plt.subplot(gs3b[1:3, 7])
        #self.histo_qc(self.DNI, self.flags.Kn, 'DNI/TOANI')

        #plt.subplot(gs3b[1:3, 8])
        #self.histo_qc(self.DIF, self.flags.K, 'DIF/GHI',legend_pos='upper left')

        #if self.cams_df is None :
        #    gs3 = GridSpec(7, 3)
        #    shadow_row = 3
        #else:
        #    gs3 = GridSpec(9, 3)
        #    shadow_row = 5

        #gs3.update(left=0.0, right=0.99, bottom=0.05, top=0.875, hspace=0.1, wspace=0.2)

        # -- Horizontality graph
        #if self.cams_df is not None:

        #    info("Horizontality test")
        #    plt.subplot(gs3[3:5, 2])#

        # self.horizontality_graph()


        # Histogram & elevation angle

        # Split row in two
        col3_row3 = GridSpecFromSubplotSpec(
            1, 2,
            col3[2, 0],
            hspace=0, wspace=0)

        # Histogram of GHI diff residual
        plt.subplot(col3_row3[0, 0])
        self.plot_closure_residual_hist()




        # -- Shadow analysis
        plt.subplot(col3[3, 0])
        self.shadow_analysis('DNI/TOANI (-)', self.DNI, self.TOANI, 0.65)



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
    def plot_dif_ghi_ratio(self):

        h1, h2 = self.compute_h1_h2()

        self.plot_ratio_heatmap(
            ratios=self.DIF / self.GHI,
            filter=(self.DIF > 0) & (self.DNI > 0) & (self.GHI > 0),
            y_label='DIF/GHI (-)', title='Comparison of DIF and GHI for DNI<10W/m2. Should be close to 1.',
            ylimit=0.25, h1=h1, h2=h2)


    @individual_graph(GraphId.GHI_GHI_EST_RATIO)
    def plot_ghi_ghi_est_ratio(self):

        h1, h2 = self.compute_h1_h2()

        self.plot_ratio_heatmap(
            ratios=self.GHI / self.GHI_est,
            filter=(self.DNI > 0) & (self.GHI > 0) & (self.DNI < 5),
            y_label='GHI/(DNI*cSZA+DIF) (-)',
            title='Ratio of global to the sum of its components. Should be close to 1.',
            hlines=[(0.08, 0.8), (0.15, 1.0)],  # (position relative to 1, linewidth)
            ylimit=0.25, h1=h1, h2=h2)

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
        self.plot_ul_1c(
            self.GHI, "GHI",
            abcs=[[1.5, 1.2, 100], [1.2, 1.2, 50]],
            texts=[
                Text("GHI_PPL_UL_TOANI_SZA", 600, 885, 45),
                Text("GHI_ERL_UL_TOANI_SZA", 700, 800, 40)])

    @individual_graph(GraphId.UL_1C_DNI)
    def plot_ul_1c_dni(self):
        self.plot_ul_1c(
            self.DNI, "DNI", ymax=1700,
            abcs=[[1, 0, 0], [0.95, 0.2, 10]],
            texts=[
                Text("DNI_PPL_UL_TOANI", 450, 1420, -2),
                Text("DNI_ERL_UL_TOANI_SZA", 300, 1020, 12)])

    @individual_graph(GraphId.UL_1C_DIF)
    def plot_ul_1c_dif(self):
        self.plot_ul_1c(
            self.DIF, "DIF", ymax=1200,
            abcs=[[0.95, 1.2, 50], [0.75, 1.2, 30]],
            texts=[
                Text("DIF_PPL_UL_TOANI_SZA", 750, 700, 40),
                Text("DIF_ERL_UL_TOANI_SZA", 700, 490, 35)])

    @individual_graph(GraphId.HEATMAP_GHI)
    def plot_heatmap_ghi(self):
        self.plot_heatmap_timeseries("GHI", self.GHI, 700)

    @individual_graph(GraphId.HEATMAP_DNI)
    def plot_heatmap_dni(self):
        self.plot_heatmap_timeseries("DNI", self.DNI, 700)

    @individual_graph(GraphId.HEATMAP_DIF)
    def plot_heatmap_dif(self):
        self.plot_heatmap_timeseries("DIF", self.DIF, 700)



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



