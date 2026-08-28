"""System stats API tests: 验证 /api/system/stats 返回字段完整 + 缓存统计可用。"""

from app.llm.providers import cache_stats


def test_system_stats_shape(client):
    resp = client.get("/api/system/stats")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    for key in ("total_runs", "success_runs", "success_rate", "issues_found", "datasets", "avg_run_seconds"):
        assert key in data
    assert "cache" in data
    cache = data["cache"]
    for key in ("hits", "misses", "hit_rate", "size", "max_size"):
        assert key in cache


def test_cache_stats_hit_rate_computes():
    stats = cache_stats()
    assert set(stats) == {"hits", "misses", "hit_rate", "size", "max_size"}
    total = stats["hits"] + stats["misses"]
    if total:
        assert stats["hit_rate"] == round(stats["hits"] / total * 100, 1)
    else:
        assert stats["hit_rate"] == 0.0
