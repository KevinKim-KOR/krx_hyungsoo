# -*- coding: utf-8 -*-
"""
scripts/automation/run_daily_report.py
일일 리포트 실행 스크립트

NAS Cron에서 실행:
    0 16 * * 1-5 python3 /path/to/run_daily_report.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import os
from datetime import date
import logging

# 환경 변수 로드 (config/env.nas.sh 우선, .env 보조)
PROJECT_ROOT = Path(__file__).parent.parent.parent

def load_env_vars():
    """NAS 환경 변수 로드"""
    # 1. config/env.nas.sh에서 로드 (우선)
    env_sh = PROJECT_ROOT / "config" / "env.nas.sh"
    if env_sh.exists():
        import subprocess
        try:
            # bash로 env.nas.sh 실행 후 환경 변수 추출
            result = subprocess.run(
                f'source {env_sh} && env',
                shell=True,
                capture_output=True,
                text=True,
                executable='/bin/bash'
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if '=' in line:
                        key, _, value = line.partition('=')
                        if key in ['TG_TOKEN', 'TG_CHAT_ID', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']:
                            os.environ[key] = value
        except Exception as e:
            print(f"⚠️ env.nas.sh 로드 실패: {e}")
    
    # 2. .env 파일에서 로드 (보조)
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    
    # 3. TG_TOKEN -> TELEGRAM_BOT_TOKEN 변환
    if 'TG_TOKEN' in os.environ and 'TELEGRAM_BOT_TOKEN' not in os.environ:
        os.environ['TELEGRAM_BOT_TOKEN'] = os.environ['TG_TOKEN']
    if 'TG_CHAT_ID' in os.environ and 'TELEGRAM_CHAT_ID' not in os.environ:
        os.environ['TELEGRAM_CHAT_ID'] = os.environ['TG_CHAT_ID']

load_env_vars()

from extensions.automation.daily_report import DailyReport

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """메인 함수"""
    try:
        # 환경 변수 로드
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # 디버깅 정보
        logger.info(f"TELEGRAM_BOT_TOKEN: {'*' * 10 if bot_token else 'None'}")
        logger.info(f"TELEGRAM_CHAT_ID: {chat_id if chat_id else 'None'}")
        
        # 텔레그램 활성화 여부
        telegram_enabled = bool(bot_token and chat_id)
        
        if not telegram_enabled:
            logger.warning("텔레그램 설정이 없습니다. 로그 모드로 실행합니다.")
        else:
            logger.info("텔레그램 설정 확인 완료. 알림 모드로 실행합니다.")
        
        # 리포트 생성
        reporter = DailyReport(
            telegram_enabled=telegram_enabled,
            bot_token=bot_token,
            chat_id=chat_id
        )
        
        # 실행
        logger.info("일일 리포트 생성 시작")
        
        report = reporter.generate_report(
            target_date=date.today(),
            current_holdings=[],  # TODO: 실제 보유 종목 입력
            portfolio_value=None,  # TODO: 실제 포트폴리오 가치 입력
            initial_capital=10000000
        )
        
        print(report)
        logger.info("일일 리포트 생성 완료")
        
    except Exception as e:
        logger.error(f"일일 리포트 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
