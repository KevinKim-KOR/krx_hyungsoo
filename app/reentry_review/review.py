"""POC5-06 — 재진입 검토 조립 · ML 실행 · 연구 산출물(설계 개정 2 §2 · §3 · §6 · §10-5).

```text
읽기 기준  보유 = 한 번 읽은 유효 문서(revision · 문서 hash) · 가격 = 한 mode=ro 읽기 트랜잭션
          (05 시장 흐름도 같은 연결) · 원장 = 한 읽기 트랜잭션 — 분산 트랜잭션은 만들지 않는다
선택 검증  position_id · cycle_id 를 그 문서에서 함께 찾는다(없으면 LookupError → 404) ·
          ticker 는 서버 문서의 값만 쓴다
GET       내 거래 · 저장된 근거(05 시장 흐름 · 최근 가격 상태 · 원장) — 학습 · 외부 조회 · 쓰기 0
POST      ML 1회 → state/ml/research/poc5_06/<생성시각>_<id>/{review.json, input_snapshot.json}
          임시 폴더에 두 파일을 다 쓴 뒤 이름을 바꾼다(반쪽 폴더를 남기지 않음) ·
          저장 실패 = ArtifactSaveError(정상 완료로 보이지 않는다)
```
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Callable, Optional

from app import holdings_history_view as history_view
from app import holdings_market_flow as market_flow
from app import holdings_store as store
from app import trading_day_lag as tdl
from app.market_briefing import calendar as cal
from app.reentry_review import ledger
from app.reentry_review import model
from app.reentry_review import models as M
from app.reentry_review import prices
from app.three_push_runtime import ledger_outcome_prices as lop

RESEARCH_ROOT = Path(
    "state/ml/research/poc5_06"
)  # 호출 때 읽는다(테스트가 tmp 로 바꾼다)
_KST = timezone(timedelta(hours=9))
_ANCHORS = ("BASELINE", "REGISTER")


class ReviewReadError(Exception):
    """시세 DB 를 읽을 수 없다(파일은 있는데 읽기 오류) — 정상 '자료 없음'과 구분한다."""


class ArtifactSaveError(Exception):
    """연구 산출물 저장 실패 — 결과를 정상 완료로 보이지 않는다."""


# ── 선택 · 내 거래 ────────────────────────────────────────────────────────────


def _select(position_id: str, cycle_id: str) -> dict[str, Any]:
    state = store.read_document()
    doc = state["doc"]
    hist = history_view.history_of(state, position_id)
    pos = next((p for p in hist["positions"] if p["position_id"] == position_id), None)
    cyc = None
    if pos is not None:
        cyc = next((c for c in pos["cycles"] if c["cycle_id"] == cycle_id), None)
    if pos is None or cyc is None:
        raise LookupError(
            "보유가 바뀌었거나 없는 보유 기간입니다 — History 를 다시 여세요."
        )
    ticker, flow_cycle = history_view.market_flow_input_of(doc, position_id, cycle_id)
    return {
        "state_status": state["status"],
        "revision": doc["revision"],
        "doc_sha256": prices.canonical_hash(doc),
        "position": pos,
        "cycle": cyc,
        "ticker": ticker,
        "flow_cycle": flow_cycle,
    }


def _my_trades(sel: dict[str, Any]) -> dict[str, Any]:
    pos, cyc = sel["position"], sel["cycle"]
    ids = [c["cycle_id"] for c in pos["cycles"]]
    sells = [e for e in cyc["events"] if e["kind"] == "SELL"]
    last_sell = max((e["payload"]["trade_date"] for e in sells), default=None)
    notes = []
    if cyc["opened_by"] in _ANCHORS:
        notes.append(
            "매수일 미상 — 기준잔고 · 잔고 등록으로 시작한 기간(입력 평단 기준)"
        )
    if cyc["closed_by"] == "ADJUSTMENT":
        notes.append(
            "입력 정정으로 종료 — 정정일은 매도일이 아니며 매도 손익을 만들지 않습니다"
        )
    if cyc["has_adjustment"]:
        notes.append("입력 정정 포함 — 기간 합계는 참고 계산")
    return {
        "position": pos,
        "selected_cycle_id": cyc["cycle_id"],
        "previous_cycle_ids": ids[: ids.index(cyc["cycle_id"])],
        "summary": {
            "status": cyc["status"],
            "opened_by": cyc["opened_by"],
            "closed_by": cyc["closed_by"],
            "purchase_date_unknown": cyc["opened_by"] in _ANCHORS,
            "closed_by_adjustment": cyc["closed_by"] == "ADJUSTMENT",
            "last_actual_sell_date": last_sell,
            "has_adjustment": cyc["has_adjustment"],
        },
        "notes": notes,
    }


# ── 시세 DB(한 읽기 트랜잭션) ─────────────────────────────────────────────────


def _with_market(work: Callable[[Optional[sqlite3.Connection]], Any]) -> Any:
    try:
        con: Optional[sqlite3.Connection] = lop.open_ro(lop.market_db_path())
    except FileNotFoundError:
        con = None  # 파일 없음 = 자료 없음(만들지 않는다)
    except sqlite3.Error as e:
        raise ReviewReadError(f"market_db_open_failed:{type(e).__name__}") from e
    try:
        if con is not None:
            con.execute("BEGIN")
        result = work(con)
        if con is not None:
            con.execute("ROLLBACK")
        return result
    except (sqlite3.Error, market_flow.MarketFlowReadError) as e:
        raise ReviewReadError(f"market_db_read_failed:{type(e).__name__}") from e
    finally:
        if con is not None:
            con.close()


def _price_input(con: Optional[sqlite3.Connection], ticker: str) -> dict[str, Any]:
    if con is None:
        return {"status": M.NO_PRICE, "reason": "시세 DB 파일 없음"}
    etf = prices.is_etf(con, ticker)
    if etf is None:  # 확인 불가 ≠ 개별주
        return {
            "status": M.NO_PRICE,
            "reason": "ETF 목록(etf_master) 없음 — ETF 여부 확인 불가",
        }
    if etf is False:
        return {"status": M.NOT_ETF, "reason": "ETF 아님(개별주)"}
    rows = prices.read_rows(con, ticker)
    if not rows:
        return {"status": M.NO_PRICE, "reason": "이 ETF 의 저장 종가 없음"}
    return {"status": None, "rows": rows, "kospi": prices.read_kospi_dates(con)}


def _prepare(pin: dict[str, Any], today: str) -> dict[str, Any]:
    """가격 입력 → 연구 축 · 축 위 계열 · 최신성. status 가 None 이면 계산 가능."""
    rows = pin["rows"]
    t = rows[-1].date
    axis = prices.research_axis(
        t, rows[0].date, pin["kospi"], calendar_dir=cal.CALENDAR_DIR
    )
    expected = tdl.expected_previous_trading_day(today, calendar_dir=cal.CALENDAR_DIR)
    out: dict[str, Any] = {
        "t": t,
        "axis": axis,
        "expected_completed_date": expected,
        "stale": bool(expected and t < expected),
        "latest_close": rows[-1].close,
        "latest_source": rows[-1].source,
    }
    problem = prices.axis_problem(t, axis)
    if problem:
        out.update(status=M.AXIS_UNCERTAIN, reason=problem, series=None)
        return out
    out.update(status=None, reason=None, series=prices.AxisSeries(axis["dates"], rows))
    return out


def _axis_view(axis: dict[str, Any]) -> dict[str, Any]:
    dates = axis["dates"]
    return {
        "label": axis["label"],
        "limit_note": axis["limit_note"],
        "rule": axis["rule"],
        "modes": axis["modes"],
        "skipped_weekday_count": axis["skipped_weekday_count"],
        "kospi_latest": axis["kospi_latest"],
        "length": len(dates),
        "first": dates[0] if dates else None,
        "last": dates[-1] if dates else None,
    }


def _price_state(prep: dict[str, Any]) -> dict[str, Any]:
    """최근 가격 상태(검토 창 · 학습 없음) — 기준일 feature 다섯 값."""
    view = {
        "t": prep["t"],
        "latest_close": prep["latest_close"],
        "latest_source": prep["latest_source"],
        "expected_completed_date": prep["expected_completed_date"],
        "stale": prep["stale"],
        "stale_note": M.STALE_NOTE if prep["stale"] else None,
        "price_basis_label": prices.PRICE_BASIS_LABEL,
        "partial_check_note": prices.PARTIAL_CHECK_NOTE,
        "axis": _axis_view(prep["axis"]),
        "features": None,
    }
    if prep["status"] is not None:
        return {**view, "status": prep["status"], "reason": prep["reason"]}
    series = prep["series"]
    T = len(series.dates) - 1
    problem = model.t_window_problem(series, T)
    if problem is not None:
        return {**view, "status": problem[0], "reason": problem[1]}
    feats = model.features_at(series.closes, T)
    return {
        **view,
        "status": M.OK,
        "reason": None,
        "features": dict(zip(model.FEATURE_NAMES, feats)),
    }


# ── GET: 검토 창 ─────────────────────────────────────────────────────────────


def build_review(position_id: str, cycle_id: str) -> dict[str, Any]:
    """검토 창 내용 — 학습 · 외부 조회 · 쓰기 0."""
    sel = _select(position_id, cycle_id)
    ticker = sel["ticker"]
    today = store.today_kst()

    def work(con: Optional[sqlite3.Connection]) -> tuple[dict, dict]:
        flow = market_flow.build_market_flow(
            ticker=ticker,
            cycle=sel["flow_cycle"],
            calendar_dir=cal.CALENDAR_DIR,
            connection=con,
        )
        pin = _price_input(con, ticker)
        if pin["status"] is not None:
            return flow, {"status": pin["status"], "reason": pin["reason"]}
        return flow, _price_state(_prepare(pin, today))

    flow, price_state = _with_market(work)
    evidence = ledger.ticker_ledger_evidence(ticker)
    pos = sel["position"]
    return {
        "schema": M.SCHEMA,
        "read_only": True,
        "selection": {
            "position_id": position_id,
            "cycle_id": cycle_id,
            "ticker": ticker,
            "name": pos["name"],
            "account_group": pos["account_group"],
        },
        "read_basis": {
            "holdings_status": sel["state_status"],
            "revision": sel["revision"],
            "doc_sha256": sel["doc_sha256"],
            "ledger_synced_at": evidence["synced_at"],
            "price_latest": price_state.get("t"),
        },
        "my_trades": _my_trades(sel),
        "stored_evidence": {
            "market_flow": flow,
            "price_state": price_state,
            "ledger": evidence,
        },
        "ml": {
            "available": price_state["status"] not in (M.NOT_ETF, M.NO_PRICE),
            "target_name": M.TARGET_NAME,
            "note": M.RESEARCH_NOTE,
        },
        "navigation": list(M.NAVIGATION),
        "notes": list(M.NOTES),
    }


# ── POST: ML 1회 ─────────────────────────────────────────────────────────────


def _versions() -> dict[str, Optional[str]]:
    out: dict[str, Optional[str]] = {}
    for dist in ("scikit-learn", "numpy"):
        try:
            out[dist] = metadata.version(dist)
        except metadata.PackageNotFoundError:
            out[dist] = None
    return out


def run_ml(position_id: str, cycle_id: str) -> dict[str, Any]:
    """선택 ETF 하나의 D20 연구 1회 → 결과 + 연구 산출물. 저장 실패는 ArtifactSaveError."""
    started = time.perf_counter()
    created = datetime.now(_KST)
    sel = _select(position_id, cycle_id)
    ticker = sel["ticker"]
    today = store.today_kst()
    pin = _with_market(lambda con: _price_input(con, ticker))
    evidence = ledger.ticker_ledger_evidence(ticker)

    result: dict[str, Any]
    snapshot_prices: list[dict[str, Any]] = []
    axis_view = None
    prep: dict[str, Any] = {}
    if pin["status"] is not None:
        result = {"status": pin["status"], "reason": pin["reason"]}
    else:
        snapshot_prices = [r.as_json() for r in pin["rows"]]
        prep = _prepare(pin, today)
        axis_view = _axis_view(prep["axis"])
        if prep["status"] is not None:
            result = {"status": prep["status"], "reason": prep["reason"]}
        else:
            result = model.evaluate(prep["series"], prep["t"])

    axis = prep.get("axis") or {}
    hash_input = {
        "ticker": ticker,
        "t": prep.get("t"),
        "prices": snapshot_prices,
        "axis": {
            "dates": axis.get("dates", []),
            "modes": axis.get("modes", {}),
            "skipped_weekdays": axis.get("skipped_weekdays", []),
            "kospi_latest": axis.get("kospi_latest"),
        },
        "recipe": model.RECIPE,
    }
    digest = prices.canonical_hash(hash_input)
    status = result["status"]
    response: dict[str, Any] = {
        "schema": M.SCHEMA,
        "status": status,
        "status_text": M.STATUS_TEXT.get(status, status),
        "reason": result.get("reason"),
        "ticker": ticker,
        "target_name": M.TARGET_NAME,
        "t": prep.get("t"),
        "expected_completed_date": prep.get("expected_completed_date"),
        "stale": prep.get("stale", False),
        "stale_note": M.STALE_NOTE if prep.get("stale") else None,
        "result": result,
        "axis": axis_view,
        "price_basis_label": prices.PRICE_BASIS_LABEL,
        "partial_check_note": prices.PARTIAL_CHECK_NOTE,
        "recipe": model.RECIPE,
        "canonical_sha256": digest,
        "read_basis": {
            "holdings_status": sel["state_status"],
            "revision": sel["revision"],
            "doc_sha256": sel["doc_sha256"],
            "ledger_synced_at": evidence["synced_at"],
            "price_latest": prep.get("t"),
        },
        "libraries": _versions(),
        "notes": list(M.NOTES),
        "runtime_seconds": round(time.perf_counter() - started, 3),
    }
    review_doc = {
        **response,
        "created_at": created.isoformat(timespec="seconds"),
        "selection": {
            "position_id": position_id,
            "cycle_id": cycle_id,
            "ticker": ticker,
            "account_group": sel["position"]["account_group"],
        },
        "facts": _my_trades(sel)["summary"],
    }
    snapshot_doc = {
        "canonical_sha256": digest,
        "hash_input": hash_input,
        "selected_cycle": sel["cycle"],
        "axis_label": prices.AXIS_LABEL,
        "axis_limit_note": prices.AXIS_LIMIT_NOTE,
        "price_basis_label": prices.PRICE_BASIS_LABEL,
        "ledger_ids": ledger.snapshot_ids(evidence),
        "ledger_status": evidence["status"],
        "ledger_status_text": evidence.get("status_text"),
    }
    response["artifact"] = _write_artifacts(created, review_doc, snapshot_doc)
    return response


def _write_artifacts(
    created: datetime, review_doc: dict, snapshot_doc: dict
) -> dict[str, str]:
    root = Path(RESEARCH_ROOT)
    name = f"{created.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    folder = root / name
    staging = root / f".{name}.partial"  # 두 파일을 다 쓴 뒤에만 보이는 이름으로 바꾼다
    made = False
    try:
        root.mkdir(parents=True, exist_ok=True)
        staging.mkdir(exist_ok=False)
        made = True
        for fname, body in (
            ("review.json", review_doc),
            ("input_snapshot.json", snapshot_doc),
        ):
            text = json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True)
            (staging / fname).write_text(text + "\n", encoding="utf-8")
        os.rename(staging, folder)
    except OSError as e:
        if made:  # 이 호출이 만든 임시 폴더만 지운다
            shutil.rmtree(staging, ignore_errors=True)
        raise ArtifactSaveError(f"연구 산출물 저장 실패: {type(e).__name__}") from e
    return {"folder": str(folder), "files": "review.json · input_snapshot.json"}
