"""
src/dashboard/callbacks/filters.py
Conjunction filter: responds to Pc slider + distance inputs.
Updates the alerts panel, all badges, and active-filter-store (which triggers globe recolor).
"""

from dash import Input, Output, html

from ..config import PC_LEVELS, SEVERITY_COLOR
from ..components import conj_card


def register(app, store):

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
        warnings_list = live_warnings if live_warnings is not None else store.all_warnings

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

        active_filter = {
            "warning_sats":  list({w["satellite_a"] for w in filtered} |
                                  {w["satellite_b"] for w in filtered}),
            "critical_sats": list({w["satellite_a"] for w in filtered
                                    if w.get("severity") == "CRITICAL"} |
                                  {w["satellite_b"] for w in filtered
                                    if w.get("severity") == "CRITICAL"}),
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