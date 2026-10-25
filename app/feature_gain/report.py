"""POC6-08 — 날짜 균형 MAE · 큰 하락 · U · A/B 판정 · report.md/json(설계 §6 · PLAN §7 · 판정 §3-2).

```text
MAE    02 `date_balanced_mae` · `method_scores`(날짜별 평균 절대오차 → 날짜 평균 · %p · 제한 예측) · 반올림 전 판정
A      후보 vs HGB_P 하나 — 02 `judge`(전체 5% · 두 구간 우위 · 구간 5% 초과 악화 없음 · 구간 기준 0 = 후보도 0)
       전체 기준 0 = NO_BASELINE_HEADROOM · 가용 부족 = DATA_SHORT · 실행 실패 = FAILED
B      수치는 A 와 별도로 모두 계산(A 결과를 지우지 않음) · 상태는 A 충족 후보만(설계 §6-3) — A 미충족 = NOT_JUDGED
       (B 수치 · 조건만 보고) · ① RIDGE · MEDIAN 전체 기준 0 → NO_BASELINE_HEADROOM ② RIDGE 5% · MEDIAN 보다 작음
       미충족 → FEATURE_GAIN_ONLY ③ 큰 하락 20날짜 · 3종 미만 → TAIL_DATA_SHORT ④ U 가 RIDGE 보다 5% 넘게 나쁨
       (RIDGE U = 0 이면 후보 0) → FEATURE_GAIN_ONLY ⑤ RESEARCH_CANDIDATE · '사용 검증 후보' = A 통과 + ⑤
U      큰 하락(실제 D20 ≤ -8%) 행만 · 날짜별 mean(max(예측 - 실제, 0)) → 날짜 평균(%p)
```
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from app.d20_pooled import study as S
from app.feature_gain import protocol as P


def scope_rows(rows: list[dict], scope: str, review: list[str]) -> list[dict]:
    if scope == "G_ALL":
        return rows
    keep = set(review)
    return [r for r in rows if r["ticker"] in keep]


def scores(rows: list[dict], cfg: str) -> dict[str, Any]:
    by_fold = [[r for r in rows if r["fold"] == k] for k in range(P.FOLDS)]
    out = S.method_scores(by_fold, cfg)
    per: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        per[r["ticker"]].append(abs(r["preds"][cfg] - r["truth"]) * 100.0)
    out["per_ticker"] = {t: sum(v) / len(v) for t, v in sorted(per.items())}
    return out


def tail(rows: list[dict], cfg: str) -> dict[str, Any]:
    deep = [r for r in rows if r["truth"] <= P.TAIL]
    by: dict[str, list[float]] = defaultdict(list)
    for r in deep:
        by[r["date"]].append(max(r["preds"][cfg] - r["truth"], 0.0) * 100.0)
    per = [sum(v) / len(v) for v in by.values()]
    return {
        "rows": len(deep),
        "dates": len(by),
        "tickers": len({r["ticker"] for r in deep}),
        "mae_pp": S.date_balanced_mae(deep, cfg)["mae_pp"] if deep else None,
        "u_pp": sum(per) / len(per) if per else None,
        "max_under_pp": max(
            (max(r["preds"][cfg] - r["truth"], 0.0) * 100.0 for r in deep), default=None
        ),
    }


SUPPORTED = "FEATURE_GAIN_SUPPORTED"
NOT_JUDGED = (
    "NOT_JUDGED"  # B 상태 — A 미충족(설계 §6-3 'A를 충족한 후보만' · 수치만 보고)
)


def _rel(base: Optional[float], cand: Optional[float]) -> Optional[float]:
    """상대 개선율(기준 0 · 값 없음 = null · 설계 §6-1)."""
    if base is None or cand is None or base == 0:
        return None
    return (base - cand) / base


def judge_a(cand: dict, base: dict) -> dict[str, Any]:
    j = S.judge(cand, base)
    rel = None if j.get("base_zero") else j["relative_improvement"]
    if j.get("base_zero"):
        return {
            "status": "NO_BASELINE_HEADROOM",
            "relative_improvement": rel,
            "judge": j,
        }
    return {
        "status": SUPPORTED if j["pass"] else "FEATURE_GAIN_NOT_SHOWN",
        "relative_improvement": rel,
        "judge": j,
    }


def judge_b(
    c: dict, ridge: dict, median: dict, t_c: dict, t_ridge: dict
) -> dict[str, Any]:
    """B 규칙(판정 §3-2 순서) — 상태와 무관하게 모든 수치 · 조건을 함께 남긴다(반올림 전)."""
    ro, mo, co = ridge["overall"], median["overall"], c["overall"]
    rel_r, rel_m = _rel(ro, co), _rel(mo, co)
    tail_enough = (
        t_c["dates"] >= P.TAIL_MIN_DATES and t_c["tickers"] >= P.TAIL_MIN_TICKERS
    )
    uc, ur = t_c.get("u_pp"), t_ridge.get("u_pp")
    u_ok = (
        None
        if uc is None or ur is None
        else (uc <= ur * (1.0 + P.U_WORSE) if ur > 0 else uc <= 0)
    )
    info: dict[str, Any] = {
        "candidate_overall": co,
        "ridge_overall": ro,
        "median_overall": mo,
        "ridge_relative_improvement": rel_r,
        "median_relative_improvement": rel_m,
        "ridge_improve_ok": rel_r is not None and rel_r >= P.IMPROVE,
        "beats_median": co < mo,
        "tail_enough": tail_enough,
        "tail_dates": t_c["dates"],
        "tail_tickers": t_c["tickers"],
        "u_candidate": uc,
        "u_ridge": ur,
        "u_ok": u_ok,
    }
    if ro == 0 or mo == 0:
        return {"status": "NO_BASELINE_HEADROOM", **info}
    if not (info["ridge_improve_ok"] and info["beats_median"]):
        return {
            "status": "FEATURE_GAIN_ONLY",
            "why": "RIDGE 5% · MEDIAN 비교 미충족",
            **info,
        }
    if not tail_enough:
        return {"status": "TAIL_DATA_SHORT", **info}
    if not u_ok:
        return {"status": "FEATURE_GAIN_ONLY", "why": "큰 하락 과소추정 U 악화", **info}
    return {"status": "RESEARCH_CANDIDATE", **info}


def judge_pair(sc: dict, tl: dict, ok_cfg: set, cand: str) -> tuple[dict, dict]:
    """한 범위 · 한 후보의 A · B(가용 · 후보 실행은 호출부가 확인)."""
    if "HGB_P" in ok_cfg:
        a = judge_a(sc[cand], sc["HGB_P"])
    else:
        a = {"status": "FAILED", "reason": "HGB_P 실행 실패(비교 기준 없음)"}
    if {"RIDGE_P", "MEDIAN_P"} <= ok_cfg:
        b = judge_b(sc[cand], sc["RIDGE_P"], sc["MEDIAN_P"], tl[cand], tl["RIDGE_P"])
    else:
        b = {"status": "FAILED", "reason": "기준선(RIDGE_P · MEDIAN_P) 실행 실패"}
    if a["status"] != SUPPORTED and b["status"] != "FAILED":
        b = {k: v for k, v in b.items() if k not in ("status", "why")}
        b = {
            "status": NOT_JUDGED,
            "reason": f"A {a['status']} — A 를 충족한 후보만 B 판단(설계 §6-3) · 수치만 보고",
            **b,
        }
    b["use_candidate"] = (
        a["status"] == SUPPORTED and b["status"] == "RESEARCH_CANDIDATE"
    )
    return a, b


def build(
    lock: dict[str, Any], run_meta: dict[str, Any], pred_rows: list[dict]
) -> dict[str, Any]:
    """저장된 예측 행만으로 지표 · 판정을 만든다(verify 가 같은 함수로 다시 계산)."""
    pl = lock["plan"]
    status = run_meta["config_status"]  # [fold][cfg] = OK/FAILED
    ok_cfg = {c for c in P.CONFIGS if all(status[k][c] == "OK" for k in range(P.FOLDS))}
    out: dict[str, Any] = {
        "schema": "poc6_08_report_v1",
        "protocol_id": P.PROTOCOL_ID,
        "lock_id": lock["lock_id"],
        "run_id": run_meta["run_id"],
        "population": {
            "cohort": len(pl["per_ticker"]),
            "eligible": len(pl["eligible"]),
            "review": len(pl["review"]),
            "not_eligible": {
                t: v["reason"] for t, v in pl["per_ticker"].items() if not v["eligible"]
            },
            # 24종 → 적격 → 가격 · 목표 유효 행(구간별 학습 · 시험) · 제외 창 원인
            "per_ticker": {
                t: {
                    "first_row": v["first_row"],
                    "eligible": v["eligible"],
                    "review": t in pl["review"],
                    "train": v["train"],
                    "test": v["test"],
                    "excluded_by_cause": v["excluded_by_cause"],
                }
                for t, v in sorted(pl["per_ticker"].items())
            },
        },
        "denominators": {
            "train_rows": pl["train_rows"],
            "test_rows": pl["test_rows"],
            "coverage": pl["coverage"],
        },
        "config_status": status,
        "scores": {},
        "tail": {},
        "A": {},
        "B": {},
    }
    for scope in P.SCOPES:
        rows = scope_rows(pred_rows, scope, pl["review"])
        sc = {c: scores(rows, c) for c in ok_cfg}
        tl = {c: tail(rows, c) for c in ok_cfg}
        out["scores"][scope] = sc
        out["tail"][scope] = tl
        out["A"][scope], out["B"][scope] = {}, {}
        for cand in P.CANDIDATES:
            cov = pl["coverage"][cand][scope]["status"]
            if cov != "OK":
                out["A"][scope][cand] = {"status": "DATA_SHORT"}
                out["B"][scope][cand] = {"status": "DATA_SHORT"}
                continue
            if cand not in ok_cfg:
                why = f"{cand} 실행 실패(구성 학습 · 예측)"
                out["A"][scope][cand] = {"status": "FAILED", "reason": why}
                out["B"][scope][cand] = {"status": "FAILED", "reason": why}
                continue
            a, b = judge_pair(sc, tl, ok_cfg, cand)
            out["A"][scope][cand], out["B"][scope][cand] = a, b
    out["limits"] = [
        "회고 연구 — 나중에 확보한 장기 가격(당시 가용 PIT 아님) · 이미 본 역사 구간 · 현재 상장 목록 선택",
        "조정 가격과 겹치는 20일 목표 — 날짜 · 행이 독립 사건이 아님",
        "이 HGB 설정 · 자료 · 범위에서의 결과 — 다른 알고리즘 · 보편 시장 우위로 일반화하지 않음",
        "여러 조합 · 범위의 탐색적 비교 — 유의확률 · 확증 아님 · 사후 최솟값 자동 채택 없음",
        "R 은 종목 변화와 함께 벤치마크 변화 정보도 준다 — RS 순위 · 강한 ETF 선별 능력이 아님",
    ]
    return out


def _f(v: Optional[float], n: int = 4) -> str:
    return "—" if v is None else f"{v:.{n}f}"


B_TEXT = {NOT_JUDGED: "판단 안 함(A 미충족)"}


def markdown(rep: dict[str, Any]) -> str:
    pop, den = rep["population"], rep["denominators"]
    lines = [
        "# POC6-08 보고서 — 거래량 · 동일 기간 상대강도의 ML 추가 효용(회고 · PC CPU)",
        "",
        f"- lock `{rep['lock_id']}` · run `{rep['run_id']}` · protocol `{rep['protocol_id']}`",
        f"- 모집단 {pop['cohort']} → 적격 {pop['eligible']} (G_REVIEW {pop['review']}) · 부적격: "
        + (
            "; ".join(f"{t} — {r}" for t, r in sorted(pop["not_eligible"].items()))
            or "없음"
        ),
        f"- 학습 행(구간별 · G_ALL 공동) {den['train_rows']} · 시험 행 {den['test_rows']}",
        "- 실행 상태(구간 1 · 2 · 3): "
        + " / ".join(
            ", ".join(f"{c} {st[c]}" for c in P.CONFIGS) for st in rep["config_status"]
        )
        + f" · 복원 대조 {rep.get('restore_ok')}",
        "",
        "## 가용(V · R 유효 행 / 전체 행 · 구간 1 · 2 · 3)",
        "",
        "| 후보 | 범위 | 학습 | 시험 | 상태 |",
        "|---|---|---|---|---|",
    ]
    for cand in P.CANDIDATES:  # 저장 JSON 은 키 정렬 — 표 순서는 고정 순서로
        for scope in P.SCOPES:
            v = den["coverage"][cand][scope]
            tr = " · ".join(f"{f['train'][0]}/{f['train'][1]}" for f in v["folds"])
            te = " · ".join(f"{f['test'][0]}/{f['test'][1]}" for f in v["folds"])
            lines.append(f"| {cand} | {scope} | {tr} | {te} | {v['status']} |")
    lines.append("")
    for scope in P.SCOPES:
        lines += [
            f"## {scope}",
            "",
            "| 구성 | 전체 MAE %p | 구간 1 | 구간 2 | 구간 3 | 날짜 | 행 | 큰 하락 MAE | U | 최대 과소 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for c in P.CONFIGS:
            s = rep["scores"][scope].get(c)
            t = rep["tail"][scope].get(c)
            if s is None:
                lines.append(f"| {c} | 실행 실패 | | | | | | | | |")
                continue
            b = s["blocks"]
            lines.append(
                f"| {c} | {_f(s['overall'])} | {_f(b[0])} | {_f(b[1])} | {_f(b[2])} | "
                f"{s['dates']} | {s['rows']} | "
                f"{_f(t['mae_pp'])} | {_f(t['u_pp'])} | {_f(t['max_under_pp'])} |"
            )
        lines += [
            "",
            "| 후보 | A(HGB_P 대비) | A 개선율 | 우위 구간 | 구간 5% 악화 없음 | B | RIDGE 대비 | "
            "MEDIAN 대비 | U 후보 / RIDGE | 사용 검증 후보 |",
            "|---|---|---:|---:|---|---|---:|---:|---|---|",
        ]
        for cand in P.CANDIDATES:
            a, b = rep["A"][scope][cand], rep["B"][scope][cand]
            j = a.get("judge") or {}
            worse = (j.get("conditions") or {}).get("no_block_worse_5pct")
            lines.append(
                f"| {cand} | {a['status']} | {_f(a.get('relative_improvement'))} | "
                f"{j.get('block_wins', '—')} | {'—' if worse is None else worse} | "
                f"{B_TEXT.get(b['status'], b['status'])} | "
                f"{_f(b.get('ridge_relative_improvement'))} | "
                f"{_f(b.get('median_relative_improvement'))} | "
                f"{_f(b.get('u_candidate'))} / {_f(b.get('u_ridge'))} | "
                f"{'예' if b.get('use_candidate') else '아니오'} |"
            )
        tl = rep["tail"][scope].get("HGB_P") or {}
        lines += [
            "",
            f"큰 하락(실제 D20 ≤ -8%) 행 {tl.get('rows')} · 날짜 {tl.get('dates')} · "
            f"종목 {tl.get('tickers')}.",
            "",
        ]
    lines += _per_ticker_md(rep)
    lines += ["## 한계", ""] + [f"- {x}" for x in rep["limits"]] + [""]
    return "\n".join(lines)


def _per_ticker_md(rep: dict[str, Any]) -> list[str]:
    """종목별 MAE(%p · G_ALL 시험 행 · G_REVIEW 값은 같은 행의 부분 집합)."""
    sc = rep["scores"]["G_ALL"]
    cfgs = [c for c in P.CONFIGS if c in sc]
    out = [
        "## 종목별 MAE %p (G_ALL · 세 구간 시험 행 평균)",
        "",
        "| 종목 | G_REVIEW | " + " | ".join(cfgs) + " |",
        "|---|---|" + "---:|" * len(cfgs),
    ]
    pt = rep["population"]["per_ticker"]
    tickers = sorted({t for c in cfgs for t in sc[c]["per_ticker"]})
    for t in tickers:
        vals = " | ".join(_f(sc[c]["per_ticker"].get(t)) for c in cfgs)
        out.append(f"| {t} | {'예' if pt[t]['review'] else '아니오'} | {vals} |")
    return out + [""]
