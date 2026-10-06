"""POC3-02D-OPS-03 — KRX 한 날짜 1회 시도(조회 → 적재 판정 → 저장 · read-back) · 대표 커버리지.

`krx_target_sync`(목표일 T-1 시각표)와 `krx_backfill`(창 안 빈 날 채우기)이 같은 시도
함수를 쓴다.

**적재 성공 조건(설계자 RESULT STEP 2 · 2026-09-30 개정)** — ① 반환 기준일 == 요청일
③ 행 수 ≥ 직전 정상 적재 × 95%(고정 행 수 아님) ④ 관계식(저가 ≤ 시가 · 종가 ≤ 고가) ·
중복 · 0행 · 결측 ⑤ 저장 뒤 read-back 기준일 · 건수(어긋나면 방금 쓴 날짜를 지운다).

**② 대표 ETF 커버리지는 적재 성공 조건에서 뺐다.** 적재가 성공한 뒤 따로 판정해
기록만 한다(`evaluate_representatives`). 장중 설정을 못 읽거나 대표 한 종목이
상장폐지돼도 KRX 전체 적재 · 08:30 기초지수는 막히지 않는다. 장중 「신규 진입
검토」만 자기 관문(`sector_signal`)으로 생략된다.

시도마다 시각 · 목표일 · HTTP · 행 수 · 가격 채움 · 결과 · 예외 종류를 남긴다(키 ·
가격 값은 남기지 않는다). 조회 예외(`fetch_error`)에는 일시 오류 여부(`transient`)를
더한다(POC3-02D-OPS-04 — `is_transient_fetch_error`).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from app.intraday_config import representatives as reps_mod
from app.market_briefing import krx_store, krx_sync

_KST = timezone(timedelta(hours=9))

# 확정 계약 4 — 연구 DB 3,138쌍 하루 대비 행 수 비율 최소 0.954 · 95% 미만 0회.
MIN_ROW_RATIO = 0.95

R_OK = "ok"
R_NOT_PUBLISHED = "not_published"
R_FETCH_ERROR = "fetch_error"
R_BASIS_MISMATCH = "basis_date_mismatch"
R_INVALID = "invalid_snapshot"
R_ROW_DROP = "row_drop"
R_READBACK = "readback_mismatch"
R_STORE_ERROR = "store_error"

REQUIRED_FROM_CONFIG = "active_intraday_config"
REQUIRED_FROM_ARGUMENT = "argument"
REQUIRED_UNAVAILABLE = "unavailable"
# 적재는 성공했는데 T-1 행을 읽지 못해 판정하지 못한 경우(기록 전용).
COVERAGE_NOT_EVALUATED = "not_evaluated"


def _as_kst(dt: datetime) -> datetime:
    return dt.replace(tzinfo=_KST) if dt.tzinfo is None else dt.astimezone(_KST)


def iso_date(bas_dd: str) -> str:
    return f"{bas_dd[:4]}-{bas_dd[4:6]}-{bas_dd[6:8]}" if len(bas_dd) == 8 else bas_dd


def relation_violation(rows: Sequence[dict[str, Any]]) -> Optional[str]:
    """관계식 위반 ticker. 거래 없는 행(시 · 고 · 저 전부 0)은 통과.

    실측(연구 DB 750거래일 · 720,356행): 거래가 있는 행의 위반 0 · 시 · 고 · 저
    일부만 0 인 행 0 · 전부 0(거래 없음) 7,863행. 세 값이 모두 비어 있으면 볼
    필드가 없는 응답이라 검사하지 않는다.
    """

    def _num(v: Any) -> Optional[float]:
        text = (v or "").replace(",", "").strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return float("nan")

    for r in rows:
        o, h, lo = (_num(r.get(k)) for k in ("TDD_OPNPRC", "TDD_HGPRC", "TDD_LWPRC"))
        c = _num(r.get("TDD_CLSPRC"))
        ohl = (o, h, lo)
        if all(v is None for v in ohl):
            continue
        ticker = (r.get("ISU_CD") or "").strip()
        if any(v is None or v != v for v in ohl) or c is None or c != c:
            return ticker
        if all(v == 0 for v in ohl):
            continue
        if any(v == 0 for v in ohl) or not (lo <= o <= h and lo <= c <= h):
            return ticker
    return None


def check_response(
    rows: list[dict[str, Any]],
    *,
    bas_dd: str,
    db_path: Optional[Path],
) -> tuple[str, dict[str, Any], Optional[list[krx_store.SnapshotRow]]]:
    """조건 ① ③ ④ 를 본다. 반환 `(결과, 세부, 통과한 snapshot)`. 쓰지 않는다.

    대표 ETF 커버리지(옛 ②)는 보지 않는다(설계자 RESULT STEP 2).
    """
    detail: dict[str, Any] = {}
    if not rows:
        return R_NOT_PUBLISHED, detail, None
    other = sorted({(r.get("BAS_DD") or "").strip() for r in rows} - {bas_dd})
    if other:
        # ① — T-2 등 다른 날 응답은 성공이 아니다(표에 쓰지 않는다).
        detail["returned_basis_dates"] = other[:3]
        return R_BASIS_MISMATCH, detail, None
    if not krx_sync.has_traded_prices(rows):
        return R_NOT_PUBLISHED, detail, None
    try:
        snapshot = krx_store.validate_snapshot(rows, expected_date=bas_dd)
    except krx_store.KrxSnapshotError as e:
        detail["error"] = str(e)[:80]
        return R_INVALID, detail, None
    bad = relation_violation(rows)
    if bad is not None:
        detail["error"] = f"relation:{bad}"
        return R_INVALID, detail, None
    base_date, base_rows = krx_store.baseline_row_count(
        iso_date(bas_dd), db_path=db_path
    )
    detail["baseline_date"], detail["baseline_rows"] = base_date, base_rows
    if base_rows and len(snapshot) < base_rows * MIN_ROW_RATIO:
        return R_ROW_DROP, detail, None
    return R_OK, detail, snapshot


def _http_status(e: BaseException) -> Optional[int]:
    code = getattr(getattr(e, "response", None), "status_code", None)
    return code if isinstance(code, int) else None


def http_status(e: BaseException) -> Optional[int]:
    """조회 예외의 HTTP 상태 코드(없으면 None). 개별주 시도(`krx_stock_sync`)도 같은 규칙을 쓴다."""
    return _http_status(e)


def is_transient_fetch_error(e: BaseException) -> bool:
    """조회 예외가 **일시 오류**인가(POC3-02D-OPS-04 Q6 b) — 09:20 보강 1회 대상.

    일시 오류 = HTTP 5xx · 429 · timeout(`httpx.TimeoutException`) · 연결 오류
    (`httpx.NetworkError` — 연결 실패 · 송수신 끊김) · `httpx.RemoteProtocolError`(서버 쪽
    프로토콜 오류 — 연결 끊김 · 잘못된 응답 모두 · 설계자 2026-10-06: 읽기 전용 GET 이고
    09:20 1회뿐이라 오류 문자열로 나누지 않는다). 그 밖(3xx · 다른 4xx · JSON 이 아닌 응답 ·
    그 밖 예외)은 같은 날 다시 부르지 않는다. httpx 는 TLS · DNS 실패도 연결 오류
    (`ConnectError`)로 낸다.
    """
    code = _http_status(e)
    if code is not None:
        return code == 429 or 500 <= code <= 599
    try:
        import httpx
    except ImportError:  # pragma: no cover - 운영 · 개발 모두 설치돼 있다
        return False
    return isinstance(
        e, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)
    )


def attempt_once(
    bas_dd: str,
    *,
    key: str,
    fetch: Callable[[str, str], list[dict[str, Any]]],
    db_path: Optional[Path],
    at: datetime,
) -> tuple[dict[str, Any], Optional[list[dict[str, Any]]]]:
    """한 날짜 1회 조회 → 검사 → 저장 → read-back. 반환 `(기록, 성공 응답)`."""
    entry: dict[str, Any] = {
        "at_kst": _as_kst(at).isoformat(timespec="seconds"),
        "target": bas_dd,
        "http": None,
        "rows": 0,
        "priced_rows": 0,
        "result": None,
        "error_type": None,
    }
    try:
        rows = fetch(bas_dd, key) or []
    except Exception as e:  # noqa: BLE001 - 시도 실패로 기록하고 다음 시도로
        entry.update(result=R_FETCH_ERROR, error_type=type(e).__name__)
        entry["http"] = _http_status(e)
        entry["transient"] = is_transient_fetch_error(e)
        return entry, None
    # 기본 fetcher 는 `raise_for_status` 를 통과해야 돌아온다(2xx).
    entry["http"] = 200
    entry["rows"] = len(rows)
    entry["priced_rows"] = sum(1 for r in rows if (r.get("TDD_CLSPRC") or "").strip())
    try:
        result, detail, snapshot = check_response(rows, bas_dd=bas_dd, db_path=db_path)
        entry.update(detail)
        if snapshot is None:
            entry["result"] = result
            return entry, None
        entry["result"] = _save_and_read_back(snapshot, bas_dd, db_path, entry)
    except sqlite3.Error as e:
        entry.update(result=R_STORE_ERROR, error_type=type(e).__name__)
    return entry, (rows if entry["result"] == R_OK else None)


def _save_and_read_back(
    snapshot: list[krx_store.SnapshotRow],
    bas_dd: str,
    db_path: Optional[Path],
    entry: dict[str, Any],
) -> str:
    """조건 ⑤ — 저장 뒤 다시 읽은 행(종목 · 종가 · 건수)이 이번 snapshot 과 같아야 성공.

    같은 날짜가 이미 **같은 내용**이면 다시 쓰지 않는다. 다르면(판정 전 중단으로 남은 부분
    저장 · 다른 값) 한 트랜잭션에서 바꿔 쓴다 — 판정 기록과 저장 행이 어긋난 채 성공하지
    않게(검증자 r1 A-1). 판정까지 끝난 T-1 은 여기 오지 않는다(already_loaded · 확정 계약 2).
    read-back 이 어긋나면 그 날짜를 비운다(부분 snapshot 을 남기지 않는다 · fail-closed).
    """
    iso = iso_date(bas_dd)
    want = {r.ticker: float(r.close) for r in snapshot}
    have = krx_store.rows_on(iso, db_path=db_path)
    if have == want:
        entry["write"] = "kept_existing"
        entry["readback_rows"] = len(have)
        return R_OK
    if have:
        written = krx_store.replace_date(snapshot, db_path=db_path)
        entry["write"] = "replaced"
        entry["replaced_rows"] = len(have)
    else:
        written = krx_store.upsert_snapshot(snapshot, db_path=db_path)
        entry["write"] = "inserted"
    back = krx_store.rows_on(iso, db_path=db_path)
    entry["rows_written"] = written
    entry["readback_rows"] = len(back)
    if back != want or written != len(snapshot):
        krx_store.delete_date(iso, db_path=db_path)
        entry["write"] = "rolled_back"
        return R_READBACK
    return R_OK


# ── 적재 뒤 대표 ETF 커버리지(설계자 RESULT STEP 2 · 적재 성공과 별개) ─────────


def load_required_representatives(
    *, runtime_db_path: Optional[Path] = None
) -> Optional[list[str]]:
    """활성 장중 설정의 사업군 **대표** ticker(대체 제외). 읽을 수 없으면 `None`.

    장중 경로(`intraday_alert_flow._load_active_sectors`)와 같은 저장소를 **읽기만**
    한다. 정책 `enabled` 와 무관하다 — 대표 정의는 번들에 있다. 대표 없는 사업군이
    있으면 전체 목록을 모르므로 `None` 이다(`representatives.representative_tickers`).
    """
    try:
        from app.intraday_config import store

        active = store.get_active(db_path=runtime_db_path)
        if not active:
            return None
        payload = json.loads(active["payload_json"])
        uni = payload.get("sector_representative_universe") or {}
        return reps_mod.representative_tickers(uni.get("sectors"))
    except Exception:  # noqa: BLE001 - 설정을 못 읽어도 배치를 멈추지 않는다
        return None


def evaluate_representatives(
    target_iso: str,
    *,
    db_path: Optional[Path],
    required_tickers: Optional[Sequence[str]] = None,
    runtime_db_path: Optional[Path] = None,
) -> dict[str, Any]:
    """적재된 T-1 행에 활성 대표가 모두 있는가. **예외를 올리지 않는다 · 쓰지 않는다.**

    반환 `{status, source, expected_previous_trading_day, count, missing,
    representatives_refresh_due}`. 장중 「신규 진입 검토」 관문과 같은 규칙이다
    (`representatives.evaluate_coverage`). 정합성 JSON(`refresh_due` · CSV 갱신
    안내)은 건드리지 않는다.
    """
    if required_tickers is not None:
        required: Optional[list[str]] = list(required_tickers) or None
        source = REQUIRED_FROM_ARGUMENT
    else:
        required = load_required_representatives(runtime_db_path=runtime_db_path)
        source = REQUIRED_FROM_CONFIG if required else REQUIRED_UNAVAILABLE
    if not required:
        cov = reps_mod.evaluate_coverage(None, (), expected=target_iso)
        return {"source": source, **cov.to_dict()}
    try:
        have = krx_store.closes_on([target_iso], db_path=db_path).get(target_iso) or {}
    except Exception as e:  # noqa: BLE001 - 성공한 적재 결과를 뒤집지 않는다
        return {
            "source": source,
            "status": COVERAGE_NOT_EVALUATED,
            "expected_previous_trading_day": target_iso,
            "count": len(set(required)),
            "missing": [],
            "error_type": type(e).__name__,
            "representatives_refresh_due": None,
        }
    cov = reps_mod.evaluate_coverage(required, have.keys(), expected=target_iso)
    return {"source": source, **cov.to_dict()}


__all__ = [
    "COVERAGE_NOT_EVALUATED",
    "MIN_ROW_RATIO",
    "R_BASIS_MISMATCH",
    "R_FETCH_ERROR",
    "R_INVALID",
    "R_NOT_PUBLISHED",
    "R_OK",
    "R_READBACK",
    "R_ROW_DROP",
    "R_STORE_ERROR",
    "attempt_once",
    "check_response",
    "evaluate_representatives",
    "http_status",
    "iso_date",
    "is_transient_fetch_error",
    "load_required_representatives",
    "relation_violation",
]
