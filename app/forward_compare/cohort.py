"""POC6-06 — 고정 표본 cohort_v1(설계 §2 · PLAN §1 · 판정 §3-2).

입력은 두 가지뿐이다: PC 에 가져온 05 ETF 목록 판 하나(object 해시 고정) · PC 시장 DB `etf_daily_price` 의
기준일 이하 유효 종가 저장일 수(mode=ro 읽기). 보유 · seed · 수익률 · D20 · 오차 · 평가 유무는 읽지 않는다.
결과가 PLAN 표(`protocol.EXPECTED_COHORT`)와 다르면 쓰지 않고 멈춘다(자동 재선정 없음). 한 번 쓰면 다시 순위를
매기지 않는다 — 이후에는 `load` 가 파일을 읽어 고정 목록을 확인만 한다.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.forward_compare import protocol as P
from app.ml_evidence import daily_naver, store

LIST_RUN = "20261022T103723Z_5cae0dd9"
LIST_OBJECT = "78c5bcd47968498d4b0aab3e3527e18927d001aa98c02933463178d42df06824"
LIST_HASH = "cbbd8259dc6ed79846e363bcc10c5cdc293aa082411c1c7fe0886e64ed3a17de"
BASE_DAY = "2026-10-21"  # 목록 판의 05 기준 거래일(이하 저장일만 센다)
COUNT_SQL = (
    "SELECT ticker, COUNT(*) FROM etf_daily_price WHERE date <= ?"
    " AND close IS NOT NULL AND close > 0 GROUP BY ticker"
)
NOT_USED = ["보유", "seed", "수익률", "D20", "모델 오차", "사용자 평가 · 관심도"]


class CohortError(Exception):
    """선정 입력 · 결과가 고정 계약과 다름(쓰지 않고 멈춤)."""


def path(root: Path) -> Path:
    return root / P.COHORT_ID / "cohort.json"


def _list_ref(ev_root: Path) -> tuple[dict[str, Any], list[dict]]:
    runs, _ = store.list_runs(ev_root)
    run = next((r for r in runs if r.run_id == LIST_RUN), None)
    if run is None or not store.object_ok(ev_root, LIST_OBJECT):
        raise CohortError("기준 목록 판(05 묶음 · object)이 PC 보관소에 없거나 손상")
    eff = run.manifest["sources"]["etf_list"]["effective"]
    if eff.get("object") != LIST_OBJECT or eff.get("list_hash") != LIST_HASH:
        raise CohortError("05 묶음의 목록 참조가 고정 판과 다름")
    body = json.loads(store.read_object(ev_root, LIST_OBJECT))
    rows = body["rows"]
    if daily_naver.list_hash(rows) != LIST_HASH:
        raise CohortError("목록 내용 해시가 고정 판과 다름")
    receipt = run.receipt or {}
    ref = {
        "run_id": LIST_RUN,
        "object": LIST_OBJECT,
        "list_hash": LIST_HASH,
        "count": len(rows),
        "list_date": eff.get("list_date"),
        "observed_at": body.get("observed_at"),
        "available_at": run.manifest["published_at"],
        "copied_at_pc": receipt.get("copied_at_pc"),
        "source": body.get("source"),
    }
    return ref, rows


def stored_days(db_path: Path, tickers: set[str]) -> dict[str, int]:
    """기준일 이하 유효 종가 저장일 수(mode=ro · 같은 읽기 한 번)."""
    con = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    try:
        got = dict(con.execute(COUNT_SQL, (BASE_DAY,)).fetchall())
    finally:
        con.close()
    return {t: int(got[t]) for t in sorted(tickers) if t in got}


def compute(ev_root: Path, db_path: Path) -> dict[str, Any]:
    ref, rows = _list_ref(ev_root)
    names = {r["ticker"]: r.get("name") for r in rows}
    days = stored_days(db_path, set(names))
    cands = {t: n for t, n in days.items() if n >= P.MIN_DAYS}
    order = sorted(cands, key=P.cohort_rank_key)[: P.COHORT_SIZE]
    selected = [
        {
            "rank": i + 1,
            "ticker": t,
            "sha256": P.cohort_rank_key(t)[0],
            "stored_days": cands[t],
            "name": names.get(t),
        }
        for i, t in enumerate(order)
    ]
    return {
        "list": ref,
        "base_day": BASE_DAY,
        "stored_days_source": {
            "table": "etf_daily_price",
            "read": "sqlite mode=ro",
            "query": COUNT_SQL,
            "list_tickers_in_table": len(days),
        },
        "candidates": cands,
        "candidate_count": len(cands),
        "selected": selected,
    }


@P.exclusive
def select(root: Path, ev_root: Path, db_path: Path, now: datetime) -> tuple[str, dict]:
    """cohort_v1 고정. 이미 있으면 다시 순위를 매기지 않고 확인만 한다."""
    if path(root).exists():
        return "ALREADY", load(root)
    got = compute(ev_root, db_path)
    tickers = tuple(s["ticker"] for s in got["selected"])
    if tickers != P.EXPECTED_COHORT:
        raise CohortError(
            f"선정 결과가 PLAN 표와 다름(후보 {got['candidate_count']}) — 쓰지 않음 · 원인 확인 필요"
        )
    body = P.doc(
        "cohort",
        cohort_id=P.COHORT_ID,
        rule=(
            f"목록 판 안에서 기준일 이하 유효 종가 저장일 ≥ {P.MIN_DAYS} → "
            f'SHA-256("{P.PROTOCOL_ID}:" + ticker) 오름차순 · 동률 ticker 순 앞 {P.COHORT_SIZE}'
        ),
        ticker_rule="원래 ETF 식별 문자열 6자(영숫자 · 정수 변환 · 문자 제거 없음)",
        not_used=NOT_USED,
        selected_at=store.iso(now),
        tickers=list(tickers),
        aux_groups=P.aux_groups(list(tickers)),
        **got,
    )
    P.write_once(path(root), P.dumps(body))
    return "OK", body


def load(root: Path) -> dict[str, Any]:
    """고정 cohort 를 읽고 계약(24종 · 순서 · schema)을 확인한다."""
    body = P.read_json(path(root))
    if (
        body.get("schema") != P.SCHEMAS["cohort"]
        or body.get("protocol_id") != P.PROTOCOL_ID
    ):
        raise CohortError("cohort 파일 schema 다름")
    if tuple(body.get("tickers", ())) != P.EXPECTED_COHORT:
        raise CohortError("cohort 파일의 목록이 고정 표와 다름")
    return body
