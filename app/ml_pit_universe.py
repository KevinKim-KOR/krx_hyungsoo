"""POC4-02A — KRX PIT universe · 이름 필터 · 편입 가능 · 제외 사유 (PLAN §3 · §4 · §6).

`docs/ai_plan/POC4/POC4-02A_KRX_PIT_UNIVERSE_BIAS_PLAN_V1.md` 의 확정 계약을 코드로 옮긴다.

- arm — PIT = 봉인 panel 의 전 종목(069500 제외) · CONTROL = 최종일(`panel.final_date`)에 행이 있는
  종목(069500 제외). 날짜 t 의 universe = arm 종목 중 t 에 v1 행이 있는 종목 (A5).
- 필터 — `classify_etf_tags(t 행 ISU_NM)` 의 inverse·leveraged·synthetic·futures 제외 (A4).
  현재 `etf_master` 는 읽지 않는다.
- 편입 가능(coverage 분모) — universe ∩ 필터 ∩ `is_pit_eligible` (A7). `is_pit_eligible` 은 t 상장을
  보지 않으므로 호출자가 universe(t 행 존재)로 먼저 감싼다 (PLAN §2-13).
- 제외 사유 — 한 쌍(t × 종목)은 PLAN §3 순서의 첫 사유 하나로만 센다. 다음 거래일로 미루거나
  마지막 체결가를 청산가로 대체하지 않는다.

DB·파일에 접근하지 않는다 — 봉인 reader 가 만든 메모리 panel 만 읽는다.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from typing import Optional

from app.krx_sealed_reader import (
    BENCHMARK_CODE,
    CLOSE_OK,
    NO_VALID_CLOSE,
    NON_POSITIVE_CLOSE,
    CodeSeries,
    SealedPanel,
)
from app.market_topn_helpers import classify_etf_tags
from app.ml_relative_upside_features import RETURN_LOOKBACK_20D
from app.ml_score_validity_eval import (
    MIN_OBSERVATIONS,
    RebalancePoint,
    is_filter_universe,
    is_pit_eligible,
)

ARM_PIT = "PIT"
ARM_CONTROL = "CONTROL"
ARMS = (ARM_PIT, ARM_CONTROL)

# --- 제외 사유 (PLAN §3 표 순서) ------------------------------------------------
NON_TRADING_DATE = "NON_TRADING_DATE"  # 달력 = v1 member 날짜 → 구조상 0
NOT_YET_LISTED = "NOT_YET_LISTED"  # CONTROL 전용 · 필터 전 수에만
BASEPRICE_RELATION_MISMATCH = "BASEPRICE_RELATION_MISMATCH"
INSUFFICIENT_WARMUP = "INSUFFICIENT_WARMUP"
NO_ENTRY_PRICE = "NO_ENTRY_PRICE"
ZERO_VOLUME_ENTRY = "ZERO_VOLUME_ENTRY"
NO_FORWARD_EXIT_PRICE = "NO_FORWARD_EXIT_PRICE"
ZERO_VOLUME_EXIT = "ZERO_VOLUME_EXIT"
BENCHMARK_UNAVAILABLE = "BENCHMARK_UNAVAILABLE"
HISTORICAL_FILTER_UNAVAILABLE = "HISTORICAL_FILTER_UNAVAILABLE"
NO_MODEL = "NO_MODEL"  # 판정 목록 밖 — 학습·검증 행이 없어 모델이 없는 날 (구현 정의 3)

REASON_CODES = (
    NON_TRADING_DATE,
    NOT_YET_LISTED,
    NO_VALID_CLOSE,
    NON_POSITIVE_CLOSE,
    BASEPRICE_RELATION_MISMATCH,
    INSUFFICIENT_WARMUP,
    NO_ENTRY_PRICE,
    ZERO_VOLUME_ENTRY,
    NO_FORWARD_EXIT_PRICE,
    ZERO_VOLUME_EXIT,
    BENCHMARK_UNAVAILABLE,
    HISTORICAL_FILTER_UNAVAILABLE,
    NO_MODEL,
)

# feature 창 = t−20..t (return_20d 가 t−20 행을 쓴다) · warm-up = t 까지 유효 행 21개.
FEATURE_WINDOW_ROWS = RETURN_LOOKBACK_20D
WARMUP_MIN_ROWS = MIN_OBSERVATIONS


def empty_reasons() -> dict[str, int]:
    """사유별 0 — 결과 표의 키 집합을 날짜·arm 마다 같게 둔다."""
    return {code: 0 for code in REASON_CODES}


# --- 종목별 누적 사실 (한 번 만들어 날짜마다 O(1) 로 본다) ------------------------


@dataclass
class SeriesFacts:
    """한 종목의 누적 수 — `valid_prefix[i]` = 0..i 의 유효 종가 행 수, `bad_prefix[i]` = 0..i 의
    관계 불일치 행 수(`relation_ok` 거짓 · 종가 무효 행 포함). `valid_history` = 유효 종가 행의
    (날짜, 연결값) — `is_pit_eligible` 입력."""

    valid_prefix: list[int] = field(default_factory=list)
    bad_prefix: list[int] = field(default_factory=list)
    valid_history: list[tuple[str, float]] = field(default_factory=list)
    valid_dates: list[str] = field(default_factory=list)

    def bad_between(self, lo: int, hi: int) -> bool:
        """행 index lo..hi(양끝 포함) 에 관계 불일치 행이 있는가."""
        lo = max(lo, 0)
        before = self.bad_prefix[lo - 1] if lo > 0 else 0
        return self.bad_prefix[hi] - before > 0


def build_facts(series: CodeSeries) -> SeriesFacts:
    facts = SeriesFacts()
    valid = bad = 0
    for i, date in enumerate(series.dates):
        ok = series.close_status[i] == CLOSE_OK
        valid += ok
        bad += not series.relation_ok[i]
        facts.valid_prefix.append(valid)
        facts.bad_prefix.append(bad)
        if ok:
            facts.valid_history.append((date, series.chain[i]))
            facts.valid_dates.append(date)
    return facts


# --- arm · universe · 필터 · 편입 가능 -----------------------------------------------


def arm_codes(panel: SealedPanel, arm: str) -> tuple[str, ...]:
    """arm 의 종목 전체 (069500 제외 · 정렬). 학습 행은 이 종목 전부의 t 절단 이력이다."""
    if arm == ARM_PIT:
        codes = set(panel.series)
    elif arm == ARM_CONTROL:
        codes = set(panel.present(panel.final_date))
    else:
        raise ValueError(f"알 수 없는 arm: {arm}")
    codes.discard(BENCHMARK_CODE)
    return tuple(sorted(codes))


def universe_at(panel: SealedPanel, codes: tuple[str, ...], date: str) -> list[str]:
    """t 에 v1 행이 있는 arm 종목 (정렬 유지). 미래 상장·이미 폐지된 종목은 들어오지 않는다."""
    present = panel.present(date)
    return [c for c in codes if c in present]


def name_at(series: CodeSeries, date: str) -> str:
    """t 행 ISU_NM (그날 이름 · 앞뒤 공백 제거)."""
    return (series.name[series.index[date]] or "").strip()


def passes_name_filter(name: str) -> bool:
    """인버스·레버리지·합성·선물이 아니면 True — 화면·E2 필터와 같은 함수."""
    return is_filter_universe(classify_etf_tags(name))


def is_eligible(facts: SeriesFacts, date: str, day_index: dict[str, int]) -> bool:
    """`is_pit_eligible`(유효 종가 21개 · 첫 종가 후 20거래일) — universe·필터는 호출자가 먼저 본다.

    `is_pit_eligible` 은 t 이하 날짜 수와 첫 날짜만 보므로 t 이하로 자른 이력을 넘겨도 결과가 같다.
    """
    upto = bisect.bisect_right(facts.valid_dates, date)
    return is_pit_eligible(facts.valid_history[:upto], date, day_index)


def has_volume(volume: Optional[float]) -> bool:
    """주 성과 진입·청산 조건 `ACC_TRDVOL > 0` (빈 값은 조건 불충족)."""
    return volume is not None and volume > 0


# --- 제외 사유 판정 ----------------------------------------------------------------


@dataclass(frozen=True)
class PairOutcome:
    """한 쌍의 판정 — `reason` 이 None 이면 주 label 이 있다."""

    reason: Optional[str]
    label: Optional[float]
    sensitivity_label: Optional[float]


def pre_score_reason(
    series: CodeSeries, facts: SeriesFacts, date: str
) -> Optional[str]:
    """점수 앞 단계 — 이름 → t 행 종가 → warm-up → feature 창(t−20..t) 관계 검증."""
    i = series.index[date]
    if not name_at(series, date):
        return HISTORICAL_FILTER_UNAVAILABLE
    if series.close_status[i] != CLOSE_OK:
        return series.close_status[i]  # NO_VALID_CLOSE · NON_POSITIVE_CLOSE
    if facts.valid_prefix[i] < WARMUP_MIN_ROWS:
        return INSUFFICIENT_WARMUP
    if facts.bad_between(i - FEATURE_WINDOW_ROWS, i):
        return BASEPRICE_RELATION_MISMATCH
    return None


def benchmark_pair(
    bench: CodeSeries, bench_facts: SeriesFacts, entry_date: str, exit_date: str
) -> Optional[tuple[float, float]]:
    """069500 연결값 (진입, 청산) — 두 행이 있고 사이에 관계 불일치가 없을 때만."""
    ie, ix = bench.index.get(entry_date), bench.index.get(exit_date)
    if ie is None or ix is None or ix < ie:
        return None
    if bench_facts.bad_between(ie, ix) or bench.segment[ie] != bench.segment[ix]:
        return None
    k0, k1 = bench.chain[ie], bench.chain[ix]
    if k0 is None or k1 is None:
        return None
    return k0, k1


def label_outcome(
    series: CodeSeries,
    facts: SeriesFacts,
    bench_pair: Optional[tuple[float, float]],
    point: RebalancePoint,
    *,
    require_volume: bool,
) -> tuple[Optional[str], Optional[float]]:
    """진입 행 → 진입 거래량 → 청산 행 → 청산 거래량 → 보유 구간 관계 → 벤치마크 → label.

    label = (C_exit/C_entry − 1) − (K_exit/K_entry − 1) — `forward_excess` 와 같은 식(연결 계열).
    `require_volume=False` 는 `OFFICIAL_REFERENCE_SENSITIVITY` (거래량 조건만 뺀다 · 행은 있어야 한다).
    """
    ie = series.index.get(point.entry_date)
    if ie is None:
        return NO_ENTRY_PRICE, None
    if require_volume and not has_volume(series.volume[ie]):
        return ZERO_VOLUME_ENTRY, None
    ix = series.index.get(point.exit_date)
    if ix is None:
        return NO_FORWARD_EXIT_PRICE, None
    if require_volume and not has_volume(series.volume[ix]):
        return ZERO_VOLUME_EXIT, None
    if facts.bad_between(ie, ix) or series.segment[ie] != series.segment[ix]:
        return BASEPRICE_RELATION_MISMATCH, None
    if bench_pair is None:
        return BENCHMARK_UNAVAILABLE, None
    p0, p1 = series.chain[ie], series.chain[ix]
    k0, k1 = bench_pair
    return None, (p1 / p0 - 1.0) - (k1 / k0 - 1.0)


def classify_pair(
    series: CodeSeries,
    facts: SeriesFacts,
    point: RebalancePoint,
    bench_pair: Optional[tuple[float, float]],
    *,
    has_model: bool,
    scored: bool,
) -> PairOutcome:
    """universe 종목 하나의 판정 (PLAN §3 순서 · 첫 사유 하나).

    점수 앞 사유가 없는데 모델이 없으면 `NO_MODEL`. 모델이 있는데 점수가 없으면 t 행 feature 의
    069500 값이 없다는 뜻이라 `BENCHMARK_UNAVAILABLE` 로 센다(warm-up·관계 검증을 통과한 행은
    벤치마크 외에는 feature 가 빠질 수 없다).
    """
    reason = pre_score_reason(series, facts, point.signal_date)
    if reason is None and not has_model:
        reason = NO_MODEL
    if reason is None and not scored:
        reason = BENCHMARK_UNAVAILABLE
    if reason is not None:
        return PairOutcome(reason, None, None)
    main_reason, label = label_outcome(
        series, facts, bench_pair, point, require_volume=True
    )
    _sens_reason, sens = label_outcome(
        series, facts, bench_pair, point, require_volume=False
    )
    return PairOutcome(main_reason, label, sens)
