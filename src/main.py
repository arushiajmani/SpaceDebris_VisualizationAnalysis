from data.tle_fetcher import fetch_tle_data
from data.tle_parser import parse_tle_data
from propagation.orbit_propagator import (
    build_satellites,
    generate_time_steps,
    propagate_positions
)
from analysis.close_approach_detector import detect_close_approaches, save_warnings
import json
import os
from datetime import datetime


# ---------- Logging ----------

def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")


# ---------- Paths ----------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEBUG_DIR = os.path.join(BASE_DIR, "debug")


# ---------- Main Pipeline ----------

def main():

    os.makedirs(DEBUG_DIR, exist_ok=True)

    log("[FETCH] Downloading TLE data...")
    raw_data = fetch_tle_data()

    retrieved_time = datetime.utcnow().isoformat()

    log("[FETCH] Data downloaded")

    # ---------- Save RAW TLE ----------
    with open(f"{DEBUG_DIR}/raw_tle.txt", "w") as f:
        f.write(
            "# Raw TLE Data\n"
            "# Source: CelesTrak\n"
            f"# Retrieved: {retrieved_time}\n"
            "#\n"
            "# TLE Format:\n"
            "# Line 1: Satellite name\n"
            "# Line 2: Orbital metadata including catalog number, epoch, drag terms\n"
            "# Line 3: Orbital parameters including inclination, eccentricity, mean motion\n"
            "# These parameters are used by the SGP4 orbital propagation model.\n\n"
        )
        f.write(raw_data)

    log("[FETCH] Saved raw_tle.txt")

    # ---------- Parse Satellites ----------
    log("[PARSE] Parsing satellites...")

    satellites = parse_tle_data(raw_data)

    log(f"[PARSE] Parsed {len(satellites)} satellites")

    # limit dataset
    satellites = satellites[:250]

    log(f"[PARSE] Using {len(satellites)} satellites for simulation")

    # ---------- Save Parsed Satellites ----------
    satellite_records = []

    for sat in satellites:
        satellite_records.append({
            "name": sat.name,
            "tle": {
                "line1": sat.line1,
                "line2": sat.line2
            }
        })

    satellites_output = {
        "metadata": {
            "description": "Parsed satellite records derived from raw TLE data",
            "source": "CelesTrak",
            "retrieved_at": retrieved_time,
            "satellite_count": len(satellite_records)
        },

        "tle_format_explanation": {
            "line1": "Contains satellite catalog number, epoch timestamp, drag terms, and orbital decay parameters",
            "line2": "Contains orbital parameters including inclination, RAAN, eccentricity, argument of perigee, mean anomaly, and mean motion"
        },

        "satellites": satellite_records
    }

    with open(f"{DEBUG_DIR}/satellites.json", "w") as f:
        json.dump(satellites_output, f, indent=2)

    log("[PARSE] Saved satellites.json")

    # ---------- Propagation ----------
    log("[PROPAGATE] Building satellite objects")
    sat_objects = build_satellites(satellites)

    log("[PROPAGATE] Generating time steps")
    times = generate_time_steps()

    log("[PROPAGATE] Computing positions")
    positions = propagate_positions(sat_objects, times)

    # ---------- Save Positions ----------
    positions_output = {
        "metadata": {
            "simulation_start": retrieved_time,
            "time_step_minutes": 1,
            "duration_minutes": 90,
            "satellite_count": len(positions)
        },
        "satellites": positions
    }

    with open(f"{DEBUG_DIR}/positions.json", "w") as f:
        json.dump(positions_output, f, indent=2)

    log("[PROPAGATE] Saved positions.json")
    log("[ANALYSIS] Detecting close approaches")

    warnings = detect_close_approaches(positions_output, threshold_km=500)

    log(f"[ANALYSIS] Found {len(warnings)} potential close approaches")

    save_warnings(warnings, f"{DEBUG_DIR}/warnings.json")

    log("[ANALYSIS] Saved warnings.json")

# ---------- Entry Point ----------

if __name__ == "__main__":
    main()