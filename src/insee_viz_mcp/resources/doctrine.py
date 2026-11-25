"""The doctrine as a resource: which Insee figure for which data, and what is never done."""

from .bundled import read_text

FALLBACK = "# Guide indisponible dans cette installation.\n"


def figure_doctrine() -> str:
    """How to choose and fill an Insee figure (routing table, bans, editorial block)."""
    return read_text("guide.md", fallback=FALLBACK)
