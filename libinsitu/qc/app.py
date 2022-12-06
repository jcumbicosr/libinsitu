
from jupyter_dash import JupyterDash
from dash import Dash, html, dcc
import pandas as pd

from libinsitu import visual_qc


def get_data():

    # For more details on this function, check : https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.read_csv.html
    df = pd.read_csv(
        "data/sample-data.csv", # Input filename
        usecols=["date", "time", "global", "diffuse", "direct"], # Only get the columns we need (drop temp)
        parse_dates = [["date", "time"]], # We can combine several columns to build timestamp
        index_col = "date_time") # Use the parsed date time as index

    # Rename columns
    df.rename(inplace=True, columns={"global":"GHI", "diffuse":"DHI", "direct":"BNI"})

    # Metadata of the station
    df.attrs["latitude"] = 39.742
    df.attrs["longitude"] = -105.18
    df.attrs["elevation"] = 1828.8
    df.attrs["station_name"] = "BMS"

    return df

if __name__ == '__main__':
    app = JupyterDash(__name__)

    df = get_data()

    fig = visual_qc(df, engine="plotly")

    app.layout = dcc.Graph("timeseries", fig)

    app.run_server(mode='inline', port=8050)