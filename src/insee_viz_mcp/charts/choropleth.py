"""Choropleth in Insee house style: quantile classes, sequential blues,
horizontal swatch legend, no data in grey."""

from __future__ import annotations

from .. import geo
from ..models.figures import MapSpec
from ..style import BLUE_CLASSES, MARGIN, MUTED, NO_DATA, WIDTH, fr_num
from ..svgkit import document, header, notes, rect, text

MAP_H = 610.0


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = q * (len(ordered) - 1)
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def class_breaks(spec: MapSpec, values: list[float]) -> list[float]:
    if spec.thresholds:
        if len(spec.thresholds) != spec.classes - 1:
            raise ValueError(f"thresholds must contain {spec.classes - 1} bounds for {spec.classes} classes")
        return sorted(spec.thresholds)
    if spec.method == "quantile":
        return [_quantile(values, i / spec.classes) for i in range(1, spec.classes)]
    lo, hi = min(values), max(values)
    step = (hi - lo) / spec.classes
    return [lo + step * i for i in range(1, spec.classes)]


def _palette(n: int) -> list[str]:
    if n == 5:
        return BLUE_CLASSES
    if n < 5:
        idx = [round(i * (len(BLUE_CLASSES) - 1) / (n - 1)) for i in range(n)]
        return [BLUE_CLASSES[i] for i in idx]
    # more classes than the base ramp: interpolate a darker tail
    out = list(BLUE_CLASSES)
    while len(out) < n:
        out.insert(len(out) - 1, "#0E3A6B")
    return out[:n]


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def _mix(a: str, b: str, t: float) -> str:
    ra, rb = _hex_to_rgb(a), _hex_to_rgb(b)
    return _rgb_to_hex(tuple(round(ra[i] + (rb[i] - ra[i]) * t) for i in range(3)))  # type: ignore[arg-type]


def render_map(spec: MapSpec) -> str:
    meta = spec.meta
    codes = {str(r.code).strip().upper(): r for r in spec.rows}
    all_paths = geo.paths(spec.level)
    values = [float(r.value) for r in spec.rows if r.value is not None]
    if not values:
        raise ValueError("no numeric values to map")
    breaks = class_breaks(spec, values)
    palette = _palette(spec.classes)

    def class_of(value: float) -> int:
        for i, bound in enumerate(breaks):
            if value <= bound:
                return i
        return len(breaks)

    head = header(meta)
    parts: list[str] = list(head.parts)
    top = head.height + 4

    # -- project to fit the map area ---------------------------------------
    x0, y0, x1, y1 = geo.bounds(spec.level)
    avail_w = WIDTH - 2 * MARGIN
    scale = min(avail_w / (x1 - x0), MAP_H / (y1 - y0))
    map_w, map_h = (x1 - x0) * scale, (y1 - y0) * scale
    offset_x = MARGIN + (avail_w - map_w) / 2
    offset_y = top

    def project(point: tuple[float, float]) -> tuple[float, float]:
        px, py = point
        return offset_x + (px - x0) * scale, offset_y + (y1 - py) * scale

    for code, polygons in all_paths:
        row = codes.get(code.upper())
        fill = NO_DATA
        label = f"{geo.names(spec.level).get(code, code)} : non disponible"
        if row is not None and row.value is not None:
            fill = palette[class_of(float(row.value))]
            label = f"{row.name or geo.names(spec.level).get(code, code)} : {fr_num(float(row.value), spec.decimals)}{spec.value_suffix or ''}"
        d_parts: list[str] = []
        for polygon in polygons:
            for ring in polygon:
                pts = [project(pt) for pt in ring]
                if len(pts) < 3:
                    continue
                d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}" + "".join(f"L{x:.1f},{y:.1f}" for x, y in pts[1:]) + "Z"
                d_parts.append(d)
        if d_parts:
            parts.append(
                f'<g><path d="{" ".join(d_parts)}" fill="{fill}" stroke="#FFFFFF" stroke-width="0.7"><title>{label}</title></path></g>'
            )

    # codes the LLM supplied that this geography does not know
    known = {code.upper() for code, _ in all_paths}
    unmatched = [c for c in codes if c not in known]

    # -- legend: one label per class, as Insee prints its cartographic ramps --
    legend_y = offset_y + map_h + 24
    swatch_h = 13.0
    swatch_w = (WIDTH - 2 * MARGIN) / spec.classes
    for i, color in enumerate(palette):
        parts.append(rect(MARGIN + i * swatch_w + 1, legend_y, swatch_w - 2, swatch_h, color))
    for i, label in enumerate(_class_labels(breaks, spec)):
        for j, chunk in enumerate(_wrap_label(label, 22)):
            parts.append(
                text(
                    MARGIN + i * swatch_w + swatch_w / 2,
                    legend_y + swatch_h + 14 + j * 12,
                    chunk,
                    size=10,
                    fill=MUTED,
                    anchor="middle",
                )
            )
    if spec.thresholds:
        method_note = "Seuils fixes"
    else:
        method_note = "Classes calculées par quantiles" if spec.method == "quantile" else "Classes à intervalles égaux"
    parts.append(text(MARGIN, legend_y + swatch_h + 42, method_note, size=10, fill=MUTED))
    if any(r.value is None for r in spec.rows) or unmatched:
        lx = MARGIN + spec.classes * swatch_w + 26
        parts.append(rect(lx, legend_y, 16, swatch_h, NO_DATA))
        parts.append(text(lx + 22, legend_y + 11, "non disponible", size=10.5, fill=MUTED))

    note_svg, bottom = notes(meta, legend_y + swatch_h + 66)
    height = bottom + 16
    return document("".join(parts) + note_svg, height, meta.title)


def _class_labels(breaks: list[float], spec: MapSpec) -> list[str]:
    """Human-readable ranges, Insee phrasing: 'Moins de 50', 'De 50 à moins de 75'."""

    def num(value: float) -> str:
        return fr_num(value, spec.decimals)

    labels = [f"Moins de {num(breaks[0])}"]
    for low, high in zip(breaks, breaks[1:], strict=False):
        labels.append(f"De {num(low)} à moins de {num(high)}")
    labels.append(f"{num(breaks[-1])} et plus")
    return labels


def _wrap_label(label: str, width: int) -> list[str]:
    words = label.split()
    if len(label) <= width:
        return [label]
    mid = len(words) // 2
    return [" ".join(words[:mid]), " ".join(words[mid:])]
