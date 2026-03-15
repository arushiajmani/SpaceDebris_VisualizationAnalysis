"""
src/dashboard/callbacks/orbit.py
Globe rendering callbacks: orbit update, recolor on filter change, zoom buttons, UTC clock.
"""

import math
from datetime import datetime, timedelta

from dash import Input, Output, State, ctx, Patch
from dash.exceptions import PreventUpdate

from ..components import marker_arrays
from ..data_store import load_positions
from ..config import DEFAULT_CAMERA_EYE, CAMERA_MIN_R, CAMERA_MAX_R, ZOOM_IN_FACTOR, ZOOM_OUT_FACTOR


def register(app, store):

    # Mutable reference so apply_sat_count can update sim_start after a SET
    _sim_start = [store.sim_start]

    def get_sim_start():
        return _sim_start[0]

    def set_sim_start(val):
        _sim_start[0] = val

    # Expose setter so satellites.py callback can call it
    app._orbitwatch_set_sim_start = set_sim_start

    # ── Orbit update (slider) ─────────────────────────────────────────────────

    @app.callback(
        Output("orbit-graph",     "figure"),
        Output("tl-time-current", "children"),
        Input("time-slider",      "value"),
        State("active-filter-store", "data"),
    )
    def update_orbit(step, active_filter):
        pd_       = load_positions()
        sats      = pd_["satellites"]
        sat_names = list(sats.keys())

        xs = [sats[s][step]["position_km"]["x"] for s in sat_names]
        ys = [sats[s][step]["position_km"]["y"] for s in sat_names]
        zs = [sats[s][step]["position_km"]["z"] for s in sat_names]

        af            = active_filter or {}
        warning_sats  = set(af.get("warning_sats",  []))
        critical_sats = set(af.get("critical_sats", []))

        colors, sizes, symbols, outlines, hovers = marker_arrays(
            sat_names, xs, ys, zs, warning_sats, critical_sats
        )

        patched = Patch()
        patched["data"][4]["x"]                       = xs
        patched["data"][4]["y"]                       = ys
        patched["data"][4]["z"]                       = zs
        patched["data"][4]["marker"]["color"]         = colors
        patched["data"][4]["marker"]["size"]          = sizes
        patched["data"][4]["marker"]["symbol"]        = symbols
        patched["data"][4]["marker"]["line"]["color"] = outlines
        patched["data"][4]["text"]                    = hovers

        start = datetime.fromisoformat(get_sim_start())
        t     = start + timedelta(minutes=step * store.timestep)
        label = f"T+{step * store.timestep:05.1f}  {t.strftime('%H:%M UTC')}"
        return patched, label

    # ── Recolor on filter change (without slider moving) ─────────────────────

    @app.callback(
        Output("orbit-graph", "figure", allow_duplicate=True),
        Input("active-filter-store", "data"),
        State("time-slider",         "value"),
        prevent_initial_call=True,
    )
    def recolor_graph(active_filter, step):
        step      = step or 0
        pd_       = load_positions()
        sats      = pd_["satellites"]
        sat_names = list(sats.keys())

        xs = [sats[s][step]["position_km"]["x"] for s in sat_names]
        ys = [sats[s][step]["position_km"]["y"] for s in sat_names]
        zs = [sats[s][step]["position_km"]["z"] for s in sat_names]

        af            = active_filter or {}
        warning_sats  = set(af.get("warning_sats",  []))
        critical_sats = set(af.get("critical_sats", []))

        colors, sizes, symbols, outlines, hovers = marker_arrays(
            sat_names, xs, ys, zs, warning_sats, critical_sats
        )

        patched = Patch()
        patched["data"][4]["marker"]["color"]         = colors
        patched["data"][4]["marker"]["size"]          = sizes
        patched["data"][4]["marker"]["symbol"]        = symbols
        patched["data"][4]["marker"]["line"]["color"] = outlines
        patched["data"][4]["text"]                    = hovers
        return patched

    # ── Zoom buttons ──────────────────────────────────────────────────────────

    @app.callback(
        Output("orbit-graph", "figure", allow_duplicate=True),
        Input("zoom-in-btn",  "n_clicks"),
        Input("zoom-out-btn", "n_clicks"),
        State("orbit-graph",  "relayoutData"),
        prevent_initial_call=True,
    )
    def zoom_globe(zoom_in, zoom_out, relayout):
        triggered = ctx.triggered_id
        factor    = ZOOM_IN_FACTOR if triggered == "zoom-in-btn" else ZOOM_OUT_FACTOR

        eye = dict(DEFAULT_CAMERA_EYE)
        if relayout and "scene.camera.eye.x" in relayout:
            eye = {
                "x": relayout.get("scene.camera.eye.x", eye["x"]),
                "y": relayout.get("scene.camera.eye.y", eye["y"]),
                "z": relayout.get("scene.camera.eye.z", eye["z"]),
            }
        elif relayout and "scene.camera" in relayout:
            eye = relayout["scene.camera"].get("eye", eye)

        r     = math.sqrt(eye["x"]**2 + eye["y"]**2 + eye["z"]**2)
        new_r = max(CAMERA_MIN_R, min(CAMERA_MAX_R, r * factor))
        scale = new_r / r if r > 0 else 1.0

        patched = Patch()
        patched["layout"]["scene"]["camera"]["eye"] = {
            "x": eye["x"] * scale,
            "y": eye["y"] * scale,
            "z": eye["z"] * scale,
        }
        return patched

    # ── UTC clock ─────────────────────────────────────────────────────────────

    @app.callback(
        Output("utc-clock", "children"),
        Input("clock-interval", "n_intervals"),
    )
    def tick_clock(_):
        return datetime.utcnow().strftime("%Y-%m-%d · %H:%M:%S")