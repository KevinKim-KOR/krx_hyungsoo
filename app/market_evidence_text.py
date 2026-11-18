"""POC6-32 V2 — 공통 시장 근거의 글(PLAN §4-1 · §4-2 · 재설계 판정 V2 §3).

`app/market_evidence.py` 가 만든 지표별 칸(`fields`)만 읽어 글을 만든다(새 계산 없음 · 다시 조회 없음).
- `evidence_items(fields)` = 시장 근거 줄 목록(번호 없음). 일일 복사는 이 줄을 그대로 잇고, 주간 복사는 같은 줄에
  `[근거 n]` 번호를 붙인다 — 두 복사가 같은 값 · 같은 날짜를 쓴다.
- `daily_text(fields)` = 일일 [AI용 시장 정보 복사] 글: 최신 공개 자료 확인 문단(판정 원문) →
  다섯 줄 답 형식(목업 원문) → 시장 근거 줄(KODEX 200 시장 판정 → 코스피 → 수급 → 원/달러 · WTI · VIX →
  가능한 해석 → 오늘 시세 참고 → 최근 큰 변화 → 자료 상태).
- `event_sentence` · `common_row` = 화면 `todayMarketLines.ts` `eventSentence`(+ 받침 조사) ·
  `morningText.ts` `commonClosedRow` 를 옮긴 것. 같은 입력에 같은 결과인지 서버 · 화면 시험이 같은 고정 자료
  (`tests/fixtures/poc6_32_evidence_cases.json`)로 대조한다. 숫자 반올림도 화면과 같게 맞춘다(소수 표기 =
  짧은 표기에서 반 올림 · 배수 = 정확한 값에서 반 올림 · 억원 = 반 올림).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Mapping, Optional

from app.supply_fx_oil_calc import num, pct, signed, won

# 재설계 판정 V2 §3 인용 문단 그대로(일일 · 주간 복사 공통 첫머리).
LATEST_CHECK = (
    "답변 전에 판단에 사용하는 항목의 최신 공개 자료를 확인해 주세요. 공식 출처를 우선하고, 국내 종가·수급과 해외 "
    "지표는 각 자료의 거래일과 공표 시점을 기준으로 확인해 주세요. 확인 결과에는 값·기준일·출처 링크를 적어 주세요. "
    "저장값과 같으면 그 사실을, 더 최신 값이나 같은 날짜의 정정값이 있으면 어느 해석이 달라지는지 적어 주세요. "
    "최신 공개 자료를 확인할 수 없으면 ‘최신 자료 확인 불가’라고 쓰고 제공된 저장 자료의 기준일을 밝혀 설명해 주세요."
)
# 목업(V2 확정) 일일 복사 예시의 답 형식 문단 그대로.
DAILY_ANSWER = (
    "다섯 줄로 답해 주세요. ① 최신 확인 결과와 시장 판정 ② 코스피 방향 ③ 외국인 매도·매수 방향과 속도 "
    "④ 환율·유가·VIX 관측 ⑤ 다음 확인 한 가지. 줄마다 근거와 실제 날짜를 쓰고, 비교 기간이 다르면 따로 써 주세요. "
    "못 읽은 자료는 '확인 불가'. 해석에 추가 자료가 필요하면 그 항목을 마지막 줄에 적어 주세요."
)
NA = "확인 불가"
KST = timezone(timedelta(hours=9))
# 일별 종가끼리 비교한 사건(종가 기준 표기 대상)
PRICE_KEYS = ("kospi", "usdkrw", "wti")
KOSPI_PERIODS = (("1M", "1개월"), ("3M", "3개월"), ("6M", "6개월"))

# ── 화면 형식 이식(todayMarketLines.ts) ─────────────────────────────────────────
_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
# 숫자 끝 글자의 받침(영 · 일 · 이 · 삼 · 사 · 오 · 육 · 칠 · 팔 · 구) — 영문 끝 글자는 받침 없음.
_DIGIT_HAS_FINAL = dict(zip("0123456789", (1, 1, 0, 1, 0, 0, 1, 1, 1, 0)))
LABEL = {
    "kospi": "코스피",
    "usdkrw": "원/달러",
    "wti": "WTI",
    "foreign": "외국인",
    "institution": "기관계",
}


def is_real_date(s: object) -> bool:
    """달력 날짜인 'YYYY-MM-DD' 만(화면 isRealDate 와 같이 0 ~ 99년은 날짜로 보지 않음)."""
    m = _DATE.fullmatch(s) if isinstance(s, str) else None
    if not m:
        return False
    y, mo, d = (int(x) for x in m.groups())
    if y < 100:
        return False
    try:
        date(y, mo, d)
    except ValueError:
        return False
    return True


def md(d: Optional[str]) -> str:
    """'M/D' — 달력 날짜가 아니면 받은 글자 그대로 · 비면 '확인 불가'."""
    if not d:
        return NA
    return f"{int(d[5:7])}/{int(d[8:10])}" if is_real_date(d) else d


def num2(v: float) -> str:
    """화면 toLocaleString(소수 둘째 자리) — 짧은 표기에서 반 올림 · 천 단위 쉼표."""
    q = Decimal(repr(float(v))).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return f"{q:,.2f}"


def with_unit(v: float, unit: Optional[str]) -> str:
    return num2(v) if not unit or unit == "pt" else f"{num2(v)}{unit}"


def fixed1(v: float) -> str:
    """화면 toFixed(1) — 정확한 값에서 반 올림(쉼표 없음)."""
    return format(Decimal(float(v)).quantize(Decimal("0.1"), ROUND_HALF_UP), "f")


def won_abs(v: float) -> str:
    """화면 wonAbs — 정수 원 → 크기만(억원 · 조원)."""
    a = abs(v) / 100_000_000
    if a >= 10000:
        q = Decimal(repr(a / 10000)).quantize(Decimal("0.1"), ROUND_HALF_UP)
        return f"{q:,.1f}조원"
    return f"{int(Decimal(a).quantize(Decimal(1), ROUND_HALF_UP)):,}억원"


def _has_final(word: str) -> bool:
    ch = word.strip()[-1:]
    if not ch:
        return False
    if ch in _DIGIT_HAS_FINAL:
        return bool(_DIGIT_HAS_FINAL[ch])
    code = ord(ch)
    return 0xAC00 <= code <= 0xD7A3 and (code - 0xAC00) % 28 != 0


def josa(word: str, with_final: str, without_final: str) -> str:
    return f"{word}{with_final if _has_final(word) else without_final}"


def event_sentence(e: Mapping[str, Any]) -> str:
    """사건 한 줄(화면 eventSentence) — 구조 칸이 없는 옛 응답이면 서버 원문 + '괄호 안 = 비교 기준값'."""
    legacy = f"{e.get('text')} (괄호 안 = 비교 기준값)"
    key, value = e.get("key"), e.get("value")
    if key is None or value is None:
        return legacy
    label = LABEL.get(key, str(key))
    when = md(e.get("date"))
    unit = e.get("unit")
    ratio = e.get("ratio")
    if key in ("foreign", "institution"):
        way = "순매도" if value < 0 else "순매수"
        if ratio is not None:
            return f"{when} {label} {way} {won_abs(value)} · 직전 20거래일 평균 규모의 {fixed1(ratio)}배"
        return f"{when} {label} 직전 20거래일 순매수 0, 이번 {way} {won_abs(value)}"
    kind = e.get("kind")
    if kind == "range" and e.get("bound") is not None and e.get("bound_date"):
        subject = (
            f"코스피 종가 {num2(value)}"
            if key == "kospi"
            else f"{label} {with_unit(value, unit)}"
        )
        low = e.get("dir") == "아래"
        bound = josa(with_unit(e["bound"], unit), "을", "를")
        return (
            f"{when} {josa(subject, '이', '가')} {md(e['bound_date'])} {'저점' if low else '고점'} "
            f"{bound} {'밑돌았습니다' if low else '넘었습니다'}"
        )
    delta = e.get("delta")
    if kind == "expansion" and delta is not None:
        move = (
            f"{with_unit(abs(delta), unit)} {'하락' if delta < 0 else '상승'}했습니다"
        )
        if e.get("zero_base"):
            return f"{when} {josa(label, '이', '가')} 직전 20회 변화가 없다가 {move}"
        tail = f" · 평소 변화의 {fixed1(ratio)}배" if ratio is not None else ""
        return f"{when} {josa(label, '이', '가')} {move}{tail}"
    return legacy


def common_row(mb: Optional[Mapping[str, Any]]) -> Optional[dict]:
    """아침 · 당일 판정이 같은 KODEX 200 마감 뒤 저장 행을 쓰면 그 행(화면 commonClosedRow) · 아니면 None.

    `mb` = 아침 기준 응답(성공 · 새로 읽은 것만 넘긴다 — 실패 · 이전 응답은 None)."""
    if not mb or mb.get("status") != "ok":
        return None
    mr, tr = mb.get("morning_regime"), mb.get("today_regime")
    item = next((i for i in mb.get("items") or [] if i.get("key") == "kodex200"), None)
    k = (item or {}).get("basis_row")
    t = (tr or {}).get("basis_row")
    if (
        not mr
        or mr.get("status") != "ok"
        or not tr
        or tr.get("status") != "ok"
        or not k
        or not t
        or not mr.get("basis_date")
    ):
        return None
    same = (
        t.get("date") == mr["basis_date"]
        and k.get("date") == mr["basis_date"]
        and t.get("state") == "after_close"
        and k.get("state") == "after_close"
        and abs(t["close"] - k["close"]) < 0.005
    )
    return dict(t) if same else None


# ── 시장 근거 줄 ─────────────────────────────────────────────────────────────
def _p(v: Optional[float]) -> str:
    return NA if v is None else pct(v)


def _hm(iso: Optional[str]) -> str:
    """KST 로 적힌 시각(저장 시각 · `fetched_at_kst`)의 'HH:MM'."""
    return iso[11:16] if isinstance(iso, str) and len(iso) >= 16 else NA


def _kst_hm(iso: Optional[str]) -> str:
    """시간대가 붙은 시각(원천 시각) → KST 'HH:MM' · 읽을 수 없으면 '확인 불가'."""
    try:
        t = datetime.fromisoformat(str(iso).strip().replace("Z", "+00:00"))
    except ValueError:
        return NA
    return t.astimezone(KST).strftime("%H:%M") if t.tzinfo else NA


STATE_WORD = {"intraday": "장중 저장", "after_close": "마감 뒤 저장"}


def stored_text(
    price_date: Optional[str], state: Optional[str], saved: Optional[str]
) -> str:
    """판정 가격 행의 저장 시점(화면 storedRowText 와 같은 구분)."""
    if not saved:
        return "(저장 시점 확인 필요)"
    when = _hm(saved) if saved[:10] == price_date else f"{md(saved[:10])} {_hm(saved)}"
    if state in STATE_WORD:
        return f"({when} {STATE_WORD[state]})"
    return f"({when} 저장 · 장중인지 마감 뒤인지 확인 필요)"


def _ma(name: str, m: Mapping[str, Any]) -> str:
    pos = {"above": "위", "below": "아래"}.get(m.get("position") or "")
    if pos is None:
        return f"{name} {NA}"
    return f"{name} {pos}(거리 {_p(m.get('distance_pct'))})"


def _ret(name: str, r: Mapping[str, Any]) -> str:
    if r.get("value") is None:
        return f"{name} {NA}"
    return f"{name} {pct(r['value'])}({md(r.get('start'))} → {md(r.get('end'))})"


def regime_text(r: Optional[Mapping[str, Any]], tag: str, same: bool) -> str:
    head = f"[시장 판정{tag}]"
    if not r or r.get("status") != "ok":
        return f"{head} 미확인 — {(r or {}).get('reason') or '근거 확인 불가'}"
    n = r.get("streak_days")
    streak = (
        f" · {n}거래일째{' 이상' if r.get('at_least') else ''}"
        if n is not None
        else " · 지속일 확인 불가"
    )
    price = r.get("price_date")
    body = (
        f"{head} KODEX 200 {r.get('label') or NA}{streak} · 판정 가격 {md(price)}"
        f"{stored_text(price, r.get('price_state'), r.get('saved_at_kst'))}"
        + (" · 아침 · 당일 같은 근거" if same else "")
    )
    basis = " · ".join(
        [
            _ret("20거래일", r["r20"]),
            _ret("60거래일", r["r60"]),
            _ma("20일선", r["ma20"]),
            _ma("60일선", r["ma60"]),
        ]
    )
    return f"{body} · {basis}"


def _regime_items(rg: Mapping[str, Any]) -> list[tuple[str, str]]:
    if (
        rg.get("status") == "unavailable"
        and not rg.get("today")
        and not rg.get("morning")
    ):
        return [("regime", f"[시장 판정] {NA} — {rg.get('reason') or '근거 없음'}")]
    if rg.get("same_basis"):
        return [("regime", regime_text(rg.get("today"), "", True))]
    return [
        ("regime_morning", regime_text(rg.get("morning"), " · 아침", False)),
        ("regime_today", regime_text(rg.get("today"), " · 당일", False)),
    ]


def _src_note(which: str, label: Optional[str], official: Optional[bool]) -> str:
    if official is True:
        return ""
    if official is None:
        return f" · {which} 종가 출처 {NA}"
    return f" · {which} 종가 출처 {label}(KRX 공식 아님)"


def _kospi_items(k: Mapping[str, Any]) -> list[tuple[str, str]]:
    if k.get("status") == "unavailable" and k.get("value") is None:
        why = k.get("reason") or "코스피 저장 자료 없음"
        return [("kospi_close", f"[코스피 공식 종가] {NA} — {why}")] + [
            (f"kospi_{c.lower()}", f"[코스피 {name}] {NA}") for c, name in KOSPI_PERIODS
        ]
    official = k.get("official")
    head = "[코스피 공식 종가]" if official is True else "[코스피 종가]"
    line = f"{head} {num2(k['value'])} · {md(k.get('date'))}"
    prev = k.get("prev")
    if prev:
        line += f" · {md(prev['from_date'])} 대비 {signed(prev['diff'], 'pt')}({_p(prev.get('pct'))})"
    if official is not True:
        line += (
            f" · 출처 {k.get('source')}(KRX 공식 아님)"
            if official is False
            else f" · 출처 {NA}"
        )
    if k.get("expected_missing"):
        line += f" · 기대 거래일 {md(k.get('expected_date'))} 종가 {NA}"
    out = [("kospi_close", line)]
    for code, name in KOSPI_PERIODS:
        p = (k.get("periods") or {}).get(code) or {}
        if p.get("status") != "ok":
            out.append(
                (
                    f"kospi_{code.lower()}",
                    f"[코스피 {name}] {NA} — {p.get('reason') or '기간 값 없음'}",
                )
            )
            continue
        out.append(
            (
                f"kospi_{code.lower()}",
                f"[코스피 {name}] {_p(p.get('pct'))}({md(p['from_date'])} {num2(p['from'])} → "
                f"{md(p['to_date'])} {num2(p['to'])}"
                f"{_src_note('시작', p.get('start_source'), p.get('start_official'))}"
                f"{_src_note('끝', p.get('end_source'), p.get('end_official'))})",
            )
        )
    return out


def _amount(v: float) -> str:
    return won(v).lstrip("+-")


def _way(v: float) -> str:
    return "순매도" if v < 0 else "순매수"


def _flow_items(f: Mapping[str, Any]) -> list[tuple[str, str]]:
    six, w20, r60 = f.get("six") or {}, f.get("w20") or {}, f.get("r60") or {}
    if six.get("status") == "ok":
        span = f"{md(six['start'])} ~ {md(six['end'])}"
        notes = [span, f"{six['days']}/{six['expected']}일"]
        if six.get("partial"):
            notes.append("부분 집계")
        if not six.get("covered", True):
            notes.append(f"부분 기간({md(six['start'])}부터)")
        total = f"{_way(six['sum'])} {_amount(six['sum'])}"
        a = f"[외국인 6개월] 누적 {total}({' · '.join(notes)})"
    else:
        a = f"[외국인 6개월] {NA} — {six.get('reason') or '자료 없음'}"
    if w20.get("status") == "ok":
        b = (
            f"[외국인 20거래일] 직전 {_window(w20['previous'])} → 최근 {_window(w20['recent'])}"
            + (f" · {w20['trend']}" if w20.get("trend") else "")
        )
    else:
        b = f"[외국인 20거래일] {NA} — {w20.get('reason') or '자료 없음'}"
    return [("foreign_6m", a), ("foreign_20", b), ("flows_60", _r60_text(r60))]


def _window(w: Mapping[str, Any]) -> str:
    """20거래일 창 {sum, avg, from, to} → '9/15 ~ 10/16 순매도 31.9조원(일평균 1.6조원)'."""
    span = f"{md(w['from'])} ~ {md(w['to'])}"
    return f"{span} {_way(w['sum'])} {_amount(w['sum'])}(일평균 {_amount(w['avg'])})"


def _r60_text(r60: Mapping[str, Any]) -> str:
    if r60.get("status") != "ok":
        return f"[60거래일 수급] {NA} — {r60.get('reason') or '자료 없음'}"
    parts = []
    for it in r60["investors"]:
        if not it.get("days"):
            parts.append(f"{it['label']} 자료 없음")
            continue
        extra = (
            f"(부분 집계 {it['days']}/{r60['expected']}일)" if it.get("partial") else ""
        )
        parts.append(f"{it['label']} {won(it['value'])}{extra}")
    nation = r60.get("nation") or {}
    if not nation.get("days"):
        nat = "이 기간 자료 없음"
    elif nation.get("value") == 0:
        nat = "이 기간 0"
    else:
        nat = f"이 기간 합 {won(nation['value'])}"
    return (
        f"[60거래일 수급] {md(r60['start'])} ~ {md(r60['end'])}"
        f"(코스피 저장 거래일 {r60['expected']}일 · 순매수 합) "
        + " · ".join(parts)
        + f"(집계 구분: {r60.get('scope')} · 국가 · 지자체는 따로 적지 않음({nat}))"
    )


def _macro_text(m: Mapping[str, Any]) -> str:
    head = f"[{m.get('label')}]"
    if m.get("status") == "unavailable":
        return f"{head} {NA} — {m.get('reason') or '자료 없음'}"
    unit = m.get("unit") or ""
    parts = [f"{head} {num(m['value'], unit)} · {md(m['date'])}({m.get('date_basis')})"]
    prev, d5, six = m.get("prev"), m.get("d5"), m.get("six")
    if prev:
        parts.append(
            f"직전 관측 {md(prev['from_date'])} 대비 {signed(prev['diff'], unit)}"
            f"({_p(prev.get('pct'))})"
        )
    if d5:
        parts.append(
            f"5개 관측 {signed(d5['diff'], unit)}({_p(d5.get('pct'))} · "
            f"{md(d5['from_date'])}부터)"
        )
    parts.append(
        f"6개월 {num(six['from'], unit)} → {num(six['to'], unit)}"
        f"({_p(six.get('pct'))} · {md(six['from_date'])} → {md(six['to_date'])})"
        if six
        else f"6개월 {NA}(기간을 덮는 저장 값 없음)"
    )
    return " · ".join(parts)


def _vix_text(v: Mapping[str, Any]) -> str:
    if v.get("status") == "unavailable":
        return f"[VIX] {NA} — {v.get('reason') or '자료 없음'}"
    parts = [f"[VIX] {num2(v['value'])} · {md(v['date'])}(미국 날짜)"]
    prev, d5, six = v.get("prev"), v.get("d5"), v.get("six")
    if prev:
        parts.append(
            f"직전 관측 {md(prev['date'])} {num2(prev['value'])} 대비 {_p(prev.get('pct'))}"
        )
    if d5:
        parts.append(
            f"5개 관측 {_p(d5.get('pct'))}({md(d5['date'])} {num2(d5['value'])}부터)"
        )
    parts.append(
        f"6개월 {num2(six['from'])} → {num2(six['to'])}({_p(six.get('pct'))} · "
        f"{md(six['from_date'])} → {md(six['to_date'])} 미국 날짜)"
        if six
        else f"6개월 {NA}({v.get('six_reason') or '기간을 덮는 저장 값 없음'})"
    )
    return " · ".join(parts)


def _interp_text(it: Mapping[str, Any]) -> str:
    if it.get("status") == "unavailable":
        return (
            f"[가능한 해석(6개월 · 확정 아님)] {NA} — {it.get('reason') or '자료 없음'}"
        )
    rows = [f"{o} → {c}(다른 설명: {x})" for o, c, x in it.get("rows") or []]
    body = " · ".join(
        x for x in (" / ".join(rows), " · ".join(it.get("notes") or [])) if x
    )
    return f"[가능한 해석(6개월 · {md(it.get('start'))} ~ {md(it.get('end'))} · 확정 아님)] {body or NA}"


def _quick_text(q: Mapping[str, Any]) -> Optional[str]:
    shown = q.get("shown") or []
    if not shown:
        return None
    parts = []
    for s in shown:
        v = f"{s['value']:,.0f}원" if s.get("kind") == "stock" else num2(s["value"])
        parts.append(
            f"{s['name']} {v}({s['status_text']} · 원천 시각 {_kst_hm(s.get('source_time'))})"
        )
    return (
        f"[오늘 시세 참고] {md(q.get('review_date'))} 네이버 시세(공식 종가 · 수급 통계 아님) · "
        + " · ".join(parts)
    )


def _event_items(ev: Mapping[str, Any]) -> list[tuple[str, str]]:
    if ev.get("status") == "unavailable":
        return [("events", f"[최근 큰 변화] {NA} — {ev.get('reason') or '자료 없음'}")]
    items = ev.get("items") or []
    out = []
    for i, e in enumerate(items, 1):
        s = event_sentence(e)
        structured = e.get("key") is not None and e.get("value") is not None
        if structured and e.get("key") in PRICE_KEYS:
            s += "(종가 기준)"
        out.append((f"event_{i}", f"[최근 큰 변화 {i}] {s}"))
    if not items:
        # '없음'은 큰 변화 확인을 실제로 했을 때(확인 결과 글이 있을 때)만 — 아니면 확인 불가(BE-1)
        empty = ev.get("empty_text")
        out.append(
            ("events", f"[최근 큰 변화] {empty or f'{NA} — 큰 변화를 확인하지 않음'}")
        )
    if ev.get("unchecked_text"):
        out.append(("event_scope", f"[최근 큰 변화 확인 범위] {ev['unchecked_text']}"))
    return out


def _fresh_part(row: Mapping[str, Any]) -> Optional[tuple[str, bool]]:
    """(자료 상태 한 조각, 늦음 여부) — 최신이면 None."""
    st, label = row.get("state"), row.get("label")
    if st == "fresh":
        return None
    if st == "late":
        n = row.get("behind")
        lag = f"{n}거래일 늦음" if n else "늦음"
        last, exp = md(row.get("last_date")), md(row.get("expected"))
        return f"{label} {last}까지(기대 {exp} · {lag})", True
    return f"{label} 기준 확인 필요({row.get('reason') or '판정 자료 없음'})", False


def _status(fields: Mapping[str, Any]) -> tuple[list[str], list[str], list[str]]:
    """(읽기 실패 + 판정 행 조각, 그중 늦음 조각, 오늘 시세 조각)."""
    parts, late = list(fields.get("read_errors") or []), []
    for row in (fields.get("data_status") or {}).get("rows") or []:
        got = _fresh_part(row)
        if got:
            parts.append(got[0])
            if got[1]:
                late.append(got[0])
    q, quick = fields.get("quick") or {}, []
    if not q.get("shown"):
        bad = q.get("status") == "invalid"
        quick.append("오늘 시세 미확보" + ("(저장 파일을 읽지 못함)" if bad else ""))
    elif q.get("missing"):
        quick.append(f"오늘 시세 미확보({' · '.join(q['missing'])})")
    return parts, late, quick


def status_parts(fields: Mapping[str, Any]) -> list[str]:
    """[자료 상태] 조각 = 읽기 실패 + 기대일보다 늦거나 기준 확인이 필요한 자료 + 오늘 시세 미확보."""
    parts, _late, quick = _status(fields)
    return parts + quick


def status_text(fields: Mapping[str, Any]) -> str:
    """'지연 원인 확인 전'은 늦은 자료 조각 바로 뒤(오늘 시세 미확보와 섞이지 않게)."""
    parts, late, quick = _status(fields)
    today = (fields.get("data_status") or {}).get("today")
    head = f"[자료 상태] {md(today)} 확인 · "
    if not parts and not quick:
        return head + "확인한 자료 모두 기대 기준일 기준 최신"
    tail = ["지연 원인 확인 전"] if late else []
    return head + " · ".join(parts + tail + quick)


def evidence_items(fields: Mapping[str, Any]) -> list[dict[str, str]]:
    """시장 근거 줄(번호 없음 · 일일 글과 같은 줄 · 주간 복사가 [근거 n] 을 붙임)."""
    out: list[tuple[str, str]] = []
    out += _regime_items(fields["regime"])
    out += _kospi_items(fields["kospi"])
    out += _flow_items(fields["flows"])
    out += [
        ("usdkrw", _macro_text(fields["usdkrw"])),
        ("wti", _macro_text(fields["wti"])),
        ("vix", _vix_text(fields["vix"])),
        ("interpretation", _interp_text(fields["interpretation"])),
    ]
    quick = _quick_text(fields["quick"])
    if quick:
        out.append(("quick", quick))
    out += _event_items(fields["events"])
    out.append(("data_status", status_text(fields)))
    return [{"key": k, "text": t} for k, t in out]


def daily_text(fields: Mapping[str, Any]) -> str:
    """일일 [AI용 시장 정보 복사] 글 — 첫머리 두 문단 + 시장 근거 줄(evidence_items 와 같은 줄)."""
    lines = [i["text"] for i in evidence_items(fields)]
    return f"{LATEST_CHECK}\n\n{DAILY_ANSWER}\n\n" + "\n".join(lines) + "\n"
