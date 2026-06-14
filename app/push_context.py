"""POC2 3-PUSH Runtime Package — push_context orchestration (2026-06-13).

지시문 §6 / §13 / AC-6 — message_text 생성 흐름:

    pc_evidence_snapshot + runtime_snapshot
    → push_context (market_view / holdings_view / spike_view)
    → message_text

본 모듈은 push_kind 별 orchestration 만 담당한다. 실제 view 빌더와 message
builder 용 line helper 는 책임 모듈로 분리되어 있다 (2026-06-14 Cleanup):

- `app.push_context_format` — 공통 helper (_fmt_pct / _has_data / _topn_candidates 등).
- `app.push_context_market` — market_view + overnight_us_lines / market_trend_lines
  / risk_pattern_lines.
- `app.push_context_holdings` — holdings_view + holdings_observation_lines.
- `app.push_context_spike` — spike_view + spike_view_lines.

기존 import 호환 유지를 위해 본 모듈에서 분리 모듈의 공개 helper 를 re-export
한다 (`from app.push_context import build_push_context`, `overnight_us_lines`,
`market_trend_lines`, `risk_pattern_lines`, `holdings_observation_lines`,
`spike_view_lines`, `build_market_view`, `build_holdings_view`,
`build_spike_view`).
"""

from __future__ import annotations

from typing import Any

# Re-export — 기존 import 경로 호환 유지.
from app.push_context_holdings import (  # noqa: F401
    build_holdings_view,
    holdings_observation_lines,
)
from app.push_context_market import (  # noqa: F401
    build_market_view,
    market_trend_lines,
    overnight_us_lines,
    risk_pattern_lines,
)
from app.push_context_spike import (  # noqa: F401
    build_spike_view,
    spike_view_lines,
)


def build_push_context(
    *,
    push_kind: str,
    pc_evidence: dict[str, Any],
    runtime_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """push_kind 별 push_context dict 빌더. message builder 가 본 결과를 받아
    message_text 를 생성한다.

    빈 view 는 키 자체 생략 — runtime_package._evaluate_generation_status 가
    "view 존재 = 의미 있는 관찰 1건 이상" 으로 판단할 수 있도록.
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
