"""POC5-03 — 받은 알림 기록 조회 조립(PC 사본 읽기만 · SSH 0).

PLAN `docs/ai_plan/POC5/POC5-03_PC_LEDGER_SYNC_AND_FEEDBACK_PLAN_V1.md` §2-4 · §8 · §10(설계 개정 2).

```text
목록        선택 날짜(runtime_date_kst)의 FINALIZED run 중 delivery_status ∈ {sent, partial}
            · 종류 필터 market · holdings · intraday · 카드 = 시각 · 종류 · 전달 상태 · 핵심 item(disposition sent)
기본 날짜    날짜를 주지 않으면 사본에서 sent · partial 알림이 있는 가장 최근 날짜(전체 종류) · 없으면 오늘 KST
상세        원문 · item 전체 · feedback 이력 · 가격 결과 — 평가(feedback) 유무와 무관하게 조회한다(개정 2)
결과 대상    event = cohort PRIMARY_LIVE ∧ off_schedule 0 · item = 그 event ∧ evaluable 1 ∧
            subject ∈ POC5-02 성숙 대상(ticker · sector · market(SP500 만) · index_group)
            — 아니면 '결과 대상 아님'
partial     body_text 는 분할 전 전체 생성 본문 — body_partial_delivery = True 로 '일부만 전달됨' 표기를 요구한다
이름        PC 보유 목록 name → PC 시장 DB etf_master name(읽기 전용) → 없으면 코드 그대로
상태 이름    알림 본문이 쓰는 기존 라벨표를 종류별로 고른다(D10_PLUS 가 급락 · 보유 하락 양쪽에 있어 섞지 않음)
            · 라벨이 없으면(시장 전망 UP · DOWN 등) 코드 그대로
```
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app import holdings, market_data_store
from app.runtime_evidence import holdings_risk, holdings_selection, sector_signal
from app.ledger_copy import store
from app.three_push_runtime import ledger_outcome
from app.three_push_runtime.ledger_market import SP500_SUBJECT

KINDS = {
    "market": "market_briefing",
    "holdings": "holdings_briefing",
    "intraday": "holdings_risk_alert",
}
PRIMARY_COHORT = "PRIMARY_LIVE"
OUTCOME_SUBJECTS = ledger_outcome._TARGET_KINDS  # POC5-02 성숙 대상과 한 곳에서 맞춘다
HOLDINGS_FILE = holdings.HOLDINGS_FILE  # 호출 때 읽는다(테스트가 바꿔 끼운다)
MARKET_DB = market_data_store.DEFAULT_DB_PATH  # 〃

_KST = timezone(timedelta(hours=9))
_RISK_LABELS = {**holdings_risk.RISK_STATE_LABEL, **holdings_risk.SURGE_STATE_LABEL}

_OUTCOME_COLUMNS = (
    "item_seq",
    "series_id",
    "horizon",
    "status",
    "t0_price",
    "t0_price_asof",
    "eval_date",
    "eval_price",
    "return_raw",
    "max_up_raw",
    "max_down_raw",
    "path_points",
)


def name_map() -> dict[str, str]:
    """ticker → 이름. 읽기 전용 · 실패해도 빈 값(코드를 그대로 보인다)."""
    out: dict[str, str] = {}
    try:
        con = sqlite3.connect(f"file:{Path(MARKET_DB)}?mode=ro", uri=True, timeout=2.0)
        try:
            for t, n in con.execute("SELECT ticker, name FROM etf_master"):
                if t and n:
                    out[str(t)] = str(n)
        finally:
            con.close()
    except sqlite3.Error:
        pass
    try:
        data = json.loads(Path(HOLDINGS_FILE).read_text(encoding="utf-8"))
        # POC5-05: 이력 문서는 공용 판정을 거친다(손상 · 이력 불일치 문서의 이름은 쓰지 않음).
        if holdings.is_history_document(data):
            rows = [
                {"ticker": h.ticker, "name": h.name}
                for h in holdings.holdings_from_document(data)
            ]
        else:
            rows = data.get("holdings") or []
        for h in rows:
            if isinstance(h, dict) and h.get("ticker") and h.get("name"):
                out[str(h["ticker"])] = str(h["name"])
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    return out


def today_kst() -> str:
    return datetime.now(_KST).date().isoformat()


def _hhmm(runtime_kst: Optional[str]) -> Optional[str]:
    s = runtime_kst or ""
    return s[11:16] if len(s) >= 16 else None


def _name(kind: str, subject_id: str, names: dict[str, str]) -> Optional[str]:
    return names.get(subject_id) if kind == "ticker" else None


def _series_name(series_id: str, names: dict[str, str]) -> str:
    prefix, _, code = series_id.partition(":")
    if prefix == "benchmark":
        return code
    return names.get(code, code)


def state_label(
    push_kind: str, subject_kind: str, state: Optional[str]
) -> Optional[str]:
    """알림 본문이 쓰는 기존 상태 라벨. 없으면 코드 그대로(None 은 None)."""
    if state is None:
        return None
    if subject_kind == "sector":
        labels: dict[str, str] = sector_signal.STATE_LABEL
    elif subject_kind == "ticker" and push_kind == "holdings_briefing":
        labels = holdings_selection.DECLINE_STATE_LABEL
    elif subject_kind == "ticker" and push_kind == "holdings_risk_alert":
        labels = _RISK_LABELS
    else:
        labels = {}
    return labels.get(state, state)


def event_target(cohort: Optional[str], off_schedule: Any) -> bool:
    return cohort == PRIMARY_COHORT and int(off_schedule or 0) == 0


def item_target(
    event_ok: bool, subject_kind: str, subject_id: str, evaluable: Any
) -> bool:
    if subject_kind == "market" and subject_id != SP500_SUBJECT:
        return False  # POC5-02 `_load_targets` 와 같다(market 은 SP500 → KOSPI 만)
    return event_ok and int(evaluable or 0) == 1 and subject_kind in OUTCOME_SUBJECTS


def _feedback_rows(con: sqlite3.Connection, event_id: str) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in con.execute(
            "SELECT feedback_seq, helpfulness, action, memo, feedback_at FROM user_feedback"
            " WHERE event_id = ? ORDER BY feedback_seq",
            (event_id,),
        )
    ]


def latest_alert_date(con: sqlite3.Connection) -> Optional[str]:
    """사본에서 sent · partial 알림이 있는 가장 최근 날짜(전체 종류). 없으면 None."""
    row = con.execute(
        "SELECT MAX(r.runtime_date_kst) FROM evaluation_run r"
        " JOIN delivery d ON d.event_id = r.event_id"
        " WHERE r.run_state = ? AND d.delivery_status IN (?, ?)",
        ("FINALIZED", *store.FEEDBACK_DELIVERY),
    ).fetchone()
    return None if row is None else row[0]


def list_alerts(
    day: Optional[str],
    kind: str = "all",
    *,
    path: Optional[Path] = None,
    names: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """선택 날짜 · 종류의 sent · partial 알림 카드 + 동기화 상태. day=None 이면 기본 날짜."""
    names = name_map() if names is None else names
    sql = (
        "SELECT r.event_id, r.push_kind, r.runtime_kst, r.schedule_expected, r.off_schedule,"
        " d.delivery_status FROM evaluation_run r JOIN delivery d ON d.event_id = r.event_id"
        " WHERE r.run_state = ? AND r.runtime_date_kst = ?"
        " AND d.delivery_status IN (?, ?)"
    )
    params: list[Any] = ["FINALIZED", None, *store.FEEDBACK_DELIVERY]
    if kind != "all":
        sql += " AND r.push_kind = ?"
        params.append(KINDS[kind])
    sql += " ORDER BY r.runtime_kst, r.started_at, r.event_id"
    con = store.connect(path)
    try:
        status = store.sync_status(con)
        if day is None:
            day = latest_alert_date(con) or today_kst()
        params[1] = day
        alerts = []
        for r in con.execute(sql, params).fetchall():
            key = [
                {
                    "subject_kind": k["subject_kind"],
                    "subject_id": k["subject_id"],
                    "name": _name(k["subject_kind"], k["subject_id"], names),
                }
                for k in con.execute(
                    "SELECT subject_kind, subject_id FROM signal_item"
                    " WHERE event_id = ? AND disposition = 'sent' ORDER BY item_seq",
                    (r["event_id"],),
                )
            ]
            fb = _feedback_rows(con, r["event_id"])
            alerts.append(
                {
                    "event_id": r["event_id"],
                    "push_kind": r["push_kind"],
                    "time_kst": _hhmm(r["runtime_kst"]),
                    "schedule_expected": r["schedule_expected"],
                    "off_schedule": bool(r["off_schedule"]),
                    "delivery_status": r["delivery_status"],
                    "key_items": key,
                    "latest_feedback": fb[-1] if fb else None,
                    "feedback_count": len(fb),
                }
            )
    finally:
        con.close()
    return {"date": day, "kind": kind, "sync": status, "alerts": alerts}


def alert_detail(
    event_id: str,
    *,
    path: Optional[Path] = None,
    names: Optional[dict[str, str]] = None,
) -> Optional[dict[str, Any]]:
    """한 알림의 원문 · item · feedback 이력 · 가격 결과. 로컬에 없으면 None."""
    names = name_map() if names is None else names
    con = store.connect(path)
    try:
        run = con.execute(
            "SELECT event_id, push_kind, runtime_kst, runtime_date_kst, schedule_expected,"
            " off_schedule, cohort FROM evaluation_run WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if run is None:
            return None
        d = con.execute(
            "SELECT delivery_status, body_text, body_withheld FROM delivery WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        ev_ok = event_target(run["cohort"], run["off_schedule"])
        items = [
            {
                "item_seq": i["item_seq"],
                "subject_kind": i["subject_kind"],
                "subject_id": i["subject_id"],
                "name": _name(i["subject_kind"], i["subject_id"], names),
                "held": i["held"],
                "state": i["state"],
                "prev_state": i["prev_state"],
                "state_label": state_label(
                    run["push_kind"], i["subject_kind"], i["state"]
                ),
                "prev_state_label": state_label(
                    run["push_kind"], i["subject_kind"], i["prev_state"]
                ),
                "disposition": i["disposition"],
                "event_type": i["event_type"],
                "t0_price": i["t0_price"],
                "t0_price_asof": i["t0_price_asof"],
                "evaluable": bool(i["evaluable"]),
                "outcome_target": item_target(
                    ev_ok, i["subject_kind"], i["subject_id"], i["evaluable"]
                ),
            }
            for i in con.execute(
                "SELECT item_seq, subject_kind, subject_id, held, state, prev_state,"
                " disposition, event_type, t0_price, t0_price_asof, evaluable"
                " FROM signal_item WHERE event_id = ? ORDER BY item_seq",
                (event_id,),
            )
        ]
        fb = _feedback_rows(con, event_id)
        # 평가(feedback) 유무와 무관하게 조회한다(개정 2 — 결과 조회에 평가 조건 없음).
        outcomes = [
            {
                **dict(o),
                "series_name": _series_name(o["series_id"], names),
            }
            for o in con.execute(
                f"SELECT {', '.join(_OUTCOME_COLUMNS)} FROM price_outcome"
                " WHERE event_id = ? ORDER BY item_seq, series_id, horizon",
                (event_id,),
            )
        ]
    finally:
        con.close()
    return {
        "event_id": run["event_id"],
        "push_kind": run["push_kind"],
        "time_kst": _hhmm(run["runtime_kst"]),
        "runtime_date_kst": run["runtime_date_kst"],
        "schedule_expected": run["schedule_expected"],
        "off_schedule": bool(run["off_schedule"]),
        "outcome_event_target": ev_ok,
        "delivery_status": None if d is None else d["delivery_status"],
        "body_text": None if d is None else d["body_text"],
        "body_withheld": False if d is None else bool(d["body_withheld"]),
        "body_partial_delivery": d is not None and d["delivery_status"] == "partial",
        "items": items,
        "feedback": fb,
        "outcomes": outcomes,
    }
