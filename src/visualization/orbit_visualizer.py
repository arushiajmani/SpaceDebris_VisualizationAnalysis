import plotly.graph_objects as go

from .utils import load_positions
from .earth import create_earth
from .warnings import load_warning_satellites
from .satellites import build_satellite_trace
from .orbits import build_orbit_traces


def visualize(positions_file):

    positions_data = load_positions(positions_file)

    satellites = positions_data["satellites"]
    sat_names = list(satellites.keys())

    warning_sats = load_warning_satellites()

    xs, ys, zs = [], [], []

    for sat in sat_names:
        pos = satellites[sat][0]["position_km"]

        xs.append(pos["x"])
        ys.append(pos["y"])
        zs.append(pos["z"])

    earth = create_earth()

    satellite_trace = build_satellite_trace(xs, ys, zs, sat_names, warning_sats)

    orbit_traces = build_orbit_traces(satellites)

    fig = go.Figure(
        data=[earth, satellite_trace] + orbit_traces
    )

    fig.update_layout(
        uirevision="orbit",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        scene=dict(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            zaxis=dict(visible=False),
            aspectmode="data",
            bgcolor="rgba(0,0,0,0)",
            camera=dict(eye=dict(x=1.5, y=1.5, z=1.5))
        )
    )

    return fig
def visualize_step(positions_file, step):

    positions_data = load_positions(positions_file)

    satellites = positions_data["satellites"]
    sat_names = list(satellites.keys())

    xs, ys, zs = [], [], []

    for sat in sat_names:
        pos = satellites[sat][step]["position_km"]

        xs.append(pos["x"])
        ys.append(pos["y"])
        zs.append(pos["z"])

    # build base figure
    fig = visualize(positions_file)

    # update satellite marker positions
    fig.data[1].x = xs
    fig.data[1].y = ys
    fig.data[1].z = zs

    return fig
#fig.data[0] → Earth
#fig.data[1] → satellite markers
#fig.data[2+] → orbit trails
