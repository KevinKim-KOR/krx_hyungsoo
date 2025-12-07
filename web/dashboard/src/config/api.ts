// API URL 설정
// Cloud API: 보유종목, 포트폴리오, 대시보드 (DB 관리)
// Local API: 백테스트, ML, 룩백 (무거운 연산)

// 환경 변수에서 읽거나 기본값 사용
export const CLOUD_API_URL = import.meta.env.VITE_CLOUD_API_URL || 'http://168.107.51.68:8000'
export const LOCAL_API_URL = import.meta.env.VITE_LOCAL_API_URL || 'http://localhost:8000'

// 페이지별 API URL 매핑
export const API_URLS = {
  // Cloud API 사용 (DB 관리) - 보유종목, 포트폴리오, 대시보드
  holdings: CLOUD_API_URL,
  portfolio: CLOUD_API_URL,
  dashboard: CLOUD_API_URL,
  regime: CLOUD_API_URL,
  
  // Local API 사용 (무거운 연산) - 백테스트, ML, 룩백
  backtest: LOCAL_API_URL,
  ml: LOCAL_API_URL,
  lookback: LOCAL_API_URL,
  signals: LOCAL_API_URL,
  market: LOCAL_API_URL,
}

// 헬퍼 함수
export function getApiUrl(page: keyof typeof API_URLS): string {
  return API_URLS[page]
}
