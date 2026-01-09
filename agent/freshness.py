from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Any, Optional

THRESHOLDS = {
    "news": timedelta(hours=24),
    "blog": timedelta(hours=48),
    "forum": timedelta(hours=6),
    "social": timedelta(hours=6),
    "other": timedelta(hours=24),
}

def _parse_dt(dt_str: str) -> Optional[datetime]:
    if not dt_str:
        return None
    # handles "2026-01-09T01:45:54.769723+00:00" and Neo4j toString(datetime())
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

def freshness_check(latest_by_type: List[Dict[str, Any]]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    stale_types = []
    details = []

    for row in latest_by_type:
        stype = row.get("source_type") or "other"
        last = _parse_dt(row.get("last_fetched"))
        threshold = THRESHOLDS.get(stype, THRESHOLDS["other"])

        if last is None or (now - last) > threshold:
            stale_types.append(stype)

        details.append({
            "source_type": stype,
            "last_fetched": last.isoformat() if last else None,
            "threshold_hours": threshold.total_seconds() / 3600.0,
        })

    return {
        "was_stale": len(stale_types) > 0,
        "stale_types": sorted(set(stale_types)),
        "details": details,
        "checked_at": now.isoformat(),
    }

