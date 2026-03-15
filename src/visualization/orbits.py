"""
orbits.py  —  OrbitWatch  |  Orbit trail traces

LEO satellites get 3 segments with fading opacity (comet-tail effect):
  oldest 30%  → opacity 0.05
  middle 40%  → opacity 0.18
  newest 30%  → opacity 0.55

MEO/GEO/HEO get a single full trail (they move slowly, gradient is invisible).

Trail color = orbital regime color, blended toward amber/red for warnings.
"""

import math
import plotly.graph_objects as go

EARTH_RADIUS = 6_371


def _mean_altitude(steps):
    total = sum(
        math.sqrt(s["position_km"]["x"]**2 +
                  s["position_km"]["y"]**2 +
                  s["position_km"]["z"]**2)
        for s in steps
    )
    return total / len(steps) - EARTH_RADIUS


def _regime_rgb(alt_km):
    if alt_km < 2_000:   return (0,   229, 192)   # teal
    if alt_km < 10_000:  return (72,  165, 255)   # blue
    if alt_km < 37_000:  return (167, 139, 250)   # purple
    return (110, 123, 255)                          # indigo


def _blend(rgb, tint, w):
    return tuple(int(rgb[i] * (1 - w) + tint[i] * w) for i in range(3))


def _rgba(rgb, alpha):
    return f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{alpha:.2f})"


def build_orbit_traces(satellites, warning_sats=None, critical_sats=None):
    if warning_sats  is None: warning_sats  = set()
    if critical_sats is None: critical_sats = set()

    WARNING_RGB  = (255, 159,  28)
    CRITICAL_RGB = (255,  71,  87)

    traces = []

    for name, steps in satellites.items():
        xs = [s["position_km"]["x"] for s in steps]
        ys = [s["position_km"]["y"] for s in steps]
        zs = [s["position_km"]["z"] for s in steps]
        n  = len(xs)
        if n < 3:
            continue

        alt      = _mean_altitude(steps)
        base_rgb = _regime_rgb(alt)

        if name in critical_sats:
            rgb = _blend(base_rgb, CRITICAL_RGB, 0.65)
        elif name in warning_sats:
            rgb = _blend(base_rgb, WARNING_RGB, 0.50)
        else:
            rgb = base_rgb

        if alt < 2_000:   # LEO — 3-segment fade
            c1, c2 = n * 3 // 10, n * 7 // 10
            for sx, sy, sz, alpha in [
                (xs[:c1+1],    ys[:c1+1],    zs[:c1+1],    0.05),
                (xs[c1:c2+1],  ys[c1:c2+1],  zs[c1:c2+1],  0.18),
                (xs[c2:],      ys[c2:],       zs[c2:],       0.55),
            ]:
                traces.append(go.Scatter3d(
                    x=sx, y=sy, z=sz,
                    mode="lines",
                    line=dict(width=1, color=_rgba(rgb, alpha)),
                    showlegend=False, hoverinfo="skip", name="",
                ))
        else:
            alpha = 0.45 if name in warning_sats else 0.25
            traces.append(go.Scatter3d(
                x=xs, y=ys, z=zs,
                mode="lines",
                line=dict(width=1, color=_rgba(rgb, alpha)),
                showlegend=False, hoverinfo="skip", name="",
            ))

    return traces