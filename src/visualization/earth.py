"""
earth.py  —  OrbitWatch  |  Earth visualisation

Returns a LIST of 4 Plotly traces (not a single trace like the old version):
  [0] Surface   — ocean/land/ice colorscale driven by latitude (z-value)
  [1] Grid      — transparent surface at +2 km with contour lines = lat/lon grid
  [2] Atmosphere — slightly-larger semi-transparent sphere for limb glow
  [3] Starfield  — 800 scattered points on a 100,000 km sphere

IMPORTANT: orbit_visualizer.py accounts for these 4 traces — satellite markers
           are always at fig.data[4], orbit trails at fig.data[5+].
"""

import numpy as np
import plotly.graph_objects as go

EARTH_RADIUS = 6_371   # km
ATMO_RADIUS  = 6_471   # km  (~100 km above surface — Kármán line)
GRID_RADIUS  = 6_373   # km  (just above surface so contours render on top)


def _sphere(radius, u_res, v_res):
    u = np.linspace(0, 2 * np.pi, u_res)
    v = np.linspace(0, np.pi,     v_res)
    x = radius * np.outer(np.cos(u), np.sin(v))
    y = radius * np.outer(np.sin(u), np.sin(v))
    z = radius * np.outer(np.ones(u_res), np.cos(v))
    return x, y, z


def _earth_surface():
    x, y, z = _sphere(EARTH_RADIUS, 80, 80)

    # surfacecolor = normalised z → latitude proxy: 0 = south pole, 1 = north pole
    intensity = (z + EARTH_RADIUS) / (2 * EARTH_RADIUS)

    # 13-stop colorscale:  deep ocean → polar ice caps
    colorscale = [
        [0.00, "#020a14"],   # deep south pole
        [0.05, "#0a1e3c"],
        [0.12, "#b0cce0"],   # S. polar ice
        [0.20, "#0c2d50"],
        [0.32, "#0d3d70"],
        [0.44, "#0e4f85"],
        [0.50, "#103f6a"],   # mid-ocean deep
        [0.58, "#0d5070"],
        [0.68, "#0a6580"],
        [0.78, "#0e5060"],
        [0.88, "#acc8dd"],   # N. polar ice start
        [0.95, "#c0dced"],
        [1.00, "#d0e8f5"],   # north pole
    ]

    return go.Surface(
        x=x, y=y, z=z,
        surfacecolor=intensity,
        colorscale=colorscale,
        cmin=0, cmax=1,
        showscale=False,
        opacity=1.0,
        lighting=dict(
            ambient=0.55,
            diffuse=0.80,
            specular=0.25,
            roughness=0.85,
            fresnel=0.10,
        ),
        lightposition=dict(x=2_000, y=2_000, z=3_000),
        hovertemplate="<extra></extra>",
        name="Earth",
    )


def _grid_overlay():
    """Transparent surface at GRID_RADIUS whose contour lines form a lat/lon grid."""
    x, y, z = _sphere(GRID_RADIUS, 36, 18)   # 10° spacing
    intensity = np.zeros_like(x)
    return go.Surface(
        x=x, y=y, z=z,
        surfacecolor=intensity,
        colorscale=[[0, "rgba(72,165,255,0.0)"], [1, "rgba(72,165,255,0.0)"]],
        showscale=False,
        opacity=0.0,          # faces invisible — only contour lines show
        contours=dict(
            x=dict(show=True, width=1, color="rgba(72,165,255,0.15)", highlight=False),
            y=dict(show=True, width=1, color="rgba(72,165,255,0.15)", highlight=False),
            z=dict(show=True, width=1, color="rgba(72,165,255,0.15)", highlight=False),
        ),
        hovertemplate="<extra></extra>",
        name="Grid",
        showlegend=False,
    )


def _atmosphere():
    """Limb-glow atmosphere sphere — brightest at the equatorial edge."""
    x, y, z = _sphere(ATMO_RADIUS, 40, 40)
    r_equatorial = np.sqrt(x**2 + y**2)
    limb = r_equatorial / ATMO_RADIUS   # 0 at poles, ~1 at equatorial limb

    colorscale = [
        [0.00, "rgba(0,10,30,0.00)"],
        [0.55, "rgba(10,40,100,0.04)"],
        [0.80, "rgba(20,80,180,0.10)"],
        [0.92, "rgba(40,120,220,0.18)"],
        [1.00, "rgba(80,160,255,0.28)"],
    ]

    return go.Surface(
        x=x, y=y, z=z,
        surfacecolor=limb,
        colorscale=colorscale,
        cmin=0, cmax=1,
        showscale=False,
        opacity=1.0,
        hovertemplate="<extra></extra>",
        name="Atmosphere",
        lighting=dict(ambient=1.0, diffuse=0.0, specular=0.0),
    )


def _starfield(n_stars=800, seed=42):
    rng = np.random.default_rng(seed)
    R   = 100_000
    theta = rng.uniform(0, 2 * np.pi, n_stars)
    phi   = rng.uniform(0, np.pi,     n_stars)
    sx = R * np.sin(phi) * np.cos(theta)
    sy = R * np.sin(phi) * np.sin(theta)
    sz = R * np.cos(phi)
    sizes    = rng.choice([1, 1, 1, 2, 2, 3], size=n_stars)
    opacities = {1: 0.35, 2: 0.60, 3: 0.85}
    colors   = [f"rgba(220,235,255,{opacities.get(int(s),0.5):.2f})" for s in sizes]
    return go.Scatter3d(
        x=sx, y=sy, z=sz,
        mode="markers",
        marker=dict(size=list(sizes.astype(int)), color=colors, symbol="circle"),
        hoverinfo="skip",
        showlegend=False,
        opacity=0.2,
        name="Stars",
    )


def create_earth():
    """Return list of 4 traces: [surface, grid, atmosphere, starfield]."""
    return [
        _earth_surface(),
        _grid_overlay(),
        _atmosphere(),
        _starfield(),
    ]