#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/nas/daily_regime_check.py
NAS 일일 레짐 감지 및 알림

매일 오전 9시 실행:
1. 현재 시장 레짐 계산
2. 이전 레짐과 비교
3. 변화 감지 시 텔레그램 알림
4. 보유 종목 매도 신호 확인
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.strategy.market_regime_detector import MarketRegimeDetector
from core.strategy.us_market_monitor import USMarketMonitor
from core.db import get_db_connection, init_db
from core.data_loader import get_ohlcv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 상태 파일 경로
STATE_DIR = project_root / "data" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
REGIME_STATE_FILE = STATE_DIR / "current_regime.json"


class RegimeMonitor:
    """레짐 모니터링 클래스"""
    
    def __init__(self):
        self.detector = MarketRegimeDetector()
        self.us_monitor = USMarketMonitor()
        self.current_regime = None
        self.previous_regime = None
        self.regime_confidence = 0.0
        self.us_market_regime = None
        
    def load_previous_regime(self) -> Optional[Dict]:
        """이전 레짐 로드"""
        if not REGIME_STATE_FILE.exists():
            return None
        
        try:
            with open(REGIME_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"이전 레짐 로드 실패: {e}")
            return None
    
    def save_current_regime(self, regime: str, confidence: float, details: Dict):
        """현재 레짐 저장"""
        state = {
            "regime": regime,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        
        try:
            with open(REGIME_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ 레짐 저장: {regime} (신뢰도: {confidence:.1%})")
        except Exception as e:
            logger.error(f"레짐 저장 실패: {e}")
    
    def detect_current_regime(self) -> Dict:
        """현재 레짐 감지"""
        try:
            # KOSPI 데이터 가져오기
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            
            kospi_data = get_ohlcv(
                "^KS11",  # KOSPI 지수
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )
            
            if kospi_data is None or kospi_data.empty:
                logger.error("KOSPI 데이터 없음")
                return None
            
            # 레짐 감지
            current_date = datetime.now().date()
            regime, confidence = self.detector.detect_regime(kospi_data, current_date)
            
            if regime is None:
                logger.error("레짐 감지 결과 없음")
                return None
            
            # 레짐 한글 변환
            regime_map = {
                'bull': '상승장',
                'bear': '하락장',
                'neutral': '중립장'
            }
            
            # 컬럼명 확인 (close 또는 Close)
            close_col = 'Close' if 'Close' in kospi_data.columns else 'close'
            
            # float 변환 (FutureWarning 방지)
            current_price = kospi_data[close_col].iloc[-1]
            ma_short_value = kospi_data[close_col].rolling(50).mean().iloc[-1]
            ma_long_value = kospi_data[close_col].rolling(200).mean().iloc[-1]
            
            return {
                "regime": regime_map.get(regime, regime),
                "confidence": float(confidence),
                "ma_short": 50,
                "ma_long": 200,
                "current_price": float(current_price.item() if hasattr(current_price, 'item') else current_price),
                "ma_short_value": float(ma_short_value.item() if hasattr(ma_short_value, 'item') else ma_short_value),
                "ma_long_value": float(ma_long_value.item() if hasattr(ma_long_value, 'item') else ma_long_value),
            }
            
        except Exception as e:
            logger.error(f"레짐 감지 실패: {e}")
            return None
    
    def check_regime_change(self) -> bool:
        """레짐 변화 확인"""
        # 이전 레짐 로드
        prev_state = self.load_previous_regime()
        
        # 1. 한국 시장 레짐 감지
        current_state = self.detect_current_regime()
        
        if current_state is None:
            logger.error("현재 레짐 감지 실패")
            return False
        
        self.current_regime = current_state["regime"]
        self.regime_confidence = current_state["confidence"]
        
        # 2. 미국 시장 레짐 감지
        try:
            self.us_market_regime = self.us_monitor.determine_us_market_regime()
            logger.info(f"미국 시장 레짐: {self.us_market_regime}")
        except Exception as e:
            logger.error(f"미국 시장 레짐 감지 실패: {e}")
            self.us_market_regime = 'neutral'
        
        # 3. 레짐 변화 확인
        regime_changed = False
        if prev_state:
            self.previous_regime = prev_state["regime"]
            regime_changed = (self.current_regime != self.previous_regime)
        else:
            logger.info("이전 레짐 없음 (최초 실행)")
            regime_changed = True
        
        # 4. 현재 레짐 저장
        current_state["us_market_regime"] = self.us_market_regime
        self.save_current_regime(
            self.current_regime,
            self.regime_confidence,
            current_state
        )
        
        return regime_changed
    
    def generate_regime_alert(self) -> str:
        """레짐 변화 알림 메시지 생성"""
        emoji_map = {
            "상승장": "📈",
            "중립장": "➡️",
            "하락장": "📉",
            "bullish": "📈",
            "neutral": "➡️",
            "bearish": "📉"
        }
        
        current_emoji = emoji_map.get(self.current_regime, "❓")
        prev_emoji = emoji_map.get(self.previous_regime, "❓") if self.previous_regime else "❓"
        us_emoji = emoji_map.get(self.us_market_regime, "❓")
        
        message = f"""
🚨 시장 레짐 변화 감지

📍 한국 시장:
{prev_emoji} 이전: {self.previous_regime or '없음'}
{current_emoji} 현재: {self.current_regime}
📊 신뢰도: {self.regime_confidence:.1%}

🇺🇸 미국 시장:
{us_emoji} 레짐: {self.us_market_regime}

"""
        
        # 미국 시장 지표 추가
        try:
            us_report = self.us_monitor.generate_report()
            message += f"\n{us_report}\n\n"
        except Exception as e:
            logger.error(f"미국 시장 리포트 생성 실패: {e}")
        
        message += "\n"
        
        # 레짐별 권장 조치
        if self.current_regime == "상승장":
            message += """
💰 권장 조치:
- 현금 보유율: 0~10%
- 포지션 크기: 100~120%
- 전략: 공격적 투자
- 종목: 모멘텀 강한 종목

"""
        elif self.current_regime == "중립장":
            message += """
💰 권장 조치:
- 현금 보유율: 40~50% 🔥
- 포지션 크기: 50~60%
- 전략: 중립적 투자
- 종목: 방어적 종목으로 전환

⚠️ 주의:
- 방향성 불확실
- 변동성 증가 가능
- 보유 종목 점검 필요

"""
        else:  # 하락장
            message += """
💰 권장 조치:
- 현금 보유율: 70~80% 🔥
- 포지션 크기: 20~30%
- 전략: 방어적 투자
- 종목: 현금 비중 확대

🚨 긴급:
- 보유 종목 매도 검토
- 손절 라인 확인
- 추가 하락 대비

"""
        
        message += f"""
📅 감지 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return message.strip()
    
    def check_holdings_sell_signals(self) -> List[Dict]:
        """보유 종목 매도 신호 확인"""
        sell_signals = []
        
        try:
            # DB에서 보유 종목 조회
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT code, name, quantity, avg_price
                FROM holdings
                WHERE quantity > 0
            """)
            
            holdings = cursor.fetchall()
            conn.close()
            
            if not holdings:
                logger.info("보유 종목 없음")
                return []
            
            # 각 종목 확인
            for code, name, quantity, avg_price in holdings:
                # TODO: MAPS 점수 및 모멘텀 계산
                # 현재는 레짐 변화만으로 판단
                
                if self.current_regime == "하락장":
                    sell_signals.append({
                        "code": code,
                        "name": name,
                        "quantity": quantity,
                        "avg_price": avg_price,
                        "reason": "하락장 전환"
                    })
                elif self.current_regime == "중립장":
                    # 중립장에서는 일부만 매도 권장
                    sell_signals.append({
                        "code": code,
                        "name": name,
                        "quantity": quantity // 2,  # 절반만
                        "avg_price": avg_price,
                        "reason": "중립장 전환 (일부 매도 권장)"
                    })
            
        except Exception as e:
            logger.error(f"보유 종목 확인 실패: {e}")
        
        return sell_signals
    
    def generate_sell_alert(self, sell_signals: List[Dict]) -> str:
        """매도 신호 알림 메시지 생성"""
        if not sell_signals:
            return ""
        
        message = f"""
⚠️ 보유 종목 매도 신호 ({len(sell_signals)}건)

"""
        
        for signal in sell_signals:
            message += f"""
📌 {signal['name']} ({signal['code']})
   수량: {signal['quantity']:,}주
   평균가: {signal['avg_price']:,.0f}원
   사유: {signal['reason']}

"""
        
        return message.strip()


def send_telegram_alert(message: str):
    """텔레그램 알림 전송"""
    try:
        from extensions.automation.telegram_notifier import TelegramNotifier
        
        # 환경 변수에서 설정 읽기
        import os
        enabled = os.getenv('TELEGRAM_ENABLED', 'false').lower() == 'true'
        
        notifier = TelegramNotifier(enabled=enabled)
        notifier.send_message(message)
        
        # 로그도 출력
        logger.info("=" * 60)
        logger.info("텔레그램 알림:")
        logger.info(message)
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"텔레그램 알림 전송 실패: {e}")


def main():
    """메인 함수"""
    logger.info("=" * 60)
    logger.info("일일 레짐 감지 시작")
    logger.info("=" * 60)
    
    # DB 초기화
    try:
        init_db()
        logger.info("✅ DB 초기화 완료")
    except Exception as e:
        logger.warning(f"DB 초기화 실패 (무시): {e}")
    
    monitor = RegimeMonitor()
    
    # 1. 레짐 변화 확인
    regime_changed = monitor.check_regime_change()
    
    if regime_changed:
        logger.info(f"🚨 레짐 변화 감지: {monitor.previous_regime} → {monitor.current_regime}")
        
        # 2. 레짐 변화 알림
        regime_alert = monitor.generate_regime_alert()
        send_telegram_alert(regime_alert)
        
        # 3. 보유 종목 매도 신호 확인
        sell_signals = monitor.check_holdings_sell_signals()
        
        if sell_signals:
            sell_alert = monitor.generate_sell_alert(sell_signals)
            send_telegram_alert(sell_alert)
    else:
        logger.info(f"✅ 레짐 유지: {monitor.current_regime} (신뢰도: {monitor.regime_confidence:.1%})")
    
    logger.info("=" * 60)
    logger.info("일일 레짐 감지 완료")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
