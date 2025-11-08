#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
"""
scripts/nas/regime_change_alert.py
시장 레짐 변경 알림
"""
import sys
import logging
import os
from datetime import date, timedelta
from pathlib import Path
import json

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 환경 변수 로드 (.env 파일 직접 파싱)
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

from extensions.monitoring import RegimeDetector
from extensions.notification.telegram_sender import TelegramSender
from infra.logging.setup import setup_logging

# 로깅 설정
setup_logging()
logger = logging.getLogger(__name__)


def load_previous_regime():
    """이전 레짐 로드"""
    regime_file = PROJECT_ROOT / "data" / "monitoring" / "last_regime.json"
    
    if not regime_file.exists():
        return None
    
    try:
        with open(regime_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"이전 레짐 로드 실패: {e}")
        return None


def save_current_regime(regime: dict):
    """현재 레짐 저장"""
    regime_file = PROJECT_ROOT / "data" / "monitoring" / "last_regime.json"
    regime_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(regime_file, 'w', encoding='utf-8') as f:
            json.dump(regime, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        logger.error(f"레짐 저장 실패: {e}")


def main():
    """레짐 변경 감지 및 알림"""
    print("=" * 60)
    print("시장 레짐 변경 감지")
    print("=" * 60)
    logger.info("=" * 60)
    logger.info("시장 레짐 변경 감지")
    logger.info("=" * 60)
    
    try:
        # 현재 레짐 감지
        detector = RegimeDetector()
        target_date = date.today() - timedelta(days=1)
        current_regime = detector.detect_regime(target_date)
        
        print(f"현재 레짐: {current_regime['state']}")
        logger.info(f"현재 레짐: {current_regime['state']}")
        
        # 이전 레짐 로드
        previous_regime = load_previous_regime()
        
        # 환경 변수 확인
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        print(f"\nTELEGRAM_BOT_TOKEN: {'*' * 10 if bot_token else 'None'}")
        print(f"TELEGRAM_CHAT_ID: {chat_id if chat_id else 'None'}\n")
        
        if previous_regime:
            print(f"이전 레짐: {previous_regime.get('state', 'unknown')}")
            logger.info(f"이전 레짐: {previous_regime.get('state', 'unknown')}")
            
            # 레짐 변경 감지
            changed, message = detector.detect_regime_change(current_regime, previous_regime)
            
            if changed:
                print("⚠️ 레짐 변경 감지!")
                logger.warning("⚠️ 레짐 변경 감지!")
                
                # 텔레그램 알림
                description = detector.get_regime_description(current_regime)
                
                alert_message = f"*[시장 레짐 변경]*\n\n"
                alert_message += f"📅 {target_date}\n\n"
                alert_message += f"{message}\n\n"
                alert_message += f"*현재 상태*\n{description}\n\n"
                alert_message += "_포트폴리오 리스크 관리에 유의하세요._"
                
                sender = TelegramSender(
                    bot_token=os.getenv('TELEGRAM_BOT_TOKEN'),
                    chat_id=int(os.getenv('TELEGRAM_CHAT_ID', 0))
                )
                success = sender.send_custom(alert_message, parse_mode='Markdown')
                
                if success:
                    print("✅ 레짐 변경 알림 전송 성공")
                    logger.info("✅ 레짐 변경 알림 전송 성공")
                else:
                    print("⚠️ 레짐 변경 알림 전송 실패")
                    logger.warning("⚠️ 레짐 변경 알림 전송 실패")
            else:
                print("레짐 변경 없음")
                logger.info("레짐 변경 없음")
        else:
            print("이전 레짐 없음 (첫 실행)")
            logger.info("이전 레짐 없음 (첫 실행)")
            
            # 첫 실행 시에도 현재 레짐 알림 전송
            description = detector.get_regime_description(current_regime)
            
            alert_message = f"*[시장 레짐 모니터링 시작]*\n\n"
            alert_message += f"📅 {target_date}\n\n"
            alert_message += f"*현재 상태*\n{description}\n\n"
            alert_message += "_레짐 모니터링을 시작합니다._"
            
            sender = TelegramSender(
                bot_token=os.getenv('TELEGRAM_BOT_TOKEN'),
                chat_id=int(os.getenv('TELEGRAM_CHAT_ID', 0))
            )
            success = sender.send_custom(alert_message, parse_mode='Markdown')
            
            if success:
                print("✅ 첫 실행 알림 전송 성공")
                logger.info("✅ 첫 실행 알림 전송 성공")
            else:
                print("⚠️ 첫 실행 알림 전송 실패")
                logger.warning("⚠️ 첫 실행 알림 전송 실패")
        
        # 현재 레짐 저장
        save_current_regime(current_regime)
        
        return 0
    
    except Exception as e:
        print(f"❌ 레짐 변경 감지 실패: {e}")
        logger.error(f"❌ 레짐 변경 감지 실패: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
