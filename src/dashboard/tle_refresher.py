"""
src/dashboard/tle_refresher.py

Owns everything main.py used to do, plus:
  - In-memory log handler the dashboard UI polls
  - Background scheduler (daemon thread, every 24 h)
  - Manual trigger callable from a Dash callback

Public API
──────────
  run_pipeline(n_sats, threshold_km) → RefreshResult
  start_scheduler(interval_hours=24)
  ui_log_handler                     → UILogHandler instance (import this)
  RefreshResult                      → dataclass with .success / .summary
"""

from __future__ import annotations

import json
import logging
import threading
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from .config import (
    DETECTION_THRESHOLD_KM,
    DURATION_MINUTES,
    TIMESTEP_MINUTES,
    MAX_SATELLITES,
)
from .data_store import (
    POSITIONS_PATH,
    WARNINGS_PATH,
    SATELLITES_PATH,
    recompute_pc,
)


# ── In-memory log handler ─────────────────────────────────────────────────────

class UILogHandler(logging.Handler):
    """
    Logging handler that keeps the last `maxlen` records in memory.
    The dashboard polls _records via the /logs callback.
    Thread-safe: emit() uses a lock.
    """

    def __init__(self, maxlen: int = 300):
        super().__init__()
        self.maxlen   = maxlen
        self._records = []
        self._lock    = threading.Lock()
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "time":    datetime.utcnow().strftime("%H:%M:%S"),
            "level":   record.levelname,   # INFO / WARNING / ERROR
            "message": self.format(record),
        }
        with self._lock:
            self._records.append(entry)
            if len(self._records) > self.maxlen:
                self._records.pop(0)

    def get_records(self) -> list:
        with self._lock:
            return list(self._records)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


# ── Module-level logger + handler (import ui_log_handler in callbacks) ────────

log = logging.getLogger("orbitwatch")
log.setLevel(logging.INFO)

ui_log_handler = UILogHandler(maxlen=300)
log.addHandler(ui_log_handler)

# Also print to terminal so docker logs / fly logs show output
_stream_handler = logging.StreamHandler()
_stream_handler.setFormatter(
    logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
)
log.addHandler(_stream_handler)


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class RefreshResult:
    success:      bool
    retrieved_at: str
    sat_count:    int
    conj_count:   int
    error:        Optional[str] = None

    @property
    def summary(self) -> str:
        if not self.success:
            return f"❌ Refresh failed: {self.error}"
        return (
            f"✓ {self.sat_count} satellites  ·  "
            f"{self.conj_count} conjunctions  ·  "
            f"fetched {self.retrieved_at[:16]} UTC"
        )


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_pipeline(
    n_sats:       int   = MAX_SATELLITES,
    threshold_km: float = DETECTION_THRESHOLD_KM,
) -> RefreshResult:
    """
    Full pipeline — runs in the calling thread.
    Writes results to debug/ on disk.
    Returns a RefreshResult regardless of success/failure.
    """

    retrieved_time = datetime.utcnow().isoformat()

    try:
        os.makedirs("debug", exist_ok=True)

        # ── 1. Fetch ──────────────────────────────────────────────────────────
        log.info("[FETCH] Downloading TLE data from CelesTrak…")
        from src.data.tle_fetcher import fetch_tle_data
        raw_data = fetch_tle_data()
        log.info("[FETCH] Data downloaded")

        # ── 2. Save raw TLE ───────────────────────────────────────────────────
        with open("debug/raw_tle.txt", "w") as f:
            f.write(
                "# Raw TLE Data\n"
                "# Source: CelesTrak\n"
                f"# Retrieved: {retrieved_time}\n\n"
            )
            f.write(raw_data)

        # ── 3. Parse ──────────────────────────────────────────────────────────
        log.info("[PARSE] Parsing satellites…")
        from src.data.tle_parser import parse_tle_data
        all_sats   = parse_tle_data(raw_data)
        satellites = all_sats[:n_sats]
        log.info(f"[PARSE] {len(all_sats)} total  ·  using {len(satellites)}")

        # ── 4. Save satellites.json ───────────────────────────────────────────
        sat_records = [
            {"name": s.name, "tle": {"line1": s.line1, "line2": s.line2}}
            for s in satellites
        ]
        satellites_output = {
            "metadata": {
                "description":     "Parsed TLE records",
                "source":          "CelesTrak",
                "retrieved_at":    retrieved_time,
                "satellite_count": len(sat_records),
                "pipeline_params": {
                    "n_satellites":  n_sats,
                    "threshold_km":  threshold_km,
                },
            },
            "satellites": sat_records,
        }
        with open(SATELLITES_PATH, "w") as f:
            json.dump(satellites_output, f, indent=2)

        # ── 5. Propagate ──────────────────────────────────────────────────────
        log.info("[PROPAGATE] Building satellite objects…")
        from src.propagation.orbit_propagator import (
            build_satellites,
            generate_time_steps,
            propagate_positions,
        )
        sat_objects = build_satellites(satellites)

        log.info(f"[PROPAGATE] Computing {DURATION_MINUTES} min of positions…")
        times     = generate_time_steps(minutes=DURATION_MINUTES, step=TIMESTEP_MINUTES)
        positions = propagate_positions(sat_objects, times)

        positions_output = {
            "metadata": {
                "simulation_start":  retrieved_time,
                "time_step_minutes": TIMESTEP_MINUTES,
                "duration_minutes":  DURATION_MINUTES,
                "satellite_count":   len(positions),
            },
            "satellites": positions,
        }
        with open(POSITIONS_PATH, "w") as f:
            json.dump(positions_output, f)
        log.info("[PROPAGATE] Positions saved")

        # ── 6. Detect conjunctions ────────────────────────────────────────────
        log.info(f"[ANALYSE] Detecting conjunctions (threshold {threshold_km} km)…")
        from src.analysis.close_approach_detector import detect_close_approaches, save_warnings
        warnings = detect_close_approaches(
            positions_output, threshold_km=threshold_km
        )
        warnings = recompute_pc(warnings)
        save_warnings(warnings, WARNINGS_PATH)
        log.info(f"[ANALYSE] Found {len(warnings)} conjunction events")

        log.info(f"[DONE] Refresh complete  ·  {retrieved_time[:16]} UTC")

        return RefreshResult(
            success      = True,
            retrieved_at = retrieved_time,
            sat_count    = len(positions),
            conj_count   = len(warnings),
        )

    except Exception as exc:
        log.error(f"[ERROR] Pipeline failed: {exc}")
        return RefreshResult(
            success      = False,
            retrieved_at = retrieved_time,
            sat_count    = 0,
            conj_count   = 0,
            error        = str(exc),
        )


# ── Background scheduler ──────────────────────────────────────────────────────

_scheduler_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


def start_scheduler(interval_hours: float = 24) -> None:
    """
    Start a daemon thread that calls run_pipeline() every `interval_hours`.
    Safe to call multiple times — only one thread runs at a time.
    """
    global _scheduler_thread

    if _scheduler_thread and _scheduler_thread.is_alive():
        log.info(f"[SCHEDULER] Already running (interval={interval_hours}h)")
        return

    _stop_event.clear()

    def _loop():
        log.info(f"[SCHEDULER] Started — refresh every {interval_hours}h")
        while not _stop_event.is_set():
            # Wait for interval, but check stop_event every 60 s so we can
            # shut down cleanly without waiting the full interval
            interval_secs = interval_hours * 3600
            waited = 0
            while waited < interval_secs and not _stop_event.is_set():
                _stop_event.wait(timeout=60)
                waited += 60
            if not _stop_event.is_set():
                log.info("[SCHEDULER] Triggering scheduled TLE refresh…")
                run_pipeline()

    _scheduler_thread = threading.Thread(target=_loop, daemon=True, name="tle-refresher")
    _scheduler_thread.start()


def stop_scheduler() -> None:
    """Signal the background scheduler to stop after its current sleep."""
    _stop_event.set()
    log.info("[SCHEDULER] Stop requested")