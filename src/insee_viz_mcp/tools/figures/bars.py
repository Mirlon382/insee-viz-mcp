"""`render_bars`: horizontal ranked bars, the Insee default for a categorical variable.

Two refusals are part of the product rather than the schema: a wall of more than fourteen bars
stops being a figure, and a highlight label that names no category is a caller mistake worth saying
out loud. Neither can be expressed as a pydantic constraint -- the first depends on the labels, the
second on comparing them to another field -- so they live here.
"""

from typing import Literal

from fastmcp.dependencies import Depends
from fastmcp.tools import ToolResult
from pydantic import ValidationError

from ...charts.bars import render_bars as draw_bars
from ...errors import AppToolError, ErrorCode
from ...models.figures import BarRow, BarSpec, FigureMeta
from ...models.results import DataTable, EditorialNotes, FigureView
from ...style import fr_num
from ...utils.apps import app_extension_declared
from ...utils.publish import Publisher, get_publisher
from .common import editorial_warnings, figure_result, rejected_contract

# An Insee bar figure stays readable at a glance; past this, it is a table.
MAX_CATEGORIES = 14


async def render_bars(
    rows: list[BarRow],
    meta: FigureMeta,
    orientation: Literal["horizontal", "vertical"] = "horizontal",
    sort: Literal["desc", "asc", "none"] = "desc",
    highlight: str | None = None,
    show_values: bool = True,
    decimals: int = 0,
    value_suffix: str | None = None,
    publisher: Publisher = Depends(get_publisher),
    inline_app: bool = Depends(app_extension_declared),
) -> ToolResult:
    """Render an Insee-style bar chart for one indicator across categories.

    Horizontal ranked bars are the Insee default. Use `series` on the rows for
    2-3 grouped series (legend, no value labels).

    Args:
        rows: Categories with their value; optional `series` name for grouped bars.
        meta: Editorial metadata; title, source and unit are required for publication.
        orientation: Horizontal (default, ranked) or vertical (short ordered labels only).
        sort: Descending, ascending, or keep the given order (ordered categories).
        highlight: Category label to emphasise; the others go light blue.
        show_values: Print the value at the bar end (single series only).
        decimals: Decimals of the value labels.
        value_suffix: Short suffix for value labels, e.g. '%' or 'euros'.
    """
    try:
        spec = BarSpec(
            rows=rows,
            meta=meta,
            orientation=orientation,
            sort=sort,
            highlight=highlight,
            show_values=show_values,
            decimals=decimals,
            value_suffix=value_suffix,
        )
    except ValidationError as exc:
        raise rejected_contract(exc) from exc

    labels = list(dict.fromkeys(row.label for row in spec.rows))
    if len(labels) > MAX_CATEGORIES:
        raise AppToolError(
            ErrorCode.INVALID_QUERY,
            f"{len(labels)} categories: aggregate to the 12 largest plus 'Autres' before drawing; "
            "an Insee bar figure stays readable at a glance.",
        )

    svg = draw_bars(spec)
    warnings = editorial_warnings(meta)
    if spec.highlight and spec.highlight not in labels:
        warnings.append(f"highlight '{spec.highlight}' does not match any category label; ignored.")
    published = await publisher.publish(svg, meta)

    values = [row.value for row in spec.rows]
    summary = (
        f"Bars ready — {len(labels)} categories, values from "
        f"{fr_num(min(values), spec.decimals)} to {fr_num(max(values), spec.decimals)}."
    )
    view = FigureView(
        kind="bars",
        svg=svg if inline_app else "",
        has_inline_svg=inline_app,
        slug=published.slug,
        title=meta.title,
        subtitle=meta.unit,
        declaration=f"Figure {meta.number} – {meta.title}" if meta.number else meta.title,
        notes=EditorialNotes(lecture=meta.lecture, champ=meta.champ, source=meta.source, note=meta.note),
        table=DataTable(
            columns=["Catégorie", f"Valeur{f' ({meta.unit})' if meta.unit else ''}"],
            rows=[[row.label, fr_num(row.value, spec.decimals)] for row in spec.rows],
        ),
        files=published.files,
        warnings=warnings,
    )
    return figure_result(view, summary)
