"""
main.py  —  OrbitWatch simulation pipeline

Usage
-----
    python main.py                          # defaults: 500 sats, 500 km threshold
    python main.py --sats 100               # limit to 100 satellites
    python main.py --threshold 200          # close-approach threshold km
    python main.py --sigma 0.3              # combined hard-body radius for Pc
    python main.py --sats 250 --threshold 300 --sigma 0.5
"""

import argparse
import json
import os
from datetime import datetime

from data.tle_fetcher import fetch_tle_data
from data.tle_parser import parse_tle_data
from propagation.orbit_propagator import (
    build_satellites,
    generate_time_steps,
    propagate_positions,
)
from analysis.close_approach_detector import detect_close_approaches, save_warnings
from visualization.orbit_visualizer import visualize


# ── Logging ───────────────────────────────────────────────────────────────────

def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")


# ── Paths ─────────────────────────────────────────────────────────────────────

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEBUG_DIR = os.path.join(BASE_DIR, "debug")


# ── Pipeline ──────────────────────────────────────────────────────────────────

def main(n_satellites: int = 500, threshold_km: float = 500, sigma_km: float = 0.5):

    os.makedirs(DEBUG_DIR, exist_ok=True)

    # ── Fetch ──────────────────────────────────────────────────────────────────
    log("[FETCH] Downloading TLE data...")
    raw_data       = fetch_tle_data()
    retrieved_time = datetime.utcnow().isoformat()
    log("[FETCH] Data downloaded")

    with open(f"{DEBUG_DIR}/raw_tle.txt", "w") as f:
        f.write(
            "# Raw TLE Data\n"
            "# Source: CelesTrak\n"
            f"# Retrieved: {retrieved_time}\n"
            "#\n"
            "# TLE Format:\n"
            "# Line 1: Satellite name\n"
            "# Line 2: Orbital metadata (catalog no., epoch, drag terms)\n"
            "# Line 3: Orbital parameters (inclination, RAAN, eccentricity,\n"
            "#          argument of perigee, mean anomaly, mean motion)\n\n"
        )
        f.write(raw_data)

    log("[FETCH] Saved raw_tle.txt")

    # ── Parse ──────────────────────────────────────────────────────────────────
    log("[PARSE] Parsing satellites...")
    satellites = parse_tle_data(raw_data)
    log(f"[PARSE] Parsed {len(satellites)} total satellites")

    # Apply user-specified limit
    satellites = satellites[:n_satellites]
    log(f"[PARSE] Using {len(satellites)} satellites for simulation")

    satellite_records = [
        {"name": s.name, "tle": {"line1": s.line1, "line2": s.line2}}
        for s in satellites
    ]

    satellites_output = {
        "metadata": {
            "description":     "Parsed satellite records derived from raw TLE data",
            "source":          "CelesTrak",
            "retrieved_at":    retrieved_time,
            "satellite_count": len(satellite_records),
            # Store pipeline params so the dashboard can display them
            "pipeline_params": {
                "n_satellites":  n_satellites,
                "threshold_km":  threshold_km,
                "sigma_km":      sigma_km,
            },
        },
        "tle_format_explanation": {
            "line1": "Catalog number, epoch, drag terms, orbital decay parameters",
            "line2": "Inclination, RAAN, eccentricity, arg of perigee, mean anomaly, mean motion",
        },
        "satellites": satellite_records,
    }

    with open(f"{DEBUG_DIR}/satellites.json", "w") as f:
        json.dump(satellites_output, f, indent=2)

    log("[PARSE] Saved satellites.json")

    # ── Propagate ──────────────────────────────────────────────────────────────
    log("[PROPAGATE] Building satellite objects")
    sat_objects = build_satellites(satellites)

    log("[PROPAGATE] Generating time steps")
    times = generate_time_steps()

    log("[PROPAGATE] Computing positions")
    positions = propagate_positions(sat_objects, times)

    positions_output = {
        "metadata": {
            "simulation_start":  retrieved_time,
            "time_step_minutes": 1,
            "duration_minutes":  90,
            "satellite_count":   len(positions),
            "pipeline_params": {
                "n_satellites": n_satellites,
                "threshold_km": threshold_km,
                "sigma_km":     sigma_km,
            },
        },
        "satellites": positions,
    }

    with open(f"{DEBUG_DIR}/positions.json", "w") as f:
        json.dump(positions_output, f, indent=2)

    log("[PROPAGATE] Saved positions.json")

    # ── Analyse ────────────────────────────────────────────────────────────────
    log(f"[ANALYSIS] Detecting close approaches (threshold={threshold_km} km, sigma={sigma_km} km)")
    warnings = detect_close_approaches(
        positions_output, threshold_km=threshold_km, sigma_km=sigma_km
    )
    log(f"[ANALYSIS] Found {len(warnings)} potential close approaches")

    save_warnings(warnings, f"{DEBUG_DIR}/warnings.json")
    log("[ANALYSIS] Saved warnings.json")

    # ── Visualise ──────────────────────────────────────────────────────────────
    log("[VISUALIZE] Launching orbit visualization")
    visualize(f"{DEBUG_DIR}/positions.json")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="OrbitWatch simulation pipeline")
    parser.add_argument(
        "--sats", type=int, default=500,
        help="Number of satellites to include (default: 500)",
    )
    parser.add_argument(
        "--threshold", type=float, default=500,
        help="Close-approach detection threshold in km (default: 500)",
    )
    parser.add_argument(
        "--sigma", type=float, default=0.5,
        help="Combined hard-body radius σ for proxy Pc in km (default: 0.5)",
    )
    args = parser.parse_args()

    main(
        n_satellites=args.sats,
        threshold_km=args.threshold,
        sigma_km=args.sigma,
    )