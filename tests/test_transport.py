"""Both transports really speak the protocol.

`http` is what this server is: the console script serves Streamable HTTP on `/mcp`, and a client
reaches it by URL. `stdio` stays supported for a client that launches the process itself, so both
paths get a handshake test -- the HTTP one through the ASGI app, the stdio one through the real
entry point on a subprocess's pipes.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from starlette.testclient import TestClient

from insee_viz_mcp.lifespan import build_lifespan
from insee_viz_mcp.server import create_mcp
from insee_viz_mcp.settings import Settings
from insee_viz_mcp.utils.publish import Publisher

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}


def test_the_default_transport_is_http():
    assert Settings(_env_file=None).mcp_transport == "http"


def _json_reply(response) -> dict:
    """The body is one JSON-RPC reply, sent as `text/event-stream` or as plain JSON depending on
    the negotiated response mode. Both are the protocol; neither is a test detail."""
    if "text/event-stream" in response.headers.get("content-type", ""):
        return json.loads(next(line[5:] for line in response.text.splitlines() if line.startswith("data:")))
    return response.json()


def test_the_http_transport_answers_a_handshake(settings: Settings):
    # The same app the server serves, built on the test settings so nothing lands in ~/.cache.
    publisher = Publisher(out_dir=Path(settings.output_dir), rasteriser=None)
    app = create_mcp(settings, lifespan=build_lifespan(settings, publisher=publisher)).http_app(
        host_origin_protection=True,
        allowed_hosts=["*"],
    )

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json=INITIALIZE,
            headers={"Accept": "application/json, text/event-stream"},
        )

    assert response.status_code == 200
    reply = _json_reply(response)
    assert reply["result"]["serverInfo"]["name"] == "Insee figures"
    assert "tools" in reply["result"]["capabilities"]


def test_the_stdio_transport_answers_a_handshake(tmp_path: Path):
    # Opt-in: MCP_TRANSPORT=stdio is what a client that launches the process itself relies on.
    env = {
        **os.environ,
        "MCP_TRANSPORT": "stdio",
        "LOG_LEVEL": "CRITICAL",
        # Keep the geometry load and the output directory out of the real cache.
        "INSEE_VIZ_OUT": str(tmp_path),
    }

    completed = subprocess.run(
        [sys.executable, "-m", "insee_viz_mcp.server"],
        input=json.dumps(INITIALIZE) + "\n",
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        check=False,
    )

    # The protocol answer is on stdout; anything else a library prints there must not become the
    # first line of this test's assumption, so parse the first line that is JSON.
    reply = next(json.loads(line) for line in completed.stdout.splitlines() if line.startswith("{"))
    assert reply["result"]["serverInfo"]["name"] == "Insee figures"
    assert "tools" in reply["result"]["capabilities"]
