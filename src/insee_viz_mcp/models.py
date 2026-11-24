"""Validated input models shared by the render tools.

The schemas are the contract the LLM fills in. Required fields are exactly
those Insee never omits (title, source); the rest produce guidance warnings
instead of blocking a figure.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class FigureMeta(BaseModel):
    """Editorial metadata every Insee figure carries."""

    title: str = Field(..., description="Statement-style title, no final period, e.g. 'Temps d'accès aux services selon le type de commune'.")
    source: str = Field(..., description="Data producer and operation, e.g. 'Insee, base permanente des équipements (BPE) 2025.'")
    unit: str | None = Field(None, description="Unit or scale shown under the title, e.g. 'en minutes', 'en %', 'indice base 100 en 2010'.")
    number: str | None = Field(None, description="Figure number when the figure belongs to a publication, e.g. '2'.")
    lecture: str | None = Field(None, description="One sentence telling the reader what to look at, starting with a fact and its value.")
    champ: str | None = Field(None, description="Field/coverage, e.g. 'France hors Mayotte, communes.'")
    note: str | None = Field(None, description="Optional methodological note.")
    brand: bool = Field(False, description="Add an 'Insee' wordmark in the top-right corner (only for real Insee publications).")

    @field_validator("title", "source", "unit", "lecture", "champ", "note", mode="before")
    @classmethod
    def _clean(cls, value):
        if isinstance(value, str):
            value = " ".join(value.split())
            return value or None
        return value

    @field_validator("title")
    @classmethod
    def _title_rules(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("title is too short: Insee titles are statements, not labels")
        if len(value) > 150:
            raise ValueError("title must be 150 characters or fewer")
        if value.endswith("."):
            value = value[:-1]
        return value

    @field_validator("source")
    @classmethod
    def _source_rules(cls, value: str) -> str:
        if len(value) < 4:
            raise ValueError("source must name the producer and the operation, e.g. 'Insee, recensement de la population 2022.'")
        return value

    @field_validator("number")
    @classmethod
    def _number_rules(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = str(value).strip()
        for prefix in ("Figure", "figure", "Fig."):
            if value.startswith(prefix):
                value = value[len(prefix):].strip()
        return value or None


class BarRow(BaseModel):
    label: str = Field(..., description="Category label, as published (sentence case).")
    value: float = Field(..., description="Numeric value for the category.")
    series: str | None = Field(None, description="Optional series name for grouped bars (max 3 series).")


class Point(BaseModel):
    x: str = Field(..., description="Period or position: '2023' (year), '2023-01' (month), '2023-T1' (quarter) or a number.")
    y: float = Field(..., description="Value at that period.")


class Series(BaseModel):
    label: str = Field(..., description="Series name, short and as published.")
    points: list[Point] = Field(..., min_length=1)


class MapRow(BaseModel):
    code: str = Field(..., description="Official geographic code: '75', '2A', '971' for departments; '11' for regions.")
    value: float | None = Field(None, description="Indicator value; null/omitted for 'non disponible'.")
    name: str | None = Field(None, description="Optional label, used in the data table.")


class BarSpec(BaseModel):
    rows: list[BarRow] = Field(..., min_length=1, max_length=80)
    meta: FigureMeta
    orientation: Literal["horizontal", "vertical"] = Field(
        "horizontal",
        description="Horizontal for ranked categories (Insee default); vertical only for ordered short labels.",
    )
    sort: Literal["desc", "asc", "none"] = Field("desc", description="Order of categories on the axis.")
    highlight: str | None = Field(None, description="A category label to emphasise; others are drawn in the light blue.")
    show_values: bool = Field(True, description="Print the value at the end of each bar (single-series only).")
    decimals: int = Field(0, ge=0, le=3, description="Decimals used for value labels and ticks.")
    value_suffix: str | None = Field(None, description="Short suffix appended to value labels, e.g. '%', 'euros', 'min'.")

    @model_validator(mode="after")
    def _series_rules(self) -> "BarSpec":
        names = list(dict.fromkeys(r.series for r in self.rows if r.series))
        if len(names) > 3:
            raise ValueError("at most 3 series can be grouped; aggregate or split the figure")
        if names:
            counts = {n: sum(1 for r in self.rows if r.series == n) for n in names}
            if len(set(counts.values())) > 1:
                raise ValueError("grouped bars need the same number of values in each category for every series")
        return self


class LineSpec(BaseModel):
    series: list[Series] = Field(..., min_length=1, max_length=4)
    meta: FigureMeta
    y_zero: bool = Field(False, description="Force the y axis to start at zero (mandatory when the unit is a level, not an index).")
    y_min: float | None = Field(None, description="Imposed lower bound for the y axis.")
    y_max: float | None = Field(None, description="Imposed upper bound for the y axis.")
    decimals: int = Field(1, ge=0, le=3)
    reference: float | None = Field(None, description="Optional horizontal reference line value, e.g. a national average.")
    reference_label: str | None = Field(None, description="Label printed on the reference line, e.g. 'Moyenne de l'artisanat'.")
    end_labels: bool = Field(True, description="Label each line at its right end instead of a legend box.")


class MapSpec(BaseModel):
    rows: list[MapRow] = Field(..., min_length=1, max_length=120)
    meta: FigureMeta
    level: Literal["departement", "region"] = Field("departement", description="Geographic level of the codes.")
    classes: int = Field(5, ge=3, le=7, description="Number of colour classes (Insee uses 4 to 6).")
    method: Literal["quantile", "equal"] = Field("quantile", description="Discretisation: quantiles (default) or equal intervals.")
    thresholds: list[float] | None = Field(None, description="Explicit class bounds, overriding method; length must be classes-1.")
    decimals: int = Field(0, ge=0, le=2)
    value_suffix: str | None = Field(None, description="Short suffix for the legend, e.g. '%' or ' hab./km²'.")
