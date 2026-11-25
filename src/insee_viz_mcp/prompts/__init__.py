"""Prompt registration entrypoint: one prompt that wraps the whole figure workflow."""

from fastmcp import FastMCP

from .figure import figure_insee


def register_prompts(mcp: FastMCP) -> None:
    """Register every prompt the server exposes. A host without prompt support simply sees none."""
    mcp.prompt(figure_insee)
