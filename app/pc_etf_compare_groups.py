"""POC6-28 — 「ETF 비교하기」 묶음 · 분류 · 공통 구성종목 · 노출(순수 계산 · 조회 없음).

PLAN `docs/ai_plan/POC6/POC6_28_ETF_COMPARISON_SECTOR_AND_HOLDINGS_PLAN_V1.md` §3-2 ~ §3-4 · 판정 §3.

- 분류는 기존 확인 자료만 쓴다(판정 Q0 (a) · ASSUMPTIONS Q4 한정): 공식 기준정보 CSV 의 기초지수명 ·
  기초시장분류 · 기초자산분류와 기존 사업군 사전의 일치(`classify`). 새 낱말 · 추정 분류를 만들지 않는다.
- 한 ETF = 한 묶음: 업종(사업군 일치) → 기초지수별 → 미분류(공식 CSV 에 없음).
  광의 시장지수(완전일치)는 업종이 아니다. 커버드콜 등 전략형은 같은 규칙으로 묶고 `strategy` 로 따로 적는다.
- 공통 구성종목 · 노출은 `constituent_key`(해외 종목은 종목코드 칸이 비어 있음)로 대조한다.
  키가 비면 종목코드 → 이름 순으로 대신한다. 같은 ETF끼리는 비교하지 않는다.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping, Optional, Sequence

from app.intraday_config.selector import BROAD_INDEX_NAMES, STRATEGY_PATTERN, classify

KIND_SECTOR = "sector"
KIND_INDEX = "index"
KIND_UNCLASSIFIED = "unclassified"

TOP_CONSTITUENTS = 10  # 묶음 · 노출 대조 범위 = 각 ETF 최신 기준일의 비중 상위 10종목

CONS_NO_SAMPLE = "no_sample"  # 구성 자료 있는 ETF 0개
CONS_SINGLE = "single"  # 1개뿐 — 공통 비교 불가
CONS_NO_OVERLAP = "no_overlap"  # 2개 이상인데 2개 이상에 나온 종목 없음
CONS_OK = "ok"

EXPO_OK = "ok"  # 겹친 종목 있음
EXPO_NONE = "none"  # 비교했으나 겹침 0건
EXPO_NO_CONSTITUENTS = "no_constituents"  # 보유 ETF 구성 자료 없음
EXPO_NO_SAMPLE = "no_sample"  # 비교할 하위 ETF 구성 자료 없음


def constituent_key(row: Mapping[str, Any]) -> Optional[str]:
    """대조 키 — `constituent_key` → 종목코드 → 이름. 셋 다 비면 None(대조에서 뺀다)."""
    for field, prefix in (("key", ""), ("ticker", "T:"), ("name", "N:")):
        v = row.get(field)
        if isinstance(v, str) and v.strip():
            return prefix + v.strip()
    return None


def classify_etf(
    ticker: str,
    name: Optional[str],
    official: Mapping[str, Mapping[str, str]],
    dictionary: Optional[Mapping[str, list[str]]],
) -> dict[str, Any]:
    """ETF 하나의 분류 사실. `dictionary` 가 None 이면(사전 읽기 실패) 업종 묶음 없이 지수별로만 묶는다."""
    row = official.get(ticker)
    if row is None:
        return {
            "kind": KIND_UNCLASSIFIED,
            "sector": None,
            "index_name": None,
            "market": None,
            "asset": None,
            "strategy": bool(name and STRATEGY_PATTERN.search(name)),
            "broad": False,
        }
    index_name = (row.get("기초지수명") or "").strip() or None
    broad = index_name in BROAD_INDEX_NAMES if index_name else False
    strategy = bool(
        (index_name and STRATEGY_PATTERN.search(index_name))
        or (name and STRATEGY_PATTERN.search(name))
    )
    sector = None
    if index_name and not broad and dictionary is not None:
        sector = classify(index_name, dict(dictionary))
    return {
        "kind": KIND_SECTOR if sector else KIND_INDEX,
        "sector": sector,
        "index_name": index_name,
        "market": (row.get("기초시장분류") or "").strip() or None,
        "asset": (row.get("기초자산분류") or "").strip() or None,
        "strategy": strategy,
        "broad": broad,
    }


def _group_key(c: Mapping[str, Any]) -> tuple[str, Optional[str]]:
    if c["kind"] == KIND_SECTOR:
        return (KIND_SECTOR, c["sector"])
    if c["kind"] == KIND_INDEX and c["index_name"]:
        return (KIND_INDEX, c["index_name"])
    return (KIND_UNCLASSIFIED, None)


def common_constituents(
    tickers: Sequence[str], constituents: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """묶음 안 구성 자료 있는 ETF만으로 2개 이상 ETF에 나온 종목(많이 나온 순 · 같으면 이름 순)."""
    have = [t for t in tickers if t in constituents]
    asofs = sorted({constituents[t]["asof"] for t in have})
    out: dict[str, Any] = {
        "etf_with_data": len(have),
        "etf_total": len(tickers),
        "asof_min": asofs[0] if asofs else None,
        "asof_max": asofs[-1] if asofs else None,
        "top_n": TOP_CONSTITUENTS,
        "common": [],
    }
    if not have:
        out["status"] = CONS_NO_SAMPLE
        return out
    if len(have) == 1:
        out["status"] = CONS_SINGLE
        return out
    count: Counter[str] = Counter()
    names: dict[str, str] = {}
    for t in have:
        seen: set[str] = set()
        for item in constituents[t]["items"]:
            k = item["match_key"]
            if k is None or k in seen:
                continue
            seen.add(k)
            count[k] += 1
            names.setdefault(k, item.get("name") or k)
    common = [k for k, n in count.items() if n >= 2]
    common.sort(key=lambda k: (-count[k], names[k]))
    out["common"] = [
        {"key": k, "name": names[k], "etf_count": count[k]} for k in common
    ]
    out["status"] = CONS_OK if common else CONS_NO_OVERLAP
    return out


def build_groups(
    rows: Sequence[Mapping[str, Any]],
    side: str,
    constituents: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """한 쪽(상위 · 하위) 목록 → 묶음. `rows` 는 선정 순서(수익률 순)다.

    순서: ETF 수가 많은 순 → 같으면 상위는 묶음 최고 수익률이 높은 순, 하위는 최저 수익률이 낮은 순.
    """
    buckets: dict[tuple[str, Optional[str]], list[Mapping[str, Any]]] = defaultdict(
        list
    )
    for r in rows:
        buckets[_group_key(r["classification"])].append(r)
    groups: list[dict[str, Any]] = []
    for (kind, name), members in buckets.items():
        rets = [m["basis_return"]["value"] for m in members]
        markets = Counter(m["classification"]["market"] or "확인 불가" for m in members)
        assets = Counter(m["classification"]["asset"] or "확인 불가" for m in members)
        tickers = [m["ticker"] for m in members]
        groups.append(
            {
                "kind": kind,
                "name": name,
                "etf_count": len(members),
                "distinct_index_count": len(
                    {
                        m["classification"]["index_name"]
                        for m in members
                        if m["classification"]["index_name"]
                    }
                ),
                "tickers": tickers,
                "return_min": min(rets),
                "return_max": max(rets),
                "markets": dict(markets),
                "assets": dict(assets),
                "strategy_count": sum(
                    1 for m in members if m["classification"]["strategy"]
                ),
                "held_count": sum(1 for m in members if m.get("held")),
                "both_sides": False,
                "constituents": common_constituents(tickers, constituents),
            }
        )
    if side == "top":
        groups.sort(key=lambda g: (-g["etf_count"], -g["return_max"]))
    else:
        groups.sort(key=lambda g: (-g["etf_count"], g["return_min"]))
    return groups


def mark_both_sides(
    top: list[dict[str, Any]], bottom: list[dict[str, Any]]
) -> list[str]:
    """같은 업종이 상·하위 양쪽에 있으면 두 묶음에 표시하고 이름 목록을 돌려준다."""
    names = {g["name"] for g in top if g["kind"] == KIND_SECTOR} & {
        g["name"] for g in bottom if g["kind"] == KIND_SECTOR
    }
    for g in top + bottom:
        if g["kind"] == KIND_SECTOR and g["name"] in names:
            g["both_sides"] = True
    return sorted(names)


def side_overview(
    rows: Sequence[Mapping[str, Any]], groups: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """카드 첫 두 줄 — 공식 기초시장 · 자산 구성 · 사업군 분류 수 · 공통 업종 확인 가능 여부."""
    mix = Counter(
        (
            r["classification"]["market"] or "확인 불가",
            r["classification"]["asset"] or "확인 불가",
        )
        for r in rows
        if r["classification"]["kind"] != KIND_UNCLASSIFIED
    )
    unclassified = sum(
        1 for r in rows if r["classification"]["kind"] == KIND_UNCLASSIFIED
    )
    sector_etfs = sum(1 for r in rows if r["classification"]["kind"] == KIND_SECTOR)
    repeated = [g for g in groups if g["kind"] == KIND_SECTOR and g["etf_count"] >= 2]
    return {
        "mix": [
            {"market": m, "asset": a, "count": n}
            for (m, a), n in sorted(mix.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "unclassified_count": unclassified,
        "sector_etf_count": sector_etfs,
        "total": len(rows),
        "repeated_sector_count": len(repeated),
        "index_group_count": sum(1 for g in groups if g["kind"] == KIND_INDEX),
        "constituents_etf_count": None,  # 호출자가 채운다
    }


def exposure(
    held_ticker: str,
    *,
    is_stock: bool,
    held_items: Optional[Mapping[str, Any]],
    side_tickers: Iterable[str],
    constituents: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """보유 한 종목과 한 쪽(하위) 목록 ETF 구성종목의 겹침(노출 확인).

    - ETF 보유: 보유 ETF 구성 상위 10 ∩ 목록 ETF 구성 상위 10(같은 ETF끼리는 비교하지 않음).
    - 개별 주식 보유: 그 종목코드가 목록 ETF 구성 상위 10 안에 있는가.
    """
    compared = [t for t in side_tickers if t != held_ticker and t in constituents]
    asofs = sorted({constituents[t]["asof"] for t in compared})
    base: dict[str, Any] = {
        "compared_etf_count": len(compared),
        "compared_asof_min": asofs[0] if asofs else None,
        "compared_asof_max": asofs[-1] if asofs else None,
        "holding_asof": None,
        "overlaps": [],
        "top_n": TOP_CONSTITUENTS,
    }
    if is_stock:
        mine = {held_ticker: held_ticker}
    else:
        if held_items is None:
            return {**base, "status": EXPO_NO_CONSTITUENTS}
        base["holding_asof"] = held_items["asof"]
        mine = {
            i["match_key"]: (i.get("name") or i["match_key"])
            for i in held_items["items"]
            if i["match_key"] is not None
        }
    if not compared:
        return {**base, "status": EXPO_NO_SAMPLE}
    hits: dict[str, dict[str, Any]] = {}
    for t in compared:
        for item in constituents[t]["items"]:
            k = item["match_key"]
            if is_stock:
                # 개별 주식은 종목코드 · 대조 키 어느 쪽으로든 같은 코드면 같은 종목이다.
                hit = item.get("ticker") == held_ticker or k == held_ticker
                key = held_ticker if hit else None
            else:
                hit = k is not None and k in mine
                key = k if hit else None
            if not hit or key is None:
                continue
            h = hits.setdefault(
                key, {"key": key, "name": item.get("name") or key, "etfs": []}
            )
            if t not in h["etfs"]:
                h["etfs"].append(t)
    overlaps = sorted(hits.values(), key=lambda h: (-len(h["etfs"]), h["name"]))
    return {**base, "overlaps": overlaps, "status": EXPO_OK if overlaps else EXPO_NONE}
