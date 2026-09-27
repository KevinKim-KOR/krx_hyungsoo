"""POC3-07 OCI 기동 상태 읽기 모듈 단위 테스트 (검증자 REJECTED r1 B-6 반영).

실제 SSH 를 하지 않는다 — _ssh_read·require_env 를 monkeypatch 로 통제한다.

검증 계약:
  - 필수 push-kind 3종(운영 3종: 시장·보유·장중 급등락) 모두 등록 → OPERATING.
    POC3-02D-OPS-01 C2: 폐지된 spike 대신 holdings_risk_alert 가 필수다.
  - 일부 push-kind 누락 → DEGRADED(누락 목록 표시). "하나만 있어도 OPERATING" 정정.
  - 등록된 runner 없음 → UNKNOWN.
  - 접속 실패/ENV 미설정 → reachable=False, overall=UNKNOWN(기동 안 막음).
  - 읽어온 stat 값(holdings·runtime)이 job detail 에 실제로 반영된다(미사용 정정).
"""

from __future__ import annotations

import app.oci_startup_status as mod


def test_classify_all_kinds_operating():
    overall, missing = mod._classify_schedule(
        {"market_briefing", "holdings_briefing", "holdings_risk_alert"}
    )
    assert overall == "OPERATING"
    assert missing == []


def test_classify_partial_degraded():
    overall, missing = mod._classify_schedule({"market_briefing"})
    assert overall == "DEGRADED"
    assert "holdings_briefing" in missing
    assert "holdings_risk_alert" in missing


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
        "holdings_briefing\nholdings_risk_alert\nmarket_briefing\n"
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
    out = "holdings_risk_alert\nmarket_briefing\n###\n0\n0 0"
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


# ── POC3-02D-OPS-01 C2 — 폐지 spike 필수 판정 정정 ─────────────────────────────


def test_refresh_operating_current_cron_shape(monkeypatch):
    # 지금 OCI cron 모양(2026-09 교체 뒤 · sort -u 결과) → OPERATING(재발 방지).
    out = (
        "holdings_briefing\nholdings_risk_alert\nmarket_briefing\n"
        "###\n"
        "1754400000\n"
        "1754400500 167936"
    )
    _patch_ssh(monkeypatch, out)
    snap = mod.refresh_snapshot()
    assert snap.overall == "OPERATING"
    assert snap.summary_line == (
        "OCI 자동 운영 스케줄 활성 (필수 3종 등록 · 기동 시 확인)"
    )
    cron = [j for j in snap.jobs if j.job == "crontab"][0]
    assert cron.status == "SUCCESS"
    assert cron.detail == "필수 스케줄(시장·보유·급등락) 모두 등록됨"


def test_refresh_degraded_old_cron_shape_missing_risk_alert(monkeypatch):
    # 옛 cron 모양(시장·보유·spike) → holdings_risk_alert 누락 DEGRADED.
    old_kinds = {"market_briefing", "holdings_briefing", "spike_or_falling_alert"}
    overall, missing = mod._classify_schedule(old_kinds)
    assert overall == "DEGRADED"
    assert missing == ["holdings_risk_alert"]

    out = "holdings_briefing\nmarket_briefing\nspike_or_falling_alert\n###\n0\n0 0"
    _patch_ssh(monkeypatch, out)
    snap = mod.refresh_snapshot()
    assert snap.overall == "DEGRADED"
    assert snap.summary_line == (
        "OCI 스케줄 일부 누락: holdings_risk_alert (기동 시 확인)"
    )
    cron = [j for j in snap.jobs if j.job == "crontab"][0]
    assert cron.status == "STALE"
    assert cron.detail == "일부 스케줄 누락: holdings_risk_alert"


def test_classify_all_four_kinds_operating():
    # spike 줄이 다시 생겨도 필수 목록 밖이라 무시한다 → OPERATING.
    overall, missing = mod._classify_schedule(
        {
            "market_briefing",
            "holdings_briefing",
            "holdings_risk_alert",
            "spike_or_falling_alert",
        }
    )
    assert overall == "OPERATING"
    assert missing == []


def test_required_push_kinds_contract():
    # 필수 목록 = 운영 3종 · 폐지 spike 제외 · 러너 공통 VALID_PUSH_KINDS 의 부분집합.
    #   패키지용 scripts/three_push_oci_helpers.py 의 같은 이름 상수는
    #   holdings_risk_alert 를 포함하지 않으므로 대조 기준으로 쓰지 않는다.
    from app.three_push_runner_common import VALID_PUSH_KINDS

    required = set(mod._REQUIRED_PUSH_KINDS)
    assert required == {"market_briefing", "holdings_briefing", "holdings_risk_alert"}
    assert len(mod._REQUIRED_PUSH_KINDS) == 3
    assert "spike_or_falling_alert" not in required
    assert required <= set(VALID_PUSH_KINDS)
