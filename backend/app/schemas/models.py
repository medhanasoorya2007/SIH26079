"""Pydantic response/request models (also drive the OpenAPI docs at /docs)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Region(BaseModel):
    id: str
    name: str
    subdivision: str
    zone: str
    lat: float
    lon: float


class Reason(BaseModel):
    feature: str
    text: str
    contribution: float = Field(description="TreeSHAP contribution to bust log-odds")
    value: float


class RegionConfidence(BaseModel):
    id: str
    name: str
    subdivision: str
    zone: str
    lat: float
    lon: float
    fc: float | None = Field(None, description="Forecast under evaluation (ECMWF HRES), mm/day")
    fc_alt: float | None = Field(None, description="Second model (GraphCast), mm/day")
    obs: float | None = Field(None, description="Verifying truth (ERA5), if already observed")
    bust_prob: float | None
    baseline_prob: float | None = None
    confidence: float | None
    risk: str | None
    regime: str | None = None
    bust: float | None = Field(
        None, description="1 if the forecast actually busted (verified rows)"
    )
    rank: int | None = None
    top_reason: str | None = None


class ConfidenceMap(BaseModel):
    source: str
    is_synthetic: bool
    date: str
    lead: int
    variable: str
    valid_date: str | None
    regions: list[RegionConfidence]
    error_prone: list[str] = Field(
        description="Region ids ranked by bust probability (highest first)"
    )
    summary: dict


class Analog(BaseModel):
    init_date: str
    valid_date: str
    region_id: str
    region_name: str
    lead_day: int
    fc: float | None
    obs: float | None
    abs_error: float | None
    bust: float | None
    regime: str | None = None
    distance: float | None


class LeadDetail(BaseModel):
    lead_day: int
    valid_date: str
    fc: float | None
    fc_alt: float | None
    obs: float | None
    abs_error: float | None
    bust: float | None
    bust_prob: float | None
    baseline_prob: float | None
    confidence: float | None
    risk: str | None
    regime: str | None
    disagreement: float | None = None
    jump: float | None = None
    reasons: list[Reason]
    analogs: list[Analog]


class RegionDetail(BaseModel):
    source: str
    is_synthetic: bool
    region: Region
    date: str
    variable: str
    leads: list[LeadDetail]


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
