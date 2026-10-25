"""POC6-09 — report.json · report.md(설계 §5 · §7 · PLAN §4) — 계산은 `core`, 실행 · 대조는 `flow`.

```text
JSON   실행 ID · 입력(경로 · 해시) · 고정 조건 · 범위별 표본 · 방법별 P/R/미해당/미포착/TP/FP/FN · 동점 · 반복 선택
       · 종목별 내역 · 모델 × 기준 판정(조건별 참거짓 · 차이) · 한계
글     저장 report.json 을 다시 읽은 값에서 고정 순서로 만든다(verify 가 같은 방법으로 대조)
```
"""

from __future__ import annotations

from typing import Any, Optional

from app.review_priority import core as C

SCOPES = ("G_ALL", "G_REVIEW")
LIMITS = [
    "08 의 예측 · 결과를 이미 본 뒤의 회고 연구 — 처음 본 시험 · 확증 검증 아님",
    "현재 상장 표본 · 나중에 수신한 조정 가격 · 이미 본 역사 구간 — 당시 가용 자료로 한 PIT 검증 아님",
    "겹치는 20일 목표 — 연속 날짜가 같은 급락을 여러 번 포함 · R 은 독립 급락 사건의 조기 경보율이 아님",
    "P 는 승률 · 수익률 · 하락 확률 정확도가 아님 · 매일 3종목이라 큰 하락이 3개를 넘는 날은 다 포착할 수 없음",
    "양성이어도 '검토 순서'의 연구 신호일 뿐 — 하락폭 정확성 · 매수 시점 · 위험 등급 · 운영 채택 아님",
    "G_REVIEW 는 사전 고정 15종 — '모든 일반 주식형 ETF' 가 아님",
    "여러 모델 · 기준 · 범위의 탐색적 비교 — 유의확률 · 일반 시장 우위 주장 없음 · 자동 우승자 없음",
    "k = 3 · -8% · 표본 기준 · 5%p 는 이번 연구 조건 — 보편적 투자 기준 아님",
]


def report(
    run_id: str,
    inputs: dict[str, Any],
    conditions: dict[str, Any],
    result: dict[str, Any],
    protocol_id: str,
) -> dict[str, Any]:
    return {
        "schema": "poc6_09_report_v1",
        "protocol_id": protocol_id,
        "run_id": run_id,
        "inputs": inputs,
        "conditions": conditions,
        "scopes": result["scopes"],
        "limits": LIMITS,
    }


def _f(v: Optional[float], n: int = 4) -> str:
    return "—" if v is None else f"{v:.{n}f}"


def _pp(v: Optional[float]) -> str:
    return "—" if v is None else f"{v * 100:+.2f}"


def markdown(rep: dict[str, Any]) -> str:
    cond = rep["conditions"]
    margin = cond["judge"]["p_margin"]
    lines = [
        "# POC6-09 보고서 — 기존 모델의 검토 우선순위 효용(회고 · 08 저장 시험 예측 · 새 학습 없음)",
        "",
        f"- run `{rep['run_id']}` · protocol `{rep['protocol_id']}` · 매일 k = {cond['k']} · "
        f"큰 하락 = 실제 D20 ≤ {cond['tail']}(포함)",
        f"- P · R · 차이는 소수({margin} = {margin * 100:g}%p) · P = 모든 날짜 평균 · "
        "R = 큰 하락이 있는 날짜만 평균 · 판정은 정확한 분수로 계산",
        "",
    ]
    for scope in SCOPES:
        lines += _scope_md(scope, rep["scopes"][scope], margin, cond)
    lines += ["## 한계", ""] + [f"- {x}" for x in rep["limits"]] + [""]
    return "\n".join(lines)


def _scope_md(scope, s, margin, cond) -> list[str]:
    sm, sp = s["summary"], s["sample"]
    fs = " · ".join(f"{f['tail_dates']}/{f['tail_tickers']}" for f in sp["folds"])
    lines = [
        f"## {scope}({s['members']}종)",
        "",
        f"- 날짜 {sp['dates']} · 행 {sp['rows']} · 큰 하락 행 {sp['tail_rows']} · 큰 하락 날짜 "
        f"{sp['tail_dates']} · 종목 {sp['tail_tickers']} · 구간별(날짜/종목) {fs} · "
        f"표본 충족 {sp['enough']} · 큰 하락 > k 인 날짜 {sp['dates_m_over_k']}",
        "",
        "| 방법 | P 전체 | 구간 1 | 2 | 3 | 1−P(미해당) | R 전체(날짜) | 미포착 | TP | FP | FN "
        "| 경계 동점 날짜 · 최대 | 선택 종목 수 · 상위 3 비중 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for m in C.METHODS + (C.UNIFORM,):
        a = sm[m]["all"]
        ties, sel = sm[m].get("ties"), sm[m].get("selection")
        tail = (
            f"{ties['boundary_tie_dates']} · {ties['max_boundary_tie']} | "
            f"{sel['tickers_selected']} · {_f(sel['top3_share'])} |"
            if ties
            else "— | — |"
        )
        lines.append(
            f"| {m} | {_f(a['P'])} | {_f(sm[m]['0']['P'])} | {_f(sm[m]['1']['P'])} | "
            f"{_f(sm[m]['2']['P'])} | {_f(a['not_hit'])} | {_f(a['R'])}({a['r_dates']}) | "
            f"{_f(a['miss'])} | {_f(a['TP'], 2)} | {_f(a['FP'], 2)} | {_f(a['FN'], 2)} | "
            + tail
        )
    lines += [
        "",
        f"| 모델 | 판정 | 기준 | 전체 P 차(%p) | 구간 P 차(%p) | 전체 R 차(%p) "
        f"| ① ≥ {margin * 100:g}%p | ② 2구간 | ③ -{cond['judge']['fold_worse'] * 100:g}%p 이내 "
        "| ④ R |",
        "|---|---|---|---:|---|---:|---|---|---|---|",
    ]
    for model in C.MODELS:
        j = s["judge"][model]
        for base in C.BASELINES:
            a = j["against"][base]
            c = a["conditions"]
            lines.append(
                f"| {model} | {j['status']} | {base} | {_pp(a['p_diff'])} | "
                + " · ".join(_pp(x) for x in a["fold_p_diff"])
                + f" | {_pp(a['r_diff'])} | {c['p_margin']} | {c['fold_wins']} | "
                f"{c['no_fold_worse']} | {c['r_not_lower']} |"
            )
        lines.append(
            f"| {model} | — | 기준 중 최고 P = {j['best_baseline']} | "
            f"{_pp(j['p_diff_vs_best'])} | | | | | | |"
        )
    lines += [
        "",
        "| 종목 | 행 | 큰 하락 행 | "
        + " | ".join(f"{m} 선택 · 적중" for m in C.METHODS)
        + " |",
        "|---|---:|---:|" + "---|" * len(C.METHODS),
    ]
    for t, e in s["per_ticker"].items():
        cells = " | ".join(
            f"{_f(e['methods'][m]['selected'], 2)} · {_f(e['methods'][m]['hit'], 2)}"
            for m in C.METHODS
        )
        lines.append(f"| {t} | {e['rows']} | {e['tail']} | {cells} |")
    return lines + [""]
