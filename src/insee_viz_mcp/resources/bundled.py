"""Reading the files shipped inside the package.

`importlib.resources` rather than a path built from `__file__`: it keeps working when the package
is imported from a wheel or a zip, which is how the container runs it.
"""

import logging
from importlib import resources

logger = logging.getLogger(__name__)

DATA_PACKAGE = "insee_viz_mcp.data"


def read_text(name: str, *, fallback: str) -> str:
    """Read one bundled file, or answer `fallback` and log why it was missing.

    A missing guide or viewer must not take the server down: the tools still render figures, and
    the caller gets a body that says so instead of a protocol error.
    """
    try:
        return resources.files(DATA_PACKAGE).joinpath(name).read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        logger.error("Bundled file %s is missing from this installation: %s", name, exc)
        return fallback
