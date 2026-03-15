"""
src/dashboard/config.py
All constants, thresholds, and UI mappings for OrbitWatch.
Single source of truth — import from here everywhere else.
"""

# ── Simulation defaults ───────────────────────────────────────────────────────
DETECTION_THRESHOLD_KM = 500      # conjunction detection radius
DURATION_MINUTES       = 90
TIMESTEP_MINUTES       = 1
MAX_SATELLITES         = 500

# ── Severity distance tiers (km) ─────────────────────────────────────────────
CRITICAL_KM = 5
WARNING_KM  = 25
# anything < DETECTION_THRESHOLD_KM and >= WARNING_KM → CAUTION

# ── Pc slider ─────────────────────────────────────────────────────────────────
PC_LEVELS = [0, 1e-2, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]

PC_MARKS  = {
    0: "any",
    1: "1e-2",
    2: "0.1",
    3: "0.3",
    4: "0.5",
    5: "0.7",
    6: "0.9",
    7: "1.0",
}

# ── Colour palette ────────────────────────────────────────────────────────────
SEVERITY_COLOR = {
    "CRITICAL": "#ff4757",
    "WARNING":  "#ff9f1c",
    "CAUTION":  "#48a5ff",
}

REGIME_COLOR = {
    "LEO": "#00e5c0",
    "MEO": "#48a5ff",
    "GEO": "#a78bfa",
    "HEO": "#6e7bff",
}

EARTH_RADIUS_KM = 6_371

# ── Camera defaults ───────────────────────────────────────────────────────────
DEFAULT_CAMERA_EYE = {"x": 1.6, "y": 1.4, "z": 0.9}
CAMERA_MIN_R       = 0.4    # closest zoom (above Earth surface)
CAMERA_MAX_R       = 6.0    # farthest zoom
ZOOM_IN_FACTOR     = 0.80
ZOOM_OUT_FACTOR    = 1.25