"""
src/dashboard/callbacks/satellites.py
Satellite counter (+/−) and SET live re-propagation.
Writes new positions + warnings to disk after SET so update_orbit always reads from file.
"""

import json
from datetime import datetime, timedelta

import plotly.graph_objects as go
from dash import Input, Output, State, ctx, html
from dash.exceptions import PreventUpdate

from ..config import MAX_SATELLITES, DETECTION_THRESHOLD_KM
from ..data_store import load_satellites_db, recompute_pc

# Internal pipeline helpers — imported from the existing analysis module
from src.analysis.close_approach_detector import (
    compute_distance,
    compute_proxy_pc,
    detect_close_approaches,
)


def _severity(dist_km: float) -> str:
    if dist_km < 5:   return "CRITICAL"
    if dist_km < 25:  return "WARNING"
    return "CAUTION"


def register(app, store):

    # ── Counter +/− ───────────────────────────────────────────────────────────

    @app.callback(
        Output("pending-sat-count", "data"),
        Output("sat-count-display", "children"),
        Input("sat-inc-btn", "n_clicks"),
        Input("sat-dec-btn", "n_clicks"),
        State("pending-sat-count", "data"),
        prevent_initial_call=True,
    )
    def update_sat_counter(_, __, current):
        triggered = ctx.triggered_id
        new_val   = (min(current + 10, MAX_SATELLITES) if triggered == "sat-inc-btn"
                     else max(current - 10, 10))
        return new_val, str(new_val)

    # ── SET — live re-propagation ─────────────────────────────────────────────

    @app.callback(
        Output("live-warnings-store",  "data"),
        Output("orbit-graph",          "figure", allow_duplicate=True),
        Output("sat-count-status",     "children"),
        Output("stat-tracked",         "children"),
        Output("active-filter-store",  "data", allow_duplicate=True),
        Input("sat-apply-btn",         "n_clicks"),
        State("pending-sat-count",     "data"),
        prevent_initial_call=True,
    )
    def apply_sat_count(_, n_sats):
        if n_sats is None or n_sats < 1:
            raise PreventUpdate

        from skyfield.api import EarthSatellite, load as skyload

        # 1. Load TLE records from disk
        db   = load_satellites_db()
        recs = db.get("satellites", [])[:min(n_sats, MAX_SATELLITES)]
        if not recs:
            raise PreventUpdate

        # 2. Build EarthSatellite objects
        ts   = skyload.timescale()
        sats = []
        for r in recs:
            try:
                sats.append(EarthSatellite(
                    r["tle"]["line1"], r["tle"]["line2"], r["name"]
                ))
            except Exception:
                pass

        # 3. Propagate
        t0    = ts.now()
        times = [ts.utc(t0.utc_datetime() + timedelta(minutes=i))
                 for i in range(store.duration)]

        positions_new = {}
        for sat in sats:
            sat_pos = []
            for t in times:
                p = sat.at(t).position.km
                sat_pos.append({
                    "time":        t.utc_iso(),
                    "position_km": {"x": float(p[0]),
                                    "y": float(p[1]),
                                    "z": float(p[2])},
                })
            positions_new[sat.name] = sat_pos

        # 4. Detect conjunctions
        positions_wrapper = {"satellites": positions_new}
        new_warnings_raw  = detect_close_approaches(
            positions_wrapper, threshold_km=DETECTION_THRESHOLD_KM
        )
        new_warnings = recompute_pc(new_warnings_raw)

        # 5. Rebuild figure
        from src.visualization.earth      import create_earth
        from src.visualization.satellites import build_satellite_trace
        from src.visualization.orbits     import build_orbit_traces

        warning_sats  = ({w["satellite_a"] for w in new_warnings} |
                         {w["satellite_b"] for w in new_warnings})
        critical_sats = ({w["satellite_a"] for w in new_warnings
                          if w.get("severity") == "CRITICAL"} |
                         {w["satellite_b"] for w in new_warnings
                          if w.get("severity") == "CRITICAL"})

        sat_names = list(positions_new.keys())
        xs = [positions_new[s][0]["position_km"]["x"] for s in sat_names]
        ys = [positions_new[s][0]["position_km"]["y"] for s in sat_names]
        zs = [positions_new[s][0]["position_km"]["z"] for s in sat_names]

        earth_traces = create_earth()
        sat_trace    = build_satellite_trace(xs, ys, zs, sat_names,
                                             warning_sats, critical_sats)
        orbit_traces = build_orbit_traces(positions_new, warning_sats, critical_sats)

        new_fig = go.Figure(data=earth_traces + [sat_trace] + orbit_traces)
        new_fig.update_layout(
            uirevision=f"orbit-{n_sats}",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor ="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=0, b=0),
            scene=dict(
                xaxis=dict(visible=False, showgrid=False, zeroline=False,
                           showspikes=False, showticklabels=False, showaxeslabels=False),
                yaxis=dict(visible=False, showgrid=False, zeroline=False,
                           showspikes=False, showticklabels=False, showaxeslabels=False),
                zaxis=dict(visible=False, showgrid=False, zeroline=False,
                           showspikes=False, showticklabels=False, showaxeslabels=False),
                bgcolor="rgba(2,5,14,0.97)", aspectmode="data",
                camera=dict(eye=dict(x=1.6, y=1.4, z=0.9), up=dict(x=0, y=0, z=1)),
            ),
            modebar=dict(remove=["all"]),
        )

        # 6. Write back to disk
        retrieved_time   = datetime.utcnow().isoformat()
        positions_output = {
            "metadata": {
                "simulation_start":  retrieved_time,
                "time_step_minutes": store.timestep,
                "duration_minutes":  store.duration,
                "satellite_count":   len(positions_new),
            },
            "satellites": positions_new,
        }
        with open("debug/positions.json", "w") as f:
            json.dump(positions_output, f)

        warnings_output = {
            "warning_count":  len(new_warnings),
            "warning_count_by_severity": {
                "CRITICAL": sum(1 for w in new_warnings if w.get("severity") == "CRITICAL"),
                "WARNING":  sum(1 for w in new_warnings if w.get("severity") == "WARNING"),
                "CAUTION":  sum(1 for w in new_warnings if w.get("severity") == "CAUTION"),
            },
            "warnings": new_warnings,
        }
        with open("debug/warnings.json", "w") as f:
            json.dump(warnings_output, f)

        # 7. Update SIM_START in orbit callback
        if hasattr(app, "_orbitwatch_set_sim_start"):
            app._orbitwatch_set_sim_start(retrieved_time)

        msg = html.Span(
            f"✓ {len(sats)} satellites  ·  {len(new_warnings)} conjunctions",
            style={"color":"#00e5c0","fontSize":"9px",
                   "fontFamily":"'Space Mono',monospace"},
        )

        new_active_filter = {
            "warning_sats":  list(warning_sats),
            "critical_sats": list(critical_sats),
        }

        return (new_warnings, new_fig, msg,
                str(len(sats)), new_active_filter)