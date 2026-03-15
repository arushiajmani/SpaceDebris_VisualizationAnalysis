"""
src/dashboard/callbacks/modals.py
Open / close callbacks for TLE Database, Conjunction Events, Risk Dashboard, Info modals.
"""

from dash import Input, Output, State, ctx, html
from dash.exceptions import PreventUpdate

from ..components import conj_table_row, tle_row, risk_dashboard_content
from ..data_store  import load_satellites_db


def register(app, store):

    # ── TLE Database modal ────────────────────────────────────────────────────

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
        ACTIVE    = "modal-tab modal-tab-active"
        PASSIVE   = "modal-tab"

        if triggered == "close-tle-modal":
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
                    f"… {len(sats)-100} more not shown",
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

    # ── Conjunction Events modal ──────────────────────────────────────────────

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
        if ctx.triggered_id == "close-conj-modal":
            return "modal-overlay modal-hidden", [], ""

        warnings_list = live_warnings if live_warnings else store.all_warnings
        subtitle      = f"{len(warnings_list)} total events · sorted by miss distance"
        rows          = [conj_table_row(w, i) for i, w in enumerate(warnings_list)]
        if not rows:
            rows = [html.P("No conjunction events detected.",
                           style={"color":"#5a7090",
                                  "fontFamily":"'Space Mono',monospace"})]
        return "modal-overlay modal-visible", rows, subtitle

    # ── Risk Dashboard modal ──────────────────────────────────────────────────

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
        if ctx.triggered_id == "close-risk-modal":
            return "modal-overlay modal-hidden", [], ""

        warnings_list = live_warnings if live_warnings else store.all_warnings
        subtitle      = f"{len(warnings_list)} conjunction events analysed"
        content       = risk_dashboard_content(warnings_list)
        return "modal-overlay modal-visible", content, subtitle

    # ── Info modal ────────────────────────────────────────────────────────────

    @app.callback(
        Output("info-modal",      "className"),
        Input("info-btn",         "n_clicks"),
        Input("close-info-modal", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_info_modal(_, __):
        if ctx.triggered_id == "close-info-modal":
            return "modal-overlay modal-hidden"
        return "modal-overlay modal-visible"