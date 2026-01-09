from datetime import datetime, timezone

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from graph.db import get_neo4j_driver
from graph.schema import ensure_schema
from graph.upsert import (
    upsert_company,
    upsert_event,
    upsert_source,
    link_source_mentions_company,
    upsert_claim,
    upsert_signal,
)
from extract.contracts import SourceDoc


def main():
    driver = get_neo4j_driver()
    ensure_schema(driver)

    company_id = upsert_company(driver, "NVIDIA", "NVDA")
    ev_latest = upsert_event(driver, company_id, period="Q3-2025", event_date=datetime(2025, 11, 20, tzinfo=timezone.utc))
    ev_prev = upsert_event(driver, company_id, period="Q2-2025", event_date=datetime(2025, 8, 21, tzinfo=timezone.utc))

    doc1 = SourceDoc(
        url="https://example.com/nvda-earnings-recap",
        title="NVIDIA earnings recap",
        raw_text="NVIDIA posted strong results and raised guidance...",
        source_type="news",
        #fetched_at=datetime.now(timezone.utc),
        fetched_at=datetime(2023, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        published_at=datetime(2025, 11, 20, tzinfo=timezone.utc),
        query="nvidia earnings Q3 2025 recap",
        site_name="Example News",
    )
    src1 = upsert_source(driver, doc1)
    link_source_mentions_company(driver, src1, company_id)

    upsert_claim(
        driver,
        company_id=company_id,
        event_id=ev_latest,
        source_id=src1,
        text="Guidance was raised for next quarter.",
        claim_type="guidance",
        confidence=0.85,
    )
    upsert_claim(
        driver,
        company_id=company_id,
        event_id=ev_latest,
        source_id=src1,
        text="AI/data center demand remained strong.",
        claim_type="demand",
        confidence=0.80,
    )

    upsert_signal(driver, company_id, ev_latest, "sentiment", score=0.62, volume=1200, window="post_earnings_7d")
    upsert_signal(driver, company_id, ev_prev, "sentiment", score=0.41, volume=900, window="post_earnings_7d")

    print("Seed complete.")
    driver.close()


if __name__ == "__main__":
    main()