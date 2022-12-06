import numpy as np
from matplotlib import pyplot as plt
from matplotlib.gridspec import GridSpec

from libinsitu import info
from libinsitu.qc.matplot.graphs import BaseMatplotlibGraphs, MC_CLEAR_COLOR


class MaplotLibGraphs(BaseMatplotlibGraphs):

    def main_layout(self) :
        """ Render main layout """

        info("QC: visual plot preparation")
        fig = plt.figure(figsize=(19.2, 9.93))

        # =====================================================================
        # First column : time series + heatmaps + ratios
        # =====================================================================

        # Draw grid
        grid = GridSpec(8 if self.cams_df is None else 9, 1)
        grid.update(
            left=0.035, right=0.32,
            bottom=0.03, top=0.98,
            hspace=0.02, wspace=0.05)

        # -- Plot time series

        plt.subplot(grid[0, 0])
        self.plot_timeseries("GHI", self.GHI, 1400)

        plt.subplot(grid[1, 0])
        self.plot_timeseries("DNI", self.DNI, 1400)

        plt.subplot(grid[2, 0])
        self.plot_timeseries("DIF", self.DIF, 1000)

        # -- Plot Heatmaps

        plt.subplot(grid[3, 0])
        self.plot_heatmap_timeseries("GHI", self.GHI, 700)

        plt.subplot(grid[4, 0])
        self.plot_heatmap_timeseries("DNI", self.DNI, 700)

        plt.subplot(grid[5, 0])
        self.plot_heatmap_timeseries("DIF", self.DIF, 700)

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

        # DIF / GHI
        plt.subplot(grid[6, 0])
        self.plot_ratio_heatmap(
            ratios=self.DIF / self.GHI,
            filter=(self.DIF > 0) & (self.DNI > 0) & (self.GHI > 0),
            y_label='DIF/GHI (-)', title='Comparison of DIF and GHI for DNI<10W/m2. Should be close to 1.',
            ylimit=0.25, h1=h1, h2=h2)

        # GHI / estimated GHI
        plt.subplot(grid[7, 0])
        self.plot_ratio_heatmap(
            ratios=self.GHI / self.GHI_est,
            filter=(self.DNI > 0) & (self.GHI > 0) & (self.DNI < 5),
            y_label='GHI/(DNI*cSZA+DIF) (-)',
            title='Ratio of global to the sum of its components. Should be close to 1.',
            hlines=[(0.08, 0.8), (0.15, 1.0)], # (position relative to 1, linewidth)
            ylimit=0.25, h1=h1, h2=h2)

        # GHI / Clear sky
        if self.cams_df is not None:
            plt.subplot(grid[8, 0])
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


        # =====================================================================
        # % % Part4: ERL& PPL tests
        # =====================================================================

        gs2 = GridSpec(4, 6)
        gs2.update(
            left=0.07, right=0.97,
            bottom=0.1, top=0.98,
            hspace=0.25, wspace=0.25)


        plt.subplot(gs2[0, 2])
        self.plot_bsrn_1c(self.GHI, "GHI", [[1.5, 1.2, 100], [1.2, 1.2, 50]])

        plt.subplot(gs2[1, 2])
        self.plot_bsrn_1c(self.DNI, "DNI", [[1, 0, 0], [0.95, 0.2, 10]])

        plt.subplot(gs2[2, 2])
        self.plot_bsrn_1c(self.DIF, "DIF", [[0.95, 1.2, 50],[0.75, 1.2, 30]])


        # BSRN 2C
        plt.subplot(gs2[0, 3])
        self.bsrn_2c()

        # SERI-Kn
        plt.subplot(gs2[1, 3])
        self.seri_kn()

        # SERI-K
        plt.subplot(gs2[2, 3])
        self.seri_k()

        # BSRN Closure
        plt.subplot(gs2[3, 2])
        self.bsrn_closure()

        # BRSN Closure ratio
        plt.subplot(gs2[3, 3])
        im = self.bsrn_closure_ratio()

        # Color legend
        cb_ax = fig.add_axes([0.38, 0.04, 0.28, 0.01])
        cbar = fig.colorbar(im, cax=cb_ax, orientation='horizontal', label='point density (-)')
        cbar.set_ticks([])

        # -- Third column

        # -- Text info
        self.print_info()

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
        self.histo_qc(self.GHI, self.flag_df.KT, 'GHI/TOA', y_label=True)

        plt.subplot(gs3b[1:3, 7])
        self.histo_qc(self.DNI, self.flag_df.Kn, 'DNI/TOANI')

        plt.subplot(gs3b[1:3, 8])
        self.histo_qc(self.DIF, self.flag_df.K, 'DIF/GHI',legend_pos='upper left')

        if self.cams_df is None :
            gs3 = GridSpec(7, 3)
            shadow_row = 3
        else:
            gs3 = GridSpec(9, 3)
            shadow_row = 5

        gs3.update(left=0.0, right=0.99, bottom=0.05, top=0.875, hspace=0.1, wspace=0.2)

        # -- Horizontality graph
        if self.cams_df is not None:

            info("Horizontality test")
            plt.subplot(gs3[3:5, 2])

            self.horizontality_graph()


        # -- Shadow analysis
        info("Shadow analysis (GHI)")

        plt.subplot(gs3[shadow_row:shadow_row+2, 2])
        self.shadow_analysis('GHI/TOA (-)', self.GHI, self.TOA, 0.85)

        plt.subplot(gs3[shadow_row + 2:shadow_row + 4, 2])
        self.shadow_analysis('DNI/TOANI (-)', self.DNI, self.TOANI, 0.65)
