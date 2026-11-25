"""Process-wide resources: opened once at startup, closed once at shutdown.

Here that is the figure publisher (output directory + rasteriser) and the geometry cache, both
resolved before the first call so a broken install fails at startup instead of on a render.

A tool never builds its own publisher. It asks for one through `utils.publish.get_publisher`,
which reads what this lifespan yielded. FastMCP wants a lifespan that takes the server, so the
settings are closed over here rather than passed to the decorator.
"""

import asyncio
import logging
from collections.abc import AsyncIterator

from fastmcp import FastMCP
from fastmcp.server.lifespan import Lifespan, lifespan

from . import geo
from .settings import Settings
from .utils.publish import Publisher

logger = logging.getLogger(__name__)

LEVELS = ("departement", "region")


def _warm_geometry() -> None:
    """Load both contour files once. `geo.features` is cached, so later renders read memory."""
    for level in LEVELS:
        features = geo.features(level)
        logger.info("Loaded %d %s contours", len(features), level)


def build_lifespan(settings: Settings, publisher: Publisher | None = None) -> Lifespan:
    """Build the lifespan. `publisher` is a seam for tests: production passes nothing.

    Whatever is yielded here is reachable from a tool as `ctx.lifespan_context["name"]`; keep the
    keys stable, they are the contract between this file and every tool.
    """

    @lifespan
    async def _lifespan(_server: FastMCP) -> AsyncIterator[dict[str, object]]:
        resolved = publisher if publisher is not None else Publisher.from_settings(settings)
        resolved.prepare()
        await asyncio.to_thread(_warm_geometry)
        yield {"publisher": resolved}

    return _lifespan
