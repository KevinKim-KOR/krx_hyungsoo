"""ETF 구성종목 상태 읽기(POC6-31 STEP 1 · PLAN C3 · C4 · 판정 §1 셋째 · 넷째).

'최근 시도'(수집 기록의 목표일 · 확인 시각 · 결과)와 '지금 보존한 구성'(원천일이 확인된 마지막 구성의 날짜)을
따로 읽는다. 서버를 다시 켜도 저장 자료만으로 같은 상태가 나온다. 읽기 전용 연결만 쓴다(쓰기 0).

원천일 확인 = 수집 기록에 상태 'ok' · 문구 `source_date_confirmed:<내용 지문>` 이 있고, **지금 읽은 그 (ETF, 구성일)
행의 내용 지문이 그 지문과 같을 때만**이다(검증자 r2 F5 — 시각 비교는 쓰지 않음: 기존 저장 경로는 잠금을 얻기 전에
시각을 정해 순서를 믿을 수 없다. 확인 뒤 다른 경로가 행을 바꾸면 지문이 달라져 미확인). 확인 판정과 행 읽기는 한
읽기 트랜잭션에서 한다(읽는 사이 덮어쓰기가 끼어들지 않게).
POC6-31 이전 저장분은 이 표시가 없어 모두 '원천 기준일 미확인'으로 본다(PLAN §8-1 · 날짜 출처를 구분할 기록이 없음).
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Optional

from app.etf_constituents_fetcher import NAVER_STOCK_SOURCE
from app.etf_constituents_store import (  # noqa: F401 — SOURCE_CONFIRMED 는 이 모듈 이름으로도 씀(다시 내보내기)
    COMPLETE_SUFFIX,
    CONFIRM_PREFIX,
    ROW_SQL,
    SOURCE_CONFIRMED,
    ConstituentRow,
    fingerprint,
    read_rows,
)

# 원천일 확인 표시 정의(문구 머리 · 지문 칸 · 지문)는 저장 모듈에 있다(쓰는 쪽과 같은 정의 · 검증자 r3 F7).
_CONFIRM_PREFIX = CONFIRM_PREFIX
_ROW_SQL = ROW_SQL


def row_tuple(r: ConstituentRow) -> tuple:
    """지문용 한 행(`_ROW_SQL` 과 같은 순서)."""
    return (
        int(r.rank),
        r.constituent_ticker,
        r.constituent_name,
        r.weight_pct,
        r.etf_name,
        r.constituent_key,
        r.constituent_isin,
        r.constituent_reuters_code,
        r.market_type,
    )


def confirmation_message(rows: Iterable[ConstituentRow], complete: bool = False) -> str:
    """원천일 확인 기록 문구 = `source_date_confirmed:<그 행들의 내용 지문>` — **시험 · 자료 심기용**.

    저장 전 값으로 계산한다. 운영 저장은 `replace_constituents_snapshot(confirm=True)` 가 저장 직후 DB 에서 다시 읽은
    행으로 계산한다(검증자 r3 F7 — 저장 표현 차이).
    """
    return (
        _CONFIRM_PREFIX
        + fingerprint(row_tuple(r) for r in rows)
        + (COMPLETE_SUFFIX if complete else "")
    )


# 수집 기록 상태(asof = 수집 목표일). 'unavailable' · 'skipped_timeout' 은 기존 값 그대로 쓴다.
LOG_OK = "ok"
LOG_FAILED = "unavailable"
LOG_TIMEOUT = "skipped_timeout"
LOG_TARGET_WAIT = "target_wait"
LOG_LOCKED = "save_locked"
LOG_NO_SOURCE_DATE = "no_source_date"

# 결과 코드(작업 응답 · 상태 읽기 공통)
EXISTING = "existing"
FETCHED = "fetched"
TARGET_WAIT = "target_wait"
FAILED = "failed"
TIMEOUT = "timeout"
LOCKED = "locked"
NO_SOURCE_DATE = "no_source_date"
NOT_CHECKED = "not_checked"  # 상태 읽기 전용 — 이 목표일로 아직 확인하지 않음

RESULT_LABEL = {
    EXISTING: "기존 자료",
    FETCHED: "새로 받음",
    TARGET_WAIT: "목표일 자료 대기",
    FAILED: "받기 실패",
    TIMEOUT: "시간 초과로 조회 안 함",
    LOCKED: "저장 잠김",
    NO_SOURCE_DATE: "원천 기준일 미확인",
    NOT_CHECKED: "아직 확인 안 함",
}
RESULT_REASON = {
    EXISTING: "목표일 이상 구성이 이미 있음 · 이번 조회 없음",
    FETCHED: "원천에서 새로 받음",
    TARGET_WAIT: "원천이 아직 목표일보다 이전 구성을 줌 · 다음 갱신 때 다시 확인",
    FAILED: "원천에서 받지 못함 · 다음 갱신 때 다시 확인",
    TIMEOUT: "이번 묶음 시간 예산이 끝나 부르지 않음 · 다음 갱신 때 다시 확인",
    LOCKED: "자료 저장소가 잠겨 읽거나 저장하지 못함 · 다음 갱신 때 다시 확인",
    NO_SOURCE_DATE: "원천 응답에 맞는 구성 기준일이 없어(없음 · 잘못된 날짜 · 오늘 뒤 날짜) 저장하지 않음 · 다음 갱신 때 다시 확인",
    NOT_CHECKED: "이 목표일로 아직 확인하지 않음",
}
# '갱신 실패'로 묶는 결과(화면 완료 줄 · 판정 §4 M1)
UPDATE_FAILED = (FAILED, TIMEOUT, LOCKED, NO_SOURCE_DATE)
# 다음 명시적 갱신 때 다시 확인하는 결과(판정 §1 셋째)
NEEDS_CHECK = frozenset(
    {TARGET_WAIT, FAILED, TIMEOUT, LOCKED, NO_SOURCE_DATE, NOT_CHECKED}
)

_LOG_TO_RESULT = {
    LOG_TARGET_WAIT: TARGET_WAIT,
    LOG_FAILED: FAILED,
    LOG_TIMEOUT: TIMEOUT,
    LOG_LOCKED: LOCKED,
    LOG_NO_SOURCE_DATE: NO_SOURCE_DATE,
}


def _ro(db_path: Path) -> Optional[sqlite3.Connection]:
    p = Path(db_path)
    if not p.exists():
        return None
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)


def _has_tables(con: sqlite3.Connection) -> bool:
    names = {
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN "
            "('etf_constituents', 'etf_constituent_refresh_log')"
        )
    }
    return names == {"etf_constituents", "etf_constituent_refresh_log"}


def _marks(seq: Iterable[str]) -> str:
    return ",".join("?" for _ in seq)


def _confirm_marks(con: sqlite3.Connection, tks: list[str]) -> dict:
    """(ETF, 구성일) → {원천일 확인 기록의 내용 지문: 원천 전체 표시 여부}.

    POC6-31 STEP 4(검토 지적 backend#0) — 기록 끝의 원천 전체 표시(`COMPLETE_SUFFIX`)는 떼고 지문 부분만 대조한다. 같은 지문의
    기록 중 하나라도 원천 전체 표시가 있으면 True(표시 없는 예전 기록 = 원천 전체인지 모름 = False).
    """
    marks: dict[tuple[str, str], dict[str, bool]] = defaultdict(dict)
    for etf, asof, message in con.execute(
        "SELECT etf_ticker, asof, message FROM etf_constituent_refresh_log "
        "WHERE status = ? AND substr(message, 1, ?) = ? "
        f"AND etf_ticker IN ({_marks(tks)})",
        (LOG_OK, len(_CONFIRM_PREFIX), _CONFIRM_PREFIX, *tks),
    ):
        body = message.removeprefix(_CONFIRM_PREFIX)
        complete = body.endswith(COMPLETE_SUFFIX)
        fp = body.removesuffix(COMPLETE_SUFFIX)
        marks[(etf, asof)][fp] = marks[(etf, asof)].get(fp, False) or complete
    return marks


def _snapshot_rows(con: sqlite3.Connection, etf: str, asof: str) -> list[tuple]:
    return list(
        con.execute(
            f"SELECT {_ROW_SQL} FROM etf_constituents "
            "WHERE etf_ticker = ? AND asof = ? AND source = ? ORDER BY rank ASC",
            (etf, asof, NAVER_STOCK_SOURCE),
        )
    )


def read_analysis_rows(
    tickers: Iterable[str], *, asof: Optional[str], db_path: Path
) -> tuple[dict[str, str], dict[str, tuple[list[ConstituentRow], bool]]]:
    """분석이 쓸 ETF별 날짜 · 행 · 원천일 확인을 **한 읽기 트랜잭션**에서 읽는다(검증자 r3 F8 — 확인 지문과 행을 따로
    읽으면 그 사이 정상 재수집이 끝난 새 행을 이전 지문과 대조해 미확인으로 잘못 표시).

    asof 를 주면 모든 ETF를 그 날짜로(그 날짜의 확인 기록 · 검증자 r2 F6), 비우면 ETF마다 마지막 구성일(네이버 출처 ·
    네이버 자료가 없는 ETF는 그 ETF 모든 출처의 마지막 구성일 · 검증자 r4 F9).
    돌려줌 = ({ETF: 날짜}, {ETF: (행 · 모든 출처 · 순위순, 원천일 확인)}) · 자료 없는 ETF는 둘 다 빠짐.
    원천일 확인 = 읽은 행 전체의 지문이 그 (ETF, 날짜)의 확인 지문 중 하나와 같을 때.
    """
    tks = list(dict.fromkeys(t for t in tickers if t))
    con = _ro(db_path) if tks else None
    if con is None:
        return {}, {}
    with closing(con):
        con.execute("BEGIN")
        return analysis_rows_in(con, tks, asof=asof)


def analysis_rows_in(
    con: sqlite3.Connection, tickers: Iterable[str], *, asof: Optional[str]
) -> tuple[dict[str, str], dict[str, tuple[list[ConstituentRow], bool]]]:
    """`read_analysis_rows` 의 읽기 본문 — 부르는 쪽이 연 읽기 트랜잭션 안에서 읽는다(POC6-32 r1 F1 · 한 응답이 구성 ·
    확인 기록 · ETF 목록을 한 번에 읽게). 돌려줌 · 날짜 규칙은 `read_analysis_rows` 와 같다."""
    tks = list(dict.fromkeys(t for t in tickers if t))
    dates: dict[str, str] = {}
    out: dict[str, tuple[list[ConstituentRow], bool]] = {}
    if not tks or not _has_tables(con):
        return dates, out
    if asof:
        dates = {t: asof for t in tks}
    else:
        # ETF마다 네이버 마지막 구성일 · 네이버 자료가 없으면 그 ETF 모든 출처의 마지막 구성일(검증자 r4 F9 —
        # 예전 출처로만 저장된 ETF도 빠지지 않고 그 날짜로 보이며 원천 기준일 미확인으로 구분된다).
        naver: dict[str, str] = {}
        any_src: dict[str, str] = {}
        for etf, src, d in con.execute(
            "SELECT etf_ticker, source, MAX(asof) FROM etf_constituents "
            f"WHERE etf_ticker IN ({_marks(tks)}) GROUP BY etf_ticker, source",
            tks,
        ):
            if src == NAVER_STOCK_SOURCE:
                naver[etf] = d
            if etf not in any_src or d > any_src[etf]:
                any_src[etf] = d
        dates = {t: naver.get(t, any_src[t]) for t in tks if t in any_src}
    marks = _confirm_marks(con, tks)
    for t, d in dates.items():
        rows = read_rows(con, etf_ticker=t, asof=d)
        if not rows:
            continue
        ok = fingerprint(row_tuple(r) for r in rows) in marks.get((t, d), {})
        out[t] = (rows, ok)
    if not asof:
        dates = {t: d for t, d in dates.items() if t in out}
    return dates, out


def read_snapshots(
    tickers: Iterable[str], *, db_path: Path
) -> dict[str, dict[str, Any]]:
    """ETF마다 {confirmed, latest, last_attempt}.

    confirmed = 원천일 확인된 마지막 구성(+ `data` = 그 확인에 쓴 행 · 같은 트랜잭션에서 읽음) ·
    latest = 저장된 마지막 구성 · last_attempt = 마지막 기록(기록 순서 = rowid · 없으면 None).

    구성 = {asof, rows, saved_at}. 기록 = {asof, status, message, created_at}.
    원천일 확인은 모듈 머리 설명(내용 지문 대조 · 한 읽기 트랜잭션 · 검증자 r2 F5).
    """
    tks = sorted({t for t in tickers if t})
    con = _ro(db_path) if tks else None
    if con is None:
        return {
            t: {"confirmed": None, "latest": None, "last_attempt": None} for t in tks
        }
    with closing(con):
        # 한 읽기 트랜잭션(공유 잠금 유지) — 구성 목록 · 확인 지문 · 행 · 기록을 같은 시점으로 읽는다.
        con.execute("BEGIN")
        return snapshots_in(con, tks)


def snapshots_in(
    con: sqlite3.Connection, tickers: Iterable[str]
) -> dict[str, dict[str, Any]]:
    """`read_snapshots` 의 읽기 본문 — 부르는 쪽이 연 읽기 트랜잭션 안에서 읽는다(POC6-32 r1 F1 · 한 응답이 구성 ·
    확인 기록 · ETF 목록을 한 번에 읽게). 돌려줌 모양은 `read_snapshots` 와 같다."""
    tks = sorted({t for t in tickers if t})
    out: dict[str, dict[str, Any]] = {
        t: {"confirmed": None, "latest": None, "last_attempt": None} for t in tks
    }
    if not tks or not _has_tables(con):
        return out
    snaps: dict[tuple[str, str], dict[str, Any]] = {}
    for etf, asof, n, saved in con.execute(
        "SELECT etf_ticker, asof, COUNT(*), MAX(created_at) FROM etf_constituents "
        f"WHERE source = ? AND etf_ticker IN ({_marks(tks)}) GROUP BY etf_ticker, asof",
        (NAVER_STOCK_SOURCE, *tks),
    ):
        snaps[(etf, asof)] = {"asof": asof, "rows": int(n), "saved_at": saved}
    marks = _confirm_marks(con, tks)
    for (etf, asof), snap in snaps.items():
        cur = out[etf]
        if cur["latest"] is None or asof > cur["latest"]["asof"]:
            cur["latest"] = snap
    for etf in tks:
        dates = sorted(
            (a for (e, a) in snaps if e == etf and (e, a) in marks), reverse=True
        )
        for asof in dates:
            rows = _snapshot_rows(con, etf, asof)
            fp = fingerprint(rows)
            if fp in marks[(etf, asof)]:
                out[etf]["confirmed"] = {
                    **snaps[(etf, asof)],
                    "data": rows,
                    # 원천이 준 전체(확인 기록 끝 표시) — 없는 주식 = 0(확인) 판정에 씀(STEP 4)
                    "complete": marks[(etf, asof)][fp],
                }
                break
    for etf, asof, status, message, created in con.execute(
        "SELECT etf_ticker, asof, status, message, created_at "
        f"FROM etf_constituent_refresh_log WHERE etf_ticker IN ({_marks(tks)}) "
        "ORDER BY rowid ASC",
        tks,
    ):
        out[etf]["last_attempt"] = {
            "asof": asof,
            "status": status,
            "message": message,
            "created_at": created,
        }
    return out


def judge(snap: dict[str, Any], target_date: str) -> dict[str, Any]:
    """한 ETF의 상태 — 목표일 기준. 결과 코드 · 실제 구성일 · 보존 자료 · 최근 확인."""
    conf = snap.get("confirmed")
    latest = snap.get("latest")
    att = snap.get("last_attempt")
    if conf is not None and conf["asof"] >= target_date:
        result = EXISTING
    elif (
        att is not None
        and att["asof"] == target_date
        and att["status"] in _LOG_TO_RESULT
    ):
        result = _LOG_TO_RESULT[att["status"]]
    else:
        result = NOT_CHECKED
    kept = conf or latest
    return {
        "result": result,
        "label": RESULT_LABEL[result],
        "reason": RESULT_REASON[result],
        "source_asof": conf["asof"] if conf else None,
        "rows": conf["rows"] if conf else None,
        "kept_asof": kept["asof"] if kept else None,
        "kept_confirmed": bool(conf) and kept is conf,
        "last_checked_at": att["created_at"] if att else None,
        "needs_check": result in NEEDS_CHECK,
    }


def read_status(
    tickers: Iterable[str], *, target_date: str, db_path: Path
) -> dict[str, dict[str, Any]]:
    """여러 ETF의 상태(목표일 기준 · 저장 자료만 · 읽기 전용)."""
    snaps = read_snapshots(tickers, db_path=db_path)
    return {t: judge(s, target_date) for t, s in snaps.items()}


# 저장 상태를 읽지 못함(잠김) — '갱신 필요 없음'과 섞지 않는다(화면은 '읽지 못함'으로 보인다).
READ_FAILED = "read_failed"
READ_LOCKED_TEXT = (
    "자료 저장소가 잠겨 구성 상태를 읽지 못했습니다 — 잠시 뒤 다시 읽어 주세요"
)
HOLDINGS_ACTION = "[최신 자료 갱신]"
CANDIDATES_ACTION = "[구성종목 수집]"


def _md(iso_day: Optional[str]) -> Optional[str]:
    if not iso_day:
        return None
    try:
        d = date.fromisoformat(iso_day)
    except ValueError:
        return iso_day
    return f"{d.month}/{d.day}"


def not_checked_reason(
    item: dict[str, Any], target_date: str, action: str = HOLDINGS_ACTION
) -> str:
    """'아직 확인 안 함'의 이유 — 자료 없음 · 예전 자료(원천 기준일 미확인) · 목표일 이전 구성."""
    kept = item.get("kept_asof")
    if not kept:
        return f"구성 자료 없음 — {action}에서 받습니다"
    if not item.get("kept_confirmed"):
        return (
            f"예전 자료 {_md(kept)} · 원천 기준일 미확인 — {action}에서 다시 확인합니다"
        )
    return f"{_md(kept)} 구성 · 목표일 {_md(target_date)} 자료 아직 확인 안 함 — {action}에서 받습니다"


def is_locked_error(e: BaseException) -> bool:
    return isinstance(e, sqlite3.OperationalError) and "locked" in str(e).lower()


def stored_status(
    tickers: list[str],
    *,
    target_date: str,
    db_path: Path,
    action: str,
    names: Optional[dict[str, Optional[str]]] = None,
) -> dict[str, Any]:
    """ETF별 저장 상태 묶음 {status, reason, total, needs_check, counts, items} — 읽기 전용.

    잠김으로 읽지 못하면 status='read_failed'(개수 0 으로 '할 일 없음'처럼 보이지 않게 따로 표시).
    """
    out: dict[str, Any] = {
        "status": "ok",
        "reason": None,
        "total": 0,
        "needs_check": 0,
        "counts": {k: 0 for k in RESULT_LABEL},
        "items": [],
    }
    try:
        st = read_status(tickers, target_date=target_date, db_path=db_path)
    except sqlite3.OperationalError as e:
        if not is_locked_error(e):
            raise
        out.update(status=READ_FAILED, reason=READ_LOCKED_TEXT)
        return out
    items = []
    for t in tickers:
        it = {"ticker": t, "name": (names or {}).get(t), **st[t]}
        if it["result"] == NOT_CHECKED:
            it["reason"] = not_checked_reason(it, target_date, action)
        items.append(it)
        out["counts"][it["result"]] += 1
    out["items"] = items
    out["total"] = len(items)
    out["needs_check"] = sum(1 for it in items if it["needs_check"])
    return out
