# -*- coding: utf-8 -*-
"""
extensions/tuning/types.py
튜닝/검증 체계 v2.1 - 자료구조 정의

문서 참조: docs/tuning/01_metrics_guardrails.md, 02_objective_gates.md
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Any


@dataclass
class BacktestMetrics:
    """
    단일 구간 백테스트 지표

    모든 값은 소수(decimal) 형태로 저장 (UI 표시 시 % 변환)
    """

    sharpe: float = 0.0  # Sharpe Ratio (무단위)
    cagr: float = 0.0  # 연복리 수익률 (소수, 예: 0.25 = 25%)
    mdd: float = 0.0  # 최대 낙폭 (음수, 예: -0.12 = -12%)
    total_return: float = 0.0  # 총 수익률 (소수)
    volatility: float = 0.0  # 연환산 변동성 (소수)
    calmar: float = 0.0  # Calmar Ratio

    # 거래 통계
    num_trades: int = 0  # 매수+매도 거래 횟수 합계
    win_rate: float = 0.0  # 거래 승률 (소수)

    # 추가 지표
    exposure_ratio: float = 0.0  # 포지션 보유일 / 전체 거래일
    annual_turnover: float = 0.0  # 연간 매매 회전율

    # Phase 2.1 추가: 멀티룩백 증거 강화
    signal_days: int = 0  # 신호 발생 일수
    order_count: int = 0  # 주문 횟수
    first_trade_date: Optional[str] = None  # 첫 거래일


class GuardrailFailCode:
    """가드레일 실패 코드 (표준화)"""

    LOW_TRADES = "LOW_TRADES"
    LOW_EXPOSURE = "LOW_EXPOSURE"
    HIGH_TURNOVER = "HIGH_TURNOVER"
    NO_SIGNAL_DAYS = "NO_SIGNAL_DAYS"
    NO_ORDERS = "NO_ORDERS"
    ZERO_SHARPE = "ZERO_SHARPE"
    NEGATIVE_CAGR = "NEGATIVE_CAGR"


@dataclass
class GuardrailChecks:
    """
    가드레일 체크 결과

    문서 참조: docs/tuning/01_metrics_guardrails.md 3.2절
    """

    num_trades: int = 0  # 거래 횟수
    exposure_ratio: float = 0.0  # 노출 비율
    annual_turnover: float = 0.0  # 연간 회전율

    # 임계값 (기본값)
    min_trades: int = 30
    min_exposure: float = 0.30
    max_turnover: float = 24.0

    @property
    def passed(self) -> bool:
        """가드레일 통과 여부"""
        return (
            self.num_trades >= self.min_trades
            and self.exposure_ratio >= self.min_exposure
            and self.annual_turnover <= self.max_turnover
        )

    @property
    def failures(self) -> List[str]:
        """실패한 가드레일 목록 (사람 읽기용)"""
        failures = []
        if self.num_trades < self.min_trades:
            failures.append(f"num_trades({self.num_trades}) < {self.min_trades}")
        if self.exposure_ratio < self.min_exposure:
            failures.append(
                f"exposure_ratio({self.exposure_ratio:.2f}) < {self.min_exposure}"
            )
        if self.annual_turnover > self.max_turnover:
            failures.append(
                f"annual_turnover({self.annual_turnover:.1f}) > {self.max_turnover}"
            )
        return failures

    @property
    def failure_codes(self) -> List[str]:
        """실패한 가드레일 코드 목록 (표준화)"""
        codes = []
        if self.num_trades < self.min_trades:
            codes.append(GuardrailFailCode.LOW_TRADES)
        if self.num_trades == 0:
            codes.append(GuardrailFailCode.NO_ORDERS)
        if self.exposure_ratio < self.min_exposure:
            codes.append(GuardrailFailCode.LOW_EXPOSURE)
        if self.annual_turnover > self.max_turnover:
            codes.append(GuardrailFailCode.HIGH_TURNOVER)
        return codes


@dataclass
class LogicChecks:
    """
    Logic Checks 결과 (v2.1 추가)

    파라미터가 실제로 전략에 영향을 줬는지 검증
    문서 참조: docs/tuning/01_metrics_guardrails.md Logic Checks 정의
    """

    rsi_scale_days: int = 0  # RSI가 비중 조절에 영향을 준 일수
    rsi_scale_events: int = 0  # RSI 기반 비중 조절 횟수

    # 임계값
    min_rsi_scale_days: int = 10
    min_rsi_scale_events: int = 5

    @property
    def rsi_effective(self) -> bool:
        """RSI가 실제로 영향을 줬는지"""
        return self.rsi_scale_days >= self.min_rsi_scale_days


@dataclass
class DebugInfo:
    """
    디버그 정보 (룩백/캐시/파라미터 추적용)

    논쟁 종결용 필드: 룩백이 실제로 어떻게 사용되었는지 기록

    Phase 1.8 추가:
    - lookback_effective_start_date: 전략이 실제로 사용하는 시작점
    - indicator_warmup_days: MA/RSI 계산을 위해 버린 구간

    Phase 2.1 추가 (멀티룩백 증거 강화):
    - effective_eval_start: 룩백 적용 후 성과 계산 시작일
    - bars_used: 룩백 적용 후 실제 계산에 사용된 봉 수
    - signal_days: 신호 발생 일수
    - order_count: 주문 횟수
    """

    lookback_months: int = 0
    lookback_start_date: Optional[date] = None
    params_hash: str = ""
    cache_key: str = ""
    period_signature: str = ""  # "train:YYYY-MM-DD~YYYY-MM-DD|val:..."

    # Phase 1.8 추가: 룩백 의미 검증용
    lookback_effective_start_date: Optional[date] = (
        None  # 전략이 실제로 사용하는 시작점
    )
    indicator_warmup_days: int = 0  # MA/RSI 계산을 위해 버린 구간

    # Phase 2.1 추가: 멀티룩백 증거 강화
    effective_eval_start: Optional[date] = None  # 룩백 적용 후 성과 계산 시작일
    bars_used: int = 0  # 룩백 적용 후 실제 계산에 사용된 봉 수
    signal_days: int = 0  # 신호 발생 일수
    order_count: int = 0  # 주문 횟수


@dataclass
class BacktestRunResult:
    """
    백테스트 실행 결과 (Train/Val/Test 포함)

    문서 참조: docs/tuning/02_objective_gates.md 6.0절

    ⚠️ 튜닝 중에는 test가 None이어야 함 (Test 봉인 원칙)
    """

    metrics: Dict[str, Optional[BacktestMetrics]] = field(default_factory=dict)
    # {'train': Metrics, 'val': Metrics, 'test': Metrics|None}

    guardrail_checks: Optional[GuardrailChecks] = None
    logic_checks: Optional[LogicChecks] = None

    # 추가 메타데이터
    params: Dict[str, Any] = field(default_factory=dict)
    period: Optional["Period"] = None
    warnings: List[str] = field(default_factory=list)

    # 디버그 정보 (v2.1 추가)
    debug: Optional[DebugInfo] = None

    @property
    def train(self) -> Optional[BacktestMetrics]:
        return self.metrics.get("train")

    @property
    def val(self) -> Optional[BacktestMetrics]:
        return self.metrics.get("val")

    @property
    def test(self) -> Optional[BacktestMetrics]:
        return self.metrics.get("test")

    @property
    def is_valid(self) -> bool:
        """결과 유효성 (가드레일 통과 여부)"""
        if self.guardrail_checks is None:
            return False
        return self.guardrail_checks.passed


@dataclass
class Period:
    """
    기간 구조 표준화 (v2.1)

    문서 참조: docs/tuning/04_implementation.md period 구조 표준화
    """

    start_date: date
    end_date: date
    train: Dict[str, date] = field(default_factory=dict)  # {'start': ..., 'end': ...}
    val: Dict[str, date] = field(default_factory=dict)
    test: Optional[Dict[str, date]] = None  # 튜닝 중에는 None

    def to_dict(self) -> Dict:
        """캐시 키 생성용 딕셔너리 변환"""
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "train": (
                {k: v.isoformat() for k, v in self.train.items()}
                if self.train
                else None
            ),
            "val": (
                {k: v.isoformat() for k, v in self.val.items()} if self.val else None
            ),
            "test": (
                {k: v.isoformat() for k, v in self.test.items()} if self.test else None
            ),
        }


@dataclass
class SplitConfig:
    """
    Split 설정

    문서 참조: docs/tuning/00_overview.md 2.3절
    """

    method: str = "chronological"  # 시간 순서 분할 강제

    # 목표 비율 (참고값)
    target_train_ratio: float = 0.70
    target_val_ratio: float = 0.15
    target_test_ratio: float = 0.15

    # 최소 기간 (개월) - 우선 적용
    min_val_months: int = 6
    min_test_months: int = 6
    min_train_months: int = 8

    # 실제 적용값 (계산 후 설정)
    applied_train_months: int = 0
    applied_val_months: int = 0
    applied_test_months: int = 0


@dataclass
class CostConfig:
    """
    거래비용 설정

    문서 참조: docs/tuning/01_metrics_guardrails.md 3.3절
    ⚠️ 편도 기준, 왕복 시 2배 적용
    """

    commission_rate: float = 0.00015  # 0.015% (편도)
    slippage_rate: float = 0.001  # 0.1% (편도)

    @property
    def round_trip_cost(self) -> float:
        """왕복 비용"""
        return 2 * (self.commission_rate + self.slippage_rate)


@dataclass
class DataConfig:
    """
    데이터/유니버스 설정

    문서 참조: docs/tuning/03_walkforward_manifest.md 9.3절
    """

    data_version: str = ""  # 예: 'ohlcv_20251216'
    universe_version: str = ""  # 예: 'krx_etf_20251216'
    universe_source: str = "KRX"
    price_type: str = "adj_close"  # 수정 종가
    dividend_handling: str = "total_return"  # 배당 재투자 가정
    delisted_handling: str = "exclude_from_start"
    survivorship_bias: str = "point_in_time"

    # 재현성 보장용 (v2.1 추가)
    universe_hash: str = ""  # ETF 코드 리스트 정렬 후 해시
    universe_count: int = 0  # 유니버스 종목 수
    sample_codes: List[str] = None  # 앞 5개 종목 샘플 (v2.2 추가)


# 기본값 상수
DEFAULT_COSTS = CostConfig()

DEFAULT_GUARDRAILS = {
    "min_trades": 30,
    "min_exposure_ratio": 0.30,
    "max_annual_turnover": 24,
}


def compute_params_hash(params: Dict[str, Any]) -> str:
    """
    파라미터 해시 계산 (중복 후보 탐지용)

    정렬된 키-값 쌍을 해시하여 동일 파라미터 식별
    """
    import hashlib
    import json

    sorted_params = sorted(params.items())
    params_str = json.dumps(sorted_params, sort_keys=True, default=str)
    return hashlib.sha256(params_str.encode()).hexdigest()[:16]


def compute_universe_hash(symbols: List[str]) -> str:
    """
    유니버스 해시 계산 (재현성 보장용)

    ETF 코드 리스트 정렬 후 해시
    """
    import hashlib

    sorted_symbols = sorted(symbols)
    symbols_str = ",".join(sorted_symbols)
    return hashlib.sha256(symbols_str.encode()).hexdigest()[:16]


# 룩백 거래일 매핑
LOOKBACK_TRADING_DAYS = {
    3: 63,  # 3개월 = 63거래일
    6: 126,  # 6개월 = 126거래일
    12: 252,  # 12개월 = 252거래일
}

# 이상치 감지 임계값
ANOMALY_THRESHOLDS = {
    "sharpe_max": 5.0,  # Sharpe > 5.0 → 경고
    "cagr_max": 1.0,  # CAGR > 100% → 경고
    "min_trades": 30,  # 거래 < 30 → 경고
    "min_exposure": 0.30,  # 노출 < 30% → 경고
}
