"""POC3-OPS-02B-2 — 07:20 KRX 전종목 수집 (가격 적재 + 정합성 판정).

설계자 §M-2 확정 — **07:20 배치가 받은 응답 하나**를 두 용도로 쓴다.

1. 신규 무조정 가격계열 **일별 적재** (`krx_store`)
2. API ticker·기초지수명과 공식 CSV **정합성 판정** (`meta_gate`)

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

## 예외를 올리지 않는다

배치가 ETF 가격 적재를 롤백하지 않도록, 실패는 **dict 로 돌려준다**
(`market_benchmark_batch` 와 같은 계약).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

from app.market_briefing import krx_store, meta_gate

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
        if rows:
            return bas_dd, rows, tried
    return None, [], tried


def _index_names(rows: list[dict[str, Any]]) -> dict[str, str]:
    return {
        (r.get("ISU_CD") or "").strip(): (r.get("IDX_IND_NM") or "").strip()
        for r in rows
        if (r.get("ISU_CD") or "").strip()
    }


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


def sync_krx_daily(
    *,
    today: date,
    official_csv_path: Path,
    consistency_path: Path,
    db_path: Optional[Path] = None,
    env_path: Optional[Path] = None,
    fetcher: Optional[Callable[[str, str], list[dict[str, Any]]]] = None,
    lookback_days: int = DAILY_LOOKBACK_DAYS,
) -> dict[str, Any]:
    """07:20 진입점. **예외를 올리지 않는다.**

    성공하면 가격 1일치를 적재하고 정합성 결과를 남긴다. 실패해도 배치가
    ETF 가격 적재를 롤백하지 않도록 dict 로 돌려준다.
    """
    key = read_api_key(env_path)
    if not key:
        result = meta_gate.ConsistencyResult(
            status=meta_gate.STATUS_API_FETCH_FAILED, error=STATUS_NO_API_KEY
        )
        meta_gate.save_consistency(result, consistency_path)
        return {"status": STATUS_NO_API_KEY, "basis_date": None, "rows_written": 0}

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
        meta_gate.save_consistency(result, consistency_path)
        return {
            "status": STATUS_NO_BASIS_DATE,
            "basis_date": None,
            "rows_written": 0,
            "tried_dates": tried,
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
        meta_gate.save_consistency(result, consistency_path)
        return {
            "status": STATUS_INVALID_SNAPSHOT,
            "basis_date": bas_dd,
            "rows_written": 0,
            "error": str(e),
        }
    written = krx_store.upsert_snapshot(snapshot, db_path=db_path)

    # ② 정합성 판정 — **같은 응답**을 쓴다. 다시 호출하지 않는다.
    try:
        csv_rows = meta_gate.load_official_csv(official_csv_path)
    except (OSError, UnicodeDecodeError) as e:  # noqa: BLE001
        csv_rows = []
        csv_error = f"{type(e).__name__}"
    else:
        csv_error = None

    result = meta_gate.evaluate_consistency(
        api_index_names=_index_names(rows),
        csv_rows=csv_rows,
        api_basis_date=bas_dd,
        csv_meta=_csv_meta(official_csv_path),
    )
    if csv_error and result.error is None:
        result.error = f"official_csv:{csv_error}"
    meta_gate.save_consistency(result, consistency_path)

    return {
        "status": STATUS_OK,
        "basis_date": bas_dd,
        "rows_written": written,
        "api_ticker_count": result.api_ticker_count,
        "consistency_status": result.status,
        "join_coverage": round(result.join_coverage, 6),
        "tried_dates": tried,
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
        if not rows:
            continue
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
    "STATUS_INVALID_SNAPSHOT",
    "STATUS_NO_API_KEY",
    "STATUS_NO_BASIS_DATE",
    "STATUS_OK",
    "initial_backfill",
    "read_api_key",
    "resolve_basis_date",
    "sync_krx_daily",
]
