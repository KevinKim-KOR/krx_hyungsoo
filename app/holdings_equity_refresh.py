"""POC5-10 — PC 수동 갱신의 보유 개별주 가격 단계 (PLAN `POC5-10_..._PLAN_V1.md` §2 · §6).

PC `POST /market/refresh` 는 ETF 목록(`etf_master`)만 받아, 보유 중인 개별주 가격이 멈춰 있었다
(`DEF-PRICE-EQUITY-REFRESH` · 2026-08-12). 이 모듈은 그 갱신 작업 안에서 한 단계로 불려
'보유 − ETF 목록' 종목만 OCI 배치와 같은 증분 함수로 받는다. PC 전용 · OCI 실행 경로 변경 0.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from app import holdings as holdings_module
from app.market_data_fdr import (
    DEFAULT_LOOKBACK_DAYS,
    FDR_SOURCE,
    PriceFetcher,
    _dataframe_to_price_rows,
    _default_price_fetcher,
)
from app.market_data_store import (
    HOLDINGS_EQUITY_PRICE_LOG_SOURCE,
    get_last_price_date,
    list_etf_tickers,
    log_refresh,
    normalize_ticker_list,
    upsert_daily_prices,
)

logger = logging.getLogger(__name__)

# POC5-10 — 보유 개별주 가격 단계(별도 로그 행 · ETF 건수와 합치지 않음 · 설계 POC5-09 §10-4).
HOLDINGS_EQUITY_LOG_SOURCE = HOLDINGS_EQUITY_PRICE_LOG_SOURCE
HOLDINGS_READ_FAILED_TEXT = "보유 목록을 읽지 못해 개별주 가격을 갱신하지 못했습니다"
HOLDINGS_EQUITY_STEP_FAILED_TEXT = "보유 개별주 가격을 갱신하지 못했습니다"


def _holdings_equity_fail_text(fail: int, attempted: int) -> str:
    if fail >= attempted:
        return f"보유 개별주 가격 갱신 실패({fail}종목)"
    return f"보유 개별주 가격 갱신 일부 실패({fail}종목)"


@dataclass
class _FetchResult:
    success: int
    failure_examples: list[dict] = field(default_factory=list)


def _fetch_and_store_without_log(price_fetcher: Optional[PriceFetcher]):
    """`refresh_approved_prices` 에 넘길 수집 · 저장 함수 — 종목별 기록 행을 남기지 않는다.

    공유 `refresh_price_history` 와 같은 조각(fetcher · 행 변환 · upsert · 출처 FinanceDataReader)을 쓰되
    호출마다 `market_refresh_log` 행(출처 'FinanceDataReader/prices' · 시도 1)을 쓰지 않는다. 그 행이
    ETF 가격 행과 구분되지 않아 '마지막 전체 갱신'을 대신할 수 있어서다(검증자 r1). 이 단계의 기록은
    요약 행 하나(`HOLDINGS_EQUITY_PRICE_LOG_SOURCE`)뿐이다.
    """
    fetch = price_fetcher or _default_price_fetcher

    def run(
        tickers,
        *,
        end_date: date,
        db_path: Path,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ):
        start = end_date - timedelta(days=lookback_days)
        success = 0
        failures: list[dict] = []
        for tk in normalize_ticker_list(tickers):
            try:
                df = fetch(tk, start, end_date)
            except Exception as e:  # noqa: BLE001 — 종목 단위 격리(공유 함수와 같음)
                failures.append(
                    {"ticker": tk, "error": f"{type(e).__name__}: {e}"[:160]}
                )
                continue
            rows = _dataframe_to_price_rows(tk, df)
            if not rows:
                failures.append({"ticker": tk, "error": "no_data"})
                continue
            try:
                upsert_daily_prices(rows, source=FDR_SOURCE, db_path=db_path)
                success += 1
            except Exception as e:  # noqa: BLE001
                failures.append(
                    {"ticker": tk, "error": f"store: {type(e).__name__}: {e}"[:160]}
                )
        return _FetchResult(success=success, failure_examples=failures[:5])

    return run


def refresh_holdings_equity_prices(
    *,
    refresh_id: str,
    end_date: date,
    db_path: Path,
    price_fetcher: Optional[PriceFetcher],
) -> Optional[str]:
    """POC5-10 — 보유 중이지만 ETF 목록(`etf_master`)에 없는 종목(개별주)의 가격을 받는다.

    - 대상 = 현재 보유 − `etf_master`(중복 없음 · 입력 순서). 개별주를 `etf_master` 에 넣지 않는다.
    - 수집 = OCI 배치와 같은 `refresh_approved_prices`(종목마다 마지막 저장일부터 끝 날짜까지 증분 ·
      공유 함수 본문 변경 0). 같은 갱신 작업의 `end_date` · PC DB · 가격 fetcher 를 넘긴다.
    - 성공 = 그 종목 수집이 행을 저장했고 유효 종가가 있는 종목(종목마다 직접 센다). 공유 함수의
      success / fail 은 수집 실패 · 저장 행 없음 종목을 두 번 세며 다른 종목의 성공까지 깎을 수 있어
      쓰지 않는다.
    - 기록 = 요약 행 하나. 종목별 수집 기록 행은 남기지 않는다(`_fetch_and_store_without_log`).
    - 결과 = `market_refresh_log` 별도 행 `holdings-equity-prices-<refresh_id>`(기술 사유는 이 행에만 ·
      기록 실패는 결과 문구를 바꾸지 않는다).
    - 보유를 읽지 못하면(파일 없음 · 손상 · 형식 오류) 빈 보유로 바꾸지 않고 실패로 기록한다
      (`holdings.load()` 는 파일 없음을 빈 목록으로 돌려주므로 파일 존재를 먼저 본다 · OCI 배치와 같음).
      유효한 빈 보유(파일 있음 · 0행)와 대상 0 은 정상 '대상 없음'이다.
    - 돌려주는 값 = 화면 `error_summary` 에 붙일 한국어 문구(실패 때만) · 성공 · 대상 없음 = None.
    """
    run_id = f"holdings-equity-prices-{refresh_id}"
    asof = end_date.isoformat()
    t0 = time.perf_counter()

    def _log(attempted: int, success: int, fail: int, tech: Optional[str]) -> None:
        try:
            log_refresh(
                run_id=run_id,
                source=HOLDINGS_EQUITY_LOG_SOURCE,
                asof=asof,
                attempted=attempted,
                success=success,
                fail=fail,
                runtime_seconds=round(time.perf_counter() - t0, 3),
                error_summary=tech,
                db_path=db_path,
            )
        except Exception:  # noqa: BLE001 — 기록 실패가 수집 결과 문구를 바꾸지 않게
            logger.exception("holdings equity log write failed")

    try:
        if not holdings_module.HOLDINGS_FILE.exists():
            raise FileNotFoundError(str(holdings_module.HOLDINGS_FILE))
        held = holdings_module.load()
    except Exception as e:  # noqa: BLE001 — 없음 · 손상 · 형식 오류 모두 '읽기 실패'
        _log(0, 0, 0, f"holdings_read_failed: {type(e).__name__}: {e}"[:200])
        return HOLDINGS_READ_FAILED_TEXT

    targets: list[str] = []
    succeeded: set[str] = set()
    tech: Optional[str] = None
    try:
        from app.three_push_runtime.market_data_batch import refresh_approved_prices

        etf = set(list_etf_tickers(db_path))
        for h in held:
            t = h.ticker
            if t and t not in etf and t not in targets:
                targets.append(t)
        if targets:
            base = _fetch_and_store_without_log(price_fetcher)

            def _tracked(tickers, **kwargs):
                res = base(tickers, **kwargs)
                if getattr(res, "success", 0):
                    succeeded.update(tickers)
                return res

            r = refresh_approved_prices(
                targets, end_date=end_date, db_path=db_path, refresh_fn=_tracked
            )
            if r.failures:
                tech = "; ".join(
                    f"{f.get('ticker')}:{str(f.get('error'))[:48]}"
                    for f in r.failures[:5]
                )
    except (
        Exception
    ) as e:  # noqa: BLE001 — 이 단계 실패로만(남은 종목 결과는 아래 재확인)
        tech = f"step_failed: {type(e).__name__}: {e}"[:200]
        if not targets:
            _log(0, 0, 0, tech)
            return HOLDINGS_EQUITY_STEP_FAILED_TEXT

    ok = {
        t
        for t in succeeded
        if get_last_price_date(t, db_path=db_path, require_valid_close=True)
    }
    attempted, success = len(targets), len(ok)
    fail = attempted - success
    _log(attempted, success, fail, tech)
    return _holdings_equity_fail_text(fail, attempted) if fail > 0 else None
