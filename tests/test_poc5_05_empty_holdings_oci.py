"""POC5-05 Q-A — OCI 소비 경로의 **정상 빈 보유** (설계 §7 · §9-5 · §11-1 Q-A).

정상 빈 보유 = 보유 파일은 있고 `holdings` 가 `[]`(전 종목 매도 뒤 적용). 확정 계약:

- 보유 브리핑: 발송하지 않고 `skipped/no_holdings`(선정 0 = `no_selection` 과 같은 결).
- 위험 알림: 사업군 대표가 있으면 대표만으로 계속 · 대표도 0 이면 `skipped/no_holdings`.
- 파일 없음 · 손상 · `holdings` 키 없음은 기존 실패 그대로 — 새 skip 으로 숨기지 않는다.
- 배치 seed · KRX 개별주 `no_holdings` · 가격 결과 보유 조회는 기존 코드 그대로 정상.

tmp 보유 파일(conftest `_isolated_store`) · tmp 상태 경로 · 시세 · Telegram 대역만 쓴다.
라이브 state · DB · 네트워크 · 실발송 0.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app import holdings as holdings_mod
from app.runtime_evidence.holdings_selection_flow import REASON_NO_HOLDINGS

# rig 들이 `holdings.load` 를 바꿔 끼우기 전에 진짜 loader 를 잡아 둔다.
_REAL_LOAD = holdings_mod.load

EMPTY = '{"holdings": []}'
# 파일 없음 · 손상 · 키 없음 — 정상 빈 보유가 아니다.
FILE_PROBLEMS = [(None, "missing"), ("{broken", "corrupt"), ('{"rows": []}', "no_key")]


def _write_holdings(content):
    """conftest 가 격리한 tmp 보유 파일에 쓴다. None 이면 파일 없음."""
    path = holdings_mod.HOLDINGS_FILE
    if content is None:
        assert not path.exists()
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _no_history(*a, **kw):
    raise AssertionError("정상 빈 보유인데 가격 이력을 조회했다")


# ── 공용 수집 helper (target_tickers) ─────────────────────────────────────────


def test_target_tickers_normal_empty_is_not_failure(monkeypatch):
    """브리핑 = [] · 위험 알림 = 사업군 대표만(대표 0 이면 [])."""
    from app.three_push_runtime import target_tickers as tt

    _write_holdings(EMPTY)
    assert tt.collect_target_tickers("holdings_briefing") == []

    monkeypatch.setattr(
        tt, "sector_representative_tickers", lambda: ["T00001", "T00002"]
    )
    assert tt.collect_target_tickers("holdings_risk_alert") == ["T00001", "T00002"]

    monkeypatch.setattr(tt, "sector_representative_tickers", lambda: [])
    assert tt.collect_target_tickers("holdings_risk_alert") == []


@pytest.mark.parametrize("kind", ["holdings_briefing", "holdings_risk_alert"])
@pytest.mark.parametrize("content, label", FILE_PROBLEMS, ids=lambda v: str(v))
def test_target_tickers_file_problems_still_raise(kind, content, label):
    """파일 없음 = RuntimeError · 손상 · 키 없음 = load() 예외 그대로(Fail-Closed)."""
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _write_holdings(content)
    if label == "missing":
        with pytest.raises(RuntimeError, match="holdings source missing"):
            collect_target_tickers(kind)
    elif label == "corrupt":
        with pytest.raises(json.JSONDecodeError):
            collect_target_tickers(kind)
    else:
        with pytest.raises(holdings_mod.HoldingsValidationError):
            collect_target_tickers(kind)


# ── 기존 소비자 회귀 (코드 변경 없음 · 공용 loader 만으로 정상) ────────────────


def test_batch_collect_approved_tickers_returns_seed_only(monkeypatch):
    """08:10 · 09:20 배치 — 정상 빈 보유는 실패가 아니다(승인 seed 만)."""
    from app import universe_seed as _us
    from app.three_push_runtime import market_data_batch as mdb
    from app.universe_seed import UniverseSeed, UniverseSeedItem

    seed = UniverseSeed(
        asof="2026-10-08",
        source="manual_seed",
        source_freshness="fresh",
        staleness_days=0,
        items=[
            UniverseSeedItem(
                ticker=t, name=t, universe_group=None, sector_or_theme=None
            )
            for t in ("069500", "102110")
        ],
    )
    monkeypatch.setattr(_us, "load_universe_seed", lambda *a, **k: seed)
    _write_holdings(EMPTY)
    assert mdb.collect_approved_tickers() == ["069500", "102110"]


def test_krx_stock_holdings_tickers_reports_no_holdings():
    """KRX 개별주 보강 — 정상 빈 보유 = `(None, 'no_holdings')`(조회 0 · 기록만)."""
    from app.market_briefing import krx_stock_sync as kss

    _write_holdings(EMPTY)
    assert kss.holdings_tickers() == (None, "no_holdings")
    assert kss.STATUS_NO_HOLDINGS == "no_holdings"


def test_price_outcome_holdings_is_empty_set_not_unknown():
    """가격 결과 — 보유 조회가 빈 집합(None 아님) → 매도 뒤 개별주 판정이 '모름' 이 아니다."""
    from app.three_push_runtime import ledger_outcome as lo
    from app.three_push_runtime import ledger_outcome_prices as px

    _write_holdings(EMPTY)
    assert px.load_holdings() == []
    holdings = px.current_holdings()
    assert holdings == set() and holdings is not None

    class _Reader:
        def latest_date(self, series, ident=None):
            # 개별주 행은 첫 빠진 날 전에 끊김 · 공통 축(ETF 표)은 평가일을 지남.
            return "2026-10-09" if series == px.SERIES_STOCK else "2026-10-20"

    target = SimpleNamespace(held=1)
    series = SimpleNamespace(series=px.SERIES_STOCK, ident="005930")
    args = ("2026-10-12", "2026-10-15", _Reader())
    assert lo._untracked(target, series, *args, holdings) is True
    # 대조군 — 보유를 모르면(None) 매도 판정을 하지 않는다.
    assert lo._untracked(target, series, *args, None) is False


# ── 조립 (가드 앞 처리) ──────────────────────────────────────────────────────


def _briefing(tmp_path, diag=None):
    from app.runtime_evidence.holdings_selection_flow import assemble_holdings_push

    return assemble_holdings_push(
        market_quotes={},
        price_refresh_diag=diag or {"attempted": 0, "success": 0, "failed": 0},
        today_kst="2026-10-08",
        state_path=tmp_path / "selection_state.json",
        slot_id="OPEN",
        runtime_kst="2026-10-08T09:15:00+09:00",
        holdings_loader=holdings_mod.load,
        fetch_history=_no_history,
    )


def _risk(tmp_path):
    from app.runtime_evidence.holdings_risk_flow import assemble_holdings_risk_push

    return assemble_holdings_risk_push(
        market_quotes={},
        price_refresh_diag={"attempted": 0, "success": 0, "failed": 0},
        today_kst="2026-10-08",
        state_path=tmp_path / "risk_state.json",
        runtime_kst="2026-10-08T10:30:00+09:00",
        holdings_loader=holdings_mod.load,
        fetch_history=_no_history,
        sector_state_path=tmp_path / "sector.json",
        tally_path=tmp_path / "tally.json",
    )


def test_briefing_assembly_skips_before_completeness_guard(tmp_path):
    """대상 0 이 `holdings_quotes_incomplete_no_today` 로 막히지 않고 no_holdings skip 지시."""
    _write_holdings(EMPTY)
    asm = _briefing(tmp_path)
    assert asm.fail is None
    assert asm.skip_non_trading_day is False
    assert asm.message_text == ""
    out = asm.outcome
    assert out.skip_reason == REASON_NO_HOLDINGS == "no_holdings"
    # 선정 0(`no_selection`)과 같은 결 — 빈 상태 저장 지시 · 본문 없음 · 원장 관측 0.
    assert out.save_empty_state is True
    assert out.save_state_on_send is False
    assert out.selected == [] and out.observations == []
    assert asm.diagnostics["holdings_loaded_count"] == 0
    assert not (tmp_path / "selection_state.json").exists()  # 저장은 러너 §6-c


def test_risk_assembly_without_reps_skips_no_holdings(tmp_path):
    """보유 0 · 대표 0 = 조회 대상 0 → 가드 앞에서 no_holdings · 장중 기록 0."""
    _write_holdings(EMPTY)
    asm = _risk(tmp_path)
    assert asm.fail is None
    assert asm.message_text == ""
    assert asm.outcome.skip_reason == "no_holdings"
    assert asm.intraday_records is None and asm.intraday is None
    assert not (tmp_path / "sector.json").exists()
    assert not (tmp_path / "tally.json").exists()


@pytest.mark.parametrize("content, label", FILE_PROBLEMS, ids=lambda v: str(v))
def test_assembly_file_problems_keep_existing_failure(tmp_path, content, label):
    """파일 없음 · 손상 · 키 없음 = 기존 완전성 가드 실패 그대로(no_holdings 아님)."""
    _write_holdings(content)
    for asm in (_briefing(tmp_path), _risk(tmp_path)):
        assert asm.fail is not None, label
        assert asm.fail[:2] == ("failed", "holdings_quotes_incomplete_no_today")
        assert asm.outcome is None


def test_briefing_with_targets_never_calls_empty_check(tmp_path):
    """조회 대상이 있으면 빈 보유 판정을 하지 않는다 — 비어 있지 않은 보유는 기존 경로."""
    from app.runtime_evidence.holdings_selection_flow import should_skip_no_holdings

    calls: list[int] = []

    def _loader():
        calls.append(1)
        return []

    _write_holdings(EMPTY)
    assert should_skip_no_holdings({"target_tickers": ["069500"]}, _loader) is False
    assert calls == []
    assert should_skip_no_holdings({}, _loader) is True
    # loader 예외(조회 실패)는 정상 빈 보유가 아니다.
    assert should_skip_no_holdings({}, lambda: 1 / 0) is False


# ── 러너 실행 경로 ───────────────────────────────────────────────────────────


def _briefing_runner(monkeypatch, tmp_path):
    from tests.low_frequency_push._fixtures import (
        _install_common_mocks,
        _install_naver,
        _seed_and_get_param,
    )

    _seed_and_get_param(tmp_path)
    runner = _install_common_mocks(monkeypatch, tmp_path)
    state = tmp_path / "selection_state.json"
    monkeypatch.setattr(runner, "HOLDINGS_SELECTION_STATE_PATH", state)
    sent: list[str] = []
    monkeypatch.setattr(
        runner,
        "telegram_send",
        lambda text, *a, **kw: (sent.append(text), (True, "", False))[1],
    )
    naver: list[str] = []

    def _fetch_many(tickers, timeout=15.0):
        naver.extend(tickers)
        raise AssertionError("정상 빈 보유인데 시세를 조회했다")

    _install_naver(monkeypatch, _fetch_many)
    return runner, sent, naver, state


def test_runner_briefing_normal_empty_is_skipped_no_holdings(tmp_path, monkeypatch):
    """보유 브리핑 실행 — skipped/no_holdings · Telegram 0 · 시세 조회 0 · 빈 상태 저장."""
    from app.runtime_sent_registry_store import count as registry_count

    runner, sent, naver, state = _briefing_runner(monkeypatch, tmp_path)
    _write_holdings(EMPTY)
    before = registry_count()
    rec = runner.run("holdings_briefing", "send", slot_id="OPEN")
    assert (rec["status"], rec["reason"]) == ("skipped", "no_holdings")
    assert rec["telegram_attempted"] is False
    assert sent == [] and naver == []
    assert registry_count() == before
    assert rec["runtime_price_refresh"]["attempted"] == 0
    saved = json.loads(state.read_text(encoding="utf-8"))
    assert saved["last_slot"] == "OPEN" and not saved["entries"]


@pytest.mark.parametrize("kind", ["holdings_briefing", "holdings_risk_alert"])
@pytest.mark.parametrize("content, label", FILE_PROBLEMS, ids=lambda v: str(v))
def test_runner_file_problems_still_fail(tmp_path, monkeypatch, kind, content, label):
    """파일 없음 · 손상 · 키 없음 = 기존 failed(runtime_price_refresh_error) · 발송 0."""
    runner, sent, naver, _ = _briefing_runner(monkeypatch, tmp_path)
    _write_holdings(content)
    rec = runner.run(
        kind, "send", slot_id="OPEN" if kind == "holdings_briefing" else None
    )
    assert (rec["status"], rec["reason"]) == ("failed", "runtime_price_refresh_error")
    assert sent == [] and naver == []


def _risk_rig(monkeypatch, tmp_path):
    """기존 장중 flow-through rig + 보유만 정상 빈 보유(진짜 loader · tmp 파일)."""
    import sqlite3

    from tests.test_intraday_alert_flow_through import FIXTURE_DAYS, _build_rig

    # 그 모듈의 `market_db` fixture 와 같은 tmp 무조정 표(대표 10종 · 25일).
    db = tmp_path / "m.sqlite"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE krx_etf_daily_price_unadjusted(ticker TEXT,date TEXT,close REAL)"
    )
    con.executemany(
        "INSERT INTO krx_etf_daily_price_unadjusted VALUES(?,?,?)",
        [
            (f"T{i:05d}", d, 100.0 + n)
            for i in range(10)
            for n, d in enumerate(FIXTURE_DAYS)
        ],
    )
    con.commit()
    con.close()
    rig = _build_rig(monkeypatch, tmp_path, db)
    # `db_path` 기본값은 정의 때 묶여 rig 의 모듈 상수 교체가 닿지 않는다(그 모듈 테스트는
    # 라이브 읽기 허용 목록). 위험 흐름은 호출 때 이 이름을 import 하므로 tmp DB 를 묶는다.
    import functools

    import app.runtime_evidence.intraday_alert_flow as iflow

    monkeypatch.setattr(
        iflow,
        "assemble_intraday_alert",
        functools.partial(iflow.assemble_intraday_alert, db_path=db),
    )
    monkeypatch.setattr(holdings_mod, "load", _REAL_LOAD)
    holdings_mod.HOLDINGS_FILE.write_text(EMPTY, encoding="utf-8")
    return rig


def test_runner_risk_with_reps_continues_on_reps_only(tmp_path, monkeypatch):
    """위험 알림 — 보유가 비어도 사업군 대표만으로 계속(조회 = 대표뿐 · 실패 아님)."""
    from tests.test_intraday_alert_flow_through import TODAY, _asof, _Q

    rig = _risk_rig(monkeypatch, tmp_path)
    rig["quotes"] = {
        f"T{i:05d}": _Q(10000.0, _asof(TODAY), -2.5 + i * 0.1) for i in range(10)
    }
    rec = rig["runner"].run("holdings_risk_alert", "send")
    assert rig["naver_calls"] and all(t.startswith("T") for t in rig["naver_calls"])
    assert rec["status"] == "sent", rec.get("reason")
    assert rec["risk_holdings_loaded_count"] == 0
    assert len(rig["sent"].calls) == 1
    assert "[장중 급등락]" in rig["sent"].calls[0]


def test_runner_risk_without_reps_is_skipped_no_holdings(tmp_path, monkeypatch):
    """위험 알림 — 보유 0 · 대표 0(정책 비활성) = skipped/no_holdings · 조회 0 · 발송 0."""
    from tests.test_intraday_alert_flow_through import _policy

    rig = _risk_rig(monkeypatch, tmp_path)
    rig["policy"] = _policy(enabled=False)
    rec = rig["runner"].run("holdings_risk_alert", "send")
    assert (rec["status"], rec["reason"]) == ("skipped", "no_holdings")
    assert rig["naver_calls"] == [] and rig["sent"].calls == []
    assert not rig["sector_state"].exists() and not rig["tally"].exists()
