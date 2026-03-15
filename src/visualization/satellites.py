import plotly.graph_objects as go

def build_satellite_trace(xs, ys, zs, sat_names, warning_sats):

    colors = [
        "#ffd166" if s in warning_sats else "#ff6b6b"
        for s in sat_names
    ]

    return go.Scatter3d(
        name="",
        showlegend=False,
        x=xs,
        y=ys,
        z=zs,
        mode="markers",
        marker=dict(size=3, color=colors, opacity=0.9),
        text=sat_names,
        hovertemplate="<b>%{text}</b><br>x:%{x:.0f} km<br>y:%{y:.0f} km<br>z:%{z:.0f} km"
    )
