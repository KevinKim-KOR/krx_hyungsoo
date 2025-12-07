# -*- coding: utf-8 -*-
"""
일일 추천 엔진 (Daily Recommendation Engine)

매일 장 시작 전 실행하여 매매 신호를 생성합니다.

워크플로우:
1. 현재 보유종목 로드 (Cloud DB)
2. 최적 포트폴리오 로드 (백테스트 결과)
3. 시장 레짐 확인 (ML 모델)
4. 각 종목별 신호 생성 (BUY/SELL/HOLD/REPLACE/STOPLOSS)
5. 텔레그램 알림 발송

사용법:
    python scripts/daily/daily_recommend.py
"""
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, date
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Literal
from enum import Enum

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.db import SessionLocal, Holdings
from extensions.notification.telegram_helper import TelegramHelper

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# 경로 설정
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
OPTIMIZATION_DIR = OUTPUT_DIR / "optimization"
REGIME_FILE = OUTPUT_DIR / "regime_history.json"
RECOMMEND_OUTPUT_DIR = OUTPUT_DIR / "recommendations"


class Signal(str, Enum):
    """매매 신호"""
    BUY = "BUY"              # 신규 매수
    SELL = "SELL"           # 전량 매도
    HOLD = "HOLD"           # 보유 유지
    INCREASE = "INCREASE"   # 비중 확대
    DECREASE = "DECREASE"   # 비중 축소
    STOPLOSS = "STOPLOSS"   # 손절
    REPLACE = "REPLACE"     # 교체 (매도 후 다른 종목 매수)


@dataclass
class Recommendation:
    """종목별 추천"""
    code: str
    name: str
    signal: Signal
    reason: str
    current_weight: float      # 현재 비중 (%)
    target_weight: float       # 목표 비중 (%)
    current_price: float
    avg_price: float
    return_pct: float          # 수익률 (%)
    quantity: int
    target_quantity: int       # 목표 수량
    action_amount: int         # 매매 수량 (+ 매수, - 매도)
    priority: int              # 우선순위 (1이 가장 높음)


@dataclass
class DailyRecommendation:
    """일일 추천 결과"""
    date: str
    regime: str
    regime_confidence: float
    total_value: float
    total_cost: float
    total_return_pct: float
    recommendations: List[Recommendation]
    summary: Dict
    timestamp: str


class DailyRecommendEngine:
    """일일 추천 엔진"""
    
    # 설정
    STOPLOSS_THRESHOLD = -8.0      # 손절 기준 (%)
    REBALANCE_THRESHOLD = 5.0     # 리밸런싱 기준 (목표 비중과 차이 %)
    MIN_TRADE_AMOUNT = 10000      # 최소 거래 금액 (원)
    
    def __init__(self):
        self.session = SessionLocal()
        self.telegram = TelegramHelper()
        self.today = date.today().strftime("%Y-%m-%d")
        
    def __del__(self):
        if hasattr(self, 'session'):
            self.session.close()
    
    def load_holdings(self) -> List[Dict]:
        """현재 보유종목 로드 (DB)"""
        holdings = self.session.query(Holdings).filter(Holdings.quantity > 0).all()
        
        result = []
        for h in holdings:
            result.append({
                "code": h.code,
                "name": h.name,
                "quantity": h.quantity,
                "avg_price": h.avg_price,
                "current_price": h.current_price or h.avg_price,
            })
        
        logger.info(f"보유종목 {len(result)}개 로드")
        return result
    
    def load_optimal_portfolio(self) -> Optional[Dict]:
        """최적 포트폴리오 로드 (최신 파일)"""
        if not OPTIMIZATION_DIR.exists():
            logger.warning("최적화 결과 디렉토리 없음")
            return None
        
        files = list(OPTIMIZATION_DIR.glob("optimal_portfolio_*.json"))
        if not files:
            logger.warning("최적화 결과 파일 없음")
            return None
        
        latest_file = max(files, key=lambda f: f.stat().st_mtime)
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # max_sharpe 방법 찾기
        if isinstance(data, list):
            for item in data:
                if item.get("method") == "max_sharpe":
                    logger.info(f"최적 포트폴리오 로드: {latest_file.name}")
                    return item
            return data[0] if data else None
        
        return data
    
    def load_regime(self) -> Dict:
        """현재 시장 레짐 로드"""
        default_regime = {
            "regime": "neutral",
            "confidence": 0.5,
            "position_ratio": 0.8,
            "defense_mode": False
        }
        
        if not REGIME_FILE.exists():
            logger.warning("레짐 히스토리 파일 없음, 기본값 사용")
            return default_regime
        
        with open(REGIME_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        if not history:
            return default_regime
        
        # 최신 레짐
        latest = history[-1]
        logger.info(f"현재 레짐: {latest.get('regime')} (신뢰도: {latest.get('confidence', 0):.0%})")
        return latest
    
    def calculate_portfolio_metrics(self, holdings: List[Dict]) -> Dict:
        """포트폴리오 지표 계산"""
        total_cost = sum(h["avg_price"] * h["quantity"] for h in holdings)
        total_value = sum(h["current_price"] * h["quantity"] for h in holdings)
        total_return = total_value - total_cost
        total_return_pct = (total_return / total_cost * 100) if total_cost > 0 else 0
        
        return {
            "total_cost": total_cost,
            "total_value": total_value,
            "total_return": total_return,
            "total_return_pct": total_return_pct,
            "holdings_count": len(holdings)
        }
    
    def analyze_position(
        self, 
        holding: Dict, 
        optimal_weights: Dict,
        total_value: float,
        regime: Dict
    ) -> Recommendation:
        """개별 종목 분석 및 신호 생성"""
        code = holding["code"]
        name = holding["name"]
        quantity = holding["quantity"]
        avg_price = holding["avg_price"]
        current_price = holding["current_price"]
        
        # 수익률 계산
        return_pct = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
        
        # 현재 비중 계산
        position_value = current_price * quantity
        current_weight = (position_value / total_value * 100) if total_value > 0 else 0
        
        # 목표 비중 (최적 포트폴리오에 있으면 해당 비중, 없으면 0)
        target_weight = optimal_weights.get(code, 0) * 100  # 소수 -> %
        
        # 레짐에 따른 조정
        position_ratio = regime.get("position_ratio", 1.0)
        defense_mode = regime.get("defense_mode", False)
        
        # 방어 모드면 목표 비중 축소
        if defense_mode:
            target_weight *= 0.5
            logger.info(f"{name}: 방어 모드로 목표 비중 50% 축소")
        
        # 목표 수량 계산
        target_value = total_value * (target_weight / 100)
        target_quantity = int(target_value / current_price) if current_price > 0 else 0
        action_amount = target_quantity - quantity
        
        # 신호 결정
        signal, reason, priority = self._determine_signal(
            code=code,
            name=name,
            return_pct=return_pct,
            current_weight=current_weight,
            target_weight=target_weight,
            action_amount=action_amount,
            current_price=current_price,
            regime=regime
        )
        
        return Recommendation(
            code=code,
            name=name,
            signal=signal,
            reason=reason,
            current_weight=round(current_weight, 2),
            target_weight=round(target_weight, 2),
            current_price=current_price,
            avg_price=avg_price,
            return_pct=round(return_pct, 2),
            quantity=quantity,
            target_quantity=target_quantity,
            action_amount=action_amount,
            priority=priority
        )
    
    def _determine_signal(
        self,
        code: str,
        name: str,
        return_pct: float,
        current_weight: float,
        target_weight: float,
        action_amount: int,
        current_price: float,
        regime: Dict
    ) -> tuple:
        """신호 결정 로직"""
        
        # 1. 손절 체크 (최우선)
        if return_pct <= self.STOPLOSS_THRESHOLD:
            return (
                Signal.STOPLOSS,
                f"손절 기준 도달 ({return_pct:.1f}% < {self.STOPLOSS_THRESHOLD}%)",
                1
            )
        
        # 2. 최적 포트폴리오에 없는 종목 → 매도 검토
        if target_weight == 0:
            if return_pct > 0:
                return (
                    Signal.HOLD,
                    f"최적 포트폴리오 외 종목이나 수익 중 ({return_pct:+.1f}%)",
                    5
                )
            else:
                return (
                    Signal.SELL,
                    f"최적 포트폴리오 외 종목, 손실 중 ({return_pct:.1f}%)",
                    2
                )
        
        # 3. 비중 차이 계산
        weight_diff = target_weight - current_weight
        trade_value = abs(action_amount * current_price)
        
        # 최소 거래 금액 미만이면 HOLD
        if trade_value < self.MIN_TRADE_AMOUNT:
            return (
                Signal.HOLD,
                f"비중 적정 (현재 {current_weight:.1f}% vs 목표 {target_weight:.1f}%)",
                6
            )
        
        # 4. 리밸런싱 필요 여부
        if weight_diff > self.REBALANCE_THRESHOLD:
            return (
                Signal.INCREASE,
                f"비중 확대 필요 ({current_weight:.1f}% → {target_weight:.1f}%)",
                3
            )
        elif weight_diff < -self.REBALANCE_THRESHOLD:
            return (
                Signal.DECREASE,
                f"비중 축소 필요 ({current_weight:.1f}% → {target_weight:.1f}%)",
                4
            )
        
        # 5. 기본: HOLD
        return (
            Signal.HOLD,
            f"비중 적정 (현재 {current_weight:.1f}% vs 목표 {target_weight:.1f}%)",
            6
        )
    
    def find_buy_candidates(
        self, 
        optimal_weights: Dict, 
        holdings: List[Dict],
        total_value: float,
        regime: Dict
    ) -> List[Recommendation]:
        """신규 매수 후보 찾기"""
        holding_codes = {h["code"] for h in holdings}
        candidates = []
        
        for code, weight in optimal_weights.items():
            if code not in holding_codes and weight > 0:
                target_weight = weight * 100
                
                # 방어 모드면 신규 매수 제한
                if regime.get("defense_mode", False):
                    logger.info(f"{code}: 방어 모드로 신규 매수 제한")
                    continue
                
                target_value = total_value * weight
                
                # TODO: 현재가 조회 필요
                # 임시로 스킵
                candidates.append(Recommendation(
                    code=code,
                    name=f"[신규] {code}",
                    signal=Signal.BUY,
                    reason=f"최적 포트폴리오 편입 대상 (목표 {target_weight:.1f}%)",
                    current_weight=0,
                    target_weight=round(target_weight, 2),
                    current_price=0,
                    avg_price=0,
                    return_pct=0,
                    quantity=0,
                    target_quantity=0,
                    action_amount=0,
                    priority=4
                ))
        
        return candidates
    
    def generate_recommendations(self) -> DailyRecommendation:
        """일일 추천 생성"""
        logger.info("=" * 60)
        logger.info(f"일일 추천 생성 시작: {self.today}")
        logger.info("=" * 60)
        
        # 1. 데이터 로드
        holdings = self.load_holdings()
        optimal = self.load_optimal_portfolio()
        regime = self.load_regime()
        
        # 2. 포트폴리오 지표 계산
        metrics = self.calculate_portfolio_metrics(holdings)
        total_value = metrics["total_value"]
        
        # 3. 최적 비중 추출
        optimal_weights = optimal.get("weights", {}) if optimal else {}
        
        # 4. 각 보유종목 분석
        recommendations = []
        for holding in holdings:
            rec = self.analyze_position(
                holding=holding,
                optimal_weights=optimal_weights,
                total_value=total_value,
                regime=regime
            )
            recommendations.append(rec)
        
        # 5. 신규 매수 후보 추가
        buy_candidates = self.find_buy_candidates(
            optimal_weights=optimal_weights,
            holdings=holdings,
            total_value=total_value,
            regime=regime
        )
        recommendations.extend(buy_candidates)
        
        # 6. 우선순위 정렬
        recommendations.sort(key=lambda r: (r.priority, -abs(r.return_pct)))
        
        # 7. 요약 생성
        summary = self._generate_summary(recommendations, metrics, regime)
        
        # 8. 결과 생성
        result = DailyRecommendation(
            date=self.today,
            regime=regime.get("regime", "unknown"),
            regime_confidence=regime.get("confidence", 0),
            total_value=metrics["total_value"],
            total_cost=metrics["total_cost"],
            total_return_pct=metrics["total_return_pct"],
            recommendations=[asdict(r) for r in recommendations],
            summary=summary,
            timestamp=datetime.now().isoformat()
        )
        
        return result
    
    def _generate_summary(
        self, 
        recommendations: List[Recommendation],
        metrics: Dict,
        regime: Dict
    ) -> Dict:
        """요약 생성"""
        signal_counts = {}
        for rec in recommendations:
            signal = rec.signal.value
            signal_counts[signal] = signal_counts.get(signal, 0) + 1
        
        # 액션 필요한 종목
        action_items = [r for r in recommendations if r.signal not in [Signal.HOLD]]
        
        return {
            "total_holdings": metrics["holdings_count"],
            "total_value": metrics["total_value"],
            "total_return_pct": metrics["total_return_pct"],
            "regime": regime.get("regime"),
            "defense_mode": regime.get("defense_mode", False),
            "signal_counts": signal_counts,
            "action_required": len(action_items),
            "stoploss_count": signal_counts.get("STOPLOSS", 0),
            "sell_count": signal_counts.get("SELL", 0),
            "buy_count": signal_counts.get("BUY", 0),
        }
    
    def save_result(self, result: DailyRecommendation) -> Path:
        """결과 저장"""
        RECOMMEND_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        filename = f"daily_recommend_{self.today.replace('-', '')}.json"
        filepath = RECOMMEND_OUTPUT_DIR / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(asdict(result), f, indent=2, ensure_ascii=False)
        
        logger.info(f"결과 저장: {filepath}")
        return filepath
    
    def format_telegram_message(self, result: DailyRecommendation) -> str:
        """텔레그램 메시지 포맷"""
        summary = result.summary
        
        # 헤더
        msg = f"*📊 [일일 추천] {result.date}*\n\n"
        
        # 시장 레짐
        regime_emoji = {"bull": "🟢", "bear": "🔴", "neutral": "🟡"}.get(result.regime, "⚪")
        msg += f"*시장 레짐*: {regime_emoji} {result.regime.upper()}"
        if summary.get("defense_mode"):
            msg += " ⚠️ 방어모드"
        msg += f" (신뢰도 {result.regime_confidence:.0%})\n\n"
        
        # 포트폴리오 현황
        return_emoji = "🔵" if result.total_return_pct < 0 else "🔴"
        msg += f"*포트폴리오 현황*\n"
        msg += f"💰 총 평가액: `{result.total_value:,.0f}원`\n"
        msg += f"📈 수익률: {return_emoji} `{result.total_return_pct:+.2f}%`\n"
        msg += f"📊 보유 종목: `{summary['total_holdings']}개`\n\n"
        
        # 액션 요약
        if summary["action_required"] > 0:
            msg += f"*🎯 오늘의 액션 ({summary['action_required']}건)*\n"
            
            # 손절 (최우선)
            stoploss_items = [r for r in result.recommendations if r["signal"] == "STOPLOSS"]
            if stoploss_items:
                msg += "\n🚨 *손절 필요*\n"
                for item in stoploss_items:
                    msg += f"  • {item['name']}: `{item['return_pct']:+.1f}%`\n"
            
            # 매도
            sell_items = [r for r in result.recommendations if r["signal"] == "SELL"]
            if sell_items:
                msg += "\n📤 *매도 검토*\n"
                for item in sell_items:
                    msg += f"  • {item['name']}: {item['reason']}\n"
            
            # 비중 조정
            adjust_items = [r for r in result.recommendations if r["signal"] in ["INCREASE", "DECREASE"]]
            if adjust_items:
                msg += "\n⚖️ *비중 조정*\n"
                for item in adjust_items:
                    arrow = "↑" if item["signal"] == "INCREASE" else "↓"
                    msg += f"  • {item['name']}: {item['current_weight']:.1f}% {arrow} {item['target_weight']:.1f}%\n"
            
            # 신규 매수
            buy_items = [r for r in result.recommendations if r["signal"] == "BUY"]
            if buy_items:
                msg += "\n📥 *매수 검토*\n"
                for item in buy_items:
                    msg += f"  • {item['name']}: 목표 {item['target_weight']:.1f}%\n"
        else:
            msg += "*✅ 오늘은 특별한 액션이 필요하지 않습니다.*\n"
        
        msg += "\n_성투하세요!_ 🚀"
        
        return msg
    
    def send_telegram(self, result: DailyRecommendation):
        """텔레그램 발송"""
        message = self.format_telegram_message(result)
        self.telegram.send_with_logging(
            message=message,
            category="daily_recommend"
        )
        logger.info("텔레그램 발송 완료")
    
    def run(self, send_telegram: bool = True) -> DailyRecommendation:
        """실행"""
        try:
            # 추천 생성
            result = self.generate_recommendations()
            
            # 결과 저장
            self.save_result(result)
            
            # 텔레그램 발송
            if send_telegram:
                self.send_telegram(result)
            
            # 요약 출력
            summary = result.summary
            logger.info("=" * 60)
            logger.info("추천 생성 완료")
            logger.info(f"  시장 레짐: {result.regime}")
            logger.info(f"  총 평가액: {result.total_value:,.0f}원")
            logger.info(f"  수익률: {result.total_return_pct:+.2f}%")
            logger.info(f"  액션 필요: {summary['action_required']}건")
            if summary['stoploss_count'] > 0:
                logger.warning(f"  ⚠️ 손절 필요: {summary['stoploss_count']}건")
            logger.info("=" * 60)
            
            return result
            
        except Exception as e:
            logger.error(f"추천 생성 실패: {e}")
            raise


def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="일일 추천 엔진")
    parser.add_argument("--no-telegram", action="store_true", help="텔레그램 발송 안함")
    parser.add_argument("--dry-run", action="store_true", help="테스트 실행 (저장/발송 안함)")
    args = parser.parse_args()
    
    engine = DailyRecommendEngine()
    
    if args.dry_run:
        result = engine.generate_recommendations()
        print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    else:
        engine.run(send_telegram=not args.no_telegram)


if __name__ == "__main__":
    main()
