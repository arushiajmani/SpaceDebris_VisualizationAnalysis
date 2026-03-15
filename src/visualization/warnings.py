"""
warnings.py  —  OrbitWatch  |  Load warning/critical satellite sets from disk.

Returns a tuple: (warning_sats, critical_sats)
  warning_sats  — all satellites in ANY conjunction event
  critical_sats — satellites in a CRITICAL event (miss dist < 5 km)
"""

import json


def load_warning_satellites():
    try:
        with open("debug/warnings.json") as f:
            data = json.load(f)

        warning_sats  = set()
        critical_sats = set()

        for w in data.get("warnings", []):
            warning_sats.add(w["satellite_a"])
            warning_sats.add(w["satellite_b"])
            if w.get("severity") == "CRITICAL":
                critical_sats.add(w["satellite_a"])
                critical_sats.add(w["satellite_b"])

        return warning_sats, critical_sats

    except Exception:
        return set(), set()