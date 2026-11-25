"""Shared test scaffolding.

Every test talks to a real FastMCP app over the real protocol (`fastmcp.Client`); what is replaced
is the outside world, never the server. Two seams:

- `settings` points the output directory at `tmp_path`, so a render never touches `~/.cache`.
- `server` builds the same application `insee_viz_mcp.server` builds, with a rasteriser pinned to
  `None`: PNG conversion is a subprocess, and a suite must not depend on what is on PATH.
"""

from pathlib import Path

import pytest
from fastmcp import FastMCP

from insee_viz_mcp.lifespan import build_lifespan
from insee_viz_mcp.server import create_mcp
from insee_viz_mcp.settings import Settings
from insee_viz_mcp.utils.publish import Publisher


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Production defaults, with the output directory and the `.env` file under control."""
    return Settings(_env_file=None, output_dir=tmp_path)


@pytest.fixture
def server(settings: Settings) -> FastMCP:
    """The production app, rendering into `tmp_path`, with no PNG rasteriser."""
    publisher = Publisher(out_dir=Path(settings.output_dir), rasteriser=None)
    return create_mcp(settings, lifespan=build_lifespan(settings, publisher=publisher))
