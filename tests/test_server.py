"""End to end over the real protocol: what the server publishes, and how it answers.

A test that called `render_bars` directly would prove the renderer works and nothing about the MCP
surface: not the registration, not the schema, not the error contract. These go through
`fastmcp.Client`, which is what a model-facing host does.
"""

import json
from pathlib import Path

from fastmcp import Client
from support import BARS, LINE, MAP, META

from insee_viz_mcp.resources.uris import GUIDE_URI, VIEW_URI


async def test_the_four_tools_are_registered_with_their_schemas(server):
    async with Client(server) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    # Subset, not equality: adding a figure form must not turn this test red.
    assert {"recommend_chart", "render_bars", "render_line", "render_map"} <= set(tools)
    # A Depends parameter never reaches the input schema: the model only sees real arguments.
    assert list(tools["render_bars"].input_schema["properties"]) == [
        "rows",
        "meta",
        "orientation",
        "sort",
        "highlight",
        "show_values",
        "decimals",
        "value_suffix",
    ]
    for tool in tools.values():
        assert tool.description  # the docstring is the description the model reads


async def test_every_tool_is_annotated_read_only(server):
    async with Client(server) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    for tool in tools.values():
        assert tool.annotations.read_only_hint is True, tool.name
        assert tool.annotations.destructive_hint is False, tool.name


async def test_the_app_viewer_and_the_doctrine_are_published(server):
    async with Client(server) as client:
        resources = {str(resource.uri) for resource in await client.list_resources()}
        view = await client.read_resource(VIEW_URI)
        doctrine = await client.read_resource(GUIDE_URI)

    assert {VIEW_URI, GUIDE_URI} <= resources
    assert "MCP Apps" in view[0].text or "ext-apps" in view[0].text
    assert "render_map" in doctrine[0].text and "Lecture" in doctrine[0].text


async def test_the_workflow_prompt_is_published(server):
    async with Client(server) as client:
        prompts = {prompt.name for prompt in await client.list_prompts()}
        rendered = await client.get_prompt("figure_insee", {"donnees": "densite par departement"})

    assert "figure_insee" in prompts
    assert "recommend_chart" in rendered.messages[0].content.text


async def test_render_bars_returns_the_app_payload(server):
    async with Client(server) as client:
        result = await client.call_tool("render_bars", BARS)

    payload = result.structured_content
    assert payload["kind"] == "bars"
    # The Client does not declare the MCP Apps extension, so the SVG is not pushed into the
    # model's context; it is written to disk instead.
    assert payload["svg"] == ""
    assert payload["has_inline_svg"] is False
    assert payload["notes"]["source"].startswith("Insee")
    assert payload["files"]["svg"].endswith(".svg")
    assert Path(payload["files"]["svg"]).read_text(encoding="utf-8").startswith("<?xml")
    assert payload["table"]["rows"][0][0] == "Grands centres urbains"
    assert "Bars ready" in result.content[0].text


async def test_render_map_reports_codes_the_geometry_does_not_know(server):
    async with Client(server) as client:
        result = await client.call_tool("render_map", MAP)

    payload = result.structured_content
    assert payload["kind"] == "map"
    assert any("99" in warning for warning in payload["warnings"])
    assert "Map ready" in result.content[0].text


async def test_render_line_warns_when_a_level_is_drawn_from_a_cropped_axis(server):
    async with Client(server) as client:
        result = await client.call_tool(
            "render_line",
            {**LINE, "meta": {**LINE["meta"], "unit": "milliers d'euros par habitant"}},
        )

    payload = result.structured_content
    assert any("y_zero" in warning for warning in payload["warnings"])
    assert "Line ready" in result.content[0].text


async def test_missing_optional_metadata_is_reported_not_blocking(server):
    async with Client(server) as client:
        args = json.loads(json.dumps(BARS))
        del args["meta"]["lecture"]
        del args["meta"]["champ"]
        result = await client.call_tool("render_bars", args)

    assert result.is_error is False
    assert len(result.structured_content["warnings"]) == 2
    assert any("lecture" in warning for warning in result.structured_content["warnings"])


async def test_too_many_categories_is_refused_with_advice(server):
    async with Client(server) as client:
        args = {"meta": META, "rows": [{"label": f"C{i}", "value": i} for i in range(20)]}
        result = await client.call_tool("render_bars", args, raise_on_error=False)

    assert result.is_error
    text = result.content[0].text
    assert "INVALID_QUERY" in text
    assert "aggregate" in text


async def test_a_broken_contract_names_the_field_to_fix(server):
    # An empty `source` is caught by the tool's own schema, before our code runs: the message is
    # FastMCP's, and it still names the field (see the skill: do not re-check what the schema says).
    async with Client(server) as client:
        args = {**BARS, "meta": {**META, "source": ""}}
        result = await client.call_tool("render_bars", args, raise_on_error=False)

    assert result.is_error
    assert "meta.source" in result.content[0].text


async def test_a_contract_the_schema_cannot_express_is_refused_with_a_code(server):
    # `rows: list[BarRow]` has no length bound in the tool schema -- the bound lives in `BarSpec`,
    # so this is the path our own `AppToolError` has to carry.
    async with Client(server) as client:
        result = await client.call_tool("render_bars", {"meta": META, "rows": []}, raise_on_error=False)

    assert result.is_error
    text = result.content[0].text
    assert "INVALID_INPUT" in text
    assert "`rows`" in text


async def test_recommend_chart_routes_each_shape(server):
    async def ask(columns, rows=100):
        async with Client(server) as client:
            return await client.call_tool("recommend_chart", {"columns": columns, "row_count": rows})

    geo = await ask([{"name": "dep", "kind": "geography", "example": "75"}, {"name": "densite", "kind": "numeric"}])
    assert "render_map" in geo.content[0].text

    time = await ask([{"name": "periode", "kind": "date", "example": "2024-01"}, {"name": "prix", "kind": "numeric"}])
    assert "render_line" in time.content[0].text

    category = await ask(
        [{"name": "secteur", "kind": "category", "distinct": 4}, {"name": "emploi", "kind": "numeric"}]
    )
    assert "render_bars" in category.content[0].text

    single = await ask([{"name": "valeur", "kind": "numeric"}], rows=1)
    assert "Aucune figure" in single.content[0].text

    two_numeric = await ask([{"name": "a", "kind": "numeric"}, {"name": "b", "kind": "numeric"}])
    assert "nuage de points" in two_numeric.content[0].text
