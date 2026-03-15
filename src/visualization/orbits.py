import plotly.graph_objects as go

def build_orbit_traces(satellites):

    traces = []

    for sat in satellites:

        xs, ys, zs = [], [], []

        for step in satellites[sat]:

            pos = step["position_km"]

            xs.append(pos["x"])
            ys.append(pos["y"])
            zs.append(pos["z"])

        traces.append(
            go.Scatter3d(
                x=xs,
                y=ys,
                z=zs,
                mode="lines",
                line=dict(width=1, color="rgba(120,180,255,0.4)"),
                showlegend=False,
                hoverinfo="skip"
            )
        )

    return traces
