from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from ingest.refresh import (
    refresh_company_period
)


from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

# Load environment variables from .env file
load_dotenv()

from graph.db import get_neo4j_driver
from graph.schema import ensure_schema
from graph.queries import (
    find_company_by_name,
    get_claims_with_sources,
    get_sentiment_delta,
    get_latest_fetch_by_type
)
from agent.freshness import (
    freshness_check
)

app = FastAPI(title="PulseGraph API", version="0.1.0")

# -------------------------
# Pydantic models
# -------------------------

class AskRequest(BaseModel):
    question: str = Field(..., description="User question")
    company: Optional[str] = Field(None, description="Company name override (optional)")
    period_a: str = Field("Q3-2025", description="Latest period (MVP default)")
    period_b: str = Field("Q2-2025", description="Comparison period (MVP default)")
    window: str = Field("post_earnings_7d", description="Signal window label")


class SourceOut(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None
    source_type: Optional[str] = None
    published_at: Optional[str] = None
    fetched_at: Optional[str] = None


class ClaimOut(BaseModel):
    id: str
    text: str
    claim_type: Optional[str] = None
    confidence: Optional[float] = None
    last_updated_at: Optional[str] = None
    sources: List[SourceOut] = []


class SentimentSignalOut(BaseModel):
    id: Optional[str] = None
    score: Optional[float] = None
    volume: Optional[int] = None
    window: Optional[str] = None
    computed_at: Optional[str] = None


class SentimentDeltaOut(BaseModel):
    period_a: str
    period_b: str
    window: str
    delta: Optional[float] = None
    a: Optional[SentimentSignalOut] = None
    b: Optional[SentimentSignalOut] = None
    note: Optional[str] = None


class FreshnessOut(BaseModel):
    was_stale: bool
    reason: str
    checked_at: str


class AskResponse(BaseModel):
    company: Dict[str, Any]
    period_a: str
    period_b: str
    sentiment: SentimentDeltaOut
    claims_a: List[ClaimOut]
    claims_b: List[ClaimOut]
    freshness: FreshnessOut


# -------------------------
# App lifecycle: Neo4j driver
# -------------------------

@app.on_event("startup")
def on_startup() -> None:
    driver = get_neo4j_driver()
    ensure_schema(driver)
    app.state.neo4j_driver = driver


@app.on_event("shutdown")
def on_shutdown() -> None:
    driver = getattr(app.state, "neo4j_driver", None)
    if driver is not None:
        driver.close()


# -------------------------
# Routes
# -------------------------

@app.get("/")
async def root():
    return {"message": "PulseGraph API is running"}


def _simple_company_guess_from_question(q: str) -> Optional[str]:
    """
    MVP: super simple heuristic.
    Later you’ll replace this with a proper entity extractor or LLM tool.
    """
    ql = q.lower()
    # Add more as you seed more companies
    if "nvidia" in ql or "nvda" in ql:
        return "NVIDIA"
    if "tesla" in ql or "tsla" in ql:
        return "Tesla"
    return None

@app.post("/ask", response_model=AskResponse)
async def ask(payload: AskRequest, auto_refresh: bool = Query(False)):
    driver = getattr(app.state, "neo4j_driver", None)
    if driver is None:
        raise HTTPException(status_code=500, detail="Neo4j driver not initialized")

    # 1) determine company
    company_name = payload.company or _simple_company_guess_from_question(payload.question)
    if not company_name:
        raise HTTPException(
            status_code=400,
            detail="Could not infer company from question. Provide `company` in the request.",
        )

    company = find_company_by_name(driver, company_name)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company not found in graph: {company_name}")

    company_id = company["id"]

    # 2) freshness check (real, graph-backed)
    latest_a = get_latest_fetch_by_type(driver, company_id, payload.period_a)
    latest_b = get_latest_fetch_by_type(driver, company_id, payload.period_b)

    combined_latest = latest_a + latest_b
    freshness_raw = freshness_check(combined_latest)

    freshness = FreshnessOut(
        was_stale=freshness_raw["was_stale"],
        reason=(
            f"Stale source types detected: {freshness_raw['stale_types']}"
            if freshness_raw["was_stale"]
            else "All source data within freshness thresholds."
        ),
        checked_at=freshness_raw["checked_at"],
    )

    refresh_log = None
    if freshness.was_stale and auto_refresh:
        refresh_log = refresh_company_period(
            driver=driver,
            company_id=company_id,
            company_name=company["name"],
            period=payload.period_a,
            source_types=freshness_raw["stale_types"],
        )

    # 3) query the graph
    claims_a_raw = get_claims_with_sources(driver, company_id, payload.period_a, limit=15)
    claims_b_raw = get_claims_with_sources(driver, company_id, payload.period_b, limit=15)

    sentiment_raw = get_sentiment_delta(driver, company_id, payload.period_a, payload.period_b, window=payload.window)

    # 4) shape response
    def to_claim_out(row: Dict[str, Any]) -> ClaimOut:
        sources = [SourceOut(**s) for s in (row.get("sources") or []) if s]
        return ClaimOut(
            id=row["id"],
            text=row["text"],
            claim_type=row.get("claim_type"),
            confidence=row.get("confidence"),
            last_updated_at=row.get("last_updated_at"),
            sources=sources,
        )

    def to_signal_out(sig: Optional[Dict[str, Any]]) -> Optional[SentimentSignalOut]:
        if not sig:
            return None
        return SentimentSignalOut(
            id=sig.get("id"),
            score=sig.get("score"),
            volume=sig.get("volume"),
            window=sig.get("window"),
            computed_at=sig.get("computed_at"),
        )

    sentiment = SentimentDeltaOut(
        period_a=sentiment_raw["period_a"],
        period_b=sentiment_raw["period_b"],
        window=sentiment_raw["window"],
        delta=sentiment_raw.get("delta"),
        a=to_signal_out(sentiment_raw.get("a")),
        b=to_signal_out(sentiment_raw.get("b")),
        note=sentiment_raw.get("note"),
    )

    return AskResponse(
        company=company,
        period_a=payload.period_a,
        period_b=payload.period_b,
        sentiment=sentiment,
        claims_a=[to_claim_out(r) for r in claims_a_raw],
        claims_b=[to_claim_out(r) for r in claims_b_raw],
        freshness=freshness,
    )