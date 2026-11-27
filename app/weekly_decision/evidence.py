"""한 후보의 화면 · 복사문 자료 조립(PLAN §2 · 판정 §2 · Q3 · Q5 · Q7) — 문장은 lines 가 만든다.

```text
한 후보   compose(ctx, ticker) = 화면과 복사문이 같이 쓰는 자료(숫자 · 날짜는 여기서 한 번 정함)
          · 검토 시점(cutoff) 필터를 한 번만 적용 — 지난 네 주 · 지난 검토와 비교 · 이 ETF 의 지난 판단 목록이 같은 결과를 씀
① 근거    같은 지수 상품(peers) · 지난 검토와 비교(Q7 순서) · 자료 공백 한 가지(Q3)
② AI      질문 한 가지 — 같은 지수 상품과 방향이 다름 → 해외 지수(현지 통화) → 국내 지수(지수 자체)
          · 안내는 지수부터 · 차이를 설명할 필요가 있을 때만 환율 · 보수 등(V2 판정 Q5) · 이 묶음에 없는 값(Q3)
흐름      지난 네 주 그래프 자료(flow.flow)
구성      구성 · 겹침(로컬 화면만 · 복사문에 넣지 않음)
```
"""

from __future__ import annotations

import datetime as dt
from datetime import datetime
import sqlite3
from typing import Any, Callable, Mapping, Optional

from app.constituents_pair_exposure import condition_of
from app.weekly_decision import flow as FL
from app.weekly_decision import history as H
from app.weekly_decision import peers as P
from app.weekly_decision import records as R
from app.weekly_decision.lines import (
    PRICE_STATE,
    SCREEN,
    copy_text,
    md,
    pct,
    same_filters,
    sign_of,
    topic,
    why,
)


def composition(
    reader: Callable[[str, Mapping[str, Any]], Mapping[str, Any]],
    item: Mapping[str, Any],
    filters: Mapping[str, bool],
) -> dict[str, Any]:
    """구성 · 겹침(펼침 · 로컬 화면만) — 저장 상위 구성의 비중 합 · 확인된 중복 주식 수."""
    cond = condition_of(
        screen=SCREEN,
        basis="one_month",
        side=None,
        rank=item["rank"],
        start_date=item["one_month"]["start"],
        end_date=item["one_month"]["end"],
        filters=dict(filters),
    )
    try:
        got = reader(item["ticker"], cond)
    except (sqlite3.Error, OSError, ValueError, KeyError):
        return {"state": "error"}
    cons = got.get("constituents") or {}
    if not isinstance(cons, dict) or cons.get("state") == "error":
        return {"state": "error"}
    rows = [r for r in (cons.get("rows") or []) if isinstance(r, dict)]
    ws = [R.num_or_none(r.get("weight_pct")) for r in rows]
    known = [w for w in ws if w is not None]
    exp = got.get("exposure") or {}
    stocks = exp.get("stocks")
    overlap = None
    if (
        not got.get("exposure_error")
        and exp.get("status") == "ok"
        and isinstance(stocks, list)
    ):
        ok = [s for s in stocks if isinstance(s, dict)]

        def ex(s: Mapping[str, Any]) -> Mapping[str, Any]:
            e = s.get("exposure")
            return e if isinstance(e, dict) else {}

        hits = [s.get("name") for s in ok if ex(s).get("terms") or ex(s).get("direct")]
        other = [
            s.get("name")
            for s in ok
            if s.get("reference") and s.get("name") not in hits
        ]
        overlap = {"checked": len(stocks), "hits": hits, "other_date": other}
    return {
        "state": "ok" if rows else "none",
        "coverage": cons.get("state"),
        "asof": R.sane_date(cons.get("asof")),
        "rows": len(rows),
        "weight": sum(known) if known else None,
        "weight_missing": len(ws) - len(known),
        "top": [r.get("name") for r in rows[:3]],
        "overlap": overlap,
    }


def _saved_key(r: Mapping[str, Any]) -> datetime:
    """내 판단 기록의 저장 시각(정렬용) — 못 읽으면 가장 앞."""
    return R.sane_time(r.get("saved_at")) or datetime.min.replace(tzinfo=R.KST)


def _previous(
    ctx: H.Context,
    ticker: str,
    records: list[Mapping[str, Any]],
    reviews: list[Mapping[str, Any]],
    weeks: Mapping[str, Any],
) -> Optional[dict[str, Any]]:
    """Q7 — POC7-04 내 판단 기록 → 비교 가능한 AI 세션 기록 → 직전 완료 주 복원."""
    mine = sorted(
        (
            rv
            for rv in reviews
            if rv.get("ticker") == ticker and rv.get("end") and rv["end"] <= ctx.end
        ),
        # 글자 순 말고 시각 순(표기가 달라도) · 같은 시각이면 기록 번호 — 「이 ETF 의 지난 판단」과 같은 순서(반박 검토 D1)
        key=lambda r: (_saved_key(r), str(r.get("review_id") or "")),
    )
    if mine:
        rv = mine[-1]
        return {
            "kind": "review",
            "review": dict(rv),
            "same_filters": same_filters(rv.get("filters") or {}, ctx.filters),
        }
    got = H.latest_comparable(records, ctx.end, ticker)
    if got:
        rec, e = got["record"], got["entry"]
        chk = H.reconcile(ctx, rec, e)
        return {
            "kind": "session",
            "record_id": rec["id"],
            "asof": rec["asof"],
            "source": rec["source"],
            "rank": e["rank"],
            "one_month": {
                "value": e["one_month"],
                "start": e["start"],
                "end": e["end"],
            },
            "filters": dict(rec["filters"]),
            "same_filters": same_filters(rec["filters"], ctx.filters),
            # 같은 조건 판정 = 복사문 인용과 같은 판정(제외 조건 + 다시 계산 · 반박 검토 D1)
            "cite_why": H.cite_judge(rec, e, ctx.filters, chk),
            "verdict": rec["verdict"],
            "verdict_state": H.verdict_state(rec),
            "memo": bool(rec["memo"].strip()),
            "check": chk,
        }
    rows = weeks.get("rows") or []
    if rows:
        return {"kind": "restore", "date": rows[-1]["date"], "seen": rows[-1]["seen"]}
    return None


def _gap(rv: Mapping[str, Any]) -> dict[str, str]:
    """판단에 영향을 주는 자료 공백 한 가지(Q3) — text = 화면(로컬) · copy = 외부 복사문(로컬 상태 없이)."""
    g = _gap_text(rv)
    return {**g, "copy": g.get("copy", g["text"])}


def _gap_text(rv: Mapping[str, Any]) -> dict[str, str]:
    peer = rv["peer"]
    if peer["state"] == "official_unread":
        # 못 읽은 것을 '없다'고 단정하지 않음 · 복사문에는 로컬 파일 상태 없이(공개 자료 한정 · 검증 F17 과 같은 종류)
        return {
            "kind": "no_official",
            "text": "공식 기준정보를 읽지 못해 이 ETF 의 기초지수와 상품 구조를 확인하지 못했습니다.",
            "copy": "이 묶음에는 이 ETF 의 기초지수와 상품 구조가 없습니다.",
        }
    if peer["state"] != "ok":
        return {
            "kind": "no_official",
            "text": "공식 기준정보에 이 ETF 가 없어 기초지수와 상품 구조를 확인하지 못했습니다.",
        }
    if rv["price_state"] != "after_close":
        st = PRICE_STATE.get(rv["price_state"], rv["price_state"])
        return {
            "kind": "price_state",
            "text": f"검토 기준일 가격이 마감 뒤 저장값이 아니어서({st}) 종가와 다를 수 있습니다.",
        }
    if rv["up"] is None:
        return {
            "kind": "weekly",
            "text": f"주 마감 가격을 확인하지 못해 최근 네 주 흐름을 모릅니다({why(rv['week_gap'])}).",
        }
    if _opposite(rv):
        return {
            "kind": "peer_gap",
            "text": "같은 지수 상품과 방향이 달라 그 원인을 아직 모릅니다.",
        }
    if peer["overseas"]:
        return {
            "kind": "currency",
            "text": "원화 가격이라 현지 지수 움직임과 환율 영향이 나뉘지 않습니다.",
        }
    return {
        "kind": "index",
        "text": "기초지수 자체의 같은 기간 움직임을 저장하지 않아, 가격 변화가 지수 변화와 같은지 화면에서 확인되지 않습니다.",
    }


def _opposite(rv: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    peer = rv["peer"]
    if peer["state"] != "ok":
        return []
    mine = sign_of(rv["one_month"]["value"])
    return [p for p in peer["same"] if sign_of(p["one_month"]["value"]) * mine < 0]


# 판정 2026-11-25 Q5 — 지수부터 · 환율 · 환헤지 · 보수 등은 ETF 와 의미 있는 차이를 설명할 필요가 있을 때만
GUIDE_GAP_OVERSEAS = (
    "원화 ETF 수익률과 의미 있는 차이를 설명할 필요가 있을 때만 환율 · 환헤지 여부 · 두 자료의 비교 시각 · "
    "수익률 기준 중 필요한 것을 출처와 기준 시각을 붙여 확인해 주세요. 환율이나 괴리율로 원인을 설명할 때는 "
    "실제 근거를 제시해 주세요."
)
GUIDE_GAP_DOMESTIC = (
    "ETF 수익률과 의미 있는 차이를 설명할 필요가 있을 때만 보수 · 분배금 · 두 자료의 비교 시각 · "
    "수익률 기준 중 필요한 것을 출처와 기준 시각을 붙여 확인해 주세요. 괴리율 등으로 원인을 설명할 때는 "
    "실제 근거를 제시해 주세요."
)
GUIDE_GAP_UNKNOWN = (
    "ETF 수익률과 의미 있는 차이를 설명할 필요가 있을 때만 환율 · 환헤지 · 보수 · 분배금 · 두 자료의 비교 시각 · "
    "수익률 기준 중 필요한 것을 출처와 기준 시각을 붙여 확인해 주세요. 차이의 원인을 말할 때는 "
    "실제 근거를 제시해 주세요."
)


def missing_values(rv: Mapping[str, Any]) -> list[str]:
    """이 묶음에 없는 값(판정 Q3) — 저장하지 않아 AI 가 공식 공개 자료에서 확인해야 하는 값."""
    one = rv["one_month"]
    when = f"같은 기간({md(one['start'])}~{md(one['end'])})"
    peer = rv["peer"]
    if peer["state"] != "ok":
        return [
            "이 ETF 의 기초지수 이름과 상품 구조(배수 · 복제 방법 · 환헤지)",
            f"{when} 그 기초지수의 수익률",
        ]
    lbl = peer["label"]
    if peer["overseas"]:
        return [
            f"{when} {lbl}의 현지 통화 기준 수익률",
            "같은 기간 환율(ETF 원화 가격과 같은 시각 기준)",
        ]
    return [f"{when} 기초지수 {lbl}의 수익률"]


def _ask(rv: Mapping[str, Any]) -> dict[str, Any]:
    """AI에 확인할 것 한 가지(Q5) — 질문 · 답에서 볼 것 · 복사문 안내."""
    one = rv["one_month"]
    when = f"{md(one['start'])}~{md(one['end'])}"
    sg = sign_of(one["value"])
    verb = {1: "올랐나요", -1: "내렸나요", 0: "움직였나요"}[sg]
    moved = {1: "올랐는지", -1: "내렸는지", 0: "움직였는지"}[sg]
    peer = rv["peer"]
    if peer["state"] != "ok":
        return {
            "kind": "no_official",
            "text": f"이 ETF의 기초지수와 상품 구조는 무엇이고, {when}에 기초지수도 이만큼 {verb}?",
            "look": [
                "기초지수 이름과 상품 구조(배수 · 복제 방법 · 환헤지)",
                f"기초지수도 같은 기간에 {moved}",
                "그 결과가 검토 의견을 어떻게 바꾸는지",
            ],
            "guide": [
                "먼저 공식 공개 자료에서 이 ETF 의 기초지수와 상품 구조를 확인하고, 같은 기간 그 지수의 수익률"
                "(해외 지수면 현지 통화 기준)을 확인해 주세요.",
                GUIDE_GAP_UNKNOWN,
            ],
        }
    opp = _opposite(rv)
    if opp:
        p = opp[0]
        lb = peer["label"]
        idx = f"{lb}의 현지 통화 기준" if peer["overseas"] else f"기초지수 {lb}의"
        return {
            "kind": "peer_gap",
            "text": (
                f"{when}에 같은 {peer['label']} 지수를 따르는 {p['name']}({p['ticker']})의 수익률은 "
                f"{pct(p['one_month']['value'])}였습니다. 이 ETF({pct(one['value'])})와 방향이 다른 이유는 무엇인가요?"
            ),
            "look": [
                "차이가 구조 · 환헤지 · 보수 · 분배 · 가격 기준일 중 무엇에서 오는지",
                "그 결과가 검토 의견을 어떻게 바꾸는지 — 설명되지 않는 차이면 보류할 근거가 됩니다",
            ],
            "guide": [
                f"먼저 같은 기간 {idx} 수익률을 확인해 두 상품 중 어느 쪽이 지수와 가까운지 봐 주세요.",
                "그다음 두 상품의 공식 자료(기초지수 · 환헤지 여부 · 복제 방법 · 보수 · 분배)와 두 가격의 기준일 · "
                "마감 시각에서 차이를 출처와 기준 시각을 붙여 확인해 주세요. 차이의 원인을 말할 때는 실제 근거를 "
                "제시해 주세요.",
            ],
        }
    lbl = peer["label"]
    if peer["overseas"]:
        note = {
            1: "현지 시장 자체의 상승이 확인되면 같은 지수 ETF 를 계속 비교할 근거가 됩니다",
            -1: "현지 시장 하락인지 환율 영향인지에 따라 보류 이유가 달라집니다",
            0: "현지 시장과 환율 중 무엇이 움직였는지에 따라 검토 이유가 달라집니다",
        }[sg]
        return {
            "kind": "local_index",
            "text": f"{when}에 {lbl}{topic(lbl)} 현지 통화로도 {verb}?",
            "look": [
                f"현지 지수도 {moved}",
                "ETF 원화 수익률과 차이가 있다면 무엇으로 설명되는지",
                f"그 결과가 검토 의견을 어떻게 바꾸는지 — {note}",
            ],
            "guide": [
                f"먼저 같은 기간 {lbl}의 현지 통화 기준 수익률을 확인해 주세요.",
                GUIDE_GAP_OVERSEAS,
            ],
        }
    note = {
        1: "지수 자체의 상승이 확인되면 이 상품을 그 지수의 대표로 비교할 근거가 됩니다",
        -1: "지수 하락과 같다면 상품 문제가 아니라 시장 흐름입니다",
        0: "지수와 같은지에 따라 검토 이유가 달라집니다",
    }[sg]
    return {
        "kind": "index",
        "text": f"{when}에 기초지수 {lbl}도 이만큼 {verb}?",
        "look": [
            f"기초지수도 같은 방향 · 비슷한 크기로 {moved}",
            "차이가 있다면 무엇으로 설명되는지(보수 · 분배 · 마감 시각)",
            f"그 결과가 검토 의견을 어떻게 바꾸는지 — {note}",
        ],
        "guide": [
            f"먼저 같은 기간 기초지수 {lbl}의 수익률을 확인해 주세요.",
            GUIDE_GAP_DOMESTIC,
        ],
    }


def compose(
    ctx: H.Context,
    ticker: str,
    *,
    sessions: Mapping[str, Any],
    reviews: list[Mapping[str, Any]],
    reader: Optional[Callable[[str, Mapping[str, Any]], Mapping[str, Any]]] = None,
    cutoff: Optional[datetime] = None,
    reviews_broken: int = 0,
) -> dict[str, Any]:
    """한 후보의 화면 · 복사문 자료 — 이번 주 후보 목록(모집단)에 있는 ETF 만(없으면 KeyError).

    cutoff = 검토 시점(없으면 지금) — 그 뒤에 만든 기록 · 내 판단은 넣지 않는다(나중 값 차단)."""
    item = ctx.item(ticker)
    if item is None:
        raise KeyError(ticker)
    b = ctx.build
    cut = cutoff or H.cutoff_of(None, ctx.end, dt.datetime.now(H.KST))
    records, reviews, late_recs, late_revs = H.visible(
        list(sessions.get("records") or []), list(reviews), ctx.end, cut
    )
    weeks = H.four_weeks(ctx, ticker, records, reviews)
    for row in weeks["rows"]:
        for m in row["records"]["mine"]:
            m["check"] = (
                H.reconcile(ctx, m["record"], m["entry"])
                if H.comparable(m["entry"])
                else None
            )
            # 외부 복사문 인용 여부 — 이번 조회 조건과 같다고 확인된 기록만(V2 RESULT 판정 §2)
            m["cite_why"] = H.cite_judge(
                m["record"], m["entry"], ctx.filters, m["check"]
            )
            m["cite"] = m["cite_why"]["state"]
    wk = b.get("weekly") or {}
    rv: dict[str, Any] = {
        "ticker": ticker,
        "name": item["name"],
        "end": ctx.end,
        "price_state": item["state"],
        "weekly": {k: wk.get(k) for k in ("w0", "finished", "mid_week", "dates")},
        "filters": dict(ctx.filters),
        "population": b["counts"]["population"],
        "rank": item["rank"],
        "top30": item["top30"],
        "one_month": dict(item["one_month"]),
        "kodex": (b.get("kodex") or {}).get("one_month"),
        "up": item["up"],
        "week_gap": item["week_gap"],
        "peer": P.peers_of(ticker, ctx.official, H._by_ticker(b), ctx.market["names"]),
        "weeks": weeks,
        "previous": _previous(ctx, ticker, records, reviews, weeks),
        # 화면 아래 '이 ETF 의 지난 판단' — 위 근거와 같은 검토 시점 필터를 지난 목록(최근 저장 먼저)
        "past": sorted(
            (dict(r) for r in reviews if r.get("ticker") == ticker),
            key=lambda r: (_saved_key(r), str(r.get("review_id") or "")),
            reverse=True,
        ),
        "sessions": {
            "state": sessions.get("state"),
            "broken": sessions.get("broken", 0),
            "reviews_broken": reviews_broken,
            # 검토 시점 뒤에 만들어 뺀 것 중 이 ETF 가 들어 있는 것만(다른 ETF 기록은 세지 않음)
            "late": sum(1 for r in late_recs if H.entry_of(r, ticker))
            + sum(1 for r in late_revs if r.get("ticker") == ticker),
            "cutoff": cut.isoformat(timespec="seconds"),
        },
        "composition": composition(reader, item, ctx.filters) if reader else None,
    }
    rv["flow"] = FL.flow(ctx, ticker, weeks["rows"], item)
    # 복사문 [당시 저장 기록]에 인용할 기록 — 조회 조건이 지금과 같다고 확인된 것만(V2 RESULT 판정 §2)
    rv["cite_records"] = H.cited_records(ctx, ticker, weeks["rows"], records)
    rv["gap"] = _gap(rv)
    rv["ask"] = _ask(rv)
    rv["missing"] = missing_values(rv)
    rv["copy"] = copy_text(rv)
    return rv
