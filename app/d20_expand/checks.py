"""POC6-04 — 비교 가능성 확인 · 표(판정 §3 · §4 · §5 · 결과 전에 고정).

```text
A 대 B      구간 · ETF 별 학습/시험 행 날짜 · 목표 창 끝(축 i+20) · feature 창 시작(축 i−60)이 같아야 함
B 대 C(4종) 위 + feature 값 · 정답이 같아야 함(학습 전체 날짜 가중치는 달라도 됨)
대조군      공통 4종 MEDIAN · RIDGE 예측 |B − C| ≤ 1e-12(수익률 단위 · 상대 0)
공통 평가   C 를 4종 행으로 제한해 B 와 같은 행 · 정답 · 날짜 균형 가중치로 MAE
보조 (a)    C 예측 그대로 · 월 분배 2종 행 빼고 평가(재학습 0)
보조 (b)    B · C 예측 그대로 · 3구간에서 목표 창 마지막 날 ≤ KRX 끝인 행만 평가(재학습 0)
```
어긋나면 원인 목록을 돌려주고 호출자가 멈춘다(교집합 축소 · 결측 대체 없음).
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Optional

from app.d20_pooled import study as S

CONTROL_TOL = 1e-12
TRUTH_DIFF = 0.001  # 수익률 단위(0.1%p)
LABEL_MET, LABEL_NOT_MET = "탐색적 기준 충족", "탐색적 기준 미충족"
METHODS = S.CPU_METHODS  # MEDIAN · RIDGE_EXISTING · POOLED_HGB


# ── 행 구조 ──────────────────────────────────────────────────────────────────


def structure(prep: dict[str, Any], tickers: list[str]) -> dict[str, Any]:
    """구간 날짜 · ETF 별 학습/시험 행(날짜) · 시험 행의 목표 창 끝 · feature 창 시작(날짜)."""
    d = prep["dates"]
    blocks, per = [], {t: [] for t in tickers}
    for b in range(len(prep["blocks"])):
        idx = prep["blocks"][b]
        blocks.append((d[idx[0]], d[idx[-1]]))
        bs = S.block_sets(prep, b)
        for t in tickers:
            per[t].append(
                {
                    "train": [d[i] for i in bs["train"].get(t, [])],
                    "test": [
                        (d[i], d[i + S.H], d[i - S.LB])
                        for tt, i in bs["test"]
                        if tt == t
                    ],
                }
            )
    return {"blocks": blocks, "etfs": per}


def compare_structure(
    a: dict[str, Any], b: dict[str, Any], tickers: list[str], what: str
) -> list[str]:
    problems = []
    if a["blocks"] != b["blocks"]:
        problems.append(f"{what}: 구간 날짜 다름 {a['blocks']} ≠ {b['blocks']}")
    for t in tickers:
        for k, (x, y) in enumerate(zip(a["etfs"][t], b["etfs"][t])):
            if x["train"] != y["train"]:
                problems.append(f"{what}: {t} {k + 1}구간 학습 행 날짜 다름")
            if x["test"] != y["test"]:
                problems.append(
                    f"{what}: {t} {k + 1}구간 시험 행 · 목표 창 · feature 창 다름"
                )
    return problems


def compare_values(
    prep_b: dict[str, Any], prep_c: dict[str, Any], tickers: list[str]
) -> list[str]:
    """B 와 C 의 공통 종목 — 학습 · 시험 행마다 feature 값 · 정답이 같아야 한다."""
    problems = []
    pos_c = {dd: k for k, dd in enumerate(prep_c["dates"])}
    for b in range(len(prep_b["blocks"])):
        bs = S.block_sets(prep_b, b)
        rows = [(t, i) for t in tickers for i in bs["train"].get(t, [])]
        rows += [(t, i) for t, i in bs["test"] if t in tickers]
        for t, i in rows:
            j = pos_c.get(prep_b["dates"][i])
            if j is None:
                problems.append(f"B 대 C: {t} {prep_b['dates'][i]} 가 C 축에 없음")
                continue
            if S.feats(prep_b, t, i) != S.feats(prep_c, t, j) or S.target(
                prep_b, t, i
            ) != S.target(prep_c, t, j):
                problems.append(f"B 대 C: {t} {prep_b['dates'][i]} feature · 정답 다름")
    return problems


# ── 행 고르기 · 점수 ───────────────────────────────────────────────────────────


def only(rows_by_block, keep) -> list[list[dict[str, Any]]]:
    return [[r for r in rows if keep(r)] for rows in rows_by_block]


def scores(rows_by_block, methods=METHODS) -> dict[str, Any]:
    return {m: S.method_scores(rows_by_block, m) for m in methods}


def window_end(prep: dict[str, Any]) -> dict[str, str]:
    """시험 날짜 → 목표 창(20거래일) 마지막 날(정답 계산에 쓴 전체 창의 끝 · 최저가 날 아님)."""
    d = prep["dates"]
    return {d[i]: d[i + S.H] for i in range(len(d) - S.H)}


def control(rows_b, rows_c4) -> dict[str, Any]:
    """공통 4종 MEDIAN · RIDGE 예측 차(ETF 별 학습이라 같아야 함)."""
    cb = {r["id"]: r for blk in rows_b for r in blk}
    out = {
        "tolerance": CONTROL_TOL,
        "max_abs_diff": {},
        "over_tolerance_by_method": {},
        "over_tolerance_rows": 0,
    }
    over = set()
    for m in (S.MEDIAN, S.RIDGE):
        mx, n = 0.0, 0
        for blk in rows_c4:
            for r in blk:
                diff = abs(r["preds"][m] - cb[r["id"]]["preds"][m])
                mx = max(mx, diff)
                if diff > CONTROL_TOL:
                    over.add(r["id"])
                    n += 1
        out["max_abs_diff"][m] = mx
        out["over_tolerance_by_method"][m] = n
    out["over_tolerance_rows"] = len(over)
    out["ok"] = not over
    return out


def truth_diff(rows_a, rows_b) -> dict[str, Any]:
    """같은 행의 정답 차 |A − B|(수익률 단위)."""
    ta = {r["id"]: r["truth"] for blk in rows_a for r in blk}
    diffs = [abs(r["truth"] - ta[r["id"]]) for blk in rows_b for r in blk]
    return {
        "rows": len(diffs),
        "mean_abs": sum(diffs) / len(diffs) if diffs else None,
        "max_abs": max(diffs) if diffs else None,
        "over_0_001": sum(1 for x in diffs if x > TRUTH_DIFF),
        "unit": "수익률(0.001 = 0.1%p)",
    }


def ids(rows_by_block) -> list[list[str]]:
    return [[r["id"] for r in blk] for blk in rows_by_block]


def verdict(sc: dict[str, Any]) -> dict[str, Any]:
    """POC6-02 세 조건 그대로(계산용 재사용) → '탐색적 기준 충족 / 미충족'."""
    v = S.verdict_for(sc, S.HGB)
    reasons = [
        f"대 {b}: {j['reason']}" for b, j in v["against"].items() if j.get("base_zero")
    ]
    return {
        "label": LABEL_MET if v["verdict"] == S.PROMISING else LABEL_NOT_MET,
        "reasons": reasons,
        "against": v["against"],
    }


def direction(sc: dict[str, Any], block: Optional[int] = None) -> Optional[bool]:
    """HGB MAE 가 두 기준보다 작은가(전체 또는 한 구간 · 보조 표 방향 비교용 · 판정 아님)."""

    def pick(k):
        return sc[k]["overall"] if block is None else sc[k]["blocks"][block]

    h, m, r = (pick(k) for k in (S.HGB, S.MEDIAN, S.RIDGE))
    if None in (h, m, r):
        return None
    return h < m and h < r


def krx_rates(basis: dict[str, Any], tickers: list[str]) -> dict[str, Any]:
    """ETF 별 POC6-03 KRX 대조 불일치율 = 불일치/(일치+불일치) · 대조 불가 따로 · 관측 기간."""
    out = {}
    for t in tickers:
        k = basis["per_ticker"][t]["krx"]
        n = k["match"] + k["mismatch"]
        ac = k.get("a_over_c") or {}
        out[t] = {
            "mismatch_rate": k["mismatch"] / n if n else None,
            "match": k["match"],
            "mismatch": k["mismatch"],
            "not_comparable": sum(k["not_comparable"].values()),
            "observed_from": (ac.get("first") or {}).get("date"),
            "observed_to": (ac.get("last") or {}).get("date"),
        }
    return out


def per_etf(rows_by_block, tickers) -> dict[str, Any]:
    out = {}
    for t in tickers:
        rows = [r for blk in rows_by_block for r in blk if r["ticker"] == t]
        out[t] = {
            "rows": len(rows),
            "mae_pp": {
                m: (
                    sum(abs(r["preds"][m] - r["truth"]) for r in rows) / len(rows) * 100
                    if rows
                    else None
                )
                for m in METHODS
            },
        }
    return out


def per_block_dates(rows_by_block) -> list[dict[str, Any]]:
    out = []
    for blk in rows_by_block:
        per = Counter(r["date"] for r in blk)
        out.append(
            {
                "rows": len(blk),
                "dates": len(per),
                "first": min(per) if per else None,
                "last": max(per) if per else None,
            }
        )
    return out
