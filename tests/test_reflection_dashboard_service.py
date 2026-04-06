import threading
import time
from unittest.mock import MagicMock
import pytest
from agent.reflection_dashboard_service import ReflectionDashboardService

def test_proposal_caching_ttl():
    pipeline = MagicMock()
    # Mock generate_proposals to return a list and track calls
    pipeline.generate_proposals.return_value = [{"proposal_id": "p1"}]

    service = ReflectionDashboardService(pipeline, proposals_ttl_s=1.0)

    # First call should trigger generation
    p1 = service._get_proposals()
    assert len(p1) == 1
    assert pipeline.generate_proposals.call_count == 1

    # Second call within TTL should NOT trigger generation
    p2 = service._get_proposals()
    assert p2 == p1
    assert pipeline.generate_proposals.call_count == 1

    # Wait for TTL to expire
    time.sleep(1.1)

    # Third call after TTL should trigger generation
    p3 = service._get_proposals()
    assert pipeline.generate_proposals.call_count == 2

def test_cache_invalidation_on_action():
    pipeline = MagicMock()
    pipeline.generate_proposals.return_value = [{"proposal_id": "p1"}]
    pipeline.cognitive_state = {}

    service = ReflectionDashboardService(pipeline, proposals_ttl_s=60.0)

    service._get_proposals()
    assert pipeline.generate_proposals.call_count == 1

    # Approve should invalidate cache
    service.approve({"proposal_id": "p1"})

    service._get_proposals()
    assert pipeline.generate_proposals.call_count == 2

def test_concurrent_proposal_generation():
    pipeline = MagicMock()

    def slow_generate():
        time.sleep(0.5)
        return [{"proposal_id": "p1"}]

    pipeline.generate_proposals.side_effect = slow_generate

    service = ReflectionDashboardService(pipeline, proposals_ttl_s=60.0)

    # Use multiple threads to call _get_proposals
    results = []
    def call_get():
        results.append(service._get_proposals())

    threads = [threading.Thread(target=call_get) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # generate_proposals should only be called once
    assert pipeline.generate_proposals.call_count == 1
    assert len(results) == 5
    for r in results:
        assert r == [{"proposal_id": "p1"}]
