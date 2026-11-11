"""POC6-28 — 「ETF 비교하기」 요약(PC · 저장 자료 읽기 전용 · `GET /market/etf-compare/summary`).

PLAN `docs/ai_plan/POC6/POC6_28_ETF_COMPARISON_SECTOR_AND_HOLDINGS_PLAN_V1.md` §3 · 판정 2026-11-11.

한 번의 응답에서 같은 모집단으로 [섹터 요약] · [ETF 순위] · 보유 약세 묶음 접점을 함께 만든다.

- 모집단(§3-1): 기존 태그로 제외 조건 → 조회 기간 수익률(기존 `_compute_period` 와 같은 시작 행 규칙).
  공통 끝일 = 시장 저장 최신일, 공통 시작일 = 069500 에 같은 규칙. 시작 · 끝 저장일이 공통 기간과 같은
  ETF만 넣고 나머지는 '기간이 달라 뺀 수'로 센다. 같은 모집단에서 상위 · 하위 최대 30.
- 네 기준(§3-6): 1개월 · 3개월(각 공통 기간과 시작 · 끝이 같아야 비교 가능) · 1개월 KODEX 200 대비
  (`same_period_kodex200.compare`) · 20저장일 고점 대비(`compute_stored_drawdown` · 069500 창과 같은 시작 · 끝).
- 가격 시점(§3-7): 끝일 행의 저장 시각(`fetched_at` → KST)으로 장중 저장값 · 마감 뒤 저장 · 마감값 확인
  필요를 나눈다. 종가라고 단정하지 않는다.
- 국면: 같은 069500 이력 · 같은 끝일로 기존 `compute_market_context` · `compute_regime_streak`.
- 보유(§3-4): ticker 와 연결 사실만 담는다(금액 · 계좌 없음).

외부 호출 · 쓰기 0. DB 는 `mode=ro` 로만 연다. 기존 `compute_topn` · 응답은 바꾸지 않는다.
"""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from app.market_regime import (
    KODEX200_TICKER,
    compute_market_context,
    compute_regime_streak,
)
from app.market_topn_helpers import (
    ONE_MONTH_LOOKBACK_DAYS,
    THREE_MONTH_LOOKBACK_DAYS,
    classify_etf_tags,
)
from app.pc_etf_compare_groups import (
    TOP_CONSTITUENTS,
    build_groups,
    classify_etf,
    constituent_key,
    exposure,
    mark_both_sides,
    side_overview,
)
from app.pc_etf_compare_holdings import holding_price_flow, read_recent_rows
from app.pc_etf_compare_periods import (
    BASIS_DAYS,
    CRIT_MISSING,
    CRIT_OK,
    CRIT_PERIOD_DIFFERS,
    criterion_from_period,
    drawdown_of,
    period_value,
    period_window,
    price_state,
    summarize_states,
)
from app.reentry_review.prices import PriceRow
from app.same_period_kodex200 import STATUS_OK as SAME_OK
from app.same_period_kodex200 import close_by_date, valid_close
from app.same_period_kodex200 import compare as same_period_compare

LIST_N = 30
FILTER_TAGS = ("inverse", "leveraged", "synthetic", "futures")

OUT_STOCK = "stock"
OUT_FILTER = "filter_excluded"
OUT_NO_PRICE = "no_price"
OUT_PERIOD = "period_differs"


def _ro(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def _read(
    con: sqlite3.Connection, end: str, start_from: str
) -> tuple[dict[str, list[PriceRow]], dict[str, Optional[str]]]:
    raw: dict[str, list[PriceRow]] = defaultdict(list)
    for tk, d, c, src, fa, ch in con.execute(
        "SELECT ticker, date, close, source, fetched_at, change FROM etf_daily_price "
        "WHERE date >= ? AND date <= ? ORDER BY ticker, date",
        (start_from, end),
    ):
        raw[tk].append(PriceRow(d, c, src, fa, ch))
    names = dict(con.execute("SELECT ticker, name FROM etf_master"))
    return raw, names


def _read_constituents(
    con: sqlite3.Connection, tickers: Sequence[str]
) -> dict[str, dict[str, Any]]:
    """ETF마다 최신 기준일 · 비중 상위 10(같은 기준일에 출처가 여럿이면 이름 순 첫 출처).

    구성종목 표가 아직 없는 DB 는 '구성 자료 없음'과 같다(시장 갱신만 한 새 DB).
    """
    out: dict[str, dict[str, Any]] = {}
    if not con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'etf_constituents'"
    ).fetchone():
        return out
    for t in sorted(set(tickers)):
        top = con.execute(
            "SELECT asof, source FROM etf_constituents WHERE etf_ticker = ? "
            "ORDER BY asof DESC, source ASC LIMIT 1",
            (t,),
        ).fetchone()
        if not top:
            continue
        rows = con.execute(
            "SELECT constituent_ticker, constituent_name, weight_pct, constituent_key "
            "FROM etf_constituents "
            "WHERE etf_ticker = ? AND asof = ? AND source = ? ORDER BY rank ASC LIMIT ?",
            (t, top[0], top[1], TOP_CONSTITUENTS),
        ).fetchall()
        items = []
        for ctk, cname, w, ckey in rows:
            item = {
                "ticker": ctk or None,
                "name": cname or None,
                "weight_pct": w,
                "key": ckey or None,
            }
            item["match_key"] = constituent_key(item)
            items.append(item)
        if items:
            out[t] = {"asof": top[0], "items": items}
    return out


def _empty(
    status: str, basis: str, filters: dict[str, bool], message: Optional[str]
) -> dict[str, Any]:
    return {
        "status": status,
        "message": message,
        "basis": basis,
        "filters": filters,
        "n": LIST_N,
    }


def build_summary(
    *,
    db_path: Path,
    basis: str,
    filters: dict[str, bool],
    official: Mapping[str, Mapping[str, str]],
    official_meta: dict[str, Any],
    dictionary: Optional[Mapping[str, list[str]]],
    dictionary_meta: dict[str, Any],
    held_tickers: Optional[Sequence[str]],
    holdings_status: str,
) -> dict[str, Any]:
    """요약 응답 전체. 실패도 200 응답 안의 `status` 로 돌려준다(기존 후보 API 와 같은 방식)."""
    if basis not in BASIS_DAYS:
        basis = "one_month"
    if not db_path.exists():
        return _empty("missing", basis, filters, "시장 DB 파일이 없습니다.")
    try:
        con = _ro(db_path)
        try:
            # 공통 끝일 = ETF 목록(etf_master) 종목의 저장 최신일. 같은 표에 보유 개별 주식 가격도
            # 저장되므로(보유 현재가 업데이트) 그 날짜가 끝일을 밀지 않게 ETF 행만 본다(독립 검토 HIGH).
            end = con.execute(
                "SELECT MAX(p.date) FROM etf_daily_price p "
                "JOIN etf_master m ON m.ticker = p.ticker"
            ).fetchone()[0]
            if not end:
                return _empty("empty", basis, filters, "저장된 가격이 없습니다.")
            start_from = (
                date.fromisoformat(end) - timedelta(days=THREE_MONTH_LOOKBACK_DAYS)
            ).isoformat()
            raw, names = _read(con, end, start_from)
            kodex_full = [
                PriceRow(d, c, s, fa, ch)
                for d, c, s, fa, ch in con.execute(
                    "SELECT date, close, source, fetched_at, change FROM etf_daily_price "
                    "WHERE ticker = ? AND date <= ? ORDER BY date",
                    (KODEX200_TICKER, end),
                )
            ]
            assembled = _assemble(
                end=end,
                raw=raw,
                names=names,
                kodex_full=kodex_full,
                basis=basis,
                filters=filters,
                official=official,
                dictionary=dictionary,
                held_tickers=held_tickers,
                con=con,
            )
        finally:
            con.close()
    except (sqlite3.Error, ValueError) as e:
        return _empty(
            "invalid", basis, filters, f"시장 DB 읽기 실패: {type(e).__name__}"
        )
    assembled.update(
        filters=filters,
        n=LIST_N,
        sources={"official_csv": official_meta, "dictionary": dictionary_meta},
    )
    assembled["holdings"]["status"] = holdings_status
    return assembled


def _assemble(
    *,
    end: str,
    raw: Mapping[str, list[PriceRow]],
    names: Mapping[str, Optional[str]],
    kodex_full: Sequence[PriceRow],
    basis: str,
    filters: dict[str, bool],
    official: Mapping[str, Mapping[str, str]],
    dictionary: Optional[Mapping[str, list[str]]],
    held_tickers: Optional[Sequence[str]],
    con: sqlite3.Connection,
) -> dict[str, Any]:
    kodex_valid = [(r.date, float(r.close)) for r in kodex_full if valid_close(r.close)]
    windows: dict[str, Optional[tuple[str, str]]] = {}
    for key, days in BASIS_DAYS.items():
        w = period_window(kodex_valid, end, days)
        windows[key] = (
            None
            if w is None or kodex_valid[w[1]][0] != end
            else (kodex_valid[w[0]][0], kodex_valid[w[1]][0])
        )
    common = windows[basis]
    base = {"basis": basis, "end_date": end}
    if common is None:
        return {
            **base,
            "status": "no_common_period",
            "message": "KODEX 200(069500)으로 공통 기간을 정할 수 없습니다.",
            "holdings": {"items": []},
        }

    exclude = {t for t in FILTER_TAGS if filters.get(f"exclude_{t}")}
    counts = Counter()
    population: list[dict[str, Any]] = []
    valid_by: dict[str, list[tuple[str, float]]] = {}
    # 모집단 = ETF 목록(etf_master) 종목만(기존 compute_topn 의 list_etf_tickers 와 같음).
    # 개별 주식 가격 행은 보유 연결(가격 상태)에만 쓴다.
    for tk in sorted(names):
        rows = raw.get(tk, [])
        valid = [(r.date, float(r.close)) for r in rows if valid_close(r.close)]
        valid_by[tk] = valid
        counts["universe"] += 1
        if not valid:
            counts["no_price"] += 1
            continue
        tags = classify_etf_tags(names.get(tk))
        if exclude & set(tags):
            counts["filter_excluded"] += 1
            continue
        v = period_value(valid, end, BASIS_DAYS[basis])
        if v is None:
            counts["no_return"] += 1
            continue
        if v["end"] != common[1]:
            counts["end_differs"] += 1
            continue
        if v["start"] != common[0]:
            counts["start_differs"] += 1
            continue
        population.append(
            {"ticker": tk, "name": names.get(tk), "tags": tags, "period": v}
        )
    counts["population"] = len(population)

    desc = sorted(population, key=lambda p: (-p["period"]["raw"], p["ticker"]))
    asc = sorted(population, key=lambda p: (p["period"]["raw"], p["ticker"]))
    top, bottom = desc[:LIST_N], asc[:LIST_N]
    top_set, bottom_set = {p["ticker"] for p in top}, {p["ticker"] for p in bottom}
    held = sorted(set(held_tickers or []))
    held_set = set(held)
    constituents = _read_constituents(
        con, sorted(top_set | bottom_set | (held_set & set(names)))
    )
    kodex_close = close_by_date(kodex_valid)
    kodex_dd = drawdown_of(kodex_full, kodex_valid[-1][0] if kodex_valid else None)
    kodex_dd_window = (
        (kodex_dd.get("start_date"), kodex_dd.get("end_date"))
        if kodex_dd["status"] == "ok"
        else None
    )

    def row_of(p: dict[str, Any], rank: int) -> dict[str, Any]:
        tk = p["ticker"]
        valid = valid_by[tk]
        last_raw = next((r for r in reversed(raw[tk]) if r.date == valid[-1][0]), None)
        one = criterion_from_period(
            period_value(valid, end, ONE_MONTH_LOOKBACK_DAYS), windows["one_month"]
        )
        three = criterion_from_period(
            period_value(valid, end, THREE_MONTH_LOOKBACK_DAYS), windows["three_month"]
        )
        same = {
            "status": CRIT_MISSING,
            "value": None,
            "start": one.get("start"),
            "end": one.get("end"),
            "kodex200_return_pct": None,
            "etf_return_pct": one.get("value"),
            "reason": None,
        }
        if one["status"] == CRIT_OK:
            cmp = same_period_compare(
                one["value"], one["start"], one["end"], kodex_close
            )
            if cmp["status"] == SAME_OK:
                same.update(
                    status=CRIT_OK,
                    value=cmp["diff_pctp"],
                    kodex200_return_pct=cmp["kodex200_return_pct"],
                )
            else:
                same["reason"] = cmp["reason"]
        elif one["status"] == CRIT_PERIOD_DIFFERS:
            same.update(status=CRIT_PERIOD_DIFFERS, reason="period_differs")
        else:
            same["reason"] = "no_period"
        dd = drawdown_of(raw[tk], valid[-1][0])
        if dd["status"] != "ok":
            dd_c = {"status": CRIT_MISSING, "value": None, "reason": dd.get("reason")}
        elif kodex_dd_window is None:
            # 비교 기준(069500) 창을 못 정하면 기간이 다른 게 아니라 비교할 수 없는 것이다.
            dd_c = {
                "status": CRIT_MISSING,
                "value": None,
                "reason": "kodex_window_unknown",
            }
        elif (dd.get("start_date"), dd.get("end_date")) != kodex_dd_window:
            dd_c = {
                "status": CRIT_PERIOD_DIFFERS,
                "value": dd["value_pct"],
                "reason": "period_differs",
            }
        else:
            dd_c = {"status": CRIT_OK, "value": dd["value_pct"], "reason": None}
        dd_c.update(
            start=dd.get("start_date"),
            end=dd.get("end_date"),
            peak_date=dd.get("peak_date"),
            peak_close=dd.get("peak_close"),
            close=dd.get("close"),
        )
        per = p["period"]
        return {
            "rank": rank,
            "ticker": tk,
            "name": p["name"],
            "held": tk in held_set,
            "tags": p["tags"],
            "classification": classify_etf(tk, p["name"], official, dictionary),
            "basis_return": {
                "value": round(per["raw"], 4),
                "start": per["start"],
                "end": per["end"],
                "start_close": per["start_close"],
                "end_close": per["end_close"],
            },
            "criteria": {
                "one_month": one,
                "three_month": three,
                "same_kodex_1m": same,
                "drawdown": dd_c,
            },
            "end_price": price_state(
                valid[-1][0], last_raw.fetched_at if last_raw else None
            ),
            "constituents": constituents.get(tk),
        }

    top_rows = [row_of(p, i) for i, p in enumerate(top, start=1)]
    bottom_rows = [row_of(p, i) for i, p in enumerate(bottom, start=1)]
    top_groups = build_groups(top_rows, "top", constituents)
    bottom_groups = build_groups(bottom_rows, "bottom", constituents)
    both = mark_both_sides(top_groups, bottom_groups)
    overview = {}
    for side, rows, groups in (
        ("top", top_rows, top_groups),
        ("bottom", bottom_rows, bottom_groups),
    ):
        ov = side_overview(rows, groups)
        ov["constituents_etf_count"] = sum(1 for r in rows if r["constituents"])
        overview[side] = ov

    end_states = []
    for p in population:
        rows = raw[p["ticker"]]
        last = next((r for r in reversed(rows) if r.date == common[1]), None)
        end_states.append(price_state(common[1], last.fetched_at if last else None))
    kodex_last = next((r for r in reversed(kodex_full) if r.date == end), None)
    kodex_state = price_state(end, kodex_last.fetched_at if kodex_last else None)

    pos = {p["ticker"]: i for i, p in enumerate(desc, start=1)}
    in_pop = {p["ticker"]: p for p in population}
    held_items = []
    bench_recent = read_recent_rows(con, KODEX200_TICKER)
    for tk in held:
        is_stock = tk not in names
        item: dict[str, Any] = {
            "ticker": tk,
            "is_stock": is_stock,
            "in_population": tk in in_pop,
            "out_reason": None,
            "basis_return": None,
            "side": None,
            "side_rank": None,
            "top_rank": None,
            "end_price": None,
            "has_constituents": tk in constituents,
        }
        # 가격 흐름 · 하락 판정 · 끝일 행 저장 상태 = 같은 응답 · 같은 읽기(검증자 r2 F4 · 기존 함수 재사용).
        # 개별 주식도 같은 표의 가격 행으로 만든다(모집단에는 넣지 않음).
        flow = holding_price_flow(read_recent_rows(con, tk), bench_recent)
        item["price_flow"] = flow
        item["end_price"] = flow["end_price"] if flow else None
        valid = valid_by.get(tk) or [
            (r.date, float(r.close)) for r in raw.get(tk, []) if valid_close(r.close)
        ]
        if is_stock:
            item["out_reason"] = OUT_STOCK
        elif tk in in_pop:
            per = in_pop[tk]["period"]
            item["basis_return"] = {
                "value": round(per["raw"], 4),
                "start": per["start"],
                "end": per["end"],
            }
            if tk in bottom_set:
                item.update(
                    side="bottom",
                    side_rank=next(r["rank"] for r in bottom_rows if r["ticker"] == tk),
                )
                if tk in top_set:  # 모집단 60 미만 — 상·하위 공통(검증자 r1 F3)
                    item["top_rank"] = pos[tk]
            elif tk in top_set:
                item.update(side="top", side_rank=pos[tk], top_rank=pos[tk])
        elif not valid:
            item["out_reason"] = OUT_NO_PRICE
        elif set(FILTER_TAGS) & exclude & set(classify_etf_tags(names.get(tk))):
            item["out_reason"] = OUT_FILTER
        else:
            item["out_reason"] = OUT_PERIOD
        item["exposure"] = exposure(
            tk,
            is_stock=is_stock,
            held_items=constituents.get(tk),
            side_tickers=[r["ticker"] for r in bottom_rows],
            constituents=constituents,
        )
        held_items.append(item)

    regime_ctx = compute_market_context(
        asof=kodex_valid[-1][0], kodex200_history=kodex_valid
    )
    streak = compute_regime_streak(kodex_valid)
    regime = {
        "status": regime_ctx.get("status"),
        "code": regime_ctx.get("regime_code"),
        "label": regime_ctx.get("regime_label"),
        "asof": regime_ctx.get("asof"),
        "score": regime_ctx.get("regime_score"),
        "reasons": regime_ctx.get("regime_reasons") or [],
        "streak_days": streak.get("streak_days"),
        "streak_at_least": streak.get("at_least"),
        "same_end_date": regime_ctx.get("asof") == end,
        "price": kodex_state,
    }

    return {
        **base,
        "status": "ok",
        "message": None,
        "period": {"start": common[0], "end": common[1]},
        "criteria_periods": {
            "one_month": _win(windows["one_month"]),
            "three_month": _win(windows["three_month"]),
            "drawdown": _win(kodex_dd_window),
        },
        "kodex200": {
            "basis_return_pct": round(
                (kodex_close[common[1]] / kodex_close[common[0]] - 1.0) * 100.0, 4
            ),
            "one_month_return_pct": _ret(kodex_close, windows["one_month"]),
            "three_month_return_pct": _ret(kodex_close, windows["three_month"]),
        },
        "counts": {
            "universe": counts["universe"],
            "no_price": counts["no_price"],
            "filter_excluded": counts["filter_excluded"],
            "no_return": counts["no_return"],
            "start_differs": counts["start_differs"],
            "end_differs": counts["end_differs"],
            "period_differs": counts["start_differs"] + counts["end_differs"],
            "population": counts["population"],
            "shown_top": len(top_rows),
            "shown_bottom": len(bottom_rows),
        },
        "price_state": {"end_date": common[1], **summarize_states(end_states)},
        "regime": regime,
        "top": top_rows,
        "bottom": bottom_rows,
        "in_both": sorted(top_set & bottom_set),
        "groups": {"top": top_groups, "bottom": bottom_groups},
        "overview": overview,
        "both_side_sectors": both,
        "holdings": {"items": held_items},
    }


def _win(
    w: Optional[tuple[Optional[str], Optional[str]]],
) -> Optional[dict[str, Optional[str]]]:
    return None if w is None else {"start": w[0], "end": w[1]}


def _ret(close: Mapping[str, float], w: Optional[tuple[str, str]]) -> Optional[float]:
    if w is None or w[0] not in close or w[1] not in close:
        return None
    return round((close[w[1]] / close[w[0]] - 1.0) * 100.0, 4)
