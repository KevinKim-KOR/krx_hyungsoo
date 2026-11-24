"""독립 재계산 ① 주 기록 · 자리 · 묶음 · 주 평가(PLAN §2-3 · 판정 §3 · 검증자 r1 F1).

실행 코드의 행렬(Panel · `population` · `study`) 대신 봉인 reader 계열(`krx_sealed_reader` CodeSeries)과 원시 행
(`entry_timing.data.read_raw`)으로 실행 산출물과 **같은 모양**의 주 기록 · 주별 평가를 처음부터 만든다.
요약 · 판정 · 손 계산 주는 `recompute.py`, 대조 · 검산 기록 · 화면 표시 확인은 `verify.py`(KS-10 으로 나눔).
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from app import krx_sealed_reader as K
from app.candidate_compare.protocol import (
    BENCH,
    HOLD_DAYS,
    LOOKBACK_1M,
    N_INTERVALS,
    N_PICK,
    UP_EPS,
    CheckRequired,
    Config,
)
from app.entry_timing import data as DA

WORDS = ("인버스", "레버리지", "2배", "합성", "선물")
ORDER_KEEP = 10
SEAL_KEYS = ("file_sha256", "content_sha256", "member_dates", "first_date", "last_date")


def _excluded(name: Optional[str]) -> bool:
    if not name:
        return False
    return any(w in name for w in WORDS) or "2X" in name.upper()


def _week(d: str) -> tuple[int, int]:
    y, w, _ = dt.date.fromisoformat(d).isocalendar()
    return (y, w)


class Src:
    """reader 계열 + 원시 시가 · 고가 · 저가 · 거래량(봉인 확인 전후 같음)."""

    def __init__(self, cfg: Config) -> None:
        etc = cfg.entry_timing()
        before = DA._verify(etc)
        self.panel = K.load_panel(cfg.db, version_id=cfg.version)
        self.raw = DA.read_raw(cfg.db, cfg.version)
        try:
            K.assert_same_source(before, DA._verify(etc))
        except K.SealedSourceError as e:
            raise CheckRequired(f"검산 중 봉인 판 바뀜: {e}"[:300]) from e
        self.seal = {k: before[k] for k in SEAL_KEYS}
        self.axis = self.panel.dates
        self.series = self.panel.series
        if BENCH not in self.series:
            raise CheckRequired(
                f"벤치마크 {BENCH} 행이 없음"
            )  # 실행 쪽(population)과 같은 멈춤(반박 NIT)

    def chain(self, code: str, d: str) -> Optional[tuple[float, int]]:
        s = self.series[code]
        r = s.index.get(d)
        if r is None or s.chain[r] is None or s.close_status[r] != K.CLOSE_OK:
            return None
        return float(s.chain[r]), int(s.segment[r])

    def has(self, code: str, d: str) -> bool:
        return d in self.series[code].index

    def seg(self, code: str, d: str) -> Optional[int]:
        r = self.series[code].index.get(d)
        return None if r is None else int(self.series[code].segment[r])

    def open_star(self, code: str, d: str) -> Optional[float]:
        """체결 가능하면 합성 시가 · 아니면 None."""
        s = self.series[code]
        r = s.index.get(d)
        if r is None:
            return None
        rw = self.raw.get(code, {}).get(d)
        if rw is None:  # reader 에는 있는데 원시 행이 없음 — 같은 판이 아님
            raise CheckRequired(f"원시 행 없음: {code} {d}")
        o, h, lo, c, v, _ = rw
        ch = s.chain[r]
        if ch is None or s.close_status[r] != K.CLOSE_OK or not s.relation_ok[r]:
            return None
        if (
            v is None
            or v <= 0
            or o is None
            or o <= 0
            or h is None
            or lo is None
            or c is None
        ):
            return None
        if not (h >= max(o, c) and 0 < lo <= min(o, c)):
            return None
        return o * (ch / c)

    def no_trade(self, code: str, d: str) -> bool:
        rw = self.raw.get(code, {}).get(d)
        return rw is not None and rw[4] is not None and rw[4] <= 0


def _window_start(axis: list[str], i: int) -> Optional[int]:
    target = (
        dt.date.fromisoformat(axis[i]) - dt.timedelta(days=LOOKBACK_1M)
    ).isoformat()
    if target < axis[0]:
        return None
    return next(j for j in range(i + 1) if axis[j] >= target)


def _ups(closes: list[Optional[float]]) -> Optional[int]:
    if any(c is None or c <= 0 for c in closes):
        return None
    return sum(1 for a, b in zip(closes, closes[1:]) if b / a - 1.0 > UP_EPS)


def _sub(d: str, subs: tuple) -> Optional[int]:
    return next((k for k, (lo, hi) in enumerate(subs) if lo <= d <= hi), None)


# ── 주 기록 ─────────────────────────────────────────────────────────────────


def _week_record(
    src: Src, k: int, sig: list[int], cfg: Config
) -> Optional[dict[str, Any]]:
    axis = src.axis
    i = sig[k]
    d = axis[i]
    span = next((key for key, (lo, hi) in cfg.spans.items() if lo <= d <= hi), None)
    if span is None or k < N_INTERVALS:
        return None
    s = _window_start(axis, i)
    if s is None:
        return None
    wk = [sig[k - N_INTERVALS + m] for m in range(N_INTERVALS + 1)]
    e1, e2 = i + 1, i + 1 + HOLD_DAYS
    pop = []
    for code, ser in src.series.items():
        cd, cs = src.chain(code, d), src.chain(code, axis[s])
        if (
            cd is None
            or cs is None
            or cd[1] != cs[1]
            or _excluded(ser.name[ser.index[d]])
        ):
            continue
        closes = []
        for w in wk:
            got = src.chain(code, axis[w])
            closes.append(got[0] if got is not None and got[1] == cd[1] else None)
        pop.append(
            {
                "code": code,
                "ret": cd[0] / cs[0] - 1.0,
                "closes": closes,
                "up": _ups(closes),
            }
        )
    pop.sort(key=lambda p: (-p["ret"], p["code"]))
    common = []
    for r, p in enumerate(pop, 1):
        p["orig_rank"] = r
        if p["up"] is not None:
            common.append(p)
            p["common_rank"] = len(common)
    dropped = [p for p in pop if p["up"] is None]
    rec: dict[str, Any] = {
        "signal": d,
        "span": span,
        "sub": _sub(d, cfg.subs) if span == "main" else None,
        "window": [axis[s], d],
        "weekly_dates": [axis[w] for w in wk],
        "weekly_before_window": axis[wk[0]] < axis[s],
        "entry": axis[e1] if e1 < len(axis) else None,
        "exit": axis[e2] if e2 < len(axis) else None,
        "n_pop": len(pop),
        "n_common": len(common),
        "dropped": [[p["code"], p["orig_rank"]] for p in dropped],
        "dropped_top3": any(p["orig_rank"] <= N_PICK for p in dropped),
        "dropped_top30": any(p["orig_rank"] <= 30 for p in dropped),
    }
    if e2 >= len(axis) or len(common) < N_PICK:
        status = "IMMATURE" if e2 >= len(axis) else "FEW"
        rec.update(status=status, a=[], b=[], same=None, picks={})
        return rec
    by_ret = sorted(common, key=lambda p: (-p["ret"], p["code"]))
    a = [p["code"] for p in by_ret[:N_PICK]]
    pos = sorted(
        (p for p in common if p["ret"] > 0),
        key=lambda p: (-p["up"], -p["ret"], p["code"]),
    )
    b = [p["code"] for p in pos[:N_PICK]]
    for p in by_ret:
        if len(b) >= N_PICK:
            break
        if p["code"] not in b:
            b.append(p["code"])
    by = {p["code"]: p for p in common}
    rec.update(
        status="OK",
        a=a,
        b=b,
        same=set(a) == set(b),
        picks={
            c: {
                k: by[c][k] for k in ("orig_rank", "common_rank", "ret", "up", "closes")
            }
            for c in sorted(set(a) | set(b))
        },
        a_order=[p["code"] for p in by_ret[:ORDER_KEEP]],
        b_order=[p["code"] for p in pos[:ORDER_KEEP]],
    )
    return rec


# ── 자리 · 묶음 · 주 평가 ─────────────────────────────────────────────────────


def _slot(src: Src, code: str, e1: str, e2: str) -> dict[str, Any]:
    if src.open_star(code, e1) is not None:
        entry, why = "OK", None
    elif src.has(code, e1) and src.no_trade(code, e1):
        entry, why = "CASH", "NO_TRADE_E1"
    else:
        entry, why = "UNKNOWN", (
            "NO_ROW_E1" if not src.has(code, e1) else "NOT_EXEC_E1"
        )
    out: dict[str, Any] = {"code": code, "entry": entry, "exit": None, "why": why}
    if entry != "OK":
        return out
    if not src.has(code, e2):
        out.update(exit="UNKNOWN", why="NO_ROW_E2")
    elif src.seg(code, e2) != src.seg(code, e1):
        out.update(exit="UNKNOWN", why="SEG_BREAK")
    elif src.open_star(code, e2) is None:
        out.update(exit="UNKNOWN", why="NOT_EXEC_E2")
    else:
        out["exit"] = "OK"
    return out


def _basket(
    src: Src,
    codes: list[str],
    e1: str,
    e2: str,
    days: list[str],
    cost: float,
    alt: bool,
) -> dict[str, Any]:
    """세 자리 — 자리 기록 · 비용 후 수익률 · 비용 전 낙폭(값을 못 내면 수익률 None)."""
    slots: list[dict] = []
    rets: list[float] = []
    paths: list[Optional[list[float]]] = []
    cash: list[bool] = []
    ok = True
    for code in codes:
        rec = _slot(src, code, e1, e2)
        if rec["entry"] == "CASH" or (alt and rec["entry"] == "UNKNOWN"):
            rec["value"] = "CASH"
            rets.append(0.0)
            paths.append(None)
            cash.append(True)
            slots.append(rec)
            continue
        if rec["entry"] == "UNKNOWN":
            ok = False
            slots.append(rec)
            continue
        o1 = src.open_star(code, e1)
        seg = src.seg(code, e1)
        x: Optional[float] = None
        if rec["exit"] == "OK":
            x = src.open_star(code, e2)
        elif alt:
            for d in reversed(days + [e2]):
                got = src.chain(code, d)
                if got is not None and got[1] == seg and got[0] > 0:
                    x = got[0]
                    rec.update(exit="REFERENCE", ref_date=d)
                    break
        if x is None:
            ok = False
            slots.append(rec)
            continue
        rets.append(x * (1.0 - cost) / (o1 * (1.0 + cost)) - 1.0)
        pv: Optional[list[float]] = [1.0]
        for d in days:
            got = src.chain(code, d)
            if got is None or got[1] != seg:
                pv = None
                break
            pv.append(got[0] / o1)
        paths.append(None if pv is None else pv + [x / o1])
        cash.append(False)
        rec.update(entry_px=o1, exit_px=x)
        slots.append(rec)
    out: dict[str, Any] = {"slots": slots, "ret": None, "mdd": None}
    if not ok or len(rets) != len(codes):
        return out
    out["ret"] = sum(rets) / len(rets)
    if all(c or p is not None for c, p in zip(cash, paths)):
        agg = [
            sum(1.0 if c else p[t] for c, p in zip(cash, paths)) / len(paths)
            for t in range(len(days) + 2)
        ]
        peak, worst = agg[0], 0.0
        for v in agg:
            peak = max(peak, v)
            worst = max(worst, 1.0 - v / peak)
        out["mdd"] = worst
    return out


def _evaluate_week(
    src: Src, w: dict[str, Any], cost: float, alt: bool
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "status": w["status"],
        "ret_a": None,
        "ret_b": None,
        "d": None,
    }
    if w["status"] != "OK":
        return out
    pos = {d: i for i, d in enumerate(src.axis)}
    lo = pos[w["entry"]]
    hi = lo + HOLD_DAYS
    days = src.axis[lo:hi]
    a = _basket(src, w["a"], w["entry"], w["exit"], days, cost, alt)
    b = _basket(src, w["b"], w["entry"], w["exit"], days, cost, alt)
    out.update(
        slots_a=a["slots"],
        slots_b=b["slots"],
        reasons=[
            [rule, s["code"], s["why"]]
            for rule, bk in (("A", a), ("B", b))
            for s in bk["slots"]
            if s["why"] is not None
        ],
    )
    if a["ret"] is None or b["ret"] is None:
        out["status"] = "INVALID"
        return out
    kx = None
    o1, o2 = src.open_star(BENCH, w["entry"]), src.open_star(BENCH, w["exit"])
    if (
        o1 is not None
        and o2 is not None
        and src.seg(BENCH, w["entry"]) == src.seg(BENCH, w["exit"])
    ):
        kx = o2 * (1.0 - cost) / (o1 * (1.0 + cost)) - 1.0
    out.update(
        ret_a=a["ret"],
        ret_b=b["ret"],
        d=0.0 if w["same"] else b["ret"] - a["ret"],
        mdd_a=a["mdd"],
        mdd_b=b["mdd"],
        kodex=kx,
    )
    return out
