"""POC2 3-PUSH Runtime Package PC 검증 — push_context 빌더 (2026-06-13).

지시문 §6 / §13 / AC-6 — message_text 생성 흐름:

    pc_evidence_snapshot + runtime_snapshot
    → push_context (market_view / holdings_view / spike_view)
    → message_text

본 모듈은 pc_evidence + runtime 결과를 입력으로 받아 push_kind 별 push_context
중간 관찰 구조를 만든다. push_context 는 기존 산식 변경 없이 evidence 의 값을
지표/문구 단위로 정렬한 dict — 매수/매도 / 위험 threshold / 조정장 확정 0건.

message builder (`message_market_briefing` / `message_spike_alert` /
`draft_message`) 는 push_context 를 받아 message_text 를 만든다 — 기존 산식
계산은 builder 내부에서 변경 없이 그대로 사용.

3-PUSH Message Text Runtime Evidence 반영 (2026-06-14) — observations 에 실제
값을 직접 노출. message builder 가 별도 evidence 접근 없이 push_context 만으로
사람이 판단할 문장을 만들 수 있도록 한다 (AC-1 / AC-2 / AC-4 / AC-5).
"""

from __future__ import annotations

from typing import Any, Optional

_US_SECTOR_HINTS: dict[str, str] = {
    "SOX": "반도체 지수 강세는 국내 반도체/성장 ETF 해석에 참고 가능",
    "NASDAQ": "기술주 지수 강세는 국내 성장/IT 테마 해석에 참고 가능",
    "SPX": "S&P 500 흐름은 한국 시장 전반의 위험 선호 분위기에 참고 가능",
}


def _has_data(snapshot: Any) -> bool:
    if not isinstance(snapshot, dict) or not snapshot:
        return False
    status = snapshot.get("status")
    if status in ("unavailable", "failed"):
        return False
    return True


def _fmt_pct(value: Any) -> Optional[str]:
    """이미 % 단위 (e.g. 0.85 = 0.85%) 인 값을 사람이 읽는 부호 포함 문자열로.

    주의: 본 헬퍼는 입력을 그대로 % 로 본다. compute_topn 의 selected_return_pct
    같이 ratio(0.15 = 15%) 일 수 있는 값은 호출자가 미리 변환하거나 별도 분기를
    사용해야 한다 (예: _candidate_return_pct).
    """
    if not isinstance(value, (int, float)):
        return None
    pct = float(value)
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.2f}%"


def _topn_candidates(md: Any) -> list[dict[str, Any]]:
    """compute_topn payload 의 candidates 또는 items 를 정규화."""
    if not isinstance(md, dict):
        return []
    cand = md.get("candidates")
    if isinstance(cand, list) and cand:
        return [c for c in cand if isinstance(c, dict)]
    items = md.get("items")
    if isinstance(items, list) and items:
        return [c for c in items if isinstance(c, dict)]
    return []


def _candidate_return_pct(c: dict[str, Any]) -> Optional[float]:
    """candidate dict 에서 표시용 return_pct (%) 추출. ratio→% 자동 변환."""
    v = c.get("selected_return_pct")
    if not isinstance(v, (int, float)):
        v = c.get("return_pct")
    if not isinstance(v, (int, float)):
        return None
    return float(v) * 100.0 if abs(v) < 1.5 else float(v)


def _candidate_name(c: dict[str, Any]) -> str:
    return c.get("name") or c.get("ticker") or "-"


def _candidate_ticker(c: dict[str, Any]) -> Optional[str]:
    t = c.get("ticker")
    return t if isinstance(t, str) and t.strip() else None


def _market_trend_observation(md: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Market Discovery TopN 의 상위/하위 흐름을 1줄 관찰로 변환."""
    candidates = _topn_candidates(md)
    sortable = [
        (c, _candidate_return_pct(c))
        for c in candidates
        if _candidate_return_pct(c) is not None
    ]
    if not sortable:
        return None
    sortable.sort(key=lambda x: x[1], reverse=True)  # type: ignore[arg-type]
    basis = md.get("basis") or "1m"
    top = sortable[:3]
    bot = sortable[-3:][::-1]
    text_parts: list[str] = []
    if top:
        head = ", ".join(f"{_candidate_name(c)} {_fmt_pct(p)}" for c, p in top)
        text_parts.append(f"상위({basis}): {head}")
    if bot:
        tail = ", ".join(f"{_candidate_name(c)} {_fmt_pct(p)}" for c, p in bot)
        text_parts.append(f"하위({basis}): {tail}")
    if not text_parts:
        return None
    return {
        "type": "market_trend",
        "basis": basis,
        "asof": md.get("asof"),
        "top_items": [
            {
                "name": _candidate_name(c),
                "ticker": _candidate_ticker(c),
                "return_pct": p,
            }
            for c, p in top
        ],
        "bottom_items": [
            {
                "name": _candidate_name(c),
                "ticker": _candidate_ticker(c),
                "return_pct": p,
            }
            for c, p in bot
        ],
        "text": " / ".join(text_parts),
        "evidence_refs": ["pc_evidence_snapshot.market_discovery_snapshot.candidates"],
    }


def _overnight_us_observation(us: dict[str, Any]) -> Optional[dict[str, Any]]:
    """US 지수 probe 결과 → 실제 등락률 1줄 관찰 + 섹터 해석 문장."""
    if not isinstance(us, dict):
        return None
    if us.get("status") not in ("ok", "partial"):
        return None
    indices_raw = us.get("indices") or []
    ok_indices: list[dict[str, Any]] = []
    for idx in indices_raw:
        if not isinstance(idx, dict):
            continue
        if idx.get("status") != "ok":
            continue
        symbol = idx.get("symbol")
        change = idx.get("change_pct")
        close = idx.get("close")
        if not isinstance(symbol, str):
            continue
        if not isinstance(change, (int, float)):
            continue
        ok_indices.append(
            {
                "symbol": symbol,
                "name": idx.get("name"),
                "close": close if isinstance(close, (int, float)) else None,
                "change_pct": float(change),
            }
        )
    if not ok_indices:
        return None
    summary_text = ", ".join(
        f"{i['symbol']} {_fmt_pct(i['change_pct'])}" for i in ok_indices
    )
    # 가장 큰 절대 변동률 지수 1건을 골라 섹터 해석 hint 부여.
    strongest = max(ok_indices, key=lambda i: abs(i["change_pct"]))
    sector_hint = _US_SECTOR_HINTS.get(strongest["symbol"]) if strongest else None
    return {
        "type": "overnight_us",
        "symbols": [i["symbol"] for i in ok_indices],
        "indices": ok_indices,
        "summary_text": summary_text,
        "sector_hint": sector_hint,
        "evidence_refs": [
            "runtime_snapshot.overnight_us_market_snapshot.indices",
        ],
    }


def _risk_pattern_observation(ml: dict[str, Any]) -> Optional[dict[str, Any]]:
    """ML baseline 의 high/low risk drawdown 1줄 관찰."""
    if not isinstance(ml, dict):
        return None
    if ml.get("status") in (None, "unavailable", "error"):
        return None
    risk = ml.get("risk_summary")
    if not isinstance(risk, dict):
        return None
    high_dd = risk.get("high_risk_group_future_drawdown") or {}
    low_dd = risk.get("low_risk_group_future_drawdown") or {}
    high10 = high_dd.get("10d") if isinstance(high_dd, dict) else None
    low10 = low_dd.get("10d") if isinstance(low_dd, dict) else None
    eval_days = risk.get("evaluated_days")
    if not (
        isinstance(high10, (int, float))
        and isinstance(low10, (int, float))
        and isinstance(eval_days, int)
    ):
        # 정보 부족 시에도 observation 자체는 만들어 둠 (text 없이) → builder 는
        # text 가 없으면 섹션 생략.
        return {
            "type": "risk_pattern",
            "evidence_refs": ["pc_evidence_snapshot.ml_baseline_snapshot"],
        }

    # ML baseline 의 drawdown 값은 ratio (-0.0837) 일 수도, % (-8.37) 일 수도
    # 있다. 절대값이 1.5 미만이면 ratio 로 보고 ×100 하여 % 로 정규화 — 기존
    # _evidence_section (message_market_briefing) 의 _fmt_pct 와 동일 규약.
    def _as_pct(v: float) -> float:
        return v * 100.0 if abs(v) < 1.5 else v

    high10_pct = _as_pct(float(high10))
    low10_pct = _as_pct(float(low10))
    return {
        "type": "risk_pattern",
        "evaluated_days": int(eval_days),
        "high_risk_drawdown_10d_pct": high10_pct,
        "low_risk_drawdown_10d_pct": low10_pct,
        "text": (
            f"과거 {eval_days}거래일 룩백 — high-risk bucket 의 이후 10d drawdown "
            f"{_fmt_pct(high10_pct)} vs low-risk {_fmt_pct(low10_pct)} "
            "(참고용 baseline)."
        ),
        "evidence_refs": ["pc_evidence_snapshot.ml_baseline_snapshot"],
    }


def build_market_view(
    *,
    pc_evidence: dict[str, Any],
    runtime_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """PUSH-1 market_view — 시장 흐름 + 미국 지수 overnight + 위험 패턴 evidence.

    observations 가 1건도 없으면 **빈 dict 반환** (의미 있는 시장 관찰이 없을 때
    상위 호출자가 market_view 를 "있는 것" 으로 오인하지 않도록 — FIX r3, 검증자
    2차 REJECTED 후속, A-1 (1)).

    3-PUSH Message Text Runtime Evidence 반영 (2026-06-14) — observation 마다
    text / 실제 수치를 포함시켜 message builder 가 그대로 노출할 수 있게 만든다.
    """
    observations: list[dict[str, Any]] = []
    md = pc_evidence.get("market_discovery_snapshot")
    if _has_data(md):
        trend = _market_trend_observation(md)
        if trend is not None:
            observations.append(trend)
    us = runtime_snapshot.get("overnight_us_market_snapshot")
    overnight = _overnight_us_observation(us) if isinstance(us, dict) else None
    if overnight is not None:
        observations.append(overnight)
    ml = pc_evidence.get("ml_baseline_snapshot")
    if _has_data(ml):
        risk = _risk_pattern_observation(ml)
        if risk is not None:
            observations.append(risk)

    if not observations:
        # 의미 있는 시장 관찰 0건 → view 자체를 만들지 않는다.
        return {}

    return {
        "push_kind": "market_briefing",
        "summary_inputs": {
            "kr_market_trend_basis": "previous_close",
            "us_overnight_basis": "latest_available",
            "risk_evidence_basis": "ml_baseline_snapshot",
        },
        "observations": observations,
        "limitations": [
            "실시간 장중 판단이 아니라 발송 시점 snapshot 기준",
        ],
    }


def _holdings_overlap_tickers(
    pc_evidence: dict[str, Any],
) -> set[str]:
    """holdings_snapshot 에서 ticker set 추출 (Market Discovery / spike overlap 용)."""
    holdings = pc_evidence.get("holdings_snapshot") or {}
    positions = holdings.get("positions") if isinstance(holdings, dict) else None
    if not isinstance(positions, list):
        return set()
    out: set[str] = set()
    for p in positions:
        if isinstance(p, dict):
            t = p.get("ticker")
            if isinstance(t, str) and t.strip():
                out.add(t)
    return out


def _holdings_position_text(
    p: dict[str, Any],
    kr_quotes_by_ticker: dict[str, dict[str, Any]],
    md_overlap_names: dict[str, str],
    us_summary_text: Optional[str],
) -> Optional[str]:
    """holdings position 1건 → 사람이 읽는 관찰 문장.

    관찰 우선순위 (앞부터):
    - runtime quote 변화율 (있으면)
    - portfolio weight 또는 평가
    - market discovery 후보 overlap
    - 미국 지수 강세와의 연결 (있으면)
    """
    ticker = p.get("ticker") if isinstance(p, dict) else None
    if not isinstance(ticker, str):
        return None
    name = p.get("name") or ticker
    parts: list[str] = []
    quote = kr_quotes_by_ticker.get(ticker)
    if isinstance(quote, dict):
        change = quote.get("change_pct")
        price = quote.get("price")
        if isinstance(change, (int, float)) and isinstance(price, (int, float)):
            parts.append(f"runtime 시세 {_fmt_pct(change)} (가격 {int(price):,})")
    weight = p.get("portfolio_weight_pct") or p.get("market_weight_pct")
    if isinstance(weight, (int, float)):
        parts.append(f"비중 {weight:.1f}%")
    pnl_rate = p.get("unrealized_return_pct") or p.get("pnl_rate_pct")
    if isinstance(pnl_rate, (int, float)):
        parts.append(f"평가수익률 {_fmt_pct(pnl_rate)}")
    if ticker in md_overlap_names:
        parts.append("Market Discovery 후보와 겹침")
    if us_summary_text and ticker == "069500":
        parts.append("국내 기준선 — 밤사이 미국 지수 흐름과 함께 확인 필요")
    if not parts:
        # 최소한 종목명만 노출하는 단순 문장은 만들지 않는다 (단순 나열 금지).
        return None
    return f"{name} ({ticker}): " + " · ".join(parts) + " — 관찰 필요"


def build_holdings_view(
    *,
    pc_evidence: dict[str, Any],
    runtime_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """PUSH-2 holdings_view — holdings positions × runtime kr quote 관찰 포인트.

    observations 가 1건도 없으면 빈 dict 반환 (FIX r3).

    3-PUSH Message Text Runtime Evidence 반영 (2026-06-14) — 단순 ticker 목록이
    아니라 portfolio_weight / runtime quote / market_discovery overlap / 미국 지수
    연결 문장을 1건씩 갖는 관찰 포인트로 만든다 (AC-3 / AC-4).
    """
    holdings = pc_evidence.get("holdings_snapshot") or {}
    positions = holdings.get("positions") if isinstance(holdings, dict) else None
    if not isinstance(positions, list):
        return {}

    # runtime quote / market discovery overlap / us_summary 준비.
    kr_snap = runtime_snapshot.get("kr_realtime_price_snapshot") or {}
    kr_items = kr_snap.get("items") if isinstance(kr_snap, dict) else None
    kr_quotes_by_ticker: dict[str, dict[str, Any]] = {}
    if isinstance(kr_items, list):
        for it in kr_items:
            if isinstance(it, dict) and isinstance(it.get("ticker"), str):
                if it.get("data_status") == "ok":
                    kr_quotes_by_ticker[it["ticker"]] = it

    md = pc_evidence.get("market_discovery_snapshot") or {}
    md_names_by_ticker: dict[str, str] = {}
    for c in _topn_candidates(md):
        t = _candidate_ticker(c)
        if t:
            md_names_by_ticker[t] = _candidate_name(c)

    us_obs = _overnight_us_observation(
        runtime_snapshot.get("overnight_us_market_snapshot") or {}
    )
    us_summary = us_obs.get("summary_text") if isinstance(us_obs, dict) else None

    obs: list[dict[str, Any]] = []

    # 우선순위 정렬: runtime quote 있는 종목 > portfolio_weight 큰 종목 > 나머지.
    def _priority(p: dict[str, Any]) -> tuple[int, float]:
        t = p.get("ticker") if isinstance(p, dict) else None
        has_quote = isinstance(t, str) and t in kr_quotes_by_ticker
        weight_val = p.get("portfolio_weight_pct") or p.get("market_weight_pct")
        w = float(weight_val) if isinstance(weight_val, (int, float)) else 0.0
        return (0 if has_quote else 1, -w)

    sorted_positions = sorted(
        [p for p in positions if isinstance(p, dict)],
        key=_priority,
    )
    for p in sorted_positions[:10]:  # 길이 안전: 상위 10건만.
        ticker = p.get("ticker")
        if not isinstance(ticker, str):
            continue
        text = _holdings_position_text(
            p,
            kr_quotes_by_ticker=kr_quotes_by_ticker,
            md_overlap_names=md_names_by_ticker,
            us_summary_text=us_summary,
        )
        if text is None:
            # 정보 부족인 종목은 skip — 단순 목록 나열 금지 (AC-3).
            continue
        obs.append(
            {
                "ticker": ticker,
                "name": p.get("name"),
                "text": text,
                "evidence_refs": [
                    f"pc_evidence_snapshot.holdings_snapshot.positions[{ticker}]",
                    f"runtime_snapshot.kr_realtime_price_snapshot.{ticker}",
                ],
            }
        )
    if not obs:
        return {}
    review_points = [
        "미국 지수와 국내 보유 ETF의 방향이 엇갈리는지 확인",
        "보유 종목이 당일 급등락 후보와 겹치는지 확인",
    ]
    view: dict[str, Any] = {
        "push_kind": "holdings_briefing",
        "depends_on": "market_view",
        "observations": obs,
        "review_points": review_points,
    }
    # market_view 가 의미 있을 때만 임베드 (없으면 키 생략).
    mv = build_market_view(pc_evidence=pc_evidence, runtime_snapshot=runtime_snapshot)
    if mv:
        view["market_view"] = mv
    return view


def _universe_momentum_items(um: dict[str, Any]) -> list[dict[str, Any]]:
    """universe_momentum_snapshot 의 summary.top_candidate / falling_candidate 를
    추출해 score / 방향 / reason 을 갖는 dict 리스트로 정규화."""
    out: list[dict[str, Any]] = []
    summary = um.get("summary") if isinstance(um, dict) else None
    if not isinstance(summary, dict):
        return []
    for key, direction in (("top_candidate", "up"), ("falling_candidate", "down")):
        cand = summary.get(key)
        if not isinstance(cand, dict):
            continue
        score = (cand.get("score_result") or {}).get("score_value")
        if not isinstance(score, (int, float)):
            continue
        phb = cand.get("price_history_basis") or {}
        basis_date = phb.get("latest_date") if isinstance(phb, dict) else None
        out.append(
            {
                "ticker": cand.get("ticker") or "",
                "name": cand.get("name") or "",
                "score_value": float(score),
                "direction": direction,
                "basis_date": basis_date,
                "evidence_refs": [
                    f"pc_evidence_snapshot.universe_momentum_snapshot.summary.{key}"
                ],
            }
        )
    return out


def build_spike_view(
    *,
    pc_evidence: dict[str, Any],
    runtime_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """PUSH-3 spike_view — universe_momentum.top_candidate + falling_candidate +
    market_discovery candidates 중 절대 수익률 큰 항목들의 관찰 묶음.

    items 가 1건도 없으면 빈 dict 반환 (FIX r3).

    3-PUSH Message Text Runtime Evidence 반영 (2026-06-14):
    각 item 에 수익률 근거 / 방향 / data_quality / holdings overlap 여부를 채움
    (AC-5 — score 단독 표시 금지).
    """
    um = pc_evidence.get("universe_momentum_snapshot") or {}
    items: list[dict[str, Any]] = _universe_momentum_items(um)

    # Market Discovery candidates 중 절대 수익률이 큰 항목도 함께 노출 (data_quality
    # flag 가 있는 항목을 우선 표시).
    md = pc_evidence.get("market_discovery_snapshot") or {}
    md_candidates = _topn_candidates(md)
    md_enriched: list[tuple[dict[str, Any], float]] = []
    for c in md_candidates:
        p = _candidate_return_pct(c)
        if p is None:
            continue
        md_enriched.append((c, p))
    md_enriched.sort(key=lambda x: abs(x[1]), reverse=True)

    holdings_tickers = _holdings_overlap_tickers(pc_evidence)
    seen_tickers: set[str] = {it["ticker"] for it in items if it.get("ticker")}

    for c, p in md_enriched[:5]:
        t = _candidate_ticker(c)
        if not t or t in seen_tickers:
            continue
        seen_tickers.add(t)
        returns = c.get("returns") if isinstance(c.get("returns"), dict) else {}
        return_1d = (
            (returns.get("daily") or {}).get("return_pct")
            if isinstance(returns, dict)
            else None
        )
        return_5d = None  # 별도 입력 없음.
        return_20d = (
            (returns.get("one_month") or {}).get("return_pct")
            if isinstance(returns, dict)
            else None
        )
        dq = c.get("data_quality_flag")
        dq_flags = [dq] if isinstance(dq, str) and dq.strip() else []
        direction = "up" if p >= 0 else "down"
        items.append(
            {
                "ticker": t,
                "name": _candidate_name(c),
                "direction": direction,
                "return_1d_pct": (
                    float(return_1d) if isinstance(return_1d, (int, float)) else None
                ),
                "return_5d_pct": (
                    float(return_5d) if isinstance(return_5d, (int, float)) else None
                ),
                "return_20d_pct": (
                    float(return_20d) * 100.0
                    if isinstance(return_20d, (int, float)) and abs(return_20d) < 1.5
                    else (
                        float(return_20d)
                        if isinstance(return_20d, (int, float))
                        else None
                    )
                ),
                "selected_return_pct": p,
                "data_quality_flags": dq_flags,
                "holdings_overlap": t in holdings_tickers,
                "evidence_refs": [
                    f"pc_evidence_snapshot.market_discovery_snapshot.candidates[{t}]"
                ],
            }
        )

    # universe_momentum item 에도 holdings_overlap / data_quality_flags 채워넣기.
    for it in items:
        t = it.get("ticker")
        if isinstance(t, str):
            it.setdefault("holdings_overlap", t in holdings_tickers)
        it.setdefault("data_quality_flags", [])

    if not items:
        return {}
    return {
        "push_kind": "spike_or_falling_alert",
        "universe_scope": "ETF",
        "ranking_basis": "absolute_return_desc",
        "items": items,
        "limitations": [
            "개별 주식 전체 universe는 포함하지 않음",
        ],
    }


def build_push_context(
    *,
    push_kind: str,
    pc_evidence: dict[str, Any],
    runtime_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """push_kind 별 push_context dict 빌더. message builder 가 본 결과를 받아
    message_text 를 생성한다 (지시문 §13 — runtime_package → push_context → message_text).

    빈 view 는 키 자체 생략 (FIX r3, A-1 (1)) — runtime_package._evaluate_generation_
    status 가 "view 존재 = 의미 있는 관찰 1건 이상" 으로 판단할 수 있도록.
    """
    ctx: dict[str, Any] = {}
    if push_kind == "market_briefing":
        mv = build_market_view(
            pc_evidence=pc_evidence, runtime_snapshot=runtime_snapshot
        )
        if mv:
            ctx["market_view"] = mv
    elif push_kind == "holdings_briefing":
        hv = build_holdings_view(
            pc_evidence=pc_evidence, runtime_snapshot=runtime_snapshot
        )
        if hv:
            ctx["holdings_view"] = hv
        # market_view 가 의미 있을 때만 노출 (계약 §9.2 depends_on).
        mv = build_market_view(
            pc_evidence=pc_evidence, runtime_snapshot=runtime_snapshot
        )
        if mv:
            ctx["market_view"] = mv
    elif push_kind == "spike_or_falling_alert":
        sv = build_spike_view(
            pc_evidence=pc_evidence, runtime_snapshot=runtime_snapshot
        )
        if sv:
            ctx["spike_view"] = sv
    return ctx


def overnight_us_lines(push_context: Optional[dict[str, Any]]) -> list[str]:
    """message builder 용 헬퍼 — push_context.market_view.observations 안의
    overnight_us 관측을 사람이 읽는 다중 라인 요약으로 변환.

    3-PUSH Message Text Runtime Evidence 반영 (2026-06-14): 단순 "조회 가능 지수"
    표시에서 실제 close / change_pct + 섹터 해석 1줄을 노출하도록 확장 (AC-1).
    """
    if not isinstance(push_context, dict):
        return []
    mv = push_context.get("market_view")
    if not isinstance(mv, dict):
        return []
    for obs in mv.get("observations") or []:
        if not (isinstance(obs, dict) and obs.get("type") == "overnight_us"):
            continue
        indices = obs.get("indices") or []
        if not isinstance(indices, list) or not indices:
            return []
        lines: list[str] = ["[밤사이 미국 시장 (runtime probe)]"]
        for idx in indices:
            if not isinstance(idx, dict):
                continue
            sym = idx.get("symbol")
            change = idx.get("change_pct")
            close = idx.get("close")
            if not isinstance(sym, str) or not isinstance(change, (int, float)):
                continue
            change_text = _fmt_pct(change)
            if isinstance(close, (int, float)):
                lines.append(f"  • {sym} {change_text} (close {close:,.2f})")
            else:
                lines.append(f"  • {sym} {change_text}")
        sector_hint = obs.get("sector_hint")
        if isinstance(sector_hint, str) and sector_hint.strip():
            lines.append(f"  • {sector_hint}")
        return lines if len(lines) > 1 else []
    return []


def market_trend_lines(push_context: Optional[dict[str, Any]]) -> list[str]:
    """message builder 용 헬퍼 — push_context.market_view 의 market_trend
    observation 을 1~2줄 관찰로 변환 (AC-2 — market evidence 연결).
    """
    if not isinstance(push_context, dict):
        return []
    mv = push_context.get("market_view")
    if not isinstance(mv, dict):
        return []
    for obs in mv.get("observations") or []:
        if not (isinstance(obs, dict) and obs.get("type") == "market_trend"):
            continue
        text = obs.get("text")
        if not isinstance(text, str) or not text.strip():
            return []
        return [
            "[국내 시장 내부 신호 (Market Discovery)]",
            f"  • {text}",
        ]
    return []


def risk_pattern_lines(push_context: Optional[dict[str, Any]]) -> list[str]:
    """message builder 용 헬퍼 — push_context.market_view 의 risk_pattern
    observation 을 1줄로 변환 (AC-2 — ML baseline evidence 연결)."""
    if not isinstance(push_context, dict):
        return []
    mv = push_context.get("market_view")
    if not isinstance(mv, dict):
        return []
    for obs in mv.get("observations") or []:
        if not (isinstance(obs, dict) and obs.get("type") == "risk_pattern"):
            continue
        text = obs.get("text")
        if not isinstance(text, str) or not text.strip():
            return []
        return [
            "[위험 패턴 참고 (ML baseline 룩백)]",
            f"  • {text}",
        ]
    return []


def holdings_observation_lines(
    push_context: Optional[dict[str, Any]],
) -> list[str]:
    """PUSH-2 draft_message 용 — push_context.holdings_view.observations 의
    관찰 문장 + push_context.market_view 의 미국 지수 1줄을 묶어 반환 (AC-3 / AC-4).
    """
    if not isinstance(push_context, dict):
        return []
    hv = push_context.get("holdings_view")
    if not isinstance(hv, dict):
        return []
    observations = hv.get("observations") or []
    if not isinstance(observations, list) or not observations:
        return []
    lines: list[str] = ["[보유 종목 관찰 포인트]"]
    for o in observations[:6]:
        if isinstance(o, dict):
            text = o.get("text")
            if isinstance(text, str) and text.strip():
                lines.append(f"  • {text}")
    if len(lines) == 1:
        return []
    # market_view 연결 1줄 — 미국 지수 흐름 + 국내 시장 내부 신호 짧은 안내.
    mv = push_context.get("market_view") or {}
    if isinstance(mv, dict):
        us_text: Optional[str] = None
        trend_text: Optional[str] = None
        for obs in mv.get("observations") or []:
            if isinstance(obs, dict):
                if obs.get("type") == "overnight_us":
                    us_text = obs.get("summary_text")
                elif obs.get("type") == "market_trend":
                    trend_text = obs.get("text")
        connection_parts: list[str] = []
        if isinstance(us_text, str) and us_text.strip():
            connection_parts.append(f"밤사이 미국: {us_text}")
        if isinstance(trend_text, str) and trend_text.strip():
            connection_parts.append(trend_text)
        if connection_parts:
            lines.append("")
            lines.append("[시장 흐름 연결 (market_view)]")
            lines.append("  • " + " / ".join(connection_parts))
    review_points = hv.get("review_points") or []
    if isinstance(review_points, list) and review_points:
        lines.append("")
        lines.append("[리뷰 포인트]")
        for rp in review_points[:3]:
            if isinstance(rp, str) and rp.strip():
                lines.append(f"  • {rp}")
    return lines


def spike_view_lines(push_context: Optional[dict[str, Any]]) -> list[str]:
    """PUSH-3 message builder 용 — push_context.spike_view.items 1건씩 사람이
    읽는 관찰 문장으로 변환. score 단독 표시 금지 (AC-5).

    각 line 에는 가능한 경우 수익률 근거 / 방향 / data_quality / holdings overlap
    중 최소 2개 이상이 포함된다.
    """
    if not isinstance(push_context, dict):
        return []
    sv = push_context.get("spike_view")
    if not isinstance(sv, dict):
        return []
    items = sv.get("items") or []
    if not isinstance(items, list) or not items:
        return []
    out: list[str] = ["[universe momentum 관찰 (push_context 기반)]"]
    for it in items[:6]:
        if not isinstance(it, dict):
            continue
        name = it.get("name") or it.get("ticker") or "-"
        direction = it.get("direction") or "-"
        return_terms: list[str] = []
        for label, key in (
            ("1d", "return_1d_pct"),
            ("5d", "return_5d_pct"),
            ("20d", "return_20d_pct"),
        ):
            v = it.get(key)
            if isinstance(v, (int, float)):
                return_terms.append(f"{label} {_fmt_pct(v)}")
        score_val = it.get("score_value")
        if isinstance(score_val, (int, float)) and not return_terms:
            return_terms.append(f"momentum score {score_val:+.2f}")
        dq_flags = it.get("data_quality_flags") or []
        dq_text = (
            f"data_quality flag: {', '.join(dq_flags)}"
            if isinstance(dq_flags, list) and dq_flags
            else "data_quality 이상 없음"
        )
        overlap = it.get("holdings_overlap")
        overlap_text = (
            "보유 종목과 겹침 (별도 확인 필요)"
            if overlap is True
            else "보유 종목과 겹치지 않음"
        )
        if not return_terms:
            # 수익률도 없고 score 도 없으면 단독 표시 회피.
            continue
        line_parts = [
            ", ".join(return_terms),
            f"방향 {direction}",
            dq_text,
            overlap_text,
        ]
        out.append(f"  • {name}: " + " · ".join(line_parts))
    if len(out) == 1:
        return []
    return out
