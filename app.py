from dash import Dash, dcc, html
from dash.dependencies import Input, Output, State
from datetime import datetime, timedelta
import json

from src.visualization.orbit_visualizer import visualize, visualize_step


# Load initial visualization
fig = visualize("debug/positions.json")


# Load simulation metadata
with open("debug/positions.json") as f:
    positions = json.load(f)

metadata = positions["metadata"]


# Load warnings
try:
    with open("debug/warnings.json") as f:
        warnings = json.load(f)["warnings"]
except:
    warnings = []


app = Dash(__name__)


app.layout = html.Div(

    style={
        "backgroundImage": "url('/assets/space_bg.jpg')",
        "backgroundSize": "cover",
        "backgroundPosition": "center",
        "backgroundRepeat": "no-repeat",
        "minHeight": "100vh",
        "color": "#f0f6ff",
        "fontFamily": "Arial",
        "padding": "30px"
    },

    children=[

        html.H1(
            "🛰 Space Debris Monitoring Dashboard",
            style={"textAlign": "center", "marginBottom": "30px"}
        ),

        # Timeline slider
        dcc.Slider(
            id="time-slider",
            min=0,
            max=metadata["duration_minutes"] - 1,
            step=1,
            value=0,
            marks={i: str(i) for i in range(0, metadata["duration_minutes"], 10)},
        ),

        # Play Pause buttons
        html.Div(
            style={"textAlign": "center", "marginTop": "10px"},
            children=[
                html.Button("▶ Play", id="play-button", n_clicks=0),
                html.Button("⏸ Pause", id="pause-button", n_clicks=0,
                            style={"marginLeft": "10px"})
            ]
        ),

        # Animation timer
        dcc.Interval(
            id="animation-interval",
            interval=500,
            n_intervals=0,
            disabled=True
        ),

        # Simulation time display
        html.Div(
            id="time-display",
            style={
                "textAlign": "center",
                "fontSize": "18px",
                "marginBottom": "15px",
                "color": "#e6f1ff"
            }
        ),

        html.Div(

            style={
                "display": "grid",
                "gridTemplateColumns": "3fr 1fr",
                "gap": "25px"
            },

            children=[

                dcc.Graph(
                    id="orbit-graph",
                    figure=fig,
                    style={"height": "80vh"}
                ),

                html.Div(

                    style={
                        "backgroundColor": "rgba(15,25,40,0.6)",
                        "padding": "25px",
                        "borderRadius": "15px",
                        "backdropFilter": "blur(8px)",
                        "border": "1px solid rgba(255,255,255,0.1)"
                    },

                    children=[

                        html.H3("⚠ Close Approaches"),

                        html.Div(
                            children=[
                                html.P(
                                    f"{w['satellite_a']} — {w['satellite_b']} | {w['distance_km']:.1f} km"
                                )
                                for w in warnings[:8]
                            ] if warnings else
                            html.P("No close approaches detected")
                        ),

                        html.Hr(),

                        html.H3("📊 Simulation Info"),

                        html.P(f"Satellites: {metadata['satellite_count']}"),
                        html.P(f"Duration: {metadata['duration_minutes']} min"),
                        html.P(f"Timestep: {metadata['time_step_minutes']} min"),
                    ]
                )
            ]
        )
    ]
)


server = app.server


# Update visualization when slider changes
@app.callback(
    Output("orbit-graph", "figure"),
    Output("time-display", "children"),
    Input("time-slider", "value")
)
def update_orbit(step):

    fig = visualize_step("debug/positions.json", step)

    start = datetime.fromisoformat(metadata["simulation_start"])
    timestep = metadata["time_step_minutes"]

    current_time = start + timedelta(minutes=step * timestep)

    time_text = f"🕒 Simulation Time: {current_time.strftime('%Y-%m-%d %H:%M:%S UTC')}"

    return fig, time_text


# Play / Pause control
@app.callback(
    Output("animation-interval", "disabled"),
    Input("play-button", "n_clicks"),
    Input("pause-button", "n_clicks"),
)
def control_animation(play, pause):

    if play > pause:
        return False

    return True


# Advance slider automatically
@app.callback(
    Output("time-slider", "value"),
    Input("animation-interval", "n_intervals"),
    State("time-slider", "value")
)
def advance_slider(n, current_value):

    max_step = metadata["duration_minutes"] - 1

    return (current_value + 1) % max_step


if __name__ == "__main__":
    app.run(debug=True)
