from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Iterable, List, Optional, Dict, Any
import hashlib

from neo4j import Driver

from extract.contracts import SourceDoc, Claim


def _id(*parts: str) -> str:
    """
    Stable, short id based on semantic components.
    """
    s = "|".join(p.strip() for p in parts if p is not None)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:24]


def upsert_company(driver: Driver, name: str, ticker: Optional[str] = None) -> str:
    company_id = _id("company", name.lower(), (ticker or "").lower())
    now = datetime.utcnow().isoformat()

    cypher = """
    MERGE (c:Company {id: $id})
    ON CREATE SET c.name = $name,
                  c.ticker = $ticker,
                  c.created_at = $now,
                  c.last_updated_at = $now
    ON MATCH SET  c.name = $name,
                  c.ticker = $ticker,
                  c.last_updated_at = $now
    RETURN c.id AS id
    """
    with driver.session() as session:
        rec = session.run(cypher, id=company_id, name=name, ticker=ticker, now=now).single()
        return rec["id"]


def upsert_event(
    driver: Driver,
    company_id: str,
    period: str,
    event_type: str = "earnings",
    event_date: Optional[datetime] = None,
) -> str:
    event_id = _id("event", company_id, event_type, period)
    now = datetime.utcnow().isoformat()
    event_date_iso = event_date.isoformat() if event_date else None

    cypher = """
    MATCH (c:Company {id: $company_id})
    MERGE (e:Event {id: $id})
    ON CREATE SET e.type = $type,
                  e.period = $period,
                  e.event_date = $event_date,
                  e.created_at = $now,
                  e.last_updated_at = $now
    ON MATCH SET  e.type = $type,
                  e.period = $period,
                  e.event_date = coalesce($event_date, e.event_date),
                  e.last_updated_at = $now
    MERGE (c)-[:HAS_EVENT]->(e)
    RETURN e.id AS id
    """
    with driver.session() as session:
        rec = session.run(
            cypher,
            company_id=company_id,
            id=event_id,
            type=event_type,
            period=period,
            event_date=event_date_iso,
            now=now,
        ).single()
        return rec["id"]


def upsert_source(driver: Driver, doc: SourceDoc) -> str:
    now = datetime.utcnow().isoformat()
    published_at = doc.published_at.isoformat() if doc.published_at else None
    fetched_at = doc.fetched_at.isoformat()

    cypher = """
    MERGE (s:Source {id: $id})
    ON CREATE SET s.url = $url,
                  s.title = $title,
                  s.source_type = $source_type,
                  s.site_name = $site_name,
                  s.author = $author,
                  s.language = $language,
                  s.query = $search_query,
                  s.published_at = $published_at,
                  s.fetched_at = $fetched_at,
                  s.created_at = $now,
                  s.last_updated_at = $now
    ON MATCH SET  s.title = coalesce($title, s.title),
                  s.source_type = coalesce($source_type, s.source_type),
                  s.site_name = coalesce($site_name, s.site_name),
                  s.author = coalesce($author, s.author),
                  s.language = coalesce($language, s.language),
                  s.query = coalesce($search_query, s.query),
                  s.published_at = coalesce($published_at, s.published_at),
                  s.fetched_at = coalesce($fetched_at, s.fetched_at),
                  s.last_updated_at = $now
    RETURN s.id AS id
    """
    with driver.session() as session:
        rec = session.run(
            cypher,
            id=doc.source_id,
            url=doc.url,
            title=doc.title,
            source_type=doc.source_type,
            site_name=doc.site_name,
            author=doc.author,
            language=doc.language,
            search_query=doc.query,
            published_at=published_at,
            fetched_at=fetched_at,
            now=now,
        ).single()
        return rec["id"]


def link_source_mentions_company(driver: Driver, source_id: str, company_id: str) -> None:
    cypher = """
    MATCH (s:Source {id: $source_id}), (c:Company {id: $company_id})
    MERGE (s)-[:MENTIONS]->(c)
    """
    with driver.session() as session:
        session.run(cypher, source_id=source_id, company_id=company_id)


def upsert_claim(
    driver: Driver,
    company_id: str,
    event_id: str,
    source_id: str,
    text: str,
    claim_type: str,
    confidence: float,
) -> str:
    claim_id = _id("claim", company_id, event_id, text.lower())
    now = datetime.utcnow().isoformat()

    cypher = """
    MATCH (c:Company {id: $company_id})
    MATCH (e:Event {id: $event_id})
    MATCH (s:Source {id: $source_id})

    MERGE (cl:Claim {id: $id})
    ON CREATE SET cl.text = $text,
                  cl.claim_type = $claim_type,
                  cl.confidence = $confidence,
                  cl.created_at = $now,
                  cl.last_updated_at = $now
    ON MATCH SET  cl.text = $text,
                  cl.claim_type = $claim_type,
                  cl.confidence = $confidence,
                  cl.last_updated_at = $now

    MERGE (e)-[:HAS_CLAIM]->(cl)
    MERGE (s)-[:SUPPORTS]->(cl)
    MERGE (cl)-[:ABOUT]->(c)

    RETURN cl.id AS id
    """
    with driver.session() as session:
        rec = session.run(
            cypher,
            company_id=company_id,
            event_id=event_id,
            source_id=source_id,
            id=claim_id,
            text=text,
            claim_type=claim_type,
            confidence=confidence,
            now=now,
        ).single()
        return rec["id"]


def upsert_signal(
    driver: Driver,
    company_id: str,
    event_id: str,
    signal_type: str,
    score: float,
    volume: int,
    window: str,  # e.g. "post_earnings_7d"
    computed_at: Optional[datetime] = None,
) -> str:
    computed_at = computed_at or datetime.utcnow()
    signal_id = _id("signal", company_id, event_id, signal_type, window)
    computed_at_iso = computed_at.isoformat()

    cypher = """
    MATCH (c:Company {id: $company_id})
    MATCH (e:Event {id: $event_id})

    MERGE (sg:Signal {id: $id})
    ON CREATE SET sg.signal_type = $signal_type,
                  sg.score = $score,
                  sg.volume = $volume,
                  sg.window = $window,
                  sg.computed_at = $computed_at
    ON MATCH SET  sg.score = $score,
                  sg.volume = $volume,
                  sg.computed_at = $computed_at

    MERGE (sg)-[:ABOUT]->(c)
    MERGE (sg)-[:IN_WINDOW]->(e)

    RETURN sg.id AS id
    """
    with driver.session() as session:
        rec = session.run(
            cypher,
            company_id=company_id,
            event_id=event_id,
            id=signal_id,
            signal_type=signal_type,
            score=score,
            volume=volume,
            window=window,
            computed_at=computed_at_iso,
        ).single()
        return rec["id"]
    
    
def upsert_claim_and_links(
    driver,
    *,
    company_id: str,
    source_id: str,
    period: str,
    claim: Claim,
):
    cypher = """
    MERGE (cl:Claim {id: $claim_id})
    SET cl.text = $text,
        cl.claim_type = $claim_type,
        cl.direction = $direction,
        cl.timeframe = $timeframe,
        cl.value = $value,
        cl.unit = $unit,
        cl.confidence = $confidence,
        cl.evidence = $evidence

    WITH cl
    MATCH (c:Company {id: $company_id})
    MATCH (s:Source {id: $source_id})

    MERGE (c)-[:HAS_CLAIM {period: $period}]->(cl)
    MERGE (s)-[:SUPPORTS]->(cl)
    """

    params = {
        "claim_id": claim.claim_id,
        "text": claim.text,
        "claim_type": claim.claim_type,
        "direction": claim.direction,
        "timeframe": claim.timeframe,
        "value": claim.value,
        "unit": claim.unit,
        "confidence": claim.confidence,
        "evidence": claim.evidence,
        "company_id": company_id,
        "source_id": source_id,
        "period": period,
    }

    with driver.session() as session:
        session.run(cypher, params)