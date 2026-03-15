"""
app.py  —  OrbitWatch  |  Space Situational Awareness Dashboard

Changes in this version
───────────────────────
1. Satellite count SET — re-propagates live from the already-fetched
   satellites.json TLEs + re-runs conjunction detection. No subprocess.
2. Pc now always visible in conjunction cards (was hidden when value==0).
3. Conjunction Events nav → opens full sorted table modal.
4. Risk Dashboard nav → opens severity breakdown + top-risk chart.
5. Distance filter default max set to 99999 (show all by default).
   Filter fires on page load via allow_duplicate=False pattern.
"""

from dash import Dash, dcc, html, ctx, Patch
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from datetime import datetime, timedelta
import math
import json

from src.visualization.orbit_visualizer import visualize, visualize_step


# ── Low-level pipeline helpers (used for live re-propagation) ─────────────────

def _compute_distance(p1, p2):
    return math.sqrt(
        (p1["x"] - p2["x"]) ** 2 +
        (p1["y"] - p2["y"]) ** 2 +
        (p1["z"] - p2["z"]) ** 2
    )

def _proxy_pc(dist_km: float, threshold_km: float = 500) -> float:
    """
    Scaled Chan-style proxy Pc.

    Uses sigma = threshold_km / 3 so that:
      - dist = 0        → Pc ≈ 1.0   (certain collision)
      - dist = thresh/3 → Pc ≈ 0.61  (high risk)
      - dist = thresh   → Pc ≈ 0.011 (low, at boundary)

    This keeps Pc as a real number across the full detection window
    instead of underflowing to 0 for anything beyond ~3 km.
    """
    if dist_km <= 0:
        return 1.0
    sigma = max(threshold_km / 3.0, 1.0)
    raw   = math.exp(-0.5 * (dist_km / sigma) ** 2)
    # Clamp to avoid exact 0.0 from extreme float underflow
    return max(raw, 1e-15)

def _severity(dist_km: float) -> str:
    if dist_km < 5:   return "CRITICAL"
    if dist_km < 25:  return "WARNING"
    return "CAUTION"

def _detect_conjunctions(positions_dict: dict, threshold_km: float = 500) -> list:
    """Re-run conjunction detection on an in-memory positions dict."""
    sat_names = list(positions_dict.keys())
    results   = []
    for i in range(len(sat_names)):
        for j in range(i + 1, len(sat_names)):
            a, b = sat_names[i], sat_names[j]
            traj_a, traj_b = positions_dict[a], positions_dict[b]
            min_dist = float("inf")
            closest_t = None
            for k in range(len(traj_a)):
                d = _compute_distance(
                    traj_a[k]["position_km"], traj_b[k]["position_km"]
                )
                if d < min_dist:
                    min_dist = d
                    closest_t = traj_a[k]["time"]
            if 0.001 < min_dist < threshold_km:
                results.append({
                    "satellite_a": a,
                    "satellite_b": b,
                    "distance_km": min_dist,
                    "time":        closest_t,
                    "proxy_pc":    _proxy_pc(min_dist, threshold_km),
                    "severity":    _severity(min_dist),
                })
    results.sort(key=lambda w: w["distance_km"])
    return results


# ── Data loaders ──────────────────────────────────────────────────────────────

def load_positions():
    with open("debug/positions.json") as f:
        return json.load(f)

def load_warnings():
    try:
        with open("debug/warnings.json") as f:
            return json.load(f)
    except Exception:
        return {"warning_count": 0, "warnings": [],
                "warning_count_by_severity": {"CRITICAL": 0, "WARNING": 0, "CAUTION": 0}}

def load_satellites_db():
    try:
        with open("debug/satellites.json") as f:
            return json.load(f)
    except Exception:
        return {"satellites": [], "metadata": {}}


# ── Bootstrap ─────────────────────────────────────────────────────────────────

positions_data = load_positions()
metadata       = positions_data["metadata"]
warnings_data  = load_warnings()

ALL_WARNINGS_RAW = warnings_data.get("warnings", [])

# Recompute proxy_pc for every warning loaded from disk — the stored value
# may be 0.0 if generated with the old sigma=0.5 formula.  We recompute
# using the scaled-sigma approach (sigma = threshold/3 = 500/3 ≈ 167 km).
def _recompute_pc(warnings_list: list, threshold_km: float = 500) -> list:
    out = []
    for w in warnings_list:
        w2 = dict(w)
        stored = w2.get("proxy_pc", 0)
        # Recompute if stored value looks like it underflowed (< 1e-14)
        if stored is None or stored < 1e-14:
            w2["proxy_pc"] = _proxy_pc(w2["distance_km"], threshold_km)
        out.append(w2)
    return out

ALL_WARNINGS = _recompute_pc(ALL_WARNINGS_RAW)
SAT_COUNT    = metadata["satellite_count"]
DURATION     = metadata["duration_minutes"]
TIMESTEP     = metadata["time_step_minutes"]
SIM_START    = metadata["simulation_start"]

_sev          = warnings_data.get("warning_count_by_severity", {})
INIT_CRITICAL = _sev.get("CRITICAL", sum(1 for w in ALL_WARNINGS if w.get("severity") == "CRITICAL"))
INIT_WARNING  = _sev.get("WARNING",  sum(1 for w in ALL_WARNINGS if w.get("severity") == "WARNING"))
INIT_CAUTION  = _sev.get("CAUTION",  sum(1 for w in ALL_WARNINGS if w.get("severity") == "CAUTION"))
INIT_TOTAL    = len(ALL_WARNINGS)

fig_initial   = visualize("debug/positions.json")


# ── Constants ─────────────────────────────────────────────────────────────────

PC_LEVELS = [0, 1e-2, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]

PC_MARKS  = {
    0: "any",
    1: "1e-2",
    2: "0.1",
    3: "0.3",
    4: "0.5",
    5: "0.7",
    6: "0.9",
    7: "1.0",
}

SEVERITY_COLOR = {
    "CRITICAL": "#ff4757",
    "WARNING":  "#ff9f1c",
    "CAUTION":  "#48a5ff",
}


# ── UI helpers ────────────────────────────────────────────────────────────────

def fmt_pc(pc_val: float) -> str:
    """Format a Pc value for display — always show something."""
    if pc_val is None:
        return "—"
    if pc_val >= 0.01:
        return f"{pc_val:.3f}"
    return f"{pc_val:.2e}"


EARTH_RADIUS_VIZ = 6_371  # km

def _regime_color_viz(x: float, y: float, z: float) -> str:
    alt = math.sqrt(x**2 + y**2 + z**2) - EARTH_RADIUS_VIZ
    if alt < 2_000:   return "#00e5c0"
    if alt < 10_000:  return "#48a5ff"
    if alt < 37_000:  return "#a78bfa"
    return "#6e7bff"


def _marker_arrays(sat_names, xs, ys, zs, warning_sats: set, critical_sats: set):
    """
    Compute per-satellite color/size/symbol arrays reflecting current filter state.
    Called both when filters change (recolor) and when the time slider moves.
    """
    colors, sizes, symbols, outlines, hovers = [], [], [], [], []

    for name, x, y, z in zip(sat_names, xs, ys, zs):
        alt = math.sqrt(x**2 + y**2 + z**2) - EARTH_RADIUS_VIZ
        regime = ("LEO" if alt < 2_000 else
                  "MEO" if alt < 10_000 else
                  "GEO" if alt < 37_000 else "HEO")

        if name in critical_sats:
            colors.append("#ff4757"); sizes.append(7); symbols.append("diamond")
            outlines.append("rgba(255,255,255,0.3)")
            status = "🔴 CRITICAL"
        elif name in warning_sats:
            colors.append("#ff9f1c"); sizes.append(5); symbols.append("diamond")
            outlines.append("rgba(255,255,255,0.2)")
            status = "🟠 WARNING"
        else:
            colors.append(_regime_color_viz(x, y, z))
            sizes.append(3); symbols.append("circle")
            outlines.append("rgba(0,0,0,0)")
            status = "🟢 NOMINAL"

        hovers.append(
            f"<b>{name}</b><br>"
            f"Alt: {alt:,.0f} km  [{regime}]<br>"
            f"Status: {status}<br>"
            f"<span style='color:#5a7090'>x:{x:.0f}  y:{y:.0f}  z:{z:.0f}</span>"
        )

    return colors, sizes, symbols, outlines, hovers


def conj_card(w):
    color    = SEVERITY_COLOR.get(w.get("severity", "CAUTION"), "#48a5ff")
    severity = w.get("severity", "CAUTION")
    pc_val   = w.get("proxy_pc")          # may be None or very small float
    pc_str   = fmt_pc(pc_val)
    t_str    = w.get("time", "")[-8:-3] if w.get("time") else "—"

    # Log-scale bar: map Pc range [1e-15, 1] → [2%, 96%]
    if pc_val and pc_val > 0:
        import math as _math
        log_pc  = _math.log10(max(pc_val, 1e-15))   # e.g. -15 .. 0
        log_min = -15.0
        bar_pct = int(2 + (log_pc - log_min) / (0 - log_min) * 94)
        bar_pct = max(2, min(96, bar_pct))
    else:
        bar_pct = 2

    return html.Div(className="conj-card", style={"borderLeft": f"3px solid {color}"}, children=[

        # Header row
        html.Div(className="conj-card-header", children=[
            html.Span(f"● {severity}",
                      style={"color": color, "fontSize": "10px", "letterSpacing": "1px"}),
            html.Span(t_str, style={"color": "#5a7090", "fontSize": "10px"}),
        ]),

        # Satellite pair
        html.Div(f"{w['satellite_a']} × {w['satellite_b']}", className="conj-pair"),

        # Distance + Pc inline
        html.Div(className="conj-meta", children=[
            html.Span(f"Δ {w['distance_km']:.2f} km",
                      style={"color": "#48a5ff", "fontFamily": "'Space Mono',monospace",
                             "fontSize": "11px"}),
            html.Span(f"Pc {pc_str}",
                      style={"color": color, "fontFamily": "'Space Mono',monospace",
                             "fontSize": "11px", "marginLeft": "8px", "fontWeight": "700"}),
        ]),

        # Pc probability bar (log-scaled)
        html.Div(className="pc-bar-track", children=[
            html.Div(className="pc-bar-fill",
                     style={"width": f"{bar_pct}%", "background": color}),
        ]),
    ])


def conj_table_row(w, idx):
    """Full-width row for the Conjunction Events modal table."""
    color   = SEVERITY_COLOR.get(w.get("severity", "CAUTION"), "#48a5ff")
    pc_str  = fmt_pc(w.get("proxy_pc"))
    t_str   = w.get("time", "")[:16] if w.get("time") else "—"
    return html.Div(className="conj-table-row", children=[
        html.Span(str(idx + 1), className="ct-idx"),
        html.Span(w.get("severity", "—"),
                  className="ct-sev", style={"color": color}),
        html.Span(f"{w['satellite_a']} × {w['satellite_b']}", className="ct-pair"),
        html.Span(f"{w['distance_km']:.2f} km", className="ct-dist"),
        html.Span(pc_str, className="ct-pc", style={"color": color}),
        html.Span(t_str,  className="ct-time"),
    ])


def tle_row(sat):
    tle = sat.get("tle", {})
    return html.Div(className="tle-row", children=[
        html.Div(sat.get("name", "?"), className="tle-name"),
        html.Div(tle.get("line1", ""), className="tle-line"),
        html.Div(tle.get("line2", ""), className="tle-line"),
    ])


# ── App ───────────────────────────────────────────────────────────────────────

app = Dash(__name__, suppress_callback_exceptions=True)

app.layout = html.Div(id="root", children=[

    # ── Stores ────────────────────────────────────────────────────────────────
    dcc.Store(id="playing-store",     data=False),
    dcc.Store(id="pending-sat-count", data=SAT_COUNT),
    # Live warnings list (updated when sat count changes) — seeded with recomputed Pc
    dcc.Store(id="live-warnings-store", data=ALL_WARNINGS),
    # Currently active highlighted sets (updated by filter changes → drives graph recolor)
    dcc.Store(id="active-filter-store", data={
        "warning_sats":  [w["satellite_a"] for w in ALL_WARNINGS] +
                         [w["satellite_b"] for w in ALL_WARNINGS],
        "critical_sats": [w["satellite_a"] for w in ALL_WARNINGS if w.get("severity") == "CRITICAL"] +
                         [w["satellite_b"] for w in ALL_WARNINGS if w.get("severity") == "CRITICAL"],
    }),
    # ── Timers ────────────────────────────────────────────────────────────────
    dcc.Interval(id="clock-interval",     interval=1_000, n_intervals=0),
    dcc.Interval(id="animation-interval", interval=600,   n_intervals=0, disabled=True),

    # ══════════════════════════════════════════════════════════════════════════
    # TOP BAR
    # ══════════════════════════════════════════════════════════════════════════
    html.Header(id="topbar", children=[

        html.Div(id="brand", children=[
            html.Div("◎", className="brand-icon"),
            html.Div([
                html.Div("ORBITWATCH",                  id="brand-name"),
                html.Div("SPACE SITUATIONAL AWARENESS", id="brand-sub"),
            ]),
        ]),

        html.Div(id="live-status", children=[
            html.Span("●", className="pulse-dot"),
            html.Div([
                html.Div("LIVE FEED",
                         style={"fontSize":"11px","letterSpacing":"1.5px","color":"#00e5c0"}),
                html.Div("ACTIVE", style={"fontSize":"10px","color":"#5a7090"}),
            ]),
        ]),

        html.Div(id="utc-display", children=[
            html.Span("UTC ", style={"color":"#5a7090","fontSize":"11px"}),
            html.Span(id="utc-clock",
                      style={"fontFamily":"'Space Mono',monospace","color":"#c8d8f0"}),
        ]),

        html.Button("ℹ", id="info-btn", n_clicks=0, className="info-btn"),

        html.Div(id="alert-badge-div",
                 style={"marginLeft":"auto","display":"flex","gap":"6px",
                        "alignItems":"center",
                        "border":"1px solid rgba(255,71,87,0.35)",
                        "borderRadius":"20px","padding":"5px 14px",
                        "background":"rgba(255,71,87,0.06)"}, children=[
            html.Span(id="crit-badge",
                      style={"color":"#ff4757","fontFamily":"'Space Mono',monospace",
                             "fontSize":"11px","letterSpacing":"1px"},
                      children=f"▲ {INIT_CRITICAL} CRITICAL"),
            html.Span("·", style={"color":"#2a3a50"}),
            html.Span(id="warn-badge",
                      style={"color":"#ff9f1c","fontFamily":"'Space Mono',monospace",
                             "fontSize":"11px"},
                      children=f"{INIT_WARNING} WARN"),
            html.Span("·", style={"color":"#2a3a50"}),
            html.Span(id="caut-badge",
                      style={"color":"#48a5ff","fontFamily":"'Space Mono',monospace",
                             "fontSize":"11px"},
                      children=f"{INIT_CAUTION} CAUTION"),
        ]),
    ]),

    # ══════════════════════════════════════════════════════════════════════════
    # BODY
    # ══════════════════════════════════════════════════════════════════════════
    html.Div(id="body", children=[

        # ── LEFT SIDEBAR ──────────────────────────────────────────────────────
        html.Nav(id="sidebar", children=[

            html.Div("WORKSPACE", className="section-label"),
            html.Div([
                html.Div([html.Span("◎ "), html.Span("Orbital View")],
                         className="nav-item nav-active"),
                html.Div(id="nav-tle-db", n_clicks=0,
                         className="nav-item nav-item-clickable",
                         children=[html.Span("≡ "), html.Span("TLE Database"),
                                   html.Span("→", style={"marginLeft":"auto",
                                                          "color":"#5a7090","fontSize":"10px"})]),
                # Conjunction Events → opens full table
                html.Div(id="nav-conj-events", n_clicks=0,
                         className="nav-item nav-item-clickable",
                         children=[
                             html.Span("✦ "), html.Span("Conjunction Events"),
                             html.Span(id="conj-nav-badge",
                                       className="nav-badge badge-red",
                                       children=str(INIT_TOTAL)),
                         ]),
                # Risk Dashboard → opens risk summary
                html.Div(id="nav-risk-dashboard", n_clicks=0,
                         className="nav-item nav-item-clickable",
                         children=[
                             html.Span("⚠ "), html.Span("Risk Dashboard"),
                             html.Span(id="warn-nav-badge",
                                       className="nav-badge badge-amber",
                                       children=str(INIT_TOTAL)),
                         ]),
            ]),

            html.Hr(className="sidebar-hr"),

            # ── Tracked objects (live re-propagation) ─────────────────────────
            html.Div("TRACKED OBJECTS", className="section-label"),
            html.Div(className="sat-counter-row", children=[
                html.Button("−", id="sat-dec-btn", n_clicks=0, className="counter-btn"),
                html.Div(id="sat-count-display", className="counter-display",
                         children=str(SAT_COUNT)),
                html.Button("+", id="sat-inc-btn", n_clicks=0, className="counter-btn"),
                html.Button("SET", id="sat-apply-btn", n_clicks=0, className="apply-btn"),
            ]),
            html.Div(id="sat-count-status", className="input-status"),
            html.Div(className="sat-meta-note", children=[
                html.Span("max 500  ·  step 10", className="sat-meta-line"),
                html.Span(id="tle-freshness-note", className="sat-meta-line sat-meta-fresh",
                          children=f"TLE fetched {metadata.get('simulation_start','?')[:10]}  ·  static this session"),
            ]),

            html.Hr(className="sidebar-hr"),

            # ── Pc threshold ──────────────────────────────────────────────────
            html.Div("Pc THRESHOLD", className="section-label"),
            html.Div(className="pc-display-row", children=[
                html.Span("Min Pc", className="slider-label"),
                html.Span(id="pc-slider-display", className="slider-value pc-value-pill",
                          children="any"),
            ]),
            dcc.Slider(
                id="pc-threshold-slider",
                min=0, max=7, step=1, value=0,
                marks=None,
                className="ow-slider ow-slider-clean",
                tooltip={"always_visible": False},
            ),
            html.Div(className="pc-tick-row", children=[
                html.Span(lbl, className="pc-tick")
                for lbl in ["any","1e-2","0.1","0.3","0.5","0.7","0.9","1.0"]
            ]),

            html.Hr(className="sidebar-hr"),

            # ── Distance filter ───────────────────────────────────────────────
            html.Div("DISTANCE FILTER", className="section-label"),
            html.Div(className="dist-filter-row", children=[
                html.Div(className="dist-filter-group", children=[
                    html.Span("MIN km", className="dist-label"),
                    dcc.Input(id="min-dist-input", type="number", value=0,
                              min=0, max=50000, step=1, debounce=True,
                              className="ow-input dist-input", placeholder="0"),
                ]),
                html.Div(className="dist-filter-group", children=[
                    html.Span("MAX km", className="dist-label"),
                    dcc.Input(id="max-dist-input", type="number", value=500,
                              min=0, max=99999, step=10, debounce=True,
                              className="ow-input dist-input", placeholder="500"),
                ]),
            ]),
            # Severity tier reference — always fixed regardless of filter
            html.Div(className="severity-ref", children=[
                html.Div(className="sev-ref-item", children=[
                    html.Span("●", style={"color":"#ff4757","fontSize":"10px"}),
                    html.Span("CRIT  < 5 km", className="sev-ref-lbl"),
                ]),
                html.Div(className="sev-ref-item", children=[
                    html.Span("●", style={"color":"#ff9f1c","fontSize":"10px"}),
                    html.Span("WARN  < 25 km", className="sev-ref-lbl"),
                ]),
                html.Div(className="sev-ref-item", children=[
                    html.Span("●", style={"color":"#48a5ff","fontSize":"10px"}),
                    html.Span("CAUT  < 500 km", className="sev-ref-lbl"),
                ]),
            ]),
        ]),

        # ── CENTER ────────────────────────────────────────────────────────────
        html.Main(id="center", children=[

            # Wrapper so we can position controls absolutely over the graph
            html.Div(style={"position":"relative","flex":"1","minHeight":"0"}, children=[

                dcc.Graph(
                    id="orbit-graph",
                    figure=fig_initial,
                    config={
                        "displayModeBar": False,
                        "scrollZoom": True,
                        "modeBarButtonsToRemove": ["all"],
                    },
                    style={"height":"100%","width":"100%"},
                ),

                # Floating 3D controls — zoom + pan hint
                html.Div(id="globe-controls", children=[
                    html.Button("＋", id="zoom-in-btn",  n_clicks=0,
                                className="globe-ctrl-btn", title="Zoom in"),
                    html.Button("－", id="zoom-out-btn", n_clicks=0,
                                className="globe-ctrl-btn", title="Zoom out"),
                    html.Div(className="globe-ctrl-divider"),
                    html.Div(className="globe-ctrl-hint", children=[
                        html.Span("✥", className="globe-ctrl-icon"),
                        html.Span("drag to rotate", className="globe-ctrl-text"),
                    ]),
                    html.Div(className="globe-ctrl-hint", children=[
                        html.Span("⊙", className="globe-ctrl-icon"),
                        html.Span("scroll to zoom", className="globe-ctrl-text"),
                    ]),
                ]),
            ]),

            html.Div(id="timeline-bar", children=[
                html.Button("▶", id="play-toggle-btn", n_clicks=0,
                            className="tl-btn tl-play-btn"),
                dcc.Slider(
                    id="time-slider",
                    min=0, max=DURATION - 1, step=1, value=0,
                    marks={
                        i: {"label": f"{i}m",
                            "style": {"color":"#6a85a8","fontSize":"9px",
                                      "fontFamily":"'Space Mono',monospace"}}
                        for i in range(0, DURATION, 15)
                    },
                    className="tl-scrubber",
                    tooltip={"always_visible": False},
                    updatemode="mouseup",
                ),
                html.Div(id="tl-time-current", className="tl-label tl-label-current",
                         children="T+00:00"),
            ]),
        ]),

        # ── RIGHT PANEL ───────────────────────────────────────────────────────
        html.Aside(id="right-panel", children=[

            html.Div(id="stats-row", children=[
                html.Div([html.Span(id="stat-tracked",  className="stat-num",
                                   children=str(SAT_COUNT)),
                          html.Span(" tracked", className="stat-label")]),
                html.Div([html.Span(id="stat-critical", className="stat-num stat-red",
                                   children=str(INIT_CRITICAL)),
                          html.Span(" critical", className="stat-label")]),
                html.Div([html.Span(id="stat-warning",  className="stat-num stat-amber",
                                   children=str(INIT_WARNING)),
                          html.Span(" warnings", className="stat-label")]),
                html.Div([html.Span(id="stat-caution",  className="stat-num stat-blue",
                                   children=str(INIT_CAUTION)),
                          html.Span(" caution", className="stat-label")]),
            ]),

            html.Div(id="view-controls", children=[
                html.Div("3D VIEW", className="view-mode-badge"),
            ]),

            html.Hr(className="sidebar-hr"),
            html.Div("CONJUNCTION ALERTS", className="section-label"),
            html.Div(id="conj-list"),
        ]),
    ]),

    # ══════════════════════════════════════════════════════════════════════════
    # TLE DATABASE MODAL
    # ══════════════════════════════════════════════════════════════════════════
    html.Div(id="tle-modal", className="modal-overlay modal-hidden", children=[
        html.Div(className="modal-box", children=[
            html.Div(className="modal-header", children=[
                html.Span("TLE DATABASE", className="modal-title"),
                html.Span(id="tle-modal-meta", className="modal-subtitle"),
                html.Button("✕", id="close-tle-modal", n_clicks=0, className="modal-close"),
            ]),
            html.Div(className="modal-tabs", children=[
                html.Button("satellites.json", id="tab-parsed", n_clicks=0,
                            className="modal-tab modal-tab-active"),
                html.Button("raw_tle.txt",     id="tab-raw",    n_clicks=0,
                            className="modal-tab"),
            ]),
            html.Div(id="tle-modal-content", className="modal-content"),
        ]),
    ]),

    # ══════════════════════════════════════════════════════════════════════════
    # CONJUNCTION EVENTS MODAL  — full sorted table
    # ══════════════════════════════════════════════════════════════════════════
    html.Div(id="conj-modal", className="modal-overlay modal-hidden", children=[
        html.Div(className="modal-box modal-box-wide", children=[
            html.Div(className="modal-header", children=[
                html.Span("CONJUNCTION EVENTS", className="modal-title"),
                html.Span(id="conj-modal-subtitle", className="modal-subtitle"),
                html.Button("✕", id="close-conj-modal", n_clicks=0, className="modal-close"),
            ]),
            # Table header
            html.Div(className="conj-table-header", children=[
                html.Span("#",          className="ct-idx"),
                html.Span("SEVERITY",   className="ct-sev"),
                html.Span("PAIR",       className="ct-pair"),
                html.Span("MISS DIST",  className="ct-dist"),
                html.Span("Pc",         className="ct-pc"),
                html.Span("TCA (UTC)",  className="ct-time"),
            ]),
            html.Div(id="conj-table-content", className="modal-content"),
        ]),
    ]),

    # ══════════════════════════════════════════════════════════════════════════
    # RISK DASHBOARD MODAL  — severity summary
    # ══════════════════════════════════════════════════════════════════════════
    html.Div(id="risk-modal", className="modal-overlay modal-hidden", children=[
        html.Div(className="modal-box modal-box-risk", children=[
            html.Div(className="modal-header", children=[
                html.Span("RISK DASHBOARD", className="modal-title"),
                html.Span(id="risk-modal-subtitle", className="modal-subtitle"),
                html.Button("✕", id="close-risk-modal", n_clicks=0, className="modal-close"),
            ]),
            html.Div(id="risk-modal-content", className="modal-content risk-content"),
        ]),
    ]),

    # ══════════════════════════════════════════════════════════════════════════
    # INFO MODAL
    # ══════════════════════════════════════════════════════════════════════════
    html.Div(id="info-modal", className="modal-overlay modal-hidden", children=[
        html.Div(className="modal-box modal-box-info", children=[
            html.Div(className="modal-header", children=[
                html.Span("ORBITWATCH — GUIDE", className="modal-title"),
                html.Button("✕", id="close-info-modal", n_clicks=0, className="modal-close"),
            ]),
            html.Div(className="modal-content info-content", children=[

                html.Div(className="info-section", children=[
                    html.Div("SATELLITE COLOUR CODING", className="info-heading"),
                    html.Div(className="legend-grid", children=[

                        # Section sub-label
                        html.Div("CONJUNCTION RISK STATUS (overrides regime colour)",
                                 className="legend-sublabel"),

                        html.Div(className="legend-row", children=[
                            html.Div(className="legend-swatch-col", children=[
                                html.Span(className="legend-dot", style={"background":"#ff4757"}),
                                html.Span("◆", style={"color":"#ff4757","fontSize":"10px",
                                                       "marginLeft":"4px"}),
                            ]),
                            html.Div([
                                html.Span("CRITICAL  —  red diamond", className="legend-label",
                                          style={"color":"#ff4757"}),
                                html.Span(
                                    "Closest approach < 5 km within the 90-min window. "
                                    "Satellite is highlighted in the alerts panel with a red left border. "
                                    "Both satellites in the pair are marked.",
                                    className="legend-desc"),
                            ]),
                        ]),
                        html.Div(className="legend-row", children=[
                            html.Div(className="legend-swatch-col", children=[
                                html.Span(className="legend-dot", style={"background":"#ff9f1c"}),
                                html.Span("◆", style={"color":"#ff9f1c","fontSize":"10px",
                                                       "marginLeft":"4px"}),
                            ]),
                            html.Div([
                                html.Span("WARNING  —  amber diamond", className="legend-label",
                                          style={"color":"#ff9f1c"}),
                                html.Span(
                                    "Closest approach 5–25 km. Monitor closely. "
                                    "Alert card has amber border.",
                                    className="legend-desc"),
                            ]),
                        ]),
                        html.Div(className="legend-row", children=[
                            html.Div(className="legend-swatch-col", children=[
                                html.Span(className="legend-dot", style={"background":"#48a5ff"}),
                                html.Span("◆", style={"color":"#48a5ff","fontSize":"10px",
                                                       "marginLeft":"4px"}),
                            ]),
                            html.Div([
                                html.Span("CAUTION  —  blue diamond", className="legend-label",
                                          style={"color":"#48a5ff"}),
                                html.Span(
                                    "Closest approach 25–500 km. Within detection window. "
                                    "Low immediate risk but tracked.",
                                    className="legend-desc"),
                            ]),
                        ]),

                        html.Div("ORBITAL REGIME (when no conjunction risk)",
                                 className="legend-sublabel",
                                 style={"marginTop":"10px"}),

                        html.Div(className="legend-row", children=[
                            html.Span(className="legend-dot", style={"background":"#00e5c0"}),
                            html.Div([
                                html.Span("LEO  —  teal circle", className="legend-label",
                                          style={"color":"#00e5c0"}),
                                html.Span("Altitude < 2,000 km. Low Earth Orbit. "
                                          "Teal orbit trail, 3-segment fade (oldest dim → newest bright).",
                                          className="legend-desc"),
                            ]),
                        ]),
                        html.Div(className="legend-row", children=[
                            html.Span(className="legend-dot", style={"background":"#48a5ff"}),
                            html.Div([
                                html.Span("MEO  —  blue circle", className="legend-label",
                                          style={"color":"#48a5ff"}),
                                html.Span("Altitude 2,000–35,000 km. Medium Earth Orbit (GPS band). "
                                          "Blue orbit trail, single opacity.",
                                          className="legend-desc"),
                            ]),
                        ]),
                        html.Div(className="legend-row", children=[
                            html.Span(className="legend-dot", style={"background":"#a78bfa"}),
                            html.Div([
                                html.Span("GEO  —  purple circle", className="legend-label",
                                          style={"color":"#a78bfa"}),
                                html.Span("Altitude ≈ 35,786 km. Geostationary ring. "
                                          "Purple orbit trail.",
                                          className="legend-desc"),
                            ]),
                        ]),
                        html.Div(className="legend-row", children=[
                            html.Span(className="legend-dot", style={"background":"#6e7bff"}),
                            html.Div([
                                html.Span("HEO  —  indigo circle", className="legend-label",
                                          style={"color":"#6e7bff"}),
                                html.Span("Altitude > 37,000 km. High / Elliptical orbit. "
                                          "Indigo orbit trail.",
                                          className="legend-desc"),
                            ]),
                        ]),
                    ]),
                ]),

                html.Hr(className="sidebar-hr"),

                html.Div(className="info-section", children=[
                    html.Div("PROBABILITY OF COLLISION (Pc)", className="info-heading"),
                    html.Div(className="controls-grid", children=[
                        html.Div(className="ctrl-row", children=[
                            html.Span("What is Pc?", className="ctrl-key"),
                            html.Span(
                                "A dimensionless number 0→1 representing collision probability. "
                                "Computed using the Chan approximation: "
                                "Pc = exp(−½ · (d/σ)²) where d = miss distance and "
                                "σ = detection threshold / 3 ≈ 167 km.",
                                className="ctrl-desc"),
                        ]),
                        html.Div(className="ctrl-row", children=[
                            html.Span("Pc bar", className="ctrl-key"),
                            html.Span(
                                "The thin bar under each alert card is log-scaled: "
                                "a full bar means Pc ≈ 1 (near-certain collision); "
                                "a short bar means Pc is very small. "
                                "Color matches severity: red / amber / blue.",
                                className="ctrl-desc"),
                        ]),
                        html.Div(className="ctrl-row", children=[
                            html.Span("Pc threshold slider", className="ctrl-key"),
                            html.Span(
                                "8 ticks: any → 1e-2 → 0.1 → 0.3 → 0.5 → 0.7 → 0.9 → 1.0. "
                                "Finer resolution in the 0.1–1.0 zone where most real Pc values fall. "
                                "Hides alerts below the threshold and recolors the globe — "
                                "only satellites whose filtered pairs remain are highlighted.",
                                className="ctrl-desc"),
                        ]),
                        html.Div(className="ctrl-row", children=[
                            html.Span("Distance filter", className="ctrl-key"),
                            html.Span(
                                "Set MIN / MAX miss-distance band in km. Updates the alerts panel "
                                "and recolors the globe — satellites outside the band revert to "
                                "their regime color. "
                                "SEVERITY LABELS are fixed: CRITICAL < 5 km, WARNING < 25 km, "
                                "CAUTION < 500 km. The filter does not change these — "
                                "it only controls what is displayed.",
                                className="ctrl-desc"),
                        ]),
                    ]),
                ]),

                html.Hr(className="sidebar-hr"),

                html.Div(className="info-section", children=[
                    html.Div("CONTROLS", className="info-heading"),
                    html.Div(className="controls-grid", children=[
                        html.Div(className="ctrl-row", children=[
                            html.Span("▶ / ⏸", className="ctrl-key"),
                            html.Span("Play or pause the 90-minute simulation timeline.",
                                      className="ctrl-desc"),
                        ]),
                        html.Div(className="ctrl-row", children=[
                            html.Span("Timeline scrubber", className="ctrl-key"),
                            html.Span("Drag to any minute in the simulation window. Animation pauses automatically.",
                                      className="ctrl-desc"),
                        ]),
                        html.Div(className="ctrl-row", children=[
                            html.Span("Scroll wheel", className="ctrl-key"),
                            html.Span("Zoom in / out on the 3D globe.",
                                      className="ctrl-desc"),
                        ]),
                        html.Div(className="ctrl-row", children=[
                            html.Span("Left-drag globe", className="ctrl-key"),
                            html.Span("Rotate the 3D view freely.",
                                      className="ctrl-desc"),
                        ]),
                    ]),
                ]),

                html.Hr(className="sidebar-hr"),

                html.Div(className="info-section", children=[
                    html.Div("DATA SOURCES", className="info-heading"),
                    html.Div(className="controls-grid", children=[
                        html.Div(className="ctrl-row", children=[
                            html.Span("TLE source", className="ctrl-key"),
                            html.Span("CelesTrak active satellite catalog. Fetched once at pipeline startup.",
                                      className="ctrl-desc"),
                        ]),
                        html.Div(className="ctrl-row", children=[
                            html.Span("Propagator", className="ctrl-key"),
                            html.Span("SGP4 via Skyfield — industry-standard two-body orbital model.",
                                      className="ctrl-desc"),
                        ]),
                        html.Div(className="ctrl-row", children=[
                            html.Span("Sim window", className="ctrl-key"),
                            html.Span(f"{DURATION} min at {TIMESTEP}-min timesteps. All times in UTC.",
                                      className="ctrl-desc"),
                        ]),
                        html.Div(className="ctrl-row", children=[
                            html.Span("Max satellites", className="ctrl-key"),
                            html.Span("500. Use − / + then SET to change. Re-runs propagation + conjunction detection live from cached TLEs.",
                                      className="ctrl-desc"),
                        ]),
                    ]),
                ]),
            ]),
        ]),
    ]),
])


# ══════════════════════════════════════════════════════════════════════════════
#  CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

# ── Play / Pause ──────────────────────────────────────────────────────────────

@app.callback(
    Output("playing-store",      "data"),
    Output("animation-interval", "disabled"),
    Output("play-toggle-btn",    "children"),
    Output("play-toggle-btn",    "className"),
    Input("play-toggle-btn",     "n_clicks"),
    State("playing-store",       "data"),
    prevent_initial_call=True,
)
def toggle_playback(_, is_playing):
    now_playing = not is_playing
    icon = "⏸" if now_playing else "▶"
    cls  = "tl-btn tl-play-btn tl-playing" if now_playing else "tl-btn tl-play-btn"
    return now_playing, not now_playing, icon, cls


@app.callback(
    Output("time-slider",   "value"),
    Input("animation-interval", "n_intervals"),
    State("time-slider",    "value"),
    State("playing-store",  "data"),
    prevent_initial_call=True,
)
def advance_slider(_, current_value, is_playing):
    if not is_playing:
        raise PreventUpdate
    return (current_value + 1) % (DURATION - 1)


# ── Orbit graph — Patch to preserve camera, apply live filter colors ──────────

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

    colors, sizes, symbols, outlines, hovers = _marker_arrays(
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

    start = datetime.fromisoformat(SIM_START)
    t     = start + timedelta(minutes=step * TIMESTEP)
    label = f"T+{step * TIMESTEP:05.1f}  {t.strftime('%H:%M UTC')}"
    return patched, label


# ── Satellite counter ─────────────────────────────────────────────────────────

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
    new_val = min(current + 10, 500) if triggered == "sat-inc-btn" \
              else max(current - 10, 10)
    return new_val, str(new_val)


# ── SET — live re-propagation ─────────────────────────────────────────────────

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
    from datetime import timedelta as td

    # 1. Load saved TLE records
    db   = load_satellites_db()
    recs = db.get("satellites", [])[:min(n_sats, 500)]

    if not recs:
        msg = html.Span("No TLE data found — run main.py first.",
                        style={"color":"#ff4757","fontSize":"9px",
                               "fontFamily":"'Space Mono',monospace"})
        raise PreventUpdate

    # 2. Build EarthSatellite objects
    ts   = skyload.timescale()
    sats = []
    for r in recs:
        try:
            sats.append(EarthSatellite(r["tle"]["line1"], r["tle"]["line2"], r["name"]))
        except Exception:
            pass

    # 3. Generate time steps
    t0    = ts.now()
    times = [ts.utc(t0.utc_datetime() + td(minutes=i)) for i in range(DURATION)]

    # 4. Propagate
    positions_new = {}
    for sat in sats:
        sat_pos = []
        for t in times:
            p = sat.at(t).position.km
            sat_pos.append({
                "time":        t.utc_iso(),
                "position_km": {"x": float(p[0]), "y": float(p[1]), "z": float(p[2])},
            })
        positions_new[sat.name] = sat_pos

    # 5. Detect conjunctions (use threshold 500 km default)
    new_warnings = _detect_conjunctions(positions_new, threshold_km=500)

    # 6. Rebuild full figure with new satellite set
    from src.visualization.warnings   import load_warning_satellites
    from src.visualization.earth      import create_earth
    from src.visualization.satellites import build_satellite_trace
    from src.visualization.orbits     import build_orbit_traces
    import plotly.graph_objects as go

    warning_sats  = {w["satellite_a"] for w in new_warnings} | \
                    {w["satellite_b"] for w in new_warnings}
    critical_sats = {w["satellite_a"] for w in new_warnings if w["severity"] == "CRITICAL"} | \
                    {w["satellite_b"] for w in new_warnings if w["severity"] == "CRITICAL"}

    sat_names = list(positions_new.keys())
    xs = [positions_new[s][0]["position_km"]["x"] for s in sat_names]
    ys = [positions_new[s][0]["position_km"]["y"] for s in sat_names]
    zs = [positions_new[s][0]["position_km"]["z"] for s in sat_names]

    earth_traces    = create_earth()
    sat_trace       = build_satellite_trace(xs, ys, zs, sat_names,
                                            warning_sats, critical_sats)
    orbit_traces    = build_orbit_traces(positions_new, warning_sats, critical_sats)

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

    msg = html.Span(
        f"✓ Loaded {len(sats)} satellites  ·  {len(new_warnings)} conjunctions found",
        style={"color":"#00e5c0","fontSize":"9px","fontFamily":"'Space Mono',monospace"},
    )

    new_active_filter = {
        "warning_sats":  list(warning_sats),
        "critical_sats": list(critical_sats),
    }

    # ── Write new positions and warnings back to disk ──────────────────────────
    # This means update_orbit always reads from debug/positions.json consistently —
    # no Store, no branching, no memory bloat.
    retrieved_time = datetime.utcnow().isoformat()

    positions_output = {
        "metadata": {
            "simulation_start":  retrieved_time,
            "time_step_minutes": TIMESTEP,
            "duration_minutes":  DURATION,
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

    # Update module-level SIM_START so timeline labels stay correct
    global SIM_START
    SIM_START = retrieved_time

    return new_warnings, new_fig, msg, str(len(sats)), new_active_filter


# ── Filter conjunctions (reads from live-warnings-store) ─────────────────────

@app.callback(
    Output("conj-list",           "children"),
    Output("stat-critical",       "children"),
    Output("stat-warning",        "children"),
    Output("stat-caution",        "children"),
    Output("crit-badge",          "children"),
    Output("warn-badge",          "children"),
    Output("caut-badge",          "children"),
    Output("conj-nav-badge",      "children"),
    Output("warn-nav-badge",      "children"),
    Output("pc-slider-display",   "children"),
    Output("active-filter-store", "data"),
    Input("live-warnings-store",  "data"),
    Input("pc-threshold-slider",  "value"),
    Input("min-dist-input",       "value"),
    Input("max-dist-input",       "value"),
)
def filter_conjunctions(live_warnings, pc_idx, min_dist, max_dist):
    warnings_list = live_warnings if live_warnings is not None else ALL_WARNINGS

    min_pc = PC_LEVELS[pc_idx if pc_idx is not None else 0]
    min_d  = float(min_dist) if min_dist is not None else 0.0
    max_d  = float(max_dist) if max_dist is not None else 99999.0

    filtered = [
        w for w in warnings_list
        if min_d <= w["distance_km"] <= max_d
        and (w.get("proxy_pc") or 0) >= min_pc
    ]

    n_crit  = sum(1 for w in filtered if w.get("severity") == "CRITICAL")
    n_warn  = sum(1 for w in filtered if w.get("severity") == "WARNING")
    n_caut  = sum(1 for w in filtered if w.get("severity") == "CAUTION")
    n_total = len(filtered)

    active_warning_sats  = list({w["satellite_a"] for w in filtered} |
                                {w["satellite_b"] for w in filtered})
    active_critical_sats = list({w["satellite_a"] for w in filtered
                                  if w.get("severity") == "CRITICAL"} |
                                {w["satellite_b"] for w in filtered
                                  if w.get("severity") == "CRITICAL"})

    active_filter = {
        "warning_sats":  active_warning_sats,
        "critical_sats": active_critical_sats,
    }

    cards = [conj_card(w) for w in filtered[:10]]
    if not cards:
        cards = [html.P("No conjunctions match current filters.",
                        style={"color":"#5a7090","fontSize":"11px",
                               "fontFamily":"'Space Mono',monospace"})]

    pc_label = f"≥ {min_pc:.0e}" if min_pc > 0 else "all"

    return (
        cards,
        str(n_crit), str(n_warn), str(n_caut),
        f"▲ {n_crit} CRITICAL", f"{n_warn} WARN", f"{n_caut} CAUTION",
        str(n_total), str(n_total),
        pc_label,
        active_filter,
    )


# ── Recolor graph when filters change (independent of slider) ────────────────

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

    colors, sizes, symbols, outlines, hovers = _marker_arrays(
        sat_names, xs, ys, zs, warning_sats, critical_sats
    )

    patched = Patch()
    patched["data"][4]["marker"]["color"]         = colors
    patched["data"][4]["marker"]["size"]          = sizes
    patched["data"][4]["marker"]["symbol"]        = symbols
    patched["data"][4]["marker"]["line"]["color"] = outlines
    patched["data"][4]["text"]                    = hovers
    return patched


# ── Zoom in / out buttons ─────────────────────────────────────────────────────

@app.callback(
    Output("orbit-graph", "figure", allow_duplicate=True),
    Input("zoom-in-btn",  "n_clicks"),
    Input("zoom-out-btn", "n_clicks"),
    State("orbit-graph",  "relayoutData"),
    prevent_initial_call=True,
)
def zoom_globe(zoom_in, zoom_out, relayout):
    """
    Scale the camera eye vector toward or away from Earth.
    ZOOM_STEP < 1 → move closer (zoom in)
    ZOOM_STEP > 1 → move farther (zoom out)
    """
    ZOOM_IN_STEP  = 0.80   # 20% closer each click
    ZOOM_OUT_STEP = 1.25   # 25% farther each click

    triggered = ctx.triggered_id
    factor = ZOOM_IN_STEP if triggered == "zoom-in-btn" else ZOOM_OUT_STEP

    # Try to read current eye from relayoutData (set by user drag/scroll)
    eye = {"x": 1.6, "y": 1.4, "z": 0.9}   # default
    if relayout and "scene.camera.eye.x" in relayout:
        eye = {
            "x": relayout.get("scene.camera.eye.x", eye["x"]),
            "y": relayout.get("scene.camera.eye.y", eye["y"]),
            "z": relayout.get("scene.camera.eye.z", eye["z"]),
        }
    elif relayout and "scene.camera" in relayout:
        cam = relayout["scene.camera"]
        eye = cam.get("eye", eye)

    # Clamp so user can't zoom inside Earth or infinitely far out
    import math as _math
    r       = _math.sqrt(eye["x"]**2 + eye["y"]**2 + eye["z"]**2)
    new_r   = max(0.4, min(6.0, r * factor))
    scale   = new_r / r if r > 0 else 1.0

    new_eye = {"x": eye["x"] * scale,
               "y": eye["y"] * scale,
               "z": eye["z"] * scale}

    patched = Patch()
    patched["layout"]["scene"]["camera"]["eye"] = new_eye
    return patched


@app.callback(
    Output("utc-clock", "children"),
    Input("clock-interval", "n_intervals"),
)
def tick_clock(_):
    return datetime.utcnow().strftime("%Y-%m-%d · %H:%M:%S")


# ── TLE Database modal ────────────────────────────────────────────────────────

@app.callback(
    Output("tle-modal",         "className"),
    Output("tle-modal-content", "children"),
    Output("tle-modal-meta",    "children"),
    Output("tab-parsed",        "className"),
    Output("tab-raw",           "className"),
    Input("nav-tle-db",         "n_clicks"),
    Input("close-tle-modal",    "n_clicks"),
    Input("tab-parsed",         "n_clicks"),
    Input("tab-raw",            "n_clicks"),
    prevent_initial_call=True,
)
def toggle_tle_modal(_, __, ___, ____):
    triggered = ctx.triggered_id

    ACTIVE  = "modal-tab modal-tab-active"
    PASSIVE = "modal-tab"

    if triggered == "close-tle-modal":
        # Reset to default state (parsed active) on close
        return "modal-overlay modal-hidden", [], "", ACTIVE, PASSIVE

    if triggered in ("nav-tle-db", "tab-parsed"):
        db      = load_satellites_db()
        sats    = db.get("satellites", [])
        meta    = db.get("metadata", {})
        subtitle = (f"{len(sats)} satellites · "
                    f"retrieved {meta.get('retrieved_at','?')[:16]} · "
                    f"source {meta.get('source','CelesTrak')}")
        rows = [tle_row(s) for s in sats[:100]]
        if len(sats) > 100:
            rows.append(html.Div(
                f"… {len(sats)-100} more satellites not shown",
                style={"color":"#5a7090","padding":"10px",
                       "fontFamily":"'Space Mono',monospace","fontSize":"10px"}
            ))
        return "modal-overlay modal-visible", rows, subtitle, ACTIVE, PASSIVE

    if triggered == "tab-raw":
        try:
            with open("debug/raw_tle.txt") as f:
                raw = f.read()
            lines   = raw.split("\n")
            preview = "\n".join(lines[:150])
            if len(lines) > 150:
                preview += f"\n\n… ({len(lines)-150} more lines not shown)"
            content = html.Pre(preview, className="tle-raw-pre")
        except Exception as e:
            content = html.P(f"Could not load raw_tle.txt: {e}",
                             style={"color":"#ff4757"})
        return "modal-overlay modal-visible", content, "raw CelesTrak TLE data", PASSIVE, ACTIVE

    raise PreventUpdate


# ── Conjunction Events modal ──────────────────────────────────────────────────

@app.callback(
    Output("conj-modal",          "className"),
    Output("conj-table-content",  "children"),
    Output("conj-modal-subtitle", "children"),
    Input("nav-conj-events",      "n_clicks"),
    Input("close-conj-modal",     "n_clicks"),
    State("live-warnings-store",  "data"),
    prevent_initial_call=True,
)
def toggle_conj_modal(_, __, live_warnings):
    triggered = ctx.triggered_id
    if triggered == "close-conj-modal":
        return "modal-overlay modal-hidden", [], ""

    warnings_list = live_warnings if live_warnings else ALL_WARNINGS
    subtitle = f"{len(warnings_list)} total events · sorted by miss distance"

    rows = [conj_table_row(w, i) for i, w in enumerate(warnings_list)]
    if not rows:
        rows = [html.P("No conjunction events detected.",
                       style={"color":"#5a7090","fontFamily":"'Space Mono',monospace"})]

    return "modal-overlay modal-visible", rows, subtitle


# ── Risk Dashboard modal ──────────────────────────────────────────────────────

@app.callback(
    Output("risk-modal",          "className"),
    Output("risk-modal-content",  "children"),
    Output("risk-modal-subtitle", "children"),
    Input("nav-risk-dashboard",   "n_clicks"),
    Input("close-risk-modal",     "n_clicks"),
    State("live-warnings-store",  "data"),
    prevent_initial_call=True,
)
def toggle_risk_modal(_, __, live_warnings):
    triggered = ctx.triggered_id
    if triggered == "close-risk-modal":
        return "modal-overlay modal-hidden", [], ""

    warnings_list = live_warnings if live_warnings else ALL_WARNINGS

    n_crit   = sum(1 for w in warnings_list if w.get("severity") == "CRITICAL")
    n_warn   = sum(1 for w in warnings_list if w.get("severity") == "WARNING")
    n_caut   = sum(1 for w in warnings_list if w.get("severity") == "CAUTION")
    n_total  = len(warnings_list)

    subtitle = f"{n_total} conjunction events analysed"

    def risk_bar(label, count, color, pct):
        return html.Div(className="risk-bar-row", children=[
            html.Div(className="risk-bar-label", children=[
                html.Span(label, style={"color": color, "fontFamily":"'Space Mono',monospace",
                                        "fontSize":"11px", "fontWeight":"700"}),
                html.Span(str(count), style={"color":"#e6f1ff",
                                              "fontFamily":"'Space Mono',monospace",
                                              "fontSize":"18px","fontWeight":"700",
                                              "marginLeft":"auto"}),
            ]),
            html.Div(className="risk-bar-track", children=[
                html.Div(className="risk-bar-fill",
                         style={"width": f"{pct}%", "background": color,
                                "boxShadow": f"0 0 8px {color}55"}),
            ]),
        ])

    max_n = max(n_crit, n_warn, n_caut, 1)

    # Top 5 highest-risk pairs
    top5 = warnings_list[:5]
    top5_rows = []
    for i, w in enumerate(top5):
        color  = SEVERITY_COLOR.get(w.get("severity","CAUTION"), "#48a5ff")
        pc_str = fmt_pc(w.get("proxy_pc"))
        top5_rows.append(html.Div(className="risk-top-row", children=[
            html.Span(f"{i+1}.", style={"color":"#5a7090","fontFamily":"'Space Mono',monospace",
                                         "fontSize":"10px","width":"18px"}),
            html.Span(f"{w['satellite_a']} × {w['satellite_b']}",
                      style={"fontFamily":"'Space Mono',monospace","fontSize":"11px",
                             "color":"#ddeeff","flex":"1"}),
            html.Span(f"{w['distance_km']:.1f} km",
                      style={"color":"#48a5ff","fontFamily":"'Space Mono',monospace",
                             "fontSize":"10px","marginRight":"8px"}),
            html.Span(f"Pc {pc_str}",
                      style={"color": color,"fontFamily":"'Space Mono',monospace",
                             "fontSize":"10px","fontWeight":"700"}),
        ]))

    content = html.Div([
        html.Div("SEVERITY BREAKDOWN", className="info-heading"),
        risk_bar("CRITICAL", n_crit, "#ff4757", int(n_crit / max_n * 100)),
        risk_bar("WARNING",  n_warn, "#ff9f1c", int(n_warn / max_n * 100)),
        risk_bar("CAUTION",  n_caut, "#48a5ff", int(n_caut / max_n * 100)),

        html.Hr(className="sidebar-hr", style={"margin":"18px 0"}),

        html.Div("TOP 5 HIGHEST-RISK PAIRS", className="info-heading"),
        html.Div(top5_rows if top5_rows else
                 html.P("No events.", style={"color":"#5a7090",
                                             "fontFamily":"'Space Mono',monospace"})),
    ])

    return "modal-overlay modal-visible", content, subtitle


# ── Info modal ────────────────────────────────────────────────────────────────

@app.callback(
    Output("info-modal",     "className"),
    Input("info-btn",        "n_clicks"),
    Input("close-info-modal","n_clicks"),
    prevent_initial_call=True,
)
def toggle_info_modal(_, __):
    if ctx.triggered_id == "close-info-modal":
        return "modal-overlay modal-hidden"
    return "modal-overlay modal-visible"


server = app.server

if __name__ == "__main__":
    app.run(debug=True)