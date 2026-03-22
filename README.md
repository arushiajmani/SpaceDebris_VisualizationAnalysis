<div align="center">

# 🛸 OrbitWatch

### Real-Time Space Debris Visualization & Conjunction Analysis

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Dash](https://img.shields.io/badge/Plotly_Dash-2.14+-00B4D8?style=for-the-badge&logo=plotly&logoColor=white)](https://dash.plotly.com)
[![Skyfield](https://img.shields.io/badge/Skyfield-1.54-blueviolet?style=for-the-badge)](https://rhodesmill.org/skyfield/)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://spacedebris-visualizationanalysis.onrender.com/)

> **Track thousands of satellites and debris objects in Earth orbit — live, in your browser.**  
> OrbitWatch ingests real Two-Line Element (TLE) data, propagates orbital mechanics with SGP4, detects conjunction events by severity, and renders everything in an interactive 3-D dashboard.
### 🌐 [Live Demo → spacedebris-visualizationanalysis.onrender.com](https://spacedebris-visualizationanalysis.onrender.com/)
---

</div>

## ✨ Features

| Capability | Details |
|---|---|
| 🌍 **3-D Globe Visualization** | Plotly-powered interactive globe showing real satellite positions |
| ⚠️ **Conjunction Detection** | Proximity warnings classified as `CAUTION`, `WARNING`, and `CRITICAL` |
| 🔄 **Auto TLE Refresh** | Live orbital elements fetched every 24 hours via a background scheduler |
| 📊 **Analytics Dashboard** | Orbit type distribution, debris density heatmaps, historical trends |
| 🪵 **Live Log Panel** | Real-time startup and pipeline log stream in the UI |

---

## 🌌 How It Works
```
TLE Source (CelesTrak / Space-Track)
          │
          ▼
  TLE Refresher (src/dashboard/tle_refresher.py)
          │  Runs SGP4 propagation via sgp4 + skyfield
          │  Saves positions & warnings → debug/
          ▼
  DataStore Bootstrap (src/dashboard/data_store.py)
          │  Loads JSON snapshots into memory
          ▼
  Dash Layout + Callbacks (src/dashboard/layout.py / callbacks.py)
          │  Renders globe, charts, warning table, log panel
          ▼
        Browser  🌐
```

---

## 🚀 Quick Start

### 1 · Local (Python)
```bash
# Clone
git clone https://github.com/arushiajmani/SpaceDebris_VisualizationAnalysis.git
cd SpaceDebris_VisualizationAnalysis

# Install dependencies
pip install -r requirements.txt

# Run
python3 app.py
```

Open **http://localhost:10000** in your browser.

> On first launch, the pipeline runs automatically to populate `debug/` with satellite positions and conjunction warnings.

---

## 🗂️ Project Structure
```
SpaceDebris_VisualizationAnalysis/
│
├── app.py                          # ← Entry point (OrbitWatch startup sequence)
├── requirements.txt                # Python dependencies
│
├── src/
│   └── dashboard/
│       ├── tle_refresher.py        # TLE fetch, SGP4 propagation, scheduler
│       ├── data_store.py           # In-memory data bootstrap from debug/
│       ├── layout.py               # Dash UI layout builder
│       └── callbacks.py            # Interactive callback registrations
│
├── assets/                         # Static CSS / JS / images
├── debug/                          # Runtime JSON snapshots (auto-generated)
│   ├── positions.json              # Propagated satellite positions + metadata
│   └── warnings.json               # Conjunction events by severity
```

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `dash >= 2.14` | Web application framework |
| `plotly == 6.6.0` | Interactive 3-D globe & charts |
| `sgp4 == 2.25` | SGP4/SDP4 orbital propagator |
| `skyfield == 1.54` | High-precision astrodynamics |
| `numpy == 2.2.6` | Numerical array operations |
| `requests == 2.32.5` | HTTP client for TLE fetching |

---

## 🛰️ Data Pipeline Detail

### Startup Sequence (`app.py`)

1. **Check for cached data** — if `debug/positions.json` is absent, the full pipeline runs immediately.
2. **Start background scheduler** — TLE refresh fires every **24 hours** in a daemon thread.
3. **Bootstrap DataStore** — load latest JSON snapshots into memory for the Dash callbacks.
4. **Build layout** — assemble the full dashboard UI from the data store.
5. **Register callbacks** — wire all Dash interactivity.
6. **Serve** — Dash's built-in server starts on `0.0.0.0:10000`.

### Conjunction Severity Levels

| Level | Meaning |
|---|---|
| 🟡 `CAUTION` | Objects within a moderate proximity threshold |
| 🟠 `WARNING` | Close approach warranting monitoring |
| 🔴 `CRITICAL` | Imminent conjunction risk — action advised |

---

## 🔧 Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `PORT` | `10000` | Port the app listens on |

The TLE refresh interval is set in `app.py`:
```python
start_scheduler(interval_hours=24)
```

Change this value to control how frequently orbital elements are updated.

---

<div align="center">

Made by [arushiajmani](https://github.com/arushiajmani)

*"The cosmos is within us. We are made of star-stuff."* — Carl Sagan

</div>
