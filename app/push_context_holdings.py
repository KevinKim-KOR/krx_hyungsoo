"""POC2 Cleanup — push_context holdings_view + 관련 line helper 분리 (2026-06-14).

3-PUSH Message Text Runtime Evidence 반영 STEP 의 KS-10 trigger 해소를 위해
`app/push_context.py` 의 holdings 책임을 본 모듈로 분리. 산식 / 문구 / 데이터
계약 변경 0건.

본 모듈은 다음 공개 helper 를 제공한다:

- `build_holdings_view` — PUSH-2 holdings_view dict.
- `holdings_observation_lines` — PUSH-2 draft_message 용 다중 라인 (관찰 포인트
  + market_view 연결 + 리뷰 포인트).
- `_holdings_overlap_tickers` — spike_view 가 사용하는 holdings ticker set.
"""

from __future__ import annotations

from typing import Any, Optional

from app.push_context_format import (
    _candidate_name,
    _candidate_ticker,
    _fmt_pct,
    _topn_candidates,
)
from app.push_context_market import _overnight_us_observation, build_market_view


def _holdings_overlap_tickers(pc_evidence: dict[str, Any]) -> set[str]:
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

    observations 가 1건도 없으면 빈 dict 반환.

    단순 ticker 목록이 아니라 portfolio_weight / runtime quote / market_discovery
    overlap / 미국 지수 연결 문장을 1건씩 갖는 관찰 포인트로 만든다.
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
            # 정보 부족인 종목은 skip — 단순 목록 나열 금지.
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


def holdings_observation_lines(
    push_context: Optional[dict[str, Any]],
) -> list[str]:
    """PUSH-2 draft_message 용 — push_context.holdings_view.observations 의
    관찰 문장 + push_context.market_view 의 미국 지수 1줄을 묶어 반환."""
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
            # Holdings-Market PENDING Judgment Draft v1 REJECTED r2 정정:
            # 내부 source key "(market_view)" 는 사용자 화면 헤더에서 제거.
            # 내부 필드/데이터 계약 미변경.
            lines.append("[시장 흐름 연결]")
            lines.append("  • " + " / ".join(connection_parts))
    review_points = hv.get("review_points") or []
    if isinstance(review_points, list) and review_points:
        lines.append("")
        lines.append("[리뷰 포인트]")
        for rp in review_points[:3]:
            if isinstance(rp, str) and rp.strip():
                lines.append(f"  • {rp}")
    return lines
