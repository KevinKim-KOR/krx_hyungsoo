"""POC6-30 — 섹터요약 보강 대조(1개월 상위 30 · 구성종목) 계산.

PLAN `docs/ai_plan/POC6/POC6_30_SECTOR_SUMMARY_CONSTITUENTS_PLAN_V1.md` §3 S4 ·
판정 `docs/ai_design/POC6/POC6_30_SECTOR_SUMMARY_CONSTITUENTS_PLAN_DECISION_2026-11-14.md` Q2 ~ Q5.

- DB 는 호출자가 연 읽기 전용 연결로만 읽는다. 외부 호출 · 쓰기 없음.
- 대조 2 는 기존 운영 함수(`_read_constituents` · `build_groups` · `side_overview`)를 고치지 않고 다시 부른다.
- 구성 행 종류(판정 Q4): 원본 순위 1 ~ 10행 · 주식으로 확인된 행만 반복 주식 · 업종 해석에 쓴다.
- 지수 계열(판정 Q2): 공식 기초지수명이 같으면 한 계열 · 판정이 확인한 계열만 이 표본에서 합친다.
- 업종(판정 Q3): 사업군으로 분류된 ETF 편입 사실은 '사업군 ETF 편입 근거'일 뿐 · 해석은 늘 가설.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from typing import Any, Mapping, Optional, Sequence

from app.pc_etf_compare_groups import (
    CONS_NO_OVERLAP,
    CONS_OK,
    TOP_CONSTITUENTS,
    build_groups,
    classify_etf,
    constituent_key,
    side_overview,
)

# 행 종류 판정은 운영 공통 모듈로 옮겼다(POC6-31 PLAN 판정 Q8 (a)) — 이 연구 모듈은 그것을 가져다 쓴다.
from app.constituent_row_kind import (  # noqa: F401 — 연구 스크립트 · 시험이 C.<이름> 으로 쓴다
    BOND,
    CASH,
    CASH_ISIN,
    DERIVATIVE,
    DOMESTIC_ETF,
    DOMESTIC_STOCK,
    ETF_WORD,
    FOREIGN_ETF,
    FOREIGN_STOCK,
    FUND_WORDS,
    ISIN_SHAPE,
    KIND_LABEL,
    STOCK_KINDS,
    UNKNOWN,
    row_kind,
)
from app.pc_etf_compare_summary import _read_constituents

TOP_ROWS = (
    TOP_CONSTITUENTS  # 판정 Q4 '원본 순위 1 ~ 10행' = 기존 공통 구성종목 범위와 같은 값
)
# 판정 Q2 — 이 표본에서만 합치는 계열(같은 기초지수를 쓴다는 근거를 판정이 확인한 것만).
SAMPLE_FAMILIES: dict[str, str] = {
    "446720": "Dow Jones U.S. Dividend 100 계열",
    "483290": "Dow Jones U.S. Dividend 100 계열",
    "458760": "Dow Jones U.S. Dividend 100 계열",
    "458750": "Dow Jones U.S. Dividend 100 계열",
}


def family_of(ticker: str, index_name: Optional[str]) -> Optional[str]:
    """지수 계열 — 판정 계열 → 공식 기초지수명 → 없으면 None(계열 미확인)."""
    if ticker in SAMPLE_FAMILIES:
        return SAMPLE_FAMILIES[ticker]
    return index_name or None


def read_latest_rows(
    con: sqlite3.Connection, tickers: Sequence[str]
) -> dict[str, dict[str, Any]]:
    """ETF마다 최신 기준일 · 첫 출처(운영 `_read_constituents` 와 같은 선택)의 저장 행 전체와 1 ~ 10행."""
    out: dict[str, dict[str, Any]] = {}
    for t in sorted(set(tickers)):
        top = con.execute(
            "SELECT asof, source FROM etf_constituents WHERE etf_ticker = ? "
            "ORDER BY asof DESC, source ASC LIMIT 1",
            (t,),
        ).fetchone()
        if not top:
            continue
        raw = con.execute(
            "SELECT rank, constituent_ticker, constituent_name, weight_pct, constituent_key, "
            "constituent_isin, constituent_reuters_code, market_type, created_at "
            "FROM etf_constituents WHERE etf_ticker = ? AND asof = ? AND source = ? "
            "ORDER BY rank ASC",
            (t, top[0], top[1]),
        ).fetchall()
        rows = [
            {
                "rank": r[0],
                "ticker": r[1] or None,
                "name": r[2] or None,
                "weight_pct": r[3],
                "key": r[4] or None,
                "isin": r[5] or None,
                "reuters": r[6] or None,
                "market_type": r[7],
                "created_at": r[8],
            }
            for r in raw
        ]
        for row in rows:
            row["match_key"] = constituent_key(row)
        out[t] = {
            "asof": top[0],
            "source": top[1],
            "stored_count": len(rows),
            "created_at": max((r["created_at"] for r in rows), default=None),
            "top": [r for r in rows if r["rank"] <= TOP_ROWS],
        }
    return out


def comparison_two(
    con: sqlite3.Connection,
    frozen_rows: Sequence[Mapping[str, Any]],
    kind_by_key: Mapping[str, str],
    both_side_sectors: Sequence[str] = (),
) -> dict[str, Any]:
    """대조 2 — 같은 30행 · 같은 분류 + 지금 연결의 구성 자료 → 기존 함수 그대로 · 주식 외 공통 항목 표시.

    '상·하위 공통 업종' 표시는 하위 목록이 있어야 정해지므로 보관 응답의 `both_side_sectors` 를 받아
    `mark_both_sides` 와 같은 규칙(업종 묶음 이름이 같으면)으로 붙인다.
    """
    cons = _read_constituents(con, [r["ticker"] for r in frozen_rows])
    rows = [{**r, "constituents": cons.get(r["ticker"])} for r in frozen_rows]
    groups = build_groups(rows, "top", cons)
    for g in groups:
        if g["kind"] == "sector" and g["name"] in set(both_side_sectors):
            g["both_sides"] = True
    overview = side_overview(rows, groups)
    overview["constituents_etf_count"] = sum(1 for r in rows if r["constituents"])
    flagged = []
    for g in groups:
        for c in g["constituents"]["common"]:
            kind = kind_by_key.get(c["key"], UNKNOWN)
            c["kind"] = kind
            if kind not in STOCK_KINDS:
                flagged.append({"group": g["name"], "name": c["name"], "kind": kind})
    return {"groups": groups, "overview": overview, "non_stock_common": flagged}


def group_scope(groups: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """공통 구성종목을 실제로 비교한 묶음(기존 `common_constituents` 상태 = 구성 자료 ETF 2개 이상).

    비교를 못 한 묶음(자료 없음 · 1개뿐 · 상태 칸 없음)의 빈 목록을 '0건'으로 세지 않기 위해(검증자 r1 F4 같은 종류).
    """
    done = [
        g
        for g in groups
        if (g.get("constituents") or {}).get("status") in (CONS_OK, CONS_NO_OVERLAP)
    ]
    return {
        "groups": len(groups),
        "compared": len(done),
        "common": sum(len(g["constituents"]["common"]) for g in done),
    }


def comparison_three(
    frozen_rows: Sequence[Mapping[str, Any]],
    latest: Mapping[str, Mapping[str, Any]],
    etf_tickers: set[str],
    visible_keys: set[str],
) -> list[dict[str, Any]]:
    """대조 3 — 주식 행만 · 서로 다른 확인 계열 2개 이상에 든 주식(계열 미확인은 세지 않음)."""
    entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    names: dict[str, str] = {}
    for r in frozen_rows:
        data = latest.get(r["ticker"])
        if not data:
            continue
        fam = family_of(r["ticker"], r["classification"].get("index_name"))
        for row in data["top"]:
            k = row["match_key"]
            if k is None or row_kind(row, etf_tickers) not in STOCK_KINDS:
                continue
            names.setdefault(k, row["name"] or k)
            entries[k].append(
                {
                    "etf": r["ticker"],
                    "etf_name": r.get("name"),
                    "selection_rank": r["rank"],
                    "family": fam,
                    "index_name": r["classification"].get("index_name"),
                    "strategy": bool(r["classification"].get("strategy")),
                    "rank": row["rank"],
                    "weight_pct": row["weight_pct"],
                    "asof": data["asof"],
                }
            )
    out = []
    for k, es in entries.items():
        fams = sorted({e["family"] for e in es if e["family"]})
        if len(fams) < 2:
            continue
        out.append(
            {
                "key": k,
                "name": names[k],
                "families": fams,
                "family_count": len(fams),
                "etf_count": len({e["etf"] for e in es}),
                "max_weight_pct": max((e["weight_pct"] or 0.0) for e in es),
                "already_visible": k in visible_keys,
                "entries": sorted(es, key=lambda e: e["selection_rank"]),
            }
        )
    out.sort(
        key=lambda x: (
            -x["family_count"],
            -x["etf_count"],
            -x["max_weight_pct"],
            x["name"],
        )
    )
    return out


def comparison_three_scope(
    frozen_rows: Sequence[Mapping[str, Any]],
    latest: Mapping[str, Mapping[str, Any]],
    etf_tickers: set[str],
) -> dict[str, Any]:
    """대조 3 을 할 수 있었는지(검증자 r1 F3) — 주식 행이 있는 ETF 의 확인된 계열이 2개 이상이어야 한다."""
    fams: set[str] = set()
    with_stock = unconfirmed = 0
    for r in frozen_rows:
        data = latest.get(r["ticker"])
        if not data or not any(
            row["match_key"] is not None and row_kind(row, etf_tickers) in STOCK_KINDS
            for row in data["top"]
        ):
            continue
        with_stock += 1
        fam = family_of(r["ticker"], r["classification"].get("index_name"))
        if fam:
            fams.add(fam)
        else:
            unconfirmed += 1
    return {
        "etf_with_stock_rows": with_stock,
        "family_count": len(fams),
        "unconfirmed_etfs": unconfirmed,
        "comparable": len(fams) >= 2,
    }


def _top_two_stocks(
    data: Mapping[str, Any], etf_tickers: set[str]
) -> list[Mapping[str, Any]]:
    """원본 1 ~ 10행 중 주식 행의 앞 두 행(원본 순위 순) = 비중 1 · 2위 주식."""
    rows = [
        row
        for row in data["top"]
        if row["match_key"] is not None and row_kind(row, etf_tickers) in STOCK_KINDS
    ]
    return rows[:2]


def lead_case(
    frozen_rows: Sequence[Mapping[str, Any]],
    latest: Mapping[str, Mapping[str, Any]],
    etf_tickers: set[str],
) -> Optional[dict[str, Any]]:
    """대조표 첫 줄 사례 — 비중 1 · 2위 주식이 같은 ETF 묶음(설계자 검토 2026-11-14 §1).

    두 주식이 같은 ETF 를 한 묶음으로 모은다. 서로 다른 확인 계열이 2개 이상인 묶음만 사례가 된다
    (같은 지수를 따르는 ETF 끼리의 겹침은 지금 요약에서도 보인다).
    고르는 순서: ETF 수가 많은 묶음 → 두 종목 합산 비중의 가장 작은 값이 큰 묶음 → 주식 키 순.
    비중이 비었거나 두 행이 같은 주식이면 합산을 말할 수 없어 그 ETF 는 넣지 않는다.
    """
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    names: dict[str, str] = {}
    holds: dict[str, dict[str, Any]] = {}  # ETF → {주식 키: 비중}(1 ~ 10행 주식 행)
    for r in frozen_rows:
        data = latest.get(r["ticker"])
        if not data:
            continue
        held: dict[str, Any] = {}
        for row in data["top"]:  # 원본 순위 순 · 같은 주식이 두 번이면 앞 행
            if (
                row["match_key"] is not None
                and row_kind(row, etf_tickers) in STOCK_KINDS
            ):
                held.setdefault(row["match_key"], row["weight_pct"])
        holds[r["ticker"]] = held
        two = _top_two_stocks(data, etf_tickers)
        if len(two) < 2 or two[0]["match_key"] == two[1]["match_key"]:
            continue
        if any(s["weight_pct"] is None for s in two):
            continue
        for s in two:
            names.setdefault(s["match_key"], s["name"] or s["match_key"])
        pair = tuple(sorted(s["match_key"] for s in two))
        groups[(pair[0], pair[1])].append(
            {
                "etf": r["ticker"],
                "etf_name": r.get("name"),
                "selection_rank": r["rank"],
                "family": family_of(r["ticker"], r["classification"].get("index_name")),
                "asof": data["asof"],
                "weights": {s["match_key"]: s["weight_pct"] for s in two},
                "sum_pct": round(two[0]["weight_pct"] + two[1]["weight_pct"], 2),
            }
        )
    found = []
    for pair, es in groups.items():
        fams = {e["family"] for e in es if e["family"]}
        if len(fams) < 2:  # 계열 2개 이상이면 ETF 도 2개 이상
            continue
        sums = [e["sum_pct"] for e in es]
        total = {k: sum(e["weights"][k] for e in es) for k in pair}
        order = sorted(pair, key=lambda k: (-total[k], k))
        found.append(
            {
                "pair": list(pair),
                "stocks": [{"key": k, "name": names[k]} for k in order],
                "etfs": sorted(es, key=lambda e: e["selection_rank"]),
                "family_count": len(fams),
                "sum_min": min(sums),
                "sum_max": max(sums),
                "asofs": sorted({e["asof"] for e in es}),
            }
        )
    if not found:
        return None
    found.sort(key=lambda g: (-len(g["etfs"]), -g["sum_min"], g["pair"]))
    case = found[0]
    inside = {e["etf"] for e in case["etfs"]}
    also = []
    for r in frozen_rows:
        w = holds.get(r["ticker"], {})
        if r["ticker"] in inside or not all(k in w for k in case["pair"]):
            continue
        ws = [w[k] for k in case["pair"]]
        also.append(
            {
                "etf": r["ticker"],
                "etf_name": r.get("name"),
                "selection_rank": r["rank"],
                "sum_pct": (
                    None if any(x is None for x in ws) else round(ws[0] + ws[1], 2)
                ),
            }
        )
    case["also_held"] = also
    case["other_groups"] = [
        {
            "stocks": [s["name"] for s in g["stocks"]],
            "etf_count": len(g["etfs"]),
            "sum_min": g["sum_min"],
            "sum_max": g["sum_max"],
        }
        for g in found[1:]
    ]
    return case


def sector_evidence(
    latest_all: Mapping[str, Mapping[str, Any]],
    keys: set[str],
    official: Mapping[str, Mapping[str, str]],
    dictionary: Optional[Mapping[str, list[str]]],
    etf_names: Mapping[str, str],
) -> dict[str, list[dict[str, Any]]]:
    """판정 Q3 — 사업군으로 분류된 ETF(구성 자료가 있는 모든 ETF)의 1 ~ 10행에 든 사실만 모은다."""
    ev: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t, data, sector in _sector_etfs(latest_all, official, dictionary, etf_names):
        for row in data["top"]:
            if row["match_key"] in keys:
                ev[row["match_key"]].append(
                    {
                        "etf": t,
                        "etf_name": etf_names.get(t),
                        "sector": sector,
                        "asof": data["asof"],
                    }
                )
    return {k: sorted(v, key=lambda e: (e["sector"], e["etf"])) for k, v in ev.items()}


def _sector_etfs(
    latest_all: Mapping[str, Mapping[str, Any]],
    official: Mapping[str, Mapping[str, str]],
    dictionary: Optional[Mapping[str, list[str]]],
    etf_names: Mapping[str, str],
) -> list[tuple[str, Mapping[str, Any], str]]:
    """구성 자료가 있는 ETF 중 사업군으로 분류되는 것 — 근거 계산과 범위 계산이 같은 목록을 쓴다."""
    out = []
    for t, data in latest_all.items():
        sector = classify_etf(t, etf_names.get(t), official, dictionary)["sector"]
        if sector:
            out.append((t, data, sector))
    return out


def sector_evidence_scope(
    latest_all: Mapping[str, Mapping[str, Any]],
    official: Mapping[str, Mapping[str, str]],
    dictionary: Optional[Mapping[str, list[str]]],
    etf_names: Mapping[str, str],
) -> dict[str, int]:
    """근거를 찾아본 범위 — 0개면 '편입 이력 없음'이 아니라 확인 못 함(검증자 r1 F4 같은 종류 · r1 정정 검토)."""
    found = _sector_etfs(latest_all, official, dictionary, etf_names)
    return {"sector_etfs": len(found), "sectors": len({s for _, _, s in found})}


# 수집 기능의 ETF별 상태(`RefreshItemResult.status`) → 확인 범위 상태(검증자 r1 F2).
# 공급자를 부른 결과(받음 · 실패)와 부르지 않은 것(시간 초과 · 요청 안 함)을 나눈다.
NOT_OK_STATE = {"unavailable": "failed", "skipped_timeout": "timeout", None: "missing"}


def collect_state(status: Optional[str], from_cache: bool, data: Any) -> str:
    """자료가 남아 있으면 'old_…'(예전 자료) · 받았다는 기록인데 저장 자료가 없으면 'inconsistent'."""
    if status == "ok":
        if data is None:
            return "inconsistent"
        return "cached" if from_cache else "new"
    base = NOT_OK_STATE.get(status, "unknown")
    return base if data is None else f"old_{base}"


def coverage(
    frozen_rows: Sequence[Mapping[str, Any]],
    latest: Mapping[str, Mapping[str, Any]],
    collected: Mapping[str, Mapping[str, Any]],
    etf_tickers: set[str],
    ranking_end: str,
) -> list[dict[str, Any]]:
    """ETF별 확인 범위 — 수집 결과 · 원천 기준일 · 조회 시각 · 행 종류 · 원본 비중 합 · 주식 비중 합."""
    out = []
    for r in frozen_rows:
        t = r["ticker"]
        data = latest.get(t)
        got = collected.get(t, {})
        kinds: dict[str, int] = defaultdict(int)
        raw_sum = stock_sum = 0.0
        for row in (data or {}).get("top", []):
            k = row_kind(row, etf_tickers)
            kinds[k] += 1
            w = row["weight_pct"] or 0.0
            raw_sum += w
            if k in STOCK_KINDS:
                stock_sum += w
        state = collect_state(got.get("status"), bool(got.get("from_cache")), data)
        out.append(
            {
                "ticker": t,
                "name": r.get("name"),
                "selection_rank": r["rank"],
                "state": state,
                "has_data": data is not None,
                "collect_status": got.get("status"),
                "collect_message": got.get("message"),
                "asof": data["asof"] if data else None,
                "after_ranking_end": bool(data and data["asof"] > ranking_end),
                "on_ranking_end": bool(data and data["asof"] == ranking_end),
                "saved_asof": got.get("saved_asof"),
                "fetched_at": data["created_at"] if data else None,
                "stored_count": data["stored_count"] if data else 0,
                "top_count": len((data or {}).get("top", [])),
                "kinds": dict(kinds),
                "raw_weight_sum": round(raw_sum, 2) if data else None,
                "stock_weight_sum": round(stock_sum, 2) if data else None,
            }
        )
    return out
