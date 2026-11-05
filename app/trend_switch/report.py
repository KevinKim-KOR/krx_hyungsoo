"""POC6-21 판정 축 · report.md — 통합 설계 §7 · PLAN 판정 §4(H1 일반 지표 · bootstrap 함수 재사용).

```text
ML 추가 효용   20bp CAGR(M1) − CAGR(R1) ≥ 0.01 그리고 보조 3구간 중 2구간 이상 기간 수익 M1 > R1
강화 효용      20bp M1 강화 기회 0 = NOT_JUDGED(결합 후보 아님) · 기회 있음 = 20bp 회전율(M1) < M0 그리고
               CAGR(M1) ≥ CAGR(M0) 그리고 40bp CAGR(M1) ≥ CAGR(M0) · 같으면 유효한 미관측 · R1 − R0 은 값으로 공개
목적·위험·부담 20bp CAGR(M1) > CAGR(K) · MDD(M1) − MDD(R1) ≥ −0.05 · MDD(M1) − MDD(K) ≥ −0.05
               · 회전율(M1) ≤ 6
높은 비용      40bp CAGR(M1) > CAGR(R1) 그리고 > CAGR(K)
후보           네 축 모두 = FURTHER_REVIEW_CANDIDATE · 불확실성(M1_20 − R1_20 주간 bootstrap)은 따로 병기
무효           CHECK_REQUIRED · DATA_SHORT · BUDGET_STOP = NOT_JUDGED(성과 미달로 바꾸지 않음)
               어느 결과든 OPERATION_ADOPTION = NO · TOTAL_RETURN_VALIDATED = NO
```
"""

from __future__ import annotations

from typing import Any, Optional

from app.weekly_selection import report as R

GAP_MIN = 0.01
SUB_WIN_MIN = 2
MDD_LIMIT = 0.05
TURNOVER_MAX = 6.0
BOOTSTRAP = {"block": R.BLOCK_WEEKS, "draws": R.BOOT_DRAWS, "seed": R.BOOT_SEED}
NAMES = ("R0", "R1", "M0", "M1", "K")
ORDER = tuple(f"{k}_{c}" for c in ("20", "40") for k in NAMES)
NOTE = (
    "봉인 KRX 합성 가격지수와 POC6-19 연구 사본으로 만든 탐색적 회고 모의 비교다. 이미 본 기간이며 새 미사용 시험 · "
    "총수익 검증 · 실제 권고 채택이 아니다(TOTAL_RETURN_VALIDATED=NO · OPERATION_ADOPTION=NO)."
)
_NJ = "NOT_JUDGED"


def _cagr(c: dict) -> float:
    return c["total"]["cagr"]


def _to(c: dict) -> float:
    return c["turnover"]["annual"]


def opportunities(trades: dict) -> dict[str, int]:
    """곡선 → 강화 기회(2h 를 대입한 문턱 판정 직전 검토 · 편입 + 이탈)."""
    return {
        k: v["reviews"]["entry"]["strengthened"] + v["reviews"]["exit"]["strengthened"]
        for k, v in trades.items()
        if "reviews" in v
    }


def judge(
    validity: str, test: Optional[dict], boot: Optional[dict], opps: Optional[dict]
) -> dict[str, Any]:
    base = {
        "validity": validity,
        "OPERATION_ADOPTION": "NO",
        "TOTAL_RETURN_VALIDATED": "NO",
    }
    if validity != "OK" or test is None or opps is None:
        return {
            **base,
            "ml_gain": _NJ,
            "strengthen_gain": _NJ,
            "purpose_risk": _NJ,
            "high_cost": _NJ,
            "candidate": _NJ,
            "uncertainty": None,
            "reasons": [],
        }
    R0, R1, M0, M1, K = (test[f"{k}_20"] for k in NAMES)
    R0_4, R1_4, M0_4, M1_4, K_4 = (test[f"{k}_40"] for k in NAMES)
    gap = _cagr(M1) - _cagr(R1)
    sub_diff = [
        a["return"] - b["return"] for a, b in zip(M1["subperiods"], R1["subperiods"])
    ]
    wins = sum(1 for x in sub_diff if x > 0)
    ml = gap >= GAP_MIN and wins >= SUB_WIN_MIN
    reasons = [] if ml else ["ML_GAIN_NOT_SHOWN"]
    if opps["M1_20"] == 0:
        strengthen = _NJ
        reasons.append("STRENGTHEN_NOT_JUDGED_NO_OPPORTUNITY")
    else:
        ok = _to(M1) < _to(M0) and _cagr(M1) >= _cagr(M0) and _cagr(M1_4) >= _cagr(M0_4)
        strengthen = "STRENGTHEN_GAIN_OBSERVED" if ok else "STRENGTHEN_GAIN_NOT_SHOWN"
        if not ok:
            reasons.append("STRENGTHEN_GAIN_NOT_SHOWN")
    above_k = _cagr(M1) > _cagr(K)
    mdd_r, mdd_k = (
        M1["total"]["mdd"] - R1["total"]["mdd"],
        M1["total"]["mdd"] - K["total"]["mdd"],
    )
    purpose = (
        above_k
        and mdd_r >= -MDD_LIMIT
        and mdd_k >= -MDD_LIMIT
        and _to(M1) <= TURNOVER_MAX
    )
    for bad, why in (
        (not above_k, "M1_NOT_ABOVE_K"),
        (not mdd_r >= -MDD_LIMIT, "MDD_WORSE_THAN_R1"),
        (not mdd_k >= -MDD_LIMIT, "MDD_WORSE_THAN_K"),
        (not _to(M1) <= TURNOVER_MAX, "TURNOVER_ABOVE_6"),
    ):
        if bad:
            reasons.append(why)
    c40_r, c40_k = _cagr(M1_4) - _cagr(R1_4), _cagr(M1_4) - _cagr(K_4)
    cost = c40_r > 0 and c40_k > 0
    if not c40_r > 0:
        reasons.append("COST_40BP_NOT_ABOVE_R1")
    if not c40_k > 0:
        reasons.append("COST_40BP_NOT_ABOVE_K")
    if opps["R1_20"] == 0:
        reasons.append("R1_NO_STRENGTHEN_OPPORTUNITY")
    candidate = ml and strengthen == "STRENGTHEN_GAIN_OBSERVED" and purpose and cost
    return {
        **base,
        "ml_gain": "ML_GAIN_OBSERVED" if ml else "ML_GAIN_NOT_SHOWN",
        "strengthen_gain": strengthen,
        "purpose_risk": "PURPOSE_RISK_MET" if purpose else "PURPOSE_RISK_NOT_MET",
        "high_cost": "HIGH_COST_MET" if cost else "HIGH_COST_NOT_MET",
        "candidate": "FURTHER_REVIEW_CANDIDATE" if candidate else "NOT_CANDIDATE",
        "uncertainty": (
            None
            if boot is None
            else ("UNCERTAIN" if boot["uncertain"] else "CI_EXCLUDES_ZERO")
        ),
        "values": {
            "cagr_gap_M1_R1": gap,
            "sub_return_diff_M1_R1": sub_diff,
            "sub_wins": wins,
            "opportunities_M1_20": opps["M1_20"],
            "opportunities_R1_20": opps["R1_20"],
            "turnover_M1_M0_20": [_to(M1), _to(M0)],
            "cagr_gap_M1_M0_20": _cagr(M1) - _cagr(M0),
            "cagr_gap_M1_M0_40": _cagr(M1_4) - _cagr(M0_4),
            "turnover_R1_R0_20": [_to(R1), _to(R0)],
            "cagr_gap_R1_R0_20": _cagr(R1) - _cagr(R0),
            "cagr_gap_R1_R0_40": _cagr(R1_4) - _cagr(R0_4),
            "cagr_M1_minus_K": _cagr(M1) - _cagr(K),
            "mdd_M1_minus_R1": mdd_r,
            "mdd_M1_minus_K": mdd_k,
            "turnover_M1": _to(M1),
            "cagr_gap_M1_R1_40bp": c40_r,
            "cagr_gap_M1_K_40bp": c40_k,
        },
        "reasons": reasons,
    }


def _ordered(d: dict) -> list:
    return [(k, d[k]) for k in ORDER if k in d] + sorted(
        (k, v) for k, v in d.items() if k not in ORDER
    )


def _pct(x: Optional[float], d: int = 2) -> str:
    return "—" if x is None else f"{x * 100:.{d}f}%"


def _curve_table(part: dict, extra: dict, title: str) -> list[str]:
    lines = [
        title,
        "",
        "| 곡선 | 상태 | 기간 수익 | CAGR | MDD | 회전율 | 최장 고점 미회복(거래일) | 끝 미회복 | "
        "평균 현금 비중 | 총비용 |",
        "|---|---|---:|---:|---:|---:|---:|---|---:|---:|",
    ]
    for k, c in _ordered(part):
        if c["status"] != "OK":
            lines.append(f"| {k} | {c['status']} | — | — | — | — | — | — | — | — |")
            continue
        t, ex = c["total"], extra.get(k) or {}
        uw, cash = ex.get("underwater") or {}, ex.get("cash") or {}
        end = f"예 · {uw['days_at_end']}일" if uw.get("underwater_at_end") else "아니오"
        cost = ex.get("costs_total")
        lines.append(
            f"| {k} | OK | {_pct(t['return'])} | {_pct(t['cagr'])} | {_pct(t['mdd'])} | "
            f"{c['turnover']['annual']:.2f} | {uw.get('longest_days', '—')} | {end} | "
            f"{_pct(cash.get('avg_cash_weight'))} | {'—' if cost is None else f'{cost:.4f}'} |"
        )
    return lines + [""]


def _trade_table(extra: dict, title: str) -> list[str]:
    lines = [
        title,
        "",
        "| 곡선 | 진입 · 재진입 · 단기 재진입 | 통상 · 단기 재이탈 · 보호 · 열림 | 강화 기회(편입/이탈 · 날짜) | "
        "자격 밖 보유 보류(주 · 종목·주 · 종목·일) | 묶음(거래) |",
        "|---|---|---|---|---|---|",
    ]
    for k, a in _ordered(extra):
        if "reviews" not in a:
            continue
        ein = "/".join(
            str(a["by_entry_kind"][x]["trades"])
            for x in ("ENTRY", "REENTRY", "SHORT_REENTRY")
        )
        eout = "/".join(
            str(a["by_exit_kind"][x]["trades"])
            for x in ("EXIT", "SHORT_REEXIT", "PROTECT", "OPEN")
        )
        rv = a["reviews"]
        opp = (
            f"{rv['entry']['strengthened']}/{rv['exit']['strengthened']} · "
            f"{rv['entry']['strengthened_dates']}/{rv['exit']['strengthened_dates']}"
        )
        ho = a["held_not_eligible"]
        b = a["bundles"]
        lines.append(
            f"| {k} | {ein} | {eout} | {opp} | {ho['dates']} · {ho['pairs']} · {ho['held_days']} | "
            f"{b['bundles']}({b['trades_in_bundles']}) |"
        )
    return lines + [""]


def _stop_lines(rep: dict) -> list[str]:
    lines = ["## 멈춘 이유", "", f"- {rep['stop']}"]
    for part in ("validation", "test"):
        for k, c in _ordered(rep.get(part) or {}):
            items = (
                ((c.get("unresolved") or {}).get("items") or [])
                if c["status"] != "OK"
                else []
            )
            for x in items:
                lines.append(
                    f"- 미확정 {part} {k}: {x.get('ticker', '—')} · 최초 "
                    f"{c['unresolved'].get('first_unresolved')} · 마지막 유효 "
                    f"{x.get('last_valid', '—')} · 원인 {x.get('cause')}"
                )
    return lines + [""]


def _coverage(cov: dict) -> list[str]:
    lines = ["## 사용 · 제외 주(성과와 무관하게 잠금에서 정함)", ""]
    for tag, name in (
        ("val", "선행 재생 2018 ~ 2020"),
        ("test", "주 평가 2021 ~ 2026-09-21"),
    ):
        c = cov.get(tag) or {}
        if c:
            lines.append(
                f"- {name}: 정기 계획 {c['weeks']}주 / 자격 20종 이상 {c['h1_weeks']}주 · "
                f"4열 미정의로 통상 판단 없음 {len(c['lost'])}주({', '.join(c['lost']) or '없음'})"
            )
    if cov.get("sub_weeks"):
        lines.append(f"- 보조 구간 정기 계획 주: {cov['sub_weeks']}")
    lines += [
        "- 통상 판단이 없는 주에도 보유 평가 · 일별 보호는 계속한다.",
        "",
    ]
    return lines


def _values(j: dict) -> list[str]:
    v = j["values"]
    return [
        "## 판정 값(반올림 전 값으로 비교)",
        "",
        f"- ML 추가 효용: CAGR(M1) − CAGR(R1) = {v['cagr_gap_M1_R1']:.6f} (기준 ≥ 0.01) · "
        f"보조 구간 우위 {v['sub_wins']}/3",
        f"- 강화 효용: M1 강화 기회 {v['opportunities_M1_20']} · 회전율 M1/M0 = "
        f"{v['turnover_M1_M0_20'][0]:.4f}/{v['turnover_M1_M0_20'][1]:.4f} · CAGR(M1) − CAGR(M0) = "
        f"{v['cagr_gap_M1_M0_20']:.6f}(20bp) · {v['cagr_gap_M1_M0_40']:.6f}(40bp)",
        f"- R1 − R0(공개): R1 강화 기회 {v['opportunities_R1_20']} · 회전율 R1/R0 = "
        f"{v['turnover_R1_R0_20'][0]:.4f}/{v['turnover_R1_R0_20'][1]:.4f} · CAGR(R1) − CAGR(R0) = "
        f"{v['cagr_gap_R1_R0_20']:.6f}(20bp) · {v['cagr_gap_R1_R0_40']:.6f}(40bp)",
        f"- 목적 · 위험 · 부담: CAGR(M1) − CAGR(K) = {v['cagr_M1_minus_K']:.6f} (기준 > 0) · "
        f"MDD(M1) − MDD(R1/K) = {v['mdd_M1_minus_R1']:.6f} / {v['mdd_M1_minus_K']:.6f} "
        f"(기준 ≥ −0.05) · 회전율(M1) = {v['turnover_M1']:.4f} (기준 ≤ 6)",
        f"- 높은 비용(40bp): CAGR(M1) − CAGR(R1) = {v['cagr_gap_M1_R1_40bp']:.6f} · "
        f"CAGR(M1) − CAGR(K) = {v['cagr_gap_M1_K_40bp']:.6f} (기준 > 0)",
        f"- 사유: {', '.join(j['reasons']) or '없음'}",
        "",
    ]


def markdown(rep: dict) -> str:
    j = rep["judgment"]
    lines = [
        "# POC6-21 추세 참여와 단기 재진입 · 재이탈의 ML 효용 — 공식 실행 보고",
        "",
        NOTE,
        "",
        "```text",
        f"VALIDITY        = {j['validity']}",
        f"ML_GAIN         = {j['ml_gain']}",
        f"STRENGTHEN_GAIN = {j['strengthen_gain']}",
        f"PURPOSE_RISK    = {j['purpose_risk']}",
        f"HIGH_COST       = {j['high_cost']}",
        f"CANDIDATE       = {j['candidate']}",
        f"UNCERTAIN       = {j.get('uncertainty')}",
        "OPERATION_ADOPTION = NO · TOTAL_RETURN_VALIDATED = NO",
        "```",
        "",
    ]
    if rep.get("stop"):
        lines += _stop_lines(rep)
    if rep.get("coverage"):
        lines += _coverage(rep["coverage"])
    for part, extra, name in (
        (
            "validation",
            "validation_trades",
            "선행 재생(2018 ~ 2020 · 20bp · 선택 없음)",
        ),
        ("test", "test_trades", "주 평가(2021-01-04 ~ 2026-09-21)"),
    ):
        if rep.get(part):
            lines += _curve_table(rep[part], rep.get(extra) or {}, f"## {name}")
        if rep.get(extra):
            lines += _trade_table(rep[extra], f"거래 · 검토 분모 — {name}")
    test = rep.get("test") or {}
    keys = tuple(f"{k}_20" for k in NAMES)
    if all(test.get(k, {}).get("status") == "OK" for k in keys):
        lines += [
            "보조 구간(20bp · 기간 수익)",
            "",
            "| 구간 | " + " | ".join(NAMES) + " |",
            "|---|" + "---:|" * len(NAMES),
        ]
        for n, sub in enumerate(test["M1_20"]["subperiods"]):
            lo, hi = sub["bounds"]
            vals = [test[k]["subperiods"][n]["return"] for k in keys]
            lines.append(f"| {lo} ~ {hi} | " + " | ".join(_pct(v) for v in vals) + " |")
        lines.append("")
    if j.get("values"):
        lines += _values(j)
    boot = rep.get("bootstrap")
    if boot:
        lines += [
            "## 주간 M1 − R1 차이 bootstrap(평가 구간 완전한 주 전체)",
            "",
            f"- 완결 주 {boot['weeks']} · 끝 불완전 주 제외 {rep.get('bootstrap_tail_excluded', 0)}",
            f"- 평균 차이 {boot['mean_diff']:.6f} · "
            f"95% 구간 [{boot['ci95'][0]:.6f}, {boot['ci95'][1]:.6f}]",
            "- 주간 평균 차이의 한정 불확실성 추정이다. CAGR 차이의 신뢰구간 · 미래 우위 확률이 아니다.",
            "",
        ]
    lines += [
        "## 한정",
        "",
        "- 60거래일은 이번 연구의 평가 길이다. 의무 보유기간 · 최적 기간이 아니다. 10거래일 · 2배 문턱은 단일 가설이다.",
        "- 시장 4열의 이용 가능 시각은 회고 비교의 고정 가정이다(실제 과거 공개 시각 · 당시 수신판 미인증).",
        "- 수급 사본은 4일 미확보(PARTIAL)다. 그 4일이 걸린 주는 통상 판단을 하지 않았다(채우지 · 줄이지 않음).",
        "- 손익은 각 모의 장부의 비용 차감 손익이다. 개인 보유 · 실거래 손익이 아니다. 작은 하위 묶음으로 일반 효과를 단정하지 않는다.",
        "- 비용 20bp · 40bp 는 연구 가정이다. 평가 기간은 이미 본 시기다.",
        "",
    ]
    return "\n".join(lines)
