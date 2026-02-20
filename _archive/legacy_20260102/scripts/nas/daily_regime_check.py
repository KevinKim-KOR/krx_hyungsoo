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
import os
from pathlib import Path
from datetime import datetime, timedelta
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from typing import Dict, List, Optional

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 환경 변수 로드 (.env 파일)
try:
    from dotenv import load_dotenv
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"✅ 환경 변수 로드: {env_file}")
    else:
        print(f"⚠️ .env 파일 없음: {env_file}")
except ImportError:
    print("⚠️ python-dotenv 패키지 없음 - 환경 변수 수동 설정 필요")

from core.strategy.market_regime_detector import MarketRegimeDetector
from core.strategy.us_market_monitor import USMarketMonitor
from core.db import get_db_connection, init_db
from core.data_loader import get_ohlcv, get_kospi_index_naver

# 로거 설정 (force=True로 기존 설정 덮어쓰기)
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s',
    force=True
)

# 파일 핸들러 추가
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 콘솔 출력
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(levelname)s:%(name)s:%(message)s'))

# 파일 출력
log_dir = project_root / "logs"
log_dir.mkdir(exist_ok=True)
file_handler = logging.FileHandler(log_dir / "daily_regime_check.log", encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s:%(name)s:%(message)s'))

logger.addHandler(console_handler)
logger.addHandler(file_handler)

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
            "timestamp": datetime.now(KST).isoformat(),
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
            end_date = datetime.now(KST)
            start_date = end_date - timedelta(days=365)
            
            logger.info(f"KOSPI 데이터 조회 중... ({start_date.date()} ~ {end_date.date()})")
            
            # get_ohlcv()는 자동으로 yfinance → PyKRX → 네이버 금융 순서로 시도
            kospi_data = get_ohlcv(
                "^KS11",  # KOSPI 지수
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )
            
            if kospi_data is None or kospi_data.empty:
                logger.error("KOSPI 데이터 없음 - 모든 데이터 소스 실패")
                logger.error("yfinance, PyKRX, 네이버 금융 모두 실패")
                return None
            
            logger.info(f"✅ KOSPI 데이터 조회 성공: {len(kospi_data)}행")
            logger.info(f"   컬럼: {kospi_data.columns.tolist()}")
            logger.info(f"   기간: {kospi_data.index.min()} ~ {kospi_data.index.max()}")
            
            # 레짐 감지
            logger.info("레짐 감지 시작...")
            current_date = datetime.now(KST).date()
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
            
            regime_kr = regime_map.get(regime, regime)
            logger.info(f"✅ 레짐 감지 완료: {regime_kr} (신뢰도: {confidence:.1%})")
            
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
            import traceback
            logger.error(traceback.format_exc())
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
            logger.info("🇺🇸 미국 시장 리포트 생성 중... (레짐 변화)")
            us_report = self.us_monitor.generate_report()
            if us_report:
                message += f"\n{us_report}\n\n"
                logger.info("✅ 미국 시장 리포트 생성 성공")
            else:
                logger.warning("⚠️ 미국 시장 리포트가 비어있음")
                message += "\n⚠️ 미국 시장 지표 조회 실패 (데이터 없음)\n\n"
        except Exception as e:
            logger.error(f"❌ 미국 시장 리포트 생성 실패: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            message += "\n⚠️ 미국 시장 지표 조회 실패\n\n"
        
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
📅 감지 시간: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return message.strip()
    
    def generate_regime_maintain_alert(self) -> str:
        """레짐 유지 알림 메시지 생성"""
        emoji_map = {
            "상승장": "📈",
            "중립장": "➡️",
            "하락장": "📉",
            "bullish": "📈",
            "neutral": "➡️",
            "bearish": "📉"
        }
        
        current_emoji = emoji_map.get(self.current_regime, "❓")
        us_emoji = emoji_map.get(self.us_market_regime, "❓")
        
        message = f"""
📅 {datetime.now(KST).strftime('%Y년 %m월 %d일')}

✅ 레짐 유지

📍 한국 시장:
{current_emoji} 현재 레짐: {self.current_regime}
📊 신뢰도: {self.regime_confidence:.1%}

🇺🇸 미국 시장:
{us_emoji} 레짐: {self.us_market_regime}

"""
        
        # 미국 시장 지표 추가
        try:
            logger.info("🇺🇸 미국 시장 리포트 생성 중... (레짐 유지)")
            us_report = self.us_monitor.generate_report()
            if us_report:
                message += f"\n{us_report}\n\n"
                logger.info("✅ 미국 시장 리포트 생성 성공")
            else:
                logger.warning("⚠️ 미국 시장 리포트가 비어있음")
                message += "\n⚠️ 미국 시장 지표 조회 실패 (데이터 없음)\n\n"
        except Exception as e:
            logger.error(f"❌ 미국 시장 리포트 생성 실패: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            message += "\n⚠️ 미국 시장 지표 조회 실패\n\n"
        
        message += "\n"
        
        # 현재 레짐 권장 조치
        if self.current_regime == "상승장":
            message += """
💰 현재 전략:
- 현금 보유율: 0~10%
- 포지션 크기: 100~120%
- 전략: 공격적 투자 유지

"""
        elif self.current_regime == "중립장":
            message += """
💰 현재 전략:
- 현금 보유율: 40~50%
- 포지션 크기: 50~60%
- 전략: 중립적 투자 유지
- 주의: 변동성 증가 가능

"""
        else:  # 하락장
            message += """
💰 현재 전략:
- 현금 보유율: 70~80%
- 포지션 크기: 20~30%
- 전략: 방어적 투자 유지
- 주의: 보유 종목 점검 필요

"""
        
        return message.strip()
    
    def get_current_price_naver(self, code: str) -> Optional[float]:
        """네이버 금융에서 현재가 조회"""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            url = f"https://finance.naver.com/item/main.naver?code={code}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=3)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 현재가 추출
            price_element = soup.select_one('.no_today .blind')
            if price_element:
                price_text = price_element.text.strip().replace(',', '')
                return float(price_text)
            
            # 대체 방법
            price_element = soup.select_one('.p11 .blind')
            if price_element:
                price_text = price_element.text.strip().replace(',', '')
                return float(price_text)
            
            return None
            
        except Exception as e:
            logger.warning(f"현재가 조회 실패 ({code}): {e}")
            return None
    
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
            
            logger.info(f"보유 종목 {len(holdings)}개 확인 중...")
            
            # 각 종목 확인
            for code, name, quantity, avg_price in holdings:
                # 현재가 조회
                current_price = self.get_current_price_naver(code)
                
                if current_price is None:
                    logger.warning(f"{name}({code}) 현재가 조회 실패 - 스킵")
                    continue
                
                # 수익률 계산
                profit_rate = ((current_price - avg_price) / avg_price) * 100
                
                # 매도 신호 판단
                should_sell = False
                reason = ""
                sell_quantity = quantity
                
                if self.current_regime == "하락장":
                    should_sell = True
                    reason = "하락장 전환"
                    sell_quantity = quantity
                elif self.current_regime == "중립장":
                    should_sell = True
                    reason = "중립장 전환 (일부 매도 권장)"
                    sell_quantity = quantity // 2
                elif profit_rate < -5.0:
                    # 손실 5% 이상이면 상승장에서도 매도 권장
                    should_sell = True
                    reason = f"손실 {profit_rate:.1f}% (손절 권장)"
                    sell_quantity = quantity
                
                if should_sell:
                    sell_signals.append({
                        "code": code,
                        "name": name,
                        "quantity": sell_quantity,
                        "avg_price": avg_price,
                        "current_price": current_price,
                        "profit_rate": profit_rate,
                        "reason": reason
                    })
                    logger.info(f"  매도 신호: {name}({code}) - {reason}")
            
        except Exception as e:
            logger.error(f"보유 종목 확인 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return sell_signals
    
    def generate_sell_alert(self, sell_signals: List[Dict]) -> str:
        """매도 신호 알림 메시지 생성"""
        if not sell_signals:
            return ""
        
        message = f"""
⚠️ 보유 종목 매도 신호 ({len(sell_signals)}건)

"""
        
        for signal in sell_signals:
            profit_emoji = "📈" if signal['profit_rate'] >= 0 else "📉"
            
            message += f"""
📌 {signal['name']} ({signal['code']})
   수량: {signal['quantity']:,}주
   평균가: {signal['avg_price']:,.0f}원
   현재가: {signal['current_price']:,.0f}원
   {profit_emoji} 수익률: {signal['profit_rate']:+.2f}%
   사유: {signal['reason']}

"""
        
        return message.strip()


def send_telegram_alert(message: str) -> bool:
    """텔레그램 알림 전송"""
    try:
        from extensions.automation.telegram_notifier import TelegramNotifier
        
        # 환경 변수에서 설정 읽기
        import os
        enabled = os.getenv('TELEGRAM_ENABLED', 'false').lower() == 'true'
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('TG_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID') or os.getenv('TG_CHAT_ID')
        
        logger.info(f"텔레그램 설정 확인:")
        logger.info(f"  - TELEGRAM_ENABLED: {enabled}")
        logger.info(f"  - BOT_TOKEN 존재: {bool(bot_token)}")
        logger.info(f"  - CHAT_ID 존재: {bool(chat_id)}")
        
        # enabled가 false여도 bot_token과 chat_id가 있으면 활성화
        if not enabled and bot_token and chat_id:
            logger.info("  - TELEGRAM_ENABLED=false이지만 토큰/ID 있음 → 활성화")
            enabled = True
        
        notifier = TelegramNotifier(
            bot_token=bot_token,
            chat_id=chat_id,
            enabled=enabled
        )
        
        result = notifier.send_message(message)
        
        # 로그 출력
        logger.info("=" * 60)
        logger.info("텔레그램 알림 내용:")
        logger.info(message)
        logger.info("=" * 60)
        
        if result:
            logger.info("✅ 텔레그램 알림 전송 성공")
            return True
        else:
            logger.error("❌ 텔레그램 알림 전송 실패 (result=False)")
            logger.error("   가능한 원인:")
            logger.error("   1. TELEGRAM_ENABLED=false")
            logger.error("   2. BOT_TOKEN 또는 CHAT_ID 없음")
            logger.error("   3. 네트워크 오류")
            return False
            
    except Exception as e:
        logger.error(f"❌ 텔레그램 알림 전송 실패 (예외): {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """메인 함수"""
    start_time = datetime.now(KST)
    
    logger.info("=" * 80)
    logger.info(f"일일 레짐 감지 시작 - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    telegram_results = []
    
    try:
        # DB 초기화
        try:
            init_db()
            logger.info("✅ DB 초기화 완료")
        except Exception as e:
            logger.warning(f"DB 초기화 실패 (무시): {e}")
        
        monitor = RegimeMonitor()
        
        # 1. 레짐 변화 확인
        logger.info(f"[{datetime.now(KST).strftime('%H:%M:%S')}] 레짐 변화 확인 시작")
        regime_changed = monitor.check_regime_change()
        
        if regime_changed:
            logger.info(f"🚨 레짐 변화 감지: {monitor.previous_regime} → {monitor.current_regime}")
            
            # 2. 레짐 변화 알림
            regime_alert = monitor.generate_regime_alert()
            result = send_telegram_alert(regime_alert)
            telegram_results.append(("레짐 변화 알림", result))
        else:
            logger.info(f"✅ 레짐 유지: {monitor.current_regime} (신뢰도: {monitor.regime_confidence:.1%})")
            
            # 2-1. 레짐 유지 알림 (매일 발송)
            maintain_alert = monitor.generate_regime_maintain_alert()
            result = send_telegram_alert(maintain_alert)
            telegram_results.append(("레짐 유지 알림", result))
        
        # 3. 보유 종목 매도 신호 확인 (레짐 변화 여부와 무관하게 항상 체크)
        logger.info(f"[{datetime.now(KST).strftime('%H:%M:%S')}] 보유 종목 매도 신호 확인 중...")
        sell_signals = monitor.check_holdings_sell_signals()
        
        if sell_signals:
            logger.info(f"⚠️ 매도 신호 {len(sell_signals)}건 발견")
            sell_alert = monitor.generate_sell_alert(sell_signals)
            result = send_telegram_alert(sell_alert)
            telegram_results.append(("매도 신호 알림", result))
        else:
            logger.info("✅ 매도 신호 없음")
        
    except Exception as e:
        logger.error(f"❌ 실행 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    finally:
        end_time = datetime.now(KST)
        elapsed = (end_time - start_time).total_seconds()
        
        logger.info("=" * 80)
        logger.info(f"일일 레짐 감지 완료 - {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"실행 시간: {elapsed:.2f}초")
        logger.info("")
        logger.info("텔레그램 알림 전송 결과:")
        for alert_type, success in telegram_results:
            status = "✅ 성공" if success else "❌ 실패"
            logger.info(f"  - {alert_type}: {status}")
        logger.info("=" * 80)


if __name__ == "__main__":
    main()
