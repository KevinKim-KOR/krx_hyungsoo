#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
core/strategy/us_market_monitor.py
미국 시장 지표 모니터링

유연한 구조:
- YAML 설정 파일로 지표 선택
- ChatGPT와 대화로 조정 가능
- 새로운 지표 쉽게 추가
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from core.data_loader import get_ohlcv

logger = logging.getLogger(__name__)

# 설정 파일 경로
CONFIG_FILE = Path(__file__).parent.parent.parent / "config" / "us_market_indicators.yaml"


class USMarketMonitor:
    """미국 시장 지표 모니터"""
    
    def __init__(self, config_file: Optional[Path] = None):
        """
        초기화
        
        Args:
            config_file: 설정 파일 경로 (기본값: config/us_market_indicators.yaml)
        """
        self.config_file = config_file or CONFIG_FILE
        self.config = self.load_config()
        self.indicators = {}
        
    def load_config(self) -> Dict:
        """설정 파일 로드"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"✅ 설정 파일 로드: {self.config_file}")
            return config
        except Exception as e:
            logger.error(f"설정 파일 로드 실패: {e}")
            return {}
    
    def calculate_indicator(self, indicator_name: str) -> Optional[Dict]:
        """
        지표 계산
        
        Args:
            indicator_name: 지표 이름 (예: nasdaq_50ma, sp500_200ma, vix)
        
        Returns:
            지표 정보 딕셔너리
        """
        if indicator_name not in self.config:
            logger.warning(f"지표 설정 없음: {indicator_name}")
            return None
        
        indicator_config = self.config[indicator_name]
        
        if not indicator_config.get('enabled', False):
            logger.info(f"지표 비활성화: {indicator_name}")
            return None
        
        try:
            # 데이터 가져오기
            symbol = indicator_config['symbol']
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            
            data = get_ohlcv(
                symbol,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )
            
            if data is None or data.empty:
                logger.error(f"데이터 없음: {symbol}")
                return None
            
            # 컬럼명 확인 (close 또는 Close)
            close_col = 'Close' if 'Close' in data.columns else 'close'
            current_price = float(data[close_col].iloc[-1])
            
            # 이동평균 지표
            if 'period' in indicator_config:
                period = indicator_config['period']
                ma = float(data[close_col].rolling(period).mean().iloc[-1])
                deviation = float((current_price - ma) / ma)
                threshold = float(indicator_config.get('threshold', 0.02))
                
                # 신호 판단
                if deviation > threshold:
                    signal = 'bullish'
                elif deviation < -threshold:
                    signal = 'bearish'
                else:
                    signal = 'neutral'
                
                return {
                    'name': indicator_name,
                    'symbol': symbol,
                    'current_price': current_price,
                    'ma_value': ma,
                    'deviation': deviation,
                    'signal': signal,
                    'weight': indicator_config.get('weight', 0.0),
                    'description': indicator_config.get('description', ''),
                    'interpretation': indicator_config['signals'].get(signal, '')
                }
            
            # VIX 지표
            elif indicator_name == 'vix':
                threshold_high = indicator_config.get('threshold_high', 20)
                threshold_low = indicator_config.get('threshold_low', 12)
                
                if current_price < threshold_low:
                    signal = 'bullish'
                elif current_price > threshold_high:
                    signal = 'bearish'
                else:
                    signal = 'neutral'
                
                return {
                    'name': indicator_name,
                    'symbol': symbol,
                    'current_value': current_price,
                    'signal': signal,
                    'weight': indicator_config.get('weight', 0.0),
                    'description': indicator_config.get('description', ''),
                    'interpretation': indicator_config['signals'].get(signal, '')
                }
            
        except Exception as e:
            logger.error(f"지표 계산 실패 ({indicator_name}): {e}")
            return None
    
    def calculate_all_indicators(self) -> Dict[str, Dict]:
        """모든 활성화된 지표 계산"""
        enabled = self.config.get('enabled_indicators', [])
        
        results = {}
        for indicator_name in enabled:
            result = self.calculate_indicator(indicator_name)
            if result:
                results[indicator_name] = result
        
        return results
    
    def determine_us_market_regime(self) -> str:
        """
        미국 시장 레짐 판단
        
        Returns:
            'bullish', 'bearish', 'neutral'
        """
        indicators = self.calculate_all_indicators()
        
        if not indicators:
            logger.warning("지표 없음, 중립장으로 판단")
            return 'neutral'
        
        # 가중 평균 계산
        total_weight = 0.0
        weighted_score = 0.0
        
        signal_scores = {
            'bullish': 1.0,
            'neutral': 0.0,
            'bearish': -1.0
        }
        
        for indicator in indicators.values():
            weight = indicator.get('weight', 0.0)
            signal = indicator.get('signal', 'neutral')
            score = signal_scores.get(signal, 0.0)
            
            weighted_score += score * weight
            total_weight += weight
        
        if total_weight == 0:
            return 'neutral'
        
        avg_score = weighted_score / total_weight
        
        # 레짐 판단
        if avg_score > 0.3:
            return 'bullish'
        elif avg_score < -0.3:
            return 'bearish'
        else:
            return 'neutral'
    
    def check_urgent_alerts(self) -> List[str]:
        """긴급 알림 확인"""
        indicators = self.calculate_all_indicators()
        alerts = []
        
        urgent_rules = self.config.get('alerts', {}).get('urgent', [])
        
        for rule in urgent_rules:
            # 규칙 파싱 (예: "nasdaq_50ma < -0.05")
            parts = rule.split()
            if len(parts) != 3:
                continue
            
            indicator_name, operator, threshold = parts
            threshold = float(threshold)
            
            if indicator_name not in indicators:
                continue
            
            indicator = indicators[indicator_name]
            value = indicator.get('deviation', 0.0)
            
            # 조건 확인
            if operator == '<' and value < threshold:
                alerts.append(f"🚨 {indicator['description']}: {value:.2%} (기준: {threshold:.2%})")
            elif operator == '>' and value > threshold:
                alerts.append(f"🚨 {indicator['description']}: {value:.2%} (기준: {threshold:.2%})")
        
        return alerts
    
    def generate_report(self) -> str:
        """미국 시장 지표 리포트 생성"""
        indicators = self.calculate_all_indicators()
        regime = self.determine_us_market_regime()
        
        report = """
📊 미국 시장 지표 분석

"""
        
        # 레짐
        regime_emoji = {
            'bullish': '📈',
            'neutral': '➡️',
            'bearish': '📉'
        }
        
        regime_text = {
            'bullish': '상승',
            'neutral': '중립',
            'bearish': '하락'
        }
        
        report += f"{regime_emoji[regime]} 미국 시장 레짐: {regime_text[regime]}\n\n"
        
        # 각 지표
        for indicator in indicators.values():
            name = indicator.get('description', indicator['name'])
            
            if 'deviation' in indicator:
                # 이동평균 지표
                current = indicator['current_price']
                ma = indicator['ma_value']
                deviation = indicator['deviation']
                signal = indicator['signal']
                
                report += f"📌 {name}\n"
                report += f"   현재가: {current:,.0f}\n"
                report += f"   이동평균: {ma:,.0f}\n"
                report += f"   괴리율: {deviation:+.2%}\n"
                report += f"   신호: {signal}\n"
                report += f"   해석: {indicator['interpretation']}\n\n"
            
            elif 'current_value' in indicator:
                # VIX 등
                value = indicator['current_value']
                signal = indicator['signal']
                
                report += f"📌 {name}\n"
                report += f"   현재값: {value:.2f}\n"
                report += f"   신호: {signal}\n"
                report += f"   해석: {indicator['interpretation']}\n\n"
        
        # 긴급 알림
        urgent_alerts = self.check_urgent_alerts()
        if urgent_alerts:
            report += "⚠️ 긴급 알림:\n"
            for alert in urgent_alerts:
                report += f"   {alert}\n"
        
        return report.strip()
    
    def generate_chatgpt_prompt(self) -> str:
        """ChatGPT 프롬프트 생성"""
        indicators = self.calculate_all_indicators()
        
        # 템플릿 로드
        template = self.config.get('chatgpt_prompt', '')
        
        # 변수 치환
        nasdaq_50ma = indicators.get('nasdaq_50ma', {})
        sp500_200ma = indicators.get('sp500_200ma', {})
        vix = indicators.get('vix', {})
        
        prompt = template.format(
            nasdaq_50ma_status=f"{nasdaq_50ma.get('deviation', 0):.2%}" if nasdaq_50ma else "N/A",
            sp500_200ma_status=f"{sp500_200ma.get('deviation', 0):.2%}" if sp500_200ma else "N/A",
            vix_value=f"{vix.get('current_value', 0):.2f}" if vix else "N/A",
            kospi_status="TODO",  # 한국 시장 정보 추가 필요
            main_sector="AI/반도체"  # 현재 주요 섹터
        )
        
        return prompt


def main():
    """테스트"""
    monitor = USMarketMonitor()
    
    print("=" * 60)
    print("미국 시장 지표 모니터링")
    print("=" * 60)
    
    # 리포트 생성
    report = monitor.generate_report()
    print(report)
    
    print("\n" + "=" * 60)
    print("ChatGPT 프롬프트")
    print("=" * 60)
    
    # ChatGPT 프롬프트
    prompt = monitor.generate_chatgpt_prompt()
    print(prompt)


if __name__ == "__main__":
    main()
