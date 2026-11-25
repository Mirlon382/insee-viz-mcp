# Multi-stage: the builder installs the dependencies, the runtime keeps only the result. The uv
# binary and the download caches never reach the image that ships.

# ---- Build stage ----------------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# UV_LINK_MODE: uv hard-links from its cache into the venv, and hard links cannot cross filesystems.
# The cache mount below is a different mount, so uv would warn on every build. Copy instead.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Pinned rather than :latest -- a build stage that changes under you is not reproducible.
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/

# Dependencies before source: a one-line code edit must not invalidate the layer that installs them.
# README.md is here because `pyproject.toml` names it as the package readme: hatchling reads it while
# building the project, so it must exist before `uv sync` installs the project itself.
COPY pyproject.toml uv.lock README.md /app/

# The cache mount survives between builds without being stored in the image.
# --locked fails when uv.lock is not current for pyproject.toml. Plain `uv sync` would rewrite the
# lock and install versions nobody tested; --frozen would use a stale lock and silently omit a
# dependency that was added but never locked.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project --locked

COPY src/ /app/src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --locked

# ---- Runtime stage --------------------------------------------------------------------------------
FROM python:3.12-slim

# librsvg2-bin is `rsvg-convert`, the rasteriser a render tool calls for the PNG twin of each SVG.
# fonts-dejavu-core is the fallback the figures name after Marianne: without a font, rsvg-convert
# still writes a PNG, with empty boxes where the labels are. Drop both if SVG-only is enough.
RUN apt-get update \
 && apt-get install --no-install-recommends --yes librsvg2-bin fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

# MCP_TRANSPORT: Streamable HTTP on /mcp, same as the default -- set here anyway, so the image never
# depends on a default that could move.
# INSEE_VIZ_OUT: `/data` is a declared volume, so rendered figures survive a container restart.
# PATH: `python` means the venv's python everywhere -- CMD, HEALTHCHECK, and docker exec.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}" \
    MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    INSEE_VIZ_OUT=/data

WORKDIR /app

# Fixed UID/GID so a bind-mounted file keeps the same owner on the host.
RUN groupadd --gid 1000 app \
 && useradd --uid 1000 --gid 1000 --create-home --shell /usr/sbin/nologin app \
 && mkdir -p /data \
 && chown app:app /data

# --chown during the copy, never a later chown: that would duplicate every file into a new layer.
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src

USER app

VOLUME ["/data"]

EXPOSE 8000

# A TCP connect, not an HTTP request: the MCP endpoint answers 400 without a session handshake, so an
# HTTP check would fail on a healthy server. The start period covers the lifespan loading the bundled
# contours. Podman's default OCI format drops HEALTHCHECK entirely: build with
# `podman build --format docker` to keep it.
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import os, socket; socket.create_connection(('127.0.0.1', int(os.environ.get('MCP_PORT', 8000))), 2).close()"

# Exec form: the process runs as PID 1 and receives SIGTERM, so shutdown is clean.
CMD ["python", "-m", "insee_viz_mcp.server"]
