"""공식 실행 결과 글(report.md) — 판정 · 본 구간 지표 · 대안 · 참고 40bp · 보조 방향 · AC2 손 계산 주."""

from __future__ import annotations

from typing import Any, Optional

from app.candidate_compare.protocol import AVAILABILITY, PRICE_NOTE, RECORD_KIND

COND_TEXT = {
    "1_lower_bound": "① Δ 95% 구간 하한 > 0",
    "2_gain": "② Δ ≥ 0.20%p",
    "3_subs": "③ 기간 3개 중 2개 이상 Δ > 0",
    "4_mdd": "④ 평균 보유 중 낙폭 B − A ≤ 1.0%p",
    "5_turnover": "⑤ 평균 교체 B − A ≤ 0.5개",
    "6_diff_weeks": "⑥ 선택이 달라진 유효 주 ≥ 26",
    "7_alternative": "⑦ 대안 비교도 자료 기준 · ① ~ ⑥ 충족",
}


def pct(x: Optional[float], nd: int = 2) -> str:
    return "—" if x is None else f"{x * 100:+.{nd}f}%"


def pp(x: Optional[float], nd: int = 3) -> str:
    return "—" if x is None else f"{x * 100:+.{nd}f}%p"


def _block(title: str, s: dict[str, Any]) -> list[str]:
    bs = s.get("bootstrap") or {}
    mdd, turn, kd = s.get("mdd") or {}, s.get("turnover") or {}, s.get("kodex") or {}
    lines = [
        f"### {title}",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        f"| 주 · 선정한 주 · 유효 주 · 평가 불가 주 | {s['weeks']} · {s['ok_weeks']} · {s['valid_weeks']} · "
        f"{s['invalid_weeks']} |",
        f"| 확인 불가 자리 / 배정 자리 | {s.get('unconfirmed_slots')} / {s.get('assigned_slots')} "
        f"({pct(s.get('unconfirmed_share'))}) |",
        f"| Δ(B − A · 20거래일 · 비용 후) | {pp(s['delta'])} |",
        f"| 95% 구간 | {pp(bs.get('lo'))} ~ {pp(bs.get('hi'))} |",
        f"| 평균 A · B | {pct(s.get('mean_a'))} · {pct(s.get('mean_b'))} |",
        "| 기간별 Δ | "
        + " · ".join(f"{pp(x['delta'])}({x['weeks']}주)" for x in s.get("subs", []))
        + " |",
        f"| 선택이 달라진 유효 주 · 그 주 Δ | {s.get('diff_weeks')} · {pp(s.get('diff_delta'))} |",
        f"| 보유 중 낙폭 평균 A · B · B − A(주) | {pct(mdd.get('a_mean'))} · {pct(mdd.get('b_mean'))} · "
        f"{pp(mdd.get('b_minus_a'))}({mdd.get('weeks')}주) |",
        f"| 낙폭 하위 5%(95백분위) A · B | {pct(mdd.get('a_p95'))} · {pct(mdd.get('b_p95'))} |",
        f"| 평균 교체 A · B · B − A(주) | {turn.get('a_mean')} · {turn.get('b_mean')} · "
        f"{turn.get('b_minus_a')}({turn.get('weeks')}주) |",
        f"| KODEX 200 대비 A · B(비교 가능 주) | {pp(kd.get('a_minus_k'))} · {pp(kd.get('b_minus_k'))}"
        f"({kd.get('weeks')}주) |",
        f"| 상위 5주를 뺀 Δ | {pp(s.get('delta_without_top'))} |",
        f"| 빠진 자리 사유(평가 불가로 만든 자리) | {s.get('dropped_reasons')} |",
        f"| 현금 자리(거래 없음 확인) · 대안 현금 가정 · 대안 참고 평가액 | {s.get('cash_slots')} · "
        f"{s.get('assumed_cash_slots')} · {s.get('reference_slots')} |",
        "",
    ]
    return lines


def _case(c: Optional[dict[str, Any]]) -> list[str]:
    if c is None:
        return [
            "### AC2 손 계산 주",
            "",
            "선택이 갈리고 평가가 가능한 주가 없음(판정 §3 — 대신 시험 예로 확인).",
            "",
        ]
    lines = [
        "### AC2 손 계산 주(선택이 갈리고 평가가 가능한 첫 주)",
        "",
        f"- 신호일 {c['signal']} · 1개월 {c['window'][0]} → {c['window'][1]} · 네 주 "
        + " → ".join(c["weekly_dates"]),
        f"- 편입 {c['entry']} 시가 · 평가 {c['exit']} 시가 · 공통 후보군 {c['n_common']}개",
        f"- A = {', '.join(c['a'])} · B = {', '.join(c['b'])} · A 비용 후 {pct(c['ret_a'])} · "
        f"B {pct(c['ret_b'])} · d {pp(c['d'])}",
        "",
        "| 종목 | 원래 순위 | 공통 순위 | 1개월 | 오른 주 | 주 마감 5번(연결 값) |",
        "|---|---|---|---|---|---|",
    ]
    for code, p in c["picks"].items():
        closes = " · ".join("—" if v is None else f"{v:.4f}" for v in p["closes"])
        lines.append(
            f"| {code} | {p['orig_rank']} | {p['common_rank']} | {pct(p['ret'])} | "
            f"{p['up']} | {closes} |"
        )
    lines.append("")
    lines.append("| 기준 | 종목 | 편입 | 청산 | 편입 값 | 청산 값 |")
    lines.append("|---|---|---|---|---|---|")
    for rule, key in (("A", "slots_a"), ("B", "slots_b")):
        for s in c[key]:
            lines.append(
                f"| {rule} | {s['code']} | {s['entry']} | {s['exit']} | "
                f"{s.get('entry_px')} | {s.get('exit_px')} |"
            )
    lines.append("")
    return lines


def render(rep: dict[str, Any]) -> str:
    v = rep["verdict"]
    cond = v.get("conditions") or {}
    lines = [
        "# POC7-03 주간 ETF 후보 선택 비교 · 공식 실행 결과",
        "",
        f"- 잠금 `{rep['lock_id']}` · 실행 `{rep['run_id']}` · 기록 종류: {RECORD_KIND}",
        f"- **판정: {v['label']}**(자료 기준 {'충족' if v['data_ok'] else '미충족'})",
        f"- 표기: {PRICE_NOTE}",
        f"- 정보 이용: {AVAILABILITY}",
        "",
    ]
    if cond:
        lines += ["| 연구 후보 조건 | 충족 |", "|---|---|"]
        lines += [
            f"| {COND_TEXT[k]} | {'예' if ok else '아니오'} |" for k, ok in cond.items()
        ]
        lines.append("")
    lines += _block("본 구간(기본 비교 · 20bp)", rep["main"])
    lines += _block("본 구간(대안 비교 · 20bp)", rep["alt"])
    c40 = rep["cost40"]
    lines += [
        "### 참고 — 편도 40bp",
        "",
        f"- 유효 주 {c40['valid_weeks']} · Δ {pp(c40['delta'])}",
        "",
        "### 보조 구간(2014 ~ 2020 · 방향만 · 판정에 쓰지 않음)",
        "",
        f"- 유효 주 {rep['aux']['valid_weeks']} · Δ {pp(rep['aux']['delta'])}",
        "",
    ]
    lines += _case(rep.get("worked_case"))
    return "\n".join(lines) + "\n"
