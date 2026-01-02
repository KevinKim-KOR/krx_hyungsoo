#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/phase3/monitor_stop_loss.py
실시간 손절 모니터링 및 알림
"""
import sys
import json
import pandas as pd
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pykrx import stock
from extensions.notification.telegram_sender import TelegramSender


class StopLossMonitor:
    """손절 모니터링"""
    
    def __init__(
        self,
        holdings_file: str,
        stop_loss_pct: float = -7.0,
        send_telegram: bool = True
    ):
        """
        Args:
            holdings_file: 보유 종목 JSON 파일 경로
            stop_loss_pct: 손절 비율 (%)
            send_telegram: 텔레그램 알림 전송 여부
        """
        self.holdings_file = holdings_file
        self.stop_loss_pct = stop_loss_pct
        self.send_telegram = send_telegram
        self.holdings = self.load_holdings()
        
        if send_telegram:
            self.telegram = TelegramSender()
    
    def load_holdings(self) -> List[Dict]:
        """보유 종목 로드"""
        with open(self.holdings_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['holdings']
    
    def get_current_price(self, code: str) -> Optional[float]:
        """현재가 조회"""
        try:
            # 6자리 코드만 pykrx 지원
            if len(code) != 6:
                return None
            
            # 오늘 날짜
            today = date.today().strftime('%Y%m%d')
            
            # 최근 5일 데이터 조회 (오늘 데이터 없을 수 있음)
            start_date = (pd.Timestamp.now() - pd.Timedelta(days=5)).strftime('%Y%m%d')
            
            df = stock.get_market_ohlcv_by_date(start_date, today, code)
            
            if df.empty:
                return None
            
            # 가장 최근 종가
            return float(df.iloc[-1]['종가'])
            
        except Exception as e:
            print(f"  ❌ {code} 가격 조회 실패: {e}")
            return None
    
    def check_stop_loss(self) -> List[Dict]:
        """
        손절 체크
        
        Returns:
            list: 손절 대상 종목 리스트
        """
        stop_loss_alerts = []
        
        print("=" * 60)
        print("손절 모니터링 시작")
        print("=" * 60)
        print(f"손절 기준: {self.stop_loss_pct}%")
        print(f"총 {len(self.holdings)}개 종목 체크")
        print("")
        
        for holding in self.holdings:
            code = holding['code']
            name = holding['name']
            avg_price = holding['avg_price']
            quantity = holding['quantity']
            current_return = holding['return_pct']
            
            # 이미 수익 중인 종목은 스킵
            if current_return >= 0:
                continue
            
            # 현재가 조회
            current_price = self.get_current_price(code)
            
            if current_price is None:
                print(f"⚠️ {name} ({code}): 가격 조회 실패")
                continue
            
            # 손실률 계산
            loss_pct = ((current_price / avg_price) - 1) * 100
            
            # 손절 체크
            if loss_pct <= self.stop_loss_pct:
                # 손절 발동!
                loss_amount = (current_price - avg_price) * quantity
                
                stop_loss_alerts.append({
                    'code': code,
                    'name': name,
                    'avg_price': avg_price,
                    'current_price': current_price,
                    'quantity': quantity,
                    'loss_pct': loss_pct,
                    'loss_amount': loss_amount
                })
                
                print(f"🚨 {name} ({code}): 손절 발동!")
                print(f"   매입가: {avg_price:,.0f}원")
                print(f"   현재가: {current_price:,.0f}원")
                print(f"   손실률: {loss_pct:+.2f}%")
                print(f"   손실액: {loss_amount:+,.0f}원")
                print("")
            else:
                # 손절 미발동
                print(f"✅ {name} ({code}): {loss_pct:+.2f}% (손절 기준 미도달)")
        
        return stop_loss_alerts
    
    def send_alert(self, stop_loss_alerts: List[Dict]):
        """
        손절 알림 전송
        
        Args:
            stop_loss_alerts: 손절 대상 종목 리스트
        """
        if not stop_loss_alerts:
            print("\n✅ 손절 대상 없음")
            return
        
        # 메시지 생성
        message = "*[손절 알림] 손절 기준 도달*\n\n"
        message += f"📅 {date.today()}\n"
        message += f"🚨 손절 대상: {len(stop_loss_alerts)}개\n"
        message += f"📉 손절 기준: {self.stop_loss_pct}%\n\n"
        
        total_loss = 0
        
        for i, alert in enumerate(stop_loss_alerts, 1):
            message += f"{i}. {alert['name']} ({alert['code']})\n"
            message += f"   매입가: {alert['avg_price']:,.0f}원\n"
            message += f"   현재가: {alert['current_price']:,.0f}원\n"
            message += f"   손실률: {alert['loss_pct']:+.2f}%\n"
            message += f"   손실액: {alert['loss_amount']:+,.0f}원\n\n"
            
            total_loss += alert['loss_amount']
        
        message += f"💰 총 손실액: {total_loss:+,.0f}원\n\n"
        message += "⚠️ *즉시 매도 검토 필요*"
        
        # 텔레그램 전송
        if self.send_telegram:
            print("\n텔레그램 전송 시도...")
            success = self.telegram.send_custom(message, parse_mode='Markdown')
            
            if success:
                print("✅ 텔레그램 전송 성공")
            else:
                print("❌ 텔레그램 전송 실패")
        else:
            print("\n" + "=" * 60)
            print("알림 메시지 (텔레그램 전송 비활성화)")
            print("=" * 60)
            print(message)
    
    def generate_report(self, stop_loss_alerts: List[Dict]) -> str:
        """
        손절 리포트 생성
        
        Args:
            stop_loss_alerts: 손절 대상 종목 리스트
            
        Returns:
            str: 리포트 텍스트
        """
        lines = []
        lines.append("\n" + "=" * 60)
        lines.append("손절 모니터링 리포트")
        lines.append("=" * 60)
        lines.append(f"날짜: {date.today()}")
        lines.append(f"손절 기준: {self.stop_loss_pct}%")
        lines.append(f"총 종목 수: {len(self.holdings)}개")
        lines.append(f"손절 대상: {len(stop_loss_alerts)}개")
        lines.append("")
        
        if not stop_loss_alerts:
            lines.append("✅ 손절 대상 없음")
            return "\n".join(lines)
        
        total_loss = 0
        
        for i, alert in enumerate(stop_loss_alerts, 1):
            lines.append(f"{i}. {alert['name']} ({alert['code']})")
            lines.append(f"   매입가: {alert['avg_price']:,.0f}원 × {alert['quantity']:.0f}주")
            lines.append(f"   현재가: {alert['current_price']:,.0f}원")
            lines.append(f"   손실률: {alert['loss_pct']:+.2f}%")
            lines.append(f"   손실액: {alert['loss_amount']:+,.0f}원")
            lines.append("")
            
            total_loss += alert['loss_amount']
        
        lines.append("=" * 60)
        lines.append(f"총 손실액: {total_loss:+,.0f}원")
        lines.append("=" * 60)
        lines.append("")
        lines.append("⚠️ 즉시 매도 검토 필요")
        
        return "\n".join(lines)
    
    def run(self):
        """모니터링 실행"""
        # 손절 체크
        stop_loss_alerts = self.check_stop_loss()
        
        # 알림 전송
        self.send_alert(stop_loss_alerts)
        
        # 리포트 생성
        report = self.generate_report(stop_loss_alerts)
        print(report)
        
        # 결과 저장
        output_dir = PROJECT_ROOT / 'data' / 'output'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # JSON 저장
        result = {
            'date': date.today().isoformat(),
            'stop_loss_pct': self.stop_loss_pct,
            'total_holdings': len(self.holdings),
            'stop_loss_count': len(stop_loss_alerts),
            'alerts': stop_loss_alerts
        }
        
        output_file = output_dir / f'stop_loss_monitor_{date.today()}.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n✅ 결과 저장: {output_file}")
        
        return len(stop_loss_alerts)


def main():
    """메인 실행"""
    # 보유 종목 파일 경로
    holdings_file = PROJECT_ROOT / 'data' / 'portfolio' / 'holdings.json'
    
    # 손절 모니터링 실행
    monitor = StopLossMonitor(
        holdings_file=holdings_file,
        stop_loss_pct=-7.0,  # Jason 기준
        send_telegram=True
    )
    
    stop_loss_count = monitor.run()
    
    # 종료 코드
    if stop_loss_count > 0:
        print(f"\n⚠️ 손절 대상 {stop_loss_count}개 발견!")
        return 1
    else:
        print(f"\n✅ 손절 대상 없음")
        return 0


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
