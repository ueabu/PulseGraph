from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from neo4j import Driver


def find_company_by_name(driver: Driver, name: str) -> Optional[Dict[str, Any]]:
    cypher = """
    MATCH (c:Company)
    WHERE toLower(c.name) = toLower($name)
    RETURN c { .id, .name, .ticker, .last_updated_at } AS company
    LIMIT 1
    """
    with driver.session() as session:
        rec = session.run(cypher, name=name).single()
        return rec["company"] if rec else None


def get_event(driver: Driver, company_id: str, period: str, event_type: str = "earnings") -> Optional[Dict[str, Any]]:
    cypher = """
    MATCH (c:Company {id: $company_id})-[:HAS_EVENT]->(e:Event)
    WHERE e.type = $event_type AND e.period = $period
    RETURN e { .id, .type, .period, .event_date, .last_updated_at } AS event
    LIMIT 1
    """
    with driver.session() as session:
        rec = session.run(cypher, company_id=company_id, period=period, event_type=event_type).single()
        return rec["event"] if rec else None


def get_claims_with_sources(
    driver: Driver,
    company_id: str,
    period: str,
    limit: int = 15,
) -> List[Dict[str, Any]]:
    cypher = """
    MATCH (c:Company {id: $company_id})-[:HAS_EVENT]->(e:Event {period: $period})
    MATCH (e)-[:HAS_CLAIM]->(cl:Claim)
    OPTIONAL MATCH (s:Source)-[:SUPPORTS]->(cl)

    WITH cl, collect(DISTINCT s{.url,.title,.source_type,.published_at,.fetched_at}) AS sources
    RETURN cl { .id, .text, .claim_type, .confidence, .last_updated_at, sources: sources } AS row
    ORDER BY cl.confidence DESC, cl.last_updated_at DESC
    LIMIT $limit
    """
    with driver.session() as session:
        rows = session.run(cypher, company_id=company_id, period=period, limit=limit)
        return [r["row"] for r in rows]


def get_signal(driver: Driver, company_id: str, period: str, window: str, signal_type: str = "sentiment") -> Optional[Dict[str, Any]]:
    cypher = """
    MATCH (c:Company {id: $company_id})-[:HAS_EVENT]->(e:Event {period: $period})
    MATCH (sg:Signal)-[:ABOUT]->(c)
    MATCH (sg)-[:IN_WINDOW]->(e)
    WHERE sg.signal_type = $signal_type AND sg.window = $window
    RETURN sg { .id, .signal_type, .score, .volume, .window, .computed_at } AS signal
    LIMIT 1
    """
    with driver.session() as session:
        rec = session.run(
            cypher,
            company_id=company_id,
            period=period,
            window=window,
            signal_type=signal_type,
        ).single()
        return rec["signal"] if rec else None


def get_sentiment_delta(
    driver: Driver,
    company_id: str,
    period_a: str,
    period_b: str,
    window: str = "post_earnings_7d",
) -> Dict[str, Any]:
    """
    Compare sentiment score for two periods.
    """
    a = get_signal(driver, company_id, period_a, window, "sentiment")
    b = get_signal(driver, company_id, period_b, window, "sentiment")

    if not a or not b:
        return {
            "period_a": period_a,
            "period_b": period_b,
            "window": window,
            "delta": None,
            "a": a,
            "b": b,
            "note": "Missing signal for one or both periods.",
        }

    return {
        "period_a": period_a,
        "period_b": period_b,
        "window": window,
        "delta": float(a["score"]) - float(b["score"]),
        "a": a,
        "b": b,
    }

def get_latest_fetch_by_type(driver: Driver, company_id: str, period: str) -> List[Dict[str, Any]]:
    cypher = """
    MATCH (c:Company {id: $company_id})-[:HAS_EVENT]->(e:Event {period: $period})
    MATCH (e)-[:HAS_CLAIM]->(cl:Claim)<-[:SUPPORTS]-(s:Source)
    WITH s.source_type AS source_type, max(datetime(s.fetched_at)) AS last_fetched
    RETURN source_type, toString(last_fetched) AS last_fetched
    """
    with driver.session() as session:
        rows = session.run(cypher, company_id=company_id, period=period)
        return [{"source_type": r["source_type"], "last_fetched": r["last_fetched"]} for r in rows]