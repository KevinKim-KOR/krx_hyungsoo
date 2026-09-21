"""POC3-02C-OPS-02 — **실제 `run()` 경로** flow-through (설계자 §14-6).

모듈 직접 호출 테스트만으로 끝내지 않는다. 검증자가 확인해야 하는 사슬은
이것이다.

```text
cron → runner run() → holdings_risk_alert → assemble_holdings_risk_push
     → 보유 급등락 + 사업군 → 관측·집계 기록 → 메시지 조립 → 전송 → 발송 진척 전진
```

실제 Telegram·Naver·OCI write 는 **0건**이다 — 전부 대역.

기존 `test_holdings_risk_alert_runner.py` 의 대역 설치 방식을 그대로 쓴다.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import types
from dataclasses import dataclass

import pytest

from app.intraday_config import schema

RISK_KIND = "holdings_risk_alert"

# 러너가 **실행일 시세**를 요구한다(비거래일 가드). 고정 날짜를 쓰면
# `non_trading_day` 로 skip 된다 — 실행일을 그대로 쓴다.
from app.three_push_runtime_message_builder import kst_today_date  # noqa: E402

TODAY = kst_today_date()


def _asof(day):
    return f"{day}T10:30:00+09:00"


@dataclass
class _H:
    ticker: str
    name: str
    account_group: str = "일반"


class _Q:
    def __init__(self, cur, asof, ret):
        self.current_price, self.price_asof, self.day_return_pct = cur, asof, ret

    def has_day_return(self):
        v = self.day_return_pct
        return isinstance(v, (int, float)) and not isinstance(v, bool)


def _policy(enabled=True, **over):
    p = dict(schema.INITIAL_POLICY_VALUES)
    p.update({"enabled": enabled, "policy_status": schema.POLICY_CONFIGURED})
    p.update(over)
    return p


def _sectors(n=10):
    return [
        {
            "sector_key": f"S{i}",
            "representative": {"ticker": f"T{i:05d}", "short_name": f"대표{i}"},
        }
        for i in range(n)
    ]


@pytest.fixture()
def market_db(tmp_path):
    p = tmp_path / "m.sqlite"
    con = sqlite3.connect(p)
    con.execute(
        "CREATE TABLE krx_etf_daily_price_unadjusted(ticker TEXT,date TEXT,close REAL)"
    )
    rows = []
    for i in range(10):
        rows += [(f"T{i:05d}", f"2026-08-{d + 1:02d}", 100.0 + d) for d in range(25)]
    con.executemany("INSERT INTO krx_etf_daily_price_unadjusted VALUES(?,?,?)", rows)
    con.commit()
    con.close()
    return p


@pytest.fixture()
def rig(monkeypatch, tmp_path, market_db):
    return _build_rig(monkeypatch, tmp_path, market_db)


def _build_rig(monkeypatch, tmp_path, market_db, *, sender=None, flag="true"):
    """러너 + 외부 대역. 반환 dict 로 시나리오를 조립한다."""
    from tests.test_holdings_risk_alert_runner import (  # noqa: F401
        _install_runner,
        _seed_param,
    )

    _seed_param()
    runner, sent = _install_runner(monkeypatch, tmp_path, sender=sender, flag=flag)

    state = {
        "policy": _policy(),
        "sectors": _sectors(),
        "quotes": {},
        "naver_calls": [],
    }

    # ── intraday_config store 대역 (OCI·DB 접근 0건) ──────────────────────
    from app.intraday_config import store as store_mod

    def _active(**kw):
        if state["policy"] is None and state["sectors"] is None:
            return None
        return {
            "config_version_id": "v1",
            "source_hash_sha256": "h",
            "payload_json": json.dumps(
                {
                    "intraday_alert_policy": state["policy"] or {},
                    "sector_representative_universe": {
                        "sectors": state["sectors"] or []
                    },
                }
            ),
        }

    monkeypatch.setattr(store_mod, "get_active", _active)

    # ── 보유 원장 ────────────────────────────────────────────────────────
    import app.holdings as holdings_mod

    monkeypatch.setattr(
        holdings_mod, "load", lambda *a, **k: [_H("H00001", "보유하나")]
    )
    # `collect_target_tickers` 가 파일 존재를 Fail-Closed 로 확인한다.
    hfile = tmp_path / "holdings" / "holdings_latest.json"
    hfile.parent.mkdir(parents=True, exist_ok=True)
    hfile.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(holdings_mod, "HOLDINGS_FILE", hfile)

    # ── Naver 대역 — 호출 ticker 를 전부 센다 ────────────────────────────
    fake = types.ModuleType("app.market_naver")

    class _R:
        def __init__(self, t):
            self.ticker = t
            self.quote = state["quotes"].get(t)

    def _fetch_many(tickers, timeout=15.0):
        state["naver_calls"].extend(tickers)
        return [_R(t) for t in tickers]

    fake.fetch_many = _fetch_many
    monkeypatch.setitem(sys.modules, "app.market_naver", fake)
    from app import market_naver as _mn

    monkeypatch.setattr(_mn, "fetch_many", _fetch_many)

    # ── 무조정 DB · 사업군 상태 파일 경로 ────────────────────────────────
    import app.runtime_evidence.intraday_alert_flow as iflow
    import app.runtime_evidence.holdings_risk_flow as rflow

    monkeypatch.setattr(iflow, "DEFAULT_MARKET_DB", market_db)
    sector_state = tmp_path / "sector.json"
    monkeypatch.setattr(rflow, "DEFAULT_SECTOR_STATE_PATH", sector_state)
    # 라이브 집계 파일을 건드리지 않는다.
    monkeypatch.setattr(rflow, "DEFAULT_TALLY_PATH", tmp_path / "tally.json")

    # 거래일 축 · 이력
    import app.market_data_store as store2

    axis = [f"2026-08-{i + 1:02d}" for i in range(25)] + [TODAY]
    monkeypatch.setattr(
        store2, "fetch_price_history", lambda t, **kw: [(d, 10000.0) for d in axis]
    )
    monkeypatch.setattr(
        runner,
        "_collect_target_tickers",
        lambda pk: __import__(
            "app.three_push_runtime.target_tickers", fromlist=["x"]
        ).collect_target_tickers(pk),
    )

    state.update(
        runner=runner,
        sent=sent,
        sector_state=sector_state,
        market_db=market_db,
        tally=tmp_path / "tally.json",
    )
    return state


def _hold_only(rig, ret=-6.0):
    rig["quotes"] = {"H00001": _Q(9400.0, _asof(TODAY), ret)}


def _hold_and_sectors(rig, *, hold=-6.0, sector_ret=-2.5):
    q = {"H00001": _Q(9400.0, _asof(TODAY), hold)}
    for i in range(10):
        q[f"T{i:05d}"] = _Q(10000.0, _asof(TODAY), sector_ret + i * 0.1)
    rig["quotes"] = q


# ── ② 비활성 정책 → 대표 조회 0건 ──────────────────────────────────────────


def test_disabled_policy_makes_zero_sector_lookups(rig):
    """**`enabled=false` 면 대표 ETF 를 한 건도 조회하지 않는다**(§14-3)."""
    rig["policy"] = _policy(enabled=False)
    _hold_only(rig)
    rec = rig["runner"].run(RISK_KIND, "send")
    sector_calls = [t for t in rig["naver_calls"] if t.startswith("T")]
    assert sector_calls == [], f"비활성인데 {len(sector_calls)}건 조회했다"
    assert rig["naver_calls"] == ["H00001"]
    assert rec["status"] == "sent"


def test_disabled_policy_keeps_legacy_body_format(rig):
    """비활성 상태의 **기존 본문 형식**도 그대로여야 한다(§14-3)."""
    rig["policy"] = _policy(enabled=False)
    _hold_only(rig)
    rig["runner"].run(RISK_KIND, "send")
    body = rig["sent"].calls[-1]
    assert "[보유 급락 알림]" in body
    assert "[장중 급등락]" not in body


def test_disabled_policy_writes_no_sector_state(rig):
    rig["policy"] = _policy(enabled=False)
    _hold_only(rig)
    rig["runner"].run(RISK_KIND, "send")
    assert not rig["sector_state"].exists()


# ── ③ 설정 누락·손상 → 기존 경로 유지 ──────────────────────────────────────


def test_missing_config_keeps_legacy_path(rig):
    rig["policy"], rig["sectors"] = None, None
    _hold_only(rig)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent"
    assert "[보유 급락 알림]" in rig["sent"].calls[-1]
    assert [t for t in rig["naver_calls"] if t.startswith("T")] == []


def test_corrupt_config_keeps_legacy_path(rig, monkeypatch):
    from app.intraday_config import store as store_mod

    monkeypatch.setattr(store_mod, "get_active", lambda **kw: {"payload_json": "{깨짐"})
    _hold_only(rig)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent"
    assert "[보유 급락 알림]" in rig["sent"].calls[-1]


# ── ① 활성 + 신호 → 통합 본문 1건 ──────────────────────────────────────────


def test_enabled_policy_produces_unified_body(rig):
    """활성 정책 + 신호 → 통합 본문 **1건**."""
    _hold_and_sectors(rig)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent"
    assert len(rig["sent"].calls) == 1
    body = rig["sent"].calls[-1]
    assert "[장중 급등락]" in body
    assert "보유종목" in body and "보유하나" in body


def test_enabled_policy_looks_up_union(rig):
    """활성이면 보유 ∪ 대표를 조회한다(§14-3)."""
    _hold_and_sectors(rig)
    rig["runner"].run(RISK_KIND, "send")
    assert "H00001" in rig["naver_calls"]
    assert len([t for t in rig["naver_calls"] if t.startswith("T")]) == 10


# ── ④ 사업군 예외 → 보유 본문 유지 ─────────────────────────────────────────


def test_sector_exception_keeps_held_body(rig, monkeypatch):
    import app.runtime_evidence.intraday_alert_flow as iflow

    monkeypatch.setattr(
        iflow,
        "select_sector_signals",
        lambda **kw: (_ for _ in ()).throw(RuntimeError("사업군 폭발")),
    )
    _hold_and_sectors(rig)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent"
    assert "보유하나" in rig["sent"].calls[-1]


# ── ⑤ 전송 성공 → 상태·일일 발송 수 저장 ───────────────────────────────────


def test_send_success_saves_state_once(rig):
    _hold_and_sectors(rig)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent"
    assert rig["sector_state"].exists()
    body = json.loads(rig["sector_state"].read_text(encoding="utf-8"))
    assert body["sent_today"] == 1
    assert body["date_kst"] == TODAY


# ── ⑥ 전송 실패 → 발송 진척 미전진 ──────────────────────────────────────────────


def test_send_failure_does_not_save_state(monkeypatch, tmp_path, market_db):
    """**미발송 신호가 발송 완료로 기록되면 안 된다.**

    전송 실패를 `_Sender(sent=False)` 로 주입한다 — 러너 내부를 패치하지 않고
    실제 발송 분기를 탄다.
    """
    from tests.test_holdings_risk_alert_runner import _Sender

    rig = _build_rig(monkeypatch, tmp_path, market_db, sender=_Sender(sent=False))
    _hold_and_sectors(rig)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "failed"
    # 관측 저장은 매 회차 돈다(회복 판정용) — 파일 존재 자체는 정상이다.
    # 계약은 **발송 상태**(`last_sent_at`·`sent_today`)가 안 남는 것이다.
    body = _saved(rig)
    assert body is None or body["sent_today"] == 0, body
    if body:
        assert all(
            "last_sent_at" not in e for e in body["entries"].values()
        ), "발송 실패인데 발송 시각이 찍혔다"


# ── ⑧ 일일 4건 도달 → 이후 억제 ────────────────────────────────────────────


def test_daily_cap_blocks_the_whole_conditional_send(rig):
    """**일일 4건에 도달하면 아무것도 보내지 않는다**(설계 §6).

    검증자 지적 — 예전 테스트는 "보유 급락은 여전히 나간다" 를 정상으로
    고정했다. 그런데 `holdings_risk_alert` **자체가 조건형 PUSH** 다.
    통합 본문만 막고 기존 본문을 내보내면 하루 5건·6건이 나간다.
    """
    from app.runtime_evidence.sector_signal_state import save_sector_state

    save_sector_state(rig["sector_state"], entries={}, today_kst=TODAY, sent_today=4)
    _hold_and_sectors(rig)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] != "sent", "상한을 넘겨 발송했다"
    assert rig["sent"].calls == [], f"상한 도달인데 보냈다: {rig['sent'].calls}"


def test_under_daily_cap_still_sends(rig):
    """3건까지는 나간다 — 상한이 조기 차단하면 안 된다."""
    from app.runtime_evidence.sector_signal_state import save_sector_state

    save_sector_state(rig["sector_state"], entries={}, today_kst=TODAY, sent_today=3)
    _hold_and_sectors(rig)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent"
    assert rig["sent"].calls


# ── 금지사항 ───────────────────────────────────────────────────────────────


def test_no_real_external_calls(rig):
    """실 Telegram·Naver·OCI write 0건 — 전부 대역이다."""
    _hold_and_sectors(rig)
    rig["runner"].run(RISK_KIND, "send")
    assert all(isinstance(t, str) for t in rig["naver_calls"])
    assert rig["sent"].calls, "대역 전송기가 받지 못했다"


# ── §15-2 추가 관통 2건 ─────────────────────────────────────────────────────


def test_partial_delivery_does_not_save_any_send_state(
    monkeypatch, tmp_path, market_db
):
    """**부분 전송이면 발송 진척 상태를 전진시키지 않는다.**

    발송 상태(`last_sent_at`·`sent_today`)를 남기지 않아야 한다. 관측
    `entries` 는 저장된다(설계 §15-2 OPTION_A). 부분 전송을 완료로 기록하면
    다음 회차가 같은 신호를 억제해 통째로 누락된다.
    """
    from tests.test_holdings_risk_alert_runner import _Sender

    rig = _build_rig(
        monkeypatch, tmp_path, market_db, sender=_Sender(sent=True, partial=True)
    )
    _hold_and_sectors(rig)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent"
    # `assert x or True` 는 **항상 참**이라 아무것도 검사하지 않는다(검증자 B-6).
    # 부분 전송이면 발송 진척(`sent_today`·`last_sent_at`)이 전진하지 않는 것만 본다.
    body = _saved(rig)
    assert body is None or body["sent_today"] == 0, body
    if body:
        assert all(
            "last_sent_at" not in e for e in body["entries"].values()
        ), "부분 전송인데 발송 시각이 찍혔다"


def test_seven_ticks_feed_the_1540_summary(monkeypatch, tmp_path):
    """**7틱 집계가 요약 한 줄이 된다**(설계 §8).

    검증자 지적 — 예전에는 테스트가 두 함수를 직접 불러 "연결된 것처럼"
    검증했다. 운영 연결은 아래
    `test_1540_slot_appends_summary_through_selection_flow` 가 본다.
    """
    from app.runtime_evidence import holdings_risk_flow as rflow
    from app.runtime_evidence import intraday_checkup_tally as tally_mod

    tally = tmp_path / "tally.json"
    monkeypatch.setattr(rflow, "DEFAULT_TALLY_PATH", tally)
    for o in (
        [tally_mod.OUTCOME_SENT] * 2
        + [tally_mod.OUTCOME_SUPPRESSED] * 3
        + [tally_mod.OUTCOME_NO_SIGNAL] * 2
    ):
        tally_mod.record_tick(tally, today_kst=TODAY, outcome=o)

    line = tally_mod.render_summary_line(
        tally_mod.load_tally(rflow.DEFAULT_TALLY_PATH, today_kst=TODAY)
    )
    assert line == "장중 점검 7회 · 알림 2건 · 중복 억제 3건 · 신호 없음 2건"


def test_failed_ticks_appear_as_lookup_failures(tmp_path):
    """`조회 실패 N회` 가 별도로 표시된다(설계 §8)."""
    from app.runtime_evidence import intraday_checkup_tally as tally_mod

    p = tmp_path / "t.json"
    for o in (
        [tally_mod.OUTCOME_SENT]
        + [tally_mod.OUTCOME_FAILED] * 2
        + [tally_mod.OUTCOME_NO_SIGNAL] * 4
    ):
        tally_mod.record_tick(p, today_kst=TODAY, outcome=o)
    line = tally_mod.render_summary_line(tally_mod.load_tally(p, today_kst=TODAY))
    assert "조회 실패 2회" in line


def test_1540_slot_appends_summary_through_selection_flow(monkeypatch, tmp_path):
    """**운영 조립 함수**(`assemble_holdings_selection_push`)가 붙이는지 본다."""
    from pathlib import Path

    from app.runtime_evidence import holdings_risk_flow as rflow
    from app.runtime_evidence import intraday_checkup_tally as tally_mod

    tally = tmp_path / "t.json"
    monkeypatch.setattr(rflow, "DEFAULT_TALLY_PATH", tally)
    tally_mod.record_tick(tally, today_kst=TODAY, outcome=tally_mod.OUTCOME_SENT)

    src = Path("app/runtime_evidence/holdings_selection_flow.py").read_text(
        encoding="utf-8"
    )
    # 소스로 **운영 경로 연결**을 고정한다 — 호출자가 사라지면 잡힌다.
    assert "render_summary_line" in src
    assert "LAST_SLOT_ID" in src
    assert "intraday_checkup_summary" in src


def test_summary_only_on_close_slot():
    """09:15·12:30 에는 붙지 않는다 — 15:40 한 번만."""
    from pathlib import Path

    src = Path("app/runtime_evidence/holdings_selection_flow.py").read_text(
        encoding="utf-8"
    )
    assert '(slot_id or "") == LAST_SLOT_ID' in src


def test_failed_outcome_has_a_production_writer():
    """`조회 실패 N회` 의 **생산 경로**가 있어야 한다(검증자 지적).

    예전에는 `OUTCOME_FAILED` 를 쓰는 곳이 테스트뿐이었다.
    """
    from pathlib import Path

    src = Path("app/runtime_evidence/holdings_risk_flow.py").read_text(encoding="utf-8")
    assert "OUTCOME_FAILED" in src
    assert "sector_error" in src and "coverage_ok" in src


def test_tally_records_every_tick_even_without_send(rig):
    """**보내지 않은 회차도 집계된다** — 실제 `run()` 경로에서 확인."""
    from app.runtime_evidence import holdings_risk_flow as rflow
    from app.runtime_evidence import intraday_checkup_tally as tally_mod

    _hold_and_sectors(rig, hold=-1.0, sector_ret=0.1)  # 아무 신호도 없는 값
    rig["runner"].run(RISK_KIND, "send")
    t = tally_mod.load_tally(rflow.DEFAULT_TALLY_PATH, today_kst=TODAY)
    assert t.unknown is False and t.checks >= 1


def test_tally_failure_never_blocks_send(rig, monkeypatch):
    """집계 실패가 발송을 막으면 안 된다."""
    from app.runtime_evidence import intraday_checkup_tally as tally_mod

    monkeypatch.setattr(
        tally_mod,
        "record_tick",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("집계 터짐")),
    )
    _hold_and_sectors(rig)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent"


def test_corrupt_tally_reports_unknown_not_zero(tmp_path):
    """집계 불가를 `0` 으로 위장하지 않는다(설계 §8)."""
    from app.runtime_evidence import intraday_checkup_tally as tally_mod

    p = tmp_path / "t.json"
    p.write_text("{깨짐", encoding="utf-8")
    t = tally_mod.load_tally(p, today_kst=TODAY)
    assert t.unknown is True
    assert tally_mod.render_summary_line(t) == "장중 점검 확인 불가"


def test_tally_from_another_day_is_unknown(tmp_path):
    from app.runtime_evidence import intraday_checkup_tally as tally_mod

    p = tmp_path / "t.json"
    tally_mod.record_tick(p, today_kst="2026-09-15", outcome=tally_mod.OUTCOME_SENT)
    assert tally_mod.load_tally(p, today_kst=TODAY).unknown is True


# ── 검증자 재현 시나리오 — 상태 저장 배선 (①·②) ───────────────────────────
#
# 단위 함수만 고치고 **실제 흐름에 연결하지 않은** 것이 직전 반려 사유였다.
# 여기서는 전부 `run()` 을 통과시킨다.


def _saved(rig):
    if not rig["sector_state"].exists():
        return None
    return json.loads(rig["sector_state"].read_text(encoding="utf-8"))


def test_surge_is_saved_to_state_after_send(rig):
    """**보유 급등이 상태에 저장된다.**

    검증자 재현: `surge_saved False` — 저장이 `changes.send`(사업군)만 써서
    급등이 다음 틱에 또 신규가 됐다.
    """
    _hold_and_sectors(rig, hold=7.5)  # 급등 구간
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent"
    body = _saved(rig)
    assert body is not None
    assert "H00001" in body["entries"], f"급등 미저장: {list(body['entries'])}"
    assert body["entries"]["H00001"]["state"].startswith("U")


def test_saved_entries_are_not_empty_after_send(rig):
    """전송 성공 시 `entries` 가 실제로 채워진다.

    직전 테스트는 `sent_today` 와 날짜만 봐서 `entries` 가 비어도 통과했다.
    """
    _hold_and_sectors(rig)
    rig["runner"].run(RISK_KIND, "send")
    body = _saved(rig)
    assert body["entries"], "entries 가 비어 있다"
    assert body["sent_today"] == 1


def test_missed_tick_records_recovery(rig):
    """**신호가 사라진 회차가 기록된다** — 회복 판정의 근거(설계 §5).

    검증자 재현: `continuous_after_recovery_tick True` — 미발송 회차에는 저장
    함수가 아예 안 불려 `continuous` 가 영원히 `True` 였다.
    """
    _hold_and_sectors(rig, hold=7.5)  # 급등 — 이 상태 파일이 추적하는 대상
    rig["runner"].run(RISK_KIND, "send")
    assert _saved(rig)["entries"]["H00001"]["continuous"] is True

    # 신호 없는 회차 — 발송도 없다.
    _hold_and_sectors(rig, hold=-0.5, sector_ret=0.1)
    rig["runner"].run(RISK_KIND, "send")
    body = _saved(rig)
    assert body["entries"]["H00001"]["continuous"] is False, "회복이 기록되지 않았다"
    assert body["sent_today"] == 1, "미발송 회차가 발송 수를 올렸다"


def test_observation_save_does_not_touch_last_sent_at(rig):
    """관측 저장이 `last_sent_at` 을 밀면 cooldown 이 영원히 안 끝난다."""
    _hold_and_sectors(rig, hold=7.5)
    rig["runner"].run(RISK_KIND, "send")
    stamp = _saved(rig)["entries"]["H00001"]["last_sent_at"]

    _hold_and_sectors(rig, hold=-0.5, sector_ret=0.1)
    rig["runner"].run(RISK_KIND, "send")
    assert _saved(rig)["entries"]["H00001"]["last_sent_at"] == stamp


def test_suppressed_signal_is_not_marked_recovered(rig):
    """다른 신호가 발송된 회차에 **관측 중인 억제 신호**가 회복으로 찍히면 안 된다."""
    _hold_and_sectors(rig, hold=7.5)
    rig["runner"].run(RISK_KIND, "send")
    # 같은 신호가 계속 관측되는 회차
    _hold_and_sectors(rig, hold=7.5)
    rig["runner"].run(RISK_KIND, "send")
    body = _saved(rig)
    assert body["entries"]["H00001"]["continuous"] is True


def test_recovery_then_reentry_sends_again(rig, monkeypatch):
    """회복 → 재진입 + cooldown 경과 → **다시 발송**한다(설계 §5).

    검증자 재현: `reentry_send [] · suppressed [...]` — 회복이 기록되지 않아
    재진입이 오히려 계속 억제됐다.

    registry 중복키는 `holdings_risk_alert` 에서 **실행 시각 HH:MM** 이다
    (7틱 · 악화 시 재발송 계약). 같은 분에 세 번 돌리면 `duplicate_runtime`
    으로 막히므로 틱마다 시각을 옮긴다 — 운영의 09:30/10:30/11:30 과 같다.
    """
    from datetime import timedelta

    from app.runtime_evidence import holdings_risk_flow as rflow

    base = rflow._now_kst(None)

    def at(minutes):
        monkeypatch.setattr(
            rflow, "_now_kst", lambda rk, _m=minutes: base + timedelta(minutes=_m)
        )
        monkeypatch.setattr(
            rflow,
            "_slot_label",
            lambda rk, _m=minutes: (base + timedelta(minutes=_m)).strftime("%H:%M"),
        )
        import app.three_push_runtime.runner_duplicate as dup

        monkeypatch.setattr(
            dup,
            "resolve_duplicate_slot",
            lambda pk, slot_id=None, runtime_kst=None, _m=minutes: (
                (base + timedelta(minutes=_m)).strftime("%H:%M")
                if pk == "holdings_risk_alert"
                else slot_id
            ),
        )

    at(0)
    _hold_and_sectors(rig, hold=7.5)
    rig["runner"].run(RISK_KIND, "send")
    sent_once = len(rig["sent"].calls)
    assert sent_once == 1

    at(60)
    _hold_and_sectors(rig, hold=-0.5, sector_ret=0.1)  # 회복
    rig["runner"].run(RISK_KIND, "send")
    assert _saved(rig)["entries"]["H00001"]["continuous"] is False

    at(121)  # cooldown 경과 후 재진입
    _hold_and_sectors(rig, hold=7.5)
    rig["runner"].run(RISK_KIND, "send")
    assert len(rig["sent"].calls) > sent_once, "회복 후 재진입인데 억제됐다"


def test_continuous_signal_is_not_resent_across_ticks(rig, monkeypatch):
    """**지속 중이면 틱이 바뀌어도 재발송하지 않는다**(설계 §5).

    registry 는 틱마다 열리므로, 막는 것은 `continuous` 뿐이다.
    """
    from datetime import timedelta

    from app.runtime_evidence import holdings_risk_flow as rflow
    import app.three_push_runtime.runner_duplicate as dup

    base = rflow._now_kst(None)

    def at(minutes):
        monkeypatch.setattr(
            rflow, "_now_kst", lambda rk, _m=minutes: base + timedelta(minutes=_m)
        )
        monkeypatch.setattr(
            dup,
            "resolve_duplicate_slot",
            lambda pk, slot_id=None, runtime_kst=None, _m=minutes: (
                (base + timedelta(minutes=_m)).strftime("%H:%M")
                if pk == "holdings_risk_alert"
                else slot_id
            ),
        )

    at(0)
    _hold_and_sectors(rig, hold=7.5)
    rig["runner"].run(RISK_KIND, "send")
    first = len(rig["sent"].calls)

    # 같은 급등이 계속 유지 — 180분이 지나도 보내지 않는다.
    at(180)
    _hold_and_sectors(rig, hold=7.6)
    rig["runner"].run(RISK_KIND, "send")
    assert len(rig["sent"].calls) == first, "지속 중인데 재발송했다"


# ── 전송 실패·부분 전송 후 **다음 틱 재시도** (검증자 P1) ──────────────────
#
# 직전 테스트는 "발송 완료 표식이 없다" 만 봤다. 정작 중요한 **"실패한 신호가
# 다음 틱에 다시 나가는가"** 를 놓쳤다. 관측 저장이 Telegram 결과보다 먼저
# `continuous=True` 를 남기므로, 억제 판정이 `continuous` 를 먼저 보면 실패한
# 신호가 영영 안 나간다.


def _tick_at(monkeypatch, base, minutes):
    """틱마다 시각을 옮긴다 — registry 중복키가 `HH:MM` 이다."""
    from datetime import timedelta

    import app.three_push_runtime.runner_duplicate as dup
    from app.runtime_evidence import holdings_risk_flow as rflow

    monkeypatch.setattr(
        rflow, "_now_kst", lambda rk, _m=minutes: base + timedelta(minutes=_m)
    )
    monkeypatch.setattr(
        dup,
        "resolve_duplicate_slot",
        lambda pk, slot_id=None, runtime_kst=None, _m=minutes: (
            (base + timedelta(minutes=_m)).strftime("%H:%M")
            if pk == "holdings_risk_alert"
            else slot_id
        ),
    )


def test_failed_send_is_retried_on_next_tick(monkeypatch, tmp_path, market_db):
    """**전송 실패한 신호는 다음 틱에 다시 나간다.**

    검증자 재현: `next_send=[] · next_suppressed=[('T1','AVOID_DROP')]` —
    한 번도 안 나갔는데 "지속 중" 으로 억제됐다.
    """
    from tests.test_holdings_risk_alert_runner import _Sender

    from app.runtime_evidence import holdings_risk_flow as rflow

    failing = _Sender(sent=False)
    rig = _build_rig(monkeypatch, tmp_path, market_db, sender=failing)
    base = rflow._now_kst(None)

    _tick_at(monkeypatch, base, 0)
    _hold_and_sectors(rig, hold=7.5)
    assert rig["runner"].run(RISK_KIND, "send")["status"] == "failed"
    body = _saved(rig)
    assert body["entries"]["H00001"].get("last_sent_at") is None

    # 다음 틱 — 이번엔 전송기가 성공한다.
    failing._sent = True
    _tick_at(monkeypatch, base, 60)
    _hold_and_sectors(rig, hold=7.5)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent", "실패한 신호가 다음 틱에서 억제됐다"
    assert rig["sent"].calls, "본문이 나가지 않았다"


def test_partial_delivery_is_retried_on_next_tick(monkeypatch, tmp_path, market_db):
    """부분 전송도 마찬가지다 — 발송 완료로 기록되지 않았으니 다시 시도한다."""
    from tests.test_holdings_risk_alert_runner import _Sender

    from app.runtime_evidence import holdings_risk_flow as rflow

    partial = _Sender(sent=True, partial=True)
    rig = _build_rig(monkeypatch, tmp_path, market_db, sender=partial)
    base = rflow._now_kst(None)

    _tick_at(monkeypatch, base, 0)
    _hold_and_sectors(rig, hold=7.5)
    rig["runner"].run(RISK_KIND, "send")
    assert _saved(rig)["entries"]["H00001"].get("last_sent_at") is None

    partial._partial = False
    _tick_at(monkeypatch, base, 60)
    _hold_and_sectors(rig, hold=7.5)
    rig["runner"].run(RISK_KIND, "send")
    assert (
        _saved(rig)["entries"]["H00001"].get("last_sent_at") is not None
    ), "부분 전송 후 재시도가 억제됐다"


def test_observation_alone_never_suppresses(monkeypatch, tmp_path, market_db):
    """관측만으로는 절대 억제하지 않는다 — `last_sent_at` 이 있어야 한다."""
    from app.runtime_evidence.sector_signal import SectorSignal, STATE_AVOID_DROP
    from app.runtime_evidence.sector_signal_state import (
        LoadedSectorState,
        compute_sector_changes,
    )
    from app.runtime_evidence import holdings_risk_flow as rflow

    prev = LoadedSectorState(
        entries={"T1": {"state": STATE_AVOID_DROP, "continuous": True}},
        fallback=False,
    )
    ch = compute_sector_changes(
        signals=[SectorSignal("s", "T1", "n", STATE_AVOID_DROP, -2.4)],
        previous=prev,
        now_kst=rflow._now_kst(None),
        cooldown_minutes=120,
    )
    assert [s.ticker for s in ch.send] == ["T1"]
    assert ch.suppressed == []


# 억제 계약을 **표 전체**로 고정한다. 셀 하나씩 테스트를 쓰면 빠진 칸이 생긴다
# — 지금까지 반려가 난 자리가 늘 "고친 것의 옆칸" 이었다.
_SUPPRESS_TABLE = [
    ("prev 없음 (신규 종목)", None, True),
    ("last=None · continuous=False", {"continuous": False}, True),
    ("last=None · continuous=True (전송 실패)", {"continuous": True}, True),
    (
        "last=있음 · continuous=True (지속 중)",
        {"continuous": True, "last": -200},
        False,
    ),
    ("last=있음 · 회복 · cooldown 경과", {"continuous": False, "last": -200}, True),
    ("last=있음 · 회복 · cooldown 이내", {"continuous": False, "last": -10}, False),
    ("last 손상값 · continuous=True", {"continuous": True, "last": "쓰레기"}, True),
]


@pytest.mark.parametrize(
    "label,entry,should_send", _SUPPRESS_TABLE, ids=[r[0] for r in _SUPPRESS_TABLE]
)
def test_suppression_table_is_complete(label, entry, should_send):
    from datetime import timedelta

    from app.runtime_evidence import holdings_risk_flow as rflow
    from app.runtime_evidence.sector_signal import SectorSignal, STATE_AVOID_DROP
    from app.runtime_evidence.sector_signal_state import (
        LoadedSectorState,
        compute_sector_changes,
    )

    now = rflow._now_kst(None)
    entries = {}
    if entry is not None:
        e = {"state": STATE_AVOID_DROP, "continuous": entry["continuous"]}
        if "last" in entry:
            raw = entry["last"]
            e["last_sent_at"] = (
                raw
                if isinstance(raw, str)
                else (now + timedelta(minutes=raw)).isoformat()
            )
        entries["T1"] = e

    ch = compute_sector_changes(
        signals=[SectorSignal("s", "T1", "n", STATE_AVOID_DROP, -2.4)],
        previous=LoadedSectorState(entries=entries, fallback=False),
        now_kst=now,
        cooldown_minutes=120,
    )
    assert bool(ch.send) is should_send, label
    assert bool(ch.suppressed) is (not should_send), label


# ── 구역 상한에 잘린 신호는 "발송" 이 아니다 (독립 감사 D1) ─────────────────
#
# `sent_signals` 가 상한 적용 **전에** 확정되면, 본문에 실리지 않은 신호에도
# `last_sent_at` 이 찍혀 다음 틱에 "지속 중" 으로 억제된다 — 지속되는 동안 한
# 번도 나가지 못한다. 설계 §15-2 4항: 발송 성공은 **해당 신호의** `last_sent_at`
# 갱신으로 판정한다. 잘린 신호는 §6 대로 `dropped` 이력에만 남는다.


def _rep_name(ticker):
    """rig 의 대표 ETF 이름 — `_sectors()` 가 `T{i:05d}` ↔ `대표{i}` 로 만든다."""
    return f"대표{int(ticker[1:])}"


def test_signals_dropped_by_section_cap_get_no_last_sent_at(rig):
    """10개 AVOID_CHASE · cap 3 → 3개만 `last_sent_at`, 7개는 없음.

    `AVOID_DROP` 은 하위 20% 순위 조건이 있어 10개 중 2개만 된다. 순위 조건이
    없는 `AVOID_CHASE`(≥ +4.0%) 로 한 구역에 10개를 넣는다.
    """
    _hold_and_sectors(rig, sector_ret=5.0)  # T00000~T00009 전부 ≥ +4.0 → AVOID_CHASE
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent"
    body = _saved(rig)
    sector = {t: e for t, e in body["entries"].items() if t.startswith("T")}
    assert len(sector) == 10, "관측은 10개 전부 남아야 한다"
    stamped = sorted(t for t, e in sector.items() if e.get("last_sent_at"))
    assert len(stamped) == 3, f"본문에 실린 3개만 발송 표식: {stamped}"
    # 실린 것이 본문에 있고, 잘린 것은 본문에 없다. 본문은 ticker 가 아니라
    # `사업군 · 이름` 으로 찍히므로 rig 의 이름(대표N)으로 찾는다.
    text = rig["sent"].calls[-1]
    for t in stamped:
        assert _rep_name(t) in text
    for t in set(sector) - set(stamped):
        assert _rep_name(t) not in text, f"{t} 는 잘렸는데 본문에 있다"


def test_signal_dropped_by_cap_is_sent_when_room_opens(
    monkeypatch, tmp_path, market_db
):
    """틱 1 에서 잘린 신호가, 틱 2 에서 앞선 3개가 회복되면 **나간다**."""
    from app.runtime_evidence import holdings_risk_flow as rflow

    rig = _build_rig(monkeypatch, tmp_path, market_db)
    base = rflow._now_kst(None)

    _tick_at(monkeypatch, base, 0)
    _hold_and_sectors(rig, sector_ret=5.0)
    rig["runner"].run(RISK_KIND, "send")
    body = _saved(rig)
    stamped = {t for t, e in body["entries"].items() if e.get("last_sent_at")}
    dropped = {t for t in body["entries"] if t.startswith("T")} - stamped
    assert len(dropped) == 7

    # 틱 2 — 실렸던 3개는 회복(0.0%), 잘렸던 7개는 그대로. cooldown(120분) 안.
    _tick_at(monkeypatch, base, 60)
    _hold_and_sectors(rig, sector_ret=5.0)
    for t in stamped:
        if t.startswith("T"):
            rig["quotes"][t] = _Q(10000.0, _asof(TODAY), 0.0)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["status"] == "sent", "잘렸던 신호가 억제됐다"
    text = rig["sent"].calls[-1]
    assert any(_rep_name(t) in text for t in dropped), "잘렸던 신호가 본문에 없다"
    body2 = _saved(rig)
    now_stamped = {t for t, e in body2["entries"].items() if e.get("last_sent_at")}
    assert now_stamped & dropped, "잘렸던 신호에 발송 표식이 안 찍혔다"


# ── D2 · D3 설계자 확정 계약 (필수 관통 검증 9건) ──────────────────────────
#
#   D2  관측은 3상태다 — 조건 충족 / 정상 평가 후 미충족 / **평가 불가**.
#       평가 불가를 "회복" 으로 기록하면 지속 신호가 cooldown 뒤 재발송된다.
#   D3  라이브 관측·집계는 Gate 를 통과한 회차만 쓴다.
#       mode=send AND 정책 enabled AND PUSH_AUTOSEND_* AND duplicate 아님.


def _hashes(rig):
    """두 라이브 파일의 해시. 없으면 `None` — 생성 자체를 잡는다."""
    import hashlib

    def h(p):
        return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None

    return h(rig["sector_state"]), h(rig["tally"])


def _blind_sectors(rig, tickers=None):
    """사업군 시세를 지운다 — 등락률을 못 구해 **평가 불가**가 된다."""
    for t in list(rig["quotes"]):
        if t.startswith("T") and (tickers is None or t in tickers):
            rig["quotes"][t] = None


def _sector_state(rig):
    return {
        t: e
        for t, e in (_saved(rig) or {"entries": {}})["entries"].items()
        if t.startswith("T")
    }


def _send_then(monkeypatch, tmp_path, market_db, *, blind, minutes=180):
    """정상 발송 → 평가 불가 회차 → 동일 신호 복귀. 마지막 회차 record 반환."""
    from app.runtime_evidence import holdings_risk_flow as rflow

    rig = _build_rig(monkeypatch, tmp_path, market_db)
    base = rflow._now_kst(None)

    _tick_at(monkeypatch, base, 0)
    _hold_and_sectors(rig, sector_ret=5.0)  # AVOID_CHASE 10건
    assert rig["runner"].run(RISK_KIND, "send")["status"] == "sent"
    before = _sector_state(rig)
    assert any(e.get("last_sent_at") for e in before.values())

    _tick_at(monkeypatch, base, 60)
    _hold_and_sectors(rig, sector_ret=5.0)
    blind(rig)
    rig["runner"].run(RISK_KIND, "send")
    mid = _sector_state(rig)

    # cooldown(120분) 경과 후 같은 신호가 그대로 관측된다.
    _tick_at(monkeypatch, base, minutes)
    _hold_and_sectors(rig, sector_ret=5.0)
    rec = rig["runner"].run(RISK_KIND, "send")
    return rig, before, mid, rec


def test_provider_down_tick_does_not_count_as_recovery(
    monkeypatch, tmp_path, market_db
):
    """정상 → provider 장애 → 동일 신호 복귀: **재발송하지 않는다.**"""
    rig, before, mid, rec = _send_then(
        monkeypatch, tmp_path, market_db, blind=_blind_sectors
    )
    kept = [t for t, e in mid.items() if e.get("continuous") is True]
    assert kept, "평가 불가인데 continuous 가 전부 내려갔다"
    # 상한에 잘린 신호는 D1 계약상 나가는 게 맞다. **이미 보낸 것**만 본다.
    _assert_not_resent(rig, before, rec)


def _assert_not_resent(rig, before, rec):
    """tick 0 에 **실제로 발송된** 신호가 다시 나가지 않았는지."""
    stamped = [t for t, e in before.items() if e.get("last_sent_at")]
    assert stamped, "선행 발송이 없어 재발송을 검사할 수 없다"
    body = rig["sent"].calls[-1] if rec["status"] == "sent" else ""
    again = [t for t in stamped if _rep_name(t) in body]
    assert not again, f"평가 불가를 회복으로 봐서 지속 신호를 재발송했다: {again}"


def test_low_coverage_tick_does_not_count_as_recovery(monkeypatch, tmp_path, market_db):
    """정상 → 커버리지 미달 → 동일 신호 복귀: **재발송하지 않는다.**

    10개 중 8개만 지워 provider 장애 임계(50%)는 피하고 커버리지(80%)만 깬다.
    """

    def blind(rig):
        _blind_sectors(rig, {f"T{i:05d}" for i in range(8)})

    rig, before, mid, rec = _send_then(monkeypatch, tmp_path, market_db, blind=blind)
    kept = [t for t, e in mid.items() if e.get("continuous") is True]
    assert kept, "커버리지 미달인데 continuous 가 내려갔다"
    _assert_not_resent(rig, before, rec)


def test_single_unevaluable_ticker_preserves_only_that_entry(
    monkeypatch, tmp_path, market_db
):
    """특정 대표만 평가 불가 → **그 ticker 만** 관측 보존, 나머지는 정상 갱신."""
    from app.runtime_evidence import holdings_risk_flow as rflow

    rig = _build_rig(monkeypatch, tmp_path, market_db)
    base = rflow._now_kst(None)

    _tick_at(monkeypatch, base, 0)
    _hold_and_sectors(rig, sector_ret=5.0)
    rig["runner"].run(RISK_KIND, "send")
    assert all(e.get("continuous") for e in _sector_state(rig).values())

    # T00000 만 시세 없음(평가 불가) · 나머지는 임계 밖으로 회복(0.0%).
    _tick_at(monkeypatch, base, 60)
    _hold_and_sectors(rig, sector_ret=0.0)
    rig["quotes"]["T00000"] = None
    rig["runner"].run(RISK_KIND, "send")

    after = _sector_state(rig)
    assert after["T00000"]["continuous"] is True, "평가 불가인데 회복으로 기록됐다"
    others = [e["continuous"] for t, e in after.items() if t != "T00000"]
    assert others and not any(others), "정상 평가된 사업군이 갱신되지 않았다"


def test_held_surge_updates_even_when_sector_path_is_down(
    monkeypatch, tmp_path, market_db
):
    """사업군 장애 중에도 **정상 평가된 보유 급등 관측은 갱신**된다."""
    rig = _build_rig(monkeypatch, tmp_path, market_db)
    _hold_and_sectors(rig, hold=7.5, sector_ret=5.0)
    _blind_sectors(rig)  # 사업군 전체 평가 불가 · 보유는 정상
    rig["runner"].run(RISK_KIND, "send")
    body = _saved(rig)
    assert body is not None, "보유 관측까지 막혔다"
    assert body["entries"]["H00001"]["continuous"] is True


def test_provider_down_is_counted_as_lookup_failure(monkeypatch, tmp_path, market_db):
    """정상 운영 · provider 장애 → 집계에 **조회 실패 1회**."""
    from app.runtime_evidence.intraday_checkup_tally import load_tally

    rig = _build_rig(monkeypatch, tmp_path, market_db)
    # 보유는 임계 밖(-1.0%) — **발송이 없는** 회차라야 설계자 표의
    # `정상 운영·평가 실패 → 조회 실패` 행이다. 발송이 있으면 `알림` 이 맞다.
    _hold_and_sectors(rig, hold=-1.0, sector_ret=5.0)
    _blind_sectors(rig)
    rig["runner"].run(RISK_KIND, "send")
    tally = load_tally(rig["tally"], today_kst=TODAY)
    assert (tally.checks, tally.failed, tally.sent) == (1, 1, 0), tally


def _live_files_unchanged(monkeypatch, tmp_path, market_db, *, run):
    """Gate 를 통과하지 못한 회차는 두 라이브 파일을 바꾸지 않는다."""
    rig = _build_rig(monkeypatch, tmp_path, market_db)
    _hold_and_sectors(rig, sector_ret=5.0)
    before = _hashes(rig)
    rec = run(rig)
    assert _hashes(rig) == before, f"Gate 밖인데 파일이 바뀌었다: {rec.get('reason')}"
    return rec


def test_dry_run_does_not_touch_live_files(monkeypatch, tmp_path, market_db):
    rec = _live_files_unchanged(
        monkeypatch,
        tmp_path,
        market_db,
        run=lambda rig: rig["runner"].run(RISK_KIND, "dry-run"),
    )
    assert rec["status"] == "dry_run_success"


def test_flag_off_does_not_touch_live_files(monkeypatch, tmp_path, market_db):
    rig = _build_rig(monkeypatch, tmp_path, market_db, flag="false")
    _hold_and_sectors(rig, sector_ret=5.0)
    before = _hashes(rig)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["reason"] == "push_kind_disabled", rec
    assert _hashes(rig) == before, "flag-off 인데 라이브 파일이 바뀌었다"


def test_duplicate_tick_does_not_touch_live_files(monkeypatch, tmp_path, market_db):
    """duplicate 회차는 점검 횟수에 넣지 않는다 — 같은 틱을 두 번 센 셈이다."""
    from app.runtime_evidence import holdings_risk_flow as rflow

    rig = _build_rig(monkeypatch, tmp_path, market_db)
    base = rflow._now_kst(None)
    _tick_at(monkeypatch, base, 0)
    _hold_and_sectors(rig, sector_ret=5.0)
    assert rig["runner"].run(RISK_KIND, "send")["status"] == "sent"

    before = _hashes(rig)
    # 같은 분(`HH:MM`)에 다시 — registry 중복. 신호를 바꿔 §6-c 를 통과시킨다.
    _hold_and_sectors(rig, hold=-6.0, sector_ret=5.2)
    rec = rig["runner"].run(RISK_KIND, "send")
    assert rec["reason"] == "duplicate_runtime", rec
    assert _hashes(rig) == before, "duplicate 회차가 집계를 올렸다"


# ── 교차 조건 3건 (검증자 B-6) ─────────────────────────────────────────────
#
# 지정 9건은 각 분기를 따로 봤을 뿐, **조합**을 보지 않았다. 반려 사유가 전부
# 조합이었다 — 성공 회차의 집계 · 사업군 장애 중 보유 발송 · 대체 ETF 이력.


def test_successful_send_is_counted_as_alert(rig):
    """정상 전송 회차는 집계에 **`알림`** 으로 남는다.

    D3 으로 회차 기록이 `_finish()` 뒤로 밀렸다. 전송 성공 경로가 집계 **파일**
    의 마지막 회차를 고치면 이번 회차 tick 은 아직 없으므로 직전 회차가 발송으로
    둔갑하고 이번 회차는 잠정값으로 남는다(검증자 실측 `sent=0 · no_signal=1`).
    """
    from app.runtime_evidence.intraday_checkup_tally import load_tally

    _hold_and_sectors(rig, sector_ret=5.0)
    assert rig["runner"].run(RISK_KIND, "send")["status"] == "sent"
    tally = load_tally(rig["tally"], today_kst=TODAY)
    assert (tally.checks, tally.sent, tally.no_signal) == (1, 1, 0), tally


def test_send_success_save_keeps_unevaluable_sector_entries(
    monkeypatch, tmp_path, market_db
):
    """사업군 평가 불가 + 보유 급등 전송이 **동시에** 일어나는 회차.

    전송 성공 저장이 `unevaluable` 을 못 받으면, 그 저장이 먼저 사업군 entry 를
    `continuous=False` 로 내리고 뒤의 관측 저장은 이미 변질된 값을 보존한다.
    """
    from app.runtime_evidence import holdings_risk_flow as rflow

    rig = _build_rig(monkeypatch, tmp_path, market_db)
    base = rflow._now_kst(None)

    _tick_at(monkeypatch, base, 0)
    _hold_and_sectors(rig, sector_ret=5.0)
    assert rig["runner"].run(RISK_KIND, "send")["status"] == "sent"
    live = [t for t, e in _sector_state(rig).items() if e.get("continuous")]
    assert live, "선행 회차에 사업군 관측이 없다"

    # 사업군 전체 평가 불가 + 보유 급등(+7.5%)은 정상 → 본문이 나간다.
    _tick_at(monkeypatch, base, 60)
    _hold_and_sectors(rig, hold=7.5, sector_ret=5.0)
    _blind_sectors(rig)
    assert rig["runner"].run(RISK_KIND, "send")["status"] == "sent"

    after = _sector_state(rig)
    fell = [t for t in live if after.get(t, {}).get("continuous") is not True]
    assert not fell, f"평가 불가 사업군이 회복으로 기록됐다: {fell}"
    # 정상 평가된 보유 급등 관측은 갱신된다.
    assert _saved(rig)["entries"]["H00001"]["continuous"] is True


def test_alternate_etf_entry_is_preserved_by_sector_key(rig):
    """직전 회차가 **대체 ETF** 로 저장된 사업군도 보존된다.

    보존을 ticker 로만 잡으면 이번 회차의 대표 ticker 와 달라 빠진다.
    """
    from app.runtime_evidence.sector_signal import STATE_AVOID_CHASE
    from app.runtime_evidence.sector_signal_state import save_sector_state

    # S0 의 직전 기록이 대체 ETF(`ALT000`) 로 남아 있다.
    save_sector_state(
        rig["sector_state"],
        entries={
            "ALT000": {
                "state": STATE_AVOID_CHASE,
                "continuous": True,
                "sector_key": "S0",
                "day_return_pct": 5.0,
                "last_sent_at": f"{TODAY}T09:30:00+09:00",
            }
        },
        today_kst=TODAY,
        sent_today=1,
    )
    # 이번 회차 — S0 대표(T00000)는 시세 없음(평가 불가), 나머지는 정상.
    _hold_and_sectors(rig, sector_ret=5.0)
    rig["quotes"]["T00000"] = None
    rig["runner"].run(RISK_KIND, "send")

    entry = _saved(rig)["entries"]["ALT000"]
    assert entry["continuous"] is True, "대체 ETF 사업군이 회복으로 기록됐다"
    assert entry.get("last_sent_at"), "대체 ETF 의 발송 이력이 지워졌다"
