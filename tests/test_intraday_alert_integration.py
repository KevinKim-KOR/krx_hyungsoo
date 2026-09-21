"""POC3-02C-OPS-02 — 실패 격리·상한·정책 게이트 통합 (설계자 §6·§9·§10).

**사업군 경로 실패가 보유 경로를 막지 않는다**를 실제 경로로 증명한다.
실 Naver·Telegram·OCI 호출 0건.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import pytest

from app.intraday_config import schema
from app.runtime_evidence import intraday_alert_flow as flow
from app.runtime_evidence.holdings_risk import STATE_D5_7, RiskTicker
from app.runtime_evidence.sector_signal_state import KST, save_sector_state

TODAY = "2026-09-16"
ASOF = "2026-09-16T10:30:00+09:00"
NOW = datetime(2026, 9, 16, 10, 30, tzinfo=KST)


class Q:
    def __init__(self, ret, *, price=10000.0, asof=ASOF):
        self.current_price, self.day_return_pct, self.price_asof = (
            ret and price or price,
            ret,
            asof,
        )
        self.current_price = price

    def has_day_return(self):
        v = self.day_return_pct
        return isinstance(v, (int, float)) and not isinstance(v, bool)


def _held_drop():
    return [RiskTicker("H00001", "보유하락", 1, STATE_D5_7, day_drop_pct=-5.4)]


def _rows():
    return [{"ticker": "H00001", "name": "보유하락"}]


def _enabled_policy(**over):
    p = dict(schema.INITIAL_POLICY_VALUES)
    p.update({"enabled": True, "policy_status": schema.POLICY_CONFIGURED})
    p.update(over)
    return p


@pytest.fixture()
def db(tmp_path):
    """무조정 이력 대역 DB. 라이브 DB 를 쓰지 않는다."""
    p = tmp_path / "m.sqlite"
    con = sqlite3.connect(p)
    con.execute(
        "CREATE TABLE krx_etf_daily_price_unadjusted(ticker TEXT,date TEXT,close REAL)"
    )
    rows = [("S00001", f"2026-08-{i + 1:02d}", 100.0 + i) for i in range(25)]
    con.executemany("INSERT INTO krx_etf_daily_price_unadjusted VALUES(?,?,?)", rows)
    con.commit()
    con.close()
    return p


def _patch(monkeypatch, *, policy=None, sectors=None, raise_on_sectors=False):
    monkeypatch.setattr(flow, "active_policy", lambda logger=None: policy)

    def _sec(logger=None):
        if raise_on_sectors:
            raise RuntimeError("의도적 실패")
        return sectors or []

    monkeypatch.setattr(flow, "_load_active_sectors", _sec)


# ── §10 정책 게이트 ─────────────────────────────────────────────────────────


def test_disabled_policy_produces_no_message(monkeypatch, tmp_path, db):
    """검증 완료 전에는 `enabled=false` — 본문을 만들지 않는다."""
    _patch(monkeypatch, policy=None)
    out = flow.assemble_intraday_alert(
        held_drop=_held_drop(),
        holding_rows=_rows(),
        market_quotes={},
        today_kst=TODAY,
        now_kst=NOW,
        state_path=tmp_path / "s.json",
        slot_label="10:30",
        db_path=db,
    )
    assert out.message_text == ""
    assert out.skip_reason == "policy_disabled"
    assert out.diagnostics["intraday_policy_enabled"] is False


def test_policy_is_not_replaced_by_defaults_when_disabled(monkeypatch, tmp_path, db):
    """승인받지 않은 수치로 발송하면 안 된다 — 기본값 대체 금지."""
    _patch(monkeypatch, policy=None)
    out = flow.assemble_intraday_alert(
        held_drop=_held_drop(),
        holding_rows=_rows(),
        market_quotes={},
        today_kst=TODAY,
        now_kst=NOW,
        state_path=tmp_path / "s.json",
        slot_label="10:30",
        db_path=db,
    )
    assert out.plan is None


# ── §9 실패 격리 ────────────────────────────────────────────────────────────


def test_sector_failure_does_not_block_held_drop(monkeypatch, tmp_path, db):
    """**이 파일의 존재 이유.** 사업군이 터져도 보유 급락은 본문에 실린다."""
    _patch(monkeypatch, policy=_enabled_policy(), raise_on_sectors=True)
    out = flow.assemble_intraday_alert(
        held_drop=_held_drop(),
        holding_rows=_rows(),
        market_quotes={},
        today_kst=TODAY,
        now_kst=NOW,
        state_path=tmp_path / "s.json",
        slot_label="10:30",
        db_path=db,
    )
    assert "보유하락" in out.message_text
    assert out.sector_error and "의도적 실패" in out.sector_error
    assert out.sector.signals == []


def test_missing_market_db_does_not_block_held_drop(monkeypatch, tmp_path):
    """무조정 DB 가 없어도 보유 경로는 산다."""
    _patch(
        monkeypatch,
        policy=_enabled_policy(),
        sectors=[
            {
                "sector_key": "반도체",
                "representative": {"ticker": "S00001", "short_name": "대표"},
            }
        ],
    )
    out = flow.assemble_intraday_alert(
        held_drop=_held_drop(),
        holding_rows=_rows(),
        market_quotes={"S00001": Q(2.5)},
        today_kst=TODAY,
        now_kst=NOW,
        state_path=tmp_path / "s.json",
        slot_label="10:30",
        db_path=tmp_path / "없음.sqlite",
    )
    assert "보유하락" in out.message_text


def test_empty_config_still_sends_held_drop(monkeypatch, tmp_path, db):
    """config 가 비어도(사업군 0개) 보유 급락은 나간다."""
    _patch(monkeypatch, policy=_enabled_policy(), sectors=[])
    out = flow.assemble_intraday_alert(
        held_drop=_held_drop(),
        holding_rows=_rows(),
        market_quotes={},
        today_kst=TODAY,
        now_kst=NOW,
        state_path=tmp_path / "s.json",
        slot_label="10:30",
        db_path=db,
    )
    assert "보유하락" in out.message_text
    assert out.sector_error is None


def test_surge_failure_does_not_block_drop(monkeypatch, tmp_path, db):
    _patch(monkeypatch, policy=_enabled_policy(), sectors=[])
    monkeypatch.setattr(
        flow,
        "select_surge_holdings",
        lambda **kw: (_ for _ in ()).throw(RuntimeError("급등 실패")),
    )
    out = flow.assemble_intraday_alert(
        held_drop=_held_drop(),
        holding_rows=_rows(),
        market_quotes={},
        today_kst=TODAY,
        now_kst=NOW,
        state_path=tmp_path / "s.json",
        slot_label="10:30",
        db_path=db,
    )
    assert "보유하락" in out.message_text


# ── §6 상한 ─────────────────────────────────────────────────────────────────


def test_daily_cap_blocks_message(monkeypatch, tmp_path, db):
    """일일 4건을 채우면 본문을 만들지 않는다."""
    _patch(monkeypatch, policy=_enabled_policy(), sectors=[])
    p = tmp_path / "s.json"
    save_sector_state(p, entries={}, today_kst=TODAY, sent_today=4)
    out = flow.assemble_intraday_alert(
        held_drop=_held_drop(),
        holding_rows=_rows(),
        market_quotes={},
        today_kst=TODAY,
        now_kst=NOW,
        state_path=p,
        slot_label="10:30",
        db_path=db,
    )
    assert out.message_text == ""
    assert out.skip_reason == flow.REASON_DAILY_CAP


def test_under_daily_cap_still_sends(monkeypatch, tmp_path, db):
    _patch(monkeypatch, policy=_enabled_policy(), sectors=[])
    p = tmp_path / "s.json"
    save_sector_state(p, entries={}, today_kst=TODAY, sent_today=3)
    out = flow.assemble_intraday_alert(
        held_drop=_held_drop(),
        holding_rows=_rows(),
        market_quotes={},
        today_kst=TODAY,
        now_kst=NOW,
        state_path=p,
        slot_label="10:30",
        db_path=db,
    )
    assert "보유하락" in out.message_text


def test_new_day_resets_daily_cap(monkeypatch, tmp_path, db):
    """어제 4건을 채웠어도 오늘은 새로 센다."""
    _patch(monkeypatch, policy=_enabled_policy(), sectors=[])
    p = tmp_path / "s.json"
    save_sector_state(p, entries={}, today_kst="2026-09-15", sent_today=4)
    out = flow.assemble_intraday_alert(
        held_drop=_held_drop(),
        holding_rows=_rows(),
        market_quotes={},
        today_kst=TODAY,
        now_kst=NOW,
        state_path=p,
        slot_label="10:30",
        db_path=db,
    )
    assert "보유하락" in out.message_text


def test_no_signal_produces_no_message(monkeypatch, tmp_path, db):
    """모든 구역이 비면 미발송."""
    _patch(monkeypatch, policy=_enabled_policy(), sectors=[])
    out = flow.assemble_intraday_alert(
        held_drop=[],
        holding_rows=_rows(),
        market_quotes={},
        today_kst=TODAY,
        now_kst=NOW,
        state_path=tmp_path / "s.json",
        slot_label="10:30",
        db_path=db,
    )
    assert out.message_text == ""
    assert out.skip_reason == flow.REASON_NO_SIGNAL


# ── 보유 대표 중복 ──────────────────────────────────────────────────────────


def test_held_representative_not_in_entry_section(monkeypatch, tmp_path, db):
    """보유 중인 대표는 신규 진입 후보에서 빠진다(§4-2)."""
    _patch(
        monkeypatch,
        policy=_enabled_policy(),
        sectors=[
            {
                "sector_key": "반도체",
                "representative": {"ticker": "H00001", "short_name": "보유하락"},
            }
        ],
    )
    out = flow.assemble_intraday_alert(
        held_drop=_held_drop(),
        holding_rows=_rows(),
        market_quotes={"H00001": Q(2.5)},
        today_kst=TODAY,
        now_kst=NOW,
        state_path=tmp_path / "s.json",
        slot_label="10:30",
        db_path=db,
    )
    assert "신규 진입 검토" not in out.message_text


def test_no_telegram_in_module():
    """이 경로는 **발송하지 않는다.** 조회는 대체 ETF 1회만 허용된다."""
    import ast
    from pathlib import Path

    src = Path("app/runtime_evidence/intraday_alert_flow.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body[0].value.value = ""
    code = ast.unparse(tree).lower()
    for banned in ("telegram", "httpx", "requests.", "urlopen", "deliver"):
        assert banned not in code, banned


def test_alternate_fetch_is_the_only_outbound_call():
    """조회는 `fetch_alternate_quotes` 한 곳뿐이다 — 주입 가능해야 테스트가 막는다."""
    import inspect

    sig = inspect.signature(flow.build_sector_outcome)
    assert "fetch_many" in sig.parameters, "대체 조회를 대역할 수 없다"
    sig2 = inspect.signature(flow.fetch_alternate_quotes)
    assert "fetch_many" in sig2.parameters


# ── `active_policy` 자체의 계약 ─────────────────────────────────────────────
#
# 위 테스트들은 `flow.active_policy` 를 통째로 대역해 **그 함수를 실행하지
# 않는다.** 그래서 "비활성이면 기본값으로 대체" 같은 결함을 못 잡는다(실측으로
# 확인). 여기서는 `store.get_active` 만 대역하고 함수를 진짜로 돌린다.


def _payload(policy):
    return {
        "payload_json": json.dumps(
            {"intraday_alert_policy": policy, "sector_representative_universe": {}}
        )
    }


def test_active_policy_returns_none_when_disabled(monkeypatch):
    """**비활성이면 `None`.** 기본값으로 대체하면 승인 없이 발송하는 셈이다."""
    from app.intraday_config import store

    monkeypatch.setattr(
        store,
        "get_active",
        lambda **kw: _payload({"enabled": False, "cooldown_minutes": 120}),
    )
    assert flow.active_policy() is None


def test_active_policy_returns_policy_when_enabled(monkeypatch):
    from app.intraday_config import store

    policy = _enabled_policy()
    monkeypatch.setattr(store, "get_active", lambda **kw: _payload(policy))
    got = flow.active_policy()
    assert got is not None and got["max_sends_per_day"] == 4


def test_active_policy_returns_none_when_no_active(monkeypatch):
    from app.intraday_config import store

    monkeypatch.setattr(store, "get_active", lambda **kw: None)
    assert flow.active_policy() is None


def test_active_policy_never_raises_on_corrupt_payload(monkeypatch):
    """손상된 payload 가 러너를 죽이면 안 된다."""
    from app.intraday_config import store

    monkeypatch.setattr(store, "get_active", lambda **kw: {"payload_json": "{깨짐"})
    assert flow.active_policy() is None


def test_active_policy_never_raises_when_store_explodes(monkeypatch):
    from app.intraday_config import store

    def boom(**kw):
        raise RuntimeError("DB 터짐")

    monkeypatch.setattr(store, "get_active", boom)
    assert flow.active_policy() is None


# ── 대체 ETF 실제 조회 (검증자 지적 #3) ────────────────────────────────────


def _sectors_with_alt(n):
    return [
        {
            "sector_key": f"S{i}",
            "representative": {"ticker": f"T{i:05d}", "short_name": f"대표{i}"},
            "alternate": {"ticker": f"A{i:05d}", "short_name": f"대체{i}"},
        }
        for i in range(n)
    ]


class _Res:
    def __init__(self, t, q):
        self.ticker, self.quote = t, q


def test_alternate_is_actually_fetched_when_primary_missing():
    """**대표가 실패하면 대체를 실제로 조회한다.**

    예전에는 조회 대상에 대체가 없어 `market_quotes` 에 들어올 길이 없었다 —
    평가 함수가 대체를 "쓸 수 있다" 고만 했지 실제로는 늘 실패했다.
    """
    sectors = _sectors_with_alt(10)
    quotes = {f"T{i:05d}": Q(2.0) for i in range(1, 10)}  # 0번만 실패
    called: list[list[str]] = []

    def fake(tickers):
        called.append(list(tickers))
        return [_Res(t, Q(1.8)) for t in tickers]

    extra = flow.fetch_alternate_quotes(sectors, quotes, TODAY, fetch_many=fake)
    assert called == [["A00000"]], called
    assert "A00000" in extra


def test_alternate_not_fetched_when_all_primaries_ok():
    sectors = _sectors_with_alt(10)
    quotes = {f"T{i:05d}": Q(2.0) for i in range(10)}
    called = []
    flow.fetch_alternate_quotes(
        sectors, quotes, TODAY, fetch_many=lambda t: called.append(t) or []
    )
    assert called == []


def test_alternate_not_fetched_on_provider_failure():
    """provider 장애면 대체를 **한 건도** 부르지 않는다(§14-5)."""
    sectors = _sectors_with_alt(27)
    called = []
    flow.fetch_alternate_quotes(
        sectors, {}, TODAY, fetch_many=lambda t: called.append(t) or []
    )
    assert called == [], f"provider 장애인데 {called} 를 조회했다"


def test_alternate_fetch_failure_is_isolated():
    sectors = _sectors_with_alt(10)
    quotes = {f"T{i:05d}": Q(2.0) for i in range(1, 10)}

    def boom(tickers):
        raise RuntimeError("네트워크 죽음")

    assert flow.fetch_alternate_quotes(sectors, quotes, TODAY, fetch_many=boom) == {}


def test_build_sector_outcome_uses_fetched_alternate(monkeypatch, tmp_path, db):
    """조회한 대체가 실제 판정에 쓰인다."""
    sectors = _sectors_with_alt(10)
    monkeypatch.setattr(flow, "_load_active_sectors", lambda logger=None: sectors)
    quotes = {f"T{i:05d}": Q(2.0 - i * 0.1) for i in range(1, 10)}
    out, err = flow.build_sector_outcome(
        market_quotes=quotes,
        today_kst=TODAY,
        policy=_enabled_policy(),
        held_tickers=set(),
        db_path=db,
        fetch_many=lambda t: [_Res(x, Q(3.0)) for x in t],
    )
    assert err is None
    assert out.evaluated_count == 10, "대체로 살아난 사업군이 빠졌다"
