// API URL 설정
// Cloud API (8000): 보유종목, 포트폴리오, 대시보드, 추천 (DB 관리)
// Backtest API (8001): 백테스트, 튜닝 (PC 전용, 무거운 연산)

// 환경 변수에서 읽거나 기본값 사용
export const CLOUD_API_URL = import.meta.env.VITE_CLOUD_API_URL || 'http://168.107.51.68:8000'
export const BACKTEST_API_URL = import.meta.env.VITE_BACKTEST_API_URL || 'http://localhost:8001'

// 페이지별 API URL 매핑
export const API_URLS = {
  // Cloud API 사용 (8000) - DB 관리
  holdings: CLOUD_API_URL,
  portfolio: CLOUD_API_URL,
  dashboard: CLOUD_API_URL,
  regime: CLOUD_API_URL,
  recommendations: CLOUD_API_URL,
  
  // Backtest API 사용 (8001) - PC 전용, 무거운 연산
  backtest: BACKTEST_API_URL,
  tuning: BACKTEST_API_URL,
  strategy: BACKTEST_API_URL,
}

// 헬퍼 함수
export function getApiUrl(page: keyof typeof API_URLS): string {
  return API_URLS[page]
}
