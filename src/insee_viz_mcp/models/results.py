"""What a render tool hands back to the MCP App viewer.

`FigureView` is the payload that lands in `structuredContent`; the viewer at
`ui://insee-viz/view.html` reads these keys by name, so they are a contract too. A model rather
than a dict so a key cannot be misspelled without a test failing.
"""

from pydantic import BaseModel, Field


class EditorialNotes(BaseModel):
    """The footer of the figure, in Insee's order: Lecture, Champ, Source."""

    lecture: str | None = Field(None, description="One factual sentence with a value, when the caller supplied one.")
    champ: str | None = Field(None, description="Geographic field and population covered.")
    source: str | None = Field(None, description="Producer + operation + vintage.")
    note: str | None = Field(None, description="Optional methodological note.")


class DataTable(BaseModel):
    """The figures behind the drawing, so a text-only client can still answer."""

    columns: list[str] = Field(description="Header labels, in display order.")
    rows: list[list[str]] = Field(description="One row per category, territory or period; values pre-formatted.")


class FigureView(BaseModel):
    """What `render_map`, `render_bars` and `render_line` return."""

    kind: str = Field(description="Figure form: 'map', 'bars' or 'line'.")
    svg: str = Field(description="The SVG document, when the client declared the MCP Apps extension; empty otherwise.")
    has_inline_svg: bool = Field(
        description="True when `svg` carries the figure. False means the figure is only on disk."
    )
    slug: str = Field(description="Filesystem-safe stem shared by the written files.")
    title: str = Field(description="The figure title, as displayed.")
    subtitle: str | None = Field(None, description="The unit line printed under the title.")
    declaration: str = Field(description="Title prefixed with its figure number, when there is one.")
    notes: EditorialNotes = Field(description="The editorial block under the figure.")
    table: DataTable = Field(description="The data behind the figure, formatted for reading.")
    files: dict[str, str] = Field(description="Absolute paths of the written files, keyed by format ('svg', 'png').")
    warnings: list[str] = Field(
        default_factory=list,
        description="What the figure is missing to be publishable, and what to do about it.",
    )
