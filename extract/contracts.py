from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
import hashlib


def _stable_id_from_url(url: str) -> str:
    """
    Stable ID derived from URL for idempotent upserts.
    """
    normalized = url.strip()
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