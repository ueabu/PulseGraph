from __future__ import annotations

from neo4j import Driver


def ensure_schema(driver: Driver) -> None:
    """
    Creates constraints/indexes. Safe to call multiple times.
    """
    statements = [
        # Uniqueness constraints
        "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE",
        "CREATE CONSTRAINT source_id IF NOT EXISTS FOR (s:Source) REQUIRE s.id IS UNIQUE",
        "CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (cl:Claim) REQUIRE cl.id IS UNIQUE",
        "CREATE CONSTRAINT signal_id IF NOT EXISTS FOR (sg:Signal) REQUIRE sg.id IS UNIQUE",

        # Helpful indexes (search / filtering)
        "CREATE INDEX company_name IF NOT EXISTS FOR (c:Company) ON (c.name)",
        "CREATE INDEX event_period IF NOT EXISTS FOR (e:Event) ON (e.period)",
        "CREATE INDEX source_type IF NOT EXISTS FOR (s:Source) ON (s.source_type)",
        "CREATE INDEX claim_type IF NOT EXISTS FOR (cl:Claim) ON (cl.claim_type)",
    ]

    with driver.session() as session:
        for stmt in statements:
            session.run(stmt)