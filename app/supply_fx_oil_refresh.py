"""POC6-01 — PC 시장 갱신('최신 시장 데이터 갱신')의 시장 흐름 단계(원/달러 · WTI · 코스피 투자자별 수급).

PC 갱신(`app/market_refresh_service.py`)이 NAV 단계 뒤에서 부른다. 화면 조회 · 기간 변경 · 복사 ·
미리보기는 외부를 부르지 않는다(설계 §5). 단계마다 따로 격리하고, 실패해도 다른 단계 · 전체 판정은 그대로다.

- 받는 범위(PLAN 판정 §4-1):
  - 처음(저장 행 없음) = 올해 1/1 이전 60 한국 거래일(저장 코스피 거래일로 셈)부터.
  - 이후 = 환율 · WTI 최근 90일 · 수급 최근 20 한국 거래일을 겹쳐 받아 같은 계열의 원천 정정을 반영 +
    빠진 날. 성공한 응답만 넣고, 실패 · 결측으로 덮거나 기존 행을 지우지 않는다.
- 오늘(한국 날짜) 수급은 저장하지 않는다(제공 시각 이전 잠정값 · 판정 §1 · PLAN §9-8). 환율 · WTI 의 진행
  중 봉은 어댑터가 뺀다(`app/yahoo_daily_series.py`).
- 수급 각 날짜는 키움 응답의 지수값이 그날 저장 코스피 종가와 같아야 저장한다(범위 · 날짜 섞임 = 실패).
  인증 실패면 바로 멈추고, 날짜 조회가 연달아 3번 실패해도 멈춘다(차단 회피 · 재로그인 반복 없음).
- 기록: `market_refresh_log` 에 단계별 행 하나(출처 `FX_WTI_LOG_SOURCE` · `FLOW_LOG_SOURCE` · '마지막 전체
  갱신' 조회에서는 뺀다). 화면용 한국어 문구는 완료 사유 끝에 붙인다. 키 · 토큰은 어디에도 남기지 않는다.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from app.config import optional_env
from app.kiwoom_investor_flow import KiwoomAuthError, KiwoomClient, KiwoomFlowError
from app.market_data_store import log_refresh
from app.supply_fx_oil_store import (
    FLOW_LOG_SOURCE,
    FX_WTI_LOG_SOURCE,
    MACRO_SERIES,
    USDKRW,
    WTI,
    read_benchmark_series,
    read_investor_flows,
    read_macro_series,
    upsert_investor_flows,
    upsert_macro_daily,
)
from app.yahoo_daily_series import fetch_completed_daily

logger = logging.getLogger(__name__)

MARKET_FLOW_STEP_FAILED_TEXT = (
    "시장 흐름 자료(수급 · 환율 · 유가)를 갱신하지 못했습니다"
)
PREP_TRADING_DAYS = 60
MACRO_OVERLAP_DAYS = 90
FLOW_OVERLAP_TRADING_DAYS = 20
MAX_FLOW_CALLS = 400
MAX_CONSECUTIVE_FAILS = 3
FLOW_TIME_BUDGET_S = (
    180  # 수급 조회 전체 상한(화면 갱신 대기 8분 안 · 첫 수집 실측 81초)
)
CALL_GAP_S = 0.25
CLOSE_TOLERANCE = 0.005  # 지수 소수 둘째 자리
KST = timezone(timedelta(hours=9))
YAHOO_SYMBOL = {USDKRW: "KRW=X", WTI: "CL=F"}
SERIES_LABEL = {USDKRW: "원/달러", WTI: "WTI"}


def collection_start(kospi_dates: list[str], today_kst: date) -> date:
    """첫 수집 시작일 = 올해 1/1 이전 60 거래일째(저장 코스피 달력). 모자라면 1/1 의 100일 전."""
    before = [d for d in kospi_dates if d < date(today_kst.year, 1, 1).isoformat()]
    if len(before) >= PREP_TRADING_DAYS:
        return date.fromisoformat(before[-PREP_TRADING_DAYS])
    return date(today_kst.year, 1, 1) - timedelta(days=100)


def refresh_fx_wti(
    *,
    db_path: Path,
    now_utc: datetime,
    start: date,
    http_get: Optional[Callable] = None,
    capture: Optional[Any] = None,
) -> list[str]:
    """원/달러 · WTI. 돌려주는 값 = 실패한 계열 이름(성공이면 빈 목록).

    `capture`(POC6-05 OCI 수집만 · PC 갱신은 None = 기존 동작 그대로)가 있으면 받은 행을 **표에 쓰기 전에**
    보관한다. 보관이 실패하면 그 계열은 upsert 하지 않는다(계열마다 격리 그대로).
    """
    failed = []
    today = now_utc.astimezone(KST).date()
    for sid, symbol in YAHOO_SYMBOL.items():
        have, _ = read_macro_series(sid, db_path=db_path)
        # 처음 = 시작일부터 · 이후 = 최근 90일 겹쳐 받기. 마지막 저장일이 90일보다 오래됐으면(갱신을 오래
        # 안 했거나 계속 실패) 그 다음 날부터 다시 받아 구멍을 남기지 않는다.
        since = (
            start
            if not have
            else max(
                start,
                min(
                    date.fromisoformat(have[-1][0]) + timedelta(days=1),
                    today - timedelta(days=MACRO_OVERLAP_DAYS),
                ),
            )
        )
        try:
            rows = fetch_completed_daily(
                symbol, since, now_utc=now_utc, http_get=http_get
            )
            if capture is not None:
                capture.fx_received(sid, rows, since)
            unit, provider, basis = MACRO_SERIES[sid]
            upsert_macro_daily(
                series_id=sid,
                rows=rows,
                unit=unit,
                provider=provider,
                basis=basis,
                db_path=db_path,
            )
            logger.info("market flow %s ok: %d rows since %s", sid, len(rows), since)
        except Exception as e:  # noqa: BLE001 — 계열마다 격리
            logger.warning("market flow %s failed: %s", sid, type(e).__name__)
            failed.append(SERIES_LABEL[sid])
            if capture is not None:
                capture.fx_fail(sid, type(e).__name__)
    return failed


def refresh_investor_flows(
    *,
    db_path: Path,
    now_utc: datetime,
    start: date,
    client: Optional[KiwoomClient] = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    capture: Optional[Any] = None,
) -> Optional[str]:
    """코스피 투자자별 순매수. 돌려주는 값 = 실패 사유(한국어 · 성공이면 None).

    `capture`(POC6-05 · 기본 None = PC 동작 그대로)는 조회 계획 · 날짜별 받은 값(표 반영 전) · 실패 사유 ·
    멈춘 사유를 받는다. 받은 값 보관이 실패한 날짜는 실패로 세고 upsert 하지 않는다.

    최신 날짜부터 조회한다 — 오래된 날짜가 계속 실패해도 새 날짜는 받는다(연속 3회 실패 멈춤 · 호출 상한 ·
    시간 상한에 걸려도 남는 것은 오래된 날짜). 남은 날짜는 다음 갱신의 '빠진 날'로 다시 조회된다.
    """
    if client is None:
        key, secret = optional_env("KIWOOM_APP_KEY", None), optional_env(
            "KIWOOM_APP_SECRET", None
        )
        if not key or not secret:
            return "투자자 수급(키움 인증 정보 없음)"
        client = KiwoomClient(key, secret)
    today = now_utc.astimezone(KST).date().isoformat()
    kospi = {
        d: c
        for d, c in read_benchmark_series("KOSPI", db_path=db_path)
        if start.isoformat() <= d < today
    }
    days = sorted(kospi)
    flows, _ = read_investor_flows(db_path=db_path)
    have = {d for d, _ in flows.get("foreign", [])}
    want = sorted(
        {d for d in days if d not in have} | set(days[-FLOW_OVERLAP_TRADING_DAYS:]),
        reverse=True,
    )[:MAX_FLOW_CALLS]
    if capture is not None:
        capture.flow_planned(want)
    rows: list[tuple[str, str, int]] = []
    fails = consecutive = 0
    auth_failed = timed_out = False
    deadline = clock() + FLOW_TIME_BUDGET_S
    for i, d in enumerate(want):
        if i:
            sleep(CALL_GAP_S)
        if clock() > deadline:
            timed_out = True
            break
        try:
            nets, index_close = client.kospi_net_by_investor(d)
            if abs(index_close - kospi[d]) > CLOSE_TOLERANCE:
                raise KiwoomFlowError(
                    f"{d} 지수값 {index_close} ≠ 저장 코스피 {kospi[d]}"
                )
            if capture is not None:
                capture.flow_received(d, nets, index_close)
            rows += [(d, inv, net) for inv, net in nets.items()]
            consecutive = 0
        except KiwoomAuthError as e:
            logger.warning("market flow investor auth failed: %s", e)
            auth_failed = True
            if capture is not None:
                capture.flow_failed(d, "인증 실패")
            break
        except KiwoomFlowError as e:
            fails += 1
            consecutive += 1
            logger.warning("market flow investor %s failed: %s", d, e)
            if capture is not None:
                capture.flow_failed(d, str(e)[:160])
            if consecutive >= MAX_CONSECUTIVE_FAILS:
                break
        except Exception as e:  # noqa: BLE001 — 연결 · 시간 초과
            fails += 1
            consecutive += 1
            logger.warning("market flow investor %s failed: %s", d, type(e).__name__)
            if capture is not None:
                capture.flow_failed(d, type(e).__name__)
            if consecutive >= MAX_CONSECUTIVE_FAILS:
                break
    if capture is not None:
        stop = None
        if auth_failed:
            stop = "인증 실패"
        elif timed_out:
            stop = f"시간 제한 {FLOW_TIME_BUDGET_S}초"
        elif consecutive >= MAX_CONSECUTIVE_FAILS:
            stop = f"연속 실패 {MAX_CONSECUTIVE_FAILS}회"
        capture.flow_stopped(stop)
    if rows:
        upsert_investor_flows(rows=rows, db_path=db_path)
    done = len({d for d, _, _ in rows})
    logger.info(
        "market flow investor: %d/%d dates stored · failed %d", done, len(want), fails
    )
    if auth_failed:
        return "투자자 수급(키움 인증 실패 — 등록 IP · 앱키 확인)"
    if timed_out:
        return f"투자자 수급(시간 제한 {FLOW_TIME_BUDGET_S}초 · {done}/{len(want)}일)"
    if done < len(want):
        return f"투자자 수급({done}/{len(want)}일)"
    return None


def refresh_market_flow(
    *,
    db_path: Path,
    now_utc: datetime,
    refresh_id: str,
    asof: str,
    http_get: Optional[Callable] = None,
    client: Optional[KiwoomClient] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Optional[str]:
    """두 하위 단계를 돌리고 기록 행을 남긴다. 성공이면 None, 아니면 화면용 한국어 문구."""
    today = now_utc.astimezone(KST).date()
    start = collection_start(
        [d for d, _ in read_benchmark_series("KOSPI", db_path=db_path)], today
    )
    problems: list[str] = []
    for source, label, name, run in (
        (
            FX_WTI_LOG_SOURCE,
            "fxwti",
            "원/달러 · WTI",
            lambda: refresh_fx_wti(
                db_path=db_path, now_utc=now_utc, start=start, http_get=http_get
            ),
        ),
        (
            FLOW_LOG_SOURCE,
            "flow",
            "투자자 수급",
            lambda: refresh_investor_flows(
                db_path=db_path,
                now_utc=now_utc,
                start=start,
                client=client,
                sleep=sleep,
            ),
        ),
    ):
        t0 = time.perf_counter()
        try:
            out = run()
            bad = out if isinstance(out, list) else ([out] if out else [])
        except Exception:  # noqa: BLE001 — 하위 단계마다 격리
            logger.exception("market flow %s step failed", label)
            bad = [f"{name}(오류)"]
        problems += bad
        try:
            log_refresh(
                run_id=f"market-flow-{label}-{refresh_id}",
                source=source,
                asof=asof,
                attempted=1,
                success=0 if bad else 1,
                fail=1 if bad else 0,
                runtime_seconds=round(time.perf_counter() - t0, 3),
                error_summary=", ".join(bad)[:200] or None,
                db_path=db_path,
            )
        except Exception:  # noqa: BLE001 — 기록 실패도 갱신을 멈추지 않는다
            logger.exception("market flow log failed")
    if not problems:
        return None
    return f"시장 흐름 자료 일부를 갱신하지 못했습니다({' · '.join(problems)})"
