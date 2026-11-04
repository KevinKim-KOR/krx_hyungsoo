"""POC6-20 판정 축 · report.md — 설계 §7 · PLAN 판정 §3 · §4(H1 일반 지표 · bootstrap 함수 재사용).

```text
추가 효용  20bp CAGR(M) − CAGR(P) ≥ 0.01 그리고 보조 3구간 중 2구간 이상 기간 수익 M − P > 0
목적       20bp CAGR(M) > CAGR(B) 그리고 CAGR(M) > CAGR(K)
위험       MDD(M) − MDD(P) · MDD(M) − MDD(B) · MDD(M) − MDD(K) 모두 ≥ −0.05 · 회전율(M) ≤ 6
비용       40bp CAGR(M) − CAGR(P) > 0 그리고 CAGR(M) − CAGR(B) > 0
후보       네 축 모두 = FURTHER_REVIEW_CANDIDATE · 불확실성(M_20 − P_20 주간 bootstrap)은 따로 병기
무효       CHECK_REQUIRED · DATA_SHORT · BUDGET_STOP = NOT_JUDGED(성과 미달로 바꾸지 않음)
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
ORDER = ("P_20", "M_20", "B_20", "K_20", "P_40", "M_40", "B_40", "K_40")
NOTE = (
    "봉인 KRX 합성 가격지수와 POC6-19 연구 사본으로 만든 회고 모의 비교다. 이미 본 기간이며 새 미사용 시험 · "
    "총수익 검증 · 실제 권고 채택이 아니다(TOTAL_RETURN_VALIDATED=NO · OPERATION_ADOPTION=NO)."
)


def _cagr(c: dict) -> float:
    return c["total"]["cagr"]


def judge(validity: str, test: Optional[dict], boot: Optional[dict]) -> dict[str, Any]:
    base = {
        "validity": validity,
        "OPERATION_ADOPTION": "NO",
        "TOTAL_RETURN_VALIDATED": "NO",
    }
    if validity != "OK" or test is None:
        return {
            **base,
            "market_gain": "NOT_JUDGED",
            "candidate": "NOT_JUDGED",
            "uncertainty": None,
            "reasons": [],
        }
    P, M, B, K = (test[f"{k}_20"] for k in "PMBK")
    P4, M4, B4 = (test[f"{k}_40"] for k in "PMB")
    gap = _cagr(M) - _cagr(P)
    sub_diff = [
        a["return"] - b["return"] for a, b in zip(M["subperiods"], P["subperiods"])
    ]
    wins = sum(1 for x in sub_diff if x > 0)
    gain = gap >= GAP_MIN and wins >= SUB_WIN_MIN
    above_b, above_k = _cagr(M) > _cagr(B), _cagr(M) > _cagr(K)
    mdd = {
        k: M["total"]["mdd"] - c["total"]["mdd"]
        for k, c in (("P", P), ("B", B), ("K", K))
    }
    to = M["turnover"]["annual"]
    risk = all(v >= -MDD_LIMIT for v in mdd.values()) and to <= TURNOVER_MAX
    gap40_p, gap40_b = _cagr(M4) - _cagr(P4), _cagr(M4) - _cagr(B4)
    cost = gap40_p > 0 and gap40_b > 0
    reasons = []
    if not gain:
        reasons.append("MARKET_GAIN_NOT_SHOWN")
    if not above_b:
        reasons.append("M_NOT_ABOVE_B")
    if not above_k:
        reasons.append("M_NOT_ABOVE_K")
    for k, v in mdd.items():
        if not v >= -MDD_LIMIT:
            reasons.append(f"MDD_WORSE_THAN_{k}")
    if not to <= TURNOVER_MAX:
        reasons.append("TURNOVER_ABOVE_6")
    if not gap40_p > 0:
        reasons.append("COST_SENSITIVE_40BP_VS_P")
    if not gap40_b > 0:
        reasons.append("COST_SENSITIVE_40BP_VS_B")
    return {
        **base,
        "market_gain": "MARKET_GAIN_OBSERVED" if gain else "MARKET_GAIN_NOT_SHOWN",
        "candidate": (
            "FURTHER_REVIEW_CANDIDATE"
            if gain and above_b and above_k and risk and cost
            else "NOT_CANDIDATE"
        ),
        "uncertainty": (
            None
            if boot is None
            else ("UNCERTAIN" if boot["uncertain"] else "CI_EXCLUDES_ZERO")
        ),
        "values": {
            "cagr_gap_M_P": gap,
            "sub_return_diff_M_P": sub_diff,
            "sub_wins": wins,
            "cagr_M_minus_B": _cagr(M) - _cagr(B),
            "cagr_M_minus_K": _cagr(M) - _cagr(K),
            "mdd_M_minus_P": mdd["P"],
            "mdd_M_minus_B": mdd["B"],
            "mdd_M_minus_K": mdd["K"],
            "turnover_M": to,
            "cagr_gap_M_P_40bp": gap40_p,
            "cagr_gap_M_B_40bp": gap40_b,
        },
        "reasons": reasons,
    }


def _ordered(d: dict) -> list:
    return [(k, d[k]) for k in ORDER if k in d] + sorted(
        (k, v) for k, v in d.items() if k not in ORDER
    )


def _pct(x: Optional[float], d: int = 2) -> str:
    return "—" if x is None else f"{x * 100:.{d}f}%"


def _curve_table(part: dict, title: str) -> list[str]:
    lines = [
        title,
        "",
        "| 곡선 | 상태 | 기간 수익 | CAGR | MDD | 회전율 | 회복 |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for k, c in _ordered(part):
        if c["status"] == "OK":
            t = c["total"]
            rec = "미회복" if t["not_recovered"] else (t["recovered"] or "—")
            lines.append(
                f"| {k} | OK | {_pct(t['return'])} | {_pct(t['cagr'])} | {_pct(t['mdd'])} | "
                f"{c['turnover']['annual']:.2f} | {rec} |"
            )
        else:
            lines.append(f"| {k} | {c['status']} | — | — | — | — | — |")
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
                f"4열 미정의로 순위 없음 {len(c['lost'])}주({', '.join(c['lost']) or '없음'})"
            )
    if cov.get("sub_weeks"):
        lines.append(f"- 보조 구간 정기 계획 주: {cov['sub_weeks']}")
    lines += [
        "- 순위 없는 주에도 보유 · 일별 가격 보호 · 재진입 대기 셈(모든 주간 신호)은 계속한다.",
        "- '자료 650주'(POC6-19 ISO 주)와 위 정기 계획 주는 다른 셈이다.",
        "",
    ]
    return lines


def markdown(rep: dict) -> str:
    j = rep["judgment"]
    lines = [
        "# POC6-20 시장 정보 추가 효용 비교 — 공식 실행 보고",
        "",
        NOTE,
        "",
        "```text",
        f"VALIDITY     = {j['validity']}",
        f"MARKET_GAIN  = {j['market_gain']}",
        f"CANDIDATE    = {j['candidate']}",
        f"UNCERTAIN    = {j.get('uncertainty')}",
        "OPERATION_ADOPTION = NO · TOTAL_RETURN_VALIDATED = NO",
        "```",
        "",
    ]
    if rep.get("stop"):
        lines += _stop_lines(rep)
    if rep.get("coverage"):
        lines += _coverage(rep["coverage"])
    if rep.get("validation"):
        lines += _curve_table(
            rep["validation"], "## 선행 재생(2018 ~ 2020 · 20bp · 선택 없음)"
        )
    test = rep.get("test") or {}
    if test:
        lines += _curve_table(test, "## 주 평가(2021-01-04 ~ 2026-09-21)")
        keys = ("P_20", "M_20", "B_20", "K_20")
        if all(test.get(k, {}).get("status") == "OK" for k in keys):
            lines += [
                "보조 구간(20bp · 기간 수익)",
                "",
                "| 구간 | P | M | B | K |",
                "|---|---:|---:|---:|---:|",
            ]
            for n, sub in enumerate(test["M_20"]["subperiods"]):
                lo, hi = sub["bounds"]
                vals = [test[k]["subperiods"][n]["return"] for k in keys]
                lines.append(
                    f"| {lo} ~ {hi} | " + " | ".join(_pct(v) for v in vals) + " |"
                )
            lines += ["", "보유 · 현금 · 의존(20bp · 설명용)", ""]
            lines += [
                "| 곡선 | 보유 중앙(거래일) | 청산 | 최대 현금 비중 | 평균 보유 수 | 상위 손익 종목 |"
            ]
            lines += ["|---|---:|---:|---:|---:|---|"]
            for k in ("P_20", "M_20", "B_20"):
                c = test[k]
                h, e, dep = (
                    c.get("holding", {}),
                    c.get("exposure", {}),
                    c.get("dependency", {}),
                )
                top = ", ".join(x["ticker"] for x in (dep.get("top") or [])[:3]) or "—"
                lines.append(
                    f"| {k} | {h.get('median', '—')} | {h.get('closed', '—')} | "
                    f"{_pct(e.get('max_cash_weight'))} | {e.get('avg_holdings', 0):.2f} | {top} |"
                )
            lines.append("")
    if j.get("values"):
        v = j["values"]
        lines += [
            "## 판정 값(반올림 전 값으로 비교)",
            "",
            f"- CAGR(M) − CAGR(P) = {v['cagr_gap_M_P']:.6f} (기준 ≥ 0.01) · "
            f"보조 구간 우위 {v['sub_wins']}/3",
            f"- CAGR(M) − CAGR(B) = {v['cagr_M_minus_B']:.6f} · CAGR(M) − CAGR(K) = "
            f"{v['cagr_M_minus_K']:.6f} (기준 > 0)",
            f"- MDD(M) − MDD(P/B/K) = {v['mdd_M_minus_P']:.6f} / {v['mdd_M_minus_B']:.6f} / "
            f"{v['mdd_M_minus_K']:.6f} (기준 ≥ −0.05) · 회전율(M) = {v['turnover_M']:.4f} (기준 ≤ 6)",
            f"- 40bp CAGR(M) − CAGR(P) = {v['cagr_gap_M_P_40bp']:.6f} · CAGR(M) − CAGR(B) = "
            f"{v['cagr_gap_M_B_40bp']:.6f} (기준 > 0)",
            f"- 사유: {', '.join(j['reasons']) or '없음'}",
            "",
        ]
    boot = rep.get("bootstrap")
    if boot:
        lines += [
            "## 주간 M − P 차이 bootstrap(평가 구간 완전한 주 전체)",
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
        "- 시장 4열의 이용 가능 시각(수급 = 다음 거래일 12:00 KST · 매크로 = 원천 d+2 00:00)은 회고 비교의 "
        "고정 가정이다. 실제 과거 공개 시각 · 당시 수신판을 인증하지 않는다.",
        "- 수급 사본은 4일 미확보(PARTIAL)다. 그 4일이 걸린 주는 순위를 만들지 않았다(채우지 · 줄이지 않음).",
        "- P 는 공통 날짜 조건을 적용한 새 대조군이다. H1 의 L · B 곡선과 학습 행 · 계획 주가 다르다(K 는 같은 날짜).",
        "- 비용 20bp · 40bp 는 연구 가정이다. 평가 기간은 이미 본 시기다.",
        "",
    ]
    return "\n".join(lines)
