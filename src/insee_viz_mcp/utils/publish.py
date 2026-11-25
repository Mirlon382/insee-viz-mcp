"""Writing a figure to disk: the one place that touches the filesystem or a subprocess.

The publisher lives in the lifespan (it resolves the rasteriser once, at startup, and creates the
output directory), and a tool reads it through `Depends`:

    async def render_bars(..., publisher: Publisher = Depends(get_publisher)) -> ToolResult:
        published = await publisher.publish(svg, meta)

Two traps this file exists to avoid:

1. `Depends` that returns a bare object with an `__aenter__` makes FastMCP open it per call. A
   `Publisher` is a plain frozen dataclass, so it is handed over as-is.
2. `shutil.which` and the PNG subprocess are blocking. Writing a 200 KB SVG is not worth a thread,
   but `rsvg-convert` takes ~150 ms, so the whole publish runs in one: the event loop keeps serving
   other callers meanwhile.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from fastmcp.dependencies import CurrentContext
from fastmcp.server.context import Context

from ..errors import AppToolError, ErrorCode
from ..models.figures import FigureMeta
from ..settings import Settings
from ..style import slugify

logger = logging.getLogger(__name__)

RASTERISERS = ("rsvg-convert", "magick")


@dataclass(frozen=True)
class Published:
    """Where one figure landed."""

    files: dict[str, str] = field(default_factory=dict)
    slug: str = ""


@dataclass(frozen=True)
class Publisher:
    """Writes the SVG, then the PNG when a rasteriser is installed.

    Frozen and dependency-free so a test can build one on `tmp_path` without the lifespan.
    """

    out_dir: Path
    raster_width: int = 1840
    rasteriser: str | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> Publisher:
        """Resolve the rasteriser once: a missing one is a warning, never a failed start."""
        found = next((path for name in RASTERISERS if (path := shutil.which(name))), None)
        if found is None:
            logger.warning("No rasteriser on PATH (%s): tools will return the SVG only.", ", ".join(RASTERISERS))
        else:
            logger.info("Rasterising PNGs with %s", found)
        return cls(out_dir=Path(settings.output_dir), raster_width=settings.raster_width, rasteriser=found)

    def prepare(self) -> None:
        """Create the output directory. Called by the lifespan, so the first call pays nothing."""
        self.out_dir.mkdir(parents=True, exist_ok=True)

    async def publish(self, svg: str, meta: FigureMeta) -> Published:
        """Write the figure off the event loop and answer with its paths."""
        return await asyncio.to_thread(self._publish, svg, meta)

    def _publish(self, svg: str, meta: FigureMeta) -> Published:
        slug = slugify(meta.title, 70)
        svg_path = self.out_dir / f"{slug}.svg"
        try:
            self.prepare()
            svg_path.write_text(svg, encoding="utf-8")
        except OSError as exc:
            # Not the caller's fault and not fixable by retrying, so it is our deployment error --
            # but it still needs words: "Error calling tool" plus a traceback in the log is how a
            # root-owned volume under a read-only root filesystem looks from the outside.
            raise AppToolError(
                ErrorCode.INTERNAL_ERROR,
                f"the figure output directory `{self.out_dir}` is not writable by this server "
                f"({exc.strerror or exc}). Point INSEE_VIZ_OUT at a writable path, or make the "
                "mounted volume writable by the user the server runs as (uid 1000 in the image).",
            ) from exc
        files = {"svg": str(svg_path)}
        png_path = self._rasterise(svg_path)
        if png_path is not None:
            files["png"] = str(png_path)
        return Published(files=files, slug=slug)

    def _rasterise(self, svg_path: Path) -> Path | None:
        """Best effort: a converter that fails must not lose a figure that already exists as SVG."""
        if not self.rasteriser:
            return None
        png_path = svg_path.with_suffix(".png")
        command = (
            [self.rasteriser, "-w", str(self.raster_width), "-o", str(png_path), str(svg_path)]
            if Path(self.rasteriser).name == "rsvg-convert"
            else [self.rasteriser, str(svg_path), "-density", "192", str(png_path)]
        )
        try:
            subprocess.run(command, check=True, timeout=30, capture_output=True)
        except (subprocess.SubprocessError, OSError) as exc:
            logger.warning("Rasterising %s failed: %s", svg_path.name, exc)
            return None
        return png_path


def get_publisher(ctx: Context = CurrentContext()) -> Publisher:
    """The publisher the lifespan created. FastMCP resolves this before the tool runs."""
    return ctx.lifespan_context["publisher"]
