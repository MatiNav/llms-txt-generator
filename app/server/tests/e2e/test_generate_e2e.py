import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from server.main import app
from shared.db.engine import get_engine


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.integration,
]


async def test_generate_coalesces_concurrent_requests(
    clean_database, mock_sqs_dependency
) -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        responses = await asyncio.gather(
            client.post("/api/generate", json={"url": "https://example.com/docs"}),
            client.post("/api/generate", json={"url": "example.com/other"}),
        )

    payloads = [response.json() for response in responses]
    run_ids = {payload["run_id"] for payload in payloads}
    coalesced_values = sorted(payload["coalesced"] for payload in payloads)

    assert [response.status_code for response in responses] == [200, 200]
    assert len(run_ids) == 1
    assert coalesced_values == [False, True]

    engine = get_engine()
    async with engine.connect() as connection:
        query_result = await connection.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM sites) AS sites_count,
                    (SELECT COUNT(*) FROM runs) AS runs_count,
                    (SELECT COUNT(*) FROM runs WHERE state IN ('discovering','processing')) AS inflight_count
                """
            )
        )
        counts = query_result.mappings().first()

    assert counts is not None
    assert counts["sites_count"] == 1
    assert counts["runs_count"] == 1
    assert counts["inflight_count"] == 1


async def test_generate_rejects_invalid_url(
    clean_database, mock_sqs_dependency
) -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/generate", json={"url": "https://"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid URL: host is required"
