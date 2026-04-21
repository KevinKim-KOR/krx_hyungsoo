"""비중 관련 보조 유틸리티 모듈.

현재 순위 화면에서는 직접 사용하지 않지만,
실보유 자산 보조 계산에 재사용할 수 있는 공통 함수를 둡니다.
"""

from __future__ import annotations


def calculate_score_weights(
    scores: dict[str, float],
    *,
    min_weight: float = 0.10,
    max_weight: float = 0.30,
) -> dict[str, float]:
    """점수 기반 비중 계산용 보조 함수입니다.

    1. 음수 점수는 0으로 치환
    2. 점수 비례로 비중 산출
    3. MIN/MAX 가드레일 적용 후 정규화(합계=1.0)

    Args:
        scores: {대상 ID: 점수} 딕셔너리
        min_weight: 대상당 최소 비중
        max_weight: 대상당 최대 비중

    Returns:
        {대상 ID: 목표 비중} 딕셔너리, 합계 1.0

    Raises:
        ValueError: 유효한 대상이 없는 경우
    """
    if not scores:
        raise ValueError("비중 계산에 필요한 종목 점수가 없습니다.")

    n = len(scores)
    if n == 0:
        raise ValueError("비중 계산에 필요한 종목 점수가 없습니다.")

    # 가드레일 유효성 검사
    if min_weight <= 0:
        raise ValueError("최소 비중은 0보다 커야 합니다.")
    if max_weight <= 0:
        raise ValueError("최대 비중은 0보다 커야 합니다.")
    if max_weight < min_weight:
        raise ValueError("최대 비중은 최소 비중보다 크거나 같아야 합니다.")
    if min_weight * n > 1.0:
        raise ValueError(
            f"최소 비중 {min_weight:.2%}는 대상 수 {n}개와 양립할 수 없습니다. 설정을 낮추거나 대상 수를 줄이세요."
        )
    if max_weight * n < 1.0:
        raise ValueError(
            f"최대 비중 {max_weight:.2%}는 대상 수 {n}개를 합쳐도 100%를 채울 수 없습니다. 설정을 높이세요."
        )

    # 1단계: 음수 점수는 0으로 치환
    clamped: dict[str, float] = {ticker: max(score, 0.0) for ticker, score in scores.items()}

    total_score = sum(clamped.values())

    # 모든 점수가 0이면 균등 배분
    if total_score <= 0:
        equal_weight = 1.0 / n
        return {ticker: equal_weight for ticker in scores}

    # 2단계: 점수 비례 비중 계산
    raw_weights: dict[str, float] = {ticker: score / total_score for ticker, score in clamped.items()}

    # 3단계: 가드레일 적용 (반복적 정규화)
    weights = _apply_guardrails(raw_weights, min_weight, max_weight)

    return weights


def _apply_guardrails(
    raw_weights: dict[str, float],
    min_weight: float,
    max_weight: float,
) -> dict[str, float]:
    """MIN/MAX 가드레일을 적용하고 합계를 1.0으로 정규화합니다.

    기본적으로는 모든 종목에 최소 비중을 먼저 할당한 뒤,
    남는 비중만 점수 비례로 추가 배분합니다.
    상한에 도달한 종목은 제외하고 반복 배분하여 합계 1.0을 맞춥니다.
    """
    tickers = list(raw_weights.keys())
    weights = {ticker: float(min_weight) for ticker in tickers}
    remaining = 1.0 - (len(tickers) * min_weight)
    if remaining <= 1e-12:
        return weights

    capacity = {ticker: float(max_weight - min_weight) for ticker in tickers}
    active = {ticker for ticker, cap in capacity.items() if cap > 1e-12}
    extras = {ticker: max(float(raw_weights.get(ticker, 0.0)) - min_weight, 0.0) for ticker in tickers}

    while remaining > 1e-12 and active:
        active_total = sum(extras[ticker] for ticker in active)
        if active_total <= 1e-12:
            equal_share = remaining / len(active)
            progressed = False
            for ticker in list(active):
                addable = min(equal_share, capacity[ticker])
                if addable > 0:
                    weights[ticker] += addable
                    capacity[ticker] -= addable
                    remaining -= addable
                    progressed = True
                if capacity[ticker] <= 1e-12:
                    active.remove(ticker)
            if not progressed:
                break
            continue

        progressed = False
        for ticker in list(active):
            desired = remaining * (extras[ticker] / active_total)
            addable = min(desired, capacity[ticker])
            if addable > 0:
                weights[ticker] += addable
                capacity[ticker] -= addable
                remaining -= addable
                progressed = True
            if capacity[ticker] <= 1e-12:
                active.remove(ticker)
        if not progressed:
            break

    total = sum(weights.values())
    if abs(total - 1.0) > 1e-9:
        deficit = 1.0 - total
        candidates = [ticker for ticker in tickers if weights[ticker] < max_weight - 1e-12]
        if candidates and deficit > 0:
            per_ticker = deficit / len(candidates)
            for ticker in candidates:
                weights[ticker] += min(per_ticker, max_weight - weights[ticker])

    return weights


def should_rebalance(
    current_weights: dict[str, float],
    target_weights: dict[str, float],
    buffer: float = 0.02,
) -> dict[str, bool]:
    """종목별 비중 차이가 버퍼를 넘는지 판단합니다.

    |현재비중 - 목표비중| > buffer 인 종목만 True를 반환합니다.

    Args:
        current_weights: {ticker: 현재 비중}
        target_weights: {ticker: 목표 비중}
        buffer: 비중 차이 허용 버퍼 (기본 2%)

    Returns:
        {ticker: 비중 조정 필요 여부}
    """
    result: dict[str, bool] = {}
    all_tickers = set(current_weights) | set(target_weights)

    for ticker in all_tickers:
        current = current_weights.get(ticker, 0.0)
        target = target_weights.get(ticker, 0.0)
        result[ticker] = abs(current - target) > buffer

    return result
