"""Resource registration entrypoint.

The only place that knows about the MCP server's resources, so a resource becomes visible -- and
stays invisible -- in exactly one list. Two are published:

- `insee://doctrine/figures` -- the doctrine the model reads before filling a figure.
- `ui://insee-viz/view.html` -- the MCP App viewer that renders the structured content every
  render tool returns.
"""

from fastmcp import FastMCP

from .doctrine import figure_doctrine
from .uris import GUIDE_URI, VIEW_URI
from .viewer import VIEWER_APP, figure_view


def register_resources(mcp: FastMCP) -> None:
    """Register every resource the server exposes."""
    mcp.resource(GUIDE_URI, mime_type="text/markdown")(figure_doctrine)
    mcp.resource(VIEW_URI, app=VIEWER_APP)(figure_view)
