"""The renderers: the SVG a figure must contain, and the inputs they refuse.

These bypass the MCP layer on purpose -- spec in, SVG out -- so a failure points at the drawing
rather than at the transport. The protocol-level tests live in `test_server.py`.
"""

import xml.etree.ElementTree as ET

import pytest
from pydantic import ValidationError

from insee_viz_mcp.charts import render_bars, render_line, render_map
from insee_viz_mcp.models.figures import BarRow, BarSpec, FigureMeta, LineSpec, MapRow, MapSpec, Point, Series
from insee_viz_mcp.style import fr_num, nice_ticks, slugify

META = FigureMeta(
    title="Une densité de population très inégale selon le département",
    unit="nombre d'habitants au km²",
    lecture="En 2022, la densité est de 14,8 habitants par km² en Lozère.",
    champ="France métropolitaine, départements.",
    source="Insee, recensement de la population 2022.",
)


def test_french_number_format():
    assert fr_num(1813800) == "1\u202f813\u202f800"
    assert fr_num(45.8, 1) == "45,8"
    assert fr_num(-2.5, 1) == "-2,5"
    assert fr_num(0.0, 0) == "0"


def test_nice_ticks_cover_domain():
    ticks = nice_ticks(0, 8.1, 6)
    assert ticks[0] <= 0 and ticks[-1] >= 8.1
    assert len(ticks) <= 8


def test_slug_is_ascii():
    assert slugify("La densité de population, en %") == "la-densite-de-population-en"


def test_meta_requires_a_source():
    with pytest.raises(ValidationError):
        FigureMeta(title="Un titre assez long pour être valide", source="")
    meta = FigureMeta(title="Un titre assez long pour être valide.", source="Insee.")
    assert not meta.title.endswith(".")


def _bars_spec(**overrides) -> BarSpec:
    rows = [
        BarRow(label="Grands centres urbains", value=2.3),
        BarRow(label="Petites villes", value=3.4),
        BarRow(label="Rural non périurbain – habitat dispersé", value=8.1),
    ]
    meta = FigureMeta(
        title="L'accès aux services varie de 2,3 à 8,1 minutes",
        unit="en minutes",
        source="Insee, BPE 2025.",
    )
    kwargs = dict(rows=rows, meta=meta, decimals=1, value_suffix="min", highlight="Petites villes")
    kwargs.update(overrides)
    return BarSpec(**kwargs)


def test_bars_render_insee_skeleton():
    svg = render_bars(_bars_spec())
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert "en minutes" in svg
    assert "Source\u202f: Insee, BPE 2025." in svg
    assert "8,1" in svg
    # one bar per category; each bar carries its native tooltip
    assert svg.count("<g><rect") == 3
    assert root.get("viewBox", "").startswith("0 0 920")


def test_bars_reject_more_than_three_series():
    with pytest.raises(ValidationError):
        _bars_spec(
            rows=[
                BarRow(label="A", value=1, series="S1"),
                BarRow(label="A", value=2, series="S2"),
                BarRow(label="A", value=3, series="S3"),
                BarRow(label="A", value=4, series="S4"),
            ]
        )


def test_vertical_bars_render():
    svg = render_bars(_bars_spec(orientation="vertical", sort="none", show_values=True))
    ET.fromstring(svg)
    assert "Grands centres urbains" in svg


def _line_spec(**overrides) -> LineSpec:
    series = [
        Series(label="Indice en euros", points=[Point(x=f"2024-{m:02d}", y=100 + m) for m in range(1, 13)]),
        Series(label="Indice en devises", points=[Point(x=f"2024-{m:02d}", y=95 + m) for m in range(1, 13)]),
    ]
    meta = FigureMeta(
        title="Les prix en euros des matières premières importées augmentent",
        unit="indice base 100 en 2010",
        source="Insee, prix des matières premières importées, octobre 2026.",
    )
    kwargs = dict(series=series, meta=meta, decimals=0)
    kwargs.update(overrides)
    return LineSpec(**kwargs)


def test_line_render_skeleton():
    svg = render_line(_line_spec())
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert svg.count("<path") == 2  # one polyline per series
    assert "Indice en euros" in svg
    # months are time-proportional: the axis starts and ends on year boundaries
    assert "2024" in svg


def test_line_breaks_on_missing_period():
    spec = _line_spec()
    # drop three months in the middle: the line must be cut, not interpolated
    spec.series[0].points = [
        point for point in spec.series[0].points if point.x not in {"2024-05", "2024-06", "2024-07"}
    ]
    svg = render_line(spec)
    assert svg.count("<path") == 3


def test_line_reference_line():
    svg = render_line(_line_spec(reference=106, reference_label="Moyenne"))
    assert "Moyenne" in svg
    assert 'stroke-dasharray="5 4"' in svg


def _map_spec(**overrides) -> MapSpec:
    rows = [MapRow(code=f"{i:02d}", value=i * 3.0) for i in range(1, 20)]
    rows.append(MapRow(code="2A", value=None))
    meta = FigureMeta(
        title="Une densité de population inégale selon le département",
        unit="nombre d'habitants au km²",
        source="Insee, recensement de la population 2022.",
        champ="France métropolitaine.",
    )
    kwargs = dict(rows=rows, meta=meta, classes=5, thresholds=[10, 20, 30, 40], decimals=0, level="departement")
    kwargs.update(overrides)
    return MapSpec(**kwargs)


def test_map_renders_all_departments_and_legend():
    svg = render_map(_map_spec())
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert svg.count('<path d="M') >= 90  # every department is drawn
    assert "Moins de 10" in svg
    assert "40 et plus" in svg
    assert "non disponible" in svg
    assert "Source" in svg


def test_map_unknown_code_is_simply_absent():
    svg = render_map(_map_spec(rows=[MapRow(code="99", value=1.0)]))
    assert "non disponible" in svg  # every real department has no value


def test_map_threshold_count_must_match_classes():
    with pytest.raises(ValueError):
        render_map(_map_spec(thresholds=[10, 20]))
