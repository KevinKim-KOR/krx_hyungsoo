"""POC6-01 — 시장 흐름 순수 계산(입력 = 날짜순 일별 관측 · 외부 · DB 없음).

설계 §3 · §3-1 · PLAN 판정 §4-2 그대로:
- 기간 경계 = 끝일 D 의 1 · 3 · 6개월 전 날짜(그 날짜 '초과'가 기간 안) · 연초 이후 = 그해 1/1 부터.
- 가격 변화 = 경계 이전 마지막 관측 → D 이하 마지막 관측(실제 두 날짜를 함께 돌려준다 · 보간 없음).
- 누적 순매수 = 기준점 0 = 기간 시작 직전 · 첫 거래일 포함 · 기간 안 모든 날의 합 · 빠진 날은 0 으로 채우지
  않고 '부분 집계(확보 n / 있어야 할 m일)'.
- 20 / 직전 20 / 60 거래일 = D 까지의 거래일 달력(코스피 저장일) · 그 창의 모든 날이 있을 때만.
- 단기(자료마다 최신 E): 직전 대비 · 5개 관측 변화(값 6개) · 변화 확대 = |Δ| ÷ (그 이전 20개 변화 절댓값 평균)
  ≥ 3(원본 22개 · 현재 변화는 기준에 넣지 않음) · 평균 0 이면 배수 없음 · 직전 20개 값 범위 위 / 아래
  (같은 값은 이탈 아님). 수급 단기 = |그날 순매수| ÷ (이전 20거래일 |순매수| 평균) ≥ 3.
- 3배 · 20개 · 5개는 이 화면의 관측 표시 기준이다(검증된 위험 · 수익 임계치가 아님).
- 최근 5개 관측 사건은 '비교를 마쳤는데 해당 없음'과 '기준 자료가 모자라 비교 못 함'을 구분한다
  (`price_event_coverage` · `flow_event_coverage` — 검증자 r1 F2 · 설계 §3-1).
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from statistics import mean
from typing import Optional

Point = tuple[str, float]
EXPANSION_RATIO = 3.0
BASE_N = 20
STEP_N = 5
RECENT_EVENTS = 5
PERIODS: tuple[tuple[str, str, Optional[int]], ...] = (
    ("1M", "1개월", 1),
    ("3M", "3개월", 3),
    ("6M", "6개월", 6),
    ("YTD", "연초 이후", None),
)
DEFAULT_PERIOD = "6M"
WON_PER_EOK = 100_000_000


# ── 숫자 표시(서버가 문장을 만든다 · 화면 · 복사문 · 미리보기 공통) ─────────────────────
def won(v: float) -> str:
    """정수 원 → '−21.3조원' · '−1,550억원'(부호 늘 · 0 은 부호 없음 · 억원 반올림 원천)."""
    e = v / WON_PER_EOK
    if round(e) == 0 and abs(e) < 0.5:
        return "0억원"
    sign = "+" if e > 0 else "-"
    a = abs(e)
    if a >= 10000:
        return f"{sign}{a / 10000:,.1f}조원"
    return f"{sign}{a:,.0f}억원"


UNIT_TEXT = {"pt": "pt", "원": "원", "달러": "달러"}


def num(v: float, unit: str) -> str:
    return f"{v:,.2f}" if unit == "pt" else f"{v:,.2f}{unit}"


def signed(v: float, unit: str) -> str:
    s = "+" if v > 0 else ("-" if v < 0 else "")
    return f"{s}{abs(v):,.2f}{unit}"


def pct(v: Optional[float]) -> str:
    if v is None:
        return "—"
    s = "+" if v > 0 else ("-" if v < 0 else "")
    return f"{s}{abs(v):.2f}%"


def md(d: str) -> str:
    return f"{int(d[5:7])}/{int(d[8:10])}"


# ── 기간 ────────────────────────────────────────────────────────────────────
def period_boundary(code: str, end: str) -> str:
    """기간 시작 경계(이 날짜 '초과'가 기간 안)."""
    e = date.fromisoformat(end)
    months = dict((c, m) for c, _, m in PERIODS)[code]
    if months is None:
        return (date(e.year, 1, 1) - timedelta(days=1)).isoformat()
    y, mo = e.year, e.month - months
    while mo <= 0:
        mo += 12
        y -= 1
    return date(y, mo, min(e.day, calendar.monthrange(y, mo)[1])).isoformat()


def change_over(points: list[Point], boundary: str, end: str) -> Optional[dict]:
    before = [p for p in points if p[0] <= boundary]
    upto = [p for p in points if p[0] <= end]
    if not before or not upto or upto[-1][0] <= boundary:
        return None
    a, b = before[-1], upto[-1]
    rate = (b[1] / a[1] - 1) * 100 if a[1] > 0 else None
    return {
        "from_date": a[0],
        "from": a[1],
        "to_date": b[0],
        "to": b[1],
        "diff": b[1] - a[1],
        "pct": rate,
    }


def period_sum(
    points: list[Point], expected: list[str], boundary: str, end: str
) -> dict:
    """기간 합(기준점 0 = 시작 직전 · 첫 거래일 포함). 있어야 할 날 = `expected`(코스피 거래일)."""
    rows = [(d, v) for d, v in points if boundary < d <= end]
    want = [d for d in expected if boundary < d <= end]
    return {
        "sum": sum(v for _, v in rows),
        "days": len(rows),
        "expected": len(want),
        "partial": len(rows) < len(want),
    }


def window(
    points: list[Point], expected: list[str], end: str, skip: int, n: int
) -> Optional[dict]:
    """D 까지 거래일 달력에서 뒤로 `skip` 일 건너뛴 n 일 창(모든 날이 있을 때만)."""
    cal = [d for d in expected if d <= end]
    stop = len(cal) - skip
    days = cal[stop - n : stop] if stop - n >= 0 else []  # noqa: E203
    rows = dict(points)
    if len(days) < n or any(d not in rows for d in days):
        return None
    s = sum(rows[d] for d in days)
    return {"sum": s, "avg": s / n, "from": days[0], "to": days[-1]}


# ── 단기(설계 §3-1) ─────────────────────────────────────────────────────────────
def short_term(points: list[Point], at: Optional[int] = None) -> dict:
    """관측 위치 `at`(기본 최신 E)의 직전 대비 · 5개 관측 · 변화 확대 · 범위 이탈."""
    i = len(points) - 1 if at is None else at
    out: dict = {
        "date": points[i][0],
        "value": points[i][1],
        "d1": None,
        "d5": None,
        "expansion": None,
        "range": None,
    }
    if i >= 1:
        prev = points[i - 1][1]
        d = points[i][1] - prev
        out["d1"] = {
            "from_date": points[i - 1][0],
            "diff": d,
            "pct": d / prev * 100 if prev > 0 else None,
        }
    if i >= STEP_N:
        p5 = points[i - STEP_N][1]
        d = points[i][1] - p5
        out["d5"] = {
            "from_date": points[i - STEP_N][0],
            "diff": d,
            "pct": d / p5 * 100 if p5 > 0 else None,
        }
    if i >= BASE_N + 1:
        delta = points[i][1] - points[i - 1][1]
        m = mean(abs(points[k][1] - points[k - 1][1]) for k in range(i - BASE_N, i))
        if m > 0:
            r = abs(delta) / m
            out["expansion"] = {
                "ratio": r,
                "flag": r >= EXPANSION_RATIO,
                "base_mean": m,
                "delta": delta,
                "zero_base": False,
                "base_from": points[i - BASE_N - 1][0],
                "base_to": points[i - 1][0],
            }
        else:
            out["expansion"] = {
                "ratio": None,
                "flag": delta != 0,
                "base_mean": 0.0,
                "delta": delta,
                "zero_base": True,
                "base_from": points[i - BASE_N - 1][0],
                "base_to": points[i - 1][0],
            }
    if i >= BASE_N:
        win = points[i - BASE_N : i]  # noqa: E203
        hi = max(win, key=lambda p: p[1])
        lo = min(win, key=lambda p: p[1])
        if points[i][1] > hi[1]:
            out["range"] = {"dir": "위", "bound": hi[1], "bound_date": hi[0]}
        elif points[i][1] < lo[1]:
            out["range"] = {"dir": "아래", "bound": lo[1], "bound_date": lo[0]}
    return out


def flow_short(net: list[Point], expected: list[str], at: Optional[int] = None) -> dict:
    """그날 순매수 절댓값 ÷ 직전 20 코스피 거래일(`expected` 달력) 절댓값 평균.

    직전 20 거래일 중 하루라도 수급이 없으면 '비교 자료 부족'(빠진 날을 건너뛰어 창을 만들지 않음 · 설계 §3-1).
    """
    i = len(net) - 1 if at is None else at
    out: dict = {
        "date": net[i][0],
        "value": net[i][1],
        "ratio": None,
        "flag": False,
        "note": None,
    }
    rows = dict(net)
    base = [d for d in expected if d < net[i][0]][-BASE_N:]
    if len(base) < BASE_N or any(d not in rows for d in base):
        out["note"] = "비교 자료 부족"
        return out
    m = mean(abs(rows[d]) for d in base)
    out["base_mean_abs"] = m
    out["base_from"], out["base_to"] = base[0], base[-1]
    if m == 0:
        out["note"] = "직전 20거래일 순매수 0"
        out["flag"] = net[i][1] != 0
        return out
    out["ratio"] = abs(net[i][1]) / m
    out["flag"] = out["ratio"] >= EXPANSION_RATIO
    return out


def price_events(points: list[Point], label: str, unit: str) -> list[dict]:
    """최근 5개 관측에서 생긴 변화 확대 · 범위 이탈(관측마다 그 시점의 기준 창으로)."""
    ev: list[dict] = []
    for at in range(max(0, len(points) - RECENT_EVENTS), len(points)):
        st = short_term(points, at)
        e = st["expansion"]
        if e and e["flag"]:
            text = (
                f"{md(st['date'])} {label} 직전 20회 변화 0, 이번 관측에서 변화 발생({signed(e['delta'], unit)})"
                if e["zero_base"]
                else f"{md(st['date'])} {label} 변화 확대({signed(e['delta'], unit)} · "
                f"이전 20회 평균 변화의 {e['ratio']:.1f}배)"
            )
            ev.append(
                {"date": st["date"], "series": label, "kind": "expansion", "text": text}
            )
        r = st["range"]
        if r:
            edge = "넘음" if r["dir"] == "위" else "밑"
            ev.append(
                {
                    "date": st["date"],
                    "series": label,
                    "kind": "range",
                    "text": f"{md(st['date'])} {label} 직전 20개 관측 범위 {r['dir']}"
                    f"({num(r['bound'], unit)} · {md(r['bound_date'])} {edge})",
                }
            )
    return ev


def flow_events(net: list[Point], label: str, expected: list[str]) -> list[dict]:
    """최근 5개 관측의 수급 규모 확대 · 직전 20거래일 순매수 0 뒤 발생(배수 없음 · 사실만)."""
    ev: list[dict] = []
    for at in range(max(0, len(net) - RECENT_EVENTS), len(net)):
        f = flow_short(net, expected, at)
        if not f["flag"]:
            continue
        way = "순매도" if f["value"] < 0 else "순매수"
        text = (
            f"{md(f['date'])} {label} {way} 규모 확대({won(f['value'])} · "
            f"이전 20거래일 평균 규모의 {f['ratio']:.1f}배)"
            if f["ratio"] is not None
            else f"{md(f['date'])} {label} 직전 20거래일 순매수 0, 이번 {way} {won(f['value'])}"
        )
        ev.append({"date": f["date"], "series": label, "kind": "flow", "text": text})
    return ev


def price_event_coverage(points: list[Point]) -> tuple[int, int]:
    """(최근 5개 관측 중 변화 확대 · 범위 이탈을 모두 비교할 수 있는 관측 수, 5). 원본 22개 이전은 비교 못 함."""
    n = len(points)
    return (
        sum(1 for at in range(n - RECENT_EVENTS, n) if at >= BASE_N + 1),
        RECENT_EVENTS,
    )


def flow_event_coverage(net: list[Point], expected: list[str]) -> tuple[int, int]:
    """(최근 5개 관측 중 직전 20 코스피 거래일 수급이 모두 있어 비교한 관측 수, 5)."""
    n = len(net)
    return (
        sum(
            1
            for at in range(n - RECENT_EVENTS, n)
            if at >= 0 and flow_short(net, expected, at)["note"] != "비교 자료 부족"
        ),
        RECENT_EVENTS,
    )
