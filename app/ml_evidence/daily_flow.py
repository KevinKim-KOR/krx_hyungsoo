"""POC6-05 — 원/달러 · WTI · 코스피 수급(POC6-01 함수 그대로 + capture · 표 반영 전에 보관).

받은 값(FX 계열 하나 · 수급 날짜 하나)마다 **그 자리에서 object 로 확정 저장(fsync · 내용 해시 이름)** 한 뒤에
함수가 표에 반영한다. 저장이 실패하면 그 값은 upsert 하지 않는다(판정 §3 · §6). 압축 버퍼에만 두지 않는다.
OCI DB 새 쓰기 = POC6-01 과 같은 스키마의 `market_macro_daily` · `market_investor_flow_daily` 뿐(판정 Q2).
보관과 표 반영이 엇갈리면 `mismatch` 로 남긴다(성공으로 감추지 않음).
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Optional

from app import supply_fx_oil_refresh as flow_refresh
from app.ml_evidence import store

FX_SEMANTICS = (
    "Yahoo 완료 일봉(POC6-01 규칙) · 최근 90일 겹침 · 받은 값을 표 반영 전에 보관"
)
FLOW_SEMANTICS = "키움 ka10051 코스피 순매수 13분류(억원 → 원) · 최근 20거래일 겹침 · 받은 값을 표 반영 전에 보관"


class FlowCapture:
    """POC6-01 수집 함수의 capture — 받은 값마다 object 하나(확정 저장 실패 = 예외 = 그 값 upsert 0)."""

    def __init__(
        self, root: Path, add: Callable[..., Any], now: Callable[[], datetime]
    ) -> None:
        self._root, self._add, self._now = root, add, now
        self.fx: dict[str, dict] = {}
        self.fx_failed: dict[str, str] = {}
        self.planned: Optional[list[str]] = None
        self.received: dict[str, str] = {}
        self.failed: dict[str, str] = {}
        self.stop: Optional[str] = None

    def _keep(self, payload: dict, role: str) -> str:
        info = store.put_bytes(self._root, store.canonical(payload))
        return self._add(info, role, "json")

    def fx_received(self, series_id: str, rows, since: date) -> None:
        at = store.iso(self._now())
        rows = [[d, v] for d, v in rows]
        line = {"series_id": series_id, "since": since.isoformat(), "observed_at": at}
        sha = self._keep(line | {"rows": rows}, "fx_wti_received")
        self.fx[series_id] = {
            "object": sha,
            "rows": len(rows),
            "observed_at": at,
            "first": rows[0][0] if rows else None,
            "last": rows[-1][0] if rows else None,
        }

    def fx_fail(self, series_id: str, reason: str) -> None:
        self.fx_failed[series_id] = reason

    def flow_planned(self, want) -> None:
        self.planned = list(want)

    def flow_received(self, d: str, nets: dict, index_close: float) -> None:
        at = store.iso(self._now())
        payload = {
            "date": d,
            "observed_at": at,
            "index_close": index_close,
            "nets": nets,
        }
        self.received[d] = self._keep(payload, "investor_flow_received")

    def flow_failed(self, d: str, reason: str) -> None:
        self.failed[d] = reason

    def flow_stopped(self, reason: Optional[str]) -> None:
        self.stop = reason


def fx_section(cap: FlowCapture, failed, error) -> dict:
    series = {}
    for sid, label in flow_refresh.SERIES_LABEL.items():
        got = cap.fx.get(sid)
        bad = error is not None or (failed is not None and label in failed)
        if got and not bad:
            state = "OK"
        elif got:
            state = "UPSERT_FAILED"  # 보관됨 · 표 반영 실패 = 엇갈림
        elif sid in cap.fx_failed:
            state = "FETCH_OR_KEEP_FAILED"
        else:
            state = "NOT_ATTEMPTED"
        series[sid] = {
            "state": state,
            "received": got,
            "reason": cap.fx_failed.get(sid) or (error if not got else None),
            "mismatch": state == "UPSERT_FAILED",
        }
    states = [s["state"] for s in series.values()]
    if all(x == "OK" for x in states):
        status = "OK"
    else:
        status = "PARTIAL" if cap.fx else "FAILED"
    return {
        "status": status,
        "series": series,
        "objects": [s["received"]["object"] for s in series.values() if s["received"]],
        "error": error,
        "semantics": FX_SEMANTICS,
    }


def flow_section(cap: FlowCapture, ret, error, kospi: list, target) -> dict:
    """미시도는 계획 안(멈춤 사유)과 계획 밖(KOSPI 저장일 없음 · 기록만)을 나눈다."""
    extra = []
    if target and target not in kospi:
        extra.append(
            {
                "date": target,
                "reason": "KOSPI 저장일 없음(08:10 배치가 아직 저장하지 않음 · 주말엔 다음 거래일 08:10) — 계획 밖 미시도",
            }
        )
    if cap.planned is None:
        return {
            "status": "FAILED",
            "reason": ret or error or "조회 계획 없음",
            "planned": 0,
            "not_attempted_extra": extra,
            "objects": [],
            "semantics": FLOW_SEMANTICS,
        }
    rest = [x for x in cap.planned if x not in cap.received and x not in cap.failed]
    upsert_failed = error is not None and bool(cap.received)
    if not cap.received:
        status = "FAILED"
    elif rest or cap.failed or upsert_failed:
        status = "PARTIAL"
    else:
        status = "OK"
    return {
        "status": status,
        "planned": len(cap.planned),
        "received": sorted(cap.received),
        "failed": cap.failed,
        "not_attempted": [{"date": x, "reason": cap.stop or "멈춤"} for x in rest],
        "not_attempted_extra": extra,
        "objects": [cap.received[d] for d in sorted(cap.received)],
        "db_upsert": (
            "FAILED" if upsert_failed else ("OK" if cap.received else "NOT_RUN")
        ),
        "mismatch": upsert_failed,
        "message": ret,
        "error": error,
        "semantics": FLOW_SEMANTICS,
    }


def run_market_flow(
    *,
    root: Path,
    db_path: Path,
    deps: Any,
    kospi: list[str],
    today: date,
    target: Optional[str],
    add: Callable[..., Any],
) -> dict:
    cap = FlowCapture(root, add, deps.now)
    start = flow_refresh.collection_start(kospi, today)
    fx_failed, fx_error, flow_ret, flow_error = None, None, None, None
    try:
        fx_failed = flow_refresh.refresh_fx_wti(
            db_path=db_path,
            now_utc=deps.now(),
            start=start,
            http_get=deps.fx_http_get,
            capture=cap,
        )
    except Exception as e:  # noqa: BLE001 — 하위 단계마다 격리
        fx_error = type(e).__name__
    try:
        flow_ret = flow_refresh.refresh_investor_flows(
            db_path=db_path,
            now_utc=deps.now(),
            start=start,
            client=deps.kiwoom_client,
            sleep=deps.sleep,
            capture=cap,
        )
    except Exception as e:  # noqa: BLE001 — 표 반영 실패 등
        flow_error = type(e).__name__
    return {
        "fx_wti": fx_section(cap, fx_failed, fx_error),
        "investor_flow": flow_section(cap, flow_ret, flow_error, kospi, target),
    }
