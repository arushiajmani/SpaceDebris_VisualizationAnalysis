"""
app.py  —  OrbitWatch entry point

All logic lives in src/dashboard/.
This file only wires the pieces together.
"""

from dash import Dash

from src.dashboard.data_store          import bootstrap
from src.dashboard.layout              import build_layout
from src.dashboard.callbacks           import register_all


# Bootstrap
store = bootstrap()

# App
app    = Dash(__name__, suppress_callback_exceptions=True)
app.layout = build_layout(store)

# Callbacks
register_all(app, store)

# Server (for gunicorn / deployment)
server = app.server

if __name__ == "__main__":
    app.run(debug=True)