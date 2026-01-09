from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import requests


BRIGHTDATA_REQUEST_URL = "https://api.brightdata.com/request"


@dataclass
class SerpResult:
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    rank: Optional[int] = None


def _headers() -> Dict[str, str]:
    api_key = os.getenv("BRIGHTDATA_API_KEY")
    if not api_key:
        raise RuntimeError("Missing BRIGHTDATA_API_KEY")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def google_serp_urls(
    query: str,
    *,
    max_results: int = 8,
    gl: str = "us",
    hl: str = "en",
    tbm: Optional[str] = None,  # e.g. "nws" for Google News vertical
) -> List[SerpResult]:
    """
    Uses Bright Data SERP API to discover relevant URLs.

    We request a parsed JSON SERP by appending brd_json=1 to the target URL.
    Bright Data supports JSON SERP structure using brd_json=1. :contentReference[oaicite:3]{index=3}
    """
    zone = os.getenv("BRIGHTDATA_SERP_ZONE")
    if not zone:
        raise RuntimeError("Missing BRIGHTDATA_SERP_ZONE")

    q = quote_plus(query)
    base = f"https://www.google.com/search?q={q}&gl={gl}&hl={hl}&brd_json=1"
    if tbm:
        base += f"&tbm={tbm}"

    payload = {
        "zone": zone,
        "url": base,
        "format": "raw",
    }

    resp = requests.post(BRIGHTDATA_REQUEST_URL, headers=_headers(), json=payload, timeout=90)
    resp.raise_for_status()

    # When using brd_json=1, the response is typically JSON.
    data = resp.json()

    # Be defensive: field names can vary based on engine/format.
    candidates = []
    for key in ("organic", "organic_results", "results", "search_results"):
        v = data.get(key)
        if isinstance(v, list):
            candidates = v
            break

    results: List[SerpResult] = []
    for item in candidates[: max_results * 2]:  # allow some filtering
        link = item.get("link") or item.get("url") or item.get("href")
        if not link or not isinstance(link, str):
            continue
        # filter obvious junk
        if link.startswith("/"):
            continue

        results.append(
            SerpResult(
                url=link,
                title=item.get("title"),
                description=item.get("description") or item.get("snippet"),
                rank=item.get("rank"),
            )
        )
        if len(results) >= max_results:
            break

    return results


def unlock_to_markdown(url: str, *, country: str = "us") -> str:
    """
    Uses Bright Data Unlocker API to fetch page content reliably.
    The REST endpoint supports payload fields like zone/url/format/method/country/data_format. :contentReference[oaicite:4]{index=4}
    """
    zone = os.getenv("BRIGHTDATA_UNLOCKER_ZONE")
    if not zone:
        raise RuntimeError("Missing BRIGHTDATA_UNLOCKER_ZONE")

    payload = {
        "zone": zone,
        "url": url,
        "format": "json",
        "method": "GET",
        "country": country,
        "data_format": "markdown",
    }

    resp = requests.post(BRIGHTDATA_REQUEST_URL, headers=_headers(), json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    # Different responses may embed content under different keys; handle common ones.
    for key in ("data", "content", "markdown", "result", "body"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val

    # Last resort: if API returns the raw content at top-level
    if isinstance(data, str):
        return data

    raise RuntimeError(f"Unlocker response missing markdown content for {url}. Keys: {list(data.keys())}")
