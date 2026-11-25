"""The MCP App viewer: figure, data table, SVG download, warnings."""

from fastmcp.apps import AppConfig, ResourceCSP

from .bundled import read_text

FALLBACK = "<!DOCTYPE html><html><body>Viewer indisponible.</body></html>"

# The viewer loads the MCP Apps SDK from a CDN. Declaring the origin in the resource CSP is what
# lets the host's iframe fetch it; a host that does not enforce the CSP ignores this.
VIEWER_APP = AppConfig(csp=ResourceCSP(resource_domains=["https://unpkg.com"]))


def figure_view() -> str:
    """Interactive viewer for the rendered SVG figure (MCP Apps)."""
    return read_text("view.html", fallback=FALLBACK)
