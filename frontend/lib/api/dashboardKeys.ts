// POC3-01 REMEDIATION — Dashboard 조회 키 + 무효화 그룹 (§4.5).
//
// Dashboard 와 변경 성공 이벤트(Holdings 저장 / Market 갱신)가 같은 키를 참조하도록
// 한 곳에 모은다. 무효화는 이 prefix 로 "관련 읽기만" 지운다.

// 개별 조회 키 (endpoint + 요청 조건 유일 식별).
export const DASH_KEY_MARKET =
  "dashboard:market/topn/latest?n=10&basis=one_month&order=desc" +
  "&exclude_inverse=true&exclude_leveraged=true" +
  "&exclude_synthetic=true&exclude_futures=true";
export const DASH_KEY_HOLDINGS = "dashboard:holdings/enriched";
export const DASH_KEY_EVIDENCE = "dashboard:holdings/market-evidence";
export const DASH_KEY_NAV = "dashboard:nav-discount/latest";

// 무효화 그룹 (변경 성공 이벤트별 "관련 읽기").
// - Holdings 변경 → 보유·Evidence 읽기 무효화 (시장·NAV 는 무관).
// - Market 갱신 → 시장 + Evidence 무효화. Holdings Market Evidence 는 현재
//   Market Discovery 후보·시장 국면을 사용하므로(holdings.ts 주석), Market 갱신
//   후 기존 Evidence 캐시가 stale 이 된다 → 함께 무효화한다. 보유·NAV 는 무관.
export const HOLDINGS_INVALIDATION_KEYS = [
  DASH_KEY_HOLDINGS,
  DASH_KEY_EVIDENCE,
];
export const MARKET_INVALIDATION_KEYS = [DASH_KEY_MARKET, DASH_KEY_EVIDENCE];
