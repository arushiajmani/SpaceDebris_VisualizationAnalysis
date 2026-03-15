"""
src/dashboard/callbacks/playback.py
Play / pause toggle and slider auto-advance.
"""

from dash import Input, Output, State
from dash.exceptions import PreventUpdate


def register(app, store):

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
        Output("time-slider",  "value"),
        Input("animation-interval", "n_intervals"),
        State("time-slider",   "value"),
        State("playing-store", "data"),
        prevent_initial_call=True,
    )
    def advance_slider(_, current_value, is_playing):
        if not is_playing:
            raise PreventUpdate
        return (current_value + 1) % (store.duration - 1)