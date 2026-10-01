"""POC3-OPS-02B-2 — 07:20 KRX 전종목 수집 (가격 적재 + 정합성 판정).

설계자 §M-2 확정 — **07:20 배치가 받은 응답 하나**를 두 용도로 쓴다.

1. 신규 무조정 가격계열 **일별 적재** (`krx_store`)
2. API ticker·기초지수명과 공식 CSV **정합성 판정** (`meta_gate`)

정합성 판정의 pending gate 입력(d20 종가 유무 · 첫 적재일 · 저장 거래일 수)도
**적재 직후 같은 응답**으로 여기서 정한다(POC3-02D-OPS-01 Q1 (c) · R2 Q23). 08:00 은
결과만 읽는다.

공식 CSV 는 운영에서 **공용 resolver**(`official_csv`)가 고른다 — 08:00 과 같은
함수다(Q2). 판정에 쓴 창(`evaluated_*`)과 `refresh_due` 를 매회 기록한다(R2 Q23 ·
Q27).

**08:00 runner 는 같은 API 를 다시 호출하지 않는다.** 여기가 유일한 외부 조회
지점이다.

## 기준일 선택 — 당일을 넣지 않는다

08:00 은 개장 전이라 **거래일에도 당일 응답이 비어 있다**(실측: `20260911`
`rows=0`). 빈 응답만으로 휴장일·조회 실패·universe 0건을 구분할 수 없다.
그래서 **완료된 거래일부터 bounded 역탐색**한다.

| 용도 | 역탐색 상한 |
|---|---:|
| 일별 | **7달력일** |
| 초기 적재 | **40달력일** |

## 휴장일 응답은 기준일이 될 수 없다

평일 휴장일에도 **행은 온다** — 가격 필드만 빈 문자열이다. `rows` 유무만 보면
휴장일을 기준일로 집어 그 다음날 배치가 통째로 실패한다. `has_traded_prices()`
로 판정한다.

## 예외를 올리지 않는다

배치가 ETF 가격 적재를 롤백하지 않도록, 실패는 **dict 로 돌려준다**
(`market_benchmark_batch` 와 같은 계약).
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from app.market_briefing import krx_store, meta_gate, official_csv

_KST = timezone(timedelta(hours=9))

KRX_ETF_DAILY_URL = "https://data-dbg.krx.co.kr/svc/apis/etp/etf_bydd_trd"
DAILY_LOOKBACK_DAYS = 7
INITIAL_LOOKBACK_DAYS = 40
REQUEST_TIMEOUT = 40.0

STATUS_OK = "ok"
STATUS_NO_BASIS_DATE = "api_fetch_failed"
STATUS_INVALID_SNAPSHOT = "invalid_snapshot"
STATUS_NO_API_KEY = "api_key_missing"


def read_api_key(env_path: Optional[Path] = None) -> Optional[str]:
    """`.env` 의 `KRX_API_KEY`. **값을 로그·반환값에 담지 않는다.**"""
    p = env_path or Path(".env")
    if not p.exists():
        return None
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("KRX_API_KEY="):
            return line.split("=", 1)[1].strip() or None
    return None


def _default_fetcher(bas_dd: str, key: str) -> list[dict[str, Any]]:
    import httpx

    r = httpx.get(
        KRX_ETF_DAILY_URL,
        params={"basDd": bas_dd},
        headers={"AUTH_KEY": key},
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    return r.json().get("OutBlock_1") or []


# POC3-02D-OPS-03 확정 계약 9 — KOSPI 공식 종가(사용자 승인 2026-09-29 · 같은 키).
# 네트워크 경계를 ETF 조회와 같은 모듈에 둔다 — 테스트 가드(`tests/conftest.py`
# `_block_live_krx_api`)가 두 경계를 함께 막는다. 소비처는 `market_benchmark_store`.
KRX_KOSPI_DAILY_URL = "https://data-dbg.krx.co.kr/svc/apis/idx/kospi_dd_trd"


def _default_kospi_fetcher(bas_dd: str, key: str) -> list[dict[str, Any]]:
    import httpx

    r = httpx.get(
        KRX_KOSPI_DAILY_URL,
        params={"basDd": bas_dd},
        headers={"AUTH_KEY": key},
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    return r.json().get("OutBlock_1") or []


def has_traded_prices(rows: list[dict[str, Any]]) -> bool:
    """이 응답이 **실제로 거래가 있었던 날** 인가.

    KRX Open API 는 **평일 휴장일에도 행을 돌려준다**. 다만 가격 필드가 전부 빈
    문자열이다(실측: `20260101` `rows=1058` · `TDD_CLSPRC=""`). 거래일은 채워져
    있다(`20260911` `rows=1168` · `TDD_CLSPRC=35130`).

    따라서 `rows` 유무만 보면 **휴장일을 기준일로 집는다.** 실제로 07:20 배치가
    휴장일 다음날마다 `invalid_snapshot` 으로 실패했다(2026년 11회).

    주말은 행 자체가 없으므로(`rows=0`) 이 함수까지 오지 않는다.
    """
    return any((r.get("TDD_CLSPRC") or "").strip() for r in rows)


def _candidate_dates(start: date, lookback_days: int) -> list[str]:
    """`start` 부터 과거로 `lookback_days` 일. **당일보다 미래를 만들지 않는다.**"""
    return [
        (start - timedelta(days=i)).strftime("%Y%m%d") for i in range(lookback_days)
    ]


def resolve_basis_date(
    *,
    start: date,
    key: str,
    fetcher: Callable[[str, str], list[dict[str, Any]]],
    lookback_days: int = DAILY_LOOKBACK_DAYS,
) -> tuple[Optional[str], list[dict[str, Any]], list[str]]:
    """응답이 있는 **가장 최근 기준일**을 bounded 역탐색으로 찾는다.

    반환 `(bas_dd, rows, 시도한 날짜들)`. 상한 내에 없으면 `(None, [], ...)` —
    **빈 응답을 universe 0건으로 처리하지 않는다.**
    """
    tried: list[str] = []
    for bas_dd in _candidate_dates(start, lookback_days):
        tried.append(bas_dd)
        try:
            rows = fetcher(bas_dd, key)
        except Exception:  # noqa: BLE001
            continue
        if rows and has_traded_prices(rows):
            return bas_dd, rows, tried
    return None, [], tried


def _index_names(rows: list[dict[str, Any]]) -> dict[str, str]:
    return {
        (r.get("ISU_CD") or "").strip(): (r.get("IDX_IND_NM") or "").strip()
        for r in rows
        if (r.get("ISU_CD") or "").strip()
    }


def _no_d20_first_loaded(
    tickers: Iterable[str],
    *,
    db_path: Optional[Path],
    window: Optional[krx_store.PriceWindow],
) -> dict[str, Optional[str]]:
    """저장 계열에서 **d20 종가가 없는** ticker → 첫 적재일.

    POC3-02D-OPS-01 Q1 (c) — d20 은 08:00 과 **같은 창**
    (`krx_store.resolve_window`)의 d20 이다. 창이 없으면(21 거래일 미만) 어느
    ticker 도 d20 종가가 없다. 창은 호출자가 한 번 정해 넘긴다 — 판정 기록
    (`evaluated_window_d20_date`)과 같은 창이어야 한다(R2 Q27).
    """
    have_d20: set[str] = (
        set(krx_store.closes_on([window.d20], db_path=db_path).get(window.d20) or {})
        if window is not None
        else set()
    )
    missing = sorted(set(tickers) - have_d20)
    first = krx_store.first_loaded_dates(missing, db_path=db_path)
    return {t: first.get(t) for t in missing}


def _csv_meta(path: Path) -> dict[str, Any]:
    import hashlib

    if not path.exists():
        return {}
    raw = path.read_bytes()
    return {
        "asof_date": _asof_from_name(path.name),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "rows": max(0, raw.decode("cp949").count("\n") - 1),
    }


def _asof_from_name(name: str) -> Optional[str]:
    """`krx_etf_basic_20260909.csv` → `2026-09-09`."""
    stem = name.rsplit(".", 1)[0]
    tail = stem.rsplit("_", 1)[-1]
    return (
        f"{tail[:4]}-{tail[4:6]}-{tail[6:8]}"
        if len(tail) == 8 and tail.isdigit()
        else None
    )


def _kst_now() -> str:
    return datetime.now(_KST).isoformat(timespec="seconds")


def _save_not_evaluated(
    result: meta_gate.ConsistencyResult,
    path: Path,
    previous: Optional[meta_gate.ConsistencyResult],
) -> dict[str, Any]:
    """판정하지 못한 날 — `refresh_due` 는 직전 값을 잇고 판정 창은 비운다.

    창이 비어 있으므로 08:00 은 이 JSON 을 `META_GATE_STALE` 로 본다(R2 Q27).
    """
    result.evaluated_at_kst = _kst_now()
    meta_gate.carry_refresh_due(result, previous=previous)
    meta_gate.save_consistency(result, path)
    return _refresh_fields(result)


def _refresh_fields(result: meta_gate.ConsistencyResult) -> dict[str, Any]:
    return {
        "refresh_due": result.refresh_due,
        "refresh_due_reason": result.refresh_due_reason,
        "refresh_due_cycle_id": result.refresh_due_cycle_id,
        "csv_name": result.csv_name,
        "csv_rejected_count": len(result.csv_rejected),
    }


def sync_krx_daily(
    *,
    today: date,
    consistency_path: Path,
    official_csv_path: Optional[Path] = None,
    meta_dir: Optional[Path] = None,
    db_path: Optional[Path] = None,
    env_path: Optional[Path] = None,
    fetcher: Optional[Callable[[str, str], list[dict[str, Any]]]] = None,
    lookback_days: int = DAILY_LOOKBACK_DAYS,
    logger: Any = None,
) -> dict[str, Any]:
    """옛 07:20 진입점(역탐색). **예외를 올리지 않는다.**

    POC3-02D-OPS-03 부터 08:10 배치 · 09:20 보강은 목표일 수집
    (`krx_target_sync.sync_krx_target`)을 쓴다 — 역탐색은 T-1 이 없으면 같은 호출
    안에서 T-2 를 돌려주므로 재시도 계약과 맞지 않는다. 이 함수는 옛 계약 그대로
    남긴다(기존 테스트 · 도구).

    성공하면 가격 1일치를 적재하고 정합성 결과를 남긴다. 실패해도 배치가
    ETF 가격 적재를 롤백하지 않도록 dict 로 돌려준다.

    공식 CSV — 운영은 `meta_dir` 을 넘겨 **공용 resolver** 가 고르게 한다.
    `official_csv_path` 는 파일을 직접 지정하는 옛 호출(합성 fixture · 고정 경로
    도구)용이며 resolver 검사를 거치지 않는다. 둘 중 하나만 넘긴다 — 호출 인자
    오류만 `TypeError` 로 올린다(실행 중 실패는 올리지 않는다).
    """
    if (meta_dir is None) == (official_csv_path is None):
        raise TypeError("meta_dir 과 official_csv_path 중 하나만 넘긴다")
    # R2 Q24 — 직전 판정의 `refresh_due` 주기를 잇기 위해 **덮어쓰기 전에** 읽는다.
    previous = meta_gate.load_consistency(consistency_path)

    key = read_api_key(env_path)
    if not key:
        result = meta_gate.ConsistencyResult(
            status=meta_gate.STATUS_API_FETCH_FAILED, error=STATUS_NO_API_KEY
        )
        extra = _save_not_evaluated(result, consistency_path, previous)
        return {
            "status": STATUS_NO_API_KEY,
            "basis_date": None,
            "rows_written": 0,
            **extra,
        }

    fetch = fetcher or _default_fetcher
    bas_dd, rows, tried = resolve_basis_date(
        start=today, key=key, fetcher=fetch, lookback_days=lookback_days
    )
    if bas_dd is None:
        # 상한 내 응답 없음 — **CSV 불일치로 위장하지 않는다.**
        result = meta_gate.ConsistencyResult(
            status=meta_gate.STATUS_API_FETCH_FAILED,
            error=f"no_response_within_{lookback_days}d",
        )
        extra = _save_not_evaluated(result, consistency_path, previous)
        return {
            "status": STATUS_NO_BASIS_DATE,
            "basis_date": None,
            "rows_written": 0,
            "tried_dates": tried,
            **extra,
        }

    # ① 가격 적재 — 검사를 통과한 **전체 ETF** 를 저장한다(196종만 저장하지 않는다).
    try:
        snapshot = krx_store.validate_snapshot(rows, expected_date=bas_dd)
    except krx_store.KrxSnapshotError as e:
        result = meta_gate.ConsistencyResult(
            status=meta_gate.STATUS_API_FETCH_FAILED,
            api_basis_date=bas_dd,
            error=f"invalid_snapshot:{e}",
        )
        extra = _save_not_evaluated(result, consistency_path, previous)
        return {
            "status": STATUS_INVALID_SNAPSHOT,
            "basis_date": bas_dd,
            "rows_written": 0,
            "error": str(e),
            **extra,
        }
    written = krx_store.upsert_snapshot(snapshot, db_path=db_path)

    # 창은 한 번만 정한다(R2 Q27 기록과 같은 창) — 저장 행 순서 창(옛 계약).
    judged = judge_and_save_consistency(
        rows,
        bas_dd=bas_dd,
        window_fn=lambda: krx_store.resolve_window(db_path=db_path),
        consistency_path=consistency_path,
        previous=previous,
        meta_dir=meta_dir,
        official_csv_path=official_csv_path,
        db_path=db_path,
        logger=logger,
    )
    return {
        "status": STATUS_OK,
        "basis_date": bas_dd,
        "rows_written": written,
        "api_ticker_count": judged["api_ticker_count"],
        "consistency_status": judged["consistency_status"],
        "join_coverage": judged["join_coverage"],
        "tried_dates": tried,
        **judged["refresh"],
    }


def judge_and_save_consistency(
    rows: list[dict[str, Any]],
    *,
    bas_dd: str,
    window_fn: Callable[[], Optional[krx_store.PriceWindow]],
    consistency_path: Path,
    previous: Optional[meta_gate.ConsistencyResult],
    meta_dir: Optional[Path],
    official_csv_path: Optional[Path],
    db_path: Optional[Path],
    logger: Any = None,
) -> dict[str, Any]:
    """적재를 마친 **같은 응답**으로 정합성을 판정하고 JSON 에 남긴다.

    `sync_krx_daily`(옛 역탐색)와 POC3-02D-OPS-03 목표일 수집(`krx_target_sync`)이
    함께 쓴다. 창은 호출자가 정한다 — 목표일 수집은 거래일 날짜 창(확정 계약 5)을
    넘긴다.
    """
    api_names = _index_names(rows)
    # pending gate 입력 — 적재 **직후** · 같은 응답의 ticker 로 본다
    # (POC3-02D-OPS-01 Q1 (c) · R2 Q23). 창은 한 번만 정한다(R2 Q27 기록과 같은 창).
    window: Optional[krx_store.PriceWindow] = None
    no_d20: Optional[dict[str, Optional[str]]]
    counts: Optional[dict[str, int]]
    try:
        window = window_fn()
        no_d20 = _no_d20_first_loaded(api_names, db_path=db_path, window=window)
        counts = krx_store.stored_day_counts(no_d20, db_path=db_path)
        pending_error = None
    except sqlite3.Error as e:
        # 조회 실패 — 옛 계약(모든 API-only 차단)으로 fail-closed 한다.
        no_d20, counts = None, None
        pending_error = f"pending_lookup:{type(e).__name__}"

    # ② 정합성 판정 — **같은 응답**을 쓴다. 다시 호출하지 않는다.
    selection: Optional[official_csv.CsvSelection] = None
    csv_error: Optional[str] = None
    if meta_dir is not None:
        selection = official_csv.resolve_official_csv(meta_dir, logger=logger)
        csv_rows = selection.records
        csv_meta = selection.csv_meta()
    else:
        try:
            csv_rows = meta_gate.load_official_csv(official_csv_path)
        except (OSError, UnicodeDecodeError) as e:  # noqa: BLE001
            csv_rows = []
            csv_error = f"{type(e).__name__}"
        csv_meta = _csv_meta(official_csv_path)

    if selection is not None and not selection.ok:
        # 유효 파일이 하나도 없다 — CSV 갱신 필요로 fail-closed(R2 Q25).
        result = meta_gate.ConsistencyResult(
            status=meta_gate.STATUS_CSV_REFRESH_REQUIRED,
            api_ticker_count=len(api_names),
            api_basis_date=bas_dd,
            error=selection.error,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
        )
    else:
        result = meta_gate.evaluate_consistency(
            api_index_names=api_names,
            csv_rows=csv_rows,
            api_basis_date=bas_dd,
            csv_meta=csv_meta,
            no_d20_first_loaded=no_d20,
            stored_day_counts=counts,
        )
    if csv_error and result.error is None:
        result.error = f"official_csv:{csv_error}"
    if pending_error and result.error is None:
        result.error = pending_error
    if selection is not None:
        result.csv_name = selection.name
        result.csv_rejected = [r.to_dict() for r in selection.rejected]
    elif official_csv_path is not None and official_csv_path.exists():
        result.csv_name = official_csv_path.name
    # R2 Q27 — 판정에 쓴 창 · R2 Q23 — refresh_due 와 주기.
    result.evaluated_api_basis_date = bas_dd
    result.evaluated_window_d20_date = window.d20 if window is not None else None
    result.evaluated_at_kst = _kst_now()
    meta_gate.apply_refresh_due(result, previous=previous)
    meta_gate.save_consistency(result, consistency_path)

    return {
        "api_ticker_count": result.api_ticker_count,
        "consistency_status": result.status,
        "join_coverage": round(result.join_coverage, 6),
        "refresh": _refresh_fields(result),
    }


def initial_backfill(
    *,
    today: date,
    db_path: Optional[Path] = None,
    env_path: Optional[Path] = None,
    fetcher: Optional[Callable[[str, str], list[dict[str, Any]]]] = None,
    required_days: int = krx_store.REQUIRED_TRADING_DAYS,
    lookback_days: int = INITIAL_LOOKBACK_DAYS,
) -> dict[str, Any]:
    """21개 완료 거래일 확보에 필요한 범위만 적재한다.

    **전체 과거 backfill 을 하지 않는다.** 역탐색은 `lookback_days`(기본 40
    달력일)로 bounded 다. 운영 DB 초기 적재는 **별도 승인 대상**이며, 이 함수는
    로컬·임시 DB 검증용이다.
    """
    key = read_api_key(env_path)
    if not key:
        return {"status": STATUS_NO_API_KEY, "days_written": 0}
    fetch = fetcher or _default_fetcher

    have = set(krx_store.stored_trading_days(db_path=db_path))
    written_days: list[str] = []
    for bas_dd in _candidate_dates(today, lookback_days):
        if len(have) + len(written_days) >= required_days:
            break
        iso = f"{bas_dd[:4]}-{bas_dd[4:6]}-{bas_dd[6:8]}"
        if iso in have:
            continue
        try:
            rows = fetch(bas_dd, key)
        except Exception:  # noqa: BLE001
            continue
        if not rows or not has_traded_prices(rows):
            continue  # 휴장일. 그 날짜만 건너뛴다.
        try:
            snapshot = krx_store.validate_snapshot(rows, expected_date=bas_dd)
        except krx_store.KrxSnapshotError:
            continue  # 그 날짜만 건너뛴다. 부분 저장하지 않는다.
        krx_store.upsert_snapshot(snapshot, db_path=db_path)
        written_days.append(iso)

    total = len(krx_store.stored_trading_days(db_path=db_path))
    return {
        "status": STATUS_OK if total >= required_days else "insufficient",
        "days_written": len(written_days),
        "written_days": written_days,
        "total_days": total,
        "required_days": required_days,
    }


__all__ = [
    "DAILY_LOOKBACK_DAYS",
    "INITIAL_LOOKBACK_DAYS",
    "KRX_ETF_DAILY_URL",
    "KRX_KOSPI_DAILY_URL",
    "STATUS_INVALID_SNAPSHOT",
    "STATUS_NO_API_KEY",
    "STATUS_NO_BASIS_DATE",
    "STATUS_OK",
    "has_traded_prices",
    "initial_backfill",
    "judge_and_save_consistency",
    "read_api_key",
    "resolve_basis_date",
    "sync_krx_daily",
]
