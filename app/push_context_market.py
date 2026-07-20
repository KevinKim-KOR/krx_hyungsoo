"""POC2 Cleanup — push_context market_view + 관련 line helper 분리 (2026-06-14).

3-PUSH Message Text Runtime Evidence 반영 STEP 의 KS-10 trigger 해소를 위해
`app/push_context.py` 의 market 책임을 본 모듈로 분리. 산식 / 문구 / 데이터 계약
변경 0건 — 함수 시그니처와 본문은 그대로 유지.

본 모듈은 다음 공개 helper 를 제공한다:

- `build_market_view` — PUSH-1 market_view dict (orchestration 진입점에서 호출).
- `overnight_us_lines` — message builder 용 [밤사이 미국 시장] 다중 라인.
- `market_trend_lines` — Market Discovery 흐름 1줄 섹션.
- `risk_pattern_lines` — ML baseline 룩백 1줄 섹션.
"""

from __future__ import annotations

from typing import Any, Optional

from app.push_context_format import (
    _US_SECTOR_HINTS,
    _candidate_name,
    _candidate_return_pct,
    _candidate_ticker,
    _fmt_pct,
    _has_data,
    _topn_candidates,
)

# 사용자 화면 노출용 basis 라벨 매핑 (내부 identifier → 사용자 이해 가능 문구).
# Holdings-Market PENDING Judgment Draft v1 REJECTED r2/r3 정정.
#
# 매핑 목록은 `app.market_topn_helpers.ALLOWED_BASIS` (daily · one_month ·
# three_month) 를 포함해야 한다. 미등록 basis 는 아래 `_basis_user_label`
# 함수가 라벨 자체를 생략 (내부 값 노출 방지). 계약: 내부 basis identifier 는
# 어떤 경우에도 사용자 화면에 원문 그대로 나타나지 않는다.
_BASIS_USER_LABEL: dict[str, str] = {
    "daily": "일간",
    "one_month": "최근 1개월",
    "three_month": "최근 3개월",
    "six_month": "최근 6개월",
    "one_year": "최근 1년",
    "1m": "최근 1개월",
    "3m": "최근 3개월",
    "6m": "최근 6개월",
    "1y": "최근 1년",
}


def _basis_user_label(basis: str) -> str:
    """미등록 basis 는 내부 값 노출 대신 빈 문자열 반환.

    호출자는 반환값이 빈 문자열이면 라벨 자체를 생략한다.
    """
    return _BASIS_USER_LABEL.get(basis, "")


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
    # Holdings-Market PENDING Judgment Draft v1 REJECTED r2/r3 정정:
    # basis 는 내부 identifier. 사용자 화면 문구는 매핑된 사용자 이해 가능한
    # 라벨로 표시하고, 매핑에 없는 값은 라벨 자체를 생략 (내부 값 노출 방지).
    # 내부 basis 값 자체는 dict return 에 그대로 보존 (계약 유지).
    basis_label = _basis_user_label(basis)
    top = sortable[:3]
    bot = sortable[-3:][::-1]
    text_parts: list[str] = []
    if top:
        head = ", ".join(f"{_candidate_name(c)} {_fmt_pct(p)}" for c, p in top)
        text_parts.append(
            f"상위 ({basis_label}): {head}" if basis_label else f"상위: {head}"
        )
    if bot:
        tail = ", ".join(f"{_candidate_name(c)} {_fmt_pct(p)}" for c, p in bot)
        text_parts.append(
            f"하위 ({basis_label}): {tail}" if basis_label else f"하위: {tail}"
        )
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
    # 있다. 절대값이 1.5 미만이면 ratio 로 보고 ×100 하여 % 로 정규화.
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
    상위 호출자가 market_view 를 "있는 것" 으로 오인하지 않도록).
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


def overnight_us_lines(push_context: Optional[dict[str, Any]]) -> list[str]:
    """message builder 용 — push_context.market_view.observations 안의
    overnight_us 관측을 사람이 읽는 다중 라인 요약으로 변환.

    실제 close / change_pct + 섹터 해석 1줄 노출. probe 실패 indices 는 행 생략.
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
    """message builder 용 — push_context.market_view 의 market_trend
    observation 을 1~2줄 관찰로 변환.
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
    """message builder 용 — push_context.market_view 의 risk_pattern
    observation 을 1줄로 변환."""
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
