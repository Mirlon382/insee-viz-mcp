"""Does the caller render an MCP App?

The viewer resource is only useful to a host that declared the MCP Apps extension. Sending a
180 KB map into a text-only client's context is worse than sending none, so the SVG is gated on
this answer and the files on disk carry the figure either way.
"""

import logging

from fastmcp.apps import UI_EXTENSION_ID
from fastmcp.dependencies import CurrentContext
from fastmcp.server.context import Context

logger = logging.getLogger(__name__)


def app_extension_declared(ctx: Context = CurrentContext()) -> bool:
    """True when this client negotiated the MCP Apps extension.

    Swallowing the lookup is deliberate: a transport or SDK that does not expose extension
    negotiation knows no apps, and a render must not fail because the question could not be asked.
    """
    try:
        return bool(ctx.client_supports_extension(UI_EXTENSION_ID))
    except Exception:
        logger.debug("Client extension lookup failed; treating the caller as having no app support.")
        return False
