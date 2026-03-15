"""
src/dashboard/layout.py
Builds and returns the complete Dash layout tree.
Call build_layout(store) once; pass the DataStore from data_store.bootstrap().
"""

from dash import dcc, html

from .config import PC_MARKS, DURATION_MINUTES, TIMESTEP_MINUTES, MAX_SATELLITES
from .components import conj_card
from .data_store import DataStore


def build_layout(store: DataStore) -> html.Div:
    """Return the root html.Div that becomes app.layout."""

    return html.Div(id="root", children=[

        # ── Stores ────────────────────────────────────────────────────────────
        dcc.Store(id="playing-store",       data=False),
        dcc.Store(id="pending-sat-count",   data=store.sat_count),
        dcc.Store(id="live-warnings-store", data=store.all_warnings),
        dcc.Store(id="active-filter-store", data={
            "warning_sats":  [w["satellite_a"] for w in store.all_warnings] +
                             [w["satellite_b"] for w in store.all_warnings],
            "critical_sats": [w["satellite_a"] for w in store.all_warnings
                              if w.get("severity") == "CRITICAL"] +
                             [w["satellite_b"] for w in store.all_warnings
                              if w.get("severity") == "CRITICAL"],
        }),

        # ── Timers ────────────────────────────────────────────────────────────
        dcc.Interval(id="clock-interval",     interval=5_000, n_intervals=0),
        dcc.Interval(id="animation-interval", interval=600,   n_intervals=0, disabled=True),
        dcc.Interval(id="log-interval",        interval=2_000, n_intervals=0, disabled=True),

        _topbar(store),
        html.Div(id="body", children=[
            _sidebar(store),
            _center(store),
            _right_panel(store),
        ]),
        _tle_modal(),
        _conj_modal(),
        _risk_modal(),
        _info_modal(store),
        _log_modal(),
    ])


# ── Top bar ───────────────────────────────────────────────────────────────────

def _topbar(store: DataStore) -> html.Header:
    return html.Header(id="topbar", children=[

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
        html.Button("⬡", id="log-btn",  n_clicks=0, className="info-btn log-btn",
                    title="Pipeline logs"),

        html.Div(id="alert-badge-div",
                 style={"marginLeft":"auto","display":"flex","gap":"6px",
                        "alignItems":"center",
                        "border":"1px solid rgba(255,71,87,0.35)",
                        "borderRadius":"20px","padding":"5px 14px",
                        "background":"rgba(255,71,87,0.06)"}, children=[
            html.Span(id="crit-badge",
                      style={"color":"#ff4757","fontFamily":"'Space Mono',monospace",
                             "fontSize":"11px","letterSpacing":"1px"},
                      children=f"▲ {store.init_critical} CRITICAL"),
            html.Span("·", style={"color":"#2a3a50"}),
            html.Span(id="warn-badge",
                      style={"color":"#ff9f1c","fontFamily":"'Space Mono',monospace",
                             "fontSize":"11px"},
                      children=f"{store.init_warning} WARN"),
            html.Span("·", style={"color":"#2a3a50"}),
            html.Span(id="caut-badge",
                      style={"color":"#48a5ff","fontFamily":"'Space Mono',monospace",
                             "fontSize":"11px"},
                      children=f"{store.init_caution} CAUTION"),
        ]),
    ])


# ── Left sidebar ──────────────────────────────────────────────────────────────

def _sidebar(store: DataStore) -> html.Nav:

    pc_ticks = list(PC_MARKS.values())

    return html.Nav(id="sidebar", children=[

        html.Div("WORKSPACE", className="section-label"),
        html.Div([
            html.Div([html.Span("◎ "), html.Span("Orbital View")],
                     className="nav-item nav-active"),
            html.Div(id="nav-tle-db", n_clicks=0,
                     className="nav-item nav-item-clickable",
                     children=[html.Span("≡ "), html.Span("TLE Database"),
                                html.Span("→", style={"marginLeft":"auto",
                                                       "color":"#5a7090","fontSize":"10px"})]),
            html.Div(id="nav-conj-events", n_clicks=0,
                     className="nav-item nav-item-clickable",
                     children=[html.Span("✦ "), html.Span("Conjunction Events"),
                                html.Span(id="conj-nav-badge",
                                          className="nav-badge badge-red",
                                          children=str(store.init_total))]),
            html.Div(id="nav-risk-dashboard", n_clicks=0,
                     className="nav-item nav-item-clickable",
                     children=[html.Span("⚠ "), html.Span("Risk Dashboard"),
                                html.Span(id="warn-nav-badge",
                                          className="nav-badge badge-amber",
                                          children=str(store.init_total))]),
        ]),

        html.Hr(className="sidebar-hr"),

        # Tracked objects counter
        html.Div("TRACKED OBJECTS", className="section-label"),
        html.Div(className="sat-counter-row", children=[
            html.Button("−", id="sat-dec-btn", n_clicks=0, className="counter-btn"),
            html.Div(id="sat-count-display",   className="counter-display",
                     children=str(store.sat_count)),
            html.Button("+", id="sat-inc-btn", n_clicks=0, className="counter-btn"),
            html.Button("SET", id="sat-apply-btn", n_clicks=0, className="apply-btn"),
        ]),
        html.Div(id="sat-count-status", className="input-status"),
        html.Div(className="sat-meta-note", children=[
            html.Span(f"max {MAX_SATELLITES}  ·  step 10", className="sat-meta-line"),
            html.Span(id="tle-freshness-note", className="sat-meta-line sat-meta-fresh",
                      children=f"TLE {store.sim_start[:10]}  {store.sim_start[11:16]} UTC  ·  ↻ 24h"),
        ]),

        html.Hr(className="sidebar-hr"),

        # TLE refresh
        html.Div("TLE DATA", className="section-label"),
        html.Button("⟳  REFRESH TLE", id="tle-refresh-btn", n_clicks=0,
                    className="refresh-btn"),
        html.Div(id="refresh-status", className="refresh-status"),

        html.Hr(className="sidebar-hr"),

        # Pc threshold
        html.Div("Pc THRESHOLD", className="section-label"),
        html.Div(className="pc-display-row", children=[
            html.Span("Min Pc", className="slider-label"),
            html.Span(id="pc-slider-display", className="slider-value pc-value-pill",
                      children="any"),
        ]),
        dcc.Slider(id="pc-threshold-slider", min=0, max=7, step=1, value=0,
                   marks=None, className="ow-slider ow-slider-clean",
                   tooltip={"always_visible": False}),
        html.Div(className="pc-tick-row", children=[
            html.Span(lbl, className="pc-tick") for lbl in pc_ticks
        ]),

        html.Hr(className="sidebar-hr"),

        # Distance filter
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
        html.Div(className="severity-ref", children=[
            html.Div(className="sev-ref-item", children=[
                html.Span("●", style={"color":"#ff4757","fontSize":"10px"}),
                html.Span("CRIT  < 5 km",   className="sev-ref-lbl"),
            ]),
            html.Div(className="sev-ref-item", children=[
                html.Span("●", style={"color":"#ff9f1c","fontSize":"10px"}),
                html.Span("WARN  < 25 km",  className="sev-ref-lbl"),
            ]),
            html.Div(className="sev-ref-item", children=[
                html.Span("●", style={"color":"#48a5ff","fontSize":"10px"}),
                html.Span("CAUT  < 500 km", className="sev-ref-lbl"),
            ]),
        ]),
    ])


# ── Center (globe + timeline) ─────────────────────────────────────────────────

def _center(store: DataStore) -> html.Main:
    from src.visualization.orbit_visualizer import visualize
    fig_initial = visualize("debug/positions.json")

    marks = {
        i: {"label": f"{i}m",
            "style": {"color":"#6a85a8","fontSize":"9px",
                      "fontFamily":"'Space Mono',monospace"}}
        for i in range(0, store.duration, 15)
    }

    return html.Main(id="center", children=[

        html.Div(style={"position":"relative","flex":"1","minHeight":"0"}, children=[

            dcc.Graph(
                id="orbit-graph",
                figure=fig_initial,
                config={"displayModeBar": False, "scrollZoom": True,
                        "modeBarButtonsToRemove": ["all"]},
                style={"height":"100%","width":"100%"},
            ),

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
            dcc.Slider(id="time-slider", min=0, max=store.duration - 1,
                       step=1, value=0, marks=marks,
                       className="tl-scrubber",
                       updatemode="mouseup"),
            html.Div(id="tl-time-current", className="tl-label tl-label-current",
                     children="T+00:00"),
        ]),
    ])


# ── Right panel ───────────────────────────────────────────────────────────────

def _right_panel(store: DataStore) -> html.Aside:

    initial_cards = ([conj_card(w) for w in store.all_warnings[:10]]
                     if store.all_warnings else
                     [html.P("No conjunctions detected.",
                             style={"color":"#5a7090","fontSize":"11px",
                                    "fontFamily":"'Space Mono',monospace"})])

    return html.Aside(id="right-panel", children=[

        html.Div(id="stats-row", children=[
            html.Div([html.Span(id="stat-tracked",  className="stat-num",
                               children=str(store.sat_count)),
                      html.Span(" tracked", className="stat-label")]),
            html.Div([html.Span(id="stat-critical", className="stat-num stat-red",
                               children=str(store.init_critical)),
                      html.Span(" critical", className="stat-label")]),
            html.Div([html.Span(id="stat-warning",  className="stat-num stat-amber",
                               children=str(store.init_warning)),
                      html.Span(" warnings", className="stat-label")]),
            html.Div([html.Span(id="stat-caution",  className="stat-num stat-blue",
                               children=str(store.init_caution)),
                      html.Span(" caution", className="stat-label")]),
        ]),

        html.Div(id="view-controls", children=[
            html.Div("3D VIEW", className="view-mode-badge"),
        ]),

        html.Hr(className="sidebar-hr"),
        html.Div("CONJUNCTION ALERTS", className="section-label"),
        html.Div(id="conj-list", children=initial_cards),
    ])


# ── Modals ────────────────────────────────────────────────────────────────────

def _tle_modal() -> html.Div:
    return html.Div(id="tle-modal", className="modal-overlay modal-hidden", children=[
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
    ])


def _conj_modal() -> html.Div:
    return html.Div(id="conj-modal", className="modal-overlay modal-hidden", children=[
        html.Div(className="modal-box modal-box-wide", children=[
            html.Div(className="modal-header", children=[
                html.Span("CONJUNCTION EVENTS", className="modal-title"),
                html.Span(id="conj-modal-subtitle", className="modal-subtitle"),
                html.Button("✕", id="close-conj-modal", n_clicks=0, className="modal-close"),
            ]),
            html.Div(className="conj-table-header", children=[
                html.Span("#",         className="ct-idx"),
                html.Span("SEVERITY",  className="ct-sev"),
                html.Span("PAIR",      className="ct-pair"),
                html.Span("MISS DIST", className="ct-dist"),
                html.Span("Pc",        className="ct-pc"),
                html.Span("TCA (UTC)", className="ct-time"),
            ]),
            html.Div(id="conj-table-content", className="modal-content"),
        ]),
    ])


def _risk_modal() -> html.Div:
    return html.Div(id="risk-modal", className="modal-overlay modal-hidden", children=[
        html.Div(className="modal-box modal-box-risk", children=[
            html.Div(className="modal-header", children=[
                html.Span("RISK DASHBOARD", className="modal-title"),
                html.Span(id="risk-modal-subtitle", className="modal-subtitle"),
                html.Button("✕", id="close-risk-modal", n_clicks=0, className="modal-close"),
            ]),
            html.Div(id="risk-modal-content", className="modal-content risk-content"),
        ]),
    ])


def _log_modal() -> html.Div:
    return html.Div(id="log-modal", className="modal-overlay modal-hidden", children=[
        html.Div(className="modal-box modal-box-log", children=[
            html.Div(className="modal-header", children=[
                html.Span("PIPELINE LOGS", className="modal-title"),
                html.Span(id="log-modal-subtitle", className="modal-subtitle",
                          children="auto-refreshes every 2s"),
                html.Button("🗑", id="clear-log-btn", n_clicks=0,
                            className="modal-close",
                            style={"marginLeft":"0","border":"1px solid rgba(72,165,255,0.3)",
                                   "color":"#48a5ff","background":"rgba(72,165,255,0.08)"},
                            title="Clear logs"),
                html.Button("✕", id="close-log-modal", n_clicks=0, className="modal-close"),
            ]),
            html.Div(id="log-content", className="modal-content log-content"),
        ]),
    ])


def _info_modal(store: DataStore) -> html.Div:
    return html.Div(id="info-modal", className="modal-overlay modal-hidden", children=[
        html.Div(className="modal-box modal-box-info", children=[
            html.Div(className="modal-header", children=[
                html.Span("ORBITWATCH — GUIDE", className="modal-title"),
                html.Button("✕", id="close-info-modal", n_clicks=0, className="modal-close"),
            ]),
            html.Div(className="modal-content info-content", children=[
                _legend_section(),
                html.Hr(className="sidebar-hr"),
                _pc_section(store),
                html.Hr(className="sidebar-hr"),
                _controls_section(),
                html.Hr(className="sidebar-hr"),
                _data_sources_section(store),
            ]),
        ]),
    ])


# ── Info modal sub-sections ───────────────────────────────────────────────────

def _legend_section() -> html.Div:
    def row(dot_style, label, desc, diamond=False):
        dot_cls = "legend-dot legend-diamond" if diamond else "legend-dot"
        return html.Div(className="legend-row", children=[
            html.Span(className=dot_cls, style=dot_style),
            html.Div([
                html.Span(label, className="legend-label"),
                html.Span(desc,  className="legend-desc"),
            ]),
        ])

    return html.Div(className="info-section", children=[
        html.Div("SATELLITE COLOUR CODING", className="info-heading"),
        html.Div(className="legend-grid", children=[
            html.Div("CONJUNCTION RISK STATUS (overrides regime colour)",
                     className="legend-sublabel"),
            row({"background":"#ff4757"}, "CRITICAL  —  red diamond",
                "Closest approach < 5 km. Immediate collision risk.", diamond=True),
            row({"background":"#ff9f1c"}, "WARNING  —  amber diamond",
                "Closest approach 5–25 km. Monitor closely.", diamond=True),
            row({"background":"#48a5ff"}, "CAUTION  —  blue diamond",
                "Closest approach 25–500 km. Low immediate risk.", diamond=True),
            html.Div("ORBITAL REGIME (when no conjunction risk)",
                     className="legend-sublabel", style={"marginTop":"10px"}),
            row({"background":"#00e5c0"}, "LEO  —  teal circle",
                "Altitude < 2,000 km. 3-segment fade trail."),
            row({"background":"#48a5ff"}, "MEO  —  blue circle",
                "Altitude 2,000–35,000 km. Single opacity trail."),
            row({"background":"#a78bfa"}, "GEO  —  purple circle",
                "Altitude ≈ 35,786 km. Geostationary ring."),
            row({"background":"#6e7bff"}, "HEO  —  indigo circle",
                "Altitude > 37,000 km. High / Elliptical orbit."),
        ]),
    ])


def _pc_section(store: DataStore) -> html.Div:
    def ctrl(key, desc):
        return html.Div(className="ctrl-row", children=[
            html.Span(key,  className="ctrl-key"),
            html.Span(desc, className="ctrl-desc"),
        ])

    return html.Div(className="info-section", children=[
        html.Div("PROBABILITY OF COLLISION (Pc)", className="info-heading"),
        html.Div(className="controls-grid", children=[
            ctrl("What is Pc?",
                 "Dimensionless 0→1. Chan approximation: Pc = exp(−½·(d/σ)²) "
                 "where σ = threshold/3 ≈ 167 km."),
            ctrl("Pc bar",
                 "Log-scaled bar under each alert card. Full = Pc≈1, short = low Pc."),
            ctrl("Pc threshold slider",
                 "8 ticks: any → 1e-2 → 0.1 → 0.3 → 0.5 → 0.7 → 0.9 → 1.0. "
                 "Hides alerts below threshold and recolors the globe."),
            ctrl("Distance filter",
                 "MIN/MAX miss-distance in km. Severity labels are fixed "
                 "(CRIT<5, WARN<25, CAUT<500) and do not change with this filter."),
        ]),
    ])


def _controls_section() -> html.Div:
    def ctrl(key, desc):
        return html.Div(className="ctrl-row", children=[
            html.Span(key,  className="ctrl-key"),
            html.Span(desc, className="ctrl-desc"),
        ])
    return html.Div(className="info-section", children=[
        html.Div("CONTROLS", className="info-heading"),
        html.Div(className="controls-grid", children=[
            ctrl("▶ / ⏸",            "Play or pause the 90-minute simulation timeline."),
            ctrl("Timeline scrubber", "Drag to any minute. Animation pauses automatically."),
            ctrl("＋ / － buttons",   "Zoom in or out on the globe."),
            ctrl("Scroll wheel",      "Zoom in / out on the 3D globe."),
            ctrl("Left-drag globe",   "Rotate the 3D view freely."),
        ]),
    ])


def _data_sources_section(store: DataStore) -> html.Div:
    def ctrl(key, desc):
        return html.Div(className="ctrl-row", children=[
            html.Span(key,  className="ctrl-key"),
            html.Span(desc, className="ctrl-desc"),
        ])
    return html.Div(className="info-section", children=[
        html.Div("DATA SOURCES", className="info-heading"),
        html.Div(className="controls-grid", children=[
            ctrl("TLE source",    "CelesTrak active catalog. Fetched once at pipeline startup."),
            ctrl("Propagator",    "SGP4 via Skyfield — industry-standard two-body model."),
            ctrl("Sim window",    f"{store.duration} min at {store.timestep}-min timesteps. All times UTC."),
            ctrl("Max satellites",
                 f"{MAX_SATELLITES}. Use − / + then SET. Re-runs propagation + conjunction detection live."),
        ]),
    ])