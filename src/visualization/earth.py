import numpy as np
import plotly.graph_objects as go

def create_earth():

    radius = 6371

    u = np.linspace(0, 2*np.pi, 50)
    v = np.linspace(0, np.pi, 50)

    x = radius * np.outer(np.cos(u), np.sin(v))
    y = radius * np.outer(np.sin(u), np.sin(v))
    z = radius * np.outer(np.ones(np.size(u)), np.cos(v))

    return go.Surface(
        x=x,
        y=y,
        z=z,
        hovertemplate="<extra></extra>",
        colorscale=[
            [0, "#1b3b6f"],
            [0.5, "#3fa7d6"],
            [1, "#a8e6ff"]
        ],
        showscale=False,
        opacity=0.9
    )
