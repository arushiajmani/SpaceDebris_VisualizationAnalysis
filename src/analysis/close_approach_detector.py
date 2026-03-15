"""
close_approach_detector.py
Detects close approaches between all satellite pairs and computes a
proxy probability of collision (Pc) using the Chan approximation:

    Pc ≈ exp( -(d / sigma)^2 / 2 )

where d is the miss distance in km and sigma is the combined hard-body
radius (default 0.5 km — conservative for LEO debris).  This is NOT a
rigorous Alfriend/Foster Pc (which needs covariance matrices), but it
scales correctly: very close → Pc near 1, far apart → Pc near 0, and
it lets the user threshold on a real dimensionless probability.
"""

import math
import json


# ── Distance helper ───────────────────────────────────────────────────────────

def compute_distance(p1, p2):
    """Euclidean distance between two 3-D position dicts {x,y,z} in km."""
    return math.sqrt(
        (p1["x"] - p2["x"]) ** 2 +
        (p1["y"] - p2["y"]) ** 2 +
        (p1["z"] - p2["z"]) ** 2
    )


# ── Proxy Pc ──────────────────────────────────────────────────────────────────

def compute_proxy_pc(miss_distance_km: float, sigma_km: float = 0.5) -> float:
    """
    Chan-style proxy Pc.  Returns a float in (1e-15, 1].

    sigma_km should be set to threshold_km/3 for meaningful values
    across the full detection window.  The default 0.5 km is only
    appropriate when filtering objects within a few km of each other.
    """
    if miss_distance_km <= 0:
        return 1.0
    raw = math.exp(-0.5 * (miss_distance_km / sigma_km) ** 2)
    return max(raw, 1e-15)


# ── Main detector ─────────────────────────────────────────────────────────────

def detect_close_approaches(
    positions_data: dict,
    threshold_km: float = 100,
    sigma_km: float = 0.5,
) -> list:
    """
    Find all satellite pairs whose closest approach is within threshold_km.

    Each warning dict now carries:
        satellite_a, satellite_b  — names
        distance_km               — miss distance at closest point
        time                      — ISO timestamp of closest point
        proxy_pc                  — Chan approximation Pc (0–1)
        severity                  — "CRITICAL" | "WARNING" | "CAUTION"
    """

    satellites = positions_data["satellites"]
    sat_names  = list(satellites.keys())
    warnings   = []

    for i in range(len(sat_names)):
        for j in range(i + 1, len(sat_names)):

            sat_a = sat_names[i]
            sat_b = sat_names[j]

            traj_a = satellites[sat_a]
            traj_b = satellites[sat_b]

            min_distance = float("inf")
            closest_time = None

            for k in range(len(traj_a)):
                pos_a    = traj_a[k]["position_km"]
                pos_b    = traj_b[k]["position_km"]
                distance = compute_distance(pos_a, pos_b)

                if distance < min_distance:
                    min_distance = distance
                    closest_time = traj_a[k]["time"]

            # Only record if within threshold and not the same object
            if min_distance < threshold_km and min_distance > 0.001:

                # Scale sigma to detection threshold so Pc is non-zero across window
                sigma = max(threshold_km / 3.0, 1.0)
                pc = compute_proxy_pc(min_distance, sigma_km=sigma)

                # Severity tiers based on miss distance
                if min_distance < 5:
                    severity = "CRITICAL"
                elif min_distance < 25:
                    severity = "WARNING"
                else:
                    severity = "CAUTION"

                warnings.append({
                    "satellite_a":  sat_a,
                    "satellite_b":  sat_b,
                    "distance_km":  min_distance,
                    "time":         closest_time,
                    "proxy_pc":     pc,
                    "severity":     severity,
                })

    # Sort worst-first
    warnings.sort(key=lambda w: w["distance_km"])

    return warnings


# ── Save ──────────────────────────────────────────────────────────────────────

def save_warnings(warnings: list, output_path: str) -> None:

    output = {
        "warning_count":  len(warnings),
        "critical_count": sum(1 for w in warnings if w["severity"] == "CRITICAL"),
        "warning_count_by_severity": {
            "CRITICAL": sum(1 for w in warnings if w["severity"] == "CRITICAL"),
            "WARNING":  sum(1 for w in warnings if w["severity"] == "WARNING"),
            "CAUTION":  sum(1 for w in warnings if w["severity"] == "CAUTION"),
        },
        "warnings": warnings,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)