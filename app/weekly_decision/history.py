"""지난 네 주 — 현재 ETF 목록과 저장 가격으로 복원 · 그 주 저장 기록 · 그 뒤 관측(PLAN §3 · 판정 §3 · Q2 · Q6).

```text
주         이번 검토가 속한 주의 직전 네 완료 주 = current.weekly_dates 의 주 마감
           (끝일이 속한 주가 끝났으면 W-4 ~ W-1 · 아니면 W-3 ~ W0)
복원       마감일마다 read_market(db, 그날) → build — 그날까지의 저장 가격 · 현재 ETF 목록 · 같은 조회 조건
           모집단 밖이면 build 와 같은 순서의 사유(not_listed · no_price · filter_excluded · no_return ·
           end_differs · start_differs) · 그날 KODEX 200 1개월 기간을 못 정하면 순위 확인 불가
그 주 기록 판단 근거 DB ai_session_records(읽기 전용) — 기준일(asof)이 그 ISO 주이고 검토 끝일 이하인 것만
나중 기록  기준일이 끝일 이하여도 만든 시각(created_at · saved_at)이 검토 시점(cutoff) 뒤면 넣지 않는다
           cutoff = 끝일을 지정하지 않으면(지금 검토) 지금 · 지정하면 min(지금, 끝일 다음 날 0시 KST)
그 뒤 ·    그 뒤 관측 · 이번 주 지금까지 = observe 모듈(after_move · this_week) — 주 마감 규칙이 직전 주를 건너뛰어
이번 주    마지막 행이 그 전 주에서 끝나면 this_week 를 then 으로 덧붙임
```
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from app.candidate_compare import current as CU
from app.candidate_compare.protocol import LOOKBACK_1M
from app.decision_evidence_store import UNRECORDED_USER_VERDICT
from app.market_topn_helpers import classify_etf_tags
from app.pc_etf_compare_periods import period_value
from app.same_period_kodex200 import valid_close
from app.weekly_decision.conditions import filter_gaps, filter_value

# 화면 · 실행 스크립트 · 시험이 H.read_sessions 로 부름(읽기 · 형식 검사는 records)
from app.weekly_decision.records import read_sessions  # noqa: F401
from app.weekly_decision.observe import after_move, this_week

N_ROWS = 4
KST = timezone(timedelta(hours=9))


def _by_ticker(build: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {it["ticker"]: it for it in build.get("items") or []}


@dataclass
class Context:
    """한 검토 끝일의 자료 — 이번 주 전체 후보 · 네 주 복원(후보와 무관 · 한 번만 계산)."""

    db: Path
    end: str
    filters: dict[str, bool]
    market: dict[str, Any]
    build: dict[str, Any]
    fingerprint: str
    is_trading: Callable[[str], bool]
    official: Optional[
        Mapping[str, Mapping[str, str]]
    ]  # None = 공식 기준정보를 읽지 못함
    rows: list[str]
    rows_gap: Optional[str]
    restores: dict[tuple, dict[str, Any]] = field(default_factory=dict)

    def item(self, ticker: str) -> Optional[Mapping[str, Any]]:
        return _by_ticker(self.build).get(ticker)

    def restore(
        self, d: str, filters: Optional[Mapping[str, bool]] = None
    ) -> dict[str, Any]:
        """그날까지의 저장 가격으로 다시 계산 — 끝일 뒤 날짜는 받지 않는다(나중 값 차단)."""
        if d > self.end:
            raise ValueError(f"검토 끝일 뒤 날짜는 복원하지 않음: {d} > {self.end}")
        f = dict(self.filters if filters is None else filters)
        key = (d, tuple(sorted(f.items())))
        if key not in self.restores:
            m = CU.read_market(self.db, d)
            b = CU.build(
                m, filters=f, official={}, dictionary=None, is_trading=self.is_trading
            )
            self.restores[key] = {
                "date": d,
                "market": m,
                "build": b,
                "fingerprint": CU.fingerprint(m),
                "by": _by_ticker(b),
            }
        return self.restores[key]

    def fingerprints(self) -> dict[str, str]:
        """저장 스냅숏에 남기는 자료 지문 — 이번 주 + 계산한 복원마다."""
        out = {"current": self.fingerprint}
        for (d, f), rs in sorted(self.restores.items()):
            out[f"{d}|{','.join(k for k, v in f if v)}"] = rs["fingerprint"]
        return out


def parse_time(ts: Any) -> Optional[datetime]:
    """기록 시각 → KST 시각(시간대 없으면 KST 로 봄) · 못 읽으면 None."""
    if not isinstance(ts, str):
        return None
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (t if t.tzinfo else t.replace(tzinfo=KST)).astimezone(KST)
    except (ValueError, OverflowError):  # 범위 밖 시각(반박 검토 D2 · D7)
        return None


def cutoff_of(end_arg: Optional[str], end: str, now: datetime) -> datetime:
    """검토 시점 — 끝일 지정 없음 = 지금 · 지정 = min(지금, 끝일 다음 날 0시 KST).

    이 시각 '앞'에 만든 기록만 넣는다(known) — 끝일 다음 날 0시 정각에 만든 기록은 다음 날 것이다."""
    n = now.astimezone(KST)
    if end_arg is None:
        return n
    nxt = datetime.fromisoformat(end).replace(tzinfo=KST) + timedelta(days=1)
    return min(n, nxt)


def known(ts: Any, cutoff: datetime) -> bool:
    """검토 시점 앞에 만든 기록인가(경계 시각 자체는 넣지 않음 · 시각을 못 읽으면 넣지 않음)."""
    t = parse_time(ts)
    return t is not None and t < cutoff


def review_rows(build: Mapping[str, Any]) -> tuple[list[str], Optional[str]]:
    """직전 네 완료 주 마감일 · 못 정하면 ([], 사유)."""
    if build.get("status") != "ok":
        return [], str(build.get("status") or "no_build")
    wk = build.get("weekly") or {}
    dates = wk.get("dates")
    if not dates:
        return [], str((wk.get("gap") or {}).get("why") or "no_dates")
    return (list(dates[:N_ROWS]) if wk.get("finished") else list(dates[-N_ROWS:])), None


def load_context(
    db: Path,
    end: Optional[str],
    *,
    filters: Mapping[str, bool],
    official: Optional[Mapping[str, Mapping[str, str]]],
    dictionary: Optional[Mapping[str, list[str]]],
    is_trading: Optional[Callable[[str], bool]] = None,
) -> Context:
    trading = is_trading or CU.default_is_trading
    market = CU.read_market(Path(db), end)
    build = CU.build(
        market,
        filters=dict(filters),
        official=official or {},
        dictionary=dictionary,
        is_trading=trading,
    )
    rows, gap = review_rows(build)
    ctx = Context(
        db=Path(db),
        end=market["end"],
        filters=dict(filters),
        market=market,
        build=build,
        fingerprint=CU.fingerprint(market),
        is_trading=trading,
        official=official,
        rows=rows,
        rows_gap=gap,
    )
    for d in rows:
        ctx.restore(d)
    return ctx


def exclusion(
    market: Mapping[str, Any],
    ticker: str,
    filters: Mapping[str, bool],
    common: Optional[tuple[str, str]],
) -> str:
    """모집단 밖 사유 — current.build 의 판정 순서 그대로(시험이 build 의 사유 개수와 대조)."""
    names, raw = market["names"], market["raw"]
    if ticker not in names:
        return "not_listed"
    valid = [
        (r.date, float(r.close)) for r in raw.get(ticker, []) if valid_close(r.close)
    ]
    if not valid:
        return "no_price"
    exclude = {t for t in CU.FILTER_TAGS if filters.get(f"exclude_{t}")}
    if exclude & set(classify_etf_tags(names.get(ticker))):
        return "filter_excluded"
    v = period_value(valid, market["end"], LOOKBACK_1M)
    if v is None:
        return "no_return"
    if common is None:
        return "no_common_period"
    if v["end"] != common[1]:
        return "end_differs"
    if v["start"] != common[0]:
        return "start_differs"
    return "in_population"


def seen_at(rs: Mapping[str, Any], ticker: str) -> dict[str, Any]:
    """그 마감일에 이 후보가 어떻게 보였나(복원) — 순위 · 상위 30 · 1개월 · 오른 주 또는 사유."""
    b = rs["build"]
    if b.get("status") != "ok":
        return {"state": "unknown", "why": str(b.get("status") or "no_build")}
    it = rs["by"].get(ticker)
    if it is None:
        why = exclusion(rs["market"], ticker, b["filters"], b["windows"]["one_month"])
        return {"state": "out", "why": why}
    return {
        "state": "ranked",
        "rank": it["rank"],
        "top30": it["top30"],
        "population": b["counts"]["population"],
        "one_month": dict(it["one_month"]),
        "up": it["up"],
        "week_gap": it["week_gap"],
        "price_state": it["state"],
        "w0": (b.get("weekly") or {}).get("w0"),
    }


# --- 판단 근거 DB(「AI 투자 세션」 저장 기록) — 읽기 · 형식 검사는 records ---


def verdict_state(rec: Mapping[str, Any]) -> str:
    """unrecorded = 미기록 · default = 그 화면 기본값과 같아 직접 고른 값인지 모름 · chosen = 직접 고름."""
    if rec["verdict"] == UNRECORDED_USER_VERDICT:
        return "unrecorded"
    if rec["verdict"] == rec["default_verdict"]:
        return "default"
    return "chosen"


def entry_of(rec: Mapping[str, Any], ticker: str) -> Optional[dict[str, Any]]:
    return next((it for it in rec["items"] if it["ticker"] == ticker), None)


def visible(
    records: list[Mapping[str, Any]],
    reviews: list[Mapping[str, Any]],
    end: str,
    cutoff: datetime,
) -> tuple[
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
]:
    """검토 시점에 있던 기록만 — 기준일 ≤ 끝일 · 만든 시각 < cutoff.

    돌려줌 = (넣은 AI 세션 기록, 넣은 내 판단, 기준일은 끝일 이하인데 검토 시점 뒤에 만들어 뺀 기록, 같은 판단)."""
    recs = [r for r in records if r["asof"] <= end]
    revs = [r for r in reviews if isinstance(r.get("end"), str) and r["end"] <= end]
    keep_recs = [r for r in recs if known(r["created_at"], cutoff)]
    keep_revs = [r for r in revs if known(r.get("saved_at"), cutoff)]
    late_recs = [r for r in recs if not known(r["created_at"], cutoff)]
    late_revs = [r for r in revs if not known(r.get("saved_at"), cutoff)]
    return keep_recs, keep_revs, late_recs, late_revs


def week_records(
    records: list[Mapping[str, Any]], d: str, end: str, ticker: str
) -> dict[str, Any]:
    """그 ISO 주에 남긴 저장 기록 — 전체 건수 · 이 ETF 가 들어 있는 기록(기준일 순)."""
    wk = CU._iso(d)
    inweek = [r for r in records if r["asof"] <= end and CU._iso(r["asof"]) == wk]
    mine = []
    for r in sorted(inweek, key=lambda x: (x["asof"], x["created_at"])):
        e = entry_of(r, ticker)
        if e is not None:
            mine.append({"record": r, "entry": e})
    return {"count": len(inweek), "mine": mine}


def comparable(entry: Optional[Mapping[str, Any]]) -> bool:
    """순위 · 1개월 값 · 기간이 모두 저장된 기록만 '지난 검토와 비교'에 쓴다."""
    return bool(
        entry
        and entry["rank"] is not None
        and entry["one_month"] is not None
        and entry["start"]
        and entry["end"]
    )


def latest_comparable(
    records: list[Mapping[str, Any]], end: str, ticker: str
) -> Optional[dict[str, Any]]:
    got = [
        {"record": r, "entry": entry_of(r, ticker)}
        for r in records
        if r["asof"] <= end and comparable(entry_of(r, ticker))
    ]
    got.sort(key=lambda x: (x["record"]["asof"], x["record"]["created_at"]))
    return got[-1] if got else None


def cite_judge(
    rec: Mapping[str, Any],
    entry: Optional[Mapping[str, Any]],
    current: Mapping[str, bool],
    check: Optional[Mapping[str, Any]],
) -> dict[str, Any]:
    """외부 AI 복사문 인용 판정(V2 RESULT 판정 2026-11-26 §2) — 이번 조회 조건과 같다고 확인된 기록만 same.

    same = 제외 조건 네 칸이 모두 불리언으로 저장돼 지금과 같고, 그 기록의 조건으로 그날을 다시 계산한 순위 · 1개월 값 ·
    기간이 저장값과 같음(순위 산정 기준까지 같다고 확인) · differs = 저장된 제외 조건 칸이 지금과 다름 ·
    unknown = 값 없음 · 조건 칸 빠짐 · 다시 계산이 저장값과 다름 · 맞춰 보지 못함.
    why = 화면에 보일 이유(no_value · filters · filter_unknown · 맞춰 보기 상태 · not_checked) ·
    diff = 다른 칸(stored · now) · missing = 저장되지 않은 칸 · invalid = 저장 형식이 맞지 않는 칸 ·
    conflict = 서로 다른 값으로 두 번 저장된 칸 · extra = 지금 조건에 없는 칸(조건 칸 판정 = conditions)."""
    if not comparable(entry):
        gaps: dict[str, list[str]] = {
            "missing": [],
            "invalid": [],
            "conflict": [],
            "extra": [],
        }
        return {"state": "unknown", "why": "no_value", "diff": [], **gaps}
    got = {k: filter_value(rec["filters"], k) for k in current}
    diff = [
        {"key": k, "stored": v, "now": bool(current[k])}
        for k, v in got.items()
        if isinstance(v, bool) and v != bool(current[k])
    ]
    cond = filter_gaps(rec["filters"], current)
    if diff:
        return {"state": "differs", "why": "filters", "diff": diff, **cond}
    if any(cond.values()):
        return {"state": "unknown", "why": "filter_unknown", "diff": [], **cond}
    st = (check or {}).get("state") or "not_checked"
    state = "same" if st == "match" else "unknown"
    return {"state": state, "why": st, "diff": [], **cond}


def cite_state(
    rec: Mapping[str, Any],
    entry: Optional[Mapping[str, Any]],
    current: Mapping[str, bool],
    check: Optional[Mapping[str, Any]],
) -> str:
    return cite_judge(rec, entry, current, check)["state"]


def cited_records(
    ctx: "Context",
    ticker: str,
    rows: list[Mapping[str, Any]],
    records: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """복사문 [당시 저장 기록]에 인용할 기록 — 정정 전 인용 대상(지난 네 주 안의 비교 가능한 기록 + 가장 최근
    비교 가능한 기록 하나) 가운데 같은 조건으로 확인된 것만(판정 §2 = 인용 대상에서 제외 · 더 앞 기록으로
    대신하지 않음 · 다시 계산은 많아야 한 번 더) · 각 = 기록 번호 · 기준일 · 순위 · 1개월 값 · 기간."""
    out: list[dict[str, Any]] = []

    def add(rec: Mapping[str, Any], e: Mapping[str, Any]) -> None:
        one = {"value": e["one_month"], "start": e["start"], "end": e["end"]}
        out.append(
            {
                "record_id": rec["id"],
                "asof": rec["asof"],
                "rank": e["rank"],
                "one_month": one,
            }
        )

    in_rows: set[str] = set()
    for row in rows:
        for m in row["records"]["mine"]:
            if m["record"]["id"] in in_rows:
                continue
            in_rows.add(m["record"]["id"])
            if m.get("cite") == "same":
                add(m["record"], m["entry"])
    got = latest_comparable(records, ctx.end, ticker)
    if got and got["record"]["id"] not in in_rows:
        rec, e = got["record"], got["entry"]
        if cite_state(rec, e, ctx.filters, reconcile(ctx, rec, e)) == "same":
            add(rec, e)
    return out


def reconcile(
    ctx: Context, rec: Mapping[str, Any], entry: Mapping[str, Any]
) -> dict[str, Any]:
    """저장 기록의 1개월 끝일을 기준일로 같은 조건 복원 → 저장 순위 · 값과 대조(Q6 대조 근거).

    비교 기간(시작일 · 끝일)이 다르면 값이 같아도 '일치'가 아니다 — period_differs(값 대조 안 함)."""
    d = entry.get("end") or rec["asof"]
    if d > ctx.end:
        return {"state": "after_end", "date": d}
    want = {k: filter_value(rec["filters"], k) for k in ctx.filters}
    if any(filter_gaps(rec["filters"], ctx.filters).values()):
        # 빠지거나 형식이 틀린 칸을 '제외 안 함'으로 가정해 다시 계산하지 않음(검증 F18 · B-1)
        return {"state": "filters_unknown", "date": d}
    seen = seen_at(ctx.restore(d, want), entry["ticker"])
    if seen["state"] != "ranked":
        return {"state": "no_restore", "date": d, "why": seen["why"]}
    so = seen["one_month"]
    restored = {
        "rank": seen["rank"],
        "value": so["value"],
        "start": so["start"],
        "end": so["end"],
    }
    stored = {
        "rank": entry["rank"],
        "value": entry["one_month"],
        "start": entry["start"],
        "end": entry["end"],
    }
    if (so["start"], so["end"]) != (entry["start"], entry["end"]):
        state = "period_differs"
    elif (
        seen["rank"] == entry["rank"]
        and abs(so["value"] - entry["one_month"]) <= 0.00005 + 1e-9
    ):
        state = "match"
    else:
        state = "differs"
    return {"state": state, "date": d, "restored": restored, "stored": stored}


def four_weeks(
    ctx: Context,
    ticker: str,
    records: list[Mapping[str, Any]],
    reviews: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """지난 네 주 표의 자료(후보 한 건) — 복원 · 그 주 기록 · 그 주 내 판단 · 그 뒤 관측."""
    if not ctx.rows:
        return {"state": "unavailable", "why": ctx.rows_gap, "rows": []}
    rows = []
    for d in ctx.rows:
        wk = CU._iso(d)
        rows.append(
            {
                "date": d,
                "seen": seen_at(ctx.restore(d), ticker),
                "records": week_records(records, d, ctx.end, ticker),
                "reviews": [
                    rv
                    for rv in reviews
                    if rv.get("ticker") == ticker
                    and rv.get("end")
                    and rv["end"] <= ctx.end
                    and CU._iso(rv["end"]) == wk
                ],
                "after": after_move(ctx, ticker, d),
            }
        )
    # 진행 주(이번 주 지금까지)는 this_week 한 곳에서 정한다 — 표 · 그래프 · 복사문이 같은 상태(반박 검토 F1 · F3)
    tw = this_week(ctx, ticker)
    last = rows[-1]
    if tw is not None and tw["from"] == last["date"]:
        # 마지막 행이 곧 직전 완료 주 마감 — 그 칸 = 이번 주 지금까지
        last["after"] = tw
    elif tw is not None and tw["from"] > last["date"]:
        # 주 마감 규칙이 직전 주를 건너뛰어(예: 금요일 KODEX 200 이 장중 저장뿐) 표 마지막 행이 그 전 주에서
        # 끝날 때 — 같은 칸 아래에 '이번 주 지금까지'(시작 = 거래 일정상 직전 완료 주 마감)를 덧붙인다
        last["after"]["then"] = tw
    skipped = (ctx.build.get("weekly") or {}).get("skipped") or []
    return {"state": "ok", "rows": rows, "skipped": list(skipped)}
