"""POC3-02D-OPS-03 설계자 RESULT STEP 1 — 보유 PUSH 가격 기준 계약 (2026-09-30).

```text
ETF     현재가 = Naver 무조정 · 20거래일 전 종가 · 구간 종가 = KRX 무조정
        조정계열(etf_daily_price · fetch_history) fallback 금지 · 두 계열을 섞지 않는다
개별주  현재가 · 과거 종가 = 기존 FDR/Naver · KRX ETF 표 가격을 읽지 않는다
        파생값은 늘 fail-closed(혼합 확정 2026-09-30) · T-1 가드(0.5%)는 기록만
구분    공식 ETF 마스터 CSV 또는 KRX 표 적재 기록 = ETF · 둘 다 읽고 없음 = 개별주 · 그 밖 = 미상
```

닫는 것은 파생값(20거래일 수익률 · 고점 대비)뿐이다 — 급락 판정(Naver 등락률)은 그대로.

실 Naver · KRX · Telegram 호출 0건 · CSV · DB · 캘린더 · 상태 파일은 전부 tmp 경로다.

다른 테스트 모듈이 쓰는 대역(`etf_basis_source` · `stock_basis_source` ·
`install_etf_basis_from_store`)은 `tests/_helpers.py` 에 있다.
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import pytest

from app.market_briefing import krx_store
from app.market_briefing.official_csv import EXPECTED_HEADER
from app.runtime_evidence import holdings_price_basis as hpb
from app.runtime_evidence.holdings_risk_flow import build_holdings_risk_alert
from app.runtime_evidence.holdings_selection_flow import (
    assemble_holdings_push,
    build_holdings_selection,
)
from app.runtime_evidence.holdings_selection_source import trading_day_axis

# ── 고정 날짜 · 캘린더 ─────────────────────────────────────────────────────────

TODAY = "2026-09-30"
HOLIDAYS = {"2026-09-24", "2026-09-25"}


def _trading_days() -> list[str]:
    d, out = date(2026, 7, 20), []
    while d <= date.fromisoformat(TODAY):
        if d.weekday() < 5 and d.isoformat() not in HOLIDAYS:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


DAYS = _trading_days()
PAST = [d for d in DAYS if d < TODAY]
T1 = PAST[-1]
BASE = PAST[-20]
WINDOW = PAST[-20:]

ETF = "0005G0"
STOCK = "005930"


@dataclass
class H:
    ticker: str
    name: str
    account_group: str = "일반"


@dataclass
class Q:
    current_price: float
    day_return_pct: Optional[float] = None
    price_asof: str = f"{TODAY}T09:14:00+09:00"

    def has_day_return(self):
        v = self.day_return_pct
        return isinstance(v, (int, float)) and not isinstance(v, bool)


def _calendar(tmp_path):
    cal = tmp_path / "cal"
    cal.mkdir(exist_ok=True)
    (cal / "krx_trading_days_2026.csv").write_text(
        "date\n" + "\n".join(DAYS) + "\n", encoding="utf-8"
    )
    return cal


def _rows(value=100.0, *, drop=(), special=None):
    special = special or {}
    return [(d, special.get(d, value)) for d in PAST if d not in set(drop)]


class _Spy:
    """원천 호출 기록 대역. `master=None` · `krx=None` 은 '읽을 수 없음'."""

    def __init__(self, *, master=(), krx=None, present=None):
        self.master = master
        self.krx = krx  # {ticker: [(date, close)]} · None = 읽기 실패
        self.present = present
        self.calls: list[tuple[tuple[str, ...], tuple[str, ...]]] = []

    def source(self) -> hpb.PriceBasisSource:
        def _master():
            if self.master is None:
                raise OSError("csv")
            return frozenset(self.master), "krx_etf_basic_fixture.csv"

        def _krx(tickers, dates=()):
            self.calls.append((tuple(tickers), tuple(dates)))
            if self.krx is None:
                raise sqlite3.OperationalError("no such table")
            present = set(self.present if self.present is not None else self.krx)
            wanted = set(dates)
            closes = {
                t: {d: c for d, c in self.krx.get(t, []) if d in wanted}
                for t in tickers
                if t in self.krx and wanted
            }
            return present & set(tickers), closes

        return hpb.PriceBasisSource(etf_master=_master, krx_prices=_krx)


class _Fetch:
    """FDR(`etf_daily_price`) 대역 — 호출 ticker 를 센다."""

    def __init__(self, rows_by_ticker):
        self.rows = rows_by_ticker
        self.calls: list[str] = []

    def __call__(self, ticker, **kw):
        self.calls.append(ticker)
        return list(self.rows.get(ticker, []))


def _selection(tmp_path, *, spy, fetch, quotes, holdings=None):
    return build_holdings_selection(
        holdings_loader=lambda: holdings or [H(t, f"종목{t}") for t in quotes],
        fetch_history=fetch,
        market_quotes=quotes,
        state_path=tmp_path / "sel.json",
        slot_id="OPEN",
        runtime_kst=f"{TODAY}T09:15:00+09:00",
        today_kst=TODAY,
        calendar_dir=_calendar(tmp_path),
        price_basis_source=spy.source(),
    )


def _risk(tmp_path, *, spy, fetch, quotes):
    return build_holdings_risk_alert(
        holdings_loader=lambda: [H(t, f"종목{t}") for t in quotes],
        fetch_history=fetch,
        market_quotes=quotes,
        state_path=tmp_path / "risk.json",
        runtime_kst=f"{TODAY}T10:30:00+09:00",
        today_kst=TODAY,
        calendar_dir=_calendar(tmp_path),
        price_basis_source=spy.source(),
    )


# ── ETF = KRX 무조정 ───────────────────────────────────────────────────────────


def test_etf_uses_krx_closes_even_when_fdr_differs(tmp_path):
    """KRX 기준 100 → -12% · FDR(조정) 기준 90 이었다면 -2.2%(미선정). FDR 은 읽지 않는다."""
    spy = _Spy(master={ETF}, krx={ETF: _rows(special={PAST[-5]: 110.0})})
    fetch = _Fetch({ETF: _rows(special={BASE: 90.0, PAST[-3]: 120.0})})
    out = _selection(tmp_path, spy=spy, fetch=fetch, quotes={ETF: Q(88.0, -1.0)})
    assert not out.error, out.error
    assert "20거래일 -12.0%" in out.message_text
    assert "고점 대비 -20.0%" in out.message_text  # 88 / 110(KRX 고점) − 1
    assert fetch.calls == []  # ETF 는 조정계열을 부르지 않는다
    # 축 20거래일 + 앞쪽 여유 10거래일(연도 파일 없는 해의 휴장 평일 건너뛰기 대비).
    assert (tuple([ETF]), tuple(PAST[-30:])) in spy.calls


def test_etf_missing_krx_base_is_not_filled_from_fdr(tmp_path):
    """KRX T-20 종가가 없으면 그 파생값만 `데이터 확인 불가` — FDR 로 메우지 않는다."""
    spy = _Spy(master={ETF}, krx={ETF: _rows(drop=[BASE])})
    fetch = _Fetch({ETF: _rows()})
    out = _selection(tmp_path, spy=spy, fetch=fetch, quotes={ETF: Q(88.0, -1.0)})
    item = out.selected[0]
    assert item.primary_reason == "DATA_UNAVAILABLE_OR_STALE"
    assert "■ 데이터 확인 필요 (1)" in out.message_text
    assert "20거래일 데이터 확인 불가" in out.message_text
    assert "현재가 조회 실패" not in out.message_text
    assert fetch.calls == []
    derived = out.diagnostics["holdings_price_basis"]["tickers"][ETF]["derived"]
    assert derived == {"base_close": "missing", "window": "missing:1"}


def test_etf_without_any_krx_rows_is_not_filled_from_fdr(tmp_path):
    """CSV 로 ETF 확정 · KRX 표에 행이 하나도 없다 → FDR 전체 이력이 있어도 쓰지 않는다."""
    spy = _Spy(master={ETF}, krx={})
    fetch = _Fetch({ETF: _rows()})
    out = _selection(tmp_path, spy=spy, fetch=fetch, quotes={ETF: Q(88.0, -1.0)})
    assert "20거래일 데이터 확인 불가" in out.message_text
    assert fetch.calls == []
    derived = out.diagnostics["holdings_price_basis"]["tickers"][ETF]["derived"]
    assert derived == {"base_close": "missing", "window": "missing:20"}


def test_current_price_failure_keeps_its_own_wording(tmp_path):
    """현재가 자체가 없을 때만 `현재가 조회 실패`(기준 종가까지 없어도 현재가가 먼저)."""
    spy = _Spy(master={ETF}, krx={ETF: _rows(drop=[BASE])})
    out = _selection(tmp_path, spy=spy, fetch=_Fetch({}), quotes={ETF: Q(0.0, None)})
    assert "현재가 조회 실패" in out.message_text
    assert "20거래일 데이터 확인 불가" not in out.message_text


def test_etf_drawdown_omitted_when_krx_window_incomplete(tmp_path):
    """구간 하루가 빠지면 고점 대비만 생략 — 20거래일 수익률은 그대로 · FDR 로 채우지 않는다."""
    spy = _Spy(master={ETF}, krx={ETF: _rows(drop=[PAST[-4]])})
    fetch = _Fetch({ETF: _rows(special={PAST[-4]: 130.0})})
    out = _selection(tmp_path, spy=spy, fetch=fetch, quotes={ETF: Q(88.0, -1.0)})
    assert "20거래일 -12.0%" in out.message_text
    assert "고점 대비" not in out.message_text
    assert out.selected[0].drawdown_20d_pct is None
    derived = out.diagnostics["holdings_price_basis"]["tickers"][ETF]["derived"]
    assert derived == {"base_close": "ok", "window": "missing:1"}


def test_krx_unreadable_closes_only_etf_derived_values(tmp_path):
    """KRX 표를 못 읽으면 ETF 파생값만 닫힌다(CSV 로 ETF 확정) — FDR fallback 없음."""
    spy = _Spy(master={ETF}, krx=None)
    fetch = _Fetch({ETF: _rows()})
    out = _selection(tmp_path, spy=spy, fetch=fetch, quotes={ETF: Q(88.0, -1.0)})
    assert "20거래일 데이터 확인 불가" in out.message_text
    assert fetch.calls == []
    ev = out.diagnostics["holdings_price_basis"]
    assert ev["krx_table"] == "unreadable:OperationalError"
    assert ev["tickers"][ETF]["reason"] == "krx_unreadable"


# ── 개별주 = FDR + 혼합 가드 ───────────────────────────────────────────────────


def test_stock_uses_fdr_and_never_reads_krx_prices(tmp_path):
    """개별주 과거 종가는 FDR. KRX 표는 구분(적재 기록)만 묻고 가격은 묻지 않는다.

    혼합 확정(설계자 RESULT STEP 1-7) — 가드가 통과해도 파생값은 닫는다.
    """
    spy = _Spy(master={ETF}, krx={ETF: _rows()})
    fetch = _Fetch({STOCK: _rows()})
    quotes = {ETF: Q(99.0, -1.0), STOCK: Q(88.0, -12.0)}  # Naver 전일 = 100 = FDR T-1
    out = _selection(tmp_path, spy=spy, fetch=fetch, quotes=quotes)
    assert fetch.calls == [STOCK]
    price_calls = [c for c in spy.calls if c[1]]
    assert price_calls and all(STOCK not in tickers for tickers, _ in price_calls)
    assert ((STOCK,), ()) in spy.calls  # 구분용 적재 기록 조회(날짜 없음)
    assert "20거래일 데이터 확인 불가" in out.message_text
    assert "20거래일 -12.0%" not in out.message_text
    ev = out.diagnostics["holdings_price_basis"]["tickers"][STOCK]
    assert ev["reason"] == "price_basis_mismatch"
    assert ev["derived"] == {"base_close": "blocked", "window": "blocked"}
    assert (
        ev["asset_type"] == "STOCK" and ev["class_source"] == "etf_master_csv+krx_table"
    )
    assert (
        ev["price_source"] == "FinanceDataReader" and ev["price_basis"] == "fdr_naver"
    )
    assert ev["guard"]["ok"] is True and ev["guard"]["diff_pct"] == 0.0
    assert ev["guard"]["t1"] == T1


@pytest.mark.parametrize(
    "fdr_t1, day_return, guard_ok",
    [
        (100.4, -12.0, True),  # +0.4% — 허용 폭 안(그래도 닫는다)
        (99.0, -12.0, False),  # -1.0% — 그날 차이
        (100.0, None, False),  # Naver 등락률 없음 — 비교 불가
        (None, -12.0, False),  # FDR T-1 종가 없음(배치 실패) — 비교 불가
    ],
)
def test_stock_derived_values_always_fail_closed_guard_is_recorded(
    tmp_path, fdr_t1, day_return, guard_ok
):
    """개별주 FDR 일봉 종가 ≠ KRX 정규장 종가(혼합 확정) — 가드 결과와 무관하게 닫는다."""
    special = {T1: fdr_t1} if fdr_t1 is not None else {}
    rows = _rows(special=special, drop=[T1] if fdr_t1 is None else ())
    spy = _Spy(master=set(), krx={})
    out = _selection(
        tmp_path,
        spy=spy,
        fetch=_Fetch({STOCK: rows}),
        quotes={STOCK: Q(88.0, day_return)},
    )
    ev = out.diagnostics["holdings_price_basis"]["tickers"][STOCK]
    assert ev["guard"]["ok"] is guard_ok
    assert ev["reason"] == "price_basis_mismatch"
    assert ev["derived"] == {"base_close": "blocked", "window": "blocked"}
    assert "20거래일 데이터 확인 불가" in out.message_text
    assert "20거래일 -" not in out.message_text


# ── 자산 유형 구분 ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "master, krx, present, expected, cls",
    [
        ({ETF}, {ETF: _rows()}, None, "ETF", "etf_master_csv"),
        (set(), {ETF: _rows()}, None, "ETF", "krx_table"),  # CSV 날짜 뒤 상장
        (None, {ETF: _rows()}, None, "ETF", "krx_table"),  # CSV 못 읽음 · 표에 있음
        (set(), {}, None, "STOCK", "etf_master_csv+krx_table"),
        (None, None, None, "UNKNOWN", None),  # 둘 다 못 읽음
        (set(), None, None, "UNKNOWN", None),  # 표 못 읽음 — 새 ETF 일 수 있다
        (None, {}, None, "UNKNOWN", None),  # CSV 못 읽음 — 개별주라고 확정 못 함
    ],
)
def test_classification_sources(tmp_path, master, krx, present, expected, cls):
    spy = _Spy(master=master, krx=krx, present=present)
    kinds, status = hpb.classify_assets([ETF], spy.source())
    assert kinds[ETF] == (expected, cls)
    assert set(status) >= {"etf_master"}


def test_unknown_asset_type_fails_closed_in_both_flows(tmp_path):
    """구분 불가 → 20거래일 · 고점 대비를 닫는다. 추측해 FDR 을 쓰지 않는다."""
    spy = _Spy(master=None, krx=None)
    fetch = _Fetch({ETF: _rows()})
    sel = _selection(tmp_path, spy=spy, fetch=fetch, quotes={ETF: Q(88.0, -6.0)})
    assert "20거래일 데이터 확인 불가" in sel.message_text
    ev = sel.diagnostics["holdings_price_basis"]
    assert ev["tickers"][ETF]["asset_type"] == "UNKNOWN"
    assert ev["tickers"][ETF]["reason"] == "asset_type_unknown"
    assert ev["etf_master"] == "unreadable:OSError"
    risk = _risk(tmp_path, spy=spy, fetch=fetch, quotes={ETF: Q(94.0, -6.0)})
    assert fetch.calls == []
    # 급락 판정은 Naver 등락률 그대로 — 고점 대비 보조값만 빠진다.
    assert risk.selected and risk.selected[0].state == "D5_7"
    assert risk.selected[0].day_drop_pct == -6.0
    assert risk.selected[0].drawdown_pct is None


# ── 캘린더 없는 해(평일 fallback) ──────────────────────────────────────────────


def test_blocked_stock_dates_still_confirm_weekdays_in_uncovered_year(tmp_path):
    """가드에 막힌 개별주 FDR 날짜도 '그 평일은 거래일' 근거다 — 가격 성격이 달라도
    거래가 있었다는 사실은 같다. 빼면 KRX 적재가 하루 빈 ETF 의 20거래일 수익률까지
    닫힌다(기준일 종가는 있는데)."""
    cal = tmp_path / "cal2026"
    cal.mkdir()
    d, days = date(2026, 1, 1), []
    while d.year == 2026:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d += timedelta(days=1)
    (cal / "krx_trading_days_2026.csv").write_text(
        "date\n" + "\n".join(days) + "\n", encoding="utf-8"
    )
    today = "2027-01-06"  # 2027 캘린더 없음
    axis = trading_day_axis(today, calendar_dir=cal)
    assert axis[-2] == "2027-01-04"
    gap = axis[-2]  # 2027-01-04 — KRX 적재가 빈 평일(캘린더 없는 해 · 기준일 아님)
    asof = f"{today}T09:14:00+09:00"
    spy = _Spy(master={ETF}, krx={ETF: [(x, 100.0) for x in axis if x != gap]})
    fetch = _Fetch({STOCK: [(x, 100.0) for x in axis[:-1]] + [(axis[-1], 103.0)]})
    out = build_holdings_selection(
        holdings_loader=lambda: [H(ETF, "ETF하나"), H(STOCK, "주식하나")],
        fetch_history=fetch,
        market_quotes={ETF: Q(88.0, -1.0, asof), STOCK: Q(88.0, -12.0, asof)},
        state_path=tmp_path / "sel.json",
        slot_id="OPEN",
        runtime_kst=f"{today}T09:15:00+09:00",
        today_kst=today,
        calendar_dir=cal,
        price_basis_source=spy.source(),
    )
    ev = out.diagnostics["holdings_price_basis"]["tickers"]
    assert ev[STOCK]["reason"] == "price_basis_mismatch"  # FDR 103 vs Naver 전일 100
    assert out.diagnostics["holdings_trading_day_axis_len"] == 20
    assert "20거래일 -12.0%" in out.message_text  # ETF — KRX 기준일 종가 있음
    assert ev[ETF]["derived"] == {"base_close": "ok", "window": "missing:1"}
    assert "20거래일 데이터 확인 불가" in out.message_text  # 개별주 — 혼합 확정


# ── 장중 보유 위험 경로 ────────────────────────────────────────────────────────


def test_risk_drawdown_uses_krx_for_etf_and_fdr_for_stock(tmp_path):
    spy = _Spy(master={ETF}, krx={ETF: _rows(special={PAST[-2]: 125.0})})
    fetch = _Fetch(
        {ETF: _rows(special={PAST[-2]: 200.0}), STOCK: _rows(special={PAST[-6]: 110.0})}
    )
    quotes = {ETF: Q(94.0, -6.0), STOCK: Q(94.0, -6.0)}
    out = _risk(tmp_path, spy=spy, fetch=fetch, quotes=quotes)
    by = {i.ticker: i for i in out.selected}
    assert by[ETF].drawdown_pct == -24.8  # 94 / 125(KRX) − 1 · FDR 200 이 아니다
    # 개별주 — FDR 을 읽어 가드는 통과하지만 혼합 확정으로 고점 대비는 닫는다 · 급락은 그대로.
    assert by[STOCK].drawdown_pct is None and by[STOCK].state == "D5_7"
    assert fetch.calls == [STOCK]
    ev = out.diagnostics["risk_price_basis"]["tickers"]
    assert ev[ETF]["price_source"] == "KRX_OPEN_API/etf_bydd_trd"
    assert ev[STOCK]["guard"]["ok"] is True
    assert ev[STOCK]["reason"] == "price_basis_mismatch"


def test_risk_stock_mismatch_omits_drawdown_but_keeps_day_drop(tmp_path):
    spy = _Spy(master=set(), krx={})
    fetch = _Fetch({STOCK: _rows(special={T1: 103.0})})  # Naver 전일 100 과 3% 차이
    out = _risk(tmp_path, spy=spy, fetch=fetch, quotes={STOCK: Q(94.0, -6.0)})
    assert out.selected and out.selected[0].state == "D5_7"
    assert out.selected[0].drawdown_pct is None
    ev = out.diagnostics["risk_price_basis"]["tickers"][STOCK]
    assert ev["reason"] == "price_basis_mismatch" and ev["guard"]["diff_pct"] == 3.0


# ── evidence · 러너 기록 ───────────────────────────────────────────────────────


def test_evidence_fields_reach_assembly_diagnostics_as_json(tmp_path):
    """러너는 `record.update(_asm.diagnostics)` 로 실행 기록에 싣는다 — JSON 직렬화 가능."""
    spy = _Spy(master={ETF}, krx={ETF: _rows()})
    quotes = {ETF: Q(88.0, -1.0), STOCK: Q(88.0, -12.0)}
    asm = assemble_holdings_push(
        market_quotes=quotes,
        price_refresh_diag={"target_tickers": [ETF, STOCK]},
        today_kst=TODAY,
        state_path=tmp_path / "sel.json",
        slot_id="OPEN",
        runtime_kst=f"{TODAY}T09:15:00+09:00",
        holdings_loader=lambda: [H(ETF, "ETF하나"), H(STOCK, "주식하나")],
        fetch_history=_Fetch({STOCK: _rows()}),
        calendar_dir=_calendar(tmp_path),
        price_basis_source=spy.source(),
    )
    assert asm.fail is None, asm.fail
    ev = json.loads(json.dumps(asm.diagnostics["holdings_price_basis"]))
    assert ev["contract"] == "ETF_KRX_UNADJUSTED__STOCK_FDR"
    assert ev["etf_master"] == "krx_etf_basic_fixture.csv" and ev["krx_table"] == "ok"
    assert ev["tickers"][ETF] == {
        "asset_type": "ETF",
        "class_source": "etf_master_csv",
        "price_source": "KRX_OPEN_API/etf_bydd_trd",
        "price_basis": "unadjusted",
        "derived": {"base_close": "ok", "window": "ok"},
    }
    assert ev["tickers"][STOCK]["price_basis"] == "fdr_naver"


def test_runner_record_and_history_carry_price_basis(monkeypatch, tmp_path):
    """실제 `run()` — 러너가 조립 진단을 실행 기록(JSONL)에 그대로 싣는다."""
    from tests import test_intraday_alert_flow_through as ft

    db = tmp_path / "unadjusted.sqlite"
    sqlite3.connect(db).close()
    rig = ft._build_rig(monkeypatch, tmp_path, db)  # 보유 전부 ETF(KRX 표 대역)
    rig["policy"] = ft._policy(enabled=False)
    ft._hold_only(rig)
    rec = rig["runner"].run("holdings_risk_alert", "send")
    assert rec["status"] == "sent", rec
    ev = rec["risk_price_basis"]["tickers"]["H00001"]
    assert ev["price_source"] == "KRX_OPEN_API/etf_bydd_trd"
    assert ev["price_basis"] == "unadjusted" and ev["asset_type"] == "ETF"
    lines = (tmp_path / "history.jsonl").read_text(encoding="utf-8").splitlines()
    last = json.loads(lines[-1])
    assert last["risk_price_basis"] == json.loads(json.dumps(rec["risk_price_basis"]))


# ── 운영 원천(default_source) — tmp CSV · tmp DB ───────────────────────────────


def _write_master_csv(meta_dir, codes):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(EXPECTED_HEADER)
    for c in codes:
        row = [""] * len(EXPECTED_HEADER)
        row[EXPECTED_HEADER.index("단축코드")] = c
        row[EXPECTED_HEADER.index("기초지수명")] = "지수"
        w.writerow(row)
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "krx_etf_basic_20260927.csv").write_bytes(
        buf.getvalue().encode("cp949")
    )


def test_default_source_reads_master_csv_and_krx_table_read_only(tmp_path):
    meta, db = tmp_path / "meta", tmp_path / "m.sqlite"
    _write_master_csv(meta, [ETF])
    new_etf = "0099X0"  # CSV 날짜 뒤 상장 — KRX 표에만 있다
    krx_store.upsert_snapshot(
        [krx_store.SnapshotRow(d, t, 100.0) for d in PAST for t in (ETF, new_etf)],
        db_path=db,
    )
    src = hpb.default_source(meta_dir=meta, db_path=db)
    kinds, status = hpb.classify_assets([ETF, new_etf, STOCK], src)
    assert kinds == {
        ETF: ("ETF", "etf_master_csv"),
        new_etf: ("ETF", "krx_table"),
        STOCK: ("STOCK", "etf_master_csv+krx_table"),
    }
    assert status == {"etf_master": "krx_etf_basic_20260927.csv", "krx_table": "ok"}
    present, closes = src.krx_prices([ETF, STOCK], [T1, BASE])
    assert present == {ETF} and closes == {ETF: {T1: 100.0, BASE: 100.0}}


def test_read_helper_never_creates_db_or_table(tmp_path):
    """읽기 전용 — 없는 DB · 없는 표를 만들지 않고 예외로 '읽을 수 없음' 을 알린다."""
    missing = tmp_path / "none.sqlite"
    with pytest.raises(sqlite3.Error):
        krx_store.read_holdings_etf_prices([ETF], [T1], db_path=missing)
    assert not missing.exists()
    empty = tmp_path / "empty.sqlite"
    sqlite3.connect(empty).close()
    with pytest.raises(sqlite3.Error):
        krx_store.read_holdings_etf_prices([ETF], [T1], db_path=empty)
    con = sqlite3.connect(empty)
    try:
        tables = con.execute("SELECT name FROM sqlite_master").fetchall()
    finally:
        con.close()
    assert tables == []
    src = hpb.default_source(meta_dir=tmp_path / "no_meta", db_path=empty)
    kinds, status = hpb.classify_assets([ETF], src)
    assert kinds[ETF] == ("UNKNOWN", None)
    assert status["etf_master"].startswith("unreadable:")
    assert status["krx_table"] == "unreadable:OperationalError"


def test_naver_previous_close_uses_raw_ratio_and_freshness_gate():
    assert hpb.naver_previous_close(Q(94.0, -6.0), TODAY) == pytest.approx(100.0)
    assert hpb.naver_previous_close(Q(94.0, None), TODAY) is None
    stale = Q(94.0, -6.0, price_asof="2026-09-29T15:30:00+09:00")
    assert hpb.naver_previous_close(stale, TODAY) is None
    assert hpb.naver_previous_close(Q(94.0, -100.0), TODAY) is None
