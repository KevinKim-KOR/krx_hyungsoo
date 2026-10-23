"""POC6-06 — 주 전향 기록의 성숙 목표 연결(설계 §8 · 판정 §4-4 · §4-5).

처음 계산한 목표 판을 `targets/<D>/<ticker>.json` 에 한 번만 쓴다(이후 정정 판이 와도 바꾸지 않음).
아직 못 정한 상태(PENDING_NOT_DUE · PENDING_CALENDAR · DUE_DATA_MISSING · DATA_CHECK_REQUIRED)는 파일을 쓰지
않고 회차 기록에만 남긴다 — 다음 실행에서 늦게 가져온 보관본으로 다시 본다(받은 값이 없다고 0 · 상승으로 두지 않음).
진단 · 부가 기록은 성숙 평가 대상이 아니다.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from app.forward_compare import inputs
from app.forward_compare import protocol as P
from app.forward_compare import records
from app.ml_evidence import store
from app.reentry_review import model as m06

STATES = (
    "MATURED",
    "PENDING_NOT_DUE",
    "PENDING_CALENDAR",
    "DUE_DATA_MISSING",
    "DATA_CHECK_REQUIRED",
)


def evaluate(
    root: Path, ev: inputs.Evidence, clock: Callable[[], datetime], run_id: str
) -> dict[str, Any]:
    prims = records.primaries(root)
    fixed = records.targets(root)
    counts = {s: 0 for s in STATES}
    counts["ALREADY_FIXED"] = 0
    open_items = []
    for (ticker, D), prim in sorted(prims.items()):
        if (ticker, D) in fixed:
            counts["ALREADY_FIXED"] += 1
            continue
        got = ev.select_target(ticker, D)
        counts[got["status"]] += 1
        if got["status"] != "MATURED":
            open_items.append(
                {
                    "ticker": ticker,
                    "D": D,
                    "status": got["status"],
                    "tried": got.get("tried"),
                }
            )
            continue
        base_pred = prim["input"]["base_close"]
        base_tgt = got["closes"][0][1]
        body = P.doc(
            "target",
            ticker=ticker,
            D=D,
            status="MATURED",
            definition=m06.RECIPE["target"],
            unit="ratio(−0.05 = −5%)",
            target=got["target"],
            target_end=got["target_end"],
            closes=got["closes"],
            source=got["source"],
            evaluation={
                "run_id": run_id,
                "cutoff": store.iso(ev.cutoff),
                "inventory_runs": len(ev.runs),
            },
            prediction_run=prim["run_id"],
            base_close_prediction=base_pred,
            base_close_target=base_tgt,
            base_close_differs=base_pred != base_tgt,
            tried_before=got["tried"],
            computed_at=store.iso(clock()),
        )
        P.write_once(records.target_path(root, ticker, D), P.dumps(body))
    return {"counts": counts, "open": open_items}
