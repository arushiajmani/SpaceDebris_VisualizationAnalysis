"""
app.py  —  OrbitWatch entry point

Startup sequence:
  1. Run pipeline once (populates debug/ if empty or stale)
  2. Start 24h background scheduler
  3. Bootstrap DataStore from debug files
  4. Build Dash layout
  5. Register all callbacks
"""

import os
import json
from dash import Dash

from src.dashboard.tle_refresher import run_pipeline, start_scheduler, log
from src.dashboard.data_store    import bootstrap
from src.dashboard.layout        import build_layout
from src.dashboard.callbacks     import register_all


# ── First-run pipeline ────────────────────────────────────────────────────────
if not os.path.exists("debug/positions.json"):
    log.info("[STARTUP] No debug data found — running initial pipeline…")
    run_pipeline()
else:
    # Log a summary from existing debug files so the log panel isn't empty
    log.info("[STARTUP] OrbitWatch initialising…")
    try:
        with open("debug/positions.json") as f:
            pos = json.load(f)
        meta = pos.get("metadata", {})
        log.info(f"[STARTUP] Loaded positions  ·  {meta.get('satellite_count','?')} satellites")
        log.info(f"[STARTUP] Sim start  ·  {meta.get('simulation_start','?')[:16]} UTC")
        log.info(f"[STARTUP] Duration  ·  {meta.get('duration_minutes','?')} min  "
                 f"·  step {meta.get('time_step_minutes','?')} min")
    except Exception as e:
        log.warning(f"[STARTUP] Could not read positions.json: {e}")
    try:
        with open("debug/warnings.json") as f:
            warn = json.load(f)
        sev = warn.get("warning_count_by_severity", {})
        log.info(f"[STARTUP] Conjunctions  ·  "
                 f"{sev.get('CRITICAL',0)} CRITICAL  "
                 f"{sev.get('WARNING',0)} WARNING  "
                 f"{sev.get('CAUTION',0)} CAUTION")
    except Exception as e:
        log.warning(f"[STARTUP] Could not read warnings.json: {e}")
    log.info("[STARTUP] Ready  ·  TLE auto-refresh every 24h")

# ── Background scheduler ──────────────────────────────────────────────────────
start_scheduler(interval_hours=24)

# ── Bootstrap ─────────────────────────────────────────────────────────────────
store = bootstrap()

# ── App ───────────────────────────────────────────────────────────────────────
app = Dash(
    __name__,
    suppress_callback_exceptions=True,
    update_title=None,          # removes "Updating..." browser tab flash
)
# Suppress the Dash "Server Unavailable" error overlay in the UI
app.config.suppress_callback_exceptions = True
app.layout = build_layout(store)

# ── Callbacks ─────────────────────────────────────────────────────────────────
register_all(app, store)

# ── Server (gunicorn / Fly.io) ────────────────────────────────────────────────
server = app.server


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run_server(debug=False, host="0.0.0.0", port=port)