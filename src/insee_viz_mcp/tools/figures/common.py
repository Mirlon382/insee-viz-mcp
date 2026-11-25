"""Plumbing shared by the three render tools.

A render tool has four jobs: validate the contract, draw, publish, answer. Only the drawing differs
between them, so everything else lives here -- one warning list, one refusal wording, one payload
shape. The texts are the product: they are what the model reads before its next attempt.
"""

from fastmcp.tools import ToolResult
from mcp.types import TextContent
from pydantic import ValidationError

from ...errors import AppToolError, ErrorCode
from ...models.figures import FigureMeta
from ...models.results import FigureView

ANSWER_HINT = (
    "Answer with the figure, its title/unit and the Lecture / Champ / Source block; "
    "quote only values present in the data."
)


def editorial_warnings(meta: FigureMeta) -> list[str]:
    """What the figure is missing to be publishable.

    These never block a render: Insee prints an incomplete editorial block every so often, and a
    caller who sees the warning in the result (and in the viewer) can still fix it next call.
    """
    out: list[str] = []
    if not meta.unit:
        out.append(
            "meta.unit is missing: Insee prints the unit under the title ('en %', 'en minutes', "
            "'indice base 100 en 2010')."
        )
    if not meta.lecture:
        out.append(
            "meta.lecture is missing: add one factual sentence with a value, e.g. 'En 2025, les "
            "habitants ... mettent en moyenne 8,1 minutes ...'."
        )
    if not meta.champ:
        out.append(
            "meta.champ is missing: state the geographic field and population, e.g. 'France hors Mayotte, communes.'."
        )
    return out


def rejected_contract(exc: ValidationError) -> AppToolError:
    """Turn pydantic's field errors into one actionable sentence.

    `loc` is the field path the caller filled in the wrong way, so it is printed verbatim: the model
    can repair the call without guessing which argument failed.
    """
    parts = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        parts.append(f"`{location}`: {error['msg']}")
    return AppToolError(
        ErrorCode.INVALID_INPUT,
        "the figure contract was rejected — " + "; ".join(parts) + ". Fix the fields named and call again.",
    )


def refused_figure(exc: ValueError) -> AppToolError:
    """A renderer refusing a combination the schema cannot describe (e.g. threshold count)."""
    return AppToolError(
        ErrorCode.INVALID_INPUT,
        f"{exc} Adjust the parameter it names and call again.",
    )


def figure_result(view: FigureView, summary: str) -> ToolResult:
    """The tool's answer: readable text for the model, structured content for the app viewer.

    `structured_content` is not a convenience here -- it is the interface the MCP App resource
    reads. The text branch matters just as much: a client without the extension gets the summary,
    the file paths and the warnings, and the figure exists on disk either way.
    """
    lines = [summary, "Files: " + " | ".join(f"{kind.upper()} {path}" for kind, path in view.files.items())]
    if view.warnings:
        lines.append("Warnings: " + " ".join(view.warnings))
    lines.append(ANSWER_HINT)
    return ToolResult(
        content=[TextContent(type="text", text="\n".join(lines))],
        structured_content=view.model_dump(mode="json"),
    )
