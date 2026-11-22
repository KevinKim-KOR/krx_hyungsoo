"""주별 기록(설계 §4-3 · 판정 §2 문구) · 결과 글 report.md — 숫자는 study 결과 그대로(반올림은 글에서만)."""

from __future__ import annotations

from typing import Any, Optional

from app.entry_timing.protocol import AVAILABILITY, FILL_NOTE, PRICE_NOTE

SCOPE = "결론의 적용 범위는 분류할 수 있었던 과거 후보와 지수다(판정 §2)"

RECORD_KIND = "뒤에 복원한 목록(봉인 KRX · 그날 이름 · 그날 지수명)"
STATUS_TEXT = {
    "A": "A. 연구 후보로 보존",
    "B": "B. 회고 설명 · 운영 판정 유보",
    "C": "C. 이 규칙 연구 종료",
    "D": "D. 판정 불가",
}
COND_TEXT = {
    "1_ci_lower_gt_0": "① Δ 의 95% 구간 하한 > 0",
    "2_hold_week_gain": "② 보류 주 평균 이득 ≥ 0.20%p",
    "3_rule_beats_always_hold": "③ 규칙 − 항상 보류 평균 > 0 · 95% 하한 > 0",
    "4_sub_wins": "④ 하위 기간 3개 중 2개 이상 Δ > 0",
    "5_downturn_ge_0": "⑤ 하락 뒤 주(KODEX 200 1개월 < 0) Δ ≥ 0",
    "6_hold_weeks": "⑥ 보류를 고른 주 ≥ 26",
    "7_official_same_sign": "⑦ 명칭 추정을 뺀 대조에서도 Δ > 0(같은 주)",
}
_RESULT_KEYS = (
    "status",
    "excluded",
    "pairs",
    "shifted",
    "imm",
    "hold",
    "rule",
    "K",
    "d_rule",
    "d_hold",
    "d_rule_hold",
)


def week_records(weeks: list[dict], rows: dict[str, list[dict]]) -> list[dict]:
    """주마다 한 기록 — 기록 종류 · 가격 기간 · 상태 · 이용 가능 시각 · 모의 체결 시각 · 원래 순위 · 결과."""
    by = {v: {r["D"]: r for r in rs} for v, rs in rows.items()}
    out = []
    for w in weeks:
        out.append(
            {
                "D": w["D"],
                "span": w["span"],
                "sub": w["sub"],
                "record_kind": RECORD_KIND,
                "price_window": [w["start"], w["D"]],
                "price_state": "종가",
                "availability": AVAILABILITY,
                "fills": {
                    "immediate": f"{w['e1']} 시가",
                    "hold_and_evaluation": f"{w['e2']} 시가",
                    "note": FILL_NOTE,
                },
                "gap_days": w["gap_days"],
                "bench_ret_1m": w["bench_ret_1m"],
                "population": w["population"],
                "top": w["top"],
                "unknown_top": w["unknown_top"],
                # 분모 갈래 · 미확인 사유(PLAN §2 · 검증자 r1 F2)
                "denominator": w["denominator"],
                "next_top": w["next_top"],
                "variants": {
                    v: {
                        **w["variants"][v],
                        "result_20bp": {
                            k: by[v][w["D"]][k]
                            for k in _RESULT_KEYS
                            if k in by[v][w["D"]]
                        },
                    }
                    for v in w["variants"]
                },
            }
        )
    return out


def _p(x: Optional[float], digits: int = 3) -> str:
    """비율 → %p 글(반올림은 글에서만)."""
    return "—" if x is None else f"{x * 100:+.{digits}f}%p"


def _pct(x: Optional[float]) -> str:
    return "—" if x is None else f"{x * 100:.2f}%"


def markdown(rep: dict[str, Any]) -> str:
    r = rep["result"]
    s = r["primary"]
    j = r["judgment"]
    c = s["counts"]
    d = s["delta"]
    rh = s["rule_minus_hold"]
    mc = rep["counts"]["main"]
    main_span = rep["spans"]["main"]
    lines = [
        "# POC7-01 주간 ETF 신규 후보의 즉시 참여와 한 주 보류 비교 · 공식 실행 결과",
        "",
        f"- 실행 {rep['run_id']} · 잠금 {rep['lock_id']} · {PRICE_NOTE}",
        f"- 이용 가능 시각: {AVAILABILITY} · {FILL_NOTE}",
        f"- {SCOPE}",
        "",
        "## 판정(PLAN §4 · 순서 D → C → A → B)",
        "",
        f"- **{STATUS_TEXT[j['status']]}**",
    ]
    for reason in j.get("reasons", []):
        lines.append(f"  - 사유: {reason}")
    if j.get("note"):
        lines.append(f"  - {j['note']}")
    lines += [
        f"- 실행 · 검산 성립: {rep['states']['execution']} · 규칙 효용: {j['status']} · "
        f"운영 채택: {rep['states']['adoption']}",
        "",
        f"## 본 구간(신호 {main_span[0]} ~ {main_span[1]} 범위 · 회고 자료)",
        "",
        f"- 분류(본 구간 상위 30): 공식 일치 짝 {mc['pairs_official']} · 명칭 추정 짝 "
        f"{mc['pairs_estimated']} · 미확인 행 {mc['unknown_rows']}(그중 나중에 폐지 "
        f"{mc['unknown_rows_delisted']}) · 분모 지수 중앙 공식 {mc['votes_official_median']} · "
        f"추정 {mc['votes_estimated_median']} · 미확인(빠짐) {mc['votes_unknown_median']}",
        f"- 주 {c['weeks']} · 후보 있는 주 {c['cand_weeks']} · 평가 가능 주 {c['evaluable_weeks']} · "
        f"보류를 고른 주 {c['hold_weeks']}",
        f"- 후보 짝 {c['pairs']} · 체결 가능 짝 {c['pairs_ok']} · 빠진 짝 {c['excluded']} · "
        f"주 상태 {c['status']}",
        f"- **Δ(규칙 − 즉시) = {_p(d['mean'], 4)}** · 95% 구간 [{_p(d['lo'], 4)}, {_p(d['hi'], 4)}] "
        f"(유효 주 {d['n_valid']} / 자리 {d['n_slots']})",
        f"- 규칙 − 항상 보류 = {_p(rh['mean'], 4)} · 95% 구간 [{_p(rh['lo'], 4)}, {_p(rh['hi'], 4)}]",
        f"- 항상 보류 − 즉시 = {_p(s['hold_minus_immediate'], 4)} · 보류 주 평균 이득 = "
        f"{_p(s['hold_week_gain'], 4)}",
        f"- 시장 기준(같은 기간 KODEX 200 · 판정 외): 즉시 − KODEX 200 = "
        f"{_p(s['immediate_minus_kodex200'], 4)} · "
        f"규칙 − KODEX 200 = {_p(s['rule_minus_kodex200'], 4)}",
        f"- 주 평균 수익: 즉시 {_p(s['means']['imm'], 4)} · 항상 보류 {_p(s['means']['hold'], 4)} · "
        f"규칙 {_p(s['means']['rule'], 4)} · KODEX 200 {_p(s['means']['K'], 4)}",
        "",
        "| 조건 | 충족 |",
        "|---|---|",
    ]
    for key, text in COND_TEXT.items():
        val = j.get("conditions", {}).get(key)
        lines.append(
            f"| {text} | {'—' if val is None else ('예' if val else '아니오')} |"
        )
    lines += ["", "### 하위 기간 · 하락 뒤 주 · 피함과 놓침", ""]
    for sub in s["subs"]:
        lines.append(
            f"- {sub['range'][0]} ~ {sub['range'][1]}: 평가 가능 주 {sub['evaluable_weeks']} · "
            f"보류 주 {sub['hold_weeks']} · Δ {_p(sub['delta'], 4)}"
        )
    dn = s["downturn"]
    lines.append(f"- 하락 뒤 주 {dn['weeks']} · Δ {_p(dn['delta'], 4)}")
    for key, text in (
        ("avoided", "피한 손실"),
        ("missed", "놓친 상승"),
        ("zero", "차이 없음"),
    ):
        part = s["split"][key]
        top = " · ".join(f"{dd} {_p(v, 3)}" for dd, v in part["top"])
        lines.append(
            f"- {text}: {part['weeks']}주 · 평균 {_p(part['mean'], 4)} · 큰 주 {top or '—'}"
        )
    m = s["mdd"]
    lines += [
        "",
        "### 1주 노출 경로 최대낙폭(비용 뺀 가격 비율 · 실제 계좌 아님 · D+1 → D'+1 주 간격)",
        "",
        f"- 즉시 {_pct(m['immediate'])} · 항상 보류 {_pct(m['always_hold'])} · 규칙 {_pct(m['rule'])} · "
        f"KODEX 200 {_pct(m['kodex200'])}",
        f"- 매수 횟수: 경로마다 {c['buys']['rule']}(짝 수) · KODEX 200 {c['kodex200_buys']} · "
        f"비용 편도 20bp(민감도 40bp) · 현금 수익 0% · 간격(거래일)별 주 {c['gap_days']} · "
        f"짝 {c['gap_pairs']}",
        f"- 다음 주 상위 30 에서 빠진 원래 후보 짝(비교에 남김) {c['next_week_dropout_pairs']} · "
        f"규칙 없음(분모 < 30) 주 {c['abstain_weeks']} · 개장 전 이용 불가 확인 주 "
        f"{c['preopen_unavailable_weeks']}",
        "",
        "## 대조 · 민감도(판정 외 · ⑦ 만 판정에 씀)",
        "",
    ]
    cmp7 = r["official_compare"]
    lines.append(
        f"- ⑦ 명칭 추정을 뺀 대조(같은 주 {cmp7['weeks']}): 포함 Δ {_p(cmp7['main'], 4)} · "
        f"공식 일치만 Δ {_p(cmp7['official'], 4)} · 결정이 달라진 주 {cmp7['decisions_differ']}"
    )
    for key, text in (
        ("alt_cost", "40bp"),
        ("aux", "보조 구간 2014 ~ 2020"),
        ("shift_sensitivity", "D'+1 체결 불가 짝 옮김"),
    ):
        dd = r[key]["delta"]
        lines.append(
            f"- {text}: Δ {_p(dd['mean'], 4)} · 95% [{_p(dd['lo'], 4)}, {_p(dd['hi'], 4)}] · "
            f"평가 가능 주 {r[key]['counts']['evaluable_weeks']}"
        )
    lines.append(f"- 기여가 가장 큰 5주를 뺀 Δ: {_p(s['delta_without_top'], 4)}")
    wc = r.get("worked_case")
    lines += ["", "## 사례(AC1 · AC2 · 본 구간 첫 평가 가능 보류 주)", ""]
    if wc is None:
        lines.append("- 평가 가능 주 없음")
    else:
        b = wc["votes"]["B"]
        lines.append(
            f"- 신호 {wc['D']} · 1개월 {wc['window'][0]} ~ {wc['window'][1]} · 결정 {wc['decision']} · "
            f"분모 {wc['votes']['votes']} · 오른 지수 {wc['votes']['up']} · "
            f"B {'—' if b is None else format(b, '.4f')}"
        )
        lines.append(
            f"- 즉시 매수 {wc['fills'][0]} 시가 · 보류 매수 · 평가 {wc['fills'][1]} 시가 · "
            f"다음 신호 {wc['next']} · 분모 갈래 {wc['denominator']}"
        )
        for x in wc["candidates"]:
            lines.append(
                f"  - 순위 {x['rank']} {x['code']}({x['index_name']}): P_E {x['p_e']:.4f} → "
                f"P_T {x['p_t']:.4f} · 즉시 값 {x['immediate_value']:.4f} · "
                f"보류 값 {x['hold_value']:.4f} · 다음 주 상위 30 {'남음' if x['in_next_top'] else '빠짐'}"
            )
        for x in wc["excluded"]:
            lines.append(
                f"  - 순위 {x['rank']} {x['code']}: 짝 제외({x['reason']}) · 다음 주 상위 30 "
                f"{'남음' if x['in_next_top'] else '빠짐'}"
            )
    lines.append("")
    return "\n".join(lines)
