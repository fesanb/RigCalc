"""In-process state for the most recent completed palette run.

Vectorworks handles are valid only for the current document session.  Keep the
latest completed palette run here rather than exposing them through reports or
the web UI payload.
"""


_active_run = None


def set_active_palette_run(palette_run):
    """Replace the palette's result only after a completed calculation."""
    global _active_run
    _active_run = palette_run


def get_active_palette_run():
    """Return the latest completed run, or ``None`` before calculation."""
    return _active_run


def clear_active_palette_run():
    """Drop potentially stale object handles when the palette/document closes."""
    global _active_run
    _active_run = None
