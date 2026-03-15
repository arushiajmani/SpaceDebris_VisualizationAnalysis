"""
src/dashboard/data_store.py
All debug-file I/O and the module-level bootstrap state.

Exposes:
  load_positions()        → dict
  load_warnings()         → dict
  load_satellites_db()    → dict
  bootstrap()             → DataStore  (call once at app startup)
  DataStore               — named tuple of startup globals
"""

from __future__ import annotations
import json
import math
from dataclasses import dataclass, field
from typing import List

from .config import DETECTION_THRESHOLD_KM


# ── File paths ────────────────────────────────────────────────────────────────

POSITIONS_PATH  = "debug/positions.json"
WARNINGS_PATH   = "debug/warnings.json"
SATELLITES_PATH = "debug/satellites.json"


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_positions() -> dict:
    with open(POSITIONS_PATH) as f:
        return json.load(f)


def load_warnings() -> dict:
    try:
        with open(WARNINGS_PATH) as f:
            return json.load(f)
    except Exception:
        return {
            "warning_count": 0,
            "warnings": [],
            "warning_count_by_severity": {"CRITICAL": 0, "WARNING": 0, "CAUTION": 0},
        }


def load_satellites_db() -> dict:
    try:
        with open(SATELLITES_PATH) as f:
            return json.load(f)
    except Exception:
        return {"satellites": [], "metadata": {}}


# ── Pc recompute ──────────────────────────────────────────────────────────────

def _proxy_pc(dist_km: float, threshold_km: float = DETECTION_THRESHOLD_KM) -> float:
    """Scaled Chan proxy Pc — sigma = threshold/3 so values don't underflow."""
    if dist_km <= 0:
        return 1.0
    sigma = max(threshold_km / 3.0, 1.0)
    return max(math.exp(-0.5 * (dist_km / sigma) ** 2), 1e-15)


def recompute_pc(warnings_list: list, threshold_km: float = DETECTION_THRESHOLD_KM) -> list:
    """
    Fix stored proxy_pc values that underflowed to 0 under the old sigma=0.5 formula.
    Safe to call on already-correct data (values >= 1e-14 are left untouched).
    """
    out = []
    for w in warnings_list:
        w2 = dict(w)
        if (w2.get("proxy_pc") or 0) < 1e-14:
            w2["proxy_pc"] = _proxy_pc(w2["distance_km"], threshold_km)
        out.append(w2)
    return out


# ── Bootstrap dataclass ───────────────────────────────────────────────────────

@dataclass
class DataStore:
    """Immutable snapshot of startup state. Passed to layout and callbacks."""
    all_warnings:  List[dict]
    sat_count:     int
    duration:      int
    timestep:      int
    sim_start:     str
    init_critical: int
    init_warning:  int
    init_caution:  int
    init_total:    int


def bootstrap() -> DataStore:
    """Load all debug files and return startup globals. Call once."""
    pos_data  = load_positions()
    meta      = pos_data["metadata"]
    warn_data = load_warnings()

    raw_warnings = warn_data.get("warnings", [])
    all_warnings = recompute_pc(raw_warnings)

    sev = warn_data.get("warning_count_by_severity", {})
    return DataStore(
        all_warnings  = all_warnings,
        sat_count     = meta["satellite_count"],
        duration      = meta["duration_minutes"],
        timestep      = meta["time_step_minutes"],
        sim_start     = meta["simulation_start"],
        init_critical = sev.get("CRITICAL", sum(1 for w in all_warnings if w.get("severity") == "CRITICAL")),
        init_warning  = sev.get("WARNING",  sum(1 for w in all_warnings if w.get("severity") == "WARNING")),
        init_caution  = sev.get("CAUTION",  sum(1 for w in all_warnings if w.get("severity") == "CAUTION")),
        init_total    = len(all_warnings),
    )