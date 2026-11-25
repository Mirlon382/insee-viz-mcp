"""Tool registration entrypoint.

The only place that knows about the MCP server. Every tool is a plain function in its own package,
so a tool becomes visible -- and stays invisible -- in exactly one list.

Annotations travel with the registration, not the function. All four tools are `READ_ONLY`: they
answer from the arguments, change nothing the caller owns, and the same call always yields the same
figure. Writing the SVG to the output directory is a cache, not state a client has to reason about.

The three render tools also carry `app=`, which is what makes the MCP App viewer eligible to render
their `structuredContent`. Registration is where that pairing belongs: the function returns a
payload, the server decides which client sees it.
"""

from fastmcp import FastMCP
from fastmcp.apps import AppConfig
from mcp.types import ToolAnnotations

from ..resources.uris import VIEW_URI
from ..settings import Settings
from .figures import render_bars, render_line, render_map
from .guidance.tools import recommend_chart

# Read-only: the tool answers a question and changes nothing, so a client may call it freely.
READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    openWorldHint=False,
    idempotentHint=True,
)


def register_tools(mcp: FastMCP, settings: Settings) -> None:
    """Register every tool the server exposes.

    `settings` is here so a figure form can be switched off by configuration later on; register a
    tool only when its flag is on. An unregistered tool is the one kind of "disabled" the protocol
    guarantees, unlike tag or visibility filtering, which a later call can undo.
    """

    mcp.tool(recommend_chart, annotations=READ_ONLY)
    mcp.tool(render_map, annotations=READ_ONLY, app=AppConfig(resource_uri=VIEW_URI))
    mcp.tool(render_bars, annotations=READ_ONLY, app=AppConfig(resource_uri=VIEW_URI))
    mcp.tool(render_line, annotations=READ_ONLY, app=AppConfig(resource_uri=VIEW_URI))
