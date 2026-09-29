"""POC3-02D-OPS-01 — 장중 위험 알림 흐름 운영 정정 C4 · C5 · C6 (확정 PLAN §3 · §4).

전부 **실제 `run()` 경로**를 통과시킨다. rig 는 `test_intraday_alert_flow_through`
의 것을 그대로 쓴다(그 파일은 KS-10 근접이라 여기에 새로 둔다 — 설계자 Q22).

```text
C4  구역 상한에 잘린 보유 급락은 worst 로 저장하지 않는다 → 다음 틱에 다시 나간다
C5  조립 뒤 failed 출구 4곳 → 집계 `send_failed` · 15:40 `발송 실패 N회`
C6  `message_text_length` = 조립된 최종 본문의 분할 전 길이
```

실제 Telegram·Naver·OCI write 는 **0건**이다 — 전송기·시세·상태 경로 전부 대역.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta

import pytest

from tests import test_intraday_alert_flow_through as ft
from tests.test_holdings_risk_alert_runner import _Sender

RISK_KIND = ft.RISK_KIND
TODAY = ft.TODAY

# 기존 rig fixture 재사용 — pytest 는 **모듈 속성 이름**으로 fixture 를 등록한다.
market_db = ft.market_db

# 보유 5종목. 전부 D5_7 이고 정렬(하락 큰 순)은 H00005 → H00001 이다.
_NAMES = {
    "H00001": "보유가",
    "H00002": "보유나",
    "H00003": "보유다",
    "H00004": "보유라",
    "H00005": "보유마",
}
_FIVE = {"H00001": -5.1, "H00002": -5.2, "H00003": -5.3, "H00004": -5.4, "H00005": -5.5}
_CARRIED = ["H00003", "H00004", "H00005"]  # 구역 상한 3 안에 든 것
_CUT = ["H00001", "H00002"]  # 잘린 것

# '기준' 다음 줄. C3 반영 뒤 `현재가` 는 러너 실행 시각(`runtime_kst`)이다 — byte
# 테스트는 헤더와 같은 시계에서 실행 시각을 고정한 뒤 이 형식으로 비교한다.
_QUOTE_LINE = "현재가 {when} · 직전 종가 2026-08-25"
_DISCLAIMER = "※ 자동 감지 결과이며, 최종 판단은 사용자가 합니다."


# ── 공용 도구 ───────────────────────────────────────────────────────────────


def _rig(monkeypatch, tmp_path, market_db, **kw):
    """기존 rig + 사업군 무조정 이력을 **tmp DB** 로 읽게 한다.

    rig 의 `DEFAULT_MARKET_DB` 교체는 효과가 없다 — `assemble_intraday_alert`
    의 `db_path` 기본값이 정의 시점에 묶여 라이브 DB 를 연다. 새 테스트는 라이브
    DB 를 열 수 없으므로(`_live_guard`) 읽는 함수 쪽에서 경로를 바꾼다.
    """
    import app.runtime_evidence.intraday_alert_flow as iflow

    rig = ft._build_rig(monkeypatch, tmp_path, market_db, **kw)
    real = iflow.load_unadjusted_history
    monkeypatch.setattr(
        iflow,
        "load_unadjusted_history",
        lambda tickers, *, db_path: real(tickers, db_path=market_db),
    )
    return rig


def _set_holdings(monkeypatch, names):
    import app.holdings as holdings_mod

    rows = [ft._H(t, n) for t, n in names.items()]
    monkeypatch.setattr(holdings_mod, "load", lambda *a, **k: list(rows))


def _set_quotes(rig, held, *, sector_ret=0.0, asof=None):
    """보유 등락률 + 사업군 대표 10종목(기본 보합 — 신호 없음 · 평가 정상)."""
    stamp = asof or ft._asof(TODAY)
    q = {t: ft._Q(9400.0, stamp, r) for t, r in held.items()}
    for i in range(10):
        q[f"T{i:05d}"] = ft._Q(10000.0, stamp, sector_ret)
    rig["quotes"] = q


def _clock(monkeypatch):
    """틱 시각 고정. `at(m)` → 헤더 `HH:MM`. registry 중복키가 `HH:MM` 이다."""
    from app.runtime_evidence import holdings_risk_flow as rflow

    base = rflow._now_kst(None)

    def at(minutes):
        ft._tick_at(monkeypatch, base, minutes)
        return (base + timedelta(minutes=minutes)).strftime("%H:%M")

    return at


def _risk_entries(rig):
    """러너가 `risk.save_entries` 를 읽어 **실제로 쓴** 위험 상태 파일."""
    p = rig["runner"].HOLDINGS_RISK_STATE_PATH
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))["entries"]


def _seed_risk(rig, entries, *, day=TODAY):
    from app.runtime_evidence.holdings_risk_state import save_risk_state

    save_risk_state(
        rig["runner"].HOLDINGS_RISK_STATE_PATH, entries=entries, today_kst=day
    )


def _tally(rig):
    from app.runtime_evidence.intraday_checkup_tally import load_tally

    return load_tally(rig["tally"], today_kst=TODAY)


# ═══ C4 — 잘린 보유 급락의 잘못된 억제 ═══════════════════════════════════════


def test_c4_cut_held_drops_are_not_saved_as_worst(monkeypatch, tmp_path, market_db):
    """5종목 신규 급락 · 상한 3 → 본문 3 · **저장 3**.

    저장은 러너가 쓴 상태 파일로 본다 — `RiskAssembly` 에 대입하는 잘못된
    구현(러너가 읽지 않는 새 속성)도 여기서 실패한다.
    """
    rig = _rig(monkeypatch, tmp_path, market_db)
    _set_holdings(monkeypatch, _NAMES)
    _clock(monkeypatch)(0)
    _set_quotes(rig, _FIVE)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent", rec
    body = rig["sent"].calls[-1]
    for t in _CARRIED:
        assert _NAMES[t] in body
    for t in _CUT:
        assert _NAMES[t] not in body
    assert "intraday_error" not in rec, rec.get("intraday_error")
    assert sorted(_risk_entries(rig)) == _CARRIED, "잘린 급락이 발송 완료로 저장됐다"


def test_c4_cut_drops_are_sent_on_next_tick(monkeypatch, tmp_path, market_db):
    """같은 날 다음 틱 · 같은 시세 → 앞 3종목 억제 · **잘린 2종목 발송** · 저장 5."""
    rig = _rig(monkeypatch, tmp_path, market_db)
    _set_holdings(monkeypatch, _NAMES)
    at = _clock(monkeypatch)
    at(0)
    _set_quotes(rig, _FIVE)
    assert rig["runner"].run(RISK_KIND, "send")["status"] == "sent"

    at(60)
    _set_quotes(rig, _FIVE)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent", f"잘린 급락이 억제됐다: {rec.get('reason')}"
    body = rig["sent"].calls[-1]
    for t in _CUT:
        assert _NAMES[t] in body
    for t in _CARRIED:
        assert _NAMES[t] not in body, f"{t} 는 이미 나갔는데 다시 실렸다"
    entries = _risk_entries(rig)
    assert sorted(entries) == sorted(_FIVE)
    assert {e["worst_state"] for e in entries.values()} == {"D5_7"}


def test_c4_cut_worsened_keeps_previous_worst(monkeypatch, tmp_path, market_db):
    """잘린 **악화**: X 가 D5_7 → D10_PLUS 인데 잘리면 저장 worst 는 D5_7 유지.

    다음 틱에 X 가 다시 악화로 잡혀 나간다.
    """
    names = {t: _NAMES[t] for t in ("H00001", "H00002", "H00003", "H00004")}
    quotes = {"H00001": -5.3, "H00002": -5.4, "H00003": -5.5, "H00004": -11.0}
    rig = _rig(monkeypatch, tmp_path, market_db)
    _set_holdings(monkeypatch, names)
    _seed_risk(rig, {"H00004": {"worst_state": "D5_7"}})
    at = _clock(monkeypatch)
    at(0)
    _set_quotes(rig, quotes)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent", rec
    # 본문 순서 = 신규 → 악화. 신규 3개가 구역을 채워 X(악화)가 잘린다.
    assert "보유라" not in rig["sent"].calls[-1]
    entries = _risk_entries(rig)
    assert entries["H00004"]["worst_state"] == "D5_7", "잘린 악화가 worst 로 기록됐다"
    assert sorted(entries) == ["H00001", "H00002", "H00003", "H00004"]

    at(60)
    _set_quotes(rig, quotes)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent", f"잘린 악화가 사라졌다: {rec.get('reason')}"
    body = rig["sent"].calls[-1]
    assert "• 보유라: 전일 대비 -11.0%\n  보유 급락 10% 이상" in body
    assert _risk_entries(rig)["H00004"]["worst_state"] == "D10_PLUS"


def test_c4_date_reset_first_tick_does_not_save_cut_new(
    monkeypatch, tmp_path, market_db
):
    """날짜가 바뀐 첫 틱(`date_reset`) — 전부 신규 · 잘린 신규는 저장하지 않는다."""
    rig = _rig(monkeypatch, tmp_path, market_db)
    _set_holdings(monkeypatch, _NAMES)
    _seed_risk(rig, {t: {"worst_state": "D10_PLUS"} for t in _FIVE}, day="2000-01-03")
    _clock(monkeypatch)(0)
    _set_quotes(rig, _FIVE)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent", rec
    assert rec["risk_state_fallback"] == "date_reset"
    assert sorted(_risk_entries(rig)) == _CARRIED


def test_c4_recompute_exception_falls_back_to_legacy_path(
    monkeypatch, tmp_path, market_db
):
    """재계산 예외 → 기존 '장중 조립 예외' 경로와 같다.

    구 본문 발송 · 위험 상태 **전체** 저장 · 사업군 발송 상태(`last_sent_at`·
    `sent_today`)와 집계 파일은 쓰지 않는다.
    """
    from app.runtime_evidence import holdings_risk_flow as rflow
    from app.runtime_evidence.sector_signal_state import save_sector_state

    rig = _rig(monkeypatch, tmp_path, market_db)
    _set_holdings(monkeypatch, _NAMES)
    save_sector_state(rig["sector_state"], entries={}, today_kst=TODAY, sent_today=1)
    before = ft._hashes(rig)

    real = rflow.merge_worst
    calls = []

    def _second_call_raises(**kw):
        # 1회차 = 조립 시점 선정 전체 · 2회차 = 본문 기준 재계산.
        calls.append(kw)
        if len(calls) >= 2:
            raise RuntimeError("재계산 주입")
        return real(**kw)

    monkeypatch.setattr(rflow, "merge_worst", _second_call_raises)
    _clock(monkeypatch)(0)
    _set_quotes(rig, _FIVE)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent", rec
    body = rig["sent"].calls[-1]
    assert "[보유 급락 알림]" in body and "[장중 급등락]" not in body
    for t in _FIVE:
        assert _NAMES[t] in body
    assert "intraday_error" in rec
    assert sorted(_risk_entries(rig)) == sorted(_FIVE)
    assert ft._hashes(rig) == before, "구 본문이 나갔는데 사업군 상태·집계를 썼다"
    assert "intraday_tally_outcome" not in rec


def test_c4_exception_after_intraday_assignment_keeps_full_save(
    monkeypatch, tmp_path, market_db
):
    """재계산은 성공 · 장중 조립 **뒤**(본문 대체 전) 예외 → 구 본문 5 · 저장 5.

    저장 대상은 본문 대체 분기에서만 바뀐다(PLAN C4 조건 1). 계산 직후에
    대입하면 구 본문 5종목이 나가는데 3종목만 저장돼, 다음 틱에 이미 보낸
    2종목이 다시 나간다. 이름의 '대입' 은 OPS-01 당시 `out.intraday` 대입 위치다
    — POC3-02D-OPS-02 Q2 로 그 대입은 본문 대체 분기로 옮겨졌고, 이 경로의
    사업군 발송 상태 · 관측 · 집계 0 은 `test_poc3_02d_ops02_delivery_state.py`
    가 단언한다(OPS-01 때는 Q8 알려진 한계였다).
    """
    import app.runtime_evidence.intraday_alert_flow as iflow

    rig = _rig(monkeypatch, tmp_path, market_db)
    _set_holdings(monkeypatch, _NAMES)
    real = iflow.assemble_intraday_alert

    def _bad_unevaluable(**kw):
        res = real(**kw)
        # 조립 뒤 `intraday_records` 구성의 `set(...)` 에서 TypeError 가 난다.
        res.unevaluable = 5
        return res

    monkeypatch.setattr(iflow, "assemble_intraday_alert", _bad_unevaluable)
    _clock(monkeypatch)(0)
    _set_quotes(rig, _FIVE)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent", rec
    assert rec["intraday_error"].startswith("TypeError"), rec
    body = rig["sent"].calls[-1]
    assert "[보유 급락 알림]" in body and "[장중 급등락]" not in body
    for t in _FIVE:
        assert _NAMES[t] in body
    assert sorted(_risk_entries(rig)) == sorted(_FIVE), "구 본문 5종목인데 일부만 저장"


def test_c4_unified_body_bytes_unchanged(monkeypatch, tmp_path, market_db):
    """정정 **전에** 먼저 통과시킨 단언 — 정정 뒤에도 본문 byte 가 같다."""
    from app.runtime_evidence import holdings_risk_flow as rflow

    rig = _rig(monkeypatch, tmp_path, market_db)
    _set_holdings(monkeypatch, _NAMES)
    hhmm = _clock(monkeypatch)(0)
    # C3 — 실행 시각을 헤더와 같은 시계로 고정한다(`_now_kst` 는 `_clock` 이 고정).
    now = rflow._now_kst(None)
    monkeypatch.setattr(rig["runner"], "kst_now_iso", lambda: now.isoformat())
    _set_quotes(rig, _FIVE)
    assert rig["runner"].run(RISK_KIND, "send")["status"] == "sent"
    assert rig["sent"].calls[-1] == (
        f"[장중 급등락] {hhmm}\n"
        "\n"
        "보유종목\n"
        "• 보유마: 전일 대비 -5.5%\n"
        "  보유 급락 5~7%\n"
        "• 보유라: 전일 대비 -5.4%\n"
        "  보유 급락 5~7%\n"
        "• 보유다: 전일 대비 -5.3%\n"
        "  보유 급락 5~7%\n"
        "\n"
        "기준\n"
        f"{_QUOTE_LINE.format(when=now.strftime('%Y-%m-%d %H:%M'))}\n"
        "\n"
        f"{_DISCLAIMER}"
    )


def _legacy_five_body(rec):
    rk = rec["runtime_kst"]
    lines = [
        f"[보유 급락 알림] {rk[11:16]} — 보유 5종목 중 5종목 동시 하락",
        f"기준: 직전 거래일 종가 2026-08-25 · 시세 {rk[:10]} {rk[11:16]}",
        "",
        "■ 전일 대비 하락 5~7% (5)",
    ]
    for t in ("H00005", "H00004", "H00003", "H00002", "H00001"):
        lines.append(f"  {_NAMES[t]}")
        lines.append(f"      전일 대비 {_FIVE[t]:+.1f}% · 고점 대비 -6.0%")
    return "\n".join(lines)


def test_c4_policy_disabled_keeps_legacy_body_and_full_save(
    monkeypatch, tmp_path, market_db
):
    """회귀 — 정책 비활성 5종목 → 구 본문 5 · 저장 5 · 본문 byte 동일."""
    rig = _rig(monkeypatch, tmp_path, market_db)
    rig["policy"] = ft._policy(enabled=False)
    _set_holdings(monkeypatch, _NAMES)
    _set_quotes(rig, _FIVE)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent", rec
    assert rig["sent"].calls[-1] == _legacy_five_body(rec)
    assert sorted(_risk_entries(rig)) == sorted(_FIVE)
    # 정책 비활성은 격리(예외) 경로가 아니다 — 재계산 guard 가 빠지면
    # `plan=None` 에서 터져 격리로 가고 이 진단이 사라진다.
    assert "intraday_error" not in rec, rec.get("intraday_error")
    assert rec.get("intraday_policy_enabled") is False, rec


def test_c4_intraday_assembly_exception_keeps_full_save(
    monkeypatch, tmp_path, market_db
):
    """회귀 — 장중 조립 예외 → 구 본문 5 · 저장 5."""
    import app.runtime_evidence.intraday_alert_flow as iflow

    rig = _rig(monkeypatch, tmp_path, market_db)
    _set_holdings(monkeypatch, _NAMES)
    monkeypatch.setattr(
        iflow,
        "assemble_intraday_alert",
        lambda **kw: (_ for _ in ()).throw(RuntimeError("장중 폭발")),
    )
    _set_quotes(rig, _FIVE)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent", rec
    assert rig["sent"].calls[-1] == _legacy_five_body(rec)
    assert sorted(_risk_entries(rig)) == sorted(_FIVE)
    # C6 — 격리 경로에서도 실제로 나간 구 본문 길이를 남긴다(0 이면 C6 결함 재발).
    assert rec["intraday_error"].startswith("RuntimeError"), rec
    assert rec["message_text_length"] > 0
    _assert_length_recorded(rig, rec, len(rig["sent"].calls[-1]))


def test_c4_daily_cap_tick_leaves_risk_state_untouched(
    monkeypatch, tmp_path, market_db
):
    """회귀 — 일일 상한 회차는 위험 상태 파일을 바꾸지 않는다."""
    from app.runtime_evidence.sector_signal_state import save_sector_state

    rig = _rig(monkeypatch, tmp_path, market_db)
    _set_holdings(monkeypatch, _NAMES)
    _seed_risk(rig, {"H00005": {"worst_state": "D5_7"}})
    before = rig["runner"].HOLDINGS_RISK_STATE_PATH.read_bytes()
    save_sector_state(rig["sector_state"], entries={}, today_kst=TODAY, sent_today=4)
    _set_quotes(rig, _FIVE)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["reason"] == "intraday_daily_cap_reached", rec
    assert rig["sent"].calls == []
    assert rig["runner"].HOLDINGS_RISK_STATE_PATH.read_bytes() == before


@pytest.mark.parametrize(
    "sender",
    [_Sender(sent=False), _Sender(sent=True, partial=True)],
    ids=["telegram_failure", "partial_delivery"],
)
def test_c4_failed_or_partial_send_saves_nothing(
    monkeypatch, tmp_path, market_db, sender
):
    """회귀 — Telegram 실패 · 부분 전송 → 위험 상태 저장 없음."""
    sender.calls.clear()
    rig = _rig(monkeypatch, tmp_path, market_db, sender=sender)
    _set_holdings(monkeypatch, _NAMES)
    _set_quotes(rig, _FIVE)
    rig["runner"].run(RISK_KIND, "send")
    assert sender.calls, "전송기가 불리지 않았다"
    assert _risk_entries(rig) is None


# ═══ C3 — 장중 본문 '기준' 줄의 `현재가` 시각 ═══════════════════════════════
# 사용자 실수신 원문(2026-09-27 전달): `현재가 ㅡ. 직전 종가 2026-09-22` — 시각 없이
# 줄표만 찍혔다. 운영 경로가 채워지지 않는 진단 키를 읽었기 때문이다. 설계자 R2 ·
# Q9 (a): 실행 시각(`format_quote_asof(runtime_kst)`)을 쓴다 — 헤더 HH:MM · 구
# [보유 급락 알림] '시세' 와 같은 값이다.

_QUOTE_RE = re.compile(r"^현재가 \d{4}-\d{2}-\d{2} \d{2}:\d{2} · 직전 종가 ")


def _pin_runtime(monkeypatch, rig, hhmm="10:30"):
    """러너 실행 시각(`runtime_kst`)을 고정한다 — 헤더와 '현재가' 가 같은 값에서 온다."""
    iso = f"{TODAY}T{hhmm}:12+09:00"
    monkeypatch.setattr(rig["runner"], "kst_now_iso", lambda: iso)
    return iso


def _basis_next_line(body):
    lines = body.split("\n")
    return lines[lines.index("기준") + 1]


def test_c3_unified_body_shows_runtime_as_quote_time(monkeypatch, tmp_path, market_db):
    """run() 관통 — '기준' 다음 줄이 `현재가 YYYY-MM-DD HH:MM · 직전 종가 …` 다."""
    rig = _rig(monkeypatch, tmp_path, market_db)
    _pin_runtime(monkeypatch, rig)
    _set_quotes(rig, {"H00001": -6.0})
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent", rec  # 금지 문구 · raw 식별자 가드 통과
    body = rig["sent"].calls[-1]
    assert body.startswith("[장중 급등락] 10:30\n"), body
    line = _basis_next_line(body)
    assert _QUOTE_RE.match(line), line
    assert line.startswith(f"현재가 {TODAY} 10:30 · 직전 종가 "), line
    assert "현재가 —" not in body


@pytest.mark.parametrize("enabled", [False, True], ids=["legacy", "unified"])
def test_c3_legacy_and_unified_bodies_share_the_same_time(
    monkeypatch, tmp_path, market_db, enabled
):
    """규약 일치 — 구 본문 '시세' 와 통합 본문 '현재가' 가 같은 실행 시각이다."""
    rig = _rig(monkeypatch, tmp_path, market_db)
    rig["policy"] = ft._policy(enabled=enabled)
    _pin_runtime(monkeypatch, rig)
    _set_quotes(rig, {"H00001": -6.0})
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent", rec
    body = rig["sent"].calls[-1]
    if enabled:
        assert f"현재가 {TODAY} 10:30 · 직전 종가 " in body, body
    else:
        assert f"시세 {TODAY} 10:30" in body, body


def test_c3_render_default_without_quote_time_is_unchanged():
    """렌더 계약은 그대로 — 값이 없으면 여전히 `현재가 —` 다(흐름만 고쳤다)."""
    from app.runtime_evidence.intraday_alert_render import (
        build_section_plan,
        render_intraday_alert,
    )
    from app.runtime_evidence.sector_signal import STATE_AVOID_DROP
    from tests.test_intraday_alert_render import _sig

    plan = build_section_plan(
        held_drop=[],
        held_surge=[],
        sector_signals=[_sig("A1", STATE_AVOID_DROP, -2.4)],
        max_items_per_section=3,
    )
    text = render_intraday_alert(
        plan, slot_label="10:30", quote_asof=None, base_close_date="2026-09-22"
    )
    assert "현재가 — · 직전 종가 2026-09-22" in text


# ═══ C5 — Telegram 실패 집계 ═════════════════════════════════════════════════


def test_c5_send_false_is_counted_as_send_failed(monkeypatch, tmp_path, market_db):
    """`sent=False` → failed/`telegram_send_error` · 집계 `send_failed` 1 · 신호 없음 0."""
    rig = _rig(monkeypatch, tmp_path, market_db, sender=_Sender(sent=False))
    _set_quotes(rig, {"H00001": -6.0})
    rec = rig["runner"].run(RISK_KIND, "send")
    assert (rec["status"], rec["reason"]) == ("failed", "telegram_send_error"), rec
    assert rec["intraday_tally_outcome"] == "send_failed"
    t = _tally(rig)
    assert (t.checks, t.send_failed, t.no_signal, t.failed, t.sent) == (1, 1, 0, 0, 0)


def _long_names():
    # 통합 본문(구역 상한 3)이 4,000자를 넘도록 긴 이름 3개.
    return {f"H0000{i}": f"긴이름{i}" + "가" * 1500 for i in (1, 2, 3)}


def _real_telegram(monkeypatch, *, fail_at=None):
    """실제 `telegram_send` 분할 로직 + **네트워크 없는** 청크 전송 대역."""
    import app.three_push_runner_common as common

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-" + "z" * 24)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat-test-id-zz")
    chunks = []

    def _one(token, chat_id, text):
        chunks.append(text)
        if fail_at is not None and len(chunks) >= fail_at:
            return False, "mock chunk 실패"
        return True, None

    monkeypatch.setattr(common, "_telegram_send_one", _one)
    full = []

    def _send(text):
        full.append(text)
        return common.telegram_send(text)

    return _send, full, chunks


def test_c5_realistic_partial_delivery_is_send_failed(monkeypatch, tmp_path, market_db):
    """실제형 부분 전송 — 첫 청크 성공 · 둘째 실패 → `sent=False` · partial."""
    send, full, chunks = _real_telegram(monkeypatch, fail_at=2)
    rig = _rig(monkeypatch, tmp_path, market_db, sender=send)
    names = _long_names()
    _set_holdings(monkeypatch, names)
    _set_quotes(rig, {t: -6.0 for t in names})
    rec = rig["runner"].run(RISK_KIND, "send")
    assert len(chunks) == 2 and len(full[-1]) > 4000
    assert (rec["status"], rec["reason"]) == ("failed", "telegram_send_error"), rec
    assert rec["telegram_sent"] is False and rec["partial_delivery"] is True
    assert rec["intraday_tally_outcome"] == "send_failed"
    assert _tally(rig).send_failed == 1


def test_c5_lookup_failure_overlapping_send_failure_is_one_send_failed_tick(
    monkeypatch, tmp_path, market_db
):
    """사업군 조회 실패 + 전송 실패가 같은 틱 → 틱 1개 · `send_failed`.

    조회 실패가 그 틱뿐이면 `조회 실패` 토큰은 없고 `발송 실패 1회` 만 붙는다.
    """
    from app.runtime_evidence.intraday_checkup_tally import render_summary_line

    rig = _rig(monkeypatch, tmp_path, market_db, sender=_Sender(sent=False))
    _set_quotes(rig, {"H00001": -6.0})
    ft._blind_sectors(rig)  # 사업군 전체 평가 불가 → 잠정값 `failed`
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["reason"] == "telegram_send_error", rec
    t = _tally(rig)
    assert (t.checks, t.failed, t.send_failed) == (1, 0, 1), t
    line = render_summary_line(t)
    assert "조회 실패" not in line
    assert (
        line
        == "장중 점검 1회 · 알림 0건 · 중복 억제 0건 · 신호 없음 0건 · 발송 실패 1회"
    )


def _inject_forbidden(monkeypatch, rig):
    _set_holdings(monkeypatch, {"H00001": "보유 매도 지시"})


def _inject_raw_identifier(monkeypatch, rig):
    _set_holdings(monkeypatch, {"H00001": "보유 param_id"})


def _inject_registry_error(monkeypatch, rig):
    def _boom(*a, **k):
        raise RuntimeError("registry 손상 주입")

    monkeypatch.setattr(rig["runner"], "is_already_sent", _boom)


@pytest.mark.parametrize(
    "inject, reason",
    [
        (_inject_forbidden, "forbidden_wording"),
        (_inject_raw_identifier, "raw_identifier_exposed"),
        (_inject_registry_error, "registry_corrupted"),
    ],
)
def test_c5_other_failed_exits_are_send_failed(
    monkeypatch, tmp_path, market_db, inject, reason
):
    """조립 뒤 발송 전 failed 출구 3곳 → 각각 `send_failed`."""
    rig = _rig(monkeypatch, tmp_path, market_db)
    inject(monkeypatch, rig)
    _set_quotes(rig, {"H00001": -6.0})
    rec = rig["runner"].run(RISK_KIND, "send")
    assert (rec["status"], rec["reason"]) == ("failed", reason), rec
    assert rig["sent"].calls == []
    assert rec["intraday_tally_outcome"] == "send_failed"
    t = _tally(rig)
    assert (t.checks, t.send_failed, t.no_signal) == (1, 1, 0), t


def _cap(rig):
    from app.runtime_evidence.sector_signal_state import save_sector_state

    save_sector_state(rig["sector_state"], entries={}, today_kst=TODAY, sent_today=4)
    _set_quotes(rig, {"H00001": -6.0})


@pytest.mark.parametrize(
    "arrange, outcome",
    [
        (lambda rig: _set_quotes(rig, {"H00001": -6.0}), "sent"),
        (_cap, "suppressed"),
        (lambda rig: _set_quotes(rig, {"H00001": -1.0}), "no_signal"),
        (
            lambda rig: (_set_quotes(rig, {"H00001": -1.0}), ft._blind_sectors(rig)),
            "failed",
        ),
    ],
    ids=["sent", "daily_cap", "no_signal_skip", "lookup_failure_only"],
)
def test_c5_regression_tick_outcomes(
    monkeypatch, tmp_path, market_db, arrange, outcome
):
    """회귀 — 성공은 sent · 상한 · 신호 없음 skip · 조회 실패만은 기존 값."""
    rig = _rig(monkeypatch, tmp_path, market_db)
    arrange(rig)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["intraday_tally_outcome"] == outcome, rec


def test_c5_sector_state_save_error_after_send_is_still_sent(
    monkeypatch, tmp_path, market_db
):
    """Q13 — 발송 성공 뒤 사업군 상태 저장이 터져도 집계는 최종 status(sent).

    기존 정정(`runner_evidence`)은 상태 저장 뒤에만 sent 로 고친다. 그래서
    이 경우는 `apply_intraday_records` 의 성공 확정만이 sent 를 만든다.
    """
    import app.runtime_evidence.sector_signal_state as sss

    rig = _rig(monkeypatch, tmp_path, market_db)

    def _raise(*a, **k):
        raise RuntimeError("사업군 상태 저장 실패 주입")

    monkeypatch.setattr(sss, "save_sector_state", _raise)  # rig 준비 뒤에 바꾼다
    _set_quotes(rig, {"H00001": -6.0})
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent", rec
    assert "intraday_state_save_error" in rec, rec
    assert rec["intraday_tally_outcome"] == "sent", rec
    t = _tally(rig)
    assert (t.checks, t.sent, t.no_signal) == (1, 1, 0), t


def test_c5_partial_success_keeps_provisional_outcome(monkeypatch, tmp_path, market_db):
    """`sent=True` · 부분 전송 → 발송 완료가 아니다 → 잠정값(신호 없음) 유지."""
    rig = _rig(
        monkeypatch, tmp_path, market_db, sender=_Sender(sent=True, partial=True)
    )
    _set_quotes(rig, {"H00001": -6.0})
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent" and rec["partial_delivery"] is True, rec
    assert rec["intraday_tally_outcome"] == "no_signal", rec
    t = _tally(rig)
    assert (t.checks, t.sent, t.no_signal, t.send_failed) == (1, 0, 1, 0), t


def test_c5_gates_write_nothing_even_when_send_would_fail(
    monkeypatch, tmp_path, market_db
):
    """회귀 — dry-run · flag-off · duplicate 는 집계·관측 파일 hash 불변."""
    failing = _Sender(sent=False)
    rig = _rig(monkeypatch, tmp_path, market_db, sender=failing)
    at = _clock(monkeypatch)
    at(0)
    _set_quotes(rig, {"H00001": -6.0}, sector_ret=5.0)

    before = ft._hashes(rig)
    assert rig["runner"].run(RISK_KIND, "dry-run")["status"] == "dry_run_success"
    assert ft._hashes(rig) == before, "dry-run 이 라이브 파일을 바꿨다"

    monkeypatch.setenv("PUSH_AUTOSEND_HOLDINGS_RISK_ALERT_ENABLED", "false")
    assert rig["runner"].run(RISK_KIND, "send")["reason"] == "push_kind_disabled"
    assert ft._hashes(rig) == before, "flag-off 가 라이브 파일을 바꿨다"
    assert failing.calls == []

    monkeypatch.setenv("PUSH_AUTOSEND_HOLDINGS_RISK_ALERT_ENABLED", "true")
    failing._sent = True
    assert rig["runner"].run(RISK_KIND, "send")["status"] == "sent"
    failing._sent = False
    before = ft._hashes(rig)
    _set_quotes(rig, {"H00001": -7.5}, sector_ret=5.2)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["reason"] == "duplicate_runtime", rec
    assert ft._hashes(rig) == before, "duplicate 회차가 집계를 올렸다"


def test_c5_render_line_bytes_unchanged_without_send_failures():
    """`send_failed=0`(기본) → 기존 문자열 byte 동일."""
    from app.runtime_evidence.intraday_alert_render import render_checkup_summary

    with_failed = dict(checks=7, sent=1, suppressed=2, no_signal=3, failed=1)
    expect = "장중 점검 7회 · 알림 1건 · 중복 억제 2건 · 신호 없음 3건 · 조회 실패 1회"
    assert render_checkup_summary(**with_failed) == expect
    assert render_checkup_summary(**with_failed, send_failed=0) == expect
    plain = dict(checks=7, sent=2, suppressed=3, no_signal=2)
    expect = "장중 점검 7회 · 알림 2건 · 중복 억제 3건 · 신호 없음 2건"
    assert render_checkup_summary(**plain) == expect
    assert render_checkup_summary(**plain, send_failed=0) == expect


def test_c5_render_line_appends_send_failed_token():
    from app.runtime_evidence.intraday_alert_render import render_checkup_summary

    assert (
        render_checkup_summary(
            checks=3, sent=1, suppressed=0, no_signal=0, failed=1, send_failed=1
        )
        == "장중 점검 3회 · 알림 1건 · 중복 억제 0건 · 신호 없음 0건 · 조회 실패 1회 · 발송 실패 1회"
    )
    assert (
        render_checkup_summary(
            checks=2, sent=0, suppressed=0, no_signal=0, send_failed=2
        )
        == "장중 점검 2회 · 알림 0건 · 중복 억제 0건 · 신호 없음 0건 · 발송 실패 2회"
    )
    assert (
        render_checkup_summary(
            checks=0, sent=0, suppressed=0, no_signal=0, send_failed=1, unknown=True
        )
        == "장중 점검 확인 불가"
    )


def test_c5_old_v1_tally_file_loads_identically(tmp_path):
    """구 v1 집계 파일(`send_failed` 없음)을 읽은 결과가 같다 — 스키마 v1 유지."""
    from app.runtime_evidence import intraday_checkup_tally as tally_mod

    p = tmp_path / "old.json"
    p.write_text(
        json.dumps(
            {
                "schema_version": "intraday_checkup_tally.v1",
                "date_kst": TODAY,
                "ticks": [
                    {"outcome": "sent", "at": f"{TODAY}T09:30:00+09:00"},
                    {"outcome": "suppressed", "at": f"{TODAY}T10:30:00+09:00"},
                    {"outcome": "no_signal", "at": f"{TODAY}T11:30:00+09:00"},
                    {"outcome": "failed", "at": f"{TODAY}T12:30:00+09:00"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    t = tally_mod.load_tally(p, today_kst=TODAY)
    assert (t.checks, t.sent, t.suppressed, t.no_signal, t.failed, t.unknown) == (
        4,
        1,
        1,
        1,
        1,
        False,
    )
    assert t.send_failed == 0
    assert tally_mod.render_summary_line(t) == (
        "장중 점검 4회 · 알림 1건 · 중복 억제 1건 · 신호 없음 1건 · 조회 실패 1회"
    )
    assert tally_mod.SCHEMA_VERSION == "intraday_checkup_tally.v1"


def test_c5_record_tick_keeps_send_failed(tmp_path):
    """`record_tick` 이 `send_failed` 를 `no_signal` 로 바꾸지 않는다."""
    from app.runtime_evidence import intraday_checkup_tally as tally_mod

    p = tmp_path / "t.json"
    tally_mod.record_tick(p, today_kst=TODAY, outcome=tally_mod.OUTCOME_SEND_FAILED)
    body = json.loads(p.read_text(encoding="utf-8"))
    assert body["schema_version"] == "intraday_checkup_tally.v1"
    assert [x["outcome"] for x in body["ticks"]] == ["send_failed"]
    assert tally_mod.OUTCOME_SEND_FAILED in tally_mod.VALID_OUTCOMES


def test_c5_send_failed_reaches_the_1540_briefing(monkeypatch, tmp_path, market_db):
    """관통 — 실패 틱 → 집계 파일 → 15:40 보유 브리핑 말미 줄."""
    rig = _rig(monkeypatch, tmp_path, market_db, sender=_Sender(sent=False))
    _set_quotes(rig, {"H00001": -6.0})
    assert rig["runner"].run(RISK_KIND, "send")["reason"] == "telegram_send_error"
    # 15:40 도구는 `tally_{state}.json` 을 읽는다 — 러너가 쓴 파일을 그대로 넘긴다.
    (tmp_path / "tally_run.json").write_bytes(rig["tally"].read_bytes())
    out = ft._selection_at_close(
        monkeypatch, tmp_path, policy={"enabled": True}, tally_state="run"
    )
    assert out.message_text.endswith(
        "장중 점검 1회 · 알림 0건 · 중복 억제 0건 · 신호 없음 0건 · 발송 실패 1회"
    ), out.message_text


# ═══ C6 — `message_text_length` ══════════════════════════════════════════════


def _assert_length_recorded(rig, rec, expected):
    """record · JSONL 마지막 행 · tmp DB 최신 행이 모두 같은 값."""
    from app.runtime_execution_status_store import latest_execution_status

    assert rec["message_text_length"] == expected, rec
    lines = rig["runner"]._HISTORY_PATH.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[-1])["message_text_length"] == expected
    assert latest_execution_status()["message_text_length"] == expected


@pytest.mark.parametrize("enabled", [False, True], ids=["legacy", "unified"])
def test_c6_length_equals_sent_body(monkeypatch, tmp_path, market_db, enabled):
    """구 본문 · 통합 본문 발송 → 보낸 본문 길이와 같다."""
    rig = _rig(monkeypatch, tmp_path, market_db)
    rig["policy"] = ft._policy(enabled=enabled)
    _set_quotes(rig, {"H00001": -6.0})
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent", rec
    body = rig["sent"].calls[-1]
    assert ("[장중 급등락]" in body) is enabled
    _assert_length_recorded(rig, rec, len(body))


def test_c6_split_send_records_full_pre_split_length(monkeypatch, tmp_path, market_db):
    """4,000자 초과(분할 발송) → **분할 전** 전체 길이."""
    send, full, chunks = _real_telegram(monkeypatch)
    rig = _rig(monkeypatch, tmp_path, market_db, sender=send)
    names = _long_names()
    _set_holdings(monkeypatch, names)
    _set_quotes(rig, {t: -6.0 for t in names})
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent", rec
    assert len(chunks) >= 2 and len(full[-1]) > 4000
    _assert_length_recorded(rig, rec, len(full[-1]))


def _no_new_or_worsened(monkeypatch, rig):
    _set_quotes(rig, {"H00001": -1.0})


def _daily_cap(monkeypatch, rig):
    _cap(rig)


def _non_trading_day(monkeypatch, rig):
    _set_quotes(rig, {"H00001": -6.0}, asof="2020-01-02T15:30:00+09:00")


def _assembly_error(monkeypatch, rig):
    import app.market_data_store as store2

    def _boom(t, **kw):
        raise RuntimeError("이력 조회 폭발")

    monkeypatch.setattr(store2, "fetch_price_history", _boom)
    _set_quotes(rig, {"H00001": -6.0})


@pytest.mark.parametrize(
    "arrange, reason",
    [
        (_no_new_or_worsened, "no_new_or_worsened"),
        (_daily_cap, "intraday_daily_cap_reached"),
        (_non_trading_day, "non_trading_day"),
        (_assembly_error, "holdings_risk_error"),
    ],
)
def test_c6_zero_when_no_body_was_assembled(
    monkeypatch, tmp_path, market_db, arrange, reason
):
    """본문이 빈 회차 · 조립 전에 끝나는 회차 → 0."""
    rig = _rig(monkeypatch, tmp_path, market_db)
    arrange(monkeypatch, rig)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["reason"] == reason, rec
    assert rig["sent"].calls == []
    _assert_length_recorded(rig, rec, 0)


def test_c6_send_error_records_assembled_length(monkeypatch, tmp_path, market_db):
    """`telegram_send_error` → 조립 길이(0 아님) — 길이 > 0 ≠ 발송."""
    rig = _rig(monkeypatch, tmp_path, market_db, sender=_Sender(sent=False))
    _set_quotes(rig, {"H00001": -6.0})
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["reason"] == "telegram_send_error", rec
    assert rec["telegram_sent"] is False
    _assert_length_recorded(rig, rec, len(rig["sent"].calls[-1]))
    assert rec["message_text_length"] > 0


def test_c6_autosend_disabled_records_assembled_length(
    monkeypatch, tmp_path, market_db
):
    """`autosend_disabled` → 조립 길이. 기대값은 같은 틱을 켜고 **실제로 보낸** 본문."""
    rig = _rig(monkeypatch, tmp_path, market_db)
    _clock(monkeypatch)(0)
    _set_quotes(rig, {"H00001": -6.0})
    monkeypatch.setenv("PUSH_AUTOSEND_ENABLED", "false")
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["reason"] == "autosend_disabled", rec
    assert rig["sent"].calls == []

    monkeypatch.setenv("PUSH_AUTOSEND_ENABLED", "true")
    assert rig["runner"].run(RISK_KIND, "send")["status"] == "sent"
    sent_len = len(rig["sent"].calls[-1])
    assert sent_len > 0 and rec["message_text_length"] == sent_len
    lines = rig["runner"]._HISTORY_PATH.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[-2])["message_text_length"] == sent_len


def test_c6_duplicate_runtime_records_assembled_length(
    monkeypatch, tmp_path, market_db
):
    """`duplicate_runtime` → 조립 길이.

    기대값은 같은 입력을 다음 틱에 **실제로 보낸** 본문 길이다 — 헤더 `HH:MM` 만
    다르고 길이는 같다.
    """
    rig = _rig(monkeypatch, tmp_path, market_db)
    at = _clock(monkeypatch)
    at(0)
    _set_quotes(rig, {"H00001": -6.0})
    assert rig["runner"].run(RISK_KIND, "send")["status"] == "sent"

    _set_quotes(rig, {"H00001": -7.5})  # 악화 — 본문이 생기고 같은 분이라 중복
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["reason"] == "duplicate_runtime", rec
    assert len(rig["sent"].calls) == 1

    at(60)
    _set_quotes(rig, {"H00001": -7.5})
    assert rig["runner"].run(RISK_KIND, "send")["status"] == "sent"
    sent_len = len(rig["sent"].calls[-1])
    assert sent_len > 0 and rec["message_text_length"] == sent_len
    lines = rig["runner"]._HISTORY_PATH.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[-2])["message_text_length"] == sent_len
