"""POC6-05 — 국내 단계: ETF 목록 · 네이버/FDR 120일 수신 창(OCI 일일 수집 · DB 쓰기 0 · 판정 Q2).

PC 가격 조회와 같은 원천 · 변환을 쓴다(`market_data_fdr._default_universe_fetcher` · `_default_price_fetcher` ·
`_dataframe_to_price_rows` · `_is_request_timeout` ·
`three_push_runtime.market_data_batch.fdr_request_timeout`).

멈춤 규칙(판정 Q4 · §5):
- 요청이 끝날 때마다 0.25초 쉼(POC6-01 `CALL_GAP_S`) · 요청 상한 20초 · 연속 시간 초과 5회(PC 규칙과 같은 값).
- 종류 무관 연속 실패 20회 · 명확한 HTTP 403/429 는 즉시 멈춤(예외 응답 또는 빈 응답 + 마지막 HTTP 상태).
  성공하면 연속 수를 0 으로.
- 30분 = 새 요청을 시작하지 않는 시간 예산(대기 전후 확인 · DNS · 느린 응답까지 끊는 강제 종료 보장 아님).
- 남은 종목은 '미시도 · 사유'. 자동 재시도 · 새 접속 방식 없음.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Iterator, Optional

from app.market_data_fdr import (
    DEFAULT_LOOKBACK_DAYS,
    _dataframe_to_price_rows,
    _is_request_timeout,
)
from app.ml_evidence.store import canonical, iso, sha256_bytes
from app.supply_fx_oil_refresh import CALL_GAP_S

OK, NO_NEW_ROW, FAILED, NOT_ATTEMPTED = "OK", "NO_NEW_ROW", "FAILED", "NOT_ATTEMPTED"
MIN_ROWS = (
    61  # feature 계산에 필요한 축 날짜 수(06 LB 60 + 1) — 미달은 관측 창 부족 표시일 뿐
)
LIST_MIN_RATIO = 0.95
LIST_SOURCE = (
    "FinanceDataReader StockListing('ETF/KR') = 네이버 ETF 목록(분류 = 네이버 탭 코드)"
)
PRICE_SEMANTICS = (
    "NAVER_FDR 수신 창 · 수정주가 · 총수익 · 당시 가용(PIT) 보증 아님 · change = 같은 응답 종가로 계산"
    "(독립 품질 근거 아님) · 공급자가 전체 이력을 준 뒤 120일로 자름 · 오늘 KST 날짜 이상 행 = 진행 중 봉으로 뺌"
)


@dataclass(frozen=True)
class Limits:
    gap_s: float = CALL_GAP_S
    budget_s: float = 30 * 60
    timeout_streak: int = (
        5  # = app.market_refresh_service.PRICE_TIMEOUT_STOP_STREAK(시험으로 같음 확인)
    )
    fail_streak: int = 20


def normalize_listing(df) -> list[dict]:
    """목록 응답 → [{ticker, name, category}] (6자리 · 종목코드 순 · 중복 제거)."""
    if df is None or len(df) == 0 or "Symbol" not in df.columns:
        return []
    out: dict[str, dict] = {}
    for _, raw in df.iterrows():
        t = str(raw["Symbol"]).strip().zfill(6)
        if len(t) != 6 or not t.isalnum():
            continue
        name = raw["Name"] if "Name" in raw and raw["Name"] is not None else None
        cat = (
            raw["Category"]
            if "Category" in raw and raw["Category"] is not None
            else None
        )
        out[t] = {
            "ticker": t,
            "name": None if name is None else str(name),
            "category": None if cat is None else str(cat),
        }
    return [out[t] for t in sorted(out)]


def list_hash(rows: list[dict]) -> str:
    return sha256_bytes(canonical(rows))


def judge_list(
    response: Optional[list[dict]], error: Optional[str], prev_count: Optional[int]
) -> Optional[str]:
    """새 목록을 쓰지 못하는 사유(쓸 수 있으면 None). 95% 규칙 = 응답 급감의 임시 보류(상장폐지 확정 아님)."""
    if error:
        return f"목록 조회 실패({error})"
    if not response:
        return "목록 응답이 비어 있음"
    if prev_count and len(response) < LIST_MIN_RATIO * prev_count:
        return (
            f"목록이 직전의 95% 미만({len(response)} < {prev_count} × 0.95) — 임시 보류"
        )
    return None


def _blocked(exc: BaseException) -> Optional[int]:
    code = getattr(getattr(exc, "response", None), "status_code", None)
    return code if code in (403, 429) else None


@contextmanager
def last_http_status() -> Iterator[dict]:
    """이 블록 안 `requests` 응답의 마지막 HTTP 상태를 적는다(FDR 네이버 경로는 403 을 빈 표로 돌려준다).

    `fdr_request_timeout` 과 같은 방식(블록 안에서만 `Session.request` 를 감싸고 끝나면 되돌림)이다.
    """
    box: dict = {"status": None}
    try:
        import requests
    except ImportError:  # pragma: no cover - FDR 의존성으로 늘 설치됨
        yield box
        return
    original = requests.Session.request

    def _request(self, *args, **kwargs):
        r = original(self, *args, **kwargs)
        box["status"] = getattr(r, "status_code", None)
        return r

    requests.Session.request = _request
    try:
        yield box
    finally:
        requests.Session.request = original


def fetch_windows(
    tickers: list[str],
    *,
    writer,
    target_day: str,
    today_kst: date,
    fetcher: Callable,
    request_timeout: Callable,
    now: Callable,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
    limits: Limits = Limits(),
    attempt_limit: Optional[int] = None,
    status_probe: Callable = last_http_status,
) -> dict:
    """종목마다 한 줄씩 writer 에 흘려 쓴다. 돌려주는 값 = 집계 · 미확보 종목 · 멈춘 사유.

    요청이 끝날 때마다 0.25초 쉰다(POC6-01 `CALL_GAP_S` 와 같은 뜻). `observed_at` = 응답을 받은 시각.
    """
    start = today_kst - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    today = today_kst.isoformat()
    counts = {OK: 0, NO_NEW_ROW: 0, FAILED: 0, NOT_ATTEMPTED: 0}
    missing: list[str] = []
    failures: list[dict] = []
    short = 0
    stop: Optional[str] = None
    t_stage = clock()
    t_streak = f_streak = attempts = 0
    budget_stop = "시간 예산 30분 — 새 요청 시작 안 함"

    def failed(t: str, line: dict, code: Optional[int]) -> Optional[str]:
        nonlocal f_streak
        f_streak += 1
        if code:
            line["http_status"] = code
        writer.write(line)
        counts[FAILED] += 1
        missing.append(t)
        if len(failures) < 20:
            failures.append({"ticker": t, "error": line["error"]})
        if code:
            return f"HTTP {code} 차단 응답 — 네이버 단계 즉시 멈춤"
        if t_streak >= limits.timeout_streak:
            return f"연속 시간 초과 {limits.timeout_streak}회"
        if f_streak >= limits.fail_streak:
            return f"연속 실패 {limits.fail_streak}회"
        return None

    for t in tickers:
        if stop is None and attempt_limit is not None and attempts >= attempt_limit:
            stop = f"시험 제한(--limit-tickers {attempt_limit})"
        if stop is None and attempts:
            if clock() - t_stage > limits.budget_s:
                stop = budget_stop
            else:
                sleep(limits.gap_s)
        if stop is None and clock() - t_stage > limits.budget_s:
            stop = budget_stop
        if stop is not None:
            writer.write({"ticker": t, "status": NOT_ATTEMPTED, "reason": stop})
            counts[NOT_ATTEMPTED] += 1
            missing.append(t)
            continue
        attempts += 1
        try:
            with request_timeout(), status_probe() as probe:
                df = fetcher(t, start, today_kst)
            rows = _dataframe_to_price_rows(t, df)
        except Exception as e:  # noqa: BLE001 — 종목마다 격리
            t_streak = t_streak + 1 if _is_request_timeout(e) else 0
            line = {"ticker": t, "status": FAILED, "observed_at": iso(now())}
            line["error"] = type(e).__name__
            stop = failed(t, line, _blocked(e))
            continue
        observed = iso(now())
        if not rows:
            t_streak = 0
            code = probe["status"] if probe["status"] in (403, 429) else None
            line = {"ticker": t, "status": FAILED, "observed_at": observed}
            line["error"] = "빈 응답"
            if probe["status"] is not None:
                line["last_http_status"] = probe["status"]
            stop = failed(t, line, code)
            continue
        t_streak = f_streak = 0
        rows = sorted(rows, key=lambda r: r.date)
        kept = [r for r in rows if r.date < today]
        status = OK if kept and kept[-1].date >= target_day else NO_NEW_ROW
        counts[status] += 1
        short += len(kept) < MIN_ROWS
        writer.write(
            {
                "ticker": t,
                "status": status,
                "observed_at": observed,
                "requested": [start.isoformat(), today],
                "returned": [rows[0].date, rows[-1].date],
                "dropped_in_progress": len(rows) - len(kept),
                "abnormal_close": sum(
                    1 for r in kept if r.close is None or r.close <= 0
                ),
                "short_lt_61": len(kept) < MIN_ROWS,
                "rows": [
                    [r.date, r.open, r.high, r.low, r.close, r.volume, r.change]
                    for r in kept
                ],
            }
        )
    return {
        "requested": [start.isoformat(), today],
        "counts": counts,
        "attempted": counts[OK] + counts[NO_NEW_ROW] + counts[FAILED],
        "received": counts[OK] + counts[NO_NEW_ROW],
        "short_lt_61": short,
        "missing": missing,
        "stop_reason": stop,
        "failures_sample": failures,
    }
