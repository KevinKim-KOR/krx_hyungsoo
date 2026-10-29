"""POC6-13 — 06 산출물 읽기만(오늘 06 실행 기록 · 필요한 D · 주 기록 완료 판정 · 보관 대기 · PLAN §3-2).

완료 판정은 06 의 `records.primaries`(영수증 해시 · id · D 일치 · confirmed_at < close_cutoff_at 인 주 기록만)를
그대로 쓴다. 필요한 D 는 오늘 KST 의 06 실행 기록이 정한 값이다(자체 달력 · 가격 계산 없음 · 판정 §5-1).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.forward_compare import archive as A06
from app.forward_compare import cohort as C06
from app.forward_compare import protocol as P06
from app.forward_compare import records as R06
from app.ml_evidence import store


def runs_on(root: Path, day: str) -> list[dict[str, Any]]:
    """06 실행 기록 중 today_kst == day(수동 · 자동 모두) · 끝난 시각 순."""
    out = []
    base = Path(root) / "runs"
    for f in sorted(base.glob("*.json")) if base.is_dir() else []:
        try:
            d = P06.read_json(f)
        except (OSError, ValueError):
            continue
        if (
            isinstance(d, dict)
            and d.get("protocol_id") == P06.PROTOCOL_ID
            and d.get("today_kst") == day
        ):
            out.append(d)
    out.sort(key=lambda d: (str(d.get("finished_at") or ""), str(d.get("id") or "")))
    return out


def run_doc(root: Path, run_id: Optional[str]) -> Optional[dict[str, Any]]:
    if not run_id:
        return None
    f = Path(root) / "runs" / f"{run_id}.json"
    try:
        return P06.read_json(f) if f.is_file() else None
    except (OSError, ValueError):
        return None


def needed_d(runs: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """오늘 06 기록 중 D 가 있는 가장 늦은 것 — 06 이 이번 입력 · 달력으로 정한 '오늘 필요한 D'."""
    for d in reversed(runs):
        if d.get("D"):
            return {
                "D": d["D"],
                "close_cutoff_at": d.get("close_cutoff_at"),
                "next_trading_day": d.get("next_trading_day"),
                "run_id": d.get("id"),
            }
    return None


def completion(root: Path, D: str) -> dict[str, Any]:
    """D 의 cohort 전 종목에 마감 전 영수증이 있는 주 기록 · 네 방법 OK 인가(실제 분모 · 부분 성공은 미완료)."""
    cohort = C06.load(root)
    docs = [
        d
        for d in R06.prediction_docs(root)
        if d.get("cohort_id") == cohort["cohort_id"]
    ]
    prims = R06.primaries(root, docs)
    tickers = list(cohort["tickers"])
    recorded, failed, visible = [], [], []
    for t in tickers:
        p = prims.get((t, D))
        if p is None:
            continue
        recorded.append(t)
        visible.append(p["visible_by"])
        bad = sorted(
            m for m in P06.METHODS if (p["methods"].get(m) or {}).get("status") != "OK"
        )
        if bad:
            failed.append({"ticker": t, "methods": bad})
    return {
        "D": D,
        "cohort_id": cohort["cohort_id"],
        "total": len(tickers),
        "recorded": len(recorded),
        "missing": [t for t in tickers if t not in recorded],
        "method_failed": failed,
        "first_visible": min(visible, default=None),
        "last_visible": max(visible, default=None),
        "done": len(recorded) == len(tickers) and not failed,
    }


def archive_pending(root: Path, ev: Path, confirmed: set[str]) -> dict[str, Any]:
    """미등록 산출물 수 · 등록됐지만 자동화가 업로드 OK 를 받은 적 없는 06 묶음(= 보관 대기)."""
    st = A06.local_state(root, ev)
    _, ids = A06.registered(ev)
    unconfirmed = [i for i in ids if i not in confirmed]
    return {
        "unregistered": st["unregistered"],
        "registered": len(ids),
        "unconfirmed": unconfirmed,
        "not_allowed": st["not_allowed"],
        "pending": st["unregistered"] > 0 or bool(unconfirmed),
    }


def parse_time(text: Any):
    try:
        return store.parse_iso(text)
    except (ValueError, TypeError):
        return None
