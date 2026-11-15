"""POC6-30 — 섹터요약 보강 대조표 HTML(한 장 · 공개 ETF · 시장 수치와 대표 근거만).

입력은 `scripts/run_sector_constituents_comparison.py report` 가 만든 문서(report.json 과 같은 내용).
설계자 검토(2026-11-14) §1: 첫 줄 = 읽을 수 있는 사례(비중 1 · 2위 주식이 같은 ETF 묶음) →
그 아래 지금 요약으로 알 수 있는 것 / 구성종목을 보고 새로 알게 된 것.
판정 §3 · 검토 §2: 원천 기준일과 조회 시각 구분 · 순위 끝날과 같은 날 = 'M/D 기준 구성' ·
끝날보다 뒤 = 현재 편입 참고 · 미확보 · 기존 캐시 · 실패 · 종류 미확인을 확인 범위에 표시.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any, Mapping

SHOW_FIRST = 12  # 반복 주식 표에서 처음부터 보이는 줄 수(나머지는 펼쳐 보기)
STOCK_KIND_KEYS = ("domestic_stock", "foreign_stock")
# 검증자 r1 F2 — 공급자를 불러 실패한 것(수집 실패)과 부르지 않은 것(시간 초과 · 요청 안 함)을 나눈다
STATE_LABEL = {
    "new": "새로 받음",
    "cached": "기존 캐시",
    "failed": "수집 실패 · 자료 없음",
    "timeout": "미확보(시간 초과로 부르지 않음)",
    "missing": "미확보(부르지 않음)",
    "unknown": "확인 불가(알 수 없는 수집 상태)",
    "inconsistent": "확인 불가(받음 기록 · 저장 자료 없음)",
    "old_failed": "수집 실패 · 예전 자료",
    "old_timeout": "시간 초과로 부르지 않음 · 예전 자료",
    "old_missing": "부르지 않음 · 예전 자료",
    "old_unknown": "확인 불가(알 수 없는 수집 상태) · 예전 자료",
}
# 운영 요약(`build_summary`)이 응답을 만들지 못한 상태(검증자 r1 F4)
SUMMARY_STATUS_KO = {
    "missing": "시장 DB 없음",
    "empty": "저장된 가격 없음",
    "invalid": "시장 DB 읽기 실패",
    "no_common_period": "공통 기간을 정할 수 없음",
}
NO_GROUP = "비교 못 함 — 구성 자료가 2개 이상인 묶음 없음"
# 수집 기능이 남기는 사유(영어 · 코드) → 쉬운 한국어. 원문은 report.json 에 그대로 있다.
REASON_KO = (
    ("constituent refresh time budget exceeded", "시간 예산을 넘겨 건너뜀"),
    ("http_status_", "원천 응답 오류"),
    ("http_failed", "원천 연결 실패"),
    ("json_parse_failed", "원천 응답을 읽지 못함"),
    ("no_data", "원천에 구성 자료 없음"),
    ("unexpected_shape", "원천 응답 모양이 다름"),
    ("all_weights_invalid", "비중을 읽지 못함"),
    ("source unclear", "출처 불명이라 저장하지 않음"),
    ("fetch_unexpected", "수집 중 예상 못 한 오류"),
    ("constituent source unavailable", "원천에서 받지 못함"),
)
FILTER_LABEL = {
    "exclude_inverse": "인버스",
    "exclude_leveraged": "레버리지",
    "exclude_synthetic": "합성",
    "exclude_futures": "선물",
}
KIND_RULE = (
    "구성 행 종류(이 순서): 원화현금(ISIN KRD010010001) → 선물 · 옵션(시장 구분 4) → "
    "국내 ETF(ETF 목록에 있는 종목코드) → 채권(시장 구분 3 · 이름에 '채권') → "
    "국내 주식(시장 구분 0 · 1 · ISIN KR7 · 6자리 종목코드) → "
    "종류 미확인(시장 구분 2 · ISIN 칸이 12자리 모양이 아님) → 해외 ETF(시장 구분 2 · 이름에 'ETF') → "
    "종류 미확인(시장 구분 2 · 이름에 Fund · Trust · SPDR · iShares) → "
    "해외 주식(시장 구분 2 · 나머지) → 그 밖 종류 미확인. "
    "이름에 ETF 가 없는 해외 펀드는 저장 칸으로 가릴 수 없습니다."
)
EVIDENCE_RULE = (
    "사업군 ETF 편입 근거: 구성 자료가 있는 모든 ETF 중 기존 사업군 사전(28업종)으로 분류되는 "
    "ETF의 원본 1~10행. 주식 업종을 확정하거나 섹터 강세를 판정하는 근거로 단독으로 쓰지 않습니다. "
    "근거 ETF 이름은 이번 표본(공개 순위 30개) 안의 것만 적고, 표본 밖은 사업군 · 개수 · 구성 기준일만 "
    "적습니다(이름 · 코드는 저장소 밖 검증용 자료에만 둡니다)."
)
CASE_RULE = (
    "첫 줄 사례: ETF마다 원본 1~10행 중 주식 행의 앞 두 행을 '비중 1·2위 주식'으로 보고, "
    "두 주식이 같은 ETF를 한 묶음으로 모읍니다. 서로 다른 지수 계열이 2개 이상인 묶음만 고르고"
    "(같은 지수를 따르는 ETF끼리의 겹침은 지금 요약에서도 보입니다), ETF 수가 많은 묶음 → "
    "두 종목 합산 비중의 가장 작은 값이 큰 묶음 순으로 하나를 고릅니다. 비중이 빈 ETF는 넣지 않습니다."
)
CSS = "\n".join(
    (
        ":root{--bg:#f7f8fa;--card:#fff;--fg:#1d2330;--muted:#6b7280;--line:#e3e6eb;",
        "--accent:#1f5fbf;--warn:#b45309}",
        "@media (prefers-color-scheme: dark){:root{--bg:#14171c;--card:#1c2027;--fg:#e8eaee;",
        "--muted:#9aa3af;--line:#2c323b;--accent:#7fb0ff;--warn:#f0b35a}}",
        "body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.6 -apple-system,",
        'BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}',
        "main{max-width:1280px;margin:0 auto;padding:24px 20px 48px}",
        "h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px}",
        ".card{background:var(--card);border:1px solid var(--line);border-radius:10px;",
        "padding:14px 16px;margin:12px 0}",
        ".card h2{margin:0 0 6px}.grid .card{margin:0}",
        ".lead p{margin:4px 0;font-size:15px}.lead b{color:var(--accent)}",
        ".lead p.case{font-size:16px;margin-bottom:2px}",
        ".grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}",
        "@media (max-width:900px){.grid{grid-template-columns:1fr}}",
        "table{border-collapse:collapse;width:100%;font-size:13px}",
        "th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;",
        "vertical-align:top}",
        "th{color:var(--muted);font-weight:600;white-space:nowrap}",
        "td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}",
        "td.nw{white-space:nowrap}ul{margin:0;padding-left:16px}",
        ".tag{display:inline-block;margin-top:2px;padding:0 6px;border-radius:4px;",
        "font-size:12px;background:var(--accent);color:var(--card)}",
        ".tag-muted{display:inline-block;margin-top:2px;font-size:12px;color:var(--muted)}",
        ".muted{color:var(--muted)}.warn{color:var(--warn)}.scroll{overflow-x:auto}",
        "details summary{cursor:pointer;color:var(--accent)}",
    )
)


def md(d: str | None) -> str:
    if not d:
        return "—"
    return f"{int(d[5:7])}/{int(d[8:10])}"


def pct(v: float | None, sign: bool = False) -> str:
    if v is None:
        return "—"
    return f"{v:+.2f}%" if sign else f"{v:.2f}%"


def _kst(ts: str | None) -> str:
    """저장 시각(UTC · …Z 또는 +00:00) → 'M/D HH:MM KST'. 형식이 다르면 원문 그대로."""
    if not ts:
        return "—"
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return escape(ts)
    t = t.astimezone(timezone(timedelta(hours=9)))
    return f"{t.month}/{t.day} {t:%H:%M} KST"


def josa(word: str, with_final: str, without_final: str) -> str:
    """끝 글자 받침으로 조사를 고른다(한글이 아니면 '은(는)' 처럼 둘 다)."""
    ch = word[-1:] if word else ""
    if "가" <= ch <= "힣":
        return with_final if (ord(ch) - 0xAC00) % 28 else without_final
    return f"{with_final}({without_final})"


def _common_text(scope: Mapping[str, int], what: str) -> str:
    """공통 구성종목 개수 — 비교한 묶음이 없으면 '0건'이 아니라 비교 못 함(검증자 r1 F4 같은 종류)."""
    if not scope["compared"]:
        return f"{what} {NO_GROUP}"
    return f"{what} {scope['common']}건(구성 자료가 2개 이상인 묶음 {scope['compared']}개 비교)"


def _summary_status(q: Mapping[str, Any]) -> str:
    return SUMMARY_STATUS_KO.get(q.get("status"), "알 수 없는 상태")


def lead_case_text(case: Mapping[str, Any] | None) -> tuple[str, list[str]]:
    """첫 줄 사례 문장과 그 아래 보충 줄(없으면 빈 문장)."""
    if not case:
        return "", []
    a, b = (s["name"] for s in case["stocks"])
    dates = case["asofs"]
    when = (
        f"{md(dates[0])} 기준"
        if len(dates) == 1
        else f"구성 기준일 {md(dates[0])} ~ {md(dates[-1])}"
    )
    etfs = " · ".join(e["etf_name"] or e["etf"] for e in case["etfs"])
    n = len(case["etfs"])
    text = (
        f"{when} {etfs} {n}개 ETF의 비중 1·2위 주식은 모두 {a}{josa(a, '과', '와')} {b}입니다. "
        f"두 종목의 합산 비중은 ETF별 {pct(case['sum_min'])}~{pct(case['sum_max'])}이고, "
        f"서로 다른 지수 계열 {case['family_count']}개에 걸쳐 있습니다."
    )
    notes = []
    also = case.get("also_held") or []
    if also:
        who = " · ".join(
            f"{e['etf_name'] or e['etf']}(합산 {pct(e['sum_pct'])})" for e in also
        )
        notes.append(
            f"두 종목을 원본 1~10행 안에 함께 담은 ETF는 이 {n}개 말고 {len(also)}개 더 있습니다: {who}."
        )
    others = case.get("other_groups") or []
    if others:
        listed = " · ".join(
            f"{g['stocks'][0]}{josa(g['stocks'][0], '과', '와')} {g['stocks'][1]}"
            f"(ETF {g['etf_count']}개 · 합산 {pct(g['sum_min'])}~{pct(g['sum_max'])})"
            for g in others
        )
        notes.append(f"비중 1·2위 주식이 같은 다른 묶음: {listed}.")
    return text, notes


def headline(doc: Mapping[str, Any]) -> tuple[str, str]:
    """첫 줄 두 문장 — (지금 요약으로 알 수 있는 것, 구성종목을 보고 새로 알게 된 것)."""
    ov1 = doc["comparison_one"]["overview"]
    g1 = doc["comparison_one"]["groups"]
    sectors = [g["name"] for g in g1 if g["kind"] == "sector"]
    now = (
        f"지금 요약: 30개 중 업종(사업군)으로 묶인 ETF {ov1['sector_etf_count']}개"
        + (f"({', '.join(sectors)})" if sectors else "")
        + f" · 나머지는 기초지수별 {ov1['index_group_count']}묶음"
        + f" · 구성 자료 {ov1['constituents_etf_count']}/30 · "
        + _common_text(doc["comparison_one_scope"], "공통 구성종목")
    )
    c3, sc = doc["comparison_three"], doc["comparison_three_scope"]
    have = sum(1 for c in doc["coverage"] if c["has_data"])
    fresh = [x for x in c3 if not x["already_visible"]]
    if not fresh:
        # 검증자 r1 F3 — 비교 못 함 · 함께 든 주식 없음 · 모두 대조 2에도 보임을 나눈다
        skip = sc["unconfirmed_etfs"]
        scope = (
            f"(구성 자료 {have}/30 · 주식 행이 있는 확인된 지수 계열 {sc['family_count']}개"
            + (f" · 계열 미확인 ETF {skip}개는 세지 않음" if skip else "")
            + ")"
        )
        if not sc["comparable"]:
            head = (
                "비교 못 함 — 주식 행이 있는 확인된 지수 계열이 2개 이상이어야 합니다"
            )
        elif not c3:
            head = "없음 — 서로 다른 지수 계열 2개 이상에 함께 든 주식이 없습니다"
        else:
            head = (
                f"없음 — 서로 다른 지수 계열 2개 이상에 함께 든 주식 {len(c3)}종목은"
                " 모두 지금 방식(대조 2)에도 보입니다"
            )
        return now, f"구성종목을 보고 새로 알게 된 것: {head}{scope}."
    top = fresh[0]
    lead = ", ".join(f"{x['name']}({x['family_count']}개 계열)" for x in fresh[:4])
    ev = doc.get("evidence", {})
    by_sector: dict[str, int] = {}
    for x in fresh:
        for sec in sorted({e["sector"] for e in ev.get(x["key"], [])}):
            by_sector[sec] = by_sector.get(sec, 0) + 1
    # 설계자 검토 §1: 편입 '이력'을 확인한 것일 뿐 주식 업종 확인이 아니다 · 그 종목들도 가설
    hyp = "주식 자체의 업종 자료는 없어 이 종목들을 포함한 업종 해석은 모두 가설입니다"
    n_ev = sum(1 for x in fresh if ev.get(x["key"]))
    if by_sector:
        ranked = sorted(by_sector.items(), key=lambda kv: (-kv[1], kv[0]))
        if len(ranked) == 1:
            where = f"'{ranked[0][0]}' 사업군 ETF"
        else:
            where = (
                "사업군 ETF(" + " · ".join(f"'{k}' {n}종목" for k, n in ranked) + ")"
            )
        ev_text = f"그중 {n_ev}종목은 {where}에 편입된 이력을 확인했을 뿐이고, {hyp}"
    else:
        # 근거를 찾아본 사업군 ETF 가 0개면 '없음'이 아니라 확인 못 함(r1 정정 검토 · F4 같은 종류)
        n_sec = doc["evidence_scope"]["sector_etfs"]
        ev_text = (
            f"구성 자료가 있는 사업군 ETF {n_sec}개에서 편입 이력이 확인된 주식은 없고,"
            if n_sec
            else "사업군 ETF 편입 이력은 확인하지 못했고(구성 자료가 있는 사업군 ETF 없음),"
        ) + " 주식 자체의 업종 자료도 없어 업종 해석은 모두 가설입니다"
    new = (
        "구성종목을 보고 새로 알게 된 것: 서로 다른 지수 계열 2개 이상에 함께 든 주식 "
        + f"{len(fresh)}종목 — {lead}"
        + (" 외" if len(fresh) > 4 else "")
        + f". 가장 넓게 반복된 {top['name']}{josa(top['name'], '은', '는')}"
        + f" {top['etf_count']}개 ETF · 최대 비중 {pct(top['max_weight_pct'])}. "
        + f"{ev_text}(구성 자료 {have}/30)."
    )
    return now, new


def reason_ko(msg: str | None) -> str:
    """수집 사유 → 쉬운 한국어(모르는 사유는 '기타 사유')."""
    if not msg:
        return ""
    for code, ko in REASON_KO:
        if code in msg:
            return ko
    return "기타 사유"


def _filters(f: Mapping[str, bool]) -> str:
    out = [label for k, label in FILTER_LABEL.items() if f.get(k)]
    return " · ".join(out) + " 제외" if out else "제외 없음"


def _table(heads: tuple[str, ...], rows: list[str]) -> str:
    th = "".join(f"<th>{h}</th>" for h in heads)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _groups_html(groups: list[Mapping[str, Any]], labels: Mapping[str, str]) -> str:
    rows = []
    for g in groups:
        c = g["constituents"]
        name = ("업종 " if g["kind"] == "sector" else "") + (g["name"] or "미분류")
        parts = []
        for x in c["common"]:
            tag = ""
            if x.get("kind") not in STOCK_KIND_KEYS:
                label = escape(labels.get(x.get("kind"), "종류 미확인"))
                tag = f" <b class=warn>[{label}]</b>"
            parts.append(f"{escape(x['name'])} {x['etf_count']}{tag}")
        # 기존 `common_constituents` 상태 — 겹침 없음(no_overlap)만 '없음' · 나머지는 비교 못 함
        if parts:
            cell = " · ".join(parts)
        elif c.get("status") == "no_overlap":
            cell = "없음"
        else:
            cell = f"비교 못 함(구성 자료 {c['etf_with_data']}/{c['etf_total']})"
        rows.append(
            f"<tr><td>{escape(name)}</td><td class=n>{g['etf_count']}</td>"
            f"<td class=n>{c['etf_with_data']}/{c['etf_total']}</td>"
            f"<td>{cell}</td></tr>"
        )
    return _table(("묶음", "ETF", "구성 자료", "공통 구성종목(숫자 = ETF 수)"), rows)


def _evidence_cell(e2: list[Mapping[str, Any]], sample: set[str], n_sec: int) -> str:
    """근거 ETF 이름은 이번 표본(공개 순위 30개)에 든 것만 적는다(설계자 검토 §2-1 · 판정 Q3 적용 기준).

    예전에 구성종목을 저장한 ETF 목록에는 보유 · 관심 ETF 가 섞여 있어, 표본 밖은 사업군 · 개수 ·
    구성 기준일만 적는다. 이름 · 코드와 개별 근거는 git 제외 실행 폴더의 report.json 에만 있다.
    """
    if not e2:
        return (
            "사업군 ETF 편입 이력 없음"
            if n_sec
            else "확인 못 함(구성 자료가 있는 사업군 ETF 없음)"
        )
    secs = sorted({e["sector"] for e in e2})
    lines = [
        f"표본 안: {e['etf_name'] or e['etf']}({e['sector']} · 구성 {md(e['asof'])})"
        for e in e2
        if e["etf"] in sample
    ]
    outside: dict[str, list[str]] = {}
    for e in e2:
        if e["etf"] not in sample:
            outside.setdefault(e["sector"], []).append(e["asof"])
    for sec in sorted(outside):
        dates = " · ".join(md(d) for d in sorted(set(outside[sec])))
        lines.append(f"표본 밖: {sec} ETF {len(outside[sec])}개(구성 {dates})")
    return f"{escape(' · '.join(secs))} 사업군 ETF {len(e2)}개에 편입 이력" + "".join(
        f"<br><span class=muted>{escape(x)}</span>" for x in lines
    )


def _repeated_html(doc: Mapping[str, Any]) -> str:
    c3, ev = doc["comparison_three"], doc["evidence"]
    sample = {t["ticker"] for t in doc["snapshot"]["top"]}
    n_sec = doc["evidence_scope"]["sector_etfs"]
    if not c3:
        n = doc["comparison_three_scope"]["family_count"]
        if not doc["comparison_three_scope"]["comparable"]:
            return f"<p>비교 못 함 — 주식 행이 있는 확인된 지수 계열이 {n}개입니다(2개 이상 필요).</p>"
        return (
            "<p>서로 다른 지수 계열 2개 이상에 함께 든 주식이 없습니다"
            f"(주식 행이 있는 확인된 지수 계열 {n}개를 대조).</p>"
        )
    rows = []
    for x in c3:
        by_fam: dict[str, list[Mapping[str, Any]]] = {}
        for e in x["entries"]:
            by_fam.setdefault(e["family"] or "계열 미확인", []).append(e)
        fams = []
        for fam, es in by_fam.items():
            best = max(es, key=lambda e: e["weight_pct"] or 0)
            more = f" 외 {len(es) - 1}" if len(es) > 1 else ""
            n_strat = sum(1 for e in es if e["strategy"])
            strat = ""
            if n_strat:
                strat = (
                    " · 전략형" if len(es) == 1 else f" · 전략형 {n_strat}/{len(es)}"
                )
            fams.append(
                f"<li>{escape(fam)} — {escape(best['etf_name'] or best['etf'])}{more}{strat}"
                f" · 비중 {pct(best['weight_pct'])} · {best['rank']}위"
                f" · 구성 {md(best['asof'])}</li>"
            )
        seen = (
            "<span class=tag-muted>대조 2에도 보임</span>"
            if x["already_visible"]
            else "<span class=tag>새로 보임</span>"
        )
        rows.append(
            f"<tr><td><b>{escape(x['name'])}</b><br>{seen}</td>"
            f"<td class=n>{x['family_count']}</td><td class=n>{x['etf_count']}</td>"
            f"<td><ul>{''.join(fams)}</ul></td>"
            f"<td>{_evidence_cell(ev.get(x['key'], []), sample, n_sec)}<br>"
            "<span class=muted>업종 해석 = 가설</span></td></tr>"
        )
    heads = (
        "주식",
        "계열",
        "ETF",
        "계열별 대표 ETF · 실제 비중 · 구성 기준일",
        f"사업군 ETF 편입 근거(구성 자료가 있는 사업군 ETF {n_sec}개 대조)",
    )
    html = _table(heads, rows[:SHOW_FIRST])
    rest = rows[SHOW_FIRST:]
    if rest:
        html += (
            f"<details><summary>나머지 {len(rest)}종목 보기</summary>"
            f"{_table(heads, rest)}</details>"
        )
    return html


def _coverage_html(doc: Mapping[str, Any]) -> str:
    labels, fam = doc["kind_labels"], doc["families"]
    rows = []
    for c, t in zip(doc["coverage"], doc["snapshot"]["top"]):
        kinds = " · ".join(
            f"{labels.get(k, k)} {n}" for k, n in sorted(c["kinds"].items())
        )
        # 설계자 검토 §2-2: 끝날과 같은 날 = 'M/D 기준 구성' · 끝날보다 뒤만 '현재 편입 참고'
        if c["after_ranking_end"]:
            when = f"{md(c['asof'])} <b>현재 편입 참고</b>"
        elif c.get("on_ranking_end"):
            when = f"{md(c['asof'])} 기준 구성"
        else:
            when = md(c["asof"])
        index_name = t["classification"].get("index_name")
        family = fam.get(t["ticker"]) or index_name or "계열 미확인"
        if fam.get(t["ticker"]) and index_name:
            family += f" (공식 지수명 {index_name})"
        strat = " <b>전략형</b>" if t["classification"].get("strategy") else ""
        notes = []
        if c.get("collect_message"):
            notes.append(reason_ko(c["collect_message"]))
        if c["state"] == "new" and c.get("saved_asof") and c["saved_asof"] != c["asof"]:
            notes.append(f"받은 기준일 {md(c['saved_asof'])} · 표는 더 최근 자료 사용")
        msg_html = "".join(f"<br><span class=muted>{escape(n)}</span>" for n in notes)
        state = escape(STATE_LABEL.get(c["state"], c["state"]))
        rows.append(
            f"<tr><td class=n>{t['rank']}</td><td>{escape(t['name'] or t['ticker'])}{strat}<br>"
            f"<span class=muted>{escape(t['ticker'])} · {escape(family)}</span></td>"
            f"<td class=n>{pct(t['return_pct'], True)}</td>"
            f"<td class=nw>{state}{msg_html}</td><td class=nw>{when}</td>"
            f"<td class=nw>{_kst(c['fetched_at'])}</td>"
            f"<td class=n>{c['top_count']}행 / {c['stored_count']}행</td><td>{kinds or '—'}</td>"
            f"<td class=n>{pct(c['raw_weight_sum'])}</td>"
            f"<td class=n>{pct(c['stock_weight_sum'])}</td></tr>"
        )
    heads = (
        "순서",
        "ETF · 지수 계열",
        "1개월",
        "수집 결과",
        "원천 기준일",
        "조회 시각",
        "읽은 행(1~10 / 저장)",
        "1~10행 종류",
        "원본 비중 합",
        "주식 비중 합",
    )
    return f"<div class=scroll>{_table(heads, rows)}</div>"


def _q5_html(doc: Mapping[str, Any]) -> str:
    labels = doc["kind_labels"]
    lines = []
    for basis, label in (("one_month", "1개월"), ("three_month", "3개월")):
        q = doc["q5"][basis]
        found = q["non_stock_common"]
        items = [
            f"{escape(f['group'] or '')} 묶음 '{escape(f['name'])}'"
            f"({escape(labels.get(f['kind'], str(f['kind'])))})"
            for f in found
        ]
        # 검증자 r1 F4 — 요약을 못 만들었거나 비교한 묶음이 없으면 '0건'이라 쓰지 않는다
        if q["status"] != "ok":
            text = (
                f"비교 못 함 — 사본으로 운영 요약을 만들지 못함({_summary_status(q)})"
            )
        elif not q["groups_compared"]:
            text = NO_GROUP
        else:
            text = (
                " · ".join(items) or "주식 외 공통 항목 0건"
            ) + f"(공통 구성종목 {q['common_checked']}건 · 묶음 {q['groups_compared']}개 비교)"
        lines.append(f"<li>{label} 상·하위: {text}</li>")
    return f"<ul>{''.join(lines)}</ul>"


def _price_text(s: Mapping[str, Any]) -> str:
    ps, n = s["price_state"], s["counts"]["population"]
    if ps.get("after_close_count") == n:
        span = f"{_kst(ps['after_close_fetched_min'])} ~ {_kst(ps['after_close_fetched_max'])}"
        return f"{n}개 모두 마감 뒤 저장({span})"
    return (
        f"장중 {ps.get('intraday_count')} · 마감 뒤 {ps.get('after_close_count')}"
        f" · 확인 불가 {ps.get('unknown_count')}"
    )


def _details_html(doc: Mapping[str, Any]) -> str:
    s, col = doc["snapshot"], doc["collect"]
    batches = " / ".join(
        f"{b['label']} {len(b['tickers'])}개(받음 {b['fetched'] - b['failed']}"
        f" · 실패 {b['failed']} · 캐시 {b['cached']} · 시간 초과 {b['skipped']})"
        for b in col["batches"]
    )
    csv_name = escape(str(doc["official"].get("name")))
    match = doc["copy_top_matches_snapshot"]
    if match is None:  # 사본으로 요약을 만들지 못함 — '다름'이 아니다
        same = (
            f"비교 못 함({_summary_status(doc['q5']['one_month'])} · 보관 목록을 사용)"
        )
    else:
        same = "같음" if match else "다름(보관 목록을 사용)"
    return "".join(
        (
            "<details class=card><summary>자세히 — 규칙 · 수집 기록 · 원본</summary>",
            f"<p>{CASE_RULE}</p>",
            f"<p>{KIND_RULE}</p>",
            f"<p>지수 계열: 공식 기초지수명(KRX 기준정보 {csv_name})이 같으면 한 계열 · "
            "판정이 확인한 Dow Jones U.S. Dividend 100 가격지수형 1개와 커버드콜 3개는 한 계열 · "
            "공식 지수명이 없으면 계열 미확인.</p>",
            f"<p>{EVIDENCE_RULE}</p>",
            f"<p>수집: 기존 네이버 수집 기능 · 대조용 DB 사본 · 요청 기준일 {md(col['request_asof'])}"
            f" · 외부 호출 {col['external_calls']}/{col['call_limit']}회 · {escape(batches)}"
            f" · {_kst(col['started_at'])} ~ {_kst(col['finished_at'])}</p>",
            f"<p>보관 응답 SHA-256 {escape(s['sha256'])} · 사본으로 다시 계산한 1개월 상위 30 = "
            f"보관 목록과 {same}</p>",
            "</details>",
        )
    )


def render_html(doc: Mapping[str, Any]) -> str:
    s = doc["snapshot"]
    now, new = headline(doc)
    case, case_notes = lead_case_text(doc.get("lead_case"))
    case_html = (
        f"<p class=case><b>{escape(case)}</b></p>"
        + "".join(f"<p class=muted>{escape(x)}</p>" for x in case_notes)
        if case
        else ""
    )
    ov1, ov2 = doc["comparison_one"]["overview"], doc["comparison_two"]["overview"]
    c2, c3 = doc["comparison_two"], doc["comparison_three"]
    s2, s3 = doc["comparison_two_scope"], doc["comparison_three_scope"]
    fresh = sum(1 for x in c3 if not x["already_visible"])
    if s2["compared"]:
        card2 = (
            _common_text(s2, "같은 묶음 안 공통 구성종목")
            + f"<br>그중 주식 외 항목 {len(c2['non_stock_common'])}건"
        )
    else:
        card2 = _common_text(s2, "같은 묶음 안 공통 구성종목")
    if s3["comparable"]:
        card3 = f"서로 다른 계열 2개 이상 {len(c3)}종목 · 그중 새로 보임 {fresh}종목"
    else:
        card3 = f"비교 못 함 — 주식 행이 있는 확인된 지수 계열 {s3['family_count']}개"
    if s3["unconfirmed_etfs"]:
        card3 += f" · 계열 미확인 ETF {s3['unconfirmed_etfs']}개는 세지 않음"
    multi = [
        g for g in c2["groups"] if g["etf_count"] > 1 or g["constituents"]["common"]
    ]
    single = sum(1 for g in c2["groups"] if g["etf_count"] == 1)
    period = f"{md(s['period']['start'])} → {md(s['period']['end'])}"
    regime = f"{escape(s['regime']['label'] or '')}({md(s['regime']['asof'])})"
    parts = (
        "<!doctype html><html lang=ko><head><meta charset=utf-8>",
        '<meta name=viewport content="width=device-width,initial-scale=1">',
        f"<title>POC6-30 섹터요약 대조표</title><style>{CSS}</style></head><body><main>",
        "<h1>1개월 상위 30개 ETF — 구성종목으로 업종을 더 읽을 수 있나</h1>",
        f"<div class=muted>{period} 1개월 · {_filters(s['filters'])}"
        f" · 비교한 ETF {s['counts']['population']}개 중 상위 30 · 가격 {_price_text(s)}"
        f" · 시장 판정 {regime}</div>",
        f'<div class="card lead">{case_html}<p>{escape(now)}</p><p><b>{escape(new)}</b></p></div>',
        "<div class=grid>",
        "<div class=card><h2>대조 1 · 지금 요약</h2>",
        f"<p>업종 묶음 {ov1['sector_etf_count']}/30 · 기초지수별 {ov1['index_group_count']}묶음<br>",
        f"구성 자료 {ov1['constituents_etf_count']}/30 · "
        f"{_common_text(doc['comparison_one_scope'], '공통 구성종목')}</p></div>",
        "<div class=card><h2>대조 2 · 자료 보충 + 지금 방식</h2>",
        f"<p>구성 자료 {ov2['constituents_etf_count']}/30 · {card2}</p></div>",
        "<div class=card><h2>대조 3 · 지수 계열을 건넌 공통 주식</h2>",
        f"<p>{card3}<br>",
        "주식 행만 · 원본 1~10행 · 업종 해석은 가설</p></div>",
        "</div>",
        f'<h2>반복 주식 근거(대조 3)</h2><div class="card scroll">{_repeated_html(doc)}</div>',
        "<h2>대조 2 — 같은 묶음 안 공통 구성종목(지금 방식 그대로)</h2>",
        f'<div class="card scroll">{_groups_html(multi, doc["kind_labels"])}',
        f"<p class=muted>ETF 1개짜리 묶음 {single}개는 공통 구성종목을 비교할 수 없어"
        " 표에서 뺐습니다.</p></div>",
        f"<h2>확인 범위 — ETF별</h2><div class=card>{_coverage_html(doc)}",
        "<p class=muted>원천 기준일 = 네이버가 밝힌 구성 기준일 · 조회 시각 = 이 PC 가 받아 저장한 시각."
        f" 원천 기준일이 순위 끝날({md(s['end_date'])})과 같으면 '{md(s['end_date'])} 기준 구성'으로,"
        " 끝날보다 뒤이면 '현재 편입 참고'로 적습니다."
        f" 순위 기간({md(s['period']['start'])} ~ {md(s['period']['end'])}) 중 편입이 어떻게 바뀌었는지와"
        " 수익에 얼마나 기여했는지를 확인하려면 그 기간의 보유 내역과 수익률 자료가 필요합니다.</p></div>",
        "<h2>현금 · 파생이 기존 공통 구성종목에 섞이는지(사본 재현)</h2>",
        f"<div class=card>{_q5_html(doc)}",
        "<p class=muted>대조용 사본으로 지금 「섹터요약」 계산을 그대로 돌린 결과(보유 정보 없이)."
        " 운영 코드는 바꾸지 않았습니다.</p></div>",
        _details_html(doc),
        "</main></body></html>",
        "",
    )
    return "\n".join(parts)
