"""Every value this server can be configured with.

Names are read from the environment in upper case (`MCP_PORT`, `INSEE_VIZ_OUT`) and from `.env`
beside the working directory. Unknown variables are ignored, so a stale key never prevents the
server from starting.
"""

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # MCP server -------------------------------------------------------------------------------------------------------
    # Sent to the client in the handshake, and shown in most inspector UIs.
    mcp_name: str = "Insee figures"
    # http: serve Streamable HTTP on POST /mcp -- this application is a server, and that is what the
    # console script, the container and a client registered by URL all use. stdio: talk over the
    # process's pipes instead, for a client that launches the process itself (MCP_TRANSPORT=stdio).
    mcp_transport: Literal["http", "stdio"] = "http"

    # HTTP server ------------------------------------------------------------------------------------------------------
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000
    # JSON list of the hostnames clients use to reach this server, checked against the Host
    # header. "*" accepts any host, which disables the check.
    allowed_hosts: list[str] = ["*"]
    # JSON list of browser origins allowed to call the server. Empty rejects every cross-origin
    # browser request; an MCP App host renders the viewer in its own iframe and needs no origin.
    allowed_origins: list[str] = []
    # Peers whose X-Forwarded-For header is believed; anything else keeps its real socket address.
    # Accepts addresses, CIDR networks and literals. Widening this lets callers forge their own address.
    trusted_proxy_hosts: list[str] = ["127.0.0.1"]

    # Figures ----------------------------------------------------------------------------------------------------------
    # Where every rendered figure is written. Both names are accepted: INSEE_VIZ_OUT is what the
    # 0.1 prototype documented and what a Hermes registration may already pass.
    output_dir: Path = Field(
        default_factory=lambda: Path.home() / ".cache" / "insee-viz",
        validation_alias=AliasChoices("INSEE_VIZ_OUT", "OUTPUT_DIR"),
    )
    # Pixel width of the rasterised PNG: two times the 920 px canvas, so it stays crisp on HiDPI.
    raster_width: int = 1840

    # Rate limiting ----------------------------------------------------------------------------------------------------
    rate_limit_max_requests: int = 100
    rate_limit_window_minutes: int = 1

    # Logging ----------------------------------------------------------------------------------------------------------
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )


def load_settings() -> Settings:
    return Settings()
