# -*- coding: utf-8 -*-
"""
core/strategy/live_signal_generator.py
Live 파라미터 기반 매매 신호 생성

기능:
- Live 파라미터 로드 (lookback, ma_period, rsi_period, stop_loss)
- 모멘텀 스코어 계산
- RSI 스케일링
- 목표 비중 계산
- 매수/매도 신호 생성
"""

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class LiveSignalGenerator:
    """
    Live 파라미터 기반 매매 신호 생성 클래스

    PLAN.md 3번 항목 구현:
    1. Live 파라미터 로드 (lookback, ma_period, rsi_period, stop_loss)
    2. 유니버스 필터링 (거래대금, 상장일)
    3. 모멘텀 스코어 계산 (lookback + ma_period)
    4. RSI 스케일링 (rsi_period)
    5. 목표 비중 계산 (Equal-Weight)
    6. 현재 보유 비중과 비교
       - 부족 → 매수 검토
       - 초과/외부 → 매도 검토
    """

    def __init__(self, optimal_params_path: Optional[Path] = None):
        """
        Args:
            optimal_params_path: optimal_params.json 경로 (None이면 기본 경로)
        """
        if optimal_params_path is None:
            optimal_params_path = Path("data/optimal_params.json")
        self.optimal_params_path = optimal_params_path

    def load_live_params(self) -> Optional[Dict]:
        """Live 파라미터 로드"""
        import json

        if not self.optimal_params_path.exists():
            logger.error(f"optimal_params.json 없음: {self.optimal_params_path}")
            return None

        try:
            with open(self.optimal_params_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            live = data.get("live")
            if not live:
                logger.warning("Live 파라미터 없음 - 기본값 사용")
                return {
                    "params": {
                        "lookback": "3M",
                        "ma_period": 60,
                        "rsi_period": 14,
                        "stop_loss": -10,
                        "max_positions": 10,
                    },
                    "promoted_at": None,
                    "notes": "기본값",
                }

            return live

        except Exception as e:
            logger.error(f"Live 파라미터 로드 실패: {e}")
            return None

    def _parse_lookback(self, lookback: str) -> int:
        """룩백 문자열을 개월 수로 변환 (예: '3M' -> 3)"""
        if not lookback:
            return 3

        lookback = lookback.upper().strip()
        if lookback.endswith("M"):
            try:
                return int(lookback[:-1])
            except ValueError:
                return 3
        try:
            return int(lookback)
        except ValueError:
            return 3

    def generate_recommendation(
        self,
        target_date: Optional[date] = None,
        current_holdings: Optional[Dict[str, float]] = None,
    ) -> Dict:
        """
        일일 추천 신호 생성

        Args:
            target_date: 대상 날짜 (None이면 오늘)
            current_holdings: 현재 보유 비중 {ticker: weight%}

        Returns:
            Dict: 추천 결과
                - buy_recommendations: 매수 검토 리스트
                - sell_recommendations: 매도 검토 리스트
                - live_params: 사용된 Live 파라미터
                - regime_info: 레짐 정보
        """
        if target_date is None:
            target_date = date.today()

        if current_holdings is None:
            current_holdings = {}

        logger.info(f"일일 추천 생성 시작: {target_date}")

        # 1. Live 파라미터 로드
        live = self.load_live_params()
        if not live:
            return self._empty_result("Live 파라미터 로드 실패")

        params = live.get("params", {})
        lookback_str = params.get("lookback", "3M")
        lookback_months = self._parse_lookback(lookback_str)
        ma_period = params.get("ma_period", 60)
        rsi_period = params.get("rsi_period", 14)
        stop_loss = params.get("stop_loss", -10)
        max_positions = params.get("max_positions", 10)

        logger.info(
            f"Live 파라미터: lookback={lookback_str}, MA={ma_period}, "
            f"RSI={rsi_period}, 손절={stop_loss}%, 최대포지션={max_positions}"
        )

        # 2. 유니버스 로드
        try:
            from core.data.filtering import get_filtered_universe

            universe = get_filtered_universe()
            if not universe:
                return self._empty_result("유니버스 로드 실패")
            logger.info(f"유니버스: {len(universe)}개 종목")
        except Exception as e:
            logger.error(f"유니버스 로드 실패: {e}")
            return self._empty_result(f"유니버스 로드 실패: {e}")

        # 3. 가격 데이터 로드
        try:
            from infra.data.loader import load_price_data

            # 룩백 기간 + MA 기간 만큼 데이터 필요
            data_days = lookback_months * 30 + ma_period + 30
            start_date = target_date - timedelta(days=data_days)

            price_data = load_price_data(
                universe=universe, start_date=start_date, end_date=target_date
            )

            if price_data.empty:
                return self._empty_result("가격 데이터 없음")

            logger.info(f"가격 데이터 로드 완료: {len(price_data)}행")
        except Exception as e:
            logger.error(f"가격 데이터 로드 실패: {e}")
            return self._empty_result(f"가격 데이터 로드 실패: {e}")

        # 4. 레짐 분석
        try:
            from extensions.automation.regime_monitor import RegimeMonitor

            regime_monitor = RegimeMonitor()
            regime_info = regime_monitor.analyze_daily_regime(target_date)
        except Exception as e:
            logger.warning(f"레짐 분석 실패: {e}")
            regime_info = {"regime": "neutral", "confidence": 0.5, "position_ratio": 0.8}

        # 5. 모멘텀 스코어 계산
        scores = {}
        for code in universe:
            try:
                # MultiIndex에서 종목 데이터 추출
                if isinstance(price_data.index, pd.MultiIndex):
                    code_data = price_data.xs(code, level="code")
                else:
                    # 단일 종목인 경우
                    code_data = price_data

                if len(code_data) < ma_period:
                    continue

                close = code_data["close"]

                # MA 계산
                ma = close.rolling(ma_period).mean()
                current_price = close.iloc[-1]
                current_ma = ma.iloc[-1]

                if pd.isna(current_ma) or current_ma == 0:
                    continue

                # 모멘텀 스코어 = (현재가 - MA) / MA * 100
                momentum_score = ((current_price - current_ma) / current_ma) * 100

                # RSI 계산
                delta = close.diff()
                gain = delta.where(delta > 0, 0).rolling(rsi_period).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(rsi_period).mean()

                if loss.iloc[-1] == 0:
                    rsi = 100
                else:
                    rs = gain.iloc[-1] / loss.iloc[-1]
                    rsi = 100 - (100 / (1 + rs))

                # RSI 스케일링 (50 기준, 과매수/과매도 조정)
                rsi_factor = 1.0
                if rsi > 70:
                    rsi_factor = 0.7  # 과매수 - 비중 감소
                elif rsi < 30:
                    rsi_factor = 1.3  # 과매도 - 비중 증가

                # 최종 스코어 = 모멘텀 * RSI 팩터
                final_score = momentum_score * rsi_factor

                scores[code] = {
                    "momentum_score": momentum_score,
                    "rsi": rsi,
                    "rsi_factor": rsi_factor,
                    "final_score": final_score,
                    "current_price": current_price,
                }

            except Exception as e:
                logger.debug(f"종목 {code} 스코어 계산 실패: {e}")
                continue

        if not scores:
            return self._empty_result("스코어 계산된 종목 없음")

        logger.info(f"스코어 계산 완료: {len(scores)}개 종목")

        # 6. Top N 선정 (양수 스코어만)
        positive_scores = {k: v for k, v in scores.items() if v["final_score"] > 0}
        sorted_scores = sorted(
            positive_scores.items(), key=lambda x: x[1]["final_score"], reverse=True
        )

        # 레짐 기반 포지션 수 조정
        position_ratio = regime_info.get("position_ratio", 0.8)
        target_count = int(max_positions * position_ratio)
        target_count = max(1, min(target_count, max_positions))

        top_n = sorted_scores[:target_count]

        # 7. 목표 비중 계산 (Equal-Weight)
        if top_n:
            target_weight = 100.0 / len(top_n)
        else:
            target_weight = 0

        target_weights = {code: target_weight for code, _ in top_n}

        # 8. 매수/매도 추천 생성
        buy_recommendations = []
        sell_recommendations = []

        # 매수 검토: 목표 비중 > 현재 비중
        for code, score_info in top_n:
            current_weight = current_holdings.get(code, 0)
            target = target_weights.get(code, 0)

            if target > current_weight + 1:  # 1% 이상 차이
                buy_recommendations.append(
                    {
                        "code": code,
                        "current_weight": current_weight,
                        "target_weight": target,
                        "momentum_score": score_info["momentum_score"],
                        "rsi": score_info["rsi"],
                        "final_score": score_info["final_score"],
                    }
                )

        # 매도 검토: 현재 보유 중이지만 Top N에 없거나 스코어 음수
        for code, current_weight in current_holdings.items():
            if current_weight <= 0:
                continue

            if code not in target_weights:
                # Top N에 없음 - 매도 검토
                score_info = scores.get(code, {})
                sell_recommendations.append(
                    {
                        "code": code,
                        "current_weight": current_weight,
                        "target_weight": 0,
                        "reason": "Top N 제외",
                        "momentum_score": score_info.get("momentum_score", 0),
                    }
                )
            elif code in scores and scores[code]["final_score"] < 0:
                # 스코어 음수 - 매도 검토
                sell_recommendations.append(
                    {
                        "code": code,
                        "current_weight": current_weight,
                        "target_weight": 0,
                        "reason": "모멘텀 하락",
                        "momentum_score": scores[code]["momentum_score"],
                    }
                )

        logger.info(
            f"추천 생성 완료: 매수 {len(buy_recommendations)}개, "
            f"매도 {len(sell_recommendations)}개"
        )

        return {
            "buy_recommendations": buy_recommendations,
            "sell_recommendations": sell_recommendations,
            "live_params": params,
            "regime_info": regime_info,
            "target_positions": target_count,
            "target_weight": target_weight,
            "total_scored": len(scores),
            "generated_at": target_date.isoformat(),
        }

    def _empty_result(self, message: str) -> Dict:
        """빈 결과 반환"""
        logger.warning(f"빈 결과: {message}")
        return {
            "buy_recommendations": [],
            "sell_recommendations": [],
            "live_params": None,
            "regime_info": None,
            "message": message,
        }

    def format_recommendation_message(self, result: Dict) -> str:
        """
        추천 결과를 텔레그램 메시지 형식으로 변환

        Args:
            result: generate_recommendation() 결과

        Returns:
            str: 포맷된 메시지
        """
        lines = []

        # 헤더
        lines.append("=" * 40)
        lines.append("📊 *일일 추천* (Live 파라미터 기반)")
        lines.append("=" * 40)

        # Live 파라미터 요약
        params = result.get("live_params", {})
        if params:
            lookback = params.get("lookback", "3M")
            ma = params.get("ma_period", 60)
            rsi = params.get("rsi_period", 14)
            stop = params.get("stop_loss", -10)
            lines.append(f"🔧 *전략*: {lookback} / MA{ma} / RSI{rsi} / 손절{stop}%")
            lines.append("")

        # 레짐 정보
        regime_info = result.get("regime_info", {})
        if regime_info:
            regime_emoji = {"bull": "📈", "bear": "📉", "neutral": "➡️"}
            regime_name = {"bull": "상승장", "bear": "하락장", "neutral": "중립장"}
            regime = regime_info.get("regime", "neutral")
            emoji = regime_emoji.get(regime, "❓")
            name = regime_name.get(regime, regime)
            confidence = regime_info.get("confidence", 0)
            lines.append(f"{emoji} *레짐*: {name} (신뢰도 {confidence:.0%})")
            lines.append("")

        # 매수 검토
        buy_recs = result.get("buy_recommendations", [])
        lines.append("📥 *매수 검토*")
        lines.append("-" * 30)
        if buy_recs:
            for rec in buy_recs[:5]:  # 최대 5개
                code = rec["code"]
                target = rec["target_weight"]
                score = rec["final_score"]
                lines.append(f"  • `{code}`: 목표 {target:.1f}% (점수 {score:.1f})")
        else:
            lines.append("  (없음)")
        lines.append("")

        # 매도 검토
        sell_recs = result.get("sell_recommendations", [])
        lines.append("📤 *매도 검토*")
        lines.append("-" * 30)
        if sell_recs:
            for rec in sell_recs[:5]:  # 최대 5개
                code = rec["code"]
                current = rec["current_weight"]
                reason = rec.get("reason", "")
                lines.append(f"  • `{code}`: 현재 {current:.1f}% → 0% ({reason})")
        else:
            lines.append("  (없음)")
        lines.append("")

        # 푸터
        lines.append("=" * 40)
        generated_at = result.get("generated_at", date.today().isoformat())
        lines.append(f"📅 생성: {generated_at}")

        return "\n".join(lines)
