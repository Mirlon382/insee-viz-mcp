"""Insee visual conventions: type, palette, spacing, number formatting.

Everything a figure needs in order to look like it belongs in an Insee
publication lives here, so chart builders never hard-code style.
"""

from __future__ import annotations

import math
import re
import unicodedata

# --- Typography -------------------------------------------------------------
# Insee uses its own "Marianne" typeface; fall back gracefully.
FONT = "Marianne, Inter, 'Noto Sans', 'DejaVu Sans', sans-serif"

INK = "#202021"        # titles, tick labels
MUTED = "#5D5D5E"      # notes, axis unit
GRID = "#E4E4E4"       # horizontal gridlines
AXIS = "#B9B9B9"       # baseline only
NO_DATA = "#CFCFCF"    # "non disponible" on maps
WHITE = "#FFFFFF"

# Categorical series (sampled from Insee Première / Informations rapides).
SERIES = ["#194E9B", "#57A9FC", "#E0494E", "#245199", "#9AD1FE", "#7A5195"]

# Sequential blue ramp used by Insee choropleths (light -> dark).
BLUE_CLASSES = ["#D9EDFE", "#9AD1FE", "#57A9FC", "#278DFE", "#245199"]

BAR_MAIN = "#194E9B"
BAR_SOFT = "#9AD1FE"

# --- Geometry ---------------------------------------------------------------
WIDTH = 920           # every figure is 920 px wide (Insee web images are 900)
MARGIN = 40

NBSP_NARROW = "\u202f"  # French thousands separator


def esc(value: object) -> str:
    """Escape text for SVG/XML."""
    s = str(value)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def fr_num(value: float, decimals: int = 0) -> str:
    """Format a number the French way: 1 813 800 / 45,8 (narrow nbsp + comma)."""
    if value is None:
        return ""
    sign = "-" if value < 0 else ""
    body = f"{abs(float(value)):,.{max(decimals, 0)}f}"
    body = body.replace(",", NBSP_NARROW).replace(".", ",")
    return sign + body


def axis_num(value: float, decimals: int = 0) -> str:
    """Axis label without noisy trailing zeros (40,0 -> 40)."""
    body = fr_num(value, decimals)
    if "," in body:
        body = body.rstrip("0").rstrip(",")
    return body


def pct(value: float, decimals: int = 1) -> str:
    return f"{fr_num(value, decimals)}{NBSP_NARROW}%"


def fmt_value(value: float, decimals: int = 0, unit: str | None = None) -> str:
    """Value label: number plus a compact unit when it fits on a bar end."""
    text = fr_num(value, decimals)
    if unit:
        text = f"{text}{NBSP_NARROW}{unit}"
    return text


def nice_ticks(lo: float, hi: float, target: int = 5) -> list[float]:
    """Round tick positions covering [lo, hi] exactly (last tick >= hi)."""
    if hi <= lo:
        hi = lo + 1
    span = hi - lo
    raw = span / max(target - 1, 1)
    exponent = math.floor(math.log10(raw)) if raw > 0 else 0
    step = 10 ** exponent
    for multiplier in (1, 2, 2.5, 5, 10):
        candidate = multiplier * 10 ** exponent
        if span / candidate <= target:
            step = candidate
            break
    start = math.floor(lo / step) * step
    end = math.ceil(hi / step) * step
    count = int(round((end - start) / step))
    return [round(start + i * step, 10) for i in range(count + 1)]


def wrap(text: str, width: int = 108) -> list[str]:
    """Greedy word wrap for notes and labels; keeps long words intact."""
    words = str(text).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def slugify(text: str, max_len: int = 60) -> str:
    """Filesystem-safe slug, accents removed."""
    ascii_text = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return (slug[:max_len].rstrip("-")) or "figure"
