"""Universe Momentum Runtime 재평가 helper (Low-Frequency Telegram Push Operation v1 · Unit 3).

목적: 이미 publish 된 `universe_momentum_latest.json` artifact 의 Published
Evidence (spike_trigger_type · spike_direction · falling_threshold_pct ·
price_history_basis.base_close · base_date · evidence_as_of) 와 실행 시점 현재
가격을 사용해 **기존 falling threshold 조건만** 재평가한다.

허용:
- artifact 의 published trigger_type · direction · threshold · base_close 재사용
- Runtime 현재 가격 (market_quotes) 으로 최신 return_pct 계산
- 신규 signal 판정 (return_pct <= threshold_pct)

금지 (A+ 재작업 계약):
- 신규 factor · 신규 threshold · 신규 ranking 산출
- Universe 전체 재계산 (외부 batch 재실행)
- 후보 재선정 · 필터 변경
- artifact.candidates 순서 재정렬
- **필수 Published Evidence 누락 시 암묵 기본값 대체 (예: threshold -10.0)**
- **가격 조회 실패를 no_signal 로 오인**

반환:
    ReevaluationResult(signals, status, missing_fields, quote_missing_tickers)

    status:
      "ok"      — 필수 evidence 모두 있고 대상 candidate 전부 재평가 완료.
      "partial" — 일부 candidate 만 재평가 (가격 조회 실패 또는 per-candidate
                   evidence 필드 누락). 재평가된 부분의 signals 는 유효.
      "failed"  — Published Evidence 상위 필수 필드 (trigger_type / direction /
                   threshold_pct) 자체 누락. signals 는 항상 [] 반환.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class SpikeSignal:
    """단일 종목의 재평가 결과. Runner 가 fingerprint 로 중복 차단."""

    ticker: str
    name: str
    trigger_type: str
    direction: str
    fingerprint: str  # ticker#trigger_type#direction (date/param_id 는 Runner 접두)
    runtime_return_pct: float
    runtime_price: float
    price_asof: Optional[str]
    base_close: float
    base_date: Optional[str]
    threshold_pct: float
    evidence_as_of: Optional[str]


@dataclass
class ReevaluationResult:
    signals: list[SpikeSignal] = field(default_factory=list)
    status: str = "ok"  # ok / partial / failed
    missing_fields: list[str] = field(default_factory=list)  # 상위 evidence 누락
    quote_missing_tickers: list[str] = field(default_factory=list)  # 가격 없음
    candidate_missing_fields: dict[str, list[str]] = field(default_factory=dict)
    # 재평가 대상이었던 (is_scored=True) candidate 수 — Runner partial 판정용.
    scored_candidate_count: int = 0


def _make_fingerprint(ticker: str, trigger_type: str, direction: str) -> str:
    """Signal fingerprint. 날짜/param_id 는 Runner registry key 에서 붙인다."""
    return f"{ticker}#{trigger_type}#{direction}"


def reevaluate_spike_signals(
    artifact: dict[str, Any],
    market_quotes: dict[str, Any],
    *,
    runtime_date_kst: str,
) -> ReevaluationResult:
    """artifact + Runtime 가격으로 Published Evidence 기반 재평가.

    - artifact.summary.spike_trigger_type / spike_direction / falling_threshold_pct
      셋 중 하나라도 없으면 status=failed, signals=[].
    - artifact.candidates 의 `is_scored=True` 항목만 대상.
    - candidate 별 필수 필드 (base_close 유효값) 누락 시 candidate_missing_fields
      에 기록하고 skip.
    - market_quotes[ticker].current_price 없으면 quote_missing_tickers 에 기록하고
      skip. no_signal 로 오인하지 않는다 (partial status 로 상위 판정).
    - threshold 재평가 결과 return_pct <= threshold_pct 인 경우만 SpikeSignal.
    - 반환 순서는 artifact.candidates 순서 그대로.
    """
    result = ReevaluationResult()

    if not isinstance(artifact, dict):
        result.status = "failed"
        result.missing_fields = ["artifact"]
        return result

    summary = artifact.get("summary") or {}
    trigger_type = summary.get("spike_trigger_type")
    direction = summary.get("spike_direction")
    threshold_raw = summary.get("falling_threshold_pct")
    evidence_as_of = summary.get("evidence_as_of")

    missing: list[str] = []
    if not isinstance(trigger_type, str) or not trigger_type:
        missing.append("spike_trigger_type")
    if not isinstance(direction, str) or not direction:
        missing.append("spike_direction")
    if not isinstance(threshold_raw, (int, float)):
        missing.append("falling_threshold_pct")
    if not isinstance(evidence_as_of, str) or not evidence_as_of:
        missing.append("evidence_as_of")
    if missing:
        result.status = "failed"
        result.missing_fields = missing
        return result

    threshold_pct = float(threshold_raw)

    scored_count = 0
    for c in artifact.get("candidates") or []:
        if not isinstance(c, dict):
            continue
        score_result = c.get("score_result") or {}
        if not score_result.get("is_scored"):
            continue
        ticker = c.get("ticker")
        if not isinstance(ticker, str) or not ticker:
            continue
        scored_count += 1

        basis = c.get("price_history_basis") or {}
        base_close = basis.get("base_close")
        base_date = basis.get("base_date")
        cand_missing: list[str] = []
        if not isinstance(base_close, (int, float)) or base_close <= 0:
            cand_missing.append("price_history_basis.base_close")
        if not isinstance(base_date, str) or not base_date:
            cand_missing.append("price_history_basis.base_date")
        if cand_missing:
            result.candidate_missing_fields[ticker] = cand_missing
            continue

        quote = market_quotes.get(ticker)
        if quote is None:
            result.quote_missing_tickers.append(ticker)
            continue
        current_price = getattr(quote, "current_price", None)
        price_asof = getattr(quote, "price_asof", None)
        if current_price is None and isinstance(quote, dict):
            current_price = quote.get("current_price")
            price_asof = quote.get("price_asof")
        if not isinstance(current_price, (int, float)) or current_price <= 0:
            result.quote_missing_tickers.append(ticker)
            continue
        # A+ 재정정: price_asof 필수. 기준시각 없는 가격을 신호 생성 근거로 사용
        # 금지 (사용자에게 언제 값인지 전달 불가). partial 로 처리.
        if not isinstance(price_asof, str) or not price_asof:
            result.quote_missing_tickers.append(ticker)
            continue

        return_pct = (
            (float(current_price) - float(base_close)) / float(base_close) * 100.0
        )
        if return_pct > threshold_pct:
            continue

        name = c.get("name") or ticker
        fingerprint = _make_fingerprint(ticker, trigger_type, direction)
        result.signals.append(
            SpikeSignal(
                ticker=ticker,
                name=name,
                trigger_type=trigger_type,
                direction=direction,
                fingerprint=fingerprint,
                runtime_return_pct=round(return_pct, 4),
                runtime_price=float(current_price),
                price_asof=price_asof if isinstance(price_asof, str) else None,
                base_close=float(base_close),
                base_date=basis.get("base_date"),
                threshold_pct=threshold_pct,
                evidence_as_of=(
                    evidence_as_of if isinstance(evidence_as_of, str) else None
                ),
            )
        )

    result.scored_candidate_count = scored_count
    # partial 판정: 재평가 대상 대비 skip 발생.
    if result.quote_missing_tickers or result.candidate_missing_fields:
        result.status = "partial"
    # runtime_date_kst 는 fingerprint 본문에 포함하지 않는다 (Runner registry key 접두).
    _ = runtime_date_kst
    return result


def format_spike_signal_note(signal: SpikeSignal) -> str:
    """단일 SpikeSignal → 사용자 메시지 fact 한 줄.

    형식: "[신규 {trigger}] {name} ({ticker}): 1개월 -X.XX% (현재가 Y원, {price_asof})"

    A+ 재정정: SpikeSignal 생성 시점 (reevaluator) 에서 price_asof 없는 quote 는
    이미 걸러지므로 signal.price_asof 는 항상 문자열이다. 방어적으로 str 아닐 시
    ValueError raise (Runner 는 이를 계약 위반 → 미발송).
    """
    if not isinstance(signal.price_asof, str) or not signal.price_asof:
        raise ValueError(f"SpikeSignal.price_asof 필수 (ticker={signal.ticker})")
    price_int = int(round(signal.runtime_price))
    return (
        f"[신규 {signal.trigger_type}] {signal.name} ({signal.ticker}): "
        f"1개월 {signal.runtime_return_pct:+.2f}% "
        f"(현재가 {price_int:,}원, {signal.price_asof})."
    )
