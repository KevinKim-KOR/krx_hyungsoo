#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
"""
scripts/nas/weekly_report.py
주간 리포트 생성 및 전송
"""
import sys
import logging
from datetime import date, timedelta
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.monitoring import SignalTracker, PerformanceTracker, DailyReporter
from extensions.notification.telegram_sender import TelegramSender
from infra.logging.setup import setup_logging

# 로깅 설정
setup_logging()
logger = logging.getLogger(__name__)


def main():
    """주간 리포트 생성 및 전송"""
    logger.info("=" * 60)
    logger.info("주간 리포트 생성 시작")
    logger.info("=" * 60)
    
    try:
        # 1. 날짜 설정 (지난 주)
        end_date = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=7)
        
        logger.info(f"기간: {start_date} ~ {end_date}")
        
        # 2. 리포터 초기화
        signal_tracker = SignalTracker()
        perf_tracker = PerformanceTracker()
        reporter = DailyReporter(signal_tracker, perf_tracker)
        
        # 3. 주간 요약 생성
        logger.info("주간 요약 생성 중...")
        summary = reporter.generate_weekly_summary(end_date)
        
        # 4. 파일 저장
        output_dir = PROJECT_ROOT / "reports" / "weekly"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"weekly_{end_date:%Y%m%d}.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(summary)
        
        logger.info(f"주간 요약 저장: {output_file}")
        
        # 5. 텔레그램 전송
        logger.info("텔레그램 전송 중...")
        
        # 요약을 텔레그램 메시지로 변환 (Markdown)
        message = f"*[주간 리포트] {start_date} ~ {end_date}*\n\n"
        
        # 요약 내용 추출 (처음 1000자만)
        summary_lines = summary.split('\n')
        message_lines = []
        
        for line in summary_lines[3:]:  # 제목 제외
            if line.startswith('##'):
                message_lines.append(f"\n*{line[3:].strip()}*")
            elif line.startswith('-'):
                message_lines.append(f"  {line}")
            elif line.strip() and not line.startswith('#'):
                message_lines.append(line)
        
        message += '\n'.join(message_lines[:30])  # 처음 30줄만
        message += f"\n\n_전체 리포트: {output_file.name}_"
        
        # 전송
        sender = TelegramSender()
        success = sender.send_custom(message, parse_mode='Markdown')
        
        if success:
            logger.info("✅ 주간 리포트 전송 성공")
        else:
            logger.warning("⚠️ 주간 리포트 전송 실패")
        
        logger.info("=" * 60)
        logger.info("주간 리포트 완료")
        logger.info("=" * 60)
        
        return 0
    
    except Exception as e:
        logger.error(f"❌ 주간 리포트 실패: {e}", exc_info=True)
        
        # 에러 알림
        try:
            sender = TelegramSender()
            sender.send_error(e, "주간 리포트 생성")
        except:
            pass
        
        return 1


if __name__ == "__main__":
    sys.exit(main())
