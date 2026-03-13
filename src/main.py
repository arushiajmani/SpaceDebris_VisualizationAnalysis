from data.tle_fetcher import fetch_tle_data
from data.tle_parser import parse_tle_data
import json
import os
from datetime import datetime

def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

DEBUG_DIR = "../debug"


def main():

    os.makedirs(DEBUG_DIR, exist_ok=True)

    log("[FETCH] Downloading TLE data...")

    raw_data = fetch_tle_data()

    log("[FETCH] Data downloaded")

    # Save raw TLE for inspection
    with open(f"{DEBUG_DIR}/raw_tle.txt", "w") as f:
        f.write(raw_data)

    log("[FETCH] Saved raw_tle.txt")

    log("[PARSE] Parsing satellites...")

    satellites = parse_tle_data(raw_data)

    log(f"[PARSE] Parsed {len(satellites)} satellites")

    # Save parsed satellites
    satellites_dict = [sat.__dict__ for sat in satellites]

    with open(f"{DEBUG_DIR}/satellites.json", "w") as f:
        json.dump(satellites_dict, f, indent=2)

    log("[PARSE] Saved satellites.json")


if __name__ == "__main__":
    main()