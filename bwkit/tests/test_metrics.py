from __future__ import annotations

from bwkit.core.metrics import Call, Metrics, iso_since, utcnow_iso


def test_roundtrip(bwkit_home):
    m = Metrics()
    m.record(Call(
        ts=utcnow_iso(), tool="markitdown", caller="cli", transport="cli",
        latency_ms=12, status="ok", error_code=None, error_class=None,
        input_hash="deadbeef",
    ))
    m.record(Call(
        ts=utcnow_iso(), tool="markitdown", caller="cli", transport="cli",
        latency_ms=9, status="error", error_code="conversion_failed",
        error_class="ToolError", input_hash="abc",
    ))

    recent = m.recent(limit=10)
    assert len(recent) == 2
    assert recent[0]["tool"] == "markitdown"

    summary = m.summary()
    assert summary == [{
        "tool": "markitdown", "total": 2, "ok": 1, "error": 1,
        "success_rate": 0.5, "p50_ms": summary[0]["p50_ms"], "p95_ms": summary[0]["p95_ms"],
    }]
    assert summary[0]["p50_ms"] in (9, 12)

    errs = m.errors()
    assert errs == [{"tool": "markitdown", "error_code": "conversion_failed", "count": 1}]


def test_iso_since_units():
    assert iso_since("24h").endswith("Z")
    assert iso_since("7d").endswith("Z")
    assert iso_since("30m").endswith("Z")
