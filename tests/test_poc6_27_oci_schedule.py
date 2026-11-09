"""POC6-27 — OCI 기동 스냅샷의 필수 3종 예약 칸(`schedule`) · 실제 SSH 없음.

계약 출처: POC6-27 PLAN V1 쟁점 3 · 설계자 PLAN 판정 §4(예약별 상태는 기동 때 이미 읽은 스냅샷에서 구분 ·
확인 실패를 예약 누락으로 세지 않는다 · OCI 재조회 없음).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.oci_startup_status as mod

ALL = "holdings_briefing\nholdings_risk_alert\nmarket_briefing\n###\n0\n0 0"


@pytest.fixture(autouse=True)
def _keep_snapshot(monkeypatch):
    # 모듈 전역 스냅샷을 시험 뒤 되돌린다(다른 시험 · 앱에 남기지 않음).
    monkeypatch.setattr(mod, "_snapshot", mod.OciStartupSnapshot())


def _refresh(monkeypatch, out: str, ok: bool = True):
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")
    monkeypatch.setattr(mod, "_ssh_read", lambda cmd: (ok, out))
    return mod.refresh_snapshot()


def _states(snap):
    return {r["kind"]: r["state"] for r in mod.schedule_rows(snap)}


def test_all_registered(monkeypatch):
    snap = _refresh(monkeypatch, ALL)
    assert snap.scheduled_kinds == [
        "holdings_briefing",
        "holdings_risk_alert",
        "market_briefing",
    ]
    rows = mod.schedule_rows(snap)
    assert [(r["kind"], r["label"], r["state"]) for r in rows] == [
        ("market_briefing", "시장 브리핑", "registered"),
        ("holdings_briefing", "보유 브리핑", "registered"),
        ("holdings_risk_alert", "장중 급등락", "registered"),
    ]


def test_one_missing(monkeypatch):
    snap = _refresh(monkeypatch, "holdings_risk_alert\nmarket_briefing\n###\n0\n0 0")
    assert snap.overall == "DEGRADED"
    assert _states(snap) == {
        "market_briefing": "registered",
        "holdings_briefing": "missing",
        "holdings_risk_alert": "registered",
    }


def test_extra_kind_ignored(monkeypatch):
    snap = _refresh(monkeypatch, "spike_or_falling_alert\n" + ALL)
    assert set(_states(snap).values()) == {"registered"}
    assert "spike_or_falling_alert" in snap.scheduled_kinds


def test_none_registered_is_unknown_not_missing(monkeypatch):
    snap = _refresh(monkeypatch, "###\n0\n0 0")
    assert snap.overall == "UNKNOWN" and snap.scheduled_kinds == []
    assert set(_states(snap).values()) == {"unknown"}


def test_ssh_failure_is_unknown(monkeypatch):
    snap = _refresh(monkeypatch, "", ok=False)
    assert snap.reachable is False and snap.scheduled_kinds is None
    assert set(_states(snap).values()) == {"unknown"}


def test_env_missing_is_unknown(monkeypatch):
    def _raise(_k):
        raise RuntimeError("unset")

    monkeypatch.setattr(mod, "require_env", _raise)
    monkeypatch.setattr(
        mod, "_ssh_read", lambda cmd: pytest.fail("SSH 를 부르면 안 된다")
    )
    snap = mod.refresh_snapshot()
    assert snap.scheduled_kinds is None
    assert set(_states(snap).values()) == {"unknown"}


def test_kinds_kept_through_param_apply_replace(monkeypatch):
    _refresh(monkeypatch, ALL)
    mod.record_param_apply(None, "2026-11-09T10:00:00+09:00", unconfirmed=True)
    snap = mod.get_snapshot()
    assert snap.oci_param_source == "apply"
    assert set(_states(snap).values()) == {"registered"}


def test_get_endpoint_returns_schedule_without_ssh(monkeypatch):
    _refresh(monkeypatch, "holdings_risk_alert\nmarket_briefing\n###\n0\n0 0")
    monkeypatch.setattr(
        mod, "_ssh_read", lambda cmd: pytest.fail("GET 이 OCI 를 다시 읽으면 안 된다")
    )
    from app.api import app

    body = TestClient(app).get("/oci/startup-status").json()
    assert body["schedule"] == [
        {"kind": "market_briefing", "label": "시장 브리핑", "state": "registered"},
        {"kind": "holdings_briefing", "label": "보유 브리핑", "state": "missing"},
        {"kind": "holdings_risk_alert", "label": "장중 급등락", "state": "registered"},
    ]
    # 기존 칸 그대로
    assert body["overall"] == "DEGRADED" and "summary_line" in body and body["jobs"]


def test_get_endpoint_unknown_before_boot_read():
    from app.api import app

    body = TestClient(app).get("/oci/startup-status").json()
    assert [r["state"] for r in body["schedule"]] == ["unknown"] * 3
