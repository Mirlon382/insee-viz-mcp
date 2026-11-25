"""The publisher: the only place a figure reaches the disk.

Pinned rasteriser to `None` in the happy path, so the suite passes on a machine without
`rsvg-convert`; the failure paths use a stand-in that always fails and an unwritable directory,
because "a broken converter must not lose a figure" and "an unwritable volume says so" are promises
worth a test each.
"""

import os
from pathlib import Path

import pytest

from insee_viz_mcp.errors import AppToolError, ErrorCode
from insee_viz_mcp.models.figures import FigureMeta
from insee_viz_mcp.style import slugify
from insee_viz_mcp.utils.publish import Publisher

META = FigureMeta(
    title="La densité de population va de 15 habitants au km² en Lozère à 20 054 à Paris",
    unit="nombre d'habitants au km²",
    source="Insee, recensement de la population 2022.",
)

SVG = '<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" width="920" height="20"/>'


async def test_publish_writes_the_svg_and_slugs_the_title(tmp_path: Path):
    publisher = Publisher(out_dir=tmp_path / "nested", rasteriser=None)

    published = await publisher.publish(SVG, META)

    assert published.slug == slugify(META.title, 70)
    assert published.slug.startswith("la-densite-de-population-va-de-15-habitants")
    written = Path(published.files["svg"])
    assert written.parent == tmp_path / "nested"  # prepare() created it
    assert written.read_text(encoding="utf-8") == SVG
    assert "png" not in published.files


async def test_a_failing_rasteriser_keeps_the_svg(tmp_path: Path):
    publisher = Publisher(out_dir=tmp_path, rasteriser="/bin/false")

    published = await publisher.publish(SVG, META)

    assert Path(published.files["svg"]).exists()
    assert "png" not in published.files


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes into a read-only directory")
async def test_an_unwritable_output_directory_names_the_fix(tmp_path: Path):
    # The deployment failure behind a root-owned volume mounted under a read-only root filesystem.
    blocked = tmp_path / "mounted"
    blocked.mkdir()
    blocked.chmod(0o555)
    try:
        publisher = Publisher(out_dir=blocked, rasteriser=None)

        with pytest.raises(AppToolError) as raised:
            await publisher.publish(SVG, META)
    finally:
        blocked.chmod(0o755)

    assert raised.value.code is ErrorCode.INTERNAL_ERROR
    assert "INSEE_VIZ_OUT" in str(raised.value)
