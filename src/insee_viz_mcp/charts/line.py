"""Line chart in Insee house style: horizontal gridlines only, direct
end-of-line labels, time-proportional x axis."""

from __future__ import annotations

import math
import re
from statistics import median

from ..models.figures import LineSpec, Series
from ..style import AXIS, GRID, MARGIN, MUTED, SERIES, WIDTH, axis_num, esc, nice_ticks
from ..svgkit import baseline, document, header, line, notes, text

PLOT_H = 320.0
PERIOD_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
PERIOD_QUARTER = re.compile(r"^(\d{4})-[TQ]([1-4])$")
PERIOD_YEAR = re.compile(r"^(\d{4})$")


def _to_ordinal(value: str) -> float | None:
    """Map a period label to a month ordinal, or a number to itself."""
    v = str(value).strip().replace("\u00a0", " ")
    m = PERIOD_MONTH.match(v)
    if m:
        return int(m.group(1)) * 12 + int(m.group(2)) - 1
    m = PERIOD_QUARTER.match(v)
    if m:
        return int(m.group(1)) * 12 + (int(m.group(2)) - 1) * 3
    m = PERIOD_YEAR.match(v)
    if m:
        return int(m.group(1)) * 12
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


def render_line(spec: LineSpec) -> str:
    meta = spec.meta
    series: list[Series] = list(spec.series)

    # -- x domain -----------------------------------------------------------
    raw_x = [p.x for s in series for p in s.points]
    ordinals = [_to_ordinal(x) for x in raw_x]
    temporal = all(o is not None for o in ordinals)
    monthly = any(
        PERIOD_MONTH.match(str(p.x).strip()) or PERIOD_QUARTER.match(str(p.x).strip()) for s in series for p in s.points
    )

    if temporal:
        x_domain = (float(min(ordinals)), float(max(ordinals)))  # type: ignore[arg-type]
    else:
        cats = list(dict.fromkeys(str(x) for x in raw_x))
        x_domain = (0.0, float(len(cats) - 1))
        cat_index = {c: float(i) for i, c in enumerate(cats)}

    def xpos(value: str) -> float:
        if temporal:
            return _to_ordinal(value)  # type: ignore[return-value]
        return cat_index[str(value)]

    # -- y domain -----------------------------------------------------------
    values = [p.y for s in series for p in s.points]
    if spec.reference is not None:
        values.append(spec.reference)
    lo, hi = min(values), max(values)
    if spec.y_zero:
        lo = min(lo, 0.0)
    if spec.y_min is not None:
        lo = spec.y_min
    if spec.y_max is not None:
        hi = spec.y_max
    if hi == lo:
        hi = lo + 1
    # no artificial padding: the ticks themselves set the frame, so the axis
    # opens on a round value instead of wasting a whole class of empty space
    ticks = nice_ticks(lo, hi, 6)
    lo, hi = ticks[0], ticks[-1]

    end_labels = spec.end_labels and len(series) <= 4
    head = header(meta)
    parts: list[str] = list(head.parts)
    top = head.height + 10
    # reserve just enough room for the end labels, capped so the plot keeps its width
    label_room = 0.0
    if end_labels:
        longest = max((len(s.label) for s in series), default=6)
        label_room = min(max(longest * 6.4 + 24, 110), 260)
    plot_x0, plot_x1 = MARGIN + 54, WIDTH - (label_room or MARGIN)
    plot_bottom = top + PLOT_H

    def px(value: str) -> float:
        d0, d1 = x_domain
        if d1 == d0:
            return plot_x0
        return plot_x0 + (xpos(value) - d0) / (d1 - d0) * (plot_x1 - plot_x0)

    def sx_ordinal(ordinal: float) -> float:
        d0, d1 = x_domain
        if d1 == d0:
            return plot_x0
        return plot_x0 + (ordinal - d0) / (d1 - d0) * (plot_x1 - plot_x0)

    def sy(value: float) -> float:
        return plot_bottom - (value - lo) / (hi - lo) * (plot_bottom - top)

    # -- legend (only when there is no room for end labels) ------------------
    if not end_labels:
        cursor = MARGIN
        for i, s in enumerate(series):
            parts.append(line(cursor, top - 6, cursor + 18, top - 6, color=SERIES[i % len(SERIES)], width=2.5))
            parts.append(text(cursor + 24, top - 2, s.label, size=11.5))
            cursor += 24 + len(s.label) * 6.3 + 20
        top += 16
        plot_bottom += 16

    # -- grid + y labels ----------------------------------------------------
    for tick in ticks:
        y = sy(tick)
        parts.append(line(plot_x0, y, plot_x1, y, color=GRID))
        parts.append(text(plot_x0 - 10, y + 4, axis_num(tick, spec.decimals), size=11, fill=MUTED, anchor="end"))
    parts.append(baseline(plot_bottom, plot_x0, plot_x1))

    # -- x ticks ------------------------------------------------------------
    for position, label in _x_ticks(raw_x, temporal, monthly):
        if temporal:
            x = sx_ordinal(position)
        else:
            d0, d1 = x_domain
            x = plot_x0 + (position - d0) / (d1 - d0) * (plot_x1 - plot_x0) if d1 != d0 else plot_x0
        if x < plot_x0 - 1 or x > plot_x1 + 1:
            continue
        parts.append(line(x, plot_bottom, x, plot_bottom + 5, color=AXIS))
        parts.append(text(x, plot_bottom + 19, label, size=11, fill=MUTED, anchor="middle"))

    # -- reference line -----------------------------------------------------
    if spec.reference is not None:
        y = sy(spec.reference)
        parts.append(line(plot_x0, y, plot_x1, y, color="#8A8A8A", width=1, dash="5 4"))
        parts.append(
            text(
                plot_x1,
                y - 6,
                spec.reference_label or axis_num(spec.reference, spec.decimals),
                size=10.5,
                fill=MUTED,
                anchor="end",
            )
        )

    # -- series -------------------------------------------------------------
    labels_to_place: list[tuple[float, int]] = []
    for i, s in enumerate(series):
        color = SERIES[i % len(SERIES)]
        points = sorted(s.points, key=lambda p: xpos(p.x))
        coords = [(px(p.x), sy(p.y)) for p in points]

        # a genuine hole in the series breaks the line
        step = (
            median([abs(xpos(b.x) - xpos(a.x)) for a, b in zip(points, points[1:], strict=False)])
            if len(points) > 1
            else 0
        )
        segments: list[list[tuple[float, float]]] = [[coords[0]] if coords else []]
        paired = zip(points, coords, strict=False)
        shifted = zip(points[1:], coords[1:], strict=False)
        for (prev_pt, _prev_xy), (pt, xy) in zip(paired, shifted, strict=False):
            if temporal and step and abs(xpos(pt.x) - xpos(prev_pt.x)) > step * 1.8:
                segments.append([])
            segments[-1].append(xy)

        for segment in segments:
            if len(segment) < 2:
                continue
            d = " ".join(("M" if j == 0 else "L") + f"{x:.1f},{y:.1f}" for j, (x, y) in enumerate(segment))
            parts.append(
                f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.2" '
                f'stroke-linejoin="round" stroke-linecap="round"><title>{esc(s.label)}</title></path>'
            )

        lx, ly = coords[-1]
        parts.append(
            f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.6" fill="{color}" stroke="#FFFFFF" stroke-width="1.4"/>'
        )
        if end_labels:
            labels_to_place.append((ly, i))

    # -- end labels, pushed apart so they never overlap ---------------------
    if end_labels:
        labels_to_place.sort()
        placed: list[float] = []
        for y, i in labels_to_place:
            target = y + 4
            if placed and target - placed[-1] < 16:
                target = placed[-1] + 16
            placed.append(target)
            label = series[i].label
            available = int((label_room - 18) / 6.2)
            if len(label) > available:
                label = label[: max(available - 1, 4)].rstrip() + "…"
            parts.append(text(plot_x1 + 10, target, label, size=11.5, fill=SERIES[i % len(SERIES)]))

    note_svg, bottom = notes(meta, plot_bottom + 42)
    return document("".join(parts) + note_svg, bottom + 16, meta.title)


def _x_ticks(raw_x, temporal: bool, monthly: bool) -> list[tuple[float, str]]:
    if not temporal:
        cats = list(dict.fromkeys(str(x) for x in raw_x))
        n = len(cats)
        step = max(1, math.ceil(n / 8))
        return [(float(i), cats[i]) for i in range(0, n, step)]

    ordinals = [_to_ordinal(x) for x in raw_x]
    d0, d1 = min(ordinals), max(ordinals)  # type: ignore[type-var]
    years = list(range(int(d0) // 12, int(d1) // 12 + 1))
    target = 7 if monthly else 9
    step = max(1, math.ceil(len(years) / target))
    out: list[tuple[float, str]] = []
    for year in years:
        ordinal = year * 12
        if year % step == 0 and d0 <= ordinal <= d1:
            out.append((float(ordinal), str(year)))
    return out
