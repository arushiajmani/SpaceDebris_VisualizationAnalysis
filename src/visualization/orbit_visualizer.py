"""
orbit_visualizer.py  —  OrbitWatch  |  Figure builder

Trace layout (fixed — app.py depends on these indices):
  fig.data[0]  Earth surface
  fig.data[1]  Lat/lon grid overlay
  fig.data[2]  Atmosphere glow
  fig.data[3]  Starfield
  fig.data[4]  Satellite markers   ← Patch target in app.py
  fig.data[5+] Orbit trail segments
"""

import plotly.graph_objects as go

from .utils      import load_positions
from .earth      import create_earth
from .warnings   import load_warning_satellites
from .satellites import build_satellite_trace
from .orbits     import build_orbit_traces

# Number of Earth-layer traces — satellite markers always land at this index
_SAT_INDEX = 4


def _base_layout():
    return dict(
        uirevision="orbit",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor ="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        scene=dict(
            xaxis=dict(
                visible=False, showgrid=False, zeroline=False,
                showspikes=False, showticklabels=False,
                # Disable the axis drag handle (the arrow)
                showaxeslabels=False,
            ),
            yaxis=dict(
                visible=False, showgrid=False, zeroline=False,
                showspikes=False, showticklabels=False,
                showaxeslabels=False,
            ),
            zaxis=dict(
                visible=False, showgrid=False, zeroline=False,
                showspikes=False, showticklabels=False,
                showaxeslabels=False,
            ),
            bgcolor="rgba(2,5,14,0.97)",
            aspectmode="data",
            camera=dict(
                eye=dict(x=1.6, y=1.4, z=0.9),
                up=dict(x=0, y=0, z=1),
            ),
        ),
        modebar=dict(remove=["all"]),
    )


def visualize(positions_file: str) -> go.Figure:
    positions_data = load_positions(positions_file)
    satellites     = positions_data["satellites"]
    sat_names      = list(satellites.keys())

    warning_sats, critical_sats = load_warning_satellites()

    xs = [satellites[s][0]["position_km"]["x"] for s in sat_names]
    ys = [satellites[s][0]["position_km"]["y"] for s in sat_names]
    zs = [satellites[s][0]["position_km"]["z"] for s in sat_names]

    earth_traces = create_earth()                     # 4 traces
    sat_trace    = build_satellite_trace(
        xs, ys, zs, sat_names, warning_sats, critical_sats
    )
    orbit_traces = build_orbit_traces(satellites, warning_sats, critical_sats)

    fig = go.Figure(data=earth_traces + [sat_trace] + orbit_traces)
    fig.update_layout(**_base_layout())
    return fig


def visualize_step(positions_file: str, step: int) -> go.Figure:
    """
    Return a full figure with satellite markers at time `step`.
    Orbit trails are always the full trajectory.
    """
    positions_data = load_positions(positions_file)
    satellites     = positions_data["satellites"]
    sat_names      = list(satellites.keys())

    xs = [satellites[s][step]["position_km"]["x"] for s in sat_names]
    ys = [satellites[s][step]["position_km"]["y"] for s in sat_names]
    zs = [satellites[s][step]["position_km"]["z"] for s in sat_names]

    fig = visualize(positions_file)
    fig.data[_SAT_INDEX].x = xs
    fig.data[_SAT_INDEX].y = ys
    fig.data[_SAT_INDEX].z = zs
    return fig