"""POC6-01 — `GET /market/flow-context` 응답 조립(저장 자료만 · 외부 조회 0 · 쓰기 0).

문장 줄은 여기서 한 번 만들고 화면 · AI 복사문 · 판단 근거 미리보기 · AI 세션 전달이 그대로 쓴다(세 경로의
숫자 · 기간 · 문구가 같다 · 설계 §4). 계산 규칙은 `app/supply_fx_oil_calc.py`.

- 끝일 D = 코스피와 코스피 투자자별 수급이 함께 확인된 가장 최근 거래일(설계 §3). 수급이 아직 없으면
  D = 코스피 최신일이고 수급 줄은 '자료 없음'으로 둔다(빈 칸을 만든 뒤 완료처럼 보이지 않게).
- 단기는 자료마다 최신 E(환율 · WTI 가 D 보다 늦을 수 있음 · 기간 선택과 무관). E < D 면 '늦음'.
- 해석은 설계 §4 표 4행에 해당할 때만(가능성 + 다른 설명 · 확정이 아님) · 기간마다 그 기간 변화로(기간 선택은
  묶음 전체에 하나 · 설계 §3). 유가 쪽 글로벌 보조 근거는 기존 저장 VIX(기간을 덮을 때만).
- 「오늘의 투자 점검」 두 줄은 6개월 고정(그 화면에는 기간 선택이 없음 · 끝일 D 를 적음).
- 확인할 수 없는 것을 '없음 · 해당 없음'으로 쓰지 않는다(검증자 r1 F1 · F2): 부분 집계 · 부분 기간 · 20일 비교
  불가는 오늘 줄에도 적고, 최근 큰 변화 '없음'은 모든 자료를 비교했을 때만 · 아니면 확인 못 한 자료와 사유를
  적는다. 해석도 입력이 없거나 부분이면 '확인 못 한 조합'으로 적는다(조건 미해당으로 바꾸지 않음).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.market_data_store import DEFAULT_DB_PATH
from app.supply_fx_oil_calc import (
    DEFAULT_PERIOD,
    PERIODS,
    change_over,
    flow_event_coverage,
    flow_events,
    flow_short,
    md,
    num,
    pct,
    period_boundary,
    period_sum,
    price_event_coverage,
    price_events,
    short_term,
    signed,
    window,
    won,
)
from app.supply_fx_oil_store import (
    USDKRW,
    WTI,
    read_benchmark_collected_at,
    read_benchmark_series,
    read_investor_flows,
    read_macro_series,
)

KST = timezone(timedelta(hours=9))
MAIN_INVESTORS = (
    ("foreign", "외국인"),
    ("individual", "개인"),
    ("institution", "기관계"),
    ("other_corp", "기타법인"),
)
SHORT_INVESTORS = (("foreign", "외국인"), ("institution", "기관계"))
PRICE = (("kospi", "코스피", "pt"), ("usdkrw", "원/달러", "원"), ("wti", "WTI", "달러"))
NO_FLOW = "투자자별 수급 자료 없음 — 시장 갱신 뒤 다시 확인(키움 인증 · 등록 IP)"
LIMITS = [
    "외국인 순매도는 주식 매매 통계다 — 같은 금액이 환전 · 해외 송금됐다는 뜻이 아니다(채권 · 예금으로 남을 수 있음).",
    "외국인 순매도와 개인 순매수의 차이를 '부족액'으로 보지 않는다 — 기관 · 기타법인 등 다른 주체가 있다.",
    "수급 = 키움 REST ka10051(KRX 코스피 종합 · 억원 단위 반올림 · 순매수만 · 외국인 = 내국인대우외국인 제외 · "
    "기관계 = 금융투자 · 보험 · 투신 · 은행 · 종신금 · 기금 · 사모 합) · 거래대금 대비 비율은 제공되지 않아 생략.",
    "원/달러 = Yahoo KRW=X 일봉 종가(런던 날짜) · WTI = Yahoo CL=F 근월물 선물 일봉 종가(뉴욕 날짜 · 만기 교체 영향 "
    "가능 · 공식 정산가 아님) — 한국 15:30 값이 아니며 같은 날짜 라벨도 관측 시각은 다르다.",
    "3배 · 직전 20개 범위는 이 화면의 관측 표시 기준이다 — 검증된 위험 · 수익 임계치가 아니다. 장중 움직임은 보지 "
    "않는다(완료된 일별 값만). 이 표는 최신 확보 자료이며 당시 알았던 값(PIT)이 아니다.",
]


def kst_stamp(iso: Optional[str]) -> str:
    """저장 시각(UTC ISO · 'Z' 가능) → 'M/D HH:MM KST'. 없거나 읽을 수 없으면 '—'."""
    if not iso:
        return "—"
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return "—"
    k = (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(KST)
    return f"{k.month}/{k.day} {k:%H:%M} KST"


def _eok_points(points: list[tuple[str, int]]) -> list[tuple[str, float]]:
    return [(d, float(v)) for d, v in points]


def build_market_flow_context(
    *, db_path: Path = DEFAULT_DB_PATH, now: Optional[datetime] = None
) -> dict:
    now = now or datetime.now(timezone.utc)
    kospi = read_benchmark_series("KOSPI", db_path=db_path)
    vix = read_benchmark_series("VIX", db_path=db_path)
    fx, fx_at = read_macro_series(USDKRW, db_path=db_path)
    oil, oil_at = read_macro_series(WTI, db_path=db_path)
    flows_raw, flow_at = read_investor_flows(db_path=db_path)
    flows = {k: _eok_points(flows_raw.get(k, [])) for k, _ in MAIN_INVESTORS}
    series = {"kospi": kospi, "usdkrw": fx, "wti": oil}
    out: dict = {
        "generated_at": now.astimezone(KST).isoformat(timespec="seconds"),
        "D": None,
        "has_flows": bool(flows["foreign"]),
        "series": {},
        "periods": {},
        "windows": {"lines": []},
        "short_lines": [],
        "events": [],
        "event_check": {
            "checked": [],
            "unchecked": [],
            "unchecked_text": None,
            "empty_text": None,
        },
        "interpretation": {},
        "limits": LIMITS,
        "status": [],
        "today_lines": [],
        "ai_text": {},
    }
    if not kospi:
        msg = "코스피 저장 자료가 없어 계산하지 않음(시장 갱신 뒤 다시 확인)"
        out["today_lines"] = [f"시장 흐름: {msg}"]
        out["ai_text"] = {
            code: f"[시장 흐름 — 수급 · 환율 · 유가 · 기간 {name}]\n- {msg}"
            for code, name, _ in PERIODS
        }
        return out
    kdates = [d for d, _ in kospi]
    fdates = {d for d, _ in flows["foreign"]}
    common = [d for d in kdates if d in fdates]
    D = common[-1] if common else kdates[-1]
    out["D"] = D
    collected = {
        "kospi": read_benchmark_collected_at("KOSPI", db_path=db_path),
        "usdkrw": fx_at,
        "wti": oil_at,
        "flows": flow_at,
    }
    for key, label, unit in PRICE:
        pts = series[key]
        out["series"][key] = {
            "label": label,
            "unit": unit,
            "E": pts[-1][0] if pts else None,
            "points": pts,
            "collected_at": collected[key],
        }
    out["series"]["flows"] = {
        "label": "투자자별 순매수",
        "unit": "원",
        "E": flows["foreign"][-1][0] if flows["foreign"] else None,
        "investors": flows,
        "collected_at": flow_at,
    }

    for code, name, _ in PERIODS:
        b = period_boundary(code, D)
        start = next((d for d in kdates if b < d <= D), None)
        # 기간을 덮음 = 경계일 이하 코스피 저장일이 있음. 없으면 저장 자료가 기간 중간부터라 앞부분이 빠진
        # '부분 기간'이다(있어야 할 날도 코스피 저장일로 세므로 부분 집계만으로는 드러나지 않음).
        covered = kdates[0] <= b
        lines = []
        if not covered:
            lines.append(
                f"부분 기간 — {b} 이전 저장 자료가 없어 {kdates[0]}부터만 계산(요청 기간 앞부분 빠짐)"
            )
        kchg = change_over(kospi, b, D)
        lines.append(
            f"코스피 {num(kchg['from'], 'pt')} → {num(kchg['to'], 'pt')} ({pct(kchg['pct'])} · "
            f"{md(kchg['from_date'])} 종가 → {md(kchg['to_date'])})"
            if kchg
            else "코스피 자료 없음(기간을 덮는 저장 값이 없음)"
        )
        inv = {k: period_sum(flows[k], kdates, b, D) for k, _ in MAIN_INVESTORS}
        if out["has_flows"]:
            f = inv["foreign"]
            part = f" · 부분 집계 {f['days']}/{f['expected']}일" if f["partial"] else ""
            if not covered:
                part += f" · 부분 기간({start}부터)"
            way = "누적 순매도" if f["sum"] < 0 else "누적 순매수"
            lines.append(
                f"외국인 {way} {won(f['sum'])} · 개인 {won(inv['individual']['sum'])} · 기관계 "
                f"{won(inv['institution']['sum'])} · 기타법인 {won(inv['other_corp']['sum'])}{part}"
            )
        else:
            lines.append(NO_FLOW)
        moves = {}
        for key, label, unit in PRICE[1:]:
            c = change_over(series[key], b, D)
            moves[key] = c
            lines.append(
                f"{label} {num(c['from'], unit)} → {num(c['to'], unit)} ({pct(c['pct'])} · "
                f"{md(c['from_date'])} → {md(c['to_date'])})"
                if c
                else f"{label} 자료 없음(기간을 덮는 저장 값이 없음)"
            )
        out["periods"][code] = {
            "label": name,
            "boundary": b,
            "start": start,
            "covered": covered,
            "end": D,
            "kospi": kchg,
            "investors": inv,
            "usdkrw": moves["usdkrw"],
            "wti": moves["wti"],
            "lines": lines,
        }

    _windows(out, flows, kdates, D)
    _short(out, series, flows, kdates, D)
    out["interpretation"] = {
        code: _interpret(out, vix, code, D) for code, _, _ in PERIODS
    }
    out["status"] = [
        {
            "key": k,
            "label": out["series"][k]["label"],
            "E": out["series"][k]["E"],
            "collected_at": out["series"][k]["collected_at"],
        }
        for k in ("kospi", "flows", "usdkrw", "wti")
    ]
    _today(out)
    out["ai_text"] = {code: ai_text(out, code) for code, _, _ in PERIODS}
    return out


def _trend(a: dict, b: dict) -> tuple[str, str]:
    """최근 20 · 직전 20 거래일 외국인 순매수 비교(문장 · 짧은 문장). 같으면 '같음' · 0 이면 증감을 말하지 않음."""
    sa, sb = a["sum"], b["sum"]
    for sign, word in ((-1, "매도"), (1, "매수")):
        if sa * sign > 0 and sb * sign > 0:
            x, y = abs(a["avg"]), abs(b["avg"])
            how = "같음" if x == y else ("감소" if x < y else "증가")
            full = (
                f"직전 20거래일{'과' if how == '같음' else '보다'} 일평균 {word} {how}"
            )
            return full, f"일평균 {word} {how} (직전 20거래일 대비)"
    if sa > 0 > sb:
        return "순매도 → 순매수 전환", "순매도 → 순매수 전환"
    if sa < 0 < sb:
        return "순매수 → 순매도 전환", "순매수 → 순매도 전환"
    text = "한쪽 합이 0 이라 증감 · 전환을 말하지 않음"
    return text, text


def _windows(out: dict, flows: dict, kdates: list[str], D: str) -> None:
    if not out["has_flows"]:
        out["windows"] = {"lines": [NO_FLOW]}
        return
    w = {
        k: {
            "r20": window(flows[k], kdates, D, 0, 20),
            "p20": window(flows[k], kdates, D, 20, 20),
            "r60": window(flows[k], kdates, D, 0, 60),
        }
        for k, _ in MAIN_INVESTORS
    }
    lines, trend, short = [], None, None
    a, b = w["foreign"]["r20"], w["foreign"]["p20"]
    if a and b:
        trend, short = _trend(a, b)
        lines.append(
            f"외국인 최근 20거래일 {won(a['sum'])}(일평균 {won(a['avg'])}) · "
            f"직전 20거래일 {won(b['sum'])}(일평균 {won(b['avg'])})"
        )
        lines.append(trend)
    else:
        lines.append("외국인 20거래일 비교 — 자료가 온전하지 않아 표시하지 않음")
    if not w["foreign"]["r60"]:
        lines.append("외국인 60거래일 — 자료가 온전하지 않아 표시하지 않음")
    else:
        r60 = {k: w[k]["r60"] for k in ("foreign", "individual", "institution")}
        lines.append(
            " · ".join(
                f"{lab} {won(r60[k]['sum']) if r60[k] else '자료 부족'}"
                for k, lab in (
                    ("foreign", "외국인 최근 60거래일"),
                    ("individual", "개인"),
                    ("institution", "기관계"),
                )
            )
        )
    out["windows"] = {"lines": lines, "trend": trend, "trend_short": short}


def _coverage_reason(checked: int, total: int) -> Optional[str]:
    if checked >= total:
        return None
    if checked == 0:
        return "비교 자료 부족"
    return f"비교 자료 부족(최근 {total}개 관측 중 {checked}개만 비교)"


def _short(out: dict, series: dict, flows: dict, kdates: list[str], D: str) -> None:
    rows, events = [], []
    checked: list[str] = []
    unchecked: list[dict] = []

    def cover(label: str, reason: Optional[str]) -> None:
        if reason is None:
            checked.append(label)
        else:
            unchecked.append({"label": label, "reason": reason})

    for key, label, unit in PRICE:
        pts = series[key]
        if not pts:
            rows.append({"text": f"{label} 자료 없음", "flags": []})
            cover(label, "자료 없음")
            continue
        cover(label, _coverage_reason(*price_event_coverage(pts)))
        st = short_term(pts)
        parts = [f"{label} {md(st['date'])}"]
        if st["d1"]:
            parts.append(
                f"직전 대비 {signed(st['d1']['diff'], unit)}({pct(st['d1']['pct'])})"
            )
        if st["d5"]:
            parts.append(
                f"5개 관측 {signed(st['d5']['diff'], unit)}({pct(st['d5']['pct'])} · "
                f"{md(st['d5']['from_date'])}부터)"
            )
        flags = []
        e = st["expansion"]
        if e is None:
            flags.append("비교 자료 부족")
        elif e["flag"]:
            base = f"{md(e['base_from'])}~{md(e['base_to'])}"
            flags.append(
                "최근 변화 확대 · "
                + (
                    f"직전 20회({base}) 변화 0, 이번 관측에서 변화 발생"
                    if e["zero_base"]
                    else f"이전 20회({base}) 평균 변화의 {e['ratio']:.1f}배"
                )
            )
        if st["range"]:
            flags.append(f"직전 20개 관측 범위 {st['range']['dir']}")
        if st["date"] < D:
            flags.append(f"늦음 — 최신 {md(st['date'])}(D {md(D)} 보다 이전)")
        rows.append({"text": " · ".join(parts), "flags": flags})
        events += price_events(pts, label, unit)
    for k, label in SHORT_INVESTORS:
        net = flows[k]
        if not net:
            rows.append({"text": f"{label} 수급 자료 없음", "flags": []})
            cover(label, "자료 없음")
            continue
        cover(label, _coverage_reason(*flow_event_coverage(net, kdates)))
        f = flow_short(net, kdates)
        way = "순매도" if f["value"] < 0 else "순매수"
        flags = (
            [f["note"]]
            if f["note"]
            else (
                [
                    f"{way} 규모 확대 · 이전 20거래일({md(f['base_from'])}~"
                    f"{md(f['base_to'])}) 평균 규모의 {f['ratio']:.1f}배"
                ]
                if f["flag"]
                else []
            )
        )
        rows.append(
            {"text": f"{label} {md(f['date'])} {way} {won(f['value'])}", "flags": flags}
        )
        events += flow_events(net, label, kdates)
    out["short_lines"] = rows
    out["events"] = sorted(events, key=lambda e: e["date"], reverse=True)
    why = " · ".join(f"{u['label']} {u['reason']}" for u in unchecked)
    if not unchecked:
        empty = (
            "최근 5개 관측: 표시 기준(이전 20회 평균 변화의 3배 · 직전 20개 범위)에 해당하는 큰 변화 없음"
            " — 안정이라는 뜻은 아님"
        )
    elif checked:
        empty = (
            f"최근 5개 관측: 확인한 자료({' · '.join(checked)})에서는 표시 기준에 해당하는 큰 변화 없음"
            f" · 확인 못 한 자료 — {why}"
        )
    else:
        empty = f"최근 5개 관측: 큰 변화를 확인하지 못함 — {why}"
    out["event_check"] = {
        "checked": checked,
        "unchecked": unchecked,
        "unchecked_text": f"확인 못 한 자료 — {why}" if unchecked else None,
        "empty_text": None if out["events"] else empty,
    }


def _interpret(out: dict, vix: list, code: str, D: str) -> dict:
    """{"rows": [[관측, 가능성, 다른 설명]], "notes": [문장]} — 입력이 없거나 부분이면 '확인 못 한 조합'."""
    p = out["periods"][code]
    kd = p["kospi"]["pct"] if p["kospi"] else None
    f = p["investors"]["foreign"]
    if not out["has_flows"]:
        fs, f_why = None, "외국인 수급 자료 없음"
    elif f["partial"]:
        fs, f_why = None, f"외국인 수급 부분 집계({f['days']}/{f['expected']}일)"
    elif not p["covered"]:
        fs, f_why = None, f"외국인 수급 부분 기간({p['start']}부터)"
    else:
        fs, f_why = f["sum"], None
    fxp = p["usdkrw"]["pct"] if p["usdkrw"] else None
    oilp = p["wti"]["pct"] if p["wti"] else None
    rows: list[list[str]] = []
    notes: list[str] = []
    evaluated = 0
    # 규칙 1 — 코스피 하락 · 외국인 순매도 · 원/달러(설계 §4 표 1 · 2행)
    ruled_out = (kd is not None and kd >= 0) or (fs is not None and fs >= 0)
    missing = [
        why
        for ok, why in (
            (kd is not None, "코스피 기간 변화 계산 불가"),
            (fs is not None, f_why),
            (fxp is not None, "원/달러 기간 변화 계산 불가"),
        )
        if not ok
    ]
    if ruled_out:
        evaluated += 1
    elif missing:
        notes.append(
            f"확인 못 한 조합: 코스피 하락 · 외국인 순매도 · 원/달러 — {' · '.join(missing)}"
        )
    else:
        evaluated += 1
        if fxp > 0:
            rows.append(
                [
                    "코스피 하락 · 외국인 순매도 · 원/달러 상승",
                    "주식 매도와 원화 약세가 함께 나타남",
                    "환율 때문에 팔았는지, 매도가 환율에 영향을 줬는지는 이 자료만으로 구분할 수 없음",
                ]
            )
        elif fxp < 0:
            rows.append(
                [
                    "코스피 하락 · 외국인 순매도 · 원/달러 하락",
                    "주식 수급 압박과 원화 강세가 동시에 관측됨",
                    "원화 강세가 외국인 주식자금 유입을 뜻하지 않음 · 달러 공급 · 다른 자금 이동 가능",
                ]
            )
    # 규칙 2 — 유가 하락 · 글로벌 근거(VIX)(설계 §4 표 3 · 4행)
    if oilp is None:
        notes.append("확인 못 한 조합: 유가 하락 · VIX — WTI 기간 변화 계산 불가")
    elif oilp >= 0:
        evaluated += 1
    else:
        vc = change_over(vix, p["boundary"], D)
        if not vc or vc["pct"] is None:
            notes.append(
                "확인 못 한 조합: 유가 하락 · VIX — VIX 기간 변화 계산 불가(기간을 덮는 저장 값 없음)"
            )
        else:
            evaluated += 1
            if vc["pct"] > 0:
                rows.append(
                    [
                        "유가 하락 · VIX 상승(글로벌 위험 회피)",
                        "수요 둔화 가능성 검토",
                        "공급 확대 · 공급 차질 완화도 유가를 낮출 수 있음 · 원인 확정 불가",
                    ]
                )
            elif vc["pct"] < 0:  # 변화 0 = 표의 어느 조합도 아님(만들지 않음)
                rows.append(
                    [
                        "유가 하락 · VIX 하락(글로벌 시장 견조)",
                        "비용 부담 완화 가능성 검토",
                        "업종별 영향이 다르고 공급 원인은 따로 확인 필요",
                    ]
                )
    if not rows and evaluated:
        notes.append(
            "확인한 조합에는 해당하는 해석 규칙 없음(설명을 만들어 내지 않음)"
            if notes
            else "지금 조합에 해당하는 해석 규칙 없음(설명을 만들어 내지 않음)"
        )
    return {"rows": rows, "notes": notes}


def _today(out: dict) -> None:
    p = out["periods"][DEFAULT_PERIOD]
    k = p["kospi"]
    l1 = (
        f"시장 흐름 6개월({md(p['end'])}까지): 코스피 "
        f"{pct(k['pct']) if k else '자료 없음(기간 시작 전 값 없음)'}"
    )
    if not p["covered"]:
        l1 += f" · 부분 기간({p['start']}부터)"
    if out["has_flows"]:
        f = p["investors"]["foreign"]
        l1 += f" · 외국인 {'누적 순매도' if f['sum'] < 0 else '누적 순매수'} {won(f['sum'])}"
        if f["partial"]:
            l1 += f"(부분 집계 {f['days']}/{f['expected']}일)"
        t = out["windows"].get("trend_short")
        l1 += (
            f" · 최근 20거래일 {t}"
            if t
            else " · 최근 20거래일 비교 불가(자료가 온전하지 않음)"
        )
    else:
        l1 += " · 투자자별 수급 자료 없음"
    ev = out["events"]
    chk = out["event_check"]
    if ev:
        l2 = (
            "최근 큰 변화: "
            + " · ".join(e["text"] for e in ev[:2])
            + (f" 외 {len(ev) - 2}건" if len(ev) > 2 else "")
            + (f" · {chk['unchecked_text']}" if chk["unchecked_text"] else "")
        )
    else:
        l2 = chk["empty_text"]
    out["today_lines"] = [l1, l2]


def ai_text(out: dict, code: str) -> str:
    """AI 복사문 · 판단 근거 미리보기 · AI 세션 전달 공통 글(빈 줄 없음 · 미리보기 상자가 쪼개지지 않게)."""
    p = out["periods"][code]
    L = [
        f"[시장 흐름 — 수급 · 환율 · 유가 · 기간 {p['label']} · {p['start'] or p['boundary']} ~ "
        f"{p['end']}(D = 코스피 · 수급이 함께 확인된 마지막 거래일)]"
    ]
    L += [f"- {x}" for x in p["lines"]]
    L += [f"- {x}" for x in out["windows"]["lines"]]
    L.append("[최근 큰 변화 — 완료된 일별 값 · 자료마다 최신일]")
    for row in out["short_lines"]:
        L.append(
            f"- {row['text']}"
            + (f" · {' · '.join(row['flags'])}" if row["flags"] else "")
        )
    chk = out["event_check"]
    if out["events"]:
        L.append(
            "- 최근 5개 관측에서 생긴 일: "
            + " · ".join(e["text"] for e in out["events"])
        )
        if chk["unchecked_text"]:
            L.append(f"- {chk['unchecked_text']}")
    else:
        L.append(f"- {chk['empty_text']}")
    it = out["interpretation"][code]
    L.append(f"[가능한 해석 — {p['label']} 기준 · 확정이 아님]")
    for obs, cand, other in it["rows"]:
        L.append(f"- 관측: {obs} → 가능성: {cand} / 다른 설명 · 한계: {other}")
    L += [f"- {n}" for n in it["notes"]]
    L.append(
        "[자료 기준일] "
        + " · ".join(
            f"{s['label']} {s['E'] or '없음'}(수집 {kst_stamp(s['collected_at'])})"
            for s in out["status"]
        )
    )
    L.append("[한계] " + " ".join(out["limits"]))
    return "\n".join(L)
