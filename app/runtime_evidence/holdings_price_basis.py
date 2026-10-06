"""보유 PUSH 가격 기준 — POC3-02D-OPS-03 설계자 RESULT STEP 1(2026-09-30) · POC3-02D-OPS-04 항목 1.

선택지 (a) 확정 — 현재가와 과거 종가를 **같은 성격**으로 맞춘다.

```text
ETF 보유종목     현재가 = Naver 무조정
                 20거래일 전 종가 · 구간 종가 = KRX 무조정(`krx_etf_daily_price_unadjusted`)
                 조정계열(`etf_daily_price`) fallback 금지 · 한 종목에 두 계열을 섞지 않는다
개별주 보유종목  현재가 = Naver 무조정(정규장)
                 20거래일 전 종가 · 구간 종가 = KRX 공식 정규장 종가(`krx_stock_daily_price_unadjusted`
                 · `sto/stk_bydd_trd` · POC3-02D-OPS-04 항목 1) · FDR 일봉을 읽지 않는다
                 표를 못 읽으면 그 종목 파생값만 닫는다 · T-1 가드(KRX vs Naver 전일)는 기록만
구분 불가        파생값 fail-closed — 추측하지 않는다
```

닫는 것은 **파생값만**이다(20거래일 수익률 · 고점 대비). 실시간 급등락 · 전일 대비
판정은 Naver 등락률이라 이 모듈과 무관하게 그대로 돈다.

가격수익률이다. 분배금을 포함한 총수익률과 섞지 않는다.

개별주 이력(2026-09-30 혼합 확정 → 2026-10-04 해소) — FDR(Naver fchart) 개별주 일봉 종가는 KRX
정규장 종가가 아니었다(+0.9~+1.4% · 시간외 체결 포함 추정). 그래서 OPS-03 은 개별주 파생값을 늘
닫았다. OPS-04 항목 1(설계자 Q1 a · 사용자 승인)로 같은 성격 원천인 KRX 공식 종가를 쓰게 됐다.

ETF/개별주 구분 = 종목 마스터의 자산 유형:

```text
ETF     공식 KRX ETF 마스터(`krx_etf_basic_*.csv` 최신 유효 파일 · 08:30 시장 브리핑과 같은 resolver)에 있다
        또는 KRX 무조정 표에 적재 기록이 있다(CSV 날짜 뒤 상장)
개별주  두 원천을 모두 읽었고 어디에도 없다
미상    그 밖 — 한쪽이라도 못 읽으면 개별주라고 확정하지 않는다
```
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from app import trading_day_lag
from app.runtime_evidence.holdings_risk import usable_day_return
from app.runtime_evidence.holdings_selection import (
    LOOKBACK_TRADING_DAYS,
    close_on,
    reference_trading_day,
)
from app.runtime_evidence.holdings_selection_source import (
    history_dates,
    trading_day_axis,
)

CONTRACT = "ETF_KRX_UNADJUSTED__STOCK_KRX_UNADJUSTED"

ASSET_ETF = "ETF"
ASSET_STOCK = "STOCK"
ASSET_UNKNOWN = "UNKNOWN"

PRICE_SOURCE_KRX = "KRX_OPEN_API/etf_bydd_trd"
PRICE_BASIS_KRX = "unadjusted"
PRICE_SOURCE_KRX_STOCK = "KRX_OPEN_API/stk_bydd_trd"

CLASS_CSV = "etf_master_csv"
CLASS_KRX_TABLE = "krx_table"
CLASS_BOTH_ABSENT = "etf_master_csv+krx_table"

REASON_UNKNOWN = "asset_type_unknown"
REASON_KRX_UNREADABLE = "krx_unreadable"
REASON_KRX_STOCK_UNREADABLE = "krx_stock_unreadable"

# 개별주 T-1 가드 허용 폭(%) — 설계자 RESULT STEP 1-6 · 1-7. 가드는 기록용이다(파생값을 막지 않는다).
MISMATCH_TOLERANCE_PCT = 0.5

# 연도 파일이 없는 해에는 저장 자료가 없는 평일을 휴장으로 건너뛰어 축이 앞쪽으로 늘어난다
# (한국 거래일 계약 2026-09-11 · `trading_day_lag` `stored`). 그만큼 KRX 종가를 앞쪽까지
# 읽어 둔다 — 설 · 추석 연휴(대체 포함)를 넉넉히 덮는다.
FETCH_EXTRA_TRADING_DAYS = 10

# 시장 브리핑과 같은 폴더 · 같은 resolver(`runner_market_briefing.MARKET_META_DIR`).
DEFAULT_META_DIR = Path("state/market_meta")


@dataclass(frozen=True)
class PriceBasisSource:
    """구분 · KRX 종가 원천. 운영은 `default_source()`, 테스트는 tmp 원천을 넣는다.

    세 함수 모두 못 읽으면 예외를 올린다 — 여기서 '읽을 수 없음' 으로 기록한다.
    `stock_prices` 가 없으면(옛 대역) 개별주 표를 읽을 수 없는 것으로 본다.
    """

    etf_master: Callable[[], tuple[frozenset[str], str]]
    krx_prices: Callable[..., tuple[set[str], dict[str, dict[str, float]]]]
    stock_prices: Optional[
        Callable[..., tuple[set[str], dict[str, dict[str, float]]]]
    ] = None


def default_source(
    *, meta_dir: Optional[Path] = None, db_path: Optional[Path] = None
) -> PriceBasisSource:
    """운영 원천 — 공식 ETF 마스터 CSV · KRX 무조정 ETF 표 · KRX 개별주 표(읽기 전용)."""

    def _master() -> tuple[frozenset[str], str]:
        from app.market_briefing.official_csv import resolve_official_csv

        sel = resolve_official_csv(meta_dir or DEFAULT_META_DIR)
        if not sel.ok:
            raise LookupError(sel.error or "no_valid_file")
        codes = {(r.get("단축코드") or "").strip() for r in sel.records}
        return frozenset(codes - {""}), sel.name or ""

    def _krx(tickers: Sequence[str], dates: Sequence[str] = ()):
        from app.market_briefing.krx_store import read_holdings_etf_prices

        return read_holdings_etf_prices(tickers, dates, db_path=db_path)

    def _stock(tickers: Sequence[str], dates: Sequence[str] = ()):
        from app.market_briefing.krx_stock_store import read_holdings_stock_prices

        return read_holdings_stock_prices(tickers, dates, db_path=db_path)

    return PriceBasisSource(etf_master=_master, krx_prices=_krx, stock_prices=_stock)


@dataclass
class BasisHistory:
    """흐름이 쓸 가격 이력 · 거래일 축 · 실행 기록 evidence."""

    history: dict[str, list[tuple[str, float]]] = field(default_factory=dict)
    axis: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


def naver_previous_close(quote: Any, today_kst: Optional[str]) -> Optional[float]:
    """Naver 가 쓴 전일 종가(무조정) = 현재가 ÷ (1 + 등락률). 못 구하면 None.

    최신성 · 값 검사는 급등락 판정과 같은 게이트(`usable_day_return`)다. 가드에만
    쓴다 — 판정 등락률을 현재가로 역산하지 않는다는 §13-2 계약은 그대로다.
    """
    if usable_day_return(quote, today_kst) is None:
        return None
    try:
        ratio = 1.0 + float(quote.day_return_pct) / 100.0
        current = float(quote.current_price)
    except (AttributeError, TypeError, ValueError):
        return None
    if ratio <= 0 or current <= 0:
        return None
    return current / ratio


def _unreadable(e: Exception) -> str:
    return f"unreadable:{type(e).__name__}"


def classify_assets(
    tickers: Sequence[str], source: PriceBasisSource
) -> tuple[dict[str, tuple[str, Optional[str]]], dict[str, str]]:
    """`({ticker: (자산 유형, 구분 원천)}, 원천 상태)`. 모듈 docstring 표 그대로."""
    status: dict[str, str] = {}
    try:
        master, name = source.etf_master()
        status["etf_master"] = name
    except Exception as e:  # noqa: BLE001 - 못 읽으면 미상으로 닫는다
        master = None
        status["etf_master"] = _unreadable(e)
    rest = [t for t in tickers if master is None or t not in master]
    present: Optional[set[str]] = set()
    if rest:
        try:
            present, _ = source.krx_prices(rest, ())
            status["krx_table"] = "ok"
        except Exception as e:  # noqa: BLE001
            present = None
            status["krx_table"] = _unreadable(e)
    out: dict[str, tuple[str, Optional[str]]] = {}
    for t in tickers:
        if master is not None and t in master:
            out[t] = (ASSET_ETF, CLASS_CSV)
        elif present is not None and t in present:
            out[t] = (ASSET_ETF, CLASS_KRX_TABLE)
        elif master is not None and present is not None:
            out[t] = (ASSET_STOCK, CLASS_BOTH_ABSENT)
        else:
            out[t] = (ASSET_UNKNOWN, None)
    return out, status


def _stock_guard(
    rows: list[tuple[str, float]], quote: Any, t1: Optional[str], today_kst
) -> dict[str, Any]:
    """KRX 공식 캘린더 T-1 종가 vs Naver 전일 종가 — 그날 차이 기록(파생값을 막지 않는다)."""
    krx = close_on(rows, t1)
    naver = naver_previous_close(quote, today_kst)
    diff = None
    if krx and naver:
        diff = round((krx / naver - 1.0) * 100.0, 3)
    return {
        "t1": t1,
        "krx_close": krx,
        "naver_prev_close": None if naver is None else round(naver, 2),
        "diff_pct": diff,
        "ok": diff is not None and abs(diff) <= MISMATCH_TOLERANCE_PCT,
    }


def _derived(
    rows: list[tuple[str, float]], axis: list[str], today_kst: Optional[str]
) -> dict[str, str]:
    """파생값 재료 상태 — 기준일 종가 · 20거래일 구간 종가."""
    have = {d[:10] for d, _ in rows}
    base = reference_trading_day(axis, today_kst, LOOKBACK_TRADING_DAYS)
    missing = sum(1 for d in axis if d not in have)
    return {
        "base_close": "ok" if base and base in have else "missing",
        "window": "ok" if axis and not missing else f"missing:{missing or 'axis'}",
    }


def _fetch_days(raw_axis: list[str], calendar_dir: Optional[Path]) -> list[str]:
    """KRX 종가를 읽을 날짜 — 평일 기본 축 + 앞쪽 여유(`FETCH_EXTRA_TRADING_DAYS`)."""
    if not raw_axis:
        return []
    return trading_day_lag.trading_days_ending(
        raw_axis[-1],
        len(raw_axis) + FETCH_EXTRA_TRADING_DAYS,
        calendar_dir=calendar_dir,
    )


def load_basis_history(
    tickers: Sequence[str],
    *,
    fetch_history: Callable[..., list[tuple[str, float]]],
    market_quotes: dict[str, Any],
    today_kst: Optional[str],
    calendar_dir: Optional[Path] = None,
    source: Optional[PriceBasisSource] = None,
) -> BasisHistory:
    """자산 유형별 가격 이력 · 캘린더 거래일 축 · evidence.

    파생값을 닫는 종목은 이력을 비운다 — 선정기가 기준일 종가 없음(`20거래일
    데이터 확인 불가`) · 보조값 생략으로 처리한다. ETF · 개별주 모두 KRX 무조정 표를
    읽는다(표를 못 읽으면 그 종목만 닫는다). `fetch_history`(FDR)는 POC3-02D-OPS-04
    항목 1 부터 읽지 않는다 — 호출자 서명(POC5-01A 경계)을 바꾸지 않으려고 인자는 둔다.
    """
    src = source or default_source()
    raw_axis = trading_day_axis(today_kst, calendar_dir=calendar_dir)
    fetch_days = _fetch_days(raw_axis, calendar_dir)
    kinds, status = classify_assets(tickers, src)
    etfs = [t for t in tickers if kinds[t][0] == ASSET_ETF]
    stocks = [t for t in tickers if kinds[t][0] == ASSET_STOCK]

    krx: Optional[dict[str, dict[str, float]]] = {}
    if etfs and raw_axis:
        try:
            _, krx = src.krx_prices(etfs, fetch_days)
            status["krx_table"] = "ok"
        except Exception as e:  # noqa: BLE001 - ETF 파생값만 닫는다
            krx = None
            status["krx_table"] = _unreadable(e)
    krx_stock: Optional[dict[str, dict[str, float]]] = {}
    if stocks and raw_axis:
        try:
            if src.stock_prices is None:
                raise LookupError("no_stock_source")
            _, krx_stock = src.stock_prices(stocks, fetch_days)
            status["krx_stock_table"] = "ok"
        except Exception as e:  # noqa: BLE001 - 개별주 파생값만 닫는다
            krx_stock = None
            status["krx_stock_table"] = _unreadable(e)

    history: dict[str, list[tuple[str, float]]] = {}
    per: dict[str, dict[str, Any]] = {}
    t1 = raw_axis[-1] if raw_axis else None
    for t in tickers:
        kind, cls = kinds[t]
        rows: list[tuple[str, float]] = []
        item: dict[str, Any] = {"asset_type": kind, "class_source": cls}
        if kind == ASSET_ETF:
            item.update(price_source=PRICE_SOURCE_KRX, price_basis=PRICE_BASIS_KRX)
            if krx is None:
                item["reason"] = REASON_KRX_UNREADABLE
            else:
                closes = krx.get(t) or {}
                rows = [(d, closes[d]) for d in fetch_days if d in closes]
        elif kind == ASSET_STOCK:
            item.update(
                price_source=PRICE_SOURCE_KRX_STOCK, price_basis=PRICE_BASIS_KRX
            )
            if krx_stock is None:
                item["reason"] = REASON_KRX_STOCK_UNREADABLE
            else:
                closes = krx_stock.get(t) or {}
                rows = [(d, closes[d]) for d in fetch_days if d in closes]
                # 가드는 그날 KRX 종가와 Naver 전일 종가의 차이 기록(파생값을 막지 않는다).
                item["guard"] = _stock_guard(rows, market_quotes.get(t), t1, today_kst)
        else:
            item.update(price_source=None, price_basis=None, reason=REASON_UNKNOWN)
        history[t] = rows
        per[t] = item

    # 평일 fallback 해의 거래일 확인 근거 — ETF · 개별주 KRX 저장 날짜.
    stored = history_dates(history)
    axis = trading_day_axis(today_kst, calendar_dir=calendar_dir, stored_dates=stored)
    for t, item in per.items():
        if "reason" in item:
            item["derived"] = {"base_close": "blocked", "window": "blocked"}
        else:
            item["derived"] = _derived(history[t], axis, today_kst)
    evidence = {"contract": CONTRACT, **status, "tickers": per}
    return BasisHistory(history=history, axis=axis, evidence=evidence)


__all__ = [
    "ASSET_ETF",
    "ASSET_STOCK",
    "ASSET_UNKNOWN",
    "BasisHistory",
    "CONTRACT",
    "MISMATCH_TOLERANCE_PCT",
    "PRICE_BASIS_KRX",
    "PRICE_SOURCE_KRX",
    "PRICE_SOURCE_KRX_STOCK",
    "PriceBasisSource",
    "REASON_KRX_STOCK_UNREADABLE",
    "REASON_KRX_UNREADABLE",
    "REASON_UNKNOWN",
    "classify_assets",
    "default_source",
    "load_basis_history",
    "naver_previous_close",
]
