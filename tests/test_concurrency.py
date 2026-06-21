import asyncio
import pytest
import time
from httpx import AsyncClient


@pytest.mark.asyncio
async def testConcurrentFeedRequests(verifiedClient: AsyncClient):
    import os
    # Number of concurrent requests to fire
    concurrencyCount = int(os.getenv("TEST_CONCURRENCY", "100"))

    # Helper function to perform a single request and capture latency
    async def performRequest():
        startTime = time.perf_counter()
        response = await verifiedClient.get("/feed/nearby?limit=5")
        latency = time.perf_counter() - startTime
        return response, latency

    # Fire all requests concurrently using asyncio.gather
    startTime = time.perf_counter()
    results = await asyncio.gather(*(performRequest() for _ in range(concurrencyCount)))
    totalDuration = time.perf_counter() - startTime

    # Verify all requests succeeded with 200 OK
    latencies = []
    for response, latency in results:
        assert response.status_code == 200
        latencies.append(latency)

    # Calculate dynamic latency threshold limit based on concurrency count (100ms baseline + 7ms per concurrent request)
    limitMs = max(250, 100 + concurrencyCount * 7)
    limitSeconds = limitMs / 1000.0

    avgLatency = sum(latencies) / len(latencies)
    print(f"\n[LoadTest] Concurrency: {concurrencyCount} parallel requests")
    print(f"[LoadTest] Limit threshold: {limitSeconds}s")
    print(f"[LoadTest] Total duration: {totalDuration:.4f}s")
    print(f"[LoadTest] Avg request latency: {avgLatency:.4f}s")

    # Export metrics for report card integration
    import json
    concurrencyMetrics = {
        "concurrency": concurrencyCount,
        "limit": limitMs,
        "avgLatency": int(avgLatency * 1000)
    }
    metricsPath = os.path.join(os.path.dirname(__file__), "concurrency_metrics.json")
    with open(metricsPath, "w") as f:
        json.dump(concurrencyMetrics, f)

    assert avgLatency < limitSeconds, f"Average concurrent latency took too long: {avgLatency:.4f}s (max {limitSeconds}s)"
