"""POC2 Step 6 — universe momentum refresh orchestration (bounded sync).

설계자 결정 (Step 6 §7):
- 동기 수동 refresh. 백그라운드 워커 / 스케줄러 / 재시도 루프 절대 미도입.
- MAX_UNIVERSE_ITEMS_PER_REFRESH = 20 — seed items 20개 초과 시 hard fail.
- PYKRX_PER_TICKER_DELAY_SECONDS = 0.5 — ticker 별 호출 사이 delay.
- UNIVERSE_REFRESH_TIME_BUDGET_SECONDS = 30 — 전체 budget. 초과 시 남은 후보 미계산
  처리하고 partial 결과 저장.
- candidate 단위 실패 격리 — 한 ticker 실패가 전체 refresh 를 중단하지 않는다.
- pykrx 호출은 app.price_history_pykrx 의 fetch_one_month_basis 만 사용한다.

역할 경계:
- 본 모듈은 seed → candidate scoring → momentum_result 조립까지 담당.
- API layer (app.api) 는 본 모듈의 run_universe_refresh() 를 호출하기만 한다.
- 저장 (atomic write to latest artifact) 은 app.momentum.universe_mode.save_latest_artifact.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

from app.price_history_pykrx import (
    DEFAULT_FETCH_WINDOW_DAYS,
    DEFAULT_LOOKBACK_DAYS,
    PriceHistoryBasis,
    PriceHistoryFailure,
    PriceHistoryResult,
    compute_one_month_return_pct,
    fetch_one_month_basis,
)
from app.universe_seed import UniverseSeed, UniverseSeedItem

# Step 6 §7 고정값.
MAX_UNIVERSE_ITEMS_PER_REFRESH = 20
PYKRX_PER_TICKER_DELAY_SECONDS = 0.5
UNIVERSE_REFRESH_TIME_BUDGET_SECONDS = 30.0

# Step 7C §3.2 — 급락 ETF 주의 신호 (PUSH 3) 초기 기준값.
# **확정값 아님 / 운영 검증 필요** — 너무 민감하면 알림 과다 (KS-5), 너무 둔하면 신호
# 지연. BACKLOG "급락 임계값 검증" 항목과 연결.
FALLING_THRESHOLD_PCT = -10.0


class UniverseRefreshError(ValueError):
    """seed-level hard fail (>20 items 등). API layer 가 422 로 변환."""


@dataclass
class CandidateScore:
    """ticker 1건의 scoring 결과 — universe_mode candidate dict 빌더 입력."""

    item: UniverseSeedItem
    is_scored: bool
    score_value: Optional[float]  # %, 음수 가능
    basis: Optional[PriceHistoryBasis]
    exclusion_reason: Optional[str]


def _classify_failure(
    failure: PriceHistoryFailure,
) -> str:
    """PriceHistoryFailure → exclusion_reason 사람이 읽는 짧은 라벨."""
    if failure.reason == "no_data":
        return "pykrx 데이터 없음"
    if failure.reason == "no_base_close":
        return "1개월 전 거래일 데이터 없음"
    if failure.reason == "asof_invalid":
        return "asof 형식 오류"
    return "pykrx 조회 실패"


def _budget_exceeded_score(item: UniverseSeedItem) -> CandidateScore:
    return CandidateScore(
        item=item,
        is_scored=False,
        score_value=None,
        basis=None,
        exclusion_reason="time_budget_exceeded",
    )


def score_candidates(
    seed: UniverseSeed,
    fetcher: Optional[Callable[[str, str], PriceHistoryResult]] = None,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    delay_seconds: Optional[float] = None,
    time_budget_seconds: Optional[float] = None,
    fetch_window_days: int = DEFAULT_FETCH_WINDOW_DAYS,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> list[CandidateScore]:
    """seed.items 각각에 대해 1개월 수익률을 계산하고 CandidateScore 리스트 반환.

    시간 예산 / delay / 예외 격리는 본 함수가 책임.
    fetcher / sleeper / clock 는 테스트에서 주입 — 기본값은 실제 pykrx + time.

    동작:
    - 시작 시각 기록. 각 ticker 처리 전 budget 체크 → 초과면 나머지 모두
      time_budget_exceeded 표시.
    - delay 는 첫 ticker 직후부터 적용 (마지막 ticker 직후 delay 는 생략).
    - 단일 ticker 의 fetch 예외는 fetcher 가 PriceHistoryFailure 반환으로 처리.
    """
    # delay / budget 기본값은 호출 시점에 모듈 상수에서 lookup — 테스트에서
    # monkeypatch 로 모듈 상수를 바꿀 수 있도록 default 인자 평가 시점을 회피한다.
    if delay_seconds is None:
        delay_seconds = PYKRX_PER_TICKER_DELAY_SECONDS
    if time_budget_seconds is None:
        time_budget_seconds = UNIVERSE_REFRESH_TIME_BUDGET_SECONDS

    # fetcher 기본값: 실제 pykrx 모듈 호출 (lookback / fetch_window 주입).
    if fetcher is None:

        def _default_fetcher(ticker: str, asof: str) -> PriceHistoryResult:
            return fetch_one_month_basis(
                ticker=ticker,
                asof=asof,
                fetch_window_days=fetch_window_days,
                lookback_days=lookback_days,
            )

        fetcher = _default_fetcher

    started = clock()
    deadline = started + time_budget_seconds

    scores: list[CandidateScore] = []
    for idx, item in enumerate(seed.items):
        if clock() >= deadline:
            scores.append(_budget_exceeded_score(item))
            continue

        # delay: 첫 ticker 는 즉시 호출, 이후 ticker 호출 직전 delay 적용.
        if idx > 0 and delay_seconds > 0:
            sleeper(delay_seconds)
            if clock() >= deadline:
                scores.append(_budget_exceeded_score(item))
                continue

        try:
            result = fetcher(item.ticker, seed.asof)
        except Exception as e:  # noqa: BLE001 — 외부 의존 광범위 예외 격리
            scores.append(
                CandidateScore(
                    item=item,
                    is_scored=False,
                    score_value=None,
                    basis=None,
                    exclusion_reason=f"pykrx 조회 실패: {e}",
                )
            )
            continue

        if isinstance(result, PriceHistoryFailure):
            scores.append(
                CandidateScore(
                    item=item,
                    is_scored=False,
                    score_value=None,
                    basis=None,
                    exclusion_reason=_classify_failure(result),
                )
            )
            continue

        # success
        score_value = compute_one_month_return_pct(result)
        scores.append(
            CandidateScore(
                item=item,
                is_scored=True,
                score_value=score_value,
                basis=result,
                exclusion_reason=None,
            )
        )

    return scores


def determine_refresh_status(scores: list[CandidateScore]) -> str:
    """ok / partial / failed 결정.

    - ok      : 모든 candidate 가 is_scored=True
    - partial : 일부만 scored
    - failed  : scored 가 0건 (전체 실패)
    """
    if not scores:
        return "failed"
    scored = sum(1 for s in scores if s.is_scored)
    if scored == 0:
        return "failed"
    if scored == len(scores):
        return "ok"
    return "partial"


def validate_seed_for_refresh(seed: UniverseSeed) -> None:
    """seed-level hard fail 검증 — items 20개 초과 시 UniverseRefreshError.

    asof / source / items 형식 검증은 universe_seed.parse_universe_seed 이미 통과.
    본 함수는 Step 6 §7 의 bounded refresh 정책 (20개 cap) 만 추가 검증한다.
    """
    if len(seed.items) > MAX_UNIVERSE_ITEMS_PER_REFRESH:
        raise UniverseRefreshError(
            f"seed items 가 {MAX_UNIVERSE_ITEMS_PER_REFRESH}개를 초과했습니다 "
            f"(received: {len(seed.items)}). 무리한 외부 호출을 방지하기 위해 "
            "조용히 자르지 않고 hard fail 처리합니다."
        )


def run_universe_refresh(
    seed: UniverseSeed,
    fetcher: Optional[Callable[[str, str], PriceHistoryResult]] = None,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    delay_seconds: Optional[float] = None,
    time_budget_seconds: Optional[float] = None,
    fetch_window_days: int = DEFAULT_FETCH_WINDOW_DAYS,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> tuple[list[CandidateScore], str]:
    """seed → scores + refresh_status. seed-level hard fail 은 호출 전 차단된 상태 가정.

    호출자는 validate_seed_for_refresh(seed) 를 본 함수 호출 전에 수행해야 한다.
    """
    scores = score_candidates(
        seed=seed,
        fetcher=fetcher,
        sleeper=sleeper,
        clock=clock,
        delay_seconds=delay_seconds,
        time_budget_seconds=time_budget_seconds,
        fetch_window_days=fetch_window_days,
        lookback_days=lookback_days,
    )
    refresh_status = determine_refresh_status(scores)
    return scores, refresh_status


def build_failure_summary_reason(
    seed: UniverseSeed,
    scores: list[CandidateScore],
) -> str:
    """전체 실패 시 summary_reason_text — pykrx 데이터 부족 등 사유 요약.

    AC-10: 전체 실패 시 실패 사유가 universe_momentum_latest.json 에 남는다.
    """
    if not scores:
        return f"pykrx 가격 데이터 부족으로 1개월 점검값을 계산하지 못했습니다 (asof {seed.asof})."
    # 다수가 동일 reason 인지 보고. 가장 흔한 사유 1개를 선택.
    counts: dict[str, int] = {}
    for s in scores:
        if s.exclusion_reason:
            counts[s.exclusion_reason] = counts.get(s.exclusion_reason, 0) + 1
    if counts:
        top_reason = max(counts.items(), key=lambda kv: kv[1])[0]
    else:
        top_reason = "원인 불명"
    return (
        f"pykrx 가격 데이터 부족으로 {len(scores)}개 후보 모두 1개월 점검값을 "
        f"계산하지 못했습니다 (asof {seed.asof}, 주된 사유: {top_reason})."
    )
