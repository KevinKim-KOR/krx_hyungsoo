"""POC6-04 — 보고서 글(report.md). 판정 · 표 값은 report.json 그대로(반올림은 글에서만)."""

from __future__ import annotations

from typing import Any

from app.d20_pooled import study as S

_M = (S.MEDIAN, S.RIDGE, S.HGB)
MONTHLY_NOTE = " (월 분배 · 조정 사유 미확인)"


def _pp(v: Any) -> str:
    return "—" if v is None else f"{v:.4f}"


def _x100(v: Any) -> Any:
    return None if v is None else v * 100


def _score_rows(label: str, sc: dict[str, Any]) -> list[str]:
    out = []
    for m in _M:
        s = sc[m]
        out.append(
            f"| {label} | {m} | {_pp(s['overall'])} | "
            + " | ".join(_pp(x) for x in s["blocks"])
            + f" | {s['dates']} | {s['rows']} |"
        )
    return out


def _pct(v: Any) -> str:
    return "—" if v is None else f"{v * 100:.2f}%"


def _table(rows: list[tuple[str, dict[str, Any]]], labels=None) -> list[str]:
    """날짜 균형 MAE 표(%p). labels = 구간 이름(보조 (b) 는 3구간 하나)."""
    labels = labels or ["1구간", "2구간", "3구간"]
    head = (
        "| 묶음 | 방법 | 전체 MAE(%p) | "
        + " | ".join(f"{x} MAE(%p)" for x in labels)
        + " | 날짜 | 행 |"
    )
    sep = "|---|---|---:|" + "---:|" * len(labels) + "---:|---:|"
    out = [head, sep]
    for label, sc in rows:
        out += _score_rows(label, sc)
    return out


def render_md(r: dict[str, Any]) -> str:
    L = [
        "# POC6-04 D20 확장 표본 재현 검증 — 탐색적 · CPU",
        "",
        f"- 실행 `{r['run_id']}` · {r['created_at']} · 상태 **{r['status']}**"
        + (f" · 사유 {r['reason']}" if r.get("reason") else ""),
        f"- 공식 snapshot digest `{r['official_digest']}` · recipe `{r['recipe_digest']}`"
        f" · B `{r['snapshots']['B']['digest'][:16]}…` · C `{r['snapshots']['C']['digest'][:16]}…`",
        f"- 공통 4종 {', '.join(r['four'])} · C {len(r['c_etfs'])}종 {', '.join(r['c_etfs'])}",
        "",
    ]
    if r["status"] != "COMPLETED":
        L += ["## 멈춘 사유", ""] + [f"- {p}" for p in r.get("problems") or []]
        if r.get("control"):
            L.append(f"- 대조군: {r['control']}")
        L += ["", "## 한계", ""] + [f"- {x}" for x in r["limits"]]
        return "\n".join(L) + "\n"
    c4, c12 = r["common4"], r["c12"]
    td = c4["truth_diff_A_vs_B"]
    ctrl = r["control"]
    L += [
        "## 주 판정 — C 12종(탐색적 · POC6-02 세 조건 · 반올림 전 값)",
        "",
        f"- **{c12['verdict']['label']}**"
        + (
            f" · {' / '.join(c12['verdict']['reasons'])}"
            if c12["verdict"]["reasons"]
            else ""
        ),
    ]
    for b, j in c12["verdict"]["against"].items():
        if j.get("base_zero"):
            continue
        cond = j["conditions"]
        L.append(
            f"  - 대 {b}: 전체 개선 {j['relative_improvement'] * 100:.2f}%"
            f"(≥5% {cond['overall_improve']}) · 엄격히 이긴 구간 {j['block_wins']}"
            f"(≥2 {cond['block_wins']}) · 5% 넘는 악화 없음 {cond['no_block_worse_5pct']}"
            + (
                f" · 경계 근처 {', '.join(j['near_boundary'])}"
                if j["near_boundary"]
                else ""
            )
        )
    L += [f"- 방향 비교(판정 아님): {n}" for n in r["direction_notes"]] or [
        "- 방향 비교(판정 아님): 보조 표의 방향이 주 분석과 같음"
    ]
    L += ["", "## T1 공통 4종 · 같은 행(A · B · C 의 4종 평가)", ""]
    L += _table(
        [("A 공식", c4["A"]), ("B 사본 4종", c4["B"]), ("C 의 4종 평가", c4["C_on_4"])]
    )
    L += [
        "",
        f"- 정답 차 |A − B|(같은 {td['rows']}행): 평균 {_pp(_x100(td['mean_abs']))}%p"
        f" · 최대 {_pp(_x100(td['max_abs']))}%p"
        f" · 0.1%p(수익률 0.001) 초과 {td['over_0_001']}행",
        f"- 대조군 MEDIAN · RIDGE |B − C|(수익률 단위): 최대 {ctrl['max_abs_diff']}"
        f" · 허용 {ctrl['tolerance']} · 초과 {ctrl['over_tolerance_by_method']}",
        "- A 와 B · C 는 정답이 달라 MAE 를 빼지 않는다. B 대 C 는 같은 정답 · 같은 행이며, HGB 차이는 종목 · 과거 학습 이력 · "
        "날짜별 가중치가 함께 확대된 효과다.",
        "",
        "## T2 C 내부 12종",
        "",
    ]
    L += _table([("C 12종", c12["scores"])])
    L += [
        "",
        "| ETF | 행 | MEDIAN MAE(%p) | RIDGE MAE(%p) | HGB MAE(%p) | KRX 불일치율(±1원) | 대조 불가 짝"
        " | KRX 대조 관측 기간(MAE 시험 기간과 다름) |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    rates = r["uncertainty"]["krx_rates"]
    for t, x in c12["per_etf"].items():
        k = rates[t]
        L.append(
            f"| {t}{MONTHLY_NOTE if t in r['uncertainty']['monthly_unconfirmed'] else ''}"
            f" | {x['rows']} | "
            + " | ".join(_pp(x["mae_pp"][m]) for m in _M)
            + f" | {_pct(k['mismatch_rate'])} | {k['not_comparable']}"
            + f" | {k['observed_from']} ~ {k['observed_to']} |"
        )
    for c, per in c12["diagnostics"]["per_etf_spread"].items():
        for b, x in per.items():
            L.append(
                f"- {c} 대 {b}: ETF 개선 {x['improved_etfs']} · 악화 {x['worse_etfs']}"
            )
    tr = r["uncertainty"]["train_rows_by_etf"]
    L += ["", "| ETF | 공동 학습 행(1 · 2 · 3구간) |", "|---|---|"]
    L += [f"| {t} | {' · '.join(str(n) for n in v)} |" for t, v in tr.items()]
    d = c12["diagnostics"]["deep_loss"]
    L += [
        "",
        f"- D20 ≤ {d['threshold'] * 100:.0f}% 사후 진단(미래 정답으로 고른 행 · 사전 탐지 성공률 아님)"
        f": 행 {d['rows']} · 날짜 {d['dates']}",
    ]
    for m in _M:
        if m in d:
            L.append(
                f"  - {m}: MAE {_pp(d[m]['mae_pp'])}%p · 위험 과소 추정 평균 {_pp(d[m]['under_pp'])}%p"
            )
    a, bb = r["aux_a"], r["aux_b"]
    L += ["", f"## 보조 (a) {a['name']}(재학습 0 · 별도 판정 없음)", ""]
    L += _table([("C 10종 평가", a["scores"])])
    rd = bb["rows_dates"]
    L += [
        "",
        f"## 보조 (b) {bb['name']}(재학습 0 · 별도 판정 없음)",
        "",
        f"- 기준: 3구간 시험 행 중 목표 창(정답 계산의 20거래일) 마지막 날 ≤ {r['rules']['krx_end_for_aux_b']}"
        " (그 가격이 ±1원 대조를 모두 통과했다는 뜻 아님)",
        f"- 3구간 남은 행: B {rd['B']['rows']}({rd['B']['dates']}일 · 시험 날짜 {rd['B']['first']}"
        f" ~ {rd['B']['last']}) · 뺀 행 {rd['removed_B']}"
        f" / C {rd['C']['rows']}({rd['C']['dates']}일) · 뺀 행 {rd['removed_C']}",
        "",
    ]
    L += _table(
        [("B", bb["B"]), ("C 의 4종", bb["C_on_4"]), ("C 12종", bb["C"])],
        labels=["3구간"],
    )
    L += ["", "## 방향 비교(판정 아님)", "", f"- {r['directions']}"]
    L += [f"- {n}" for n in r["direction_notes"]] or ["- 보조 방향이 주 분석과 같음"]
    L += ["", "## 한계", ""] + [f"- {x}" for x in r["limits"]]
    return "\n".join(L) + "\n"
