from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

ClaimType = Literal["revenue", "eps", "guidance", "margin", "demand", "risk", "product", "other"]
Direction = Literal["up", "down", "flat", "mixed", "unknown"]

class ClaimOut(BaseModel):
    text: str
    claim_type: ClaimType = "other"
    direction: Direction = "unknown"
    timeframe: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    evidence: str = ""

class ClaimsPayload(BaseModel):
    claims: List[ClaimOut]
