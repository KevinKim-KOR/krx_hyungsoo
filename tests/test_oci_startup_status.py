"""POC3-07 OCI 기동 상태 읽기 모듈 단위 테스트 (검증자 REJECTED r1 B-6 반영).

실제 SSH 를 하지 않는다 — _ssh_read·require_env 를 monkeypatch 로 통제한다.

검증 계약:
  - 필수 push-kind 3종 모두 등록 → OPERATING.
  - 일부 push-kind 누락 → DEGRADED(누락 목록 표시). "하나만 있어도 OPERATING" 정정.
  - 등록된 runner 없음 → UNKNOWN.
  - 접속 실패/ENV 미설정 → reachable=False, overall=UNKNOWN(기동 안 막음).
  - 읽어온 stat 값(holdings·runtime)이 job detail 에 실제로 반영된다(미사용 정정).
"""

from __future__ import annotations

import app.oci_startup_status as mod


def test_classify_all_kinds_operating():
    overall, missing = mod._classify_schedule(
        {"market_briefing", "holdings_briefing", "spike_or_falling_alert"}
    )
    assert overall == "OPERATING"
    assert missing == []


def test_classify_partial_degraded():
    overall, missing = mod._classify_schedule({"market_briefing"})
    assert overall == "DEGRADED"
    assert "holdings_briefing" in missing
    assert "spike_or_falling_alert" in missing


def test_classify_empty_unknown():
    overall, missing = mod._classify_schedule(set())
    assert overall == "UNKNOWN"
    assert set(missing) == set(mod._REQUIRED_PUSH_KINDS)


def _patch_ssh(monkeypatch, out: str, ok: bool = True):
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")
    monkeypatch.setattr(mod, "_ssh_read", lambda cmd: (ok, out))


def test_refresh_operating_uses_stat_values(monkeypatch):
    # 필수 3종 등록 + holdings/runtime stat 값 제공.
    out = (
        "holdings_briefing\nmarket_briefing\nspike_or_falling_alert\n"
        "###\n"
        "1754400000\n"
        "1754400500 167936"
    )
    _patch_ssh(monkeypatch, out)
    snap = mod.refresh_snapshot()
    assert snap.reachable is True
    assert snap.overall == "OPERATING"
    assert snap.crontab_active is True
    # 읽어온 stat 값이 job detail 에 반영된다(미사용 정정).
    details = " ".join(j.detail for j in snap.jobs)
    assert "167936 bytes" in details
    assert "holdings 소스 최근 수정" in details
    # 개별 PUSH job 은 여전히 UNKNOWN(Q5).
    push = [j for j in snap.jobs if j.job == "push_job_results"][0]
    assert push.status == "UNKNOWN"


def test_refresh_degraded_when_kind_missing(monkeypatch):
    # holdings_briefing 누락 → DEGRADED.
    out = "market_briefing\nspike_or_falling_alert\n###\n0\n0 0"
    _patch_ssh(monkeypatch, out)
    snap = mod.refresh_snapshot()
    assert snap.overall == "DEGRADED"
    assert "holdings_briefing" in snap.summary_line
    # crontab job 은 STALE 로 누락을 알린다.
    cron = [j for j in snap.jobs if j.job == "crontab"][0]
    assert cron.status == "STALE"
    assert "holdings_briefing" in cron.detail


def test_refresh_unknown_when_no_runner(monkeypatch):
    out = "###\n0\n0 0"
    _patch_ssh(monkeypatch, out)
    snap = mod.refresh_snapshot()
    assert snap.overall == "UNKNOWN"
    assert snap.crontab_active is False


def test_refresh_connection_fail_unknown_not_blocking(monkeypatch):
    _patch_ssh(monkeypatch, "", ok=False)
    snap = mod.refresh_snapshot()
    assert snap.reachable is False
    assert snap.overall == "UNKNOWN"
    # 기동을 막지 않는다 = 예외 없이 스냅샷 반환.


def test_refresh_no_env_skips(monkeypatch):
    def _raise(_k):
        raise RuntimeError("no env")

    monkeypatch.setattr(mod, "require_env", _raise)
    snap = mod.refresh_snapshot()
    assert snap.reachable is False
    assert snap.overall == "UNKNOWN"
    assert "미설정" in snap.summary_line
