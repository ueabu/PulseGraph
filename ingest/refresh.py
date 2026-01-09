from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from neo4j import Driver

from extract.contracts import SourceDoc
from graph.upsert import upsert_source, link_source_mentions_company

from ingest.brightdata import google_serp_urls, unlock_to_markdown


def _earnings_query(company_name: str, period: str) -> str:
    # Simple, effective first pass. You can tune later.
    return f'{company_name} {period} earnings recap guidance revenue EPS reaction'


def refresh_company_period(
    driver: Driver,
    company_id: str,
    company_name: str,
    period: str,
    source_types: Optional[List[str]] = None,
) -> Dict:
    source_types = source_types or ["news"]

    # 1) Discover URLs via SERP (use Google News vertical to bias toward coverage)
    serp_query = _earnings_query(company_name, period)
    serp_results = google_serp_urls(serp_query, max_results=8, tbm="nws")

    # 2) Fetch pages via Unlocker (markdown), normalize to SourceDoc, upsert
    upserted = 0
    docs: List[SourceDoc] = []
    errors: List[Dict] = []

    for r in serp_results:
        try:
            md = unlock_to_markdown(r.url, country="us")
            doc = SourceDoc(
                url=r.url,
                title=r.title or r.url,
                raw_text=md,
                source_type="news",
                fetched_at=datetime.now(timezone.utc),
                query=serp_query,
                site_name=None,
                metadata={
                    "serp_title": r.title,
                    "serp_description": r.description,
                    "serp_rank": r.rank,
                },
            )
            docs.append(doc)

            source_id = upsert_source(driver, doc)
            link_source_mentions_company(driver, source_id, company_id)
            upserted += 1
        except Exception as e:
            errors.append({"url": r.url, "error": str(e)})

    return {
        "company": company_name,
        "period": period,
        "query": serp_query,
        "discovered_urls": len(serp_results),
        "fetched_docs": len(docs),
        "upserted_sources": upserted,
        "errors": errors[:3],  # keep response small
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }
