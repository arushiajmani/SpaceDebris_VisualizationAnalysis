"""
src/dashboard/callbacks/__init__.py
Single entry point: register_all(app, store) wires every callback.
"""

from . import playback, orbit, satellites, filters, modals, refresh


def register_all(app, store):
    """Call once after app = Dash(...) to register every callback."""
    playback.register(app, store)
    orbit.register(app, store)
    satellites.register(app, store)
    filters.register(app, store)
    modals.register(app, store)
    refresh.register(app, store)