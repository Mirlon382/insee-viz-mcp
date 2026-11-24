"""Server-level tests: what an MCP client actually sees."""

import asyncio
import json

from fastmcp import Client
from fastmcp.exceptions import ToolError

from insee_viz_mcp.server import mcp

META = {
    "title": "L'accès aux services varie de 2,3 à 8,1 minutes selon le type de commune",
    "unit": "en minutes",
    "lecture": "En 2025, les habitants des communes rurales dispersées mettent 8,1 minutes.",
    "champ": "France hors Mayotte, communes.",
    "source": "Insee, base permanente des équipements (BPE) 2025.",
}

BARS = {
    "rows": [
        {"label": "Grands centres urbains", "value": 2.3},
        {"label": "Petites villes", "value": 3.4},
        {"label": "Rural non périurbain – habitat dispersé", "value": 8.1},
    ],
    "meta": META,
    "decimals": 1,
    "value_suffix": "min",
}


def run(coro):
    return asyncio.run(coro)


def test_tools_and_app_resource_are_published():
    async def scenario():
        async with Client(mcp) as client:
            listed = await client.list_tools()
            assert "ctx" not in listed[0].input_schema.get("properties", {})
            tools = {t.name for t in listed}
            assert {"recommend_chart", "render_bars", "render_line", "render_map"} <= tools
            resources = [str(r.uri) for r in await client.list_resources()]
            assert "ui://insee-viz/view.html" in resources
            view = await client.read_resource("ui://insee-viz/view.html")
            return view

    view = run(scenario())
    body = view[0].text
    assert "MCP Apps" in body or "ext-apps" in body


def test_render_bars_returns_app_payload():
    async def scenario():
        async with Client(mcp) as client:
            return await client.call_tool("render_bars", BARS)

    result = run(scenario())
    payload = result.structured_content
    assert payload["kind"] == "bars"
    # the Client does not declare the MCP Apps extension, so the SVG is not
    # pushed into the model's context; it is written to disk instead
    assert payload["svg"] == ""
    assert payload["has_inline_svg"] is False
    assert payload["notes"]["source"].startswith("Insee")
    assert payload["files"]["svg"].endswith(".svg")
    assert open(payload["files"]["svg"], encoding="utf-8").read().startswith("<?xml")
    assert payload["table"]["rows"][0][0] == "Grands centres urbains"
    assert "Bars ready" in result.content[0].text


def test_missing_optional_metadata_is_reported_not_blocking():
    async def scenario():
        async with Client(mcp) as client:
            args = json.loads(json.dumps(BARS))
            del args["meta"]["lecture"]
            del args["meta"]["champ"]
            return await client.call_tool("render_bars", args)

    payload = run(scenario()).structured_content
    assert len(payload["warnings"]) == 2
    assert any("lecture" in w for w in payload["warnings"])


def test_too_many_categories_is_refused_with_advice():
    async def scenario():
        async with Client(mcp) as client:
            args = {"meta": META, "rows": [{"label": f"C{i}", "value": i} for i in range(20)]}
            return await client.call_tool("render_bars", args)

    try:
        run(scenario())
    except ToolError as exc:
        assert "aggregate" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ToolError")


def test_recommend_chart_routes_each_shape():
    async def scenario(columns, rows=100):
        async with Client(mcp) as client:
            return await client.call_tool("recommend_chart", {"columns": columns, "row_count": rows})

    geo = run(scenario([{"name": "dep", "kind": "geography", "example": "75"}, {"name": "densite", "kind": "numeric"}]))
    assert "render_map" in geo.content[0].text

    time = run(scenario([{"name": "periode", "kind": "date", "example": "2024-01"}, {"name": "prix", "kind": "numeric"}]))
    assert "render_line" in time.content[0].text

    cat = run(scenario([{"name": "secteur", "kind": "category", "distinct": 4}, {"name": "emploi", "kind": "numeric"}]))
    assert "render_bars" in cat.content[0].text

    single = run(scenario([{"name": "valeur", "kind": "numeric"}], rows=1))
    assert "Aucune figure" in single.content[0].text

    two_num = run(scenario([{"name": "a", "kind": "numeric"}, {"name": "b", "kind": "numeric"}]))
    assert "nuage de points" in two_num.content[0].text


def test_doctrine_resource_is_readable():
    async def scenario():
        async with Client(mcp) as client:
            return await client.read_resource("insee://doctrine/figures")

    body = run(scenario())[0].text
    assert "render_map" in body and "Lecture" in body
