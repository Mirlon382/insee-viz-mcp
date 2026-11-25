"""The routing contract: what `recommend_chart` needs to know about a dataset.

A column profile is all the router reads. It never sees the data itself, which is what keeps the
choice of figure deterministic and independent of the values.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

ColumnKind = Literal["numeric", "date", "geography", "category", "text"]

ColumnName = Annotated[
    str,
    Field(
        description="Column name as it appears in the data.",
        examples=["densite", "code_departement"],
        min_length=1,
    ),
]

ColumnRole = Annotated[
    ColumnKind,
    Field(
        description=(
            "Role of the column: numeric measure, date/period, official geographic code, category, free text."
        ),
        examples=["geography"],
    ),
]


class ColumnProfile(BaseModel):
    """One column of the dataset, described by role rather than by value."""

    name: ColumnName
    kind: ColumnRole
    distinct: int | None = Field(None, description="Number of distinct values, when known.")
    example: str | None = Field(None, description="One example value, e.g. '2023-01' or '75'.")
