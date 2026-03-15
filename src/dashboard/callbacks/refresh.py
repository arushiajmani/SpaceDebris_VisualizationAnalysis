"""
src/dashboard/callbacks/refresh.py
Manual TLE refresh button + live log panel callbacks.
"""

from datetime import datetime

from dash import Input, Output, State, ctx, html
from dash.exceptions import PreventUpdate

from ..tle_refresher import run_pipeline, ui_log_handler
from ..data_store    import load_warnings, recompute_pc


# ── Log level → CSS class ─────────────────────────────────────────────────────

_LEVEL_CLASS = {
    "INFO":    "log-info",
    "WARNING": "log-warn",
    "ERROR":   "log-error",
}


def _render_log_rows(records: list) -> list:
    if not records:
        return [html.Div("No logs yet — waiting for pipeline run.",
                         className="log-empty")]
    rows = []
    for r in reversed(records):   # newest first
        cls = _LEVEL_CLASS.get(r["level"], "log-info")
        rows.append(html.Div(className=f"log-row {cls}", children=[
            html.Span(r["time"],    className="log-time"),
            html.Span(r["message"], className="log-msg"),
        ]))
    return rows


def register(app, store):

    # ── Manual refresh button ─────────────────────────────────────────────────

    @app.callback(
        Output("refresh-status",       "children"),
        Output("tle-freshness-note",   "children"),
        Output("live-warnings-store",  "data",     allow_duplicate=True),
        Output("stat-tracked",         "children", allow_duplicate=True),
        Input("tle-refresh-btn",       "n_clicks"),
        prevent_initial_call=True,
    )
    def manual_refresh(_):
        result = run_pipeline(
            n_sats       = store.sat_count,
            threshold_km = 500,
        )

        # Reload warnings from disk after pipeline writes them
        warn_data    = load_warnings()
        new_warnings = recompute_pc(warn_data.get("warnings", []))

        status_color = "#00e5c0" if result.success else "#ff4757"
        status = html.Span(
            result.summary,
            style={"color": status_color, "fontSize": "9px",
                   "fontFamily": "'Space Mono',monospace"},
        )

        freshness = f"TLE {result.retrieved_at[:10]}  {result.retrieved_at[11:16]} UTC  ·  ↻ 24h"
        tracked   = str(result.sat_count) if result.success else str(store.sat_count)

        return status, freshness, new_warnings, tracked

    # ── Log panel — open / close / clear ─────────────────────────────────────

    @app.callback(
        Output("log-modal",    "className"),
        Output("log-interval", "disabled"),
        Input("log-btn",         "n_clicks"),
        Input("close-log-modal", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_log_modal(_, __):
        if ctx.triggered_id == "close-log-modal":
            return "modal-overlay modal-hidden", True   # disable interval on close
        return "modal-overlay modal-visible", False      # enable interval on open

    @app.callback(
        Output("log-content",       "children"),
        Output("log-modal-subtitle","children"),
        Input("log-interval",       "n_intervals"),
        Input("clear-log-btn",      "n_clicks"),
    )
    def update_log_panel(_, clear_clicks):
        if ctx.triggered_id == "clear-log-btn":
            ui_log_handler.clear()
            return [html.Div("Logs cleared.", className="log-empty")], "cleared"

        records  = ui_log_handler.get_records()
        subtitle = (f"{len(records)} entries  ·  "
                    f"last update {datetime.utcnow().strftime('%H:%M:%S')} UTC")
        return _render_log_rows(records), subtitle