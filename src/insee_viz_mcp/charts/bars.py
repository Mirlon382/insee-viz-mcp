"""Bar chart in Insee house style.

Single series: one blue, optional emphasis on one category, value labels at
the bar ends. Grouped (2-3 series): side-by-side bars, legend under the
title, no value labels (reading is done on the axis, as in Insee Première).
"""

from __future__ import annotations

from ..models import BarSpec
from ..style import (
    AXIS,
    BAR_MAIN,
    BAR_SOFT,
    GRID,
    MARGIN,
    MUTED,
    NBSP_NARROW,
    SERIES,
    WIDTH,
    esc,
    axis_num,
    fr_num,
    nice_ticks,
    wrap,
)
from ..svgkit import baseline, document, header, line, notes, rect, text

ROW_H = 30.0
GROUP_BAR_H = 15.0
GROUP_GAP = 3.0
VERTICAL_PLOT_H = 210.0


class Scale:
    """Maps a data domain onto pixels (linear)."""

    def __init__(self, dmin: float, dmax: float, pmin: float, pmax: float):
        self.dmin, self.dmax, self.pmin, self.pmax = dmin, dmax, pmin, pmax

    def __call__(self, value: float) -> float:
        if self.dmax == self.dmin:
            return self.pmin
        ratio = (value - self.dmin) / (self.dmax - self.dmin)
        return self.pmin + ratio * (self.pmax - self.pmin)


def _value_label(spec: BarSpec, value: float) -> str:
    body = fr_num(value, spec.decimals)
    return f"{body}{NBSP_NARROW}{spec.value_suffix}" if spec.value_suffix else body


def _series_names(rows) -> list[str]:
    return list(dict.fromkeys(r.series for r in rows if r.series))


def render_bars(spec: BarSpec) -> str:
    meta = spec.meta
    rows = list(spec.rows)
    names = _series_names(rows)
    grouped = bool(names)
    labels = list(dict.fromkeys(r.label for r in rows))

    if spec.sort != "none":
        totals = {lab: sum(r.value for r in rows if r.label == lab) for lab in labels}
        labels.sort(key=lambda lab: totals[lab], reverse=(spec.sort == "desc"))

    wrapped = {lab: wrap(lab, 40)[:2] for lab in labels}
    max_lines = max(len(v) for v in wrapped.values())

    head = header(meta)
    parts: list[str] = list(head.parts)
    top = head.height

    if grouped:
        cursor = MARGIN
        for i, name in enumerate(names):
            parts.append(rect(cursor, top - 8, 10, 10, SERIES[i % len(SERIES)]))
            parts.append(text(cursor + 16, top + 1, name, size=11.5))
            cursor += 16 + len(name) * 6.3 + 18
        top += 24

    values = [r.value for r in rows]
    data_lo = min(0.0, min(values))
    data_hi = max(0.0, max(values))
    if data_hi == data_lo:
        data_hi = data_lo + 1.0
    ticks = nice_ticks(data_lo, data_hi, 6)
    domain_lo, domain_hi = ticks[0], ticks[-1]

    if spec.orientation == "horizontal":
        label_col = min(max(90.0, max((max((len(x) for x in v), default=0) for v in wrapped.values()), default=8) * 6.9), 330.0)
        if max_lines > 1:
            label_col += 10
        label_values = [_value_label(spec, v) for v in values] if spec.show_values and not grouped else []
        value_space = (max((len(v) for v in label_values), default=0) * 6.4 + 14)
        plot_x0 = MARGIN + label_col + 14
        plot_x1 = WIDTH - MARGIN - value_space
        sx = Scale(domain_lo, domain_hi, plot_x0, plot_x1)

        row_h = max(ROW_H, 34.0 if max_lines > 1 else ROW_H)
        if grouped:
            row_h = max(row_h, len(names) * (GROUP_BAR_H + GROUP_GAP) + 10)
        plot_top = top + 6
        plot_bottom = plot_top + row_h * len(labels)

        for tick in ticks:
            x = sx(tick)
            parts.append(line(x, plot_top - 6, x, plot_bottom, color=GRID))
            parts.append(text(x, plot_bottom + 17, axis_num(tick, spec.decimals), size=11, fill=MUTED, anchor="middle"))
        parts.append(line(sx(0), plot_top - 6, sx(0), plot_bottom, color=AXIS))

        for i, lab in enumerate(labels):
            cy = plot_top + row_h * i + row_h / 2
            lines = wrapped[lab]
            first_y = cy - (len(lines) - 1) * 7 + 4
            for j, chunk in enumerate(lines):
                parts.append(text(plot_x0 - 14, first_y + j * 14, chunk, size=12, anchor="end"))

            if grouped:
                total_h = len(names) * (GROUP_BAR_H + GROUP_GAP) - GROUP_GAP
                for k, name in enumerate(names):
                    value = next(r.value for r in rows if r.label == lab and r.series == name)
                    y = cy - total_h / 2 + k * (GROUP_BAR_H + GROUP_GAP)
                    parts.append(_bar_geom(min(sx(0), sx(value)), y, abs(sx(value) - sx(0)), GROUP_BAR_H, SERIES[k % len(SERIES)], f"{lab} — {name}", spec, value))
            else:
                value = next(r.value for r in rows if r.label == lab)
                color = BAR_MAIN
                if spec.highlight:
                    color = BAR_MAIN if lab == spec.highlight else BAR_SOFT
                parts.append(_bar_geom(min(sx(0), sx(value)), cy - 9, abs(sx(value) - sx(0)), 18, color, lab, spec, value))
                if spec.show_values:
                    anchor = "start" if value >= 0 else "end"
                    parts.append(text(sx(value) + (6 if value >= 0 else -6), cy + 4, _value_label(spec, value), size=11, anchor=anchor))
        plot_bottom += 10

    else:  # vertical
        plot_x0, plot_x1 = MARGIN, WIDTH - MARGIN
        plot_top = top + 18
        plot_bottom = plot_top + VERTICAL_PLOT_H
        sy = Scale(domain_lo, domain_hi, plot_bottom, plot_top)

        for tick in ticks:
            y = sy(tick)
            parts.append(line(plot_x0, y, plot_x1, y, color=GRID))
            parts.append(text(plot_x0 - 10, y + 4, axis_num(tick, spec.decimals), size=11, fill=MUTED, anchor="end"))
        parts.append(baseline(plot_bottom, plot_x0, plot_x1))
        parts.append(line(plot_x0, sy(0), plot_x1, sy(0), color=AXIS))

        band = (plot_x1 - plot_x0) / max(len(labels), 1)
        bar_w = min(band * 0.55, 64)
        for i, lab in enumerate(labels):
            cx = plot_x0 + band * i + band / 2
            if grouped:
                inner = bar_w / len(names)
                for k, name in enumerate(names):
                    value = next(r.value for r in rows if r.label == lab and r.series == name)
                    x = cx - bar_w / 2 + k * inner
                    parts.append(_bar_geom(x, min(sy(0), sy(value)), inner - 3, abs(sy(value) - sy(0)), SERIES[k % len(SERIES)], f"{lab} — {name}", spec, value))
            else:
                value = next(r.value for r in rows if r.label == lab)
                color = BAR_MAIN if (not spec.highlight or lab == spec.highlight) else BAR_SOFT
                parts.append(_bar_geom(cx - bar_w / 2, min(sy(0), sy(value)), bar_w, abs(sy(value) - sy(0)), color, lab, spec, value))
                if spec.show_values:
                    parts.append(text(cx, sy(value) - 7, _value_label(spec, value), size=11, anchor="middle"))
            for j, chunk in enumerate(wrapped[lab]):
                parts.append(text(cx, plot_bottom + 18 + j * 13, chunk, size=11, fill=MUTED, anchor="middle"))

    note_svg, bottom = notes(meta, plot_bottom + 36)
    return document("".join(parts) + note_svg, bottom + 16, meta.title)


def _bar_geom(x, y, w, h, color, tooltip, spec, value) -> str:
    """A filled bar with a native SVG tooltip."""
    label = esc(tooltip) + " : " + esc(_value_label(spec, value))
    return f"<g>{rect(x, y, max(w, 0.8), max(h, 0.8), color)}<title>{label}</title></g>"
