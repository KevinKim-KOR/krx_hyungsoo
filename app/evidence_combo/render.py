"""POC5-20 — report.json 본문 → 사람이 읽는 report.md(설계 §5 '앞부분 = 질문 · 자료 기간 · 대상 수 ·
제외 요약 · 가격 구간별 네 조합 대조표').

숫자는 report.json 그대로 쓰고 표시만 소수 둘째 자리 %로 줄인다. 빈 칸은 '표본 없음'(0% 아님).
"""

from __future__ import annotations

from typing import Any, Optional

from app.evidence_combo.tables import COMBOS, OUTCOMES

EMPTY = "표본 없음"


def _span_text(sp: dict[str, Any]) -> str:
    if not sp.get("days"):
        return EMPTY
    return f"{sp['first']} ~ {sp['last']} · {sp['days']}일"


def _pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{v:+.2f}%"


def _stats(c: dict[str, Any], key: str) -> str:
    s = c[key]
    spread = f"[{_pct(s['p25'])} ~ {_pct(s['p75'])}]"
    return f"{_pct(s['median'])} {spread} · 날짜별 {_pct(s['date_median_of_medians'])}"


def _row(label: str, c: dict[str, Any]) -> str:
    if c["empty"]:
        return f"| {label} | 0 | 0 | 0 | {EMPTY} | {EMPTY} |"
    return (
        f"| {label} | {c['n']} | {c['tickers']} | {c['dates']} | "
        f"{_stats(c, OUTCOMES[0][0])} | {_stats(c, OUTCOMES[1][0])} |"
    )


def _band_tables(rows: list[dict[str, Any]]) -> list[str]:
    head = (
        "| 조합 | 건수 | 종목 | 기준일 | 끝점 변화 중앙값 [25% ~ 75%] · 날짜별 중앙값의 중앙값 | "
        "기간 중 최저 종가 변화 중앙값 [25% ~ 75%] · 날짜별 중앙값의 중앙값 |"
    )
    out: list[str] = []
    for row in rows:
        out += [f"#### {row['label']}", "", head, "|---|---:|---:|---:|---|---|"]
        out.append(_row("전체(이 구간)", row["all"]))
        for code, label, _, _ in COMBOS:
            out.append(_row(label, row["combos"][code]))
        out.append("")
    return out


def render_md(r: dict[str, Any]) -> str:
    u = r["universe"]
    b = u["base_dates"]
    lines = [
        "# POC5-20 가격 · 거래량 · 변동성 근거 조합 — 과거 사례 대조",
        "",
        f"생성 {r['generated_at']} · 종료일 {r['end']}",
        "",
        f"입력 식별 `{r['input_hash'][:16]}` · 본문 식별 `{r['body_hash'][:16]}`",
        "",
        "## 질문",
        "",
        r["question"],
        "",
        "## 자료 · 대상",
        "",
        f"- 기준일: {b.get('first', '—')} ~ {b.get('last', '—')} · {b['days']}거래일(2026 거래일 캘린더)",
        f"- 현재 보유 종목 {u['held_tickers']} 중 ETF {len(u['etf_targets'])}종목 대상 · "
        f"대상 밖(개별주) {len(u['non_etf_excluded'])}종목({', '.join(u['non_etf_excluded']) or '없음'})",
        f"- 종목 × 기준일 {u['pairs']}건 → 공통 표본 **{r['common_sample']}건**",
        f"- 실제 자료 기간(공통 표본의 기준일): {_span_text(u['common_sample_dates'])} · "
        f"시장 DB 최신 저장일 {u['db_latest']}",
        "",
        "## 제외 요약(정해진 순서에서 처음 걸린 사유 하나로 셈)",
        "",
        "| 순서 | 사유 | 건수 |",
        "|---:|---|---:|",
    ]
    lines += [
        f"| {i} | {e['label']} | {e['count']} |"
        for i, e in enumerate(r["exclusions"], 1)
    ]
    lines += [f"| — | 공통 표본 | {r['common_sample']} |", ""]
    lines += [
        f"## 가격 구간별 네 조합 대조(공통 표본 {r['common_sample']}건 · 결과는 %)",
        "",
        "각 칸: 중앙값 [25% ~ 75% 분위] · 날짜별 = 기준일마다 중앙값을 구한 뒤 그 중앙값(보조값).",
        "",
    ]
    lines += _band_tables(r["tables"]["all"])
    lines += ["## 정의", ""]
    lines += [f"- **{k}**: {v}" for k, v in r["definitions"].items()]
    lines += ["", "## 한계 · 편향", ""]
    lines += [f"- {n}" for n in r["notes"]]
    for key, title in (("front", "부록 A — 앞 기간"), ("back", "부록 B — 뒤 기간")):
        p = u[key]
        actual = _span_text(u[f"{key}_sample_dates"])
        lines += [
            "",
            f"## {title}({p.get('first', '—')} ~ {p.get('last', '—')} · {p['days']}거래일 · "
            "기준일로 나눔)",
            "",
            f"실제 자료 기간(이 기간 공통 표본의 기준일): {actual}",
            "",
        ]
        lines += _band_tables(r["tables"][key])
    return "\n".join(lines).rstrip("\n") + "\n"
