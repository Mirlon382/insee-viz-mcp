"""`render_line`: up to four dated series, direct end labels, no false axis drama.

The chart builder already refuses to interpolate a gap and prints a label at the end of each line.
What is left here is the editorial check that a *level* (euros, jobs, inhabitants) must be drawn
from zero: an axis cropped on a level exaggerates a variation that may be a rounding artefact.
"""

import re

from fastmcp.dependencies import Depends
from fastmcp.tools import ToolResult
from pydantic import ValidationError

from ...charts.line import render_line as draw_line
from ...models.figures import FigureMeta, LineSpec, Series
from ...models.results import DataTable, EditorialNotes, FigureView
from ...style import fr_num
from ...utils.apps import app_extension_declared
from ...utils.publish import Publisher, get_publisher
from .common import editorial_warnings, figure_result, rejected_contract

# A unit that names a count rather than an index: the y axis must start at zero.
LEVEL_UNIT = re.compile(r"\b(euros?|emplois?|habitants?)\b", re.IGNORECASE)


async def render_line(
    series: list[Series],
    meta: FigureMeta,
    y_zero: bool = False,
    y_min: float | None = None,
    y_max: float | None = None,
    decimals: int = 1,
    reference: float | None = None,
    reference_label: str | None = None,
    end_labels: bool = True,
    publisher: Publisher = Depends(get_publisher),
    inline_app: bool = Depends(app_extension_declared),
) -> ToolResult:
    """Render an Insee-style line chart for up to four time series.

    Use when the data has an ordered time dimension. Periods are ISO-like:
    '2023' (year), '2023-01' (month), '2023-T1' (quarter).

    Args:
        series: One to four series, each with a label and dated points.
        meta: Editorial metadata; title, source and unit are required for publication.
        y_zero: Force the y axis to start at zero (levels such as counts or euros).
        y_min: Imposed lower bound.
        y_max: Imposed upper bound.
        decimals: Decimals on the y axis and reference line.
        reference: Optional horizontal reference value (average, target).
        reference_label: Label printed on the reference line.
        end_labels: Label each line at its right end instead of a legend.
    """
    try:
        spec = LineSpec(
            series=series,
            meta=meta,
            y_zero=y_zero,
            y_min=y_min,
            y_max=y_max,
            decimals=decimals,
            reference=reference,
            reference_label=reference_label,
            end_labels=end_labels,
        )
    except ValidationError as exc:
        raise rejected_contract(exc) from exc

    svg = draw_line(spec)
    warnings = editorial_warnings(meta)
    if not spec.y_zero and meta.unit and LEVEL_UNIT.search(meta.unit):
        warnings.append("meta.unit describes a level: set y_zero=true so the axis does not exaggerate variations.")
    published = await publisher.publish(svg, meta)

    all_y = [point.y for one in spec.series for point in one.points]
    periods = [point.x for one in spec.series for point in one.points]
    summary = (
        f"Line ready — {len(spec.series)} series, {len(periods)} points, "
        f"{min(periods)} to {max(periods)}, values from {fr_num(min(all_y), spec.decimals)} "
        f"to {fr_num(max(all_y), spec.decimals)}."
    )
    view = FigureView(
        kind="line",
        svg=svg if inline_app else "",
        has_inline_svg=inline_app,
        slug=published.slug,
        title=meta.title,
        subtitle=meta.unit,
        declaration=f"Figure {meta.number} – {meta.title}" if meta.number else meta.title,
        notes=EditorialNotes(lecture=meta.lecture, champ=meta.champ, source=meta.source, note=meta.note),
        table=DataTable(columns=["Période", *[one.label for one in spec.series]], rows=_table_rows(spec)),
        files=published.files,
        warnings=warnings,
    )
    return figure_result(view, summary)


def _table_rows(spec: LineSpec) -> list[list[str]]:
    """One row per period of the first series, every series' value aligned on it (blank when absent)."""
    first = spec.series[0]
    return [
        [
            point.x,
            *[
                next((fr_num(other.y, spec.decimals) for other in one.points if other.x == point.x), "")
                for one in spec.series
            ],
        ]
        for point in first.points
    ]
