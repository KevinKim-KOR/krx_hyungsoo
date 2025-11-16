#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/test_api.py
API 테스트 스크립트
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def print_response(title, response):
    """응답 출력"""
    print(f"\n{'='*60}")
    print(f"📊 {title}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        try:
            data = response.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
        except:
            print(response.text)
    else:
        print(f"Error: {response.text}")
    print()


def test_all_apis():
    """모든 API 테스트"""
    
    print("\n" + "🚀 " * 30)
    print("FastAPI 백엔드 API 테스트")
    print("🚀 " * 30)
    
    # 1. 헬스 체크
    print_response(
        "1. 헬스 체크",
        requests.get(f"{BASE_URL}/health")
    )
    
    # 2. 루트
    print_response(
        "2. 루트",
        requests.get(f"{BASE_URL}/")
    )
    
    # 3. 대시보드 요약
    print_response(
        "3. 대시보드 요약",
        requests.get(f"{BASE_URL}/api/v1/dashboard/summary")
    )
    
    # 4. 백테스트 결과
    print_response(
        "4. 백테스트 결과",
        requests.get(f"{BASE_URL}/api/v1/backtest/results")
    )
    
    # 5. 백테스트 파라미터 비교
    print_response(
        "5. 백테스트 파라미터 비교",
        requests.get(f"{BASE_URL}/api/v1/backtest/compare")
    )
    
    # 6. 손절 전략 목록
    print_response(
        "6. 손절 전략 목록",
        requests.get(f"{BASE_URL}/api/v1/stop-loss/strategies")
    )
    
    # 7. 손절 전략 비교
    print_response(
        "7. 손절 전략 비교",
        requests.get(f"{BASE_URL}/api/v1/stop-loss/comparison")
    )
    
    # 8. 손절 대상 종목
    print_response(
        "8. 손절 대상 종목 (하이브리드)",
        requests.get(f"{BASE_URL}/api/v1/stop-loss/targets?strategy=hybrid")
    )
    
    # 9. 매매 신호
    print_response(
        "9. 매매 신호",
        requests.get(f"{BASE_URL}/api/v1/signals/?days=7")
    )
    
    # 10. 알림 히스토리
    print_response(
        "10. 알림 히스토리",
        requests.get(f"{BASE_URL}/api/v1/signals/alerts?days=7")
    )
    
    # 11. 시장 레짐
    print_response(
        "11. 시장 레짐",
        requests.get(f"{BASE_URL}/api/v1/market/regime")
    )
    
    # 12. 변동성 분석
    print_response(
        "12. 변동성 분석",
        requests.get(f"{BASE_URL}/api/v1/market/volatility")
    )
    
    # 13. 섹터 분석
    print_response(
        "13. 섹터 분석",
        requests.get(f"{BASE_URL}/api/v1/market/sectors")
    )
    
    print("\n" + "✅ " * 30)
    print("테스트 완료!")
    print("✅ " * 30 + "\n")


if __name__ == "__main__":
    try:
        test_all_apis()
    except requests.exceptions.ConnectionError:
        print("\n❌ 오류: FastAPI 서버가 실행되지 않았습니다.")
        print("다음 명령어로 서버를 먼저 실행하세요:")
        print("cd backend")
        print("python -m uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
