from plotly.subplots import make_subplots
import plotly.express as px
from libinsitu.qc.matplot import MaplotLibGraphs
import datashader as ds
import datashader.transfer_functions as tf

class PlotlyGraphs(MaplotLibGraphs) :

    def main_layout(self):

        fig = make_subplots(rows=3, cols=1, shared_xaxes=True)

        fig.add_trace(
            self.plot_timeseries("GHI", self.GHI, 1400),
            row=1, col=1)

        fig.add_trace(
            self.plot_timeseries("DNI", self.DNI, 1400),
            row=2, col=1)

        fig.add_trace(
            self.plot_timeseries("DIF", self.DIF, 1000),
            row=3, col=1)

        return fig


    def plot_timeseries(self, label, data, ymax):

        df = data.to_frame("y")
        # Time as int
        df["x"] = data.index.astype('int64')

        x_range = (df.x[0], df.x[-1])
        y_range = (0, ymax)

        cvs = ds.Canvas(x_range=x_range, y_range=y_range, plot_height=100, plot_width=900)

        line = cvs.line(df, 'x', 'y')
        img = tf.shade(line).to_pil()

        print(type(cvs), type(img), cvs, img)

        im = px.imshow(img)

        return im.data[0]
