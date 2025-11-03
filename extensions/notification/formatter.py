# -*- coding: utf-8 -*-
"""
extensions/notification/formatter.py
텔레그램 메시지 포맷터
"""
from datetime import date
from typing import List, Dict
from extensions.realtime.signal_generator import Signal


def format_daily_signals(signals: List[Signal], target_date: date) -> str:
    """
    일일 매매 신호 메시지 포맷
    
    Args:
        signals: 신호 리스트
        target_date: 신호 날짜
        
    Returns:
        포맷된 메시지 (Markdown)
    """
    if not signals:
        return f"""*[장마감] 매매 신호 알림*

📅 날짜: {target_date}
📊 신호 수: 0개

⚠️ 오늘은 매수 신호가 없습니다.
"""
    
    # 매수/매도/유지 분류
    buy_signals = [s for s in signals if s.action == 'BUY']
    sell_signals = [s for s in signals if s.action == 'SELL']
    hold_signals = [s for s in signals if s.action == 'HOLD']
    
    # 메시지 구성
    lines = [
        "*[장마감] 매매 신호 알림*",
        "",
        f"📅 날짜: {target_date}",
        f"📊 총 신호: {len(signals)}개",
        f"   • 매수: {len(buy_signals)}개",
        f"   • 매도: {len(sell_signals)}개",
        f"   • 유지: {len(hold_signals)}개",
        "",
    ]
    
    # 매수 신호
    if buy_signals:
        lines.append("*🟢 매수 신호*")
        lines.append("")
        
        # 신뢰도 순으로 정렬
        sorted_buys = sorted(buy_signals, key=lambda x: x.confidence, reverse=True)
        
        for i, signal in enumerate(sorted_buys[:10], 1):  # 상위 10개만
            lines.append(f"{i}. `{signal.code}` ({signal.name})")
            lines.append(f"   • 신뢰도: {signal.confidence:.1%} | 비중: {signal.target_weight:.1%}")
            lines.append(f"   • 가격: {signal.current_price:,.0f}원")
            lines.append(f"   • MAPS: {signal.maps_score:.2f} | RSI: {signal.rsi_value:.0f}")
            lines.append(f"   • 사유: {signal.reason}")
            lines.append("")
    
    # 매도 신호
    if sell_signals:
        lines.append("*🔴 매도 신호*")
        lines.append("")
        
        for i, signal in enumerate(sell_signals[:5], 1):  # 상위 5개만
            lines.append(f"{i}. `{signal.code}` ({signal.name})")
            lines.append(f"   • 가격: {signal.current_price:,.0f}원")
            lines.append(f"   • MAPS: {signal.maps_score:.2f} | RSI: {signal.rsi_value:.0f}")
            lines.append(f"   • 사유: {signal.reason}")
            lines.append("")
    
    # 푸터
    lines.append("---")
    lines.append("_자동 생성된 신호입니다. 투자 판단은 신중히 하세요._")
    
    return "\n".join(lines)


def format_portfolio_summary(signals: List[Signal], summary: Dict) -> str:
    """
    포트폴리오 요약 메시지 포맷
    
    Args:
        signals: 신호 리스트
        summary: 포트폴리오 요약 딕셔너리
        
    Returns:
        포맷된 메시지 (Markdown)
    """
    lines = [
        "*📊 포트폴리오 요약*",
        "",
        f"• 총 포지션: {summary['total_positions']}개",
        f"• 총 비중: {summary['total_weight']:.1%}",
        f"• 평균 신뢰도: {summary['avg_confidence']:.2f}",
        "",
        "*상위 5개 종목*",
        ""
    ]
    
    for i, signal in enumerate(summary.get('top_signals', [])[:5], 1):
        lines.append(f"{i}. `{signal.code}` - {signal.target_weight:.1%}")
        lines.append(f"   신뢰도: {signal.confidence:.2f} | MAPS: {signal.maps_score:.2f}")
        lines.append("")
    
    return "\n".join(lines)


def format_rebalancing_actions(actions: List) -> str:
    """
    리밸런싱 액션 메시지 포맷
    
    Args:
        actions: 액션 리스트
        
    Returns:
        포맷된 메시지 (Markdown)
    """
    if not actions:
        return "*리밸런싱 불필요*\n\n현재 포트폴리오가 목표와 일치합니다."
    
    # 매수/매도 액션만 필터
    active_actions = [a for a in actions if a.action_type != 'HOLD']
    
    if not active_actions:
        return "*리밸런싱 불필요*\n\n현재 포트폴리오가 목표와 일치합니다."
    
    lines = [
        "*🔄 리밸런싱 필요*",
        "",
        f"총 {len(active_actions)}개 액션",
        ""
    ]
    
    # 매수 액션
    buy_actions = [a for a in active_actions if a.action_type == 'BUY']
    if buy_actions:
        lines.append("*매수*")
        for action in buy_actions[:5]:
            lines.append(f"• `{action.code}`: {abs(action.quantity_diff)}주")
            lines.append(f"  예상 금액: {action.estimated_amount:,.0f}원")
        lines.append("")
    
    # 매도 액션
    sell_actions = [a for a in active_actions if a.action_type == 'SELL']
    if sell_actions:
        lines.append("*매도*")
        for action in sell_actions[:5]:
            lines.append(f"• `{action.code}`: {abs(action.quantity_diff)}주")
            lines.append(f"  예상 금액: {action.estimated_amount:,.0f}원")
        lines.append("")
    
    return "\n".join(lines)


def format_error_message(error: Exception, context: str = "") -> str:
    """
    에러 메시지 포맷
    
    Args:
        error: 예외 객체
        context: 에러 발생 컨텍스트
        
    Returns:
        포맷된 에러 메시지
    """
    lines = [
        "*⚠️ 오류 발생*",
        "",
        f"컨텍스트: {context}",
        f"오류: {str(error)}",
        "",
        "시스템 관리자에게 문의하세요."
    ]
    
    return "\n".join(lines)
