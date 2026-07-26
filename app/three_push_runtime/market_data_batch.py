"""OCI 일별 시장 데이터 배치 (OCI Operational Market Data Refresh v1 · §5).

평일 하루 한 번 실행:
    승인 대상(seed ∪ Holdings) ticker 증분 시세 갱신
    → SQLite 저장 검증
    → Universe 운영 artifact 생성 (SQLite fetcher)
    → freshness 검증

Spike 조건 평가와 분리된다 (Spike 는 이 배치를 반복 실행하지 않는다).

허용/금지 (지시문 §3·§4·§9):
- 기존 FDR source (market_data_fdr.refresh_price_history) 재사용. 신규 source 없음.
- 기존 etf_daily_price 저장 계약·DB schema 그대로. schema 변경 없음.
- 승인 seed ∪ Holdings ticker 만 갱신. 전체 시장 수집·seed 변경 금지.
- 기존 scoring·factor·threshold·산식 유지 (SQLite fetcher 만 주입).
- Fail-Closed: 실패 시 기존 artifact/이전 가격으로 대체하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import json

from app.market_data_store import DEFAULT_DB_PATH, get_last_price_date

# ── 배치 실행 상태 저장소 (C 확정: Spike 가 당일 배치 성공 여부를 읽는다) ──────

MARKET_DATA_BATCH_STATE_PATH = Path("state/market/oci_market_data_batch_state.json")


def write_batch_state(
    *,
    status: str,
    price_data_as_of: Optional[str],
    artifact_generated_at: Optional[str],
    refresh_date_kst: str,
    refresh_completed_at: str,
    state_path: Optional[Path] = None,
) -> None:
    """일일 갱신 배치의 실행 결과를 저장 (latest 1건 덮어쓰기).

    Spike guard 가 "당일 배치 status=success" + "price_data_as_of 일치" 를 검증하는
    단일 소스. 신규 DB 아닌 기존 JSON state 패턴.

    state_path=None 이면 모듈 상수를 **런타임에** 참조 (test monkeypatch 지원).
    """
    state_path = state_path or MARKET_DATA_BATCH_STATE_PATH
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "price_data_as_of": price_data_as_of,
        "artifact_generated_at": artifact_generated_at,
        "refresh_date_kst": refresh_date_kst,
        "refresh_completed_at": refresh_completed_at,
    }
    state_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def read_batch_state(
    state_path: Optional[Path] = None,
) -> Optional[dict]:
    """저장된 배치 실행 결과. 없거나 파싱 실패 시 None (Spike Fail-Closed).

    state_path=None 이면 모듈 상수 MARKET_DATA_BATCH_STATE_PATH 를 **런타임에**
    참조 (test 가 monkeypatch 로 상수를 대체할 수 있도록).
    """
    p = state_path or MARKET_DATA_BATCH_STATE_PATH
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


# ── 대상 ticker 수집 (승인 seed ∪ 현재 Holdings) ─────────────────────────────


def collect_approved_tickers() -> list[str]:
    """승인 seed ticker ∪ 현재 Holdings ticker (중복 제거 · 입력 순서 보존).

    Fail-Closed: seed/Holdings 로드 예외는 그대로 raise (호출자가 failed 종료).
    빈 결과는 반환하지 않고 raise — 갱신 대상 0 은 운영상 비정상.
    """
    from app.universe_seed import load_universe_seed
    from app import holdings as _holdings

    seed = load_universe_seed()
    seed_tickers = [
        it.ticker for it in seed.items if isinstance(it.ticker, str) and it.ticker
    ]

    # B-1 (Fail-Closed): Holdings 파일이 없으면 현재 Holdings ticker 를 확인할 수
    # 없어 승인 대상 집합이 불완전해진다. seed 만으로 축소 진행하지 않고 raise
    # (호출자가 failed 종료). Market·Holdings 운영은 이 배치 실패와 독립.
    if not _holdings.HOLDINGS_FILE.exists():
        raise RuntimeError(f"holdings source missing: {_holdings.HOLDINGS_FILE}")
    hs = _holdings.load()
    holdings_tickers = [h.ticker for h in hs if isinstance(h.ticker, str) and h.ticker]

    seen: set[str] = set()
    out: list[str] = []
    for t in seed_tickers + holdings_tickers:
        if t not in seen:
            seen.add(t)
            out.append(t)
    if not out:
        raise RuntimeError("approved ticker set empty (seed ∪ holdings)")
    return out


# ── 증분 시세 갱신 ───────────────────────────────────────────────────────────


@dataclass
class RefreshResult:
    attempted: int = 0
    success: int = 0
    fail: int = 0
    failures: list[dict] = field(default_factory=list)
    price_data_as_of: Optional[str] = None  # 갱신 후 대상 ticker 공통 최신일


def refresh_approved_prices(
    tickers: list[str],
    *,
    end_date: date,
    db_path: Path = DEFAULT_DB_PATH,
    refresh_fn: Callable[..., Any] = None,
) -> RefreshResult:
    """승인 ticker 의 일별 시세를 마지막 저장일 이후만 증분 갱신.

    - 기존 FDR refresh_price_history 재사용 (신규 source 없음).
    - lookback = (end_date - 마지막 저장일). refresh_price_history 의
      start_date = end_date - lookback 이므로 정확히 마지막 저장일부터 fetch
      (그 이전 재조회 없음). upsert 는 (ticker,date) PK ON CONFLICT 라 멱등.
    - Fail-Closed: refresh 결과에 success 필드 없음 · DB 최신일 형식 손상 ·
      유효 종가(close>0) 전무 대상은 모두 fail 로 집계 (성공 위장 금지).
    - 전체 대상이 유효 종가를 확보한 경우에만 price_data_as_of 확정 (아니면 None).
    """
    from app.market_data_fdr import refresh_price_history

    _refresh = refresh_fn or refresh_price_history
    result = RefreshResult(attempted=len(tickers))

    for tk in tickers:
        # 증분 시작점: close 유효성 무관 MAX(date) (어느 날짜까지 row 가 있나).
        last = get_last_price_date(tk, db_path=db_path, require_valid_close=False)
        if last is None:
            # 첫 적재: 넉넉히 (기존 FDR 기본 lookback 사용).
            lookback = None
        else:
            try:
                last_d = datetime.strptime(last, "%Y-%m-%d").date()
            except ValueError:
                # B-1 (Fail-Closed): DB 최신일 형식 손상은 조용히 전체 lookback
                # 으로 넘어가지 않고 실패로 집계 (기존 행 대량 재조회·훼손 방지).
                result.fail += 1
                if len(result.failures) < 10:
                    result.failures.append(
                        {"ticker": tk, "error": f"bad_last_date:{last!r}"}
                    )
                continue
            # A-1 증분: "마지막 저장일 이후만" 수집. refresh_price_history 는
            # start_date = end_date - lookback_days 이므로 lookback = gap 이면
            # start_date == 마지막 저장일. 마지막 저장일 **이전** 을 재조회하는
            # 경계 여유(+N)를 두지 않는다. gap=0 (오늘이 마지막 저장일) 이면
            # lookback=0 → 오늘 하루만 (당일 마감 데이터 갱신).
            lookback = max((end_date - last_d).days, 0)
        try:
            kwargs: dict[str, Any] = {"end_date": end_date, "db_path": db_path}
            if lookback is not None:
                kwargs["lookback_days"] = lookback
            r = _refresh([tk], **kwargs)
            # B-1 (Fail-Closed): refresh 결과에 success 필드가 없으면 성공으로
            # 처리하지 않는다 (계약 미상 반환을 성공 위장 금지).
            ok = getattr(r, "success", None)
            if ok is None:
                result.fail += 1
                if len(result.failures) < 10:
                    result.failures.append(
                        {"ticker": tk, "error": "refresh_result_no_success_field"}
                    )
            elif ok == 0:
                result.fail += 1
                fails = getattr(r, "failure_examples", None) or []
                if fails and len(result.failures) < 10:
                    result.failures.append(fails[0])
                elif len(result.failures) < 10:
                    result.failures.append({"ticker": tk, "error": "no_data"})
            else:
                result.success += 1
        except Exception as e:  # noqa: BLE001
            result.fail += 1
            if len(result.failures) < 10:
                result.failures.append(
                    {"ticker": tk, "error": f"{type(e).__name__}: {e}"[:160]}
                )

    # A-1 전체 최솟값: 승인 대상 **전체** 가 유효 종가를 확보해야 한다. 유효 종가
    # (close>0) 가 하나도 없는 ticker 는 조용히 제외하지 않고 fail 로 집계 →
    # 배치가 성공으로 확정되지 않는다 (일부 대상 누락을 성공 위장 금지).
    latest_dates: list[str] = []
    missing_valid: list[str] = []
    for tk in tickers:
        d = get_last_price_date(tk, db_path=db_path, require_valid_close=True)
        if d:
            latest_dates.append(d)
        else:
            missing_valid.append(tk)
    if missing_valid:
        # 유효 종가 없는 ticker 는 fetch 단계에서 success 로 집계됐을 수 있으므로
        # fail 로 재분류한다 (카운터 정합: success/fail 이 동일 ticker 를 이중
        # 집계하지 않도록 success 를 그만큼 되돌린다).
        n = len(missing_valid)
        result.fail += n
        result.success = max(result.success - n, 0)
        for tk in missing_valid[:10]:
            if len(result.failures) < 10:
                result.failures.append({"ticker": tk, "error": "no_valid_close_price"})
    # 전체 승인 대상이 유효 종가를 확보한 경우에만 price_data_as_of 확정.
    # 하나라도 누락(missing_valid)이면 None 으로 남겨 배치가 성공 못하게 한다.
    if latest_dates and not missing_valid:
        result.price_data_as_of = min(latest_dates)
    return result


# ── freshness 계약 (C 확정 · OCI Operational Market Data Refresh v1) ──────────
#
# 설계자 C 확정: DB 를 거래일 캘린더로 쓰는 방식은 순환 결함(stale DB → lag 0)이라
# 폐기. freshness 는 일일 갱신 배치가 한 번 확정하고 Spike 는 그 결과만 검증한다.
#
# Spike 실행 조건 (모두 충족):
#   - 당일 데이터 갱신 배치 status = success
#   - artifact.price_data_as_of == 갱신 결과 price_data_as_of
#   - artifact_generated_at 이 현재 36시간 이내
#   - 현재일 - price_data_as_of <= 7 달력일 (장기 stale 최종 안전 상한)
#   - Runtime 현재가 조회 성공 (Runner 별도 단계)
#
# 7일은 "정상 freshness 증명 기준" 이 아니라 주말·설/추석 연휴를 흡수하는 **장기
# stale 차단 최종 안전 상한**. 실제 freshness 의 주 판단은 "당일 배치 성공 +
# source 가 반환한 price_data_as_of" 다.

DEFAULT_ARTIFACT_MAX_AGE_HOURS = 36
DEFAULT_PRICE_MAX_LAG_CALENDAR_DAYS = 7


@dataclass
class FreshnessVerdict:
    ok: bool
    reason: str = ""
    price_data_as_of: Optional[str] = None
    artifact_generated_at: Optional[str] = None
    price_lag_days: Optional[int] = None
    artifact_age_hours: Optional[float] = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def evaluate_freshness(
    *,
    price_data_as_of: Optional[str],
    artifact_generated_at: Optional[str],
    current_date: str,
    now: Optional[datetime] = None,
    price_max_lag_calendar_days: int = DEFAULT_PRICE_MAX_LAG_CALENDAR_DAYS,
    artifact_max_age_hours: int = DEFAULT_ARTIFACT_MAX_AGE_HOURS,
) -> FreshnessVerdict:
    """freshness 판정 (C 확정 계약).

    - price_data_as_of: current_date 대비 price_max_lag_calendar_days **달력일**
      이내. 장기 stale 최종 안전 상한 (외부 거래일 조회 없음 · DB 순환 없음).
    - artifact_generated_at: artifact_max_age_hours 이내.
    하나라도 미달 → ok=False (Fail-Closed). "당일 배치 성공" 과 "artifact.price_
    data_as_of == 배치 결과" 검증은 호출자(Spike guard)가 별도 수행한다.
    """
    now = now or _utc_now()

    if not price_data_as_of:
        return FreshnessVerdict(ok=False, reason="price_data_as_of_missing")
    if not artifact_generated_at:
        return FreshnessVerdict(
            ok=False,
            reason="artifact_generated_at_missing",
            price_data_as_of=price_data_as_of,
        )

    try:
        price_d = datetime.strptime(price_data_as_of, "%Y-%m-%d").date()
        cur_d = datetime.strptime(current_date, "%Y-%m-%d").date()
    except ValueError:
        return FreshnessVerdict(
            ok=False,
            reason="date_parse_error",
            price_data_as_of=price_data_as_of,
            artifact_generated_at=artifact_generated_at,
        )
    lag_days = (cur_d - price_d).days
    # 미래 데이터(음수 lag) 도 비정상 → 차단.
    if lag_days < 0:
        return FreshnessVerdict(
            ok=False,
            reason=f"price_data_future:lag={lag_days}d",
            price_data_as_of=price_data_as_of,
            artifact_generated_at=artifact_generated_at,
            price_lag_days=lag_days,
        )
    if lag_days > price_max_lag_calendar_days:
        return FreshnessVerdict(
            ok=False,
            reason=f"price_data_stale:lag={lag_days}d",
            price_data_as_of=price_data_as_of,
            artifact_generated_at=artifact_generated_at,
            price_lag_days=lag_days,
        )

    # artifact 나이.
    try:
        gen = datetime.fromisoformat(artifact_generated_at)
        if gen.tzinfo is None:
            gen = gen.replace(tzinfo=timezone.utc)
    except ValueError:
        return FreshnessVerdict(
            ok=False,
            reason="artifact_generated_at_parse_error",
            price_data_as_of=price_data_as_of,
            artifact_generated_at=artifact_generated_at,
        )
    age_hours = (now - gen).total_seconds() / 3600.0
    if age_hours > artifact_max_age_hours:
        return FreshnessVerdict(
            ok=False,
            reason=f"artifact_stale:age={age_hours:.1f}h",
            price_data_as_of=price_data_as_of,
            artifact_generated_at=artifact_generated_at,
            price_lag_days=lag_days,
            artifact_age_hours=age_hours,
        )

    return FreshnessVerdict(
        ok=True,
        reason="fresh",
        price_data_as_of=price_data_as_of,
        artifact_generated_at=artifact_generated_at,
        price_lag_days=lag_days,
        artifact_age_hours=age_hours,
    )
