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
"""

from __future__ import annotations

from typing import Any, Optional


def _has_data(snapshot: Any) -> bool:
    if not isinstance(snapshot, dict) or not snapshot:
        return False
    status = snapshot.get("status")
    if status in ("unavailable", "failed"):
        return False
    return True


def build_market_view(
    *,
    pc_evidence: dict[str, Any],
    runtime_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """PUSH-1 market_view — 시장 흐름 + 미국 지수 overnight + 위험 패턴 evidence.

    observations 가 1건도 없으면 **빈 dict 반환** (의미 있는 시장 관찰이 없을 때
    상위 호출자가 market_view 를 "있는 것" 으로 오인하지 않도록 — FIX r3, 검증자
    2차 REJECTED 후속, A-1 (1)).
    """
    observations: list[dict[str, Any]] = []
    md = pc_evidence.get("market_discovery_snapshot")
    if _has_data(md):
        observations.append(
            {
                "type": "market_trend",
                "evidence_refs": [
                    "pc_evidence_snapshot.market_discovery_snapshot.top_candidates"
                ],
            }
        )
    us = runtime_snapshot.get("overnight_us_market_snapshot")
    if isinstance(us, dict) and us.get("status") in ("ok", "partial"):
        ok_symbols = [
            i.get("symbol")
            for i in (us.get("indices") or [])
            if isinstance(i, dict) and i.get("status") == "ok"
        ]
        if ok_symbols:
            observations.append(
                {
                    "type": "overnight_us",
                    "symbols": ok_symbols,
                    "evidence_refs": [
                        "runtime_snapshot.overnight_us_market_snapshot.indices"
                    ],
                }
            )
    ml = pc_evidence.get("ml_baseline_snapshot")
    if _has_data(ml):
        observations.append(
            {
                "type": "risk_pattern",
                "evidence_refs": ["pc_evidence_snapshot.ml_baseline_snapshot"],
            }
        )

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


def build_holdings_view(
    *,
    pc_evidence: dict[str, Any],
    runtime_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """PUSH-2 holdings_view — holdings positions × runtime kr quote 관찰 포인트.

    observations 가 1건도 없으면 빈 dict 반환 (FIX r3).
    """
    holdings = pc_evidence.get("holdings_snapshot") or {}
    positions = holdings.get("positions") if isinstance(holdings, dict) else None
    obs: list[dict[str, Any]] = []
    if isinstance(positions, list):
        for p in positions[:10]:  # 길이 안전: 상위 10건만.
            if not isinstance(p, dict):
                continue
            ticker = p.get("ticker")
            if not isinstance(ticker, str):
                continue
            obs.append(
                {
                    "ticker": ticker,
                    "name": p.get("name"),
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


def build_spike_view(
    *,
    pc_evidence: dict[str, Any],
    runtime_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """PUSH-3 spike_view — universe_momentum.top_candidate + falling_candidate 관찰.

    items 가 1건도 없으면 빈 dict 반환 (FIX r3).
    """
    um = pc_evidence.get("universe_momentum_snapshot") or {}
    items: list[dict[str, Any]] = []
    summary = um.get("summary") if isinstance(um, dict) else None
    if isinstance(summary, dict):
        for key, direction in (("top_candidate", "up"), ("falling_candidate", "down")):
            cand = summary.get(key)
            if not isinstance(cand, dict):
                continue
            score = (cand.get("score_result") or {}).get("score_value")
            if not isinstance(score, (int, float)):
                continue
            items.append(
                {
                    "ticker": cand.get("ticker") or "",
                    "name": cand.get("name") or "",
                    "score_value": float(score),
                    "direction": direction,
                    "evidence_refs": [
                        f"pc_evidence_snapshot.universe_momentum_snapshot.summary.{key}"
                    ],
                }
            )
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
    overnight_us 관측을 사람이 읽는 1줄 요약으로 변환 (있을 때만)."""
    if not isinstance(push_context, dict):
        return []
    mv = push_context.get("market_view")
    if not isinstance(mv, dict):
        return []
    for obs in mv.get("observations") or []:
        if isinstance(obs, dict) and obs.get("type") == "overnight_us":
            symbols = obs.get("symbols") or []
            if not symbols:
                return []
            return [
                "[밤사이 미국 시장 (runtime probe)]",
                f"  • 조회 가능 지수: {', '.join(s for s in symbols if isinstance(s, str))}",
            ]
    return []
