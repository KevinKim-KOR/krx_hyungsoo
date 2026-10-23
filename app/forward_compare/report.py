"""POC6-06 — 같은 행 · 날짜 균형 MAE 비교 보고(설계 §9 · 판정 §3-1 보조 표).

```text
주 지표   날짜마다 공통 유효 종목의 |예측 − 실제| 평균(%p) → 날짜 평균(종목 수 많은 날 가중 없음)
비교      HGB vs MEDIAN · RIDGE = 세 방법 + 목표가 모두 있는 행 · MLP_CPU vs 두 기준 = 그 세 방법의 행
          HGB vs MLP_CPU 직접 = 네 방법 모두 있는 행만 · 비교별 행 · 날짜 수와 빠진 행 수
분모      cohort 24 · 입력 · 예측(방법별) · 성숙 · 실제 비교 행 · 행이 없으면 MAE = null(0 · 기각 아님)
보조      종목별 · 달별 · 모델 판별 · D20 ≤ −8% 행의 MAE · max(예측 − 실제, 0) 평균 · 사전 고정 3 묶음
```

주 기록(FORWARD_RESEARCH · 마감 전 공개)만 센다. 진단 · 부가 기록은 개수만 따로 적는다. 결과는 월별 갱신 recipe 의
누적이며 단일 가중치 성과가 아니다. 20일 목표가 겹치므로 행 수는 독립 사건 수가 아니다.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Callable, Optional

from app.forward_compare import protocol as P
from app.forward_compare import records
from app.ml_evidence import store

COMPARISONS = {
    "HGB_vs_MEDIAN_RIDGE": ("HGB", "MEDIAN", "RIDGE"),
    "MLP_CPU_vs_MEDIAN_RIDGE": ("MLP_CPU", "MEDIAN", "RIDGE"),
    "ALL_FOUR": ("MEDIAN", "RIDGE", "HGB", "MLP_CPU"),
}
DEEP = -0.08
NOTES = [
    "월별 갱신 recipe 의 누적 결과 — 단일 고정 가중치의 성과가 아님(행마다 평가한 model_version 표시)",
    "20일 목표가 겹침 — 행 수는 독립 사건 수가 아님 · 신뢰구간 · 유의성 검정 없음",
    "D20 ≤ −8% 행의 max(예측 − 실제, 0) = 큰 하락을 작게 추정한 정도(매매 수익률 · 사전 감지율 아님)",
    "결과를 보고 표본 · 국면을 고르지 않음 · 이전 5% 개선 gate 를 자동 합격선으로 쓰지 않음",
    "보조 묶음은 이름으로 관찰한 분리 관측 — 유형 판정 · 안전 전제 아님 · 주 표를 대신하지 않음",
]


def date_balanced(rows: list[dict], method: str) -> Optional[float]:
    by: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        by[r["D"]].append(abs(r["preds"][method] - r["truth"]) * 100.0)
    per = [sum(v) / len(v) for v in by.values()]
    return sum(per) / len(per) if per else None


def compare(rows: list[dict], methods: tuple, deep: bool = True) -> dict[str, Any]:
    same = [r for r in rows if all(m in r["preds"] for m in methods)]
    out: dict[str, Any] = {
        "rows": len(same),
        "dates": len({r["D"] for r in same}),
        "tickers": len({r["ticker"] for r in same}),
        "excluded_rows": len(rows) - len(same),
        "mae_pp": {m: date_balanced(same, m) for m in methods},
    }
    if deep:
        d = [r for r in same if r["truth"] <= DEEP]
        out["deep_loss_le_8pct"] = {
            "rows": len(d),
            "mae_pp": {m: date_balanced(d, m) for m in methods},
            "under_estimate_pp": {
                m: (
                    sum(max(r["preds"][m] - r["truth"], 0.0) for r in d)
                    * 100.0
                    / len(d)
                    if d
                    else None
                )
                for m in methods
            },
        }
    return out


def _by(rows: list[dict], key: Callable[[dict], str]) -> dict[str, dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    return {
        k: {name: compare(v, ms, deep=False) for name, ms in COMPARISONS.items()}
        for k, v in sorted(groups.items())
    }


def _months_later(d: str, n: int) -> str:
    x = date.fromisoformat(d)
    y, m = divmod(x.month - 1 + n, 12)
    year, mon = x.year + y, m + 1
    last = [
        31,
        29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ]
    return date(year, mon, min(x.day, last[mon - 1])).isoformat()


def build(root: Path, cohort: dict[str, Any]) -> dict[str, Any]:
    docs = records.prediction_docs(root)
    prims = records.primaries(root, docs)
    tgts = records.targets(root)
    rows = []
    for (t, D), p in sorted(prims.items()):
        tg = tgts.get((t, D))
        if tg is None:
            continue
        preds = {
            m: v["pred"] for m, v in p["methods"].items() if v.get("status") == "OK"
        }
        rows.append(
            {
                "ticker": t,
                "D": D,
                "truth": tg["target"],
                "preds": preds,
                "model_version": p["model_version"],
                "month": D[:7],
            }
        )
    forward_days = sorted({D for (_, D) in prims})
    counts = {
        "cohort": len(cohort["tickers"]),
        "forward_dates": len(forward_days),
        "primary_records": len(prims),
        "predicted_by_method": {
            m: sum(
                1
                for p in prims.values()
                if p["methods"].get(m, {}).get("status") == "OK"
            )
            for m in P.METHODS
        },
        "matured": len(rows),
        "pending_or_missing": len(prims) - len(rows),
        "diagnostic_entries": sum(
            len(d["entries"]) for d in docs if d["record_type"] == records.DIAGNOSTIC
        ),
        "supplementary_entries": sum(
            1 for d in docs for e in d["entries"] if e["role"] == "SUPPLEMENTARY"
        ),
        # 전향 후보인데 마감 전 공개 확인(영수증)이 없는 기록 — 성과 · 학습 제외
        "unconfirmed_forward_records": len(records.unconfirmed(docs)),
    }
    # 최초 실제 예측일 = 가장 이른 주 기록의 공개가 확인된 날(KST · 영수증 시각 = 공개의 상한).
    # 가격 기준일 D(r1 F3)도 쓰기 시작 시각(하한 · 자정을 넘는 공개에서 하루 이름 · r2 F3)도 아니다.
    # 다음 run 이 늦게 확인한 기록은 날짜가 늦어질 수 있으나 해석일을 앞당기지 않는다.
    first_pub = min(
        (store.parse_iso(p["visible_by"]) for p in prims.values()), default=None
    )
    first_day = P.kst_day(first_pub) if first_pub is not None else None
    per_date = {
        D: {
            "input_ok_primary": sum(1 for (_, d) in prims if d == D),
            "matured": sum(1 for r in rows if r["D"] == D),
        }
        for D in forward_days
    }
    groups = P.aux_groups(list(cohort["tickers"]))
    aux = {}
    for g, members in groups.items():
        sub = [r for r in rows if r["ticker"] in members]
        aux[g] = {
            "tickers": members,
            "matured_rows": len(sub),
            "missing_tickers": sorted(set(members) - {r["ticker"] for r in sub}),
            **{name: compare(sub, ms) for name, ms in COMPARISONS.items()},
        }
    return {
        "counts": counts,
        "per_date": per_date,
        "main": {name: compare(rows, ms) for name, ms in COMPARISONS.items()},
        "by_ticker": _by(rows, lambda r: r["ticker"]),
        "by_month": _by(rows, lambda r: r["month"]),
        "by_model_version": _by(rows, lambda r: r["model_version"]),
        "aux_groups": aux,
        "first_forward_D": forward_days[0] if forward_days else None,
        "first_forward_published_kst": first_day,
        "first_interpretation_date": _months_later(first_day, 3) if first_day else None,
        "notes": NOTES,
    }


def write(root: Path, cohort: dict, run_id: str, clock) -> str:
    body = P.doc(
        "report", id=run_id, generated_at=store.iso(clock()), **build(root, cohort)
    )
    path = root / "reports" / f"{run_id}.json"
    P.write_once(path, P.dumps(body))
    return P.rel_in(root, path)
