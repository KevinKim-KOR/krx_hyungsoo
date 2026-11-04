"""POC6-20 시장 정보 4열 — POC6-19 연구 사본 → 신호일별 값 · 근거 · 미정의 사유 — 설계 §3 · §4 · PLAN §2 · 판정 §4.

```text
사본    수급 = POC6-19 추가 실행 normalized(investor_flow · investor_flow_dates) · 외국인 · 기관계 두 분류만
        (세부 7개 · 국가는 읽지 않는다) · 매크로 = 낮 실행 normalized/macro.csv 의 canonical=1(B 장기)만
        (A 표본 116행은 합치지 않는다) · 파일 sha256 이 고정값과 다르면 CheckRequired
가용    마감 = 신호일 D 23:59:59 KST · 수급 관측일 d = d 다음 축 거래일 12:00 KST
        매크로 관측일 d = 원천 시간대 d + 2달력일 00:00 을 KST 로 바꾼 시각 · 마감 이하만 쓴다
4열     FLOW_FRGN_DIR_20 · FLOW_ORGN_DIR_20 = 마지막 가용 예상 거래일까지 20 축 거래일 순매수 합 / 절댓값 합
        (20일 모두 VALID · 절댓값 합 0 = 0.0 + ALL_ZERO 표시) · USDKRW_CHG_20 = 최신 유효 관측 / 20개 앞 − 1
        WTI_DIFF_20 = 최신 유효 관측 − 20개 앞(USD/bbl · 0 · 음수 유지 · 비율 · 로그로 바꾸지 않음)
미정의  창이 축 시작 앞 · 수급 요청 전 날짜 · 실패일 포함 · 매크로 21개 부족 = None + 사유(채우지 · 줄이지 않음)
```

예상 한국 거래일 = 봉인 판 069500 날짜 축(H1 과 같은 축). 시각은 이번 회고 비교의 고정 가정이며 실제 과거
공개 시각이 아니다(설계 §4).
"""

from __future__ import annotations

import bisect
import csv
import datetime as dt
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app.ml_evidence import store
from app.weekly_selection.data import CheckRequired

KST = ZoneInfo("Asia/Seoul")
RESEARCH = Path("state/ml/research/poc6_19")
FLOW_RUN = "20261103T171931Z_b0ea4fcf"
MACRO_RUN = "20261103T044323Z_92947186"
FLOW_FILE = "normalized/investor_flow.csv"
FLOW_DATES_FILE = "normalized/investor_flow_dates.csv"
MACRO_FILE = "normalized/macro.csv"
SHA = {
    FLOW_FILE: "43f9578de7ba319e3883acdfbe99762ce0e050f5698c16a56e2f8bd4cf9a9e68",
    FLOW_DATES_FILE: "e7d8baa529d87dff1a47e58f49da9dfb9a870b67587f013dd01b24ce1ce77e71",
    MACRO_FILE: "60be6c20fd453c187995672238e62b155454a15eca762af69a6694d11c7e9ef0",
}
COLUMNS = ("FLOW_FRGN_DIR_20", "FLOW_ORGN_DIR_20", "USDKRW_CHG_20", "WTI_DIFF_20")
FLOW_INVESTOR = {"FLOW_FRGN_DIR_20": "foreign", "FLOW_ORGN_DIR_20": "institution"}
KRW = "YAHOO_KRW_X_CLOSE_KRW_PER_USD"
WTI = "YAHOO_CL_F_CLOSE_USD_PER_BBL"
MACRO_SERIES = {"USDKRW_CHG_20": KRW, "WTI_DIFF_20": WTI}
FLOW_WIN = 20
MACRO_GAP = 20
FLOW_HOUR = 12
MACRO_LAG_DAYS = 2


@dataclass
class Sources:
    flow_status: dict[str, str]  # 날짜 → VALID · FAILED
    flow_net: dict[str, dict[str, int]]  # VALID 날짜 → {foreign · institution: 정수 원}
    macro: dict[
        str, list[dict]
    ]  # 계열 → 관측(날짜 오름차순 · obs_date · timezone · close · flag)
    files: dict[str, str] = field(default_factory=dict)  # 상대 경로 → sha256


def _path(base: Path, run: str, rel: str) -> Path:
    return Path(base) / run / rel


def _checked(base: Path, run: str, rel: str, files: dict[str, str]) -> Path:
    f = _path(base, run, rel)
    if not f.is_file():
        raise CheckRequired(f"시장 사본 없음: {run}/{rel}")
    got = store.sha256_file(f)
    if got != SHA[rel]:
        raise CheckRequired(f"시장 사본 해시 다름: {run}/{rel} {got}")
    files[f"{run}/{rel}"] = got
    return f


def _iso(s: str, what: str) -> str:
    try:
        return dt.date.fromisoformat(s).isoformat()
    except (TypeError, ValueError) as e:
        raise CheckRequired(f"{what} 날짜 형식 이상: {s!r}") from e


def _finite(s: str, what: str) -> float:
    try:
        v = float(s)
    except (TypeError, ValueError) as e:
        raise CheckRequired(f"{what} 값 형식 이상: {s!r}") from e
    if not math.isfinite(v):
        raise CheckRequired(f"{what} 값 비유한: {s!r}")
    return v


def load_sources(base: Path = RESEARCH) -> Sources:
    """두 실행의 정규화 파일을 해시 확인 뒤 읽는다(원본 쓰기 0)."""
    files: dict[str, str] = {}
    status: dict[str, str] = {}
    with open(_checked(base, FLOW_RUN, FLOW_DATES_FILE, files), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            d = _iso(r["date"], "수급 날짜")
            if d in status:
                raise CheckRequired(f"수급 날짜 중복: {d}")
            if r["status"] not in ("VALID", "FAILED"):
                raise CheckRequired(f"수급 상태 이상: {d} {r['status']!r}")
            status[d] = r["status"]
    net: dict[str, dict[str, int]] = {}
    want = set(FLOW_INVESTOR.values())
    with open(_checked(base, FLOW_RUN, FLOW_FILE, files), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["investor"] not in want:
                continue
            d = _iso(r["date"], "수급 날짜")
            try:
                v = int(r["net_won"])
            except ValueError as e:
                raise CheckRequired(f"수급 값 형식 이상: {d} {r['net_won']!r}") from e
            per = net.setdefault(d, {})
            if r["investor"] in per:
                raise CheckRequired(f"수급 값 중복: {d} {r['investor']}")
            per[r["investor"]] = v
    for d, st in status.items():
        has = set(net.get(d, {}))
        if st == "VALID" and has != want:
            raise CheckRequired(f"수급 VALID 날짜에 값 없음: {d} {sorted(want - has)}")
        if st != "VALID" and has:
            raise CheckRequired(f"수급 실패 날짜에 값이 있음: {d}")
    if set(net) - set(status):
        raise CheckRequired("수급 값에 날짜 표에 없는 날짜")
    macro: dict[str, list[dict]] = {KRW: [], WTI: []}
    with open(_checked(base, MACRO_RUN, MACRO_FILE, files), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["canonical"] != "1" or r["series_id"] not in macro:
                continue
            tz = r["timezone"]
            try:
                ZoneInfo(tz)
            except (KeyError, ValueError) as e:
                raise CheckRequired(f"매크로 시간대 이상: {tz!r}") from e
            macro[r["series_id"]].append(
                {
                    "obs_date": _iso(r["obs_date"], "매크로 날짜"),
                    "timezone": tz,
                    "close": _finite(r["close"], "매크로 종가"),
                    "flag": r["flag"],
                }
            )
    for sid, obs in macro.items():
        ds = [o["obs_date"] for o in obs]
        if ds != sorted(set(ds)):
            raise CheckRequired(f"매크로 날짜 순서 · 중복 이상: {sid}")
        if len({o["timezone"] for o in obs}) > 1:
            raise CheckRequired(f"매크로 시간대가 하나가 아님: {sid}")
    if any(o["close"] <= 0 for o in macro[KRW]):
        raise CheckRequired("원/달러 0 이하 값(양수여야 함)")
    return Sources(flow_status=status, flow_net=net, macro=macro, files=files)


# ── 가용 시각 ────────────────────────────────────────────────────────────────────


def deadline(day: str) -> dt.datetime:
    d = dt.date.fromisoformat(day)
    return dt.datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=KST)


def flow_available(axis: list[str], k: int) -> Optional[dt.datetime]:
    """축 위치 k 의 수급 = 다음 축 거래일 12:00 KST(다음 거래일이 축 밖이면 None)."""
    if k + 1 >= len(axis):
        return None
    d = dt.date.fromisoformat(axis[k + 1])
    return dt.datetime(d.year, d.month, d.day, FLOW_HOUR, tzinfo=KST)


def macro_available(obs_date: str, tz: str) -> dt.datetime:
    d = dt.date.fromisoformat(obs_date) + dt.timedelta(days=MACRO_LAG_DAYS)
    return dt.datetime(d.year, d.month, d.day, tzinfo=ZoneInfo(tz)).astimezone(KST)


def _kst(t: dt.datetime) -> str:
    return t.astimezone(KST).isoformat()


# ── 4열 ──────────────────────────────────────────────────────────────────────────


def _flow(
    axis: list[str], i: int, src: Sources
) -> tuple[Optional[dict], list[str], dict]:
    dl = deadline(axis[i])
    e = i
    while e >= 0 and ((t := flow_available(axis, e)) is None or t > dl):
        e -= 1
    if e - FLOW_WIN + 1 < 0:
        return None, ["FLOW_AXIS_SHORT"], {}
    win = axis[e - FLOW_WIN + 1 : e + 1]  # noqa: E203
    ev = {
        "first": win[0],
        "last": win[-1],
        "days": len(win),
        "last_available_at": _kst(flow_available(axis, e)),
    }
    if any(d not in src.flow_status for d in win):
        return None, ["FLOW_NOT_REQUESTED"], ev
    bad = [d for d in win if src.flow_status[d] != "VALID"]
    if bad:
        return None, ["FLOW_FAILED " + ",".join(bad)], ev
    vals = {}
    for col, inv in FLOW_INVESTOR.items():
        s = sum(src.flow_net[d][inv] for d in win)
        a = sum(abs(src.flow_net[d][inv]) for d in win)
        vals[col] = s / a if a > 0 else 0.0
        ev[inv] = {"sum": s, "abs_sum": a, "all_zero": a == 0}
    return vals, [], ev


def _macro(col: str, i: int, axis: list[str], src: Sources, avail: dict) -> tuple:
    sid = MACRO_SERIES[col]
    obs = src.macro[sid]
    k = bisect.bisect_right(avail[sid], deadline(axis[i])) - 1
    if k < MACRO_GAP:
        return None, [f"MACRO_SHORT {sid}"], {}
    a, b = obs[k], obs[k - MACRO_GAP]
    if col == "USDKRW_CHG_20":
        v = a["close"] / b["close"] - 1.0
    else:
        v = a["close"] - b["close"]
    ev = {
        "series": sid,
        "timezone": a["timezone"],
        "latest": [a["obs_date"], a["close"], _kst(avail[sid][k])],
        "base": [b["obs_date"], b["close"], _kst(avail[sid][k - MACRO_GAP])],
        "calendar_days": (
            dt.date.fromisoformat(a["obs_date"]) - dt.date.fromisoformat(b["obs_date"])
        ).days,
        "flags": sorted({o["flag"] for o in obs[k - MACRO_GAP : k + 1]}),  # noqa: E203
    }
    return v, [], ev


def build(
    axis: list[str], signals: list[int], src: Sources
) -> dict[int, dict[str, Any]]:
    """신호 위치 → {values(4열 순서 · 미정의 = None), reasons, evidence}."""
    avail = {
        sid: [macro_available(o["obs_date"], o["timezone"]) for o in obs]
        for sid, obs in src.macro.items()
    }
    for sid, ts in avail.items():
        if ts != sorted(ts):
            raise CheckRequired(f"매크로 가용 시각 순서 이상: {sid}")
    out: dict[int, dict[str, Any]] = {}
    for i in signals:
        fv, reasons, fev = _flow(axis, i, src)
        ev: dict[str, Any] = {"deadline": _kst(deadline(axis[i])), "flow": fev}
        mv = {}
        for col in ("USDKRW_CHG_20", "WTI_DIFF_20"):
            v, why, mev = _macro(col, i, axis, src, avail)
            reasons += why
            ev[col] = mev
            mv[col] = v
        ok = fv is not None and all(v is not None for v in mv.values())
        out[i] = {
            "values": [{**(fv or {}), **mv}[c] for c in COLUMNS] if ok else None,
            "reasons": reasons,
            "evidence": ev,
        }
    return out
