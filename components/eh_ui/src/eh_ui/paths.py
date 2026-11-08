"""Locations of the packaged templates and static assets."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def templates_dir() -> Path:
    """Directory to register in a Jinja loader (macros: ``eh_ui/macros.html``)."""
    return _ROOT / "templates"


def static_dir() -> Path:
    """Directory containing ``eh_ui.css``; mount it as static files."""
    return _ROOT / "static"
