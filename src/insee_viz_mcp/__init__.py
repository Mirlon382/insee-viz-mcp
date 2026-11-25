"""Insee-style figure server (FastMCP 4 + MCP Apps).

The package is an application, not a library: importing it registers nothing. `insee_viz_mcp.server`
holds the app (`mcp`), the ASGI app (`app`) and the console entry point (`main`).

Layout:

- `server.py`     settings, lifespan, middlewares, both transports
- `tools/`        the MCP surface: one package per concern, one registration list
- `resources/`    the doctrine and the app viewer
- `prompts/`      the prepared workflow
- `models/`       the typed contract the model fills in
- `charts/`       the renderers, in Insee house style
- `style.py`, `svgkit.py`, `geo.py`  typography, SVG primitives, Lambert-93 projection
- `utils/`        the shared publisher, the rate-limit key, the app check
"""
