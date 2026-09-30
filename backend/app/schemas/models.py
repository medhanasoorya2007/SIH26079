"""Pydantic request/response models (drive the OpenAPI docs at /docs)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Region(BaseModel):
    id: str
    name: str
    subdivision: str
    zone: str
    lat: float
    lon: float


class SavedAnalysisIn(BaseModel):
    title: str = Field(max_length=200)
    note: str = Field("", max_length=4000)
    date: str
    lead: int
    variable: str = "rain"
    region_id: str | None = None
    source: str | None = None


class SavedAnalysis(SavedAnalysisIn):
    id: str
    created_utc: str
