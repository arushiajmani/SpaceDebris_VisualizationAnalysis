"""
src/dashboard/components.py
Pure functions that build Dash HTML components.
No callbacks, no side effects — all inputs explicit, all outputs html.Div / html.Span.
"""

import math
from dash import html

from .config import SEVERITY_COLOR, REGIME_COLOR, EARTH_RADIUS_KM


# ── Formatting helpers ────────────────────────────────────────────────────────

def fmt_pc(pc_val: float) -> str:
    """Format a Pc float for display — always returns a non-empty string."""
    if pc_val is None:
        return "—"
    if pc_val >= 0.01:
        return f"{pc_val:.3f}"
    return f"{pc_val:.2e}"


def _regime_from_alt(alt_km: float) -> str:
    if alt_km < 2_000:   return "LEO"
    if alt_km < 10_000:  return "MEO"
    if alt_km < 37_000:  return "GEO"
    return "HEO"


# ── Satellite marker arrays ───────────────────────────────────────────────────

def marker_arrays(sat_names, xs, ys, zs, warning_sats: set, critical_sats: set):
    """
    Return (colors, sizes, symbols, outlines, hover_texts) lists — one entry
    per satellite — reflecting the current filter state.

    Used by both update_orbit (every slider tick) and recolor_graph (filter change).
    """
    colors, sizes, symbols, outlines, hovers = [], [], [], [], []

    for name, x, y, z in zip(sat_names, xs, ys, zs):
        alt    = math.sqrt(x**2 + y**2 + z**2) - EARTH_RADIUS_KM
        regime = _regime_from_alt(alt)

        if name in critical_sats:
            c, sz, sym = "#ff4757", 7, "diamond"
            outlines.append("rgba(255,255,255,0.3)")
            status = "🔴 CRITICAL"
        elif name in warning_sats:
            c, sz, sym = "#ff9f1c", 5, "diamond"
            outlines.append("rgba(255,255,255,0.2)")
            status = "🟠 WARNING"
        else:
            c   = REGIME_COLOR[regime]
            sz  = 3
            sym = "circle"
            outlines.append("rgba(0,0,0,0)")
            status = "🟢 NOMINAL"

        colors.append(c); sizes.append(sz); symbols.append(sym)
        hovers.append(
            f"<b>{name}</b><br>"
            f"Alt: {alt:,.0f} km  [{regime}]<br>"
            f"Status: {status}<br>"
            f"<span style='color:#5a7090'>x:{x:.0f}  y:{y:.0f}  z:{z:.0f}</span>"
        )

    return colors, sizes, symbols, outlines, hovers


# ── Conjunction alert card ────────────────────────────────────────────────────

def conj_card(w: dict) -> html.Div:
    """Render a single conjunction event as a styled card for the right panel."""
    color    = SEVERITY_COLOR.get(w.get("severity", "CAUTION"), "#48a5ff")
    severity = w.get("severity", "CAUTION")
    pc_val   = w.get("proxy_pc")
    pc_str   = fmt_pc(pc_val)
    t_str    = w.get("time", "")[-8:-3] if w.get("time") else "—"

    # Log-scale bar: [1e-15, 1] → [2%, 96%]
    if pc_val and pc_val > 0:
        log_pc  = math.log10(max(pc_val, 1e-15))
        bar_pct = int(2 + (log_pc + 15) / 15 * 94)
        bar_pct = max(2, min(96, bar_pct))
    else:
        bar_pct = 2

    return html.Div(className="conj-card", style={"borderLeft": f"3px solid {color}"}, children=[
        html.Div(className="conj-card-header", children=[
            html.Span(f"● {severity}",
                      style={"color": color, "fontSize": "10px", "letterSpacing": "1px"}),
            html.Span(t_str, style={"color": "#5a7090", "fontSize": "10px"}),
        ]),
        html.Div(f"{w['satellite_a']} × {w['satellite_b']}", className="conj-pair"),
        html.Div(className="conj-meta", children=[
            html.Span(f"Δ {w['distance_km']:.2f} km",
                      style={"color": "#48a5ff", "fontFamily": "'Space Mono',monospace",
                             "fontSize": "11px"}),
            html.Span(f"Pc {pc_str}",
                      style={"color": color, "fontFamily": "'Space Mono',monospace",
                             "fontSize": "11px", "marginLeft": "8px", "fontWeight": "700"}),
        ]),
        html.Div(className="pc-bar-track", children=[
            html.Div(className="pc-bar-fill",
                     style={"width": f"{bar_pct}%", "background": color}),
        ]),
    ])


# ── Conjunction table row (for the full modal) ────────────────────────────────

def conj_table_row(w: dict, idx: int) -> html.Div:
    color  = SEVERITY_COLOR.get(w.get("severity", "CAUTION"), "#48a5ff")
    t_str  = w.get("time", "")[:16] if w.get("time") else "—"
    return html.Div(className="conj-table-row", children=[
        html.Span(str(idx + 1),              className="ct-idx"),
        html.Span(w.get("severity", "—"),    className="ct-sev", style={"color": color}),
        html.Span(f"{w['satellite_a']} × {w['satellite_b']}", className="ct-pair"),
        html.Span(f"{w['distance_km']:.2f} km", className="ct-dist"),
        html.Span(fmt_pc(w.get("proxy_pc")), className="ct-pc",  style={"color": color}),
        html.Span(t_str,                     className="ct-time"),
    ])


# ── TLE record row (for the database modal) ───────────────────────────────────

def tle_row(sat: dict) -> html.Div:
    tle = sat.get("tle", {})
    return html.Div(className="tle-row", children=[
        html.Div(sat.get("name", "?"), className="tle-name"),
        html.Div(tle.get("line1", ""), className="tle-line"),
        html.Div(tle.get("line2", ""), className="tle-line"),
    ])


# ── Risk dashboard content ────────────────────────────────────────────────────

def risk_dashboard_content(warnings_list: list) -> html.Div:
    """Build the full Risk Dashboard modal body from a warnings list."""
    n_crit  = sum(1 for w in warnings_list if w.get("severity") == "CRITICAL")
    n_warn  = sum(1 for w in warnings_list if w.get("severity") == "WARNING")
    n_caut  = sum(1 for w in warnings_list if w.get("severity") == "CAUTION")
    max_n   = max(n_crit, n_warn, n_caut, 1)

    def bar_row(label, count, color):
        pct = int(count / max_n * 100)
        return html.Div(className="risk-bar-row", children=[
            html.Div(className="risk-bar-label", children=[
                html.Span(label, style={"color": color,
                                        "fontFamily": "'Space Mono',monospace",
                                        "fontSize": "11px", "fontWeight": "700"}),
                html.Span(str(count), style={"color": "#e6f1ff",
                                              "fontFamily": "'Space Mono',monospace",
                                              "fontSize": "18px", "fontWeight": "700",
                                              "marginLeft": "auto"}),
            ]),
            html.Div(className="risk-bar-track", children=[
                html.Div(className="risk-bar-fill",
                         style={"width": f"{pct}%", "background": color,
                                "boxShadow": f"0 0 8px {color}55"}),
            ]),
        ])

    top5 = warnings_list[:5]
    top5_rows = [
        html.Div(className="risk-top-row", children=[
            html.Span(f"{i+1}.",
                      style={"color":"#5a7090","fontFamily":"'Space Mono',monospace",
                             "fontSize":"10px","width":"18px"}),
            html.Span(f"{w['satellite_a']} × {w['satellite_b']}",
                      style={"fontFamily":"'Space Mono',monospace","fontSize":"11px",
                             "color":"#ddeeff","flex":"1"}),
            html.Span(f"{w['distance_km']:.1f} km",
                      style={"color":"#48a5ff","fontFamily":"'Space Mono',monospace",
                             "fontSize":"10px","marginRight":"8px"}),
            html.Span(f"Pc {fmt_pc(w.get('proxy_pc'))}",
                      style={"color": SEVERITY_COLOR.get(w.get("severity","CAUTION"),"#48a5ff"),
                             "fontFamily":"'Space Mono',monospace",
                             "fontSize":"10px","fontWeight":"700"}),
        ])
        for i, w in enumerate(top5)
    ]

    return html.Div([
        html.Div("SEVERITY BREAKDOWN", className="info-heading"),
        bar_row("CRITICAL", n_crit, "#ff4757"),
        bar_row("WARNING",  n_warn, "#ff9f1c"),
        bar_row("CAUTION",  n_caut, "#48a5ff"),
        html.Hr(className="sidebar-hr", style={"margin": "18px 0"}),
        html.Div("TOP 5 HIGHEST-RISK PAIRS", className="info-heading"),
        html.Div(top5_rows if top5_rows else
                 html.P("No events.", style={"color":"#5a7090",
                                              "fontFamily":"'Space Mono',monospace"})),
    ])