"""`render_map`: one indicator per official geographic code.

A map is the form Insee uses whenever a column carries an official territory code, and it is read
in a rate, a density, a share or an evolution -- never a raw count. The tool does not try to enforce
that: it renders what the caller validated, and the routing tool carries the rule that keeps them
away from counts in the first place.
"""

from typing import Literal

from fastmcp.dependencies import Depends
from fastmcp.tools import ToolResult
from pydantic import ValidationError

from ... import geo
from ...charts.choropleth import render_map as draw_map
from ...models.figures import FigureMeta, MapRow, MapSpec
from ...models.results import DataTable, EditorialNotes, FigureView
from ...style import fr_num
from ...utils.apps import app_extension_declared
from ...utils.publish import Publisher, get_publisher
from .common import editorial_warnings, figure_result, refused_figure, rejected_contract


async def render_map(
    rows: list[MapRow],
    meta: FigureMeta,
    level: Literal["departement", "region"] = "departement",
    classes: int = 5,
    method: Literal["quantile", "equal"] = "quantile",
    thresholds: list[float] | None = None,
    decimals: int = 0,
    value_suffix: str | None = None,
    publisher: Publisher = Depends(get_publisher),
    inline_app: bool = Depends(app_extension_declared),
) -> ToolResult:
    """Render a choropleth map of France (departments or regions), Insee style.

    Use for one indicator per official geographic code. Map a rate, a density,
    a share or an evolution — never a raw count.

    Args:
        rows: One row per territory; code is the official code ('75', '2A', '971'), value null when unavailable.
        meta: Editorial metadata; title, source and unit are what makes the figure publishable.
        level: Geographic level of the codes.
        classes: Number of colour classes (Insee uses 4 to 6).
        method: Quantile classes (default) or equal intervals.
        thresholds: Explicit class bounds instead of `method` (length classes-1).
        decimals: Decimals shown in the legend.
        value_suffix: Suffix appended to legend values, e.g. '%' or ' hab./km²'.
    """
    try:
        spec = MapSpec(
            rows=rows,
            meta=meta,
            level=level,
            classes=classes,
            method=method,
            thresholds=thresholds,
            decimals=decimals,
            value_suffix=value_suffix,
        )
    except ValidationError as exc:
        raise rejected_contract(exc) from exc

    try:
        svg = draw_map(spec)
    except ValueError as exc:
        raise refused_figure(exc) from exc

    warnings = editorial_warnings(meta)
    warnings.extend(_unknown_codes(spec))
    published = await publisher.publish(svg, meta)

    values = [row.value for row in spec.rows if row.value is not None]
    summary = (
        f"Map ready — {len(spec.rows)} territories, {spec.classes} classes, "
        f"values from {fr_num(min(values), spec.decimals)} to {fr_num(max(values), spec.decimals)}."
    )
    view = FigureView(
        kind="map",
        svg=svg if inline_app else "",
        has_inline_svg=inline_app,
        slug=published.slug,
        title=meta.title,
        subtitle=meta.unit,
        declaration=f"Figure {meta.number} – {meta.title}" if meta.number else meta.title,
        notes=EditorialNotes(lecture=meta.lecture, champ=meta.champ, source=meta.source, note=meta.note),
        table=DataTable(
            columns=["Code", "Territoire", f"Valeur{f' ({meta.unit})' if meta.unit else ''}"],
            rows=[
                [row.code, row.name or "", "" if row.value is None else fr_num(row.value, spec.decimals)]
                for row in spec.rows
            ],
        ),
        files=published.files,
        warnings=warnings,
    )
    return figure_result(view, summary)


def _unknown_codes(spec: MapSpec) -> list[str]:
    """Codes the bundled geometry does not know: reported, never fatal (they are simply not drawn)."""
    known = set(geo.names(spec.level))
    unknown = sorted({str(row.code).strip().upper() for row in spec.rows} - known)
    if not unknown:
        return []
    shown = ", ".join(unknown[:8]) + ("…" if len(unknown) > 8 else "")
    return [f"codes absents de la géographie {spec.level} : {shown} (ils ne sont pas dessinés)."]
