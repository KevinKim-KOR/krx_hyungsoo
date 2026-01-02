#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
nas/app_realtime.py
NAS 실시간 신호 생성 및 알림 (경량 버전)
"""
import sys
import logging
from datetime import date, timedelta
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.realtime import RealtimeSignalGenerator, RealtimeDataCollector
from extensions.notification import send_daily_signals
from extensions.monitoring import SignalTracker, PerformanceTracker, DailyReporter, RegimeDetector
from infra.logging.setup import setup_logging

# 로깅 설정
setup_logging()
logger = logging.getLogger(__name__)


def load_best_params() -> dict:
    """최적 파라미터 로드"""
    import json
    
    params_file = PROJECT_ROOT / "best_params.json"
    
    if params_file.exists():
        with open(params_file, 'r', encoding='utf-8') as f:
            params = json.load(f)
            logger.info(f"파라미터 로드: {params_file}")
            return params
    
    # 기본 파라미터
    default_params = {
        'ma_period': 60,
        'rsi_period': 14,
        'rsi_overbought': 70,
        'maps_buy_threshold': 1.0,
        'maps_sell_threshold': -5.0,
        'max_positions': 10,
        'min_confidence': 0.1,
        'portfolio_vol_target': 0.15,
        'max_drawdown_threshold': -0.15,
        'cooldown_days': 7,
        'max_correlation': 0.7
    }
    
    logger.warning(f"파라미터 파일 없음, 기본값 사용: {params_file}")
    return default_params


def main():
    """메인 실행 함수"""
    logger.info("=" * 60)
    logger.info("실시간 신호 생성 및 알림 시작")
    logger.info("=" * 60)
    
    try:
        # 1. 날짜 설정 (어제 데이터 사용)
        target_date = date.today() - timedelta(days=1)
        logger.info(f"대상 날짜: {target_date}")
        
        # 2. 데이터 수집 (선택적)
        # collector = RealtimeDataCollector()
        # logger.info("데이터 수집 시작...")
        # if not collector.update_latest(target_date):
        #     logger.warning("데이터 수집 실패, 기존 캐시 사용")
        
        # 3. 파라미터 로드
        params = load_best_params()
        
        # 4. 신호 생성
        logger.info("신호 생성 시작...")
        generator = RealtimeSignalGenerator(params)
        signals = generator.generate_signals(target_date)
        
        logger.info(f"생성된 신호: {len(signals)}개")
        
        # 5. 포트폴리오 요약
        summary = generator.get_portfolio_summary(signals)
        
        # 6. 신호 CSV 저장
        output_dir = PROJECT_ROOT / "reports" / "realtime"
        output_file = output_dir / f"signals_{target_date:%Y%m%d}.csv"
        generator.save_signals(signals, output_file)
        
        # 7. 신호 이력 DB 저장
        logger.info("신호 이력 저장...")
        signal_tracker = SignalTracker()
        signal_tracker.save_signals(signals, target_date)
        
        # 8. 레짐 감지
        logger.info("시장 레짐 감지...")
        regime_detector = RegimeDetector()
        regime = regime_detector.detect_regime(target_date)
        logger.info(f"레짐: {regime['state']}, 변동성={regime['volatility']:.2%}")
        
        # 9. 일일 리포트 생성
        logger.info("일일 리포트 생성...")
        reporter = DailyReporter(signal_tracker)
        report = reporter.generate_daily_report(target_date, signals)
        reporter.save_report(target_date, report)
        
        # 10. 텔레그램 알림
        logger.info("텔레그램 알림 전송...")
        success = send_daily_signals(signals, target_date, summary)
        
        if success:
            logger.info("✅ 알림 전송 성공")
        else:
            logger.warning("⚠️ 알림 전송 실패")
        
        # 11. 완료
        logger.info("=" * 60)
        logger.info("작업 완료")
        logger.info("=" * 60)
        
        return 0
    
    except Exception as e:
        logger.error(f"❌ 오류 발생: {e}", exc_info=True)
        
        # 에러 알림
        try:
            from extensions.notification.telegram_sender import TelegramSender
            sender = TelegramSender()
            sender.send_error(e, "실시간 신호 생성")
        except:
            pass
        
        return 1


if __name__ == "__main__":
    sys.exit(main())
