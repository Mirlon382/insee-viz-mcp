"""Small SVG toolkit: primitives, figure header and source/notes block."""

from __future__ import annotations

from dataclasses import dataclass, field

from .style import AXIS, FONT, GRID, INK, MARGIN, MUTED, NBSP_NARROW, WIDTH, esc, wrap


def text(
    x: float,
    y: float,
    value: object,
    *,
    size: float = 12,
    fill: str = INK,
    anchor: str = "start",
    weight: str | int = "normal",
    style: str = "",
    opacity: float | None = None,
) -> str:
    parts = [
        f'x="{x:.1f}" y="{y:.1f}"',
        f'font-family="{FONT}"',
        f'font-size="{size}"',
        f'fill="{fill}"',
        f'text-anchor="{anchor}"',
    ]
    if weight != "normal":
        parts.append(f'font-weight="{weight}"')
    if style:
        parts.append(f'font-style="{style}"')
    if opacity is not None:
        parts.append(f'opacity="{opacity}"')
    return f"<text {' '.join(parts)}>{esc(value)}</text>"


def line(
    x1: float, y1: float, x2: float, y2: float, color: str = GRID, width: float = 1, dash: str | None = None
) -> str:
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{color}" stroke-width="{width}"{extra}/>'
    )


def rect(
    x: float, y: float, w: float, h: float, fill: str, stroke: str | None = None, stroke_width: float = 0, rx: float = 0
) -> str:
    extra = ""
    if stroke:
        extra += f' stroke="{stroke}" stroke-width="{stroke_width}"'
    if rx:
        extra += f' rx="{rx}"'
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" height="{max(h, 0):.1f}" fill="{fill}"{extra}/>'


def path(d: str, fill: str, stroke: str | None = None, stroke_width: float = 0) -> str:
    extra = f' stroke="{stroke}" stroke-width="{stroke_width}" stroke-linejoin="round"' if stroke else ""
    return f'<path d="{d}" fill="{fill}"{extra}/>'


@dataclass
class Header:
    parts: list[str] = field(default_factory=list)
    height: float = 0.0


def header(meta, *, top: float = 30, note: str | None = None) -> Header:
    """Figure title + unit line, left aligned, above the plot area.

    Long titles wrap onto two lines (Insee titles are statements, not labels,
    so they are never truncated).
    """
    parts: list[str] = []
    title = f"Figure {meta.number} – {meta.title}" if meta.number else meta.title
    lines = wrap(title, 88)[:2]
    y = top
    for line_text in lines:
        parts.append(text(MARGIN, y, line_text, size=15.5, weight=600))
        y += 20
    height = y - 2
    if meta.unit:
        parts.append(text(MARGIN, height, meta.unit, size=12, fill=MUTED))
        height += 18
    if note:
        parts.append(text(MARGIN, height, note, size=11, fill=MUTED, style="italic"))
        height += 16
    if getattr(meta, "brand", False):
        parts.append(text(WIDTH - MARGIN, top - 2, "Insee", size=18, fill=MUTED, anchor="end", weight=700))
    return Header(parts=parts, height=height + 10)


def notes(meta, y: float, *, width: int = WIDTH) -> tuple[str, float]:
    """Lecture / Champ / Note / Source, wrapped, small grey, Insee order."""
    blocks: list[tuple[str, str]] = []
    if meta.lecture:
        blocks.append(("Lecture", meta.lecture))
    if meta.champ:
        blocks.append(("Champ", meta.champ))
    if meta.note:
        blocks.append(("Note", meta.note))
    blocks.append(("Source", meta.source))

    parts: list[str] = []
    wrap_width = max(int((width - 2 * MARGIN) / 5.5), 40)
    for label, value in blocks:
        lines = wrap(value, wrap_width)
        first = f"{label}{NBSP_NARROW}: {lines[0]}"
        parts.append(text(MARGIN, y, first, size=11, fill=MUTED))
        y += 15
        for extra in lines[1:]:
            parts.append(text(MARGIN, y, extra, size=11, fill=MUTED))
            y += 15
    return "".join(parts), y


def document(body: str, height: float, title: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height:.0f}" '
        f'viewBox="0 0 {WIDTH} {height:.0f}" role="img" aria-label="{esc(title)}">'
        f"<title>{esc(title)}</title>"
        f'<rect width="{WIDTH}" height="{height:.0f}" fill="#FFFFFF"/>'
        f"{body}</svg>"
    )


def baseline(y: float, x0: float = MARGIN, x1: float = WIDTH - MARGIN) -> str:
    return line(x0, y, x1, y, color=AXIS, width=1)
