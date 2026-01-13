from __future__ import annotations

from typing import List
from openai import OpenAI

from extract.contracts import SourceDoc, Claim
from extract.schemas import ClaimsPayload

def extract_claims_from_source_openai(
    *,
    client: OpenAI,
    company_name: str,
    period: str,
    source: SourceDoc,
    model: str = "gpt-4o-mini",
    max_chars: int = 12000,
) -> List[Claim]:
    # Keep it simple: trim content so calls stay fast/cheap
    text = source.raw_text[:max_chars]

    prompt = f"""
        Extract earnings-related claims for a knowledge graph.

        Company: {company_name}
        Period: {period}
        Source title: {source.title}
        Source URL: {source.url}

        Rules:
        - Extract only claims grounded in the text.
        - Evidence must be an exact short quote from the text.
        - Max 10 claims.
"""

    resp = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": "You extract structured claims from business articles."},
            {"role": "user", "content": prompt},
            {"role": "user", "content": f"TEXT:\n{text}"},
        ],
        text_format=ClaimsPayload,  # <-- schema-enforced structured output
        temperature=0.2,
        max_output_tokens=900,
    )

    payload: ClaimsPayload = resp.output_parsed

    claims: List[Claim] = []
    for c in payload.claims:
        claims.append(
            Claim(
                company_name=company_name,
                period=period,
                text=c.text,
                claim_type=c.claim_type,
                direction=c.direction,
                timeframe=c.timeframe,
                value=c.value,
                unit=c.unit,
                confidence=c.confidence,
                evidence=c.evidence,
                source_url=source.url,
                source_title=source.title,
            )
        )

    return claims
