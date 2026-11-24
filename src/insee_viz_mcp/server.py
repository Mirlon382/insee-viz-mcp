"""FastMCP server: three standardised Insee figures + the routing guide.

The LLM never draws anything itself. It profiles the data, is told which of
the three Insee figure forms applies, then fills a typed contract whose
required fields are exactly the ones Insee never omits (title, source, unit).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from importlib import resources
from pathlib import Path
from typing import Literal

from fastmcp import Context, FastMCP
from fastmcp.apps import UI_EXTENSION_ID, AppConfig, ResourceCSP
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult
from mcp.types import TextContent
from pydantic import BaseModel, Field, ValidationError

from . import geo
from .charts import render_bars as _render_bars
from .charts import render_line as _render_line
from .charts import render_map as _render_map
from .models import BarRow, BarSpec, FigureMeta, LineSpec, MapRow, MapSpec, Series
from .style import fr_num, slugify

VIEW_URI = "ui://insee-viz/view.html"
GUIDE_URI = "insee://doctrine/figures"
OUT_DIR = Path(os.environ.get("INSEE_VIZ_OUT", Path.home() / ".cache" / "insee-viz"))

mcp = FastMCP(
    "Insee figures",
    instructions=(
        "Any chart must be produced by this server, never drawn by hand. "
        "Workflow: (1) call recommend_chart with the columns you have; "
        "(2) call the render tool it names; (3) fill meta.title, meta.source and "
        "meta.unit, and preferably meta.lecture and meta.champ; (4) answer with the "
        "figure and its Lecture / Champ / Source block, quoting only values present "
        "in the data. The full doctrine is at " + GUIDE_URI + "."
    ),
)


# --------------------------------------------------------------------------- #
# Shared plumbing
# --------------------------------------------------------------------------- #
class ColumnProfile(BaseModel):
    name: str = Field(..., description="Column name as it appears in the data.")
    kind: Literal["numeric", "date", "geography", "category", "text"] = Field(
        ..., description="Role of the column: numeric measure, date/period, official geographic code, category, free text."
    )
    distinct: int | None = Field(None, description="Number of distinct values, when known.")
    example: str | None = Field(None, description="One example value, e.g. '2023-01' or '75'.")


def _warnings(meta: FigureMeta) -> list[str]:
    out: list[str] = []
    if not meta.unit:
        out.append("meta.unit is missing: Insee prints the unit under the title ('en %', 'en minutes', 'indice base 100 en 2010').")
    if not meta.lecture:
        out.append("meta.lecture is missing: add one factual sentence with a value, e.g. 'En 2025, les habitants ... mettent en moyenne 8,1 minutes ...'.")
    if not meta.champ:
        out.append("meta.champ is missing: state the geographic field and population, e.g. 'France hors Mayotte, communes.'.")
    return out


def _publish(svg: str, meta: FigureMeta, kind: str) -> tuple[dict[str, str], str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(meta.title, 70)
    svg_path = OUT_DIR / f"{slug}.svg"
    svg_path.write_text(svg, encoding="utf-8")
    files = {"svg": str(svg_path)}
    png_path = OUT_DIR / f"{slug}.png"
    converter = shutil.which("rsvg-convert")
    if converter:
        try:
            subprocess.run(
                [converter, "-w", "1840", "-o", str(png_path), str(svg_path)],
                check=True, timeout=30, capture_output=True,
            )
            files["png"] = str(png_path)
        except (subprocess.SubprocessError, OSError):
            pass
    elif shutil.which("magick"):
        try:
            subprocess.run(["magick", str(svg_path), "-density", "192", str(png_path)], check=True, timeout=30, capture_output=True)
            files["png"] = str(png_path)
        except (subprocess.SubprocessError, OSError):
            pass
    return files, slug


def _supports_app(ctx: Context | None) -> bool:
    """True when the host rendered an MCP App, so the SVG belongs in the payload."""
    if ctx is None:
        return False
    try:
        return bool(ctx.client_supports_extension(UI_EXTENSION_ID))
    except Exception:
        return False


def _result(
    *,
    kind: str,
    svg: str,
    meta: FigureMeta,
    table: dict,
    files: dict[str, str],
    slug: str,
    warnings: list[str],
    summary: str,
) -> ToolResult:
    payload = {
        "kind": kind,
        "svg": svg,
        "has_inline_svg": bool(svg),
        "slug": slug,
        "title": meta.title,
        "subtitle": meta.unit,
        "declaration": f"Figure {meta.number} – {meta.title}" if meta.number else meta.title,
        "notes": {"lecture": meta.lecture, "champ": meta.champ, "source": meta.source, "note": meta.note},
        "table": table,
        "files": files,
        "warnings": warnings,
    }
    lines = [summary, "Files: " + " | ".join(f"{k.upper()} {v}" for k, v in files.items())]
    if warnings:
        lines.append("Warnings: " + " ".join(warnings))
    lines.append("Answer with the figure, its title/unit and the Lecture / Champ / Source block; quote only values present in the data.")
    return ToolResult(
        content=[TextContent(type="text", text="\n".join(lines))],
        structured_content=payload,
    )


def _validation_error(exc: ValidationError) -> ToolError:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        parts.append(f"{loc}: {err['msg']}")
    return ToolError("Invalid figure contract — " + "; ".join(parts))


# --------------------------------------------------------------------------- #
# The guide: which Insee figure for which data
# --------------------------------------------------------------------------- #
@mcp.tool()
def recommend_chart(columns: list[ColumnProfile], row_count: int, goal: str | None = None) -> str:
    """Choose the Insee figure form for a dataset before rendering it.

    Call this first with one entry per column. It returns the figure type, the
    tool to call, the parameter contract and the pitfalls, so the same data is
    always shown the same way.

    Args:
        columns: Profile of each column (name + role + optional cardinality/example).
        row_count: Number of rows in the dataset.
        goal: Optional sentence about what the figure must show.
    """
    geo_cols = [c for c in columns if c.kind == "geography"]
    date_cols = [c for c in columns if c.kind == "date"]
    cat_cols = [c for c in columns if c.kind == "category"]
    num_cols = [c for c in columns if c.kind == "numeric"]

    header = f"**{row_count} ligne(s)** — objectif : {goal}" if goal else f"**{row_count} ligne(s)**"
    contract = (
        "\n\nChamps éditoriaux (obligatoires) : `meta.title` (phrase qui énonce le résultat, sans point final), "
        "`meta.source` (producteur + opération + millésime), `meta.unit` ('en %', 'en minutes'…). "
        "Recommandés : `meta.lecture` (une phrase avec une valeur), `meta.champ` (périmètre)."
    )

    if row_count <= 1:
        return (
            f"{header}\n\n**Aucune figure.** Une seule observation se dit dans une phrase, pas dans un graphique."
        )

    if geo_cols:
        geo = geo_cols[0]
        level = "departement"
        example = (geo.example or "").strip()
        if example.isdigit() and len(example) == 2 and int(example) < 100:
            level = "region" if int(example) in {11, 24, 27, 28, 32, 44, 52, 53, 75, 76, 84, 93, 94} and geo.name.lower().startswith("reg") else "departement"
        return (
            f"{header}\n\n**Figure : carte choroplèthe** → `render_map` (level='{level}')\n\n"
            f"Pourquoi : la colonne `{geo.name}` porte un code géographique officiel. Insee montre ce type de données par carte, "
            "pas par barres ni par courbe, et la carte se lit en taux, densité, part ou évolution — jamais en effectif brut.\n\n"
            "Contrat : `rows=[{code, value, name?}]` (codes officiels : '75', '2A', '971' ; value=null → gris « non disponible »), "
            "`classes=5`, `method='quantile'`.\n"
            "Contrôles : une valeur par territoire, même millésime, unité normalisée (hab./km², %, euros par habitant)."
            + contract
        )

    if date_cols and num_cols:
        return (
            f"{header}\n\n**Figure : courbe** → `render_line`\n\n"
            f"Pourquoi : la colonne `{date_cols[0].name}` est temporelle et `{num_cols[0].name}` est l'indicateur. "
            "Une série temporelle se lit en courbe ; l'ordre chronologique est la structure, pas le classement.\n\n"
            "Contrat : `series=[{label, points=[{x: '2023-01'|'2023'|'2023-T1', y}]}]` (1 à 4 séries), `y_zero=true` si l'unité est un niveau "
            "(effectif, euros) et non un indice.\n"
            "Contrôles : périodes ISO, pas de trous silencieux (laisser le point absent plutôt qu'inventer), unité unique."
            + contract
        )

    if cat_cols and num_cols:
        cat = cat_cols[0]
        n = cat.distinct or 0
        orientation = "horizontal"  # Insee ranks categories left-to-right, never vertical by default
        extra = ""
        if goal and re.search(r"camembert|donut|secteur|circulaire|pie", goal, re.I):
            extra += (
                "\n\n**Pas de camembert** : Insee n'en publie pas. Des barres classées montrent les mêmes parts "
                "et se comparent exactement ; garder le cercle uniquement si le client l'exige explicitement.\n"
            )
        if n > 14:
            extra += (
                f"\n\n**Attention** : {n} catégories. Regrouper les plus petites dans « Autres » pour rester ≤ 14 barres ; "
                "sinon la figure devient un tableau."
            )
        return (
            f"{header}\n\n**Figure : barres horizontales classées** → `render_bars` (orientation='{orientation}')\n\n"
            f"Pourquoi : `{cat.name}` est une variable catégorielle et `{num_cols[0].name}` un indicateur. Insee classe les barres par valeur décroissante "
            "et imprime la valeur au bout de chaque barre.\n\n"
            "Contrat : `rows=[{label, value}]`, `sort='desc'`, `highlight` éventuel pour la catégorie à commenter, "
            "`value_suffix` ('%', 'euros') si l'unité tient au bout de la barre. "
            "`orientation='vertical'` seulement pour des libellés courts et ordonnés (tranches d'âge, mois).\n"
            "Contrôles : une seule série (au-delà, `series` sur les lignes pour 2-3 séries groupées), barres partant de zéro."
            + extra
            + contract
        )

    if len(num_cols) >= 2:
        return (
            f"{header}\n\n**Hors périmètre.** Deux variables numériques appellent un nuage de points, que ce prototype ne produit pas. "
            "Renvoyer un tableau trié, ou demander une agrégation (moyenne par catégorie) pour passer en barres."
        )

    return (
        f"{header}\n\n**Aucune figure adaptée.** Les colonnes décrivent du texte ou des catégories sans mesure numérique. "
        "Compter les occurrences pour obtenir un indicateur, puis rappeler `recommend_chart` (barres)."
    )


# --------------------------------------------------------------------------- #
# Renderers
# --------------------------------------------------------------------------- #
@mcp.tool(app=AppConfig(resource_uri=VIEW_URI))
def render_map(
    rows: list[MapRow],
    meta: FigureMeta,
    level: Literal["departement", "region"] = "departement",
    classes: int = 5,
    method: Literal["quantile", "equal"] = "quantile",
    thresholds: list[float] | None = None,
    decimals: int = 0,
    value_suffix: str | None = None,
    ctx: Context | None = None,
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
            rows=rows, meta=meta, level=level, classes=classes, method=method,
            thresholds=thresholds, decimals=decimals, value_suffix=value_suffix,
        )
    except ValidationError as exc:
        raise _validation_error(exc) from exc

    try:
        svg = _render_map(spec)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc

    warnings = _warnings(meta)
    known = set(geo.names(spec.level))
    unknown = sorted({str(r.code).strip().upper() for r in spec.rows} - known)
    if unknown:
        warnings.append(
            "codes absents de la géographie " + spec.level + " : " + ", ".join(unknown[:8])
            + ("…" if len(unknown) > 8 else "") + " (ils ne sont pas dessinés)."
        )
    files, slug = _publish(svg, meta, "map")
    values = [r.value for r in spec.rows if r.value is not None]
    summary = (
        f"Map ready — {len(spec.rows)} territories, {spec.classes} classes, "
        f"values from {fr_num(min(values), spec.decimals)} to {fr_num(max(values), spec.decimals)}."
    )
    table = {
        "columns": ["Code", "Territoire", f"Valeur{f' ({meta.unit})' if meta.unit else ''}"],
        "rows": [[r.code, r.name or "", "" if r.value is None else fr_num(r.value, spec.decimals)] for r in spec.rows],
    }
    return _result(kind="map", svg=svg if _supports_app(ctx) else "", meta=meta, table=table, files=files, slug=slug, warnings=warnings, summary=summary)


@mcp.tool(app=AppConfig(resource_uri=VIEW_URI))
def render_bars(
    rows: list[BarRow],
    meta: FigureMeta,
    orientation: Literal["horizontal", "vertical"] = "horizontal",
    sort: Literal["desc", "asc", "none"] = "desc",
    highlight: str | None = None,
    show_values: bool = True,
    decimals: int = 0,
    value_suffix: str | None = None,
    ctx: Context | None = None,
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
            rows=rows, meta=meta, orientation=orientation, sort=sort, highlight=highlight,
            show_values=show_values, decimals=decimals, value_suffix=value_suffix,
        )
    except ValidationError as exc:
        raise _validation_error(exc) from exc

    labels = list(dict.fromkeys(r.label for r in spec.rows))
    if len(labels) > 14:
        raise ToolError(
            f"{len(labels)} categories: aggregate to the 12 largest plus 'Autres' before drawing; "
            "an Insee bar figure stays readable at a glance."
        )

    svg = _render_bars(spec)
    warnings = _warnings(meta)
    if spec.highlight and spec.highlight not in labels:
        warnings.append(f"highlight '{spec.highlight}' does not match any category label; ignored.")
    files, slug = _publish(svg, meta, "bars")
    values = [r.value for r in spec.rows]
    summary = (
        f"Bars ready — {len(labels)} categories, values from {fr_num(min(values), spec.decimals)} to {fr_num(max(values), spec.decimals)}."
    )
    table = {
        "columns": ["Catégorie", f"Valeur{f' ({meta.unit})' if meta.unit else ''}"],
        "rows": [[r.label, fr_num(r.value, spec.decimals)] for r in spec.rows],
    }
    return _result(kind="bars", svg=svg if _supports_app(ctx) else "", meta=meta, table=table, files=files, slug=slug, warnings=warnings, summary=summary)


@mcp.tool(app=AppConfig(resource_uri=VIEW_URI))
def render_line(
    series: list[Series],
    meta: FigureMeta,
    y_zero: bool = False,
    y_min: float | None = None,
    y_max: float | None = None,
    decimals: int = 1,
    reference: float | None = None,
    reference_label: str | None = None,
    end_labels: bool = True,
    ctx: Context | None = None,
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
            series=series, meta=meta, y_zero=y_zero, y_min=y_min, y_max=y_max,
            decimals=decimals, reference=reference, reference_label=reference_label,
            end_labels=end_labels,
        )
    except ValidationError as exc:
        raise _validation_error(exc) from exc

    svg = _render_line(spec)
    warnings = _warnings(meta)
    if spec.y_zero is False and meta.unit and re.search(r"\b(euros?|emplois?|habitants?)\b", meta.unit, re.I):
        warnings.append("meta.unit describes a level: set y_zero=true so the axis does not exaggerate variations.")

    files, slug = _publish(svg, meta, "line")
    all_y = [p.y for s in spec.series for p in s.points]
    periods = [p.x for s in spec.series for p in s.points]
    summary = (
        f"Line ready — {len(spec.series)} series, {len(periods)} points, "
        f"{min(periods)} to {max(periods)}, values from {fr_num(min(all_y), spec.decimals)} to {fr_num(max(all_y), spec.decimals)}."
    )
    table = {
        "columns": ["Période", *[s.label for s in spec.series]],
        "rows": [[p.x, *[next((fr_num(q.y, spec.decimals) for q in s.points if q.x == p.x), "") for s in spec.series]] for p in spec.series[0].points],
    }
    return _result(kind="line", svg=svg if _supports_app(ctx) else "", meta=meta, table=table, files=files, slug=slug, warnings=warnings, summary=summary)


# --------------------------------------------------------------------------- #
# Doctrine as a resource, plus a ready-made prompt
# --------------------------------------------------------------------------- #
@mcp.resource(GUIDE_URI, mime_type="text/markdown")
def figure_doctrine() -> str:
    """How to choose and fill an Insee figure (routing table, bans, editorial block)."""
    try:
        return resources.files("insee_viz_mcp.data").joinpath("guide.md").read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError):
        return "Guide indisponible dans cette installation."


@mcp.prompt()
def figure_insee(donnees: str, objectif: str = "") -> str:
    """Ask for an Insee figure from a data description."""
    return (
        "Tu produis une figure au standard Insee à partir des données suivantes.\n\n"
        f"Données : {donnees}\n"
        f"Objectif : {objectif or 'décrire la structure des données'}\n\n"
        "1. Appelle `recommend_chart` avec le profil des colonnes.\n"
        "2. Appelle l'outil de rendu indiqué, en remplissant `meta.title` (une phrase qui énonce le résultat), "
        "`meta.source`, `meta.unit`, puis `meta.lecture` et `meta.champ`.\n"
        "3. Réponds avec la figure et son bloc Lecture / Champ / Source. Ne cite que les valeurs présentes dans les données."
    )


@mcp.resource(VIEW_URI, app=AppConfig(csp=ResourceCSP(resource_domains=["https://unpkg.com"])))
def figure_view() -> str:
    """Interactive viewer for the rendered SVG figure (MCP Apps)."""
    try:
        return resources.files("insee_viz_mcp.data").joinpath("view.html").read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError):
        return "<!DOCTYPE html><html><body>Viewer indisponible.</body></html>"


def main() -> None:
    """Console entry point (stdio), used by MCP clients."""
    mcp.run(show_banner=False)


if __name__ == "__main__":
    main()
