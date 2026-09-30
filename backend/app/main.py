"""BustGuard API.

uv run uvicorn app.main:app --reload --port 8000     (docs at http://localhost:8000/docs)
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.routes import confidence, evidence, meta, region, regions

app = FastAPI(
    title="BustGuard API",
    version="0.1.0",
    description=(
        "Forecast bust detection for medium-range NWP (SIH26079, MoES/NCMRWF). Predicts where and at "
        "which lead day a forecast is likely to fail, with calibrated probabilities, confidence, "
        "plain-English reasons, analog cases and replay of real past busts."
    ),
)
origins = os.environ.get(
    "BUSTGUARD_CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)

for r in (meta.router, regions.router, confidence.router, region.router, evidence.router):
    app.include_router(r)
