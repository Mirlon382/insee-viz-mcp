"""Shim so `fastmcp run server.py:mcp` works from the project root."""

from insee_viz_mcp.server import mcp

if __name__ == "__main__":
    mcp.run()
