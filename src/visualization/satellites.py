"""
satellites.py  —  OrbitWatch  |  Satellite marker trace

Visual encoding
───────────────
CRITICAL  → red #ff4757   diamond  size 7   (miss dist < 5 km)
WARNING   → amber #ff9f1c diamond  size 5   (miss dist 5–25 km)
CAUTION   → blue #48a5ff  diamond  size 4   (miss dist 25–500 km)
NOMINAL:
  LEO  alt < 2,000 km      → teal   #00e5c0  circle  size 3
  MEO  alt 2,000–35,000 km → blue   #48a5ff  circle  size 3
  GEO  alt ~35,786 km      → purple #a78bfa  circle  size 3
  HEO  alt > 37,000 km     → indigo #6e7bff  circle  size 3
"""

import math
import plotly.graph_objects as go

EARTH_RADIUS = 6_371   # km


def _altitude(x, y, z):
    return math.sqrt(x**2 + y**2 + z**2) - EARTH_RADIUS


def _regime_color(alt_km):
    if alt_km < 2_000:   return "#00e5c0"
    if alt_km < 10_000:  return "#48a5ff"
    if alt_km < 37_000:  return "#a78bfa"
    return "#6e7bff"


def build_satellite_trace(xs, ys, zs, sat_names, warning_sats, critical_sats=None, caution_sats=None):
    """
    Build one Scatter3d trace for all satellites.

    Parameters
    ----------
    warning_sats  : set of names with WARNING conjunction
    critical_sats : set of names with CRITICAL conjunction
    caution_sats  : set of names with CAUTION conjunction (optional, inferred from warning_sats)
    """
    if critical_sats is None:
        critical_sats = set()
    if caution_sats is None:
        # Backwards compat: anything in warning_sats that isn't critical is caution
        caution_sats = warning_sats - critical_sats

    colors, sizes, symbols, outlines, hovers = [], [], [], [], []

    for name, x, y, z in zip(sat_names, xs, ys, zs):
        alt    = _altitude(x, y, z)
        regime = ("LEO" if alt < 2_000 else
                  "MEO" if alt < 10_000 else
                  "GEO" if alt < 37_000 else "HEO")

        if name in critical_sats:
            c, sz, sym = "#ff4757", 7, "diamond"
            outlines.append("rgba(255,255,255,0.30)")
            status = "🔴 CRITICAL"
        elif name in warning_sats and name not in caution_sats:
            # pure WARNING
            c, sz, sym = "#ff9f1c", 5, "diamond"
            outlines.append("rgba(255,255,255,0.20)")
            status = "🟠 WARNING"
        elif name in caution_sats:
            c, sz, sym = "#48a5ff", 4, "diamond"
            outlines.append("rgba(255,255,255,0.15)")
            status = "🔵 CAUTION"
        else:
            c, sz, sym = _regime_color(alt), 3, "circle"
            outlines.append("rgba(0,0,0,0)")
            status = "🟢 NOMINAL"

        colors.append(c); sizes.append(sz); symbols.append(sym)

        hovers.append(
            f"<b>{name}</b><br>"
            f"Alt: {alt:,.0f} km  [{regime}]<br>"
            f"Status: {status}<br>"
            f"<span style='color:#5a7090'>x:{x:.0f}  y:{y:.0f}  z:{z:.0f}</span>"
        )

    return go.Scatter3d(
        name="Satellites",
        showlegend=False,
        x=xs, y=ys, z=zs,
        mode="markers",
        marker=dict(
            size=sizes,
            color=colors,
            symbol=symbols,
            opacity=0.92,
            line=dict(color=outlines, width=0.8),
        ),
        text=hovers,
        hovertemplate="%{text}<extra></extra>",
    )