# -*- coding: utf-8 -*-
"""
ui/portfolio_manager.py
포트폴리오 관리 UI (Streamlit)

기능:
- 보유 종목 추가/수정/삭제
- 추가 매수 처리 (평균 단가 자동 계산)
- 현재가 자동 조회
- 평가손익 실시간 계산
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path
import json
import sys

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pykrx.website import naver


# 페이지 설정
st.set_page_config(
    page_title="포트폴리오 관리",
    page_icon="💼",
    layout="wide"
)


class PortfolioManager:
    """포트폴리오 관리 클래스"""
    
    def __init__(self, data_file: Path):
        """
        Args:
            data_file: 포트폴리오 데이터 파일 경로
        """
        self.data_file = data_file
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        
        # ETF 이름 매핑
        self.etf_names = {
            '069500': 'KODEX 200',
            '102110': 'TIGER 200',
            '229200': 'KODEX 코스닥150',
            '091160': 'KODEX 반도체',
            '091180': 'KODEX 자동차',
            '091170': 'KODEX 은행',
            '102780': 'KODEX 삼성그룹',
            '117460': 'KODEX 2차전지산업',
            '364980': 'KODEX 2차전지산업',
            '272560': 'KODEX 미국S&P500TR',
            '379800': 'KODEX 미국나스닥100TR',
            '360750': 'TIGER 미국S&P500',
            '133690': 'TIGER 미국나스닥100',
        }
    
    def load_portfolio(self) -> dict:
        """포트폴리오 로드"""
        if self.data_file.exists():
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {
                'last_updated': datetime.now().isoformat(),
                'holdings': [],
                'cash': 0,
                'initial_capital': 10000000
            }
    
    def save_portfolio(self, portfolio: dict):
        """포트폴리오 저장"""
        portfolio['last_updated'] = datetime.now().isoformat()
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(portfolio, f, ensure_ascii=False, indent=2)
    
    def get_stock_name(self, code: str) -> str:
        """종목명 조회"""
        # 매핑 테이블 우선
        if code in self.etf_names:
            return self.etf_names[code]
        
        # PyKRX로 조회 시도
        try:
            import pykrx.stock as stock
            name = stock.get_market_ticker_name(code)
            if name and isinstance(name, str) and name.strip():
                return name.strip()
        except:
            pass
        
        return f"종목_{code}"
    
    def get_current_price(self, code: str) -> float:
        """현재가 조회 (네이버 API)"""
        try:
            from datetime import date, timedelta
            today = date.today()
            fromdate = (today - timedelta(days=5)).strftime('%Y%m%d')
            todate = today.strftime('%Y%m%d')
            
            df = naver.get_market_ohlcv_by_date(fromdate, todate, code)
            
            if not df.empty:
                return float(df.iloc[-1]['종가'])
        except Exception as e:
            st.warning(f"현재가 조회 실패 [{code}]: {e}")
        
        return 0.0
    
    def add_holding(self, portfolio: dict, code: str, quantity: int, avg_price: float):
        """종목 추가"""
        # 종목명 조회
        name = self.get_stock_name(code)
        
        # 현재가 조회
        current_price = self.get_current_price(code)
        
        # 계산
        total_cost = quantity * avg_price
        current_value = quantity * current_price if current_price > 0 else 0
        return_amount = current_value - total_cost
        return_pct = (return_amount / total_cost * 100) if total_cost > 0 else 0
        
        holding = {
            'code': code,
            'name': name,
            'quantity': quantity,
            'avg_price': avg_price,
            'total_cost': total_cost,
            'current_price': current_price,
            'current_value': current_value,
            'return_amount': return_amount,
            'return_pct': return_pct,
            'last_updated': datetime.now().isoformat()
        }
        
        portfolio['holdings'].append(holding)
        return holding
    
    def update_holding(self, portfolio: dict, index: int, quantity: int, avg_price: float):
        """종목 수정"""
        holding = portfolio['holdings'][index]
        code = holding['code']
        
        # 현재가 조회
        current_price = self.get_current_price(code)
        
        # 계산
        total_cost = quantity * avg_price
        current_value = quantity * current_price if current_price > 0 else 0
        return_amount = current_value - total_cost
        return_pct = (return_amount / total_cost * 100) if total_cost > 0 else 0
        
        # 업데이트
        holding['quantity'] = quantity
        holding['avg_price'] = avg_price
        holding['total_cost'] = total_cost
        holding['current_price'] = current_price
        holding['current_value'] = current_value
        holding['return_amount'] = return_amount
        holding['return_pct'] = return_pct
        holding['last_updated'] = datetime.now().isoformat()
    
    def add_purchase(self, portfolio: dict, index: int, add_quantity: int, add_price: float):
        """추가 매수 (평균 단가 자동 계산)"""
        holding = portfolio['holdings'][index]
        
        # 기존 정보
        old_quantity = holding['quantity']
        old_avg_price = holding['avg_price']
        old_total_cost = old_quantity * old_avg_price
        
        # 추가 매수
        add_total_cost = add_quantity * add_price
        
        # 새로운 평균 단가 계산
        new_quantity = old_quantity + add_quantity
        new_total_cost = old_total_cost + add_total_cost
        new_avg_price = new_total_cost / new_quantity
        
        # 업데이트
        self.update_holding(portfolio, index, new_quantity, new_avg_price)
        
        return {
            'old_quantity': old_quantity,
            'old_avg_price': old_avg_price,
            'new_quantity': new_quantity,
            'new_avg_price': new_avg_price
        }
    
    def delete_holding(self, portfolio: dict, index: int):
        """종목 삭제"""
        del portfolio['holdings'][index]
    
    def update_all_prices(self, portfolio: dict):
        """모든 종목 현재가 업데이트"""
        for holding in portfolio['holdings']:
            code = holding['code']
            current_price = self.get_current_price(code)
            
            if current_price > 0:
                holding['current_price'] = current_price
                holding['current_value'] = holding['quantity'] * current_price
                holding['return_amount'] = holding['current_value'] - holding['total_cost']
                holding['return_pct'] = (holding['return_amount'] / holding['total_cost'] * 100) if holding['total_cost'] > 0 else 0
                holding['last_updated'] = datetime.now().isoformat()


def main():
    """메인 함수"""
    st.title("💼 포트폴리오 관리")
    
    # 포트폴리오 매니저 초기화
    data_file = PROJECT_ROOT / "data" / "portfolio" / "holdings.json"
    manager = PortfolioManager(data_file)
    
    # 포트폴리오 로드
    if 'portfolio' not in st.session_state:
        st.session_state.portfolio = manager.load_portfolio()
    
    portfolio = st.session_state.portfolio
    
    # 사이드바: 메뉴
    st.sidebar.title("📋 메뉴")
    menu = st.sidebar.radio(
        "선택",
        ["📊 포트폴리오 현황", "➕ 종목 추가", "📈 추가 매수", "✏️ 종목 수정", "🗑️ 종목 삭제"]
    )
    
    # 1. 포트폴리오 현황
    if menu == "📊 포트폴리오 현황":
        st.header("📊 전체 현황")
        
        # 현재가 업데이트 버튼
        col1, col2, col3 = st.columns([1, 1, 4])
        with col1:
            if st.button("🔄 현재가 업데이트"):
                with st.spinner("현재가 조회 중..."):
                    manager.update_all_prices(portfolio)
                    manager.save_portfolio(portfolio)
                st.success("✅ 현재가 업데이트 완료!")
                st.rerun()
        
        with col2:
            if st.button("💾 저장"):
                manager.save_portfolio(portfolio)
                st.success("✅ 저장 완료!")
        
        # 전체 통계
        holdings = portfolio['holdings']
        if holdings:
            total_cost = sum(h['total_cost'] for h in holdings)
            total_value = sum(h['current_value'] for h in holdings)
            total_return = total_value - total_cost
            total_return_pct = (total_return / total_cost * 100) if total_cost > 0 else 0
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("총 평가액", f"{total_value:,.0f}원")
            with col2:
                st.metric("총 매입액", f"{total_cost:,.0f}원")
            with col3:
                st.metric("평가손익", f"{total_return:+,.0f}원", f"{total_return_pct:+.2f}%")
            with col4:
                st.metric("보유 종목", f"{len(holdings)}개")
            
            st.divider()
            
            # 보유 종목 테이블
            st.subheader("📈 보유 종목 목록")
            
            df = pd.DataFrame(holdings)
            df_display = df[[
                'name', 'code', 'quantity', 'avg_price', 'current_price',
                'total_cost', 'current_value', 'return_amount', 'return_pct'
            ]].copy()
            
            df_display.columns = [
                '종목명', '코드', '수량', '평균단가', '현재가',
                '매입금액', '평가금액', '평가손익', '수익률(%)'
            ]
            
            # 숫자 포맷팅
            df_display['수량'] = df_display['수량'].apply(lambda x: f"{x:,}")
            df_display['평균단가'] = df_display['평균단가'].apply(lambda x: f"{x:,.0f}")
            df_display['현재가'] = df_display['현재가'].apply(lambda x: f"{x:,.0f}")
            df_display['매입금액'] = df_display['매입금액'].apply(lambda x: f"{x:,.0f}")
            df_display['평가금액'] = df_display['평가금액'].apply(lambda x: f"{x:,.0f}")
            df_display['평가손익'] = df_display['평가손익'].apply(lambda x: f"{x:+,.0f}")
            df_display['수익률(%)'] = df_display['수익률(%)'].apply(lambda x: f"{x:+.2f}")
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
        else:
            st.info("보유 종목이 없습니다. '➕ 종목 추가' 메뉴에서 종목을 추가하세요.")
    
    # 2. 종목 추가
    elif menu == "➕ 종목 추가":
        st.header("➕ 종목 추가")
        
        with st.form("add_holding_form"):
            code = st.text_input("종목 코드", placeholder="예: 069500")
            
            if code:
                name = manager.get_stock_name(code)
                st.info(f"종목명: **{name}**")
            
            quantity = st.number_input("보유 수량 (주)", min_value=1, value=100, step=1)
            avg_price = st.number_input("평균 단가 (원)", min_value=1, value=50000, step=100)
            
            # 계산 미리보기
            total_cost = quantity * avg_price
            st.info(f"💡 총 매입금액: **{total_cost:,.0f}원**")
            
            submitted = st.form_submit_button("✅ 추가")
            
            if submitted:
                if not code:
                    st.error("종목 코드를 입력하세요.")
                else:
                    with st.spinner("종목 추가 중..."):
                        holding = manager.add_holding(portfolio, code, quantity, avg_price)
                        manager.save_portfolio(portfolio)
                    
                    st.success(f"✅ {holding['name']} 추가 완료!")
                    st.rerun()
    
    # 3. 추가 매수
    elif menu == "📈 추가 매수":
        st.header("📈 추가 매수")
        
        holdings = portfolio['holdings']
        if not holdings:
            st.warning("보유 종목이 없습니다. 먼저 종목을 추가하세요.")
        else:
            # 종목 선택
            holding_names = [f"{h['name']} ({h['code']})" for h in holdings]
            selected = st.selectbox("종목 선택", holding_names)
            selected_index = holding_names.index(selected)
            holding = holdings[selected_index]
            
            # 현재 보유 정보
            st.subheader("현재 보유")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("수량", f"{holding['quantity']:,}주")
            with col2:
                st.metric("평균 단가", f"{holding['avg_price']:,.0f}원")
            with col3:
                st.metric("총 매입금액", f"{holding['total_cost']:,.0f}원")
            
            st.divider()
            
            # 추가 매수 입력
            with st.form("add_purchase_form"):
                st.subheader("추가 매수")
                
                add_quantity = st.number_input("추가 수량 (주)", min_value=1, value=10, step=1)
                add_price = st.number_input("매수 단가 (원)", min_value=1, value=int(holding['avg_price']), step=100)
                
                # 계산 미리보기
                new_quantity = holding['quantity'] + add_quantity
                new_total_cost = holding['total_cost'] + (add_quantity * add_price)
                new_avg_price = new_total_cost / new_quantity
                
                st.info("💡 **매수 후 예상**")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("총 수량", f"{new_quantity:,}주", f"+{add_quantity}")
                with col2:
                    st.metric("평균 단가", f"{new_avg_price:,.0f}원", f"{new_avg_price - holding['avg_price']:+,.0f}")
                with col3:
                    st.metric("총 매입금액", f"{new_total_cost:,.0f}원", f"+{add_quantity * add_price:,.0f}")
                
                submitted = st.form_submit_button("✅ 매수 실행")
                
                if submitted:
                    with st.spinner("추가 매수 처리 중..."):
                        result = manager.add_purchase(portfolio, selected_index, add_quantity, add_price)
                        manager.save_portfolio(portfolio)
                    
                    st.success("✅ 추가 매수 완료!")
                    st.info(f"평균 단가: {result['old_avg_price']:,.0f}원 → {result['new_avg_price']:,.0f}원")
                    st.rerun()
    
    # 4. 종목 수정
    elif menu == "✏️ 종목 수정":
        st.header("✏️ 종목 수정")
        
        holdings = portfolio['holdings']
        if not holdings:
            st.warning("보유 종목이 없습니다.")
        else:
            # 종목 선택
            holding_names = [f"{h['name']} ({h['code']})" for h in holdings]
            selected = st.selectbox("종목 선택", holding_names)
            selected_index = holding_names.index(selected)
            holding = holdings[selected_index]
            
            # 수정 폼
            with st.form("update_holding_form"):
                st.info(f"종목명: **{holding['name']}** (코드: {holding['code']})")
                
                quantity = st.number_input("보유 수량 (주)", min_value=1, value=holding['quantity'], step=1)
                avg_price = st.number_input("평균 단가 (원)", min_value=1, value=int(holding['avg_price']), step=100)
                
                # 계산 미리보기
                total_cost = quantity * avg_price
                st.info(f"💡 총 매입금액: **{total_cost:,.0f}원**")
                
                submitted = st.form_submit_button("✅ 수정")
                
                if submitted:
                    with st.spinner("종목 수정 중..."):
                        manager.update_holding(portfolio, selected_index, quantity, avg_price)
                        manager.save_portfolio(portfolio)
                    
                    st.success("✅ 수정 완료!")
                    st.rerun()
    
    # 5. 종목 삭제
    elif menu == "🗑️ 종목 삭제":
        st.header("🗑️ 종목 삭제")
        
        holdings = portfolio['holdings']
        if not holdings:
            st.warning("보유 종목이 없습니다.")
        else:
            # 종목 선택
            holding_names = [f"{h['name']} ({h['code']})" for h in holdings]
            selected = st.selectbox("종목 선택", holding_names)
            selected_index = holding_names.index(selected)
            holding = holdings[selected_index]
            
            # 삭제 확인
            st.warning(f"**{holding['name']}** 종목을 삭제하시겠습니까?")
            st.info(f"수량: {holding['quantity']:,}주 | 평균 단가: {holding['avg_price']:,.0f}원")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ 삭제", type="primary"):
                    manager.delete_holding(portfolio, selected_index)
                    manager.save_portfolio(portfolio)
                    st.success("✅ 삭제 완료!")
                    st.rerun()
            with col2:
                if st.button("취소"):
                    st.info("삭제 취소됨")


if __name__ == "__main__":
    main()
