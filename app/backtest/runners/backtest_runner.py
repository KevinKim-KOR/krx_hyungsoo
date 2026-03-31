# -*- coding: utf-8 -*-
"""
extensions/backtest/runner.py
백테스트 실행기

비중 스케일링 파이프라인:
① 모멘텀 기반 base weight (equal weight)
② RSI 스케일링 (종목 레벨)
③ Soft Normalize (초과 시만 압축, 부족 시 cash)
④ 레짐 스케일링 (포트폴리오 레벨)
"""

from typing import Dict, List, Optional, Any
from datetime import date
import pandas as pd
import logging

from app.backtest.engine.backtest import BacktestEngine
from app.backtest.strategy.weight_scaler import WeightScaler, WeightScalingResult

logger = logging.getLogger(__name__)


class BacktestRunner:
    """백테스트 실행기"""

    def __init__(
        self,
        initial_capital: float = 10000000,
        commission_rate: float = 0.00015,
        slippage_rate: float = 0.001,
        max_positions: int = 10,
        rebalance_frequency: str = "daily",
        instrument_type: str = "etf",
        enable_defense: bool = True,
        min_holding_days: int = 0,
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.max_positions = max_positions
        self.rebalance_frequency = rebalance_frequency
        self.instrument_type = instrument_type
        self.enable_defense = enable_defense
        self.min_holding_days = min_holding_days

        # 레짐 감지기 초기화
        from app.backtest.strategy.market_regime_detector import MarketRegimeDetector

        self.regime_detector = MarketRegimeDetector(
            enable_regime_detection=enable_defense
        )

        # 비중 스케일러 초기화
        self.weight_scaler = WeightScaler()

    def _get_rsi_exposure(
        self, rsi: float, enable_oversold_boost: bool = True
    ) -> float:
        """
        RSI 기반 비중 스케일링 계수 반환

        Args:
            rsi: RSI 값 (0~100)
            enable_oversold_boost: 과매도 시 비중 증가 여부

        Returns:
            exposure 계수 (0.0 ~ 1.2)
        """
        if rsi >= 80:
            return 0.0  # 극단적 과열 → 비중 0
        elif rsi >= 70:
            return 0.5  # 과열 → 비중 50%
        elif rsi >= 60:
            return 0.8  # 경계 → 비중 80%
        elif rsi <= 30 and enable_oversold_boost:
            return 1.2  # 과매도 → 비중 120%
        else:
            return 1.0  # 정상 → 비중 100%

    def _apply_rsi_scaling(
        self,
        base_weights: Dict[str, float],
        rsi_values: Dict[str, float],
        enable_oversold_boost: bool = True,
        log_details: bool = False,
        current_date: date = None,
    ) -> Dict[str, float]:
        """
        RSI 기반 비중 스케일링 적용

        Args:
            base_weights: 기본 비중 (종목코드: 비중)
            rsi_values: RSI 값 (종목코드: RSI)
            enable_oversold_boost: 과매도 시 비중 증가 여부
            log_details: 상세 로깅 여부
            current_date: 현재 날짜 (로깅용)

        Returns:
            RSI 스케일링 적용된 비중
        """
        if not base_weights:
            return {}

        # 1. RSI exposure 계산 및 적용
        scaled_weights = {}
        exposure_log = []

        for code, base_weight in base_weights.items():
            rsi = rsi_values.get(code, 50.0)  # RSI 없으면 중립값
            exposure = self._get_rsi_exposure(rsi, enable_oversold_boost)
            scaled_weight = base_weight * exposure
            scaled_weights[code] = scaled_weight

            if log_details:
                exposure_log.append(
                    {
                        "code": code,
                        "base_weight": base_weight,
                        "rsi": rsi,
                        "exposure": exposure,
                        "scaled_weight": scaled_weight,
                    }
                )

        # 2. 정규화 (합계 1.0으로)
        total_weight = sum(scaled_weights.values())
        if total_weight > 0:
            normalized_weights = {
                code: w / total_weight for code, w in scaled_weights.items()
            }
        else:
            normalized_weights = {}

        # 3. 상세 로깅
        if log_details and exposure_log:
            logger.info(f"[{current_date}] RSI 스케일링 적용:")
            for item in exposure_log:
                final_weight = normalized_weights.get(item["code"], 0)
                logger.info(
                    f"  {item['code']}: base={item['base_weight']:.3f} "
                    f"→ RSI={item['rsi']:.1f} (exp={item['exposure']:.1f}) "
                    f"→ scaled={item['scaled_weight']:.3f} → final={final_weight:.3f}"
                )

        return normalized_weights

    def _calculate_rsi(self, close_prices: pd.Series, period: int = 14) -> float:
        """
        RSI 계산 (Wilder's Smoothing Method)

        Args:
            close_prices: 종가 시리즈
            period: RSI 기간

        Returns:
            RSI 값 (0~100)
        """
        if len(close_prices) < period + 1:
            return 50.0  # 데이터 부족 시 중립값

        # float 변환 (uint32 overflow 방지)
        prices = close_prices.astype(float).tail(period * 3)
        delta = prices.diff().dropna()

        if len(delta) < period:
            return 50.0

        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        # EMA 방식 (Wilder's smoothing)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean().iloc[-1]
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean().iloc[-1]

        if pd.isna(avg_gain) or pd.isna(avg_loss):
            return 50.0

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi if not pd.isna(rsi) else 50.0

    def _calculate_momentum_scores(
        self,
        price_data: pd.DataFrame,
        current_date: date,
        lookback_days: int = 60,
        rsi_period: int = 14,
    ) -> Dict[str, tuple]:
        """
        모멘텀 스코어 + RSI 계산

        Args:
            price_data: 가격 데이터
            current_date: 현재 날짜
            lookback_days: MA 룩백 기간
            rsi_period: RSI 계산 기간

        Returns:
            종목별 (모멘텀 스코어, RSI) 튜플
        """
        scores = {}
        ts = pd.Timestamp(current_date)

        if not isinstance(price_data.index, pd.MultiIndex):
            return scores

        # 모든 종목 코드 추출
        codes = price_data.index.get_level_values("code").unique()

        for code in codes:
            try:
                # 해당 종목의 과거 데이터 추출
                code_data = price_data.xs(code, level="code")

                # 현재 날짜 이전 데이터만 사용
                historical = code_data[code_data.index <= ts]

                if len(historical) < lookback_days:
                    continue

                close = historical["close"]

                # MAPS 스코어: (현재가 / MA) - 1
                ma = close.rolling(window=lookback_days).mean()

                if len(ma) > 0 and not pd.isna(ma.iloc[-1]) and ma.iloc[-1] > 0:
                    current_price = close.iloc[-1]
                    maps_score = ((current_price / ma.iloc[-1]) - 1.0) * 100
                    rsi = self._calculate_rsi(close, rsi_period)
                    scores[code] = (maps_score, rsi)

            except (KeyError, IndexError):
                continue

        return scores

    def _calculate_candidate_scores(
        self,
        price_data: pd.DataFrame,
        current_date: date,
        lookback_days: int = 60,
        rsi_period: int = 14,
        volatility_period: int = 14,
        entry_threshold: float = 0.02,
    ) -> Dict[str, tuple]:
        """5? ??? ?? ?? ??."""
        scores = {}
        ts = pd.Timestamp(current_date)

        if not isinstance(price_data.index, pd.MultiIndex):
            return scores

        codes = price_data.index.get_level_values("code").unique()
        for code in codes:
            try:
                code_data = price_data.xs(code, level="code")
                historical = code_data[code_data.index <= ts]
                min_history = max(lookback_days + 1, volatility_period + 1)
                if len(historical) < min_history:
                    continue

                close = historical["close"].astype(float)
                daily_ret = close.pct_change()
                momentum = close.pct_change(lookback_days)
                ma = close.rolling(window=lookback_days).mean()
                volatility = daily_ret.rolling(window=volatility_period).std() * (
                    252**0.5
                )

                if (
                    pd.isna(ma.iloc[-1])
                    or pd.isna(momentum.iloc[-1])
                    or pd.isna(volatility.iloc[-1])
                ):
                    continue

                ma_value = float(ma.iloc[-1])
                momentum_value = float(momentum.iloc[-1])
                volatility_value = float(volatility.iloc[-1])
                current_price = float(close.iloc[-1])

                if ma_value <= 0 or volatility_value <= 0:
                    continue
                if current_price <= ma_value:
                    continue
                if momentum_value <= entry_threshold:
                    continue

                ranking_score = momentum_value / volatility_value
                rsi = self._calculate_rsi(close, rsi_period)
                scores[code] = (
                    ranking_score,
                    rsi,
                    momentum_value,
                    volatility_value,
                )
            except (KeyError, IndexError):
                continue

        return scores

    def run(
        self,
        price_data: pd.DataFrame,
        target_weights: Dict[str, float],
        start_date: date,
        end_date: date,
        market_index_data: Optional[pd.DataFrame] = None,
        rebalance_period: int = 5,  # 리밸런싱 주기 (영업일)
        ma_period: int = 60,  # ??? ??? MA ??
        volatility_period: int = 14,
        entry_threshold: float = 0.02,
        rsi_period: int = 14,  # RSI ?? ??
        stop_loss: float = -0.10,  # 손절 기준 (예: -0.10 = -10%)
        regime_ma_period: int = 200,  # Legacy: internally mapped if needed
        min_regime_hold_days: int = 20,  # Phase 7.1: Hysteresis
        regime_ma_long: int = 200,  # Phase 8: Long Term MA for Regime
        adx_period: int = 14,  # Phase 9: ADX Period
        adx_threshold: float = 20.0,  # Phase 9: ADX Threshold (Chop Filter)
        portfolio_mode: str = "single_universe",
        sell_mode: str = "stop_loss",
        rebalance_rule: Optional[Dict[str, Any]] = None,
        buckets: Optional[List[Dict[str, Any]]] = None,
        universe_resolver: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        백테스트 실행 (모멘텀 기반 동적 종목 선정)

        Args:
            price_data: 종목별 가격 데이터 (MultiIndex: code, date)
            target_weights: 초기 목표 비중 (종목 코드: 비중) - 유니버스로 사용
            start_date: 시작일
            end_date: 종료일
            market_index_data: 시장 지수 데이터 (레짐 감지용)
            rebalance_period: 리밸런싱 주기 (영업일, 기본 5일=주간)

        Returns:
            성과 지표
        """
        # [EVIDENCE] Strategy (Runner) initialized with params
        if logger.isEnabledFor(logging.INFO):
            logger.info(
                f"[EVIDENCE] BacktestRunner.run called with params: "
                f"ma_period={ma_period}, volatility_period={volatility_period}, "
                f"entry_threshold={entry_threshold}, rsi_period={rsi_period}, "
                f"stop_loss={stop_loss}"
            )

        # ---------------------------------------------------------------------
        # [Action A] Index Type Check & Auto-Recovery (Fail-Fast)
        # ---------------------------------------------------------------------
        if not isinstance(price_data.index, pd.MultiIndex):
            logger.warning(
                f"[Runner] Invalid Index Type detected: {type(price_data.index)}"
            )

            # 1. Normalize Columns (Lowercase) for recovery attempt
            price_data = price_data.rename(
                columns={c: c.lower() for c in price_data.columns}
            )

            # Map common variations
            col_map = {"date": "date", "날짜": "date", "time": "date"}
            for c in price_data.columns:
                if c.lower() in col_map and "date" not in price_data.columns:
                    price_data = price_data.rename(columns={c: col_map[c.lower()]})

            # 2. Check essential columns
            has_code = "code" in price_data.columns
            has_date = "date" in price_data.columns

            if has_code and has_date:
                logger.info(
                    "[Runner] Attempting Auto-Recovery: Setting MultiIndex(['code', 'date'])"
                )
                try:
                    price_data["date"] = pd.to_datetime(price_data["date"])
                    price_data = price_data.set_index(["code", "date"]).sort_index()
                    logger.info("[Runner] Auto-Recovery Successful.")
                except Exception as e:
                    logger.error(f"[Runner] Auto-Recovery Failed: {e}")
                    raise ValueError(
                        f"Runner requires MultiIndex(code, date) and recovery failed: {e}"
                    )
            else:
                # 3. Explicit Failure
                msg = (
                    f"[Runner Critical] Index must be MultiIndex(code, date). "
                    f"Got {type(price_data.index)}. "
                    f"Columns: {list(price_data.columns)}. "
                    f"Sample: {price_data.head(1).to_dict() if not price_data.empty else 'Empty'}"
                )
                logger.error(msg)
                raise ValueError(msg)

        # Double check MultiIndex levels
        if "code" not in price_data.index.names or "date" not in price_data.index.names:
            # Try to adjust level names if they match by position but not name?
            # For now, strict check is safer.
            # Or swap levels if date is first?
            pass

        # ---------------------------------------------------------------------

        # 엔진 생성 (각 실행마다 독립적)
        engine = BacktestEngine(
            initial_capital=self.initial_capital,
            commission_rate=self.commission_rate,
            slippage_rate=self.slippage_rate,
            max_positions=self.max_positions,
            rebalance_frequency=self.rebalance_frequency,
            instrument_type=self.instrument_type,
            min_holding_days=self.min_holding_days,
        )

        # 유니버스 (target_weights의 키들)
        universe = list(target_weights.keys())
        _universe_resolver = universe_resolver
        _rebalance_universe_changes = 0

        # 날짜 범위 생성
        dates = pd.date_range(start_date, end_date, freq="B")

        current_regime = "neutral"
        regime_confidence = 0.5
        position_ratio = 1.0
        day_count = 0
        current_top_n = []  # 현재 보유 종목
        current_base_weights = None  # 버킷별 명시적 보유 비중
        current_rsi_values = {}  # 현재 RSI 값 (비중 스케일링용)
        daily_logs = []  # 일별 비중 스케일링 로그
        signal_days = 0  # 신호 발생 일수 (v2.2 추가)

        # Funnel Metrics (Phase 2)
        raw_signal_count = 0
        filtered_signal_count = 0

        # Hysteresis Variables
        locked_regime = None
        last_regime_change_idx = -999

        # Phase 7.2 Diagnostics
        regime_switch_count = 0
        regime_locked_count = 0

        # Phase 2 Rebalance Trackers
        prev_month = None
        prev_week = None

        # P183 Trade Evidence Counters (telemetry only, no logic change)
        stop_loss_sell_count = 0

        for i, current_date in enumerate(dates):
            d = current_date.date()
            day_count += 1

            # 1. 레짐 감지 및 비중 조절
            if self.enable_defense and market_index_data is not None:
                # Phase 9: Dual Timeframe + ADX Chop Filter
                # detect_regime_adx returns (regime, confidence, is_golden_cross, is_chop)
                raw_regime, raw_confidence, is_golden_cross, is_chop = (
                    self.regime_detector.detect_regime_adx(
                        market_index_data,
                        d,
                        long_ma_period=regime_ma_long,
                        short_ma_period=ma_period,
                        adx_period=adx_period,
                        adx_threshold=adx_threshold,
                    )
                )

                # Warm-up Safety: Default to 'bull' if not enough data
                desired_regime = raw_regime if raw_regime else "bull"

                # Phase 7.1: Hysteresis Logic
                if locked_regime is None:
                    # 초기화
                    locked_regime = desired_regime
                    last_regime_change_idx = i
                    current_regime = locked_regime

                if desired_regime != locked_regime:
                    days_since_change = i - last_regime_change_idx
                    if days_since_change < min_regime_hold_days:
                        # Phase 8 Override: Golden Cross -> Force UNLOCK
                        if (
                            is_golden_cross
                            and locked_regime == "bear"
                            and desired_regime == "bull"
                        ):
                            # 하락장 Lock 상태인데 골든크로스 발생 -> 즉시 상승장 전환 허용
                            logger.debug(
                                f"Hysteresis Override: Golden Cross Triggered on {d}!"
                            )
                            # UNLOCK & SWITCH
                            if locked_regime != desired_regime:
                                logger.debug(
                                    f"Regime Switched (Override): {locked_regime} -> {desired_regime}"
                                )
                                regime_switch_count += 1
                            locked_regime = desired_regime
                            last_regime_change_idx = i
                            current_regime = locked_regime
                        else:
                            # LOCK Active: 변경 무시
                            current_regime = locked_regime
                            regime_locked_count += 1
                            # logger.debug(f"Regime Locked: desire={desired_regime}, locked={locked_regime} ({days_since_change}/{min_regime_hold_days})")
                    else:
                        # UNLOCK & SWITCH: 변경 승인
                        if locked_regime != desired_regime:
                            logger.debug(
                                f"Regime Switched: {locked_regime} -> {desired_regime} (Held {days_since_change} days)"
                            )
                            regime_switch_count += 1
                        locked_regime = desired_regime
                        last_regime_change_idx = i
                        current_regime = locked_regime

                # Phase 9 Priority: Chop Filter (Kill Switch)
                # 우선순위: Hysteresis/Dual 결과가 'bull'이더라도, ADX < Threshold(Chop)이면 강제 Bear(Cash).
                if is_chop:
                    # Log chop event occasionally
                    if current_regime == "bull":
                        # logger.debug(f"Chop Detected on {d} (ADX Low): Force Risk-Off")
                        pass
                    current_regime = "bear"
                    # Note: We technically override 'current_regime' to bear, but keep 'locked_regime' state
                    # so that when chop ends, we resume the locked state logic.
                else:
                    current_regime = locked_regime

                # Use raw confidence for now, or maybe locked confidence?
                # Let's stick to raw confidence for position sizing inside the regime
                regime_confidence = raw_confidence
                position_ratio = self.regime_detector.get_position_ratio(
                    current_regime, regime_confidence
                )

            # 2. 현재 가격 조회
            current_prices = {}
            if isinstance(price_data.index, pd.MultiIndex):
                try:
                    ts = pd.Timestamp(d)
                    daily_data = price_data.xs(ts, level="date")
                    current_prices = daily_data["close"].to_dict()
                except KeyError:
                    pass

            if not current_prices:
                continue

            # NAV 업데이트
            engine.update_nav(d, current_prices)

            # 2.5 리밸런싱 주기 계산
            if rebalance_rule:
                freq = rebalance_rule.get("frequency", "M")
                if freq == "M":
                    should_rebalance = (day_count == 1) or (
                        prev_month is not None and d.month != prev_month
                    )
                elif freq == "W":
                    cur_week = d.isocalendar()[1]
                    should_rebalance = (day_count == 1) or (
                        prev_week is not None and cur_week != prev_week
                    )
                else:
                    should_rebalance = True
            else:
                should_rebalance = (day_count == 1) or (
                    day_count % rebalance_period == 0
                )

            # 3. 손절 체크 (sell_mode에 따라 제한)
            can_sell_today = True
            if sell_mode == "rebalance_only" and not should_rebalance:
                can_sell_today = False

            positions_to_sell = []
            if can_sell_today:
                for symbol, position in engine.portfolio.positions.items():
                    if symbol in current_prices and position.quantity > 0:
                        current_price = current_prices[symbol]
                        entry_price = position.entry_price
                        if entry_price > 0:
                            drawdown = (current_price / entry_price) - 1.0
                            if drawdown <= stop_loss:
                                positions_to_sell.append(
                                    (symbol, position.quantity, current_price)
                                )
                                logger.debug(
                                    f"{d}: 손절 - {symbol}, 손실률: {drawdown*100:.2f}%"
                                )

                # 손절 매도 실행
                for symbol, qty, price in positions_to_sell:
                    engine.execute_sell(symbol, qty, price, d)
                    stop_loss_sell_count += 1
                    if symbol in current_top_n:
                        current_top_n.remove(symbol)

            # 4. 리밸런싱 (주기적으로 Top N 재선정)

            if should_rebalance:
                # P205-STEP5E: dynamic universe resolver
                if _universe_resolver:
                    new_univ = _universe_resolver(d)
                    if new_univ and set(new_univ) != set(universe):
                        universe = new_univ
                        _rebalance_universe_changes += 1

                # 모멘텀 스코어 + RSI 계산
                scores = self._calculate_candidate_scores(
                    price_data,
                    d,
                    lookback_days=ma_period,
                    rsi_period=rsi_period,
                    volatility_period=volatility_period,
                    entry_threshold=entry_threshold,
                )

                if portfolio_mode == "bucket_portfolio" and buckets:
                    # 버킷별 할당 로직 (Phase 2)
                    new_top_n = []
                    new_base_weights = {}

                    for b in buckets:
                        b_univ = b.get("universe", [])
                        b_weight = b.get("weight", 0.0)

                        b_scores = {k: v for k, v in scores.items() if k in b_univ}
                        raw_signal_count += len(b_scores)

                        if b_scores:
                            b_sorted = sorted(
                                b_scores.items(), key=lambda x: x[1][0], reverse=True
                            )
                            best_code = b_sorted[0][0]  # N=1 per bucket
                            new_top_n.append(best_code)
                            new_base_weights[best_code] = (
                                new_base_weights.get(best_code, 0.0) + b_weight
                            )

                    if new_top_n:
                        signal_days += 1
                        # Remove duplicates but keep order
                        new_top_n = list(dict.fromkeys(new_top_n))
                        filtered_signal_count += len(new_top_n)

                        if current_top_n and set(new_top_n) != set(current_top_n):
                            removed = set(current_top_n) - set(new_top_n)
                            added = set(new_top_n) - set(current_top_n)
                            if removed or added:
                                logger.debug(
                                    f"{d}: 종목 변경 - 제외: {removed}, 추가: {added}"
                                )

                        current_top_n = new_top_n
                        current_base_weights = new_base_weights

                        current_rsi_values = {
                            code: scores[code][1]
                            for code in current_top_n
                            if code in scores
                        }

                        scaling_result = self.weight_scaler.compute_final_weights(
                            top_n_codes=current_top_n,
                            rsi_values=current_rsi_values,
                            regime=current_regime,
                            regime_confidence=regime_confidence,
                            regime_scale=position_ratio,
                            current_date=d,
                            log_details=(day_count == 1),
                            base_weights=current_base_weights,
                        )

                        adjusted_weights = scaling_result.w_final
                        daily_logs.append(
                            self.weight_scaler.result_to_dict(scaling_result)
                        )
                    else:
                        adjusted_weights = {}
                        current_rsi_values = {}
                else:
                    # 기존 Single Universe 로직
                    universe_scores = {k: v for k, v in scores.items() if k in universe}

                    # Raw Signal: 이번 리밸런싱 시점에 조건 만족한 종목 수 누적
                    raw_signal_count += len(universe_scores)

                    if universe_scores:
                        # 신호 발생 일수 증가 (유효한 점수가 산출됨)
                        signal_days += 1

                        # Top N 선정: 모멘텀 스코어 기준 (RSI 필터링은 비중 스케일링에서 처리)
                        sorted_scores = sorted(
                            universe_scores.items(),
                            key=lambda x: x[1][0],  # 모멘텀 스코어만으로 정렬
                            reverse=True,
                        )
                        new_top_n = [
                            code for code, _ in sorted_scores[: self.max_positions]
                        ]

                        # Filtered Signal: Top N에 선정된 종목 수 누적 (이번 리밸런싱에 '새로' 혹은 '유지'된 슬롯)
                        filtered_signal_count += len(new_top_n)

                        # 종목 변경 로깅
                        if current_top_n and set(new_top_n) != set(current_top_n):
                            removed = set(current_top_n) - set(new_top_n)
                            added = set(new_top_n) - set(current_top_n)
                            if removed or added:
                                logger.debug(
                                    f"{d}: 종목 변경 - 제외: {removed}, 추가: {added}"
                                )

                        current_top_n = new_top_n

                        # Set to None for equal weights logic in weight_scaler
                        current_base_weights = None

                        # RSI 값 저장 (비중 스케일링용)
                        current_rsi_values = {
                            code: universe_scores[code][1]
                            for code in current_top_n
                            if code in universe_scores
                        }

                        # WeightScaler를 통한 비중 계산 파이프라인
                        # ① base weight → ② RSI scaling → ③ Soft Normalize → ④ Regime scaling
                        scaling_result = self.weight_scaler.compute_final_weights(
                            top_n_codes=current_top_n,
                            rsi_values=current_rsi_values,
                            regime=current_regime,
                            regime_confidence=regime_confidence,
                            regime_scale=position_ratio,
                            current_date=d,
                            log_details=(day_count == 1),
                        )

                        adjusted_weights = scaling_result.w_final

                        # 일별 로그 저장
                        daily_logs.append(
                            self.weight_scaler.result_to_dict(scaling_result)
                        )
                    else:
                        adjusted_weights = {}
                        current_rsi_values = {}
            else:
                # 리밸런싱 주기가 아니면 기존 종목 유지 (비중 재계산)
                if current_top_n:
                    # WeightScaler를 통한 비중 계산
                    scaling_result = self.weight_scaler.compute_final_weights(
                        top_n_codes=current_top_n,
                        rsi_values=current_rsi_values,
                        regime=current_regime,
                        regime_confidence=regime_confidence,
                        regime_scale=position_ratio,
                        current_date=d,
                        log_details=False,
                        base_weights=current_base_weights,
                    )

                    adjusted_weights = scaling_result.w_final
                else:
                    adjusted_weights = {}

            # 리밸런싱 실행
            try:
                if adjusted_weights:
                    # P184-Fix: Strict rebalance_only guardrail
                    can_rebalance_execute = True
                    if sell_mode == "rebalance_only" and not should_rebalance:
                        can_rebalance_execute = False

                    if can_rebalance_execute:
                        engine.rebalance(adjusted_weights, current_prices, d)
            except Exception as e:
                logger.error(f"리밸런싱 실패: {e}", exc_info=True)

            prev_month = d.month
            prev_week = d.isocalendar()[1]

        # 성과 지표
        metrics = engine.get_performance_metrics()

        # 신호 통계 추가 (v2.2)
        metrics["signal_days"] = signal_days
        metrics["order_count"] = len(engine.portfolio.trades)
        metrics["raw_signal_count"] = raw_signal_count
        metrics["filtered_signal_count"] = filtered_signal_count

        # [Phase 6.1] Post-Run Validation
        if len(engine.portfolio.trades) == 0:
            # Just warning or raising? If strictly no trades, metrics like sharpe are 0.0 which is fine, but maybe we want to classify?
            # Let's keep it as is, but rely on 'metrics' check in tool.
            # Actually, user wants specific Fail Reason.
            # If we return, run_phase15 sees sharpe=0.0 and might think it's valid but bad.
            # But if it's TRULY no trades due to logic, it's valid (just inactive).
            pass

        # Metrics에 레짐 통계 추가
        metrics["regime_switch_count"] = regime_switch_count
        metrics["regime_locked_count"] = regime_locked_count

        # P183 Trade Evidence: build histogram from confirmed trades
        from collections import Counter

        trade_dates = [str(t.date) for t in engine.portfolio.trades]
        trade_histogram = dict(Counter(trade_dates))
        total_rebalance_trades = len(engine.portfolio.trades) - stop_loss_sell_count
        trade_reason_counts = {
            "rebalance": max(total_rebalance_trades, 0),
            "stop_loss": stop_loss_sell_count,
        }

        # Top 10 trade dates by volume
        sorted_dates = sorted(trade_histogram.items(), key=lambda x: x[1], reverse=True)
        trade_dates_top10 = [{"date": d, "count": c} for d, c in sorted_dates[:10]]

        # Cluster check: are trades concentrated on day 1~3 of month?
        trade_days_of_month = [int(d.split("-")[2]) for d in trade_dates if d]
        early_month_count = sum(1 for day in trade_days_of_month if day <= 3)
        total_trade_events = len(trade_days_of_month)
        cluster_ratio = (
            early_month_count / total_trade_events if total_trade_events > 0 else 0
        )
        rebal_freq = (rebalance_rule or {}).get("frequency", "M")
        rebal_dom = (rebalance_rule or {}).get("day_of_month", 1)
        rebalance_cluster_check = {
            "expected_frequency": rebal_freq,
            "day_of_month": rebal_dom,
            "cluster_ok": cluster_ratio >= 0.8,
            "cluster_ratio": round(cluster_ratio, 4),
            "note": f"{early_month_count}/{total_trade_events} trades on day 1~3",
        }

        return {
            "metrics": metrics,
            "nav_history": engine.nav_history,
            "trades": engine.portfolio.trades,
            "final_positions": engine.portfolio.positions,
            "daily_logs": daily_logs,
            "trade_histogram_by_date": trade_histogram,
            "trade_reason_counts": trade_reason_counts,
            "trade_dates_top10": trade_dates_top10,
            "rebalance_cluster_check": rebalance_cluster_check,
            "rebalance_universe_changes": _rebalance_universe_changes,
        }

    def run_batch(
        self,
        price_data: pd.DataFrame,
        params_list: List[Dict[str, Any]],
        start_date: date,
        end_date: date,
        market_index_data: Optional[pd.DataFrame] = None,
        n_jobs: int = -1,
    ) -> List[Dict[str, Any]]:
        """
        배치 백테스트 실행 (병렬 처리)

        Args:
            price_data: 가격 데이터
            params_list: 파라미터 리스트 (각 항목은 target_weights 생성 등에 사용될 수 있음)
                         현재 구조에서는 target_weights가 필수이므로,
                         params_list의 각 항목이 {'target_weights': ..., 'label': ...} 형태라고 가정
            start_date: 시작일
            end_date: 종료일
            market_index_data: 시장 지수 데이터
            n_jobs: 병렬 작업 수 (-1: 모든 코어 사용)

        Returns:
            결과 리스트
        """
        from joblib import Parallel, delayed

        logger.info(
            f"배치 백테스트 시작: {len(params_list)}개 시나리오, n_jobs={n_jobs}"
        )

        def _run_single(params):
            # 엔진 별도 생성 (스레드 안전성 확보)
            runner = BacktestRunner(
                initial_capital=self.initial_capital,
                commission_rate=self.commission_rate,
                slippage_rate=self.slippage_rate,
                max_positions=self.max_positions,
                rebalance_frequency=self.rebalance_frequency,
                instrument_type=self.instrument_type,
                enable_defense=self.enable_defense,
                min_holding_days=self.min_holding_days,
            )

            # 파라미터 추출
            weights = params.get("target_weights", {})
            label = params.get("label", "unknown")

            try:
                result = runner.run(
                    price_data=price_data,
                    target_weights=weights,
                    start_date=start_date,
                    end_date=end_date,
                    market_index_data=market_index_data,
                )
                result["label"] = label
                result["params"] = params
                return result
            except Exception as e:
                logger.error(f"시나리오 실패 ({label}): {e}")
                return {"label": label, "error": str(e)}

        # 병렬 실행
        results = Parallel(n_jobs=n_jobs)(
            delayed(_run_single)(params) for params in params_list
        )

        logger.info("배치 백테스트 완료")
        return results


class MomentumBacktestRunner(BacktestRunner):
    """모멘텀 전략 백테스트 실행기"""

    # 기존 로직 유지 (필요 시 오버라이드)
    pass


def create_default_runner(
    initial_capital: float = 10000000, max_positions: int = 10
) -> BacktestRunner:
    """기본 백테스트 실행기 생성"""
    return BacktestRunner(initial_capital=initial_capital, max_positions=max_positions)


def create_momentum_runner(
    initial_capital: float = 10000000, max_positions: int = 10
) -> MomentumBacktestRunner:
    """모멘텀 백테스트 실행기 생성"""
    return MomentumBacktestRunner(
        initial_capital=initial_capital, max_positions=max_positions
    )
