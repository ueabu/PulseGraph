# from __future__ import annotations
# from dataclasses import dataclass, field
# from datetime import datetime
# from typing import Any, Dict, Optional
# import hashlib


# def _stable_id_from_url(url: str) -> str:
#     """
#     Stable ID derived from URL for idempotent upserts.
#     """
#     normalized = url.strip()
#     return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


# @dataclass(frozen=True)
# class SourceDoc:
#     """
#     Normalized document produced by ingestion.

#     Everything downstream (extraction, graph upserts) should depend on THIS shape,
#     not on Bright Data's raw response format.
#     """
#     url: str
#     title: str
#     raw_text: str

#     source_type: str  # "news" | "blog" | "forum" | "social" | "docs" | "other"
#     fetched_at: datetime

#     published_at: Optional[datetime] = None
#     query: Optional[str] = None

#     # Optional fields (useful for debugging/traceability)
#     site_name: Optional[str] = None
#     author: Optional[str] = None
#     language: Optional[str] = None

#     # Raw payloads (optional)
#     raw_html: Optional[str] = None
#     metadata: Dict[str, Any] = field(default_factory=dict)

#     @property
#     def source_id(self) -> str:
#         return _stable_id_from_url(self.url)

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, List, Literal
import hashlib


def _stable_id_from_url(url: str) -> str:
    """
    Stable ID derived from URL for idempotent upserts.
    """
    normalized = url.strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def _stable_id_from_text(*parts: str) -> str:
    """
    Stable ID derived from normalized text fields for idempotent upserts.
    Use this for Claim IDs (company + timeframe + type + normalized text).
    """
    normalized = " | ".join(p.strip().lower() for p in parts if p is not None).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class SourceDoc:
    """
    Normalized document produced by ingestion.

    Everything downstream (extraction, graph upserts) should depend on THIS shape,
    not on Bright Data's raw response format.
    """
    url: str
    title: str
    raw_text: str

    source_type: str  # "news" | "blog" | "forum" | "social" | "docs" | "other"
    fetched_at: datetime

    published_at: Optional[datetime] = None
    query: Optional[str] = None

    # Optional fields (useful for debugging/traceability)
    site_name: Optional[str] = None
    author: Optional[str] = None
    language: Optional[str] = None

    # Raw payloads (optional)
    raw_html: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def source_id(self) -> str:
        return _stable_id_from_url(self.url)


ClaimType = Literal[
    "revenue",
    "eps",
    "guidance",
    "margin",
    "cash_flow",
    "capex",
    "demand",
    "supply",
    "pricing",
    "product",
    "competition",
    "risk",
    "regulatory",
    "macro",
    "other",
]

Direction = Literal["up", "down", "flat", "mixed", "unknown"]


@dataclass(frozen=True)
class Claim:
    """
    A single structured claim extracted from a source document.

    This is the contract between:
      - LLM extraction
      - graph upsert (Neo4j)
      - any claim comparison logic

    Design goals:
      - idempotent (stable claim_id)
      - grounded (evidence snippet required)
      - minimal but useful
    """
    company_name: str
    period: str  # e.g. "Q3-2025" or your canonical period key

    text: str  # normalized claim statement
    claim_type: ClaimType = "other"
    timeframe: Optional[str] = None  # e.g. "Q3 FY2026", "next quarter", "FY2026"
    direction: Direction = "unknown"

    # Optional quantitative fields
    value: Optional[float] = None
    unit: Optional[str] = None  # "USD", "%", "bps", etc.

    confidence: float = 0.5

    # Grounding: short excerpt copied from the source text
    evidence: str = ""

    # Traceability
    source_url: Optional[str] = None
    source_title: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def claim_id(self) -> str:
        """
        Stable ID for idempotent upserts.

        We include company + period + type + timeframe + claim text.
        If timeframe is None, it becomes an empty string in the hash.
        """
        return _stable_id_from_text(
            self.company_name,
            self.period,
            self.claim_type,
            self.timeframe or "",
            self.text,
        )
