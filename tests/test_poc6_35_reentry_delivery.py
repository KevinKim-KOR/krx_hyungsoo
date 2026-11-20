"""POC6-35 — 장중 재진입 알림 누락(K2) 정정 · PLAN V1 §3 시나리오 ① ~ ⑮.

K2: 마지막 성공 전달 → 회복 → 대기 충족 재진입(= 이번 회차 **발송 후보**) → 구역
한도 · 전송 실패 · 부분 전송 · 발송 전 차단으로 본문 전달 실패 → 관측 저장이 그
행을 `continuous=True` 로 덮어 다음 회차부터 억제됐다.

정정(원안 A1 · 설계자 판정 2026-11-19): 관측 저장 두 곳(`merge_sector_entries` ·
`save_observation`)에 이번 회차 후보 `(ticker, state)` 를 넘겨, '회복 ∧ 마지막 전달
상태와 같음 ∧ 후보' 인 행은 회복 기록(`continuous=False`)을 유지한다. 대기로 억제된
재진입은 후보가 아니므로 예전처럼 `True`(K3 그대로).

보완 1(Q3): 전체 전송 성공인데 첫 상태 저장이 실패하면 뒤의 관측 저장이 같은 병합
(전달 필드 · `sent_today` +1 · 한 번만)을 대신 한다. 그 병합까지 실패하면 관측만 다시
쓴다(독립 검토 B-1). 보완 2(Q5): 다음 회차 판정은 그 회차의 활성 정책 재발송 대기다.

rig 는 OPS-02 시험(`test_poc3_02d_ops02_delivery_state`)의 `_Scenario` 를 그대로 쓴다.
상태 · 집계 · 위험 상태 파일은 tmp 경로(`DEFAULT_SECTOR_STATE_PATH` ·
`DEFAULT_TALLY_PATH` monkeypatch), Telegram · Naver 는 대역이다(`_live_guard`).

**다음 회차 본문 포함 여부는 전송기에 넘어간 본문 문자열로 직접 단언한다.** rig 의
`pending` 정의(`_delivered_of(entry) != s.state`)는 같은 상태 재진입을 대기로 보지
않아(PLAN §1-5 맹점) 여기서는 쓰지 않는다.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from tests import test_intraday_alert_flow_through as ft
from tests import test_poc3_02d_ops02_delivery_state as ops02

TODAY = ft.TODAY
AC, ER = ops02.AC, ops02.ER
U57, U710, D57 = ops02.U57, ops02.U710, ops02.D57
NAMES, ONE = ops02.NAMES, ops02.ONE

# 기존 rig fixture 재사용 — pytest 는 모듈 속성 이름으로 fixture 를 등록한다.
market_db = ft.market_db

REP9 = "대표9"  # T00009(사업군 S9) 의 본문 표기 — rig `_sectors()` 이름
FLAT = {"H00001": -1.0}
FILL3 = {"T00000": 5.0, "T00001": 5.0, "T00002": 5.0}  # 진입 회피 구역 3자리


def _run(sc, minutes, label, **kw):
    """`_Scenario.run` + 이번 회차 본문(`body`) · 조립 결과(`res`)를 붙인다."""
    n_sent, n_calls = len(sc.sender.calls), len(sc.calls)
    t = sc.run(minutes, label, **kw)
    t.body = sc.sender.calls[-1] if len(sc.sender.calls) > n_sent else ""
    t.res = sc.calls[-1][1] if len(sc.calls) > n_calls else None
    t.row9 = dict((sc.state() or {}).get("entries", {}).get("T00009") or {})
    return t


def _sent_with(t, *names):
    return t.status == "sent" and not t.partial and all(n in t.body for n in names)


def _suppressed(t):
    return (t.status, t.reason, t.body) == ("skipped", "no_new_or_worsened", "")


def _k2_prefix(sc, before_cut=None):
    """09:30 T00009 추격 주의 전달 → 10:30 회복 → 11:30 재진입(대기 120분 충족).

    11:30 는 T00000 ~ T00002 신규 3건이 같은 구역(진입 회피)을 먼저 채워 T00009 가
    구역 한도 3에 잘린다(PLAN §1-2 K2 고정 사례). `before_cut` 은 11:30 직전에 부른다.
    """
    sc.quotes(FLAT, {"T00009": 5.0})
    t0 = _run(sc, 0, "T1 전달")
    sc.quotes(FLAT, {})
    t60 = _run(sc, 60, "회복")
    sc.quotes(FLAT, {**FILL3, "T00009": 5.0})
    if before_cut is not None:
        before_cut()
    t120 = _run(sc, 120, "재진입 · 구역 한도 잘림")
    assert _sent_with(t0, REP9) and t0.delivery["T00009"] == (AC, "t+0")
    assert _suppressed(t60) and t60.row9["continuous"] is False
    assert t120.status == "sent" and REP9 not in t120.body
    assert all(ft._rep_name(t) in t120.body for t in FILL3)
    assert t120.res is not None
    assert ("T00009", AC) in {(s.ticker, s.state) for s in t120.res.changes.send}
    assert t120.delivery["T00009"] == (AC, "t+0") and t120.sent_today == 2
    return t0, t60, t120


def _fail_state_saves(monkeypatch, n):
    """`save_sector_state` 를 앞으로 n 번 실패시킨다(첫 저장 · 관측 저장 순)."""
    import app.runtime_evidence.sector_signal_state as sss

    real = sss.save_sector_state
    left = {"n": n}

    def _maybe(*a, **k):
        if left["n"] > 0:
            left["n"] -= 1
            raise OSError("POC6-35 주입: 상태 저장 실패")
        return real(*a, **k)

    monkeypatch.setattr(sss, "save_sector_state", _maybe)
    return left


# ═══ ① K2 고정 사례 — 구역 한도 잘림 → 다음 회차 본문 포함 ═══════════════════


def test_k2_reentry_cut_by_section_cap_is_sent_next_tick(
    monkeypatch, tmp_path, market_db
):
    """① AC1 — 잘린 재진입이 12:30 에 실리고, 재전달 뒤에는 AC2 대로 억제된다."""
    sc = ops02._Scenario("K2", monkeypatch, tmp_path, market_db, holdings=ONE)
    *_, t120 = _k2_prefix(sc)
    t180 = _run(sc, 180, "조건 유지 · 자리 있음")
    # 동작 먼저(변경 전 RED 의 원인이 '다음 회차 누락' 으로 드러나게) — 그다음 저장 값
    assert _sent_with(t180, REP9), "K2: 잘린 재진입이 다음 회차에 실리지 않았다"
    assert all(ft._rep_name(t) not in t180.body for t in FILL3)
    # 잘린 회차 상태: 회복 기록 유지(후보였는데 미전달) · 전달 필드 불변
    assert t120.observation["T00009"] == (AC, False), "K2: 잘린 재진입이 굳었다"
    assert t180.delivery["T00009"] == (AC, "t+180") and t180.sent_today == 3
    assert t180.observation["T00009"] == (AC, True)
    # AC2 — 재전달 뒤 지속 억제 · 해소 → 새 전달 기준 90분 재진입 억제 · 이후 지속 억제
    t210 = _run(sc, 210, "재전달 뒤 지속")
    sc.quotes(FLAT, FILL3)
    t240 = _run(sc, 240, "해소")
    sc.quotes(FLAT, {**FILL3, "T00009": 5.0})
    t270 = _run(sc, 270, "새 전달 기준 90분 재진입")
    t330 = _run(sc, 330, "그 뒤 지속")
    for t in (t210, t240, t270, t330):
        assert _suppressed(t), t.label
        assert t.delivery["T00009"] == (AC, "t+180") and t.sent_today == 3
    assert t240.observation["T00009"] == (AC, False)
    assert t270.observation["T00009"] == (AC, True)  # 대기 억제 = 후보 아님 → K3


# ═══ ② 재진입 회차 전송 실패 · 부분 전송 · 발송 전 차단 ══════════════════════


@pytest.mark.parametrize(
    "mode", ["telegram_send_error", "partial_delivery", "blocked_before_send"]
)
def test_k2_reentry_undelivered_by_send_outcome_is_retried(
    monkeypatch, tmp_path, market_db, mode
):
    """② Q1 — 본문에 실렸지만 전달 성공이 아닌 재진입도 다음 회차 후보다."""
    sc = ops02._Scenario(mode, monkeypatch, tmp_path, market_db, holdings=ONE)
    runner = sc.rig["runner"]
    sc.quotes(FLAT, {"T00009": 5.0})
    t0 = _run(sc, 0, "전달")
    sc.quotes(FLAT, {})
    _run(sc, 60, "회복")
    sc.quotes(FLAT, {"T00009": 5.0})
    real_check = runner.check_forbidden_wording
    if mode == "telegram_send_error":
        sc.sender._sent = False
    elif mode == "partial_delivery":
        sc.sender._partial = True
    else:
        monkeypatch.setattr(runner, "check_forbidden_wording", lambda text: "주입")
    t120 = _run(sc, 120, f"재진입 · {mode}")
    sc.sender._sent, sc.sender._partial = True, False
    monkeypatch.setattr(runner, "check_forbidden_wording", real_check)
    t180 = _run(sc, 180, "다음 회차 · 정상")
    t240 = _run(sc, 240, "지속")

    assert _sent_with(t0, REP9)
    if mode == "telegram_send_error":
        assert (t120.status, t120.reason) == ("failed", "telegram_send_error")
        assert REP9 in t120.body
    elif mode == "partial_delivery":
        assert t120.status == "sent" and t120.partial and REP9 in t120.body
    else:
        assert (t120.status, t120.reason) == ("failed", "forbidden_wording")
        assert t120.body == ""
    assert _sent_with(t180, REP9), "K2: 전달 못 한 재진입이 다음 회차에 억제됐다"
    assert "intraday_state_saved_by_observation" not in t120.record
    assert t120.delivery["T00009"] == (AC, "t+0") and t120.sent_today == 1
    assert t120.observation["T00009"] == (AC, False), "K2: 미전달 재진입이 굳었다"
    assert t180.delivery["T00009"] == (AC, "t+180") and t180.sent_today == 2
    assert _suppressed(t240) and t240.sent_today == 2


# ═══ ③ 보유 급등 재진입 — 「보유종목」 구역에서 급락 3건에 밀림 ═════════════════


def test_k2_held_surge_reentry_cut_by_held_drops_is_sent_next_tick(
    monkeypatch, tmp_path, market_db
):
    """③ Q2 — 같은 상태 파일 · 같은 판정을 쓰는 보유 급등에도 같은 정정이 적용된다."""
    sc = ops02._Scenario("급등 K2", monkeypatch, tmp_path, market_db, holdings=NAMES)
    flat = {"H00002": -1.0, "H00003": -1.0, "H00004": -1.0}
    drops = {"H00002": -6.0, "H00003": -6.0, "H00004": -6.0}
    sc.quotes({"H00001": 5.5, **flat})
    t0 = _run(sc, 0, "급등 전달")
    sc.quotes({"H00001": 1.0, **flat})
    t60 = _run(sc, 60, "회복")
    sc.quotes({"H00001": 5.5, **drops})
    t120 = _run(sc, 120, "재진입 · 급락 3건에 밀림")
    t180 = _run(sc, 180, "조건 유지 · 자리 있음")
    t240 = _run(sc, 240, "지속")

    assert _sent_with(t0, NAMES["H00001"])
    assert t0.delivery["H00001"] == (U57, "t+0")
    assert _suppressed(t60) and t60.observation["H00001"] == (U57, False)
    assert t120.status == "sent" and NAMES["H00001"] not in t120.body
    assert {("H00002", D57), ("H00003", D57), ("H00004", D57)} <= t120.included
    assert ("H00001", U57) in {(s.ticker, s.state) for s in t120.res.surge_changes.send}
    assert _sent_with(t180, NAMES["H00001"]), "K2: 밀린 급등 재진입이 억제됐다"
    assert t120.observation["H00001"] == (U57, False), "K2: 밀린 급등 재진입이 굳었다"
    assert t180.delivery["H00001"] == (U57, "t+180")
    assert _suppressed(t240)


# ═══ ④ ~ ⑥ 조건 이탈 · AC2 · K3 (변경 전후 같음) ═══════════════════════════


def test_reentry_cut_then_condition_exits_uses_last_successful_delivery(
    monkeypatch, tmp_path, market_db
):
    """④ 잘린 다음 회차에 조건 이탈 → 발송 안 함 · 그 뒤 재진입 대기는 마지막 **성공**
    전달(t+0) 기준이다. 잘린 회차(t+120) 기준이면 t+200 은 80분이라 억제된다."""
    sc = ops02._Scenario("이탈", monkeypatch, tmp_path, market_db, holdings=ONE)
    _k2_prefix(sc)
    sc.quotes(FLAT, FILL3)
    t180 = _run(sc, 180, "조건 이탈")
    sc.quotes(FLAT, {**FILL3, "T00009": 5.0})
    t200 = _run(sc, 200, "다시 재진입")
    t260 = _run(sc, 260, "지속")
    assert _suppressed(t180)
    assert t180.observation["T00009"] == (AC, False)
    assert t180.delivery["T00009"] == (AC, "t+0") and t180.sent_today == 2
    assert _sent_with(t200, REP9) and t200.delivery["T00009"] == (AC, "t+200")
    assert _suppressed(t260)


def test_ac2_redelivered_reentry_is_not_repeated(monkeypatch, tmp_path, market_db):
    """⑤ AC2 — 재진입 재전달 성공 → 지속 억제 · 해소 → 새 전달 기준 90분 재진입 억제
    → 그 뒤 지속도 억제(전송이 성공한 같은 재진입의 반복 발송 없음)."""
    sc = ops02._Scenario("AC2", monkeypatch, tmp_path, market_db, holdings=ONE)
    sc.quotes(FLAT, {"T00009": 5.0})
    t0 = _run(sc, 0, "전달")
    sc.quotes(FLAT, {})
    _run(sc, 60, "회복")
    sc.quotes(FLAT, {"T00009": 5.0})
    t120 = _run(sc, 120, "재진입 전달")
    t150 = _run(sc, 150, "지속")
    sc.quotes(FLAT, {})
    t180 = _run(sc, 180, "해소")
    sc.quotes(FLAT, {"T00009": 5.0})
    t210 = _run(sc, 210, "새 전달 기준 90분 재진입")
    t270 = _run(sc, 270, "그 뒤 지속(150분)")
    assert _sent_with(t0, REP9) and _sent_with(t120, REP9)
    assert t120.delivery["T00009"] == (AC, "t+120") and t120.sent_today == 2
    for t in (t150, t180, t210, t270):
        assert _suppressed(t), t.label
        assert t.delivery["T00009"] == (AC, "t+120") and t.sent_today == 2
    assert t210.observation["T00009"] == (AC, True)


def test_k3_reentry_within_cooldown_then_continues_is_suppressed(
    monkeypatch, tmp_path, market_db
):
    """⑥ K3(POC6-34 RESULT 판정 · 현행 유지) — 119분 재진입 억제 → 그 뒤 지속 억제."""
    sc = ops02._Scenario("K3", monkeypatch, tmp_path, market_db, holdings=ONE)
    sc.quotes(FLAT, {"T00009": 5.0})
    t0 = _run(sc, 0, "전달")
    sc.quotes(FLAT, {})
    _run(sc, 60, "회복")
    sc.quotes(FLAT, {"T00009": 5.0})
    t119 = _run(sc, 119, "119분 재진입")
    t180 = _run(sc, 180, "지속")
    t300 = _run(sc, 300, "지속(300분)")
    assert _sent_with(t0, REP9)
    assert ("T00009", AC) in t119.res.changes.suppressed
    for t in (t119, t180, t300):
        assert _suppressed(t), t.label
        assert t.observation["T00009"] == (AC, True)
        assert t.delivery["T00009"] == (AC, "t+0") and t.sent_today == 1


# ═══ ⑦ ~ ⑨ 두 번 잘림 · 일일 상한 · 평가 불가 ═══════════════════════════════


def test_reentry_cut_twice_stays_candidate(monkeypatch, tmp_path, market_db):
    """⑦ Q4 — 다음 회차도 구역이 가득 차면 다시 잘리고(우선권 없음), 자리가 나면 실린다."""
    sc = ops02._Scenario("두 번 잘림", monkeypatch, tmp_path, market_db, holdings=ONE)
    _k2_prefix(sc)
    more = {"T00003": 5.0, "T00004": 5.0, "T00005": 5.0}
    sc.quotes(FLAT, {**FILL3, **more, "T00009": 5.0})
    t180 = _run(sc, 180, "두 번째 잘림")
    t240 = _run(sc, 240, "자리 있음")
    assert t180.status == "sent" and REP9 not in t180.body
    assert _sent_with(t240, REP9), "두 번 잘린 재진입이 자리가 나도 억제됐다"
    assert ("T00009", AC) in {(d["ticker"], d["state"]) for d in t180.res.plan.dropped}
    assert t180.observation["T00009"] == (AC, False)
    assert t180.delivery["T00009"] == (AC, "t+0")
    assert t240.delivery["T00009"] == (AC, "t+240")


def test_daily_cap_keeps_reentry_candidate_and_ledger_says_daily_cap(
    monkeypatch, tmp_path, market_db
):
    """⑧ Q6 — 일일 상한 회차의 재진입 후보는 대기로 남는다. 그날 발송 0 · 원장 처분은
    그 뒤 회차에서도 `cut_by_daily_cap`(실제 제한 사유)이다."""
    from app.runtime_evidence.sector_signal_state import save_sector_state
    from app.three_push_runtime.ledger_items import CUT_DAILY, risk_items

    sc = ops02._Scenario("일일 상한", monkeypatch, tmp_path, market_db, holdings=ONE)
    sc.quotes(FLAT, {"T00009": 5.0})
    _run(sc, 0, "전달")
    sc.quotes(FLAT, {})
    _run(sc, 60, "회복")
    body = sc.state()
    save_sector_state(
        sc.rig["sector_state"], entries=body["entries"], today_kst=TODAY, sent_today=4
    )
    sent_before = len(sc.sender.calls)
    sc.quotes(FLAT, {"T00009": 5.0})
    t120 = _run(sc, 120, "상한 · 재진입")
    t180 = _run(sc, 180, "상한 · 지속")

    def disposition(t):
        items = risk_items(
            SimpleNamespace(outcome=None, intraday_eval=t.res), intraday_isolated=False
        )
        return {i["subject_id"]: i["disposition"] for i in items}.get("S9")

    for t in (t120, t180):
        assert t.reason == "intraday_daily_cap_reached" and t.body == "", t.label
        assert t.res.daily_cap_reached and t.sent_today == 4
        assert disposition(t) == CUT_DAILY, t.label
    assert len(sc.sender.calls) == sent_before
    for t in (t120, t180):
        assert t.observation["T00009"] == (AC, False), t.label


@pytest.mark.parametrize("scope", ["provider_down", "single_ticker"])
def test_unevaluable_tick_keeps_cut_reentry_pending(
    monkeypatch, tmp_path, market_db, scope
):
    """⑨ · ⑮(보완 2) — 잘린 재진입의 다음 회차가 그 신호를 평가하지 못하면 행을 그대로
    둔다(대기 유지). 그다음 정상 평가에서 그 회차의 정책으로 다시 판정한다."""
    sc = ops02._Scenario(scope, monkeypatch, tmp_path, market_db, holdings=ONE)
    _k2_prefix(sc)
    row_cut = dict(sc.ticks[-1].observation)
    sc.quotes(FLAT, {**FILL3, "T00009": 5.0})
    ft._blind_sectors(sc.rig, None if scope == "provider_down" else {"T00009"})
    t180 = _run(sc, 180, f"평가 불가 · {scope}")
    sc.quotes(FLAT, {**FILL3, "T00009": 5.0})
    t240 = _run(sc, 240, "정상 평가")
    assert REP9 not in t180.body
    assert "T00009" in t180.res.unevaluable
    assert _sent_with(t240, REP9), "평가 불가 회차 뒤 잘린 재진입이 억제됐다"
    assert t180.observation["T00009"] == row_cut["T00009"] == (AC, False)
    assert t180.delivery["T00009"] == (AC, "t+0")
    assert t240.delivery["T00009"] == (AC, "t+240")


# ═══ ⑩ ~ ⑬ 보완 1 — 성공 전달 기록 ════════════════════════════════════════


def _reentry_delivered(sc, on_tick=None):
    """전달 → 회복 → 재진입(자리 있음) 전송 성공. `on_tick` 은 t+120 직전에 부른다."""
    sc.quotes(FLAT, {"T00009": 5.0})
    _run(sc, 0, "전달")
    sc.quotes(FLAT, {})
    _run(sc, 60, "회복")
    sc.quotes(FLAT, {"T00009": 5.0})
    if on_tick is not None:
        on_tick()
    t120 = _run(sc, 120, "재진입 전달")
    t180 = _run(sc, 180, "지속")
    assert _sent_with(t120, REP9) and t120.record["status"] == "sent"
    return t120, t180


def test_first_save_fails_observation_save_keeps_success(
    monkeypatch, tmp_path, market_db
):
    """⑩ — 재진입 전달 성공 · 첫 저장만 실패 → 관측 저장이 성공 사실을 남긴다.
    다음 회차 반복 발송 없음 · `sent_today` +1 한 번 · `last_sent_at` = 이번 회차."""
    sc = ops02._Scenario("⑩", monkeypatch, tmp_path, market_db, holdings=ONE)
    t120, t180 = _reentry_delivered(sc, lambda: _fail_state_saves(monkeypatch, 1))
    assert "intraday_state_save_error" in t120.record
    assert "intraday_state_saved" not in t120.record
    assert _suppressed(t180)
    assert t120.delivery["T00009"] == (AC, "t+120"), "성공 전달 시각이 남지 않았다"
    assert t120.sent_today == 2, "성공 회차가 일일 발송 수에 반영되지 않았다"
    assert t120.observation["T00009"] == (AC, True)
    assert t120.record.get("intraday_state_saved_by_observation") is True
    assert "intraday_observation_error" not in t120.record
    assert t180.sent_today == 2


def test_first_save_succeeds_observation_save_does_not_recount(
    monkeypatch, tmp_path, market_db
):
    """⑪ — 첫 저장 성공 → 관측 저장은 대신 저장을 하지 않는다(`sent_today` 이중 증가 0)."""
    sc = ops02._Scenario("⑪", monkeypatch, tmp_path, market_db, holdings=ONE)
    t120, t180 = _reentry_delivered(sc)
    assert t120.record.get("intraday_state_saved") is True
    assert "intraday_state_saved_by_observation" not in t120.record
    assert t120.delivery["T00009"] == (AC, "t+120") and t120.sent_today == 2
    assert _suppressed(t180) and t180.sent_today == 2


def test_first_save_written_but_flag_lost_counts_once(monkeypatch, tmp_path, market_db):
    """⑪-b — 첫 저장이 실제로는 써졌는데 표식만 없다 → 이번 회차 시각이 이미 행에 있으므로
    관측 저장이 `sent_today` 를 다시 올리지 않는다(같은 회차 한 번만 반영)."""
    import app.three_push_runtime.runner_evidence as rev

    real = rev._save_intraday_state_after_send

    def _lose_flag(record, **kw):
        real(record, **kw)
        record.pop("intraday_state_saved", None)

    sc = ops02._Scenario("⑪-b", monkeypatch, tmp_path, market_db, holdings=ONE)
    t120, t180 = _reentry_delivered(
        sc,
        lambda: monkeypatch.setattr(rev, "_save_intraday_state_after_send", _lose_flag),
    )
    assert t120.record.get("intraday_state_saved_by_observation") is True
    assert t120.delivery["T00009"] == (AC, "t+120")
    assert t120.sent_today == 2, "같은 회차를 두 번 셌다"
    assert _suppressed(t180) and t180.sent_today == 2


def test_both_saves_fail_is_a_general_state_save_failure(
    monkeypatch, tmp_path, market_db
):
    """⑫ — 이번 회차 상태 쓰기가 모두 실패(첫 저장 · 대신 저장 · 관측만 다시 쓰기) → 두
    진단 키가 남고 발송 결과(sent)는 뒤집지 않는다. 성공 사실이 남지 않아 다음 회차에 한
    번 더 나가고 `sent_today` 는 실제 발송 회차보다 1 적다(변경 전과 같음 · 결과서 §5)."""
    sc = ops02._Scenario("⑫", monkeypatch, tmp_path, market_db, holdings=ONE)
    sc.quotes(FLAT, {"T00009": 5.0})
    _run(sc, 0, "전달")
    sc.quotes(FLAT, {})
    _run(sc, 60, "회복")
    before = sc.rig["sector_state"].read_bytes()
    sc.quotes(FLAT, {"T00009": 5.0})
    left = _fail_state_saves(monkeypatch, 3)
    t120 = _run(sc, 120, "재진입 전달 · 모든 저장 실패")
    left["n"] = 0  # 이번 회차 밖으로 새지 않게(변경 전 코드는 쓰기가 2번뿐)
    assert _sent_with(t120, REP9) and t120.record["status"] == "sent"
    assert "intraday_state_save_error" in t120.record
    assert "intraday_observation_error" in t120.record
    assert "intraday_state_saved_by_observation" not in t120.record
    assert "intraday_state_save_fallback_error" not in t120.record
    assert sc.rig["sector_state"].read_bytes() == before
    assert t120.record.get("intraday_tally_outcome") == "sent"
    t180 = _run(sc, 180, "다음 회차 · 저장 정상")
    t240 = _run(sc, 240, "지속")
    assert _sent_with(t180, REP9), "실측 사실(한계): 다음 회차에 한 번 더 나간다"
    assert t180.delivery["T00009"] == (AC, "t+180")
    assert t180.sent_today == 2  # 발송 회차 3(t+0 · t+120 · t+180) - 1
    assert _suppressed(t240) and t240.sent_today == 2


@pytest.mark.parametrize("cause", ["bad_sent_signal", "write_fails_twice"])
def test_fallback_merge_fails_still_saves_observation(
    monkeypatch, tmp_path, market_db, cause
):
    """독립 검토 B-1 — 첫 저장 실패 뒤 대신 저장(병합 · 쓰기)까지 실패해도 관측만 쓰는
    저장을 한 번 더 해 이번 회차 관측 · 회복 기록을 남긴다. 진단 = 대신 저장 예외 형.

    `bad_sent_signal` = 검토 탐침 그대로(실린 신호에 `sector_key` 없음 → 두 병합 모두
    AttributeError). `write_fails_twice` = 첫 저장 · 대신 저장 쓰기만 실패.
    """
    sc = ops02._Scenario(cause, monkeypatch, tmp_path, market_db, holdings=ONE)
    rep1 = ft._rep_name("T00001")
    sc.quotes(FLAT, {"T00001": 5.0, "T00009": 5.0})
    t0 = _run(sc, 0, "두 신호 전달")
    sc.quotes(FLAT, {"T00001": 5.0})
    t60 = _run(sc, 60, "T00009 회복 · T00001 지속")
    sc.quotes(FLAT, {"T00009": 5.0})
    if cause == "bad_sent_signal":
        sc.inject(
            lambda res: setattr(
                res,
                "sent_signals",
                [
                    SimpleNamespace(ticker=s.ticker, state=s.state)
                    for s in res.sent_signals
                ],
            )
        )
    else:
        _fail_state_saves(monkeypatch, 2)
    t120 = _run(sc, 120, "재진입 전달 · 대신 저장 실패")
    t180 = _run(sc, 180, "다음 회차")
    err = "AttributeError" if cause == "bad_sent_signal" else "OSError"
    rec = t120.record
    assert _sent_with(t0, REP9, rep1) and _suppressed(t60)
    assert _sent_with(t120, REP9) and rec["status"] == "sent" and rep1 not in t120.body
    assert rec["intraday_state_save_error"].startswith(err)
    assert rec.get("intraday_state_save_fallback_error") == err
    assert "intraday_observation_error" not in rec
    assert "intraday_state_saved_by_observation" not in rec
    assert rec.get("intraday_observation_saved") == len(t120.res.observed)
    # 이번 회차 관측이 남았다 — 빠진 T00001 = 회복 기록 · 재진입 T00009 = 후보 · 전달
    # 기록 못 함 → 회복 유지(전달 필드 · `sent_today` 는 그대로)
    assert t60.observation["T00001"] == (AC, True)
    assert t120.observation["T00001"] == (AC, False), "이번 회차 관측이 사라졌다"
    assert t120.observation["T00009"] == (AC, False)
    assert t120.delivery["T00009"] == (AC, "t+0") and t120.sent_today == 1
    # 성공 사실을 못 남긴 일반 저장 장애와 같다 — 다음 회차에 한 번 더 나간다(결과서 §5)
    assert _sent_with(t180, REP9) and t180.sent_today == 2


@pytest.mark.parametrize("kind", ["first_detected", "state_change"])
def test_first_save_fails_for_new_and_changed_signals_keeps_success(
    monkeypatch, tmp_path, market_db, kind
):
    """⑬ — 처음 잡힌 신호 · 상태 변화의 전달 성공 + 첫 저장만 실패 → 성공 사실이 남아
    다음 회차에 다시 나가지 않는다(전에는 한 번 더 나갔다)."""
    sc = ops02._Scenario(kind, monkeypatch, tmp_path, market_db, holdings=ONE)
    start = 0
    if kind == "state_change":
        sc.quotes({"H00001": 5.5}, {"T00009": 2.0})
        t0 = _run(sc, 0, "X 전달")
        assert t0.delivery == {"H00001": (U57, "t+0"), "T00009": (ER, "t+0")}
        start = 60
    sc.quotes({"H00001": 8.0}, {"T00009": 5.0})
    _fail_state_saves(monkeypatch, 1)
    t1 = _run(sc, start, "전달 · 첫 저장 실패")
    t2 = _run(sc, start + 60, "지속")
    stamp = f"t+{start}"
    assert _sent_with(t1, REP9, NAMES["H00001"])
    assert "intraday_state_save_error" in t1.record
    assert _suppressed(t2), "전달된 신호가 다음 회차에 다시 나갔다"
    assert t1.record.get("intraday_state_saved_by_observation") is True
    assert t1.delivery == {"H00001": (U710, stamp), "T00009": (AC, stamp)}
    assert t1.sent_today == (1 if kind == "first_detected" else 2)
    assert t2.sent_today == t1.sent_today


def test_k2_cut_tick_first_save_fails_keeps_cut_reentry_pending(
    monkeypatch, tmp_path, market_db
):
    """독립 검토 B-5 — K2 잘림 회차에 첫 저장만 실패 → 대신 저장이 실린 3건만 전달로
    남기고(`sent_today` +1 한 번) 잘린 재진입은 회복 기록을 유지한다(같은 후보 집합) →
    다음 회차 발송 → 그다음 억제."""
    sc = ops02._Scenario("B-5", monkeypatch, tmp_path, market_db, holdings=ONE)
    # `_k2_prefix` 가 t+120 의 `sent_today == 2` · T00009 전달 필드 t+0 을 단언한다
    *_, t120 = _k2_prefix(sc, before_cut=lambda: _fail_state_saves(monkeypatch, 1))
    t180 = _run(sc, 180, "조건 유지 · 자리 있음")
    t240 = _run(sc, 240, "지속")
    rec = t120.record
    assert "intraday_state_save_error" in rec and "intraday_state_saved" not in rec
    assert rec.get("intraday_state_saved_by_observation") is True
    assert "intraday_state_save_fallback_error" not in rec
    assert t120.observation["T00009"] == (AC, False), "대신 저장이 잘린 재진입을 굳혔다"
    assert all(t120.delivery[t] == (AC, "t+120") for t in FILL3)
    assert _sent_with(t180, REP9), "K2: 잘린 재진입이 다음 회차에 실리지 않았다"
    assert all(ft._rep_name(t) not in t180.body for t in FILL3)
    assert t180.delivery["T00009"] == (AC, "t+180") and t180.sent_today == 3
    assert _suppressed(t240) and t240.sent_today == 3


# ═══ ⑭ 보완 2 — 다음 회차의 활성 정책 재발송 대기 ════════════════════════════


def test_policy_cooldown_change_turns_cut_reentry_into_k3(
    monkeypatch, tmp_path, market_db
):
    """⑭ — 잘린 재진입의 다음 회차에 활성 정책 대기가 240분으로 늘어 미충족 → 그 회차
    억제 → 후보가 아니므로 K3 지속 억제로 전환(대기를 채운 뒤에도 억제)."""
    sc = ops02._Scenario("⑭", monkeypatch, tmp_path, market_db, holdings=ONE)
    _k2_prefix(sc)
    assert sc.ticks[-1].observation["T00009"] == (AC, False)
    sc.rig["policy"] = ft._policy(cooldown_minutes=240)
    t180 = _run(sc, 180, "대기 240분 · 미충족")
    t300 = _run(sc, 300, "대기 240분 · 경과 뒤 지속")
    assert ("T00009", AC) in t180.res.changes.suppressed
    for t in (t180, t300):
        assert _suppressed(t), t.label
        assert t.observation["T00009"] == (AC, True), t.label
        assert t.delivery["T00009"] == (AC, "t+0")


# ═══ 검증자 r1 F1 — 저장 직전 다시 읽기 실패 ≠ 발송 이력 없음 ══════════════════
#
# 세 쓰기 경로(러너 첫 저장 · 매 회차 관측 저장 · 대신 저장과 그 재시도)는 저장 직전에
# 상태 파일을 다시 읽는다. 그 읽기가 실패(unreadable)하면 빈 상태 위에 써서 앞선 전달
# 기록과 `sent_today` 를 지웠다. 정정 = 이번 회차가 이미 아는 상태(조립 때 읽은 상태 ·
# 첫 저장이 방금 쓴 상태)를 기준으로 쓴다. 조립 때도 못 읽었으면 예전처럼 새로 쓴다.

NEW4 = ("T00001", "T00002", "T00003", "T00004")


def _fail_state_read_in(monkeypatch, sc, module, name, calls=1):
    """`module.name` 의 다음 `calls` 번 호출에서 그 안의 **첫 상태 파일 읽기 한 번**을
    OSError 로 실패시킨다. 파일은 그대로다(검증자 r1 F1 재현 방식 · 일시 읽기 실패)."""
    import pathlib

    path = sc.rig["sector_state"]
    real_read = pathlib.Path.read_text
    real_fn = getattr(module, name)
    armed = {"calls": calls, "n": 0, "failed": 0}

    def _read(self, *a, **k):
        if armed["n"] > 0 and self == path:
            armed["n"] -= 1
            armed["failed"] += 1
            raise OSError("POC6-35 r1 주입: 상태 파일 읽기 실패")
        return real_read(self, *a, **k)

    def _fn(*a, **k):
        if armed["calls"] > 0:
            armed["calls"] -= 1
            armed["n"] = 1
        try:
            return real_fn(*a, **k)
        finally:
            armed["n"] = 0

    monkeypatch.setattr(pathlib.Path, "read_text", _read)
    monkeypatch.setattr(module, name, _fn)
    return armed


def _three_sent(sc):
    """신규 신호를 회차마다 하나씩 3번 전달(`sent_today` 3) · 다음 회차 시세는 4건."""
    held = {}
    for i, tk in enumerate(NEW4[:3]):
        held[tk] = 5.0
        sc.quotes(FLAT, dict(held))
        t = _run(sc, 60 * i, f"{tk} 전달")
        assert _sent_with(t, ft._rep_name(tk)) and t.sent_today == i + 1, t.label
    sc.quotes(FLAT, {tk: 5.0 for tk in NEW4})
    return {tk: f"t+{60 * i}" for i, tk in enumerate(NEW4[:3])}


def _assert_cap_holds(sc, t180, stamps):
    """4번째 전달이 기록됐고(발송 수 4 · 앞선 전달 기록 그대로) 다음 회차는 일일 상한."""
    assert t180.sent_today == 4, "일일 발송 수를 잃었다"
    for tk, stamp in stamps.items():
        assert t180.delivery[tk] == (AC, stamp), f"{tk} 앞선 전달 기록을 잃었다"
    assert t180.delivery["T00004"] == (AC, "t+180")
    sent_before = len(sc.sender.calls)
    sc.quotes(FLAT, {**{tk: 5.0 for tk in NEW4}, "T00005": 5.0})
    t240 = _run(sc, 240, "다음 회차 · 입출력 정상")
    assert t240.reason == "intraday_daily_cap_reached" and t240.body == "", t240.label
    assert len(sc.sender.calls) == sent_before, "일일 상한 4건을 넘겨 보냈다"
    assert t240.sent_today == 4


def test_r1_f1_fallback_reload_unreadable_keeps_history_and_daily_cap(
    monkeypatch, tmp_path, market_db
):
    """검증자 r1 F1 재현 표 그대로 — 3회 발송 → 4번째 전송 성공 뒤 첫 쓰기만 실패 →
    대신 저장의 기존 파일 읽기만 실패 → 대신 저장은 조립 때 읽은 상태 위에 병합해
    앞선 전달 기록 · 발송 수를 지키고, 다음 회차(입출력 정상)는 일일 상한으로 막힌다."""
    import app.runtime_evidence.sector_signal_state as sss

    sc = ops02._Scenario("r1-F1", monkeypatch, tmp_path, market_db, holdings=ONE)
    stamps = _three_sent(sc)
    _fail_state_saves(monkeypatch, 1)
    armed = _fail_state_read_in(monkeypatch, sc, sss, "save_observation")
    t180 = _run(sc, 180, "4번째 전달 · 첫 쓰기 실패 · 대신 저장 읽기 실패")
    rec = t180.record
    assert _sent_with(t180, ft._rep_name("T00004")) and rec["status"] == "sent"
    assert armed["failed"] == 1, "읽기 실패가 주입되지 않았다"
    assert rec["intraday_state_save_error"].startswith("OSError")
    _assert_cap_holds(sc, t180, stamps)  # 동작 먼저(변경 전 RED 원인이 드러나게)
    assert rec.get("intraday_state_saved_by_observation") is True
    assert rec.get("intraday_observation_base") == "snapshot"
    assert "intraday_state_save_fallback_error" not in rec
    assert "intraday_observation_error" not in rec


def test_r1_observation_reload_unreadable_after_first_save_keeps_history(
    monkeypatch, tmp_path, market_db
):
    """같은 뿌리(변경 전부터 있던 경로) — 4번째 전송 · 첫 저장 성공 → 매 회차 관측 저장의
    다시 읽기만 실패 → 첫 저장이 방금 쓴 상태 위에 관측을 쓴다."""
    import app.runtime_evidence.sector_signal_state as sss

    sc = ops02._Scenario("r1-관측", monkeypatch, tmp_path, market_db, holdings=ONE)
    stamps = _three_sent(sc)
    armed = _fail_state_read_in(monkeypatch, sc, sss, "save_observation")
    t180 = _run(sc, 180, "4번째 전달 · 관측 저장 읽기 실패")
    rec = t180.record
    assert armed["failed"] == 1
    assert rec.get("intraday_state_saved") is True
    _assert_cap_holds(sc, t180, stamps)
    assert "intraday_state_saved_by_observation" not in rec
    assert rec.get("intraday_observation_base") == "snapshot"
    assert "intraday_state_save_base" not in rec


def test_r1_observation_reload_unreadable_on_quiet_tick_keeps_history(
    monkeypatch, tmp_path, market_db
):
    """같은 뿌리 · 보내지 않은 회차(지속 억제) — 관측 저장 다시 읽기만 실패해도 조립 때
    읽은 상태 위에 쓴다. 다음 회차에 같은 신호가 다시 나가지 않는다."""
    import app.runtime_evidence.sector_signal_state as sss

    sc = ops02._Scenario("r1-조용", monkeypatch, tmp_path, market_db, holdings=ONE)
    sc.quotes(FLAT, {"T00009": 5.0})
    t0 = _run(sc, 0, "전달")
    armed = _fail_state_read_in(monkeypatch, sc, sss, "save_observation")
    t60 = _run(sc, 60, "지속 · 관측 저장 읽기 실패")
    t120 = _run(sc, 120, "지속 · 입출력 정상")
    assert _sent_with(t0, REP9) and armed["failed"] == 1 and _suppressed(t60)
    assert _suppressed(t120), "읽기 실패 회차 뒤 같은 신호가 다시 나갔다"
    assert t60.delivery["T00009"] == (AC, "t+0") and t60.sent_today == 1
    assert t60.observation["T00009"] == (AC, True)
    assert t120.delivery["T00009"] == (AC, "t+0") and t120.sent_today == 1
    assert t60.record.get("intraday_observation_base") == "snapshot"


def test_r1_first_save_reload_unreadable_uses_assembly_state(
    monkeypatch, tmp_path, market_db
):
    """같은 뿌리(변경 전부터) — 러너 첫 저장의 다시 읽기만 실패 → 조립 때 읽은 상태 위에
    병합한다(실행 기록 `intraday_state_save_base=snapshot`)."""
    import app.three_push_runtime.runner_evidence as rev

    sc = ops02._Scenario("r1-첫저장", monkeypatch, tmp_path, market_db, holdings=ONE)
    stamps = _three_sent(sc)
    armed = _fail_state_read_in(monkeypatch, sc, rev, "_save_intraday_state_after_send")
    t180 = _run(sc, 180, "4번째 전달 · 첫 저장 읽기 실패")
    rec = t180.record
    assert armed["failed"] == 1
    assert rec.get("intraday_state_saved") is True
    _assert_cap_holds(sc, t180, stamps)
    assert rec.get("intraday_sent_today") == 4
    assert rec.get("intraday_state_save_base") == "snapshot"
    assert "intraday_observation_base" not in rec


def test_r1_corrupt_state_file_is_rewritten_as_before(monkeypatch, tmp_path, market_db):
    """조립 때도 못 읽은 손상 파일은 예전처럼 비교 불가(전부 신규)로 보고 새로 써서 복구한다
    — 기준으로 쓸 상태가 없다(실행 기록 `intraday_state_save_base=unreadable`)."""
    sc = ops02._Scenario("r1-손상", monkeypatch, tmp_path, market_db, holdings=ONE)
    sc.quotes(FLAT, {"T00009": 5.0})
    _run(sc, 0, "전달")
    sc.rig["sector_state"].write_text("{손상", encoding="utf-8")
    t60 = _run(sc, 60, "손상 파일 · 전부 신규")
    t120 = _run(sc, 120, "복구 뒤 지속")
    assert _sent_with(t60, REP9), "비교 불가는 전부 신규(OPS-02 계약)"
    assert t60.delivery["T00009"] == (AC, "t+60") and t60.sent_today == 1
    assert _suppressed(t120) and t120.sent_today == 1
    # 여기까지 변경 전과 같다(복구 동작 그대로) — 아래 진단 키만 새로 남는다
    assert t60.record.get("intraday_state_save_base") == "unreadable"
    assert "intraday_observation_base" not in t60.record


def test_r1_fallback_merge_fails_and_reload_unreadable_keeps_history(
    monkeypatch, tmp_path, market_db
):
    """B-1 재시도(관측만 다시 쓰기)도 같은 기준을 쓴다 — 대신 저장 병합이 실패하고 다시
    읽기도 실패하면 조립 때 읽은 상태 위에 관측만 쓴다(앞선 전달 기록 · 발송 수 유지)."""
    import app.runtime_evidence.sector_signal_state as sss

    sc = ops02._Scenario("r1-B1", monkeypatch, tmp_path, market_db, holdings=ONE)
    rep1 = ft._rep_name("T00001")
    sc.quotes(FLAT, {"T00001": 5.0, "T00009": 5.0})
    t0 = _run(sc, 0, "두 신호 전달")
    sc.quotes(FLAT, {"T00001": 5.0})
    _run(sc, 60, "T00009 회복 · T00001 지속")
    sc.quotes(FLAT, {"T00001": 5.0, "T00009": 5.0})
    sc.inject(
        lambda res: setattr(
            res,
            "sent_signals",
            [SimpleNamespace(ticker=s.ticker, state=s.state) for s in res.sent_signals],
        )
    )
    armed = _fail_state_read_in(monkeypatch, sc, sss, "save_observation")
    t120 = _run(sc, 120, "재진입 전달 · 두 병합 실패 · 다시 읽기 실패")
    t180 = _run(sc, 180, "다음 회차")
    rec = t120.record
    assert _sent_with(t0, REP9, rep1) and armed["failed"] == 1
    assert _sent_with(t120, REP9) and rep1 not in t120.body
    assert t120.delivery["T00001"] == (AC, "t+0"), "앞선 전달 기록을 잃었다"
    assert t120.sent_today == 1
    # 성공 사실은 못 남겼다(일반 저장 장애 · 결과서 §5) — T00009 만 한 번 더 나간다
    assert _sent_with(t180, REP9) and rep1 not in t180.body
    assert t180.sent_today == 2
    assert rec.get("intraday_state_save_fallback_error") == "AttributeError"
    assert rec.get("intraday_observation_base") == "snapshot"
    assert "intraday_observation_error" not in rec


# ═══ 단위 — `_apply_observation` · 후보 집합 · 대신 저장 ═════════════════════


def _sig(ticker, state):
    from app.runtime_evidence.sector_signal import SectorSignal

    return SectorSignal("S", ticker, f"n{ticker}", state, 0.0)


def _now():
    from app.runtime_evidence.sector_signal_state import KST

    return datetime(2026, 11, 19, 11, 30, tzinfo=KST)


_ROWS = [
    # (id, 이전 continuous, 전달 상태, 관측, 후보, 기대 continuous)
    # 회복 · 같은 상태 · 이번 회차 후보 · 미전달 → 회복 유지(K2)
    ("k2_recovered_same_candidate", False, ER, ER, {("T1", ER)}, False),
    # 회복 · 같은 상태 · 후보 아님(대기 억제) → True(K3 그대로)
    ("k3_recovered_same_not_candidate", False, ER, ER, set(), True),
    ("candidate_key_other_state", False, ER, ER, {("T1", AC)}, True),
    ("candidate_key_other_ticker", False, ER, ER, {("T2", ER)}, True),
    ("not_recovered_same_candidate", True, ER, ER, {("T1", ER)}, True),
    ("not_recovered_change_candidate", True, ER, AC, {("T1", AC)}, True),
    ("never_delivered_candidate", False, None, ER, {("T1", ER)}, True),
    ("no_continuous_field_candidate", None, None, ER, {("T1", ER)}, True),
    # 회복 · 다른 상태 → 회복 유지(OPS-02 리뷰 · 예전과 같다)
    ("recovered_other_state", False, ER, AC, set(), False),
    ("recovered_other_state_candidate", False, ER, AC, {("T1", AC)}, False),
]


def _row(continuous, delivered):
    row = {"state": delivered or ER}
    if continuous is not None:
        row["continuous"] = continuous
    if delivered is not None:
        row["last_delivered_state"] = delivered
        row["last_sent_at"] = (_now() - timedelta(minutes=120)).isoformat()
    return row


@pytest.mark.parametrize("path", ["merge", "save_observation"])
@pytest.mark.parametrize(
    "label, continuous, delivered, observed, cands, expected",
    _ROWS,
    ids=[r[0] for r in _ROWS],
)
def test_unit_observation_keeps_recovery_for_undelivered_candidate(
    tmp_path, path, label, continuous, delivered, observed, cands, expected
):
    """관측 저장 두 경로가 같은 후보 규칙을 쓴다(A1)."""
    from app.runtime_evidence import sector_signal_state as sss

    prev = sss.LoadedSectorState(
        entries={"T1": _row(continuous, delivered)}, fallback=False
    )
    if path == "merge":
        out = sss.merge_sector_entries(
            sent=[],
            previous=prev,
            now_kst=_now(),
            observed=[_sig("T1", observed)],
            candidates=frozenset(cands),
        )["T1"]
    else:
        p = tmp_path / "s.json"
        sss.save_sector_state(p, entries=prev.entries, today_kst=TODAY, sent_today=1)
        wrote = sss.save_observation(
            p,
            observed=[_sig("T1", observed)],
            today_kst=TODAY,
            candidates=frozenset(cands),
        )
        assert wrote == ("observation", None, None)
        loaded = sss.load_sector_state(p, today_kst=TODAY)
        assert loaded.sent_today == 1
        out = loaded.entries["T1"]
    assert out["state"] == observed
    assert out["continuous"] is expected, label
    assert out.get("last_delivered_state") == delivered  # 관측은 전달을 전진시키지 않음


def test_unit_sent_candidate_row_is_delivered_and_continuous():
    """후보이면서 본문에 실려 전달된 행 = 전달 필드 · `continuous=True`(AC2 반복 억제)."""
    from app.runtime_evidence import sector_signal_state as sss

    prev = sss.LoadedSectorState(entries={"T1": _row(False, ER)}, fallback=False)
    out = sss.merge_sector_entries(
        sent=[_sig("T1", ER)],
        previous=prev,
        now_kst=_now(),
        observed=[_sig("T1", ER)],
        candidates=frozenset({("T1", ER)}),
    )["T1"]
    assert out["continuous"] is True
    assert out["last_delivered_state"] == ER
    assert out["last_sent_at"] == _now().isoformat()


def test_unit_send_candidates_is_union_of_sector_and_surge_send():
    from app.runtime_evidence.sector_signal_state import (
        SectorChangeSet,
        send_candidates,
    )

    sector = SectorChangeSet(send=[_sig("T1", AC)], suppressed=[("T2", ER)])
    surge = SectorChangeSet(send=[_sig("H1", U57)], suppressed=[("H2", U710)])
    assert send_candidates(sector, surge) == {("T1", AC), ("H1", U57)}
    assert send_candidates(None, surge) == {("H1", U57)}
    assert send_candidates(sector, None) == {("T1", AC)}
    assert send_candidates() == frozenset()


def test_unit_save_observation_records_success_once_per_run(tmp_path):
    """보완 1 — 대신 저장 = 첫 저장과 같은 병합. 같은 회차 시각이면 한 번만 센다."""
    from app.runtime_evidence import sector_signal_state as sss

    p = tmp_path / "s.json"
    sss.save_sector_state(
        p,
        entries={"T1": _row(False, AC), "T2": _row(False, AC), "B": _row(True, AC)},
        today_kst=TODAY,
        sent_today=1,
    )
    blind_before = sss.load_sector_state(p, today_kst=TODAY).entries["B"]
    kw = dict(
        observed=[_sig("T1", AC), _sig("T2", AC)],
        today_kst=TODAY,
        unevaluable={"B"},
        candidates=frozenset({("T1", AC), ("T2", AC)}),
        sent=[_sig("T1", AC)],
    )
    assert sss.save_observation(p, now_kst=_now(), **kw) == ("sent", None, None)
    first = sss.load_sector_state(p, today_kst=TODAY)
    assert first.sent_today == 2
    t1, t2 = first.entries["T1"], first.entries["T2"]
    assert (t1["last_delivered_state"], t1["last_sent_at"]) == (AC, _now().isoformat())
    assert t1["continuous"] is True
    assert t2["continuous"] is False and t2["last_sent_at"] != _now().isoformat()
    assert first.entries["B"] == blind_before, "평가 불가 entry 를 바꿨다"
    # 같은 회차(같은 시각)를 다시 반영 → 세지 않는다
    sss.save_observation(p, now_kst=_now(), **kw)
    assert sss.load_sector_state(p, today_kst=TODAY).sent_today == 2
    # 다른 회차 → 센다
    sss.save_observation(p, now_kst=_now() + timedelta(minutes=60), **kw)
    assert sss.load_sector_state(p, today_kst=TODAY).sent_today == 3


def test_unit_save_observation_empty_sent_counts_run(tmp_path):
    """통합 본문에 장중 신호 없이 보유 급락만 실린 회차도 첫 저장처럼 한 번 센다."""
    from app.runtime_evidence import sector_signal_state as sss

    p = tmp_path / "s.json"
    sss.save_sector_state(
        p, entries={"T1": _row(True, AC)}, today_kst=TODAY, sent_today=2
    )
    wrote = sss.save_observation(
        p, observed=[], today_kst=TODAY, sent=[], now_kst=_now()
    )
    assert wrote == ("sent", None, None)
    loaded = sss.load_sector_state(p, today_kst=TODAY)
    assert loaded.sent_today == 3
    assert loaded.entries["T1"]["last_sent_at"] != _now().isoformat()
    with pytest.raises(ValueError):
        sss.save_observation(p, observed=[], today_kst=TODAY, sent=[])


def test_unit_save_observation_fallback_merge_error_still_saves_observation(tmp_path):
    """B-1 — 대신 저장 병합이 예외(탐침: `sector_key` 없는 실린 신호 → AttributeError)여도
    관측만 쓰는 저장을 한 번 더 한다. `sent_today` 는 그대로 · 반환에 예외 형."""
    from app.runtime_evidence import sector_signal_state as sss

    p = tmp_path / "s.json"
    sss.save_sector_state(
        p,
        entries={"A": _row(True, AC), "T1": _row(False, AC)},
        today_kst=TODAY,
        sent_today=1,
    )
    wrote = sss.save_observation(
        p,
        observed=[_sig("T1", AC)],
        today_kst=TODAY,
        candidates=frozenset({("T1", AC)}),
        sent=[SimpleNamespace(ticker="T1", state=AC)],  # sector_key 없음
        now_kst=_now(),
    )
    assert wrote == ("observation", "AttributeError", None)
    loaded = sss.load_sector_state(p, today_kst=TODAY)
    assert loaded.sent_today == 1, "관측만 쓴 회차가 발송 수를 올렸다"
    assert loaded.entries["A"]["continuous"] is False  # 이번 회차에 없음 → 회복 기록
    assert loaded.entries["T1"]["continuous"] is False  # 후보 · 전달 기록 못 함
    assert loaded.entries["T1"]["last_sent_at"] != _now().isoformat()


def test_unit_save_observation_raises_only_when_nothing_written(tmp_path, monkeypatch):
    """B-1 — 대신 저장 쓰기와 관측만 다시 쓰기가 모두 실패해야 예외를 낸다(파일 그대로)."""
    from app.runtime_evidence import sector_signal_state as sss

    p = tmp_path / "s.json"
    sss.save_sector_state(
        p, entries={"T1": _row(False, AC)}, today_kst=TODAY, sent_today=1
    )
    before = p.read_bytes()
    left = _fail_state_saves(monkeypatch, 2)
    with pytest.raises(OSError):
        sss.save_observation(
            p,
            observed=[_sig("T1", AC)],
            today_kst=TODAY,
            sent=[_sig("T1", AC)],
            now_kst=_now(),
        )
    assert left["n"] == 0 and p.read_bytes() == before
    # 한 번만 실패하면 관측만 쓴다
    _fail_state_saves(monkeypatch, 1)
    assert sss.save_observation(
        p, observed=[_sig("T1", AC)], today_kst=TODAY, sent=[], now_kst=_now()
    ) == ("observation", "OSError", None)
    assert sss.load_sector_state(p, today_kst=TODAY).sent_today == 1


def test_unit_apply_intraday_records_fallback_error_keeps_observation(tmp_path):
    """B-1 검토 탐침 그대로 — 대신 저장이 AttributeError 여도 관측(빠진 A = 회복 기록)이
    저장되고, 진단은 `intraday_state_save_fallback_error` · `intraday_observation_saved`."""
    from app.runtime_evidence import holdings_risk_flow as rflow
    from app.runtime_evidence import sector_signal_state as sss

    p = tmp_path / "s.json"
    sss.save_sector_state(
        p, entries={"A": _row(True, AC)}, today_kst=TODAY, sent_today=1
    )
    pending = {
        "sector_state_path": p,
        "tally_path": tmp_path / "tally.json",
        "today_kst": TODAY,
        "observed": [],
        "unevaluable": set(),
        "runtime_kst": _now().isoformat(),
        "tick_outcome": "no_signal",
        "entry_omitted": False,
        "candidates": frozenset(),
        "sent_signals": [SimpleNamespace(ticker="B", state=AC)],
    }
    record = {rflow.PENDING_KEY: pending, "partial_delivery": False}
    rflow.apply_intraday_records(record, mode="send", status="sent", reason=None)
    loaded = sss.load_sector_state(p, today_kst=TODAY)
    assert loaded.entries["A"]["continuous"] is False, "이번 회차 관측이 사라졌다"
    assert "B" not in loaded.entries and loaded.sent_today == 1
    assert record.get("intraday_state_save_fallback_error") == "AttributeError"
    assert record.get("intraday_observation_saved") == 0
    assert "intraday_observation_error" not in record
    assert "intraday_state_saved_by_observation" not in record


_FALLBACK = [
    # (id, status, partial, 첫 저장 표식, pending 에 sent_signals, 대신 저장?)
    ("sent_first_save_failed", "sent", False, False, True, True),
    ("sent_first_save_ok", "sent", False, True, True, False),
    ("partial_delivery", "sent", True, False, True, False),
    ("send_failed", "failed", False, False, True, False),
    # 통합 본문이 나가지 않은 회차(구 본문 · 일일 상한 · 신호 없음)
    ("not_integrated_body", "sent", False, False, False, False),
    ("skipped", "skipped", False, False, True, False),
]


@pytest.mark.parametrize(
    "label, status, partial, saved, carried, expected",
    _FALLBACK,
    ids=[r[0] for r in _FALLBACK],
)
def test_unit_apply_intraday_records_fallback_conditions(
    tmp_path, label, status, partial, saved, carried, expected
):
    """대신 저장 조건 = 최종 `sent` ∧ 부분 전송 아님 ∧ 첫 저장 표식 없음 ∧ 통합 본문 회차."""
    from app.runtime_evidence import holdings_risk_flow as rflow
    from app.runtime_evidence import sector_signal_state as sss

    p = tmp_path / "s.json"
    sss.save_sector_state(
        p, entries={"T1": _row(False, AC)}, today_kst=TODAY, sent_today=1
    )
    pending = {
        "sector_state_path": p,
        "tally_path": tmp_path / "tally.json",
        "today_kst": TODAY,
        "observed": [_sig("T1", AC)],
        "unevaluable": set(),
        "runtime_kst": _now().isoformat(),
        "tick_outcome": "no_signal",
        "entry_omitted": False,
        "candidates": frozenset({("T1", AC)}),
    }
    if carried:
        pending["sent_signals"] = [_sig("T1", AC)]
    record = {rflow.PENDING_KEY: pending, "partial_delivery": partial}
    if saved:
        record["intraday_state_saved"] = True
    rflow.apply_intraday_records(record, mode="send", status=status, reason=None)
    loaded = sss.load_sector_state(p, today_kst=TODAY)
    row = loaded.entries["T1"]
    assert (record.get("intraday_state_saved_by_observation") is True) is expected
    assert (row["last_sent_at"] == _now().isoformat()) is expected, label
    assert loaded.sent_today == (2 if expected else 1), label
    assert row["continuous"] is expected, label  # 미전달 후보 = 회복 유지
    assert rflow.PENDING_KEY not in record


_BASE = [
    # (id, 다시 읽을 파일, snapshot, 기대 sent_today, 기대 진단)
    ("reload_ok_ignores_snapshot", "ok", "today", 2, None),
    ("missing_keeps_existing_rule", "missing", "today", 0, None),
    ("date_reset_keeps_existing_rule", "yesterday", "today", 0, None),
    ("schema_mismatch_keeps_existing_rule", "schema", "today", 0, None),
    ("unreadable_uses_snapshot", "corrupt", "today", 9, "snapshot"),
    ("unreadable_no_snapshot", "corrupt", None, 0, "unreadable"),
    ("unreadable_snapshot_not_comparable", "corrupt", "fallback", 0, "unreadable"),
    ("unreadable_snapshot_other_day", "corrupt", "yesterday", 0, "unreadable"),
]


@pytest.mark.parametrize(
    "label, on_disk, snap, expected, diag", _BASE, ids=[r[0] for r in _BASE]
)
def test_unit_load_merge_base(tmp_path, label, on_disk, snap, expected, diag):
    """r1 F1 — 다시 읽기가 **읽기 실패**일 때만 이번 회차가 아는 상태를 쓴다. 없음 · 날짜
    바뀜 · 형식 다름 · 정상 읽기는 예전 규칙 그대로."""
    import json

    from app.runtime_evidence import sector_signal_state as sss

    p = tmp_path / "s.json"
    if on_disk in ("ok", "yesterday"):
        day = TODAY if on_disk == "ok" else "2026-11-18"
        sss.save_sector_state(
            p, entries={"T1": _row(True, AC)}, today_kst=day, sent_today=2
        )
    elif on_disk == "schema":
        p.write_text(json.dumps({"schema_version": "old", "sent_today": 2}), "utf-8")
    elif on_disk == "corrupt":
        p.write_text("{손상", encoding="utf-8")
    snapshot = {
        None: None,
        "today": sss.LoadedSectorState(
            entries={"T1": _row(True, AC)}, date_kst=TODAY, sent_today=9, fallback=False
        ),
        "yesterday": sss.LoadedSectorState(
            entries={}, date_kst="2026-11-18", sent_today=9, fallback=False
        ),
        "fallback": sss.LoadedSectorState(fallback=True, fallback_reason="unreadable"),
    }[snap]
    base, got = sss.load_merge_base(p, today_kst=TODAY, snapshot=snapshot)
    assert got == diag, label
    assert (base.sent_today if base.comparable else 0) == expected, label
    if diag == "snapshot":
        assert base is snapshot


def test_unit_apply_intraday_records_uses_snapshot_when_reload_unreadable(tmp_path):
    """r1 F1 — pending 의 `state_snapshot` 이 관측 저장 · 대신 저장의 기준이 된다."""
    from app.runtime_evidence import holdings_risk_flow as rflow
    from app.runtime_evidence import sector_signal_state as sss

    p = tmp_path / "s.json"
    p.write_text("{손상", encoding="utf-8")
    snap = sss.LoadedSectorState(
        entries={"A": _row(True, AC)}, date_kst=TODAY, sent_today=3, fallback=False
    )
    pending = {
        "sector_state_path": p,
        "tally_path": tmp_path / "tally.json",
        "today_kst": TODAY,
        "observed": [_sig("T1", AC)],
        "unevaluable": set(),
        "runtime_kst": _now().isoformat(),
        "tick_outcome": "no_signal",
        "entry_omitted": False,
        "candidates": frozenset({("T1", AC)}),
        "sent_signals": [_sig("T1", AC)],
        "state_snapshot": snap,
    }
    record = {rflow.PENDING_KEY: pending, "partial_delivery": False}
    rflow.apply_intraday_records(record, mode="send", status="sent", reason=None)
    loaded = sss.load_sector_state(p, today_kst=TODAY)
    assert record.get("intraday_observation_base") == "snapshot"
    assert record.get("intraday_state_saved_by_observation") is True
    assert loaded.sent_today == 4
    assert loaded.entries["A"]["last_sent_at"] == snap.entries["A"]["last_sent_at"]
    assert loaded.entries["A"]["continuous"] is False  # 이번 회차에 없음 → 회복 기록
    assert loaded.entries["T1"]["last_sent_at"] == _now().isoformat()
