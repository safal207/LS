from datetime import datetime, timedelta, timezone

from hexagon_core.belief.temporal_index import TemporalIndex


def test_temporal_index_basic():
    index = TemporalIndex()
    t1 = datetime.now(timezone.utc)
    t2 = t1 + timedelta(hours=1)

    index.add(t1, "a")
    index.add(t2, "b")

    result = index.query_range(t1, t2)
    assert "a" in result
    assert "b" in result


def test_temporal_index_remove():
    index = TemporalIndex()
    t1 = datetime.now(timezone.utc)

    index.add(t1, "x")
    index.remove(t1, "x")

    assert index.query_range(t1, t1) == []
