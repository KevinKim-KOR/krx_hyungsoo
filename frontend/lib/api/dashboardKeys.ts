// POC3-01/02 — 조회 키 + 무효화 그룹 (§4.5 · POC3-02 §9).
//
// Dashboard·Workbench 와 변경 성공 이벤트(Holdings 저장 / Market 갱신)가 같은 키를
// 참조하도록 한 곳에 모은다. 무효화는 이 prefix 로 "관련 읽기만" 지운다.

// ── Dashboard 조회 키 (endpoint + 요청 조건 유일 식별) ──────────────────────
export const DASH_KEY_MARKET =
  "dashboard:market/topn/latest?n=10&basis=one_month&order=desc" +
  "&exclude_inverse=true&exclude_leveraged=true" +
  "&exclude_synthetic=true&exclude_futures=true";
export const DASH_KEY_HOLDINGS = "dashboard:holdings/enriched";
export const DASH_KEY_EVIDENCE = "dashboard:holdings/market-evidence";
export const DASH_KEY_NAV = "dashboard:nav-discount/latest";

// ── Workbench 조회 키 ──────────────────────────────────────────────────────
// §9: "동일 endpoint·동일 요청 조건에만 같은 cache key". Holdings/Evidence/NAV 는
// Dashboard 와 요청 조건이 완전히 같으므로 **같은 키를 공유**한다 (화면 왕복 시
// 재조회 방지). Market topn 만 요청 조건(n=30 vs n=10)이 달라 별도 키 — 이 분리가
// AC-28("Workbench cache 를 Dashboard 후보 공급 경로로 쓰지 않음")을 충족한다.
export const WB_KEY_CAND =
  "workbench:market/topn/latest?n=30&basis=one_month&order=desc" +
  "&exclude_inverse=true&exclude_leveraged=true" +
  "&exclude_synthetic=true&exclude_futures=true";
export const WB_KEY_HOLD = DASH_KEY_HOLDINGS;
export const WB_KEY_EVID = DASH_KEY_EVIDENCE;
export const WB_KEY_NAV = DASH_KEY_NAV;

// 무효화 그룹 (변경 성공 이벤트별 "관련 읽기").
// - Holdings 변경 → 보유·Evidence 무효화 (공유 키라 Dashboard·Workbench 동시).
// - Market 갱신 → 시장(Dashboard·Workbench 각 키) + Evidence(공유) 무효화.
//   Evidence 는 시장 후보·국면 사용 → Market 갱신 시 함께. 보유·NAV 는 무관.
export const HOLDINGS_INVALIDATION_KEYS = [
  DASH_KEY_HOLDINGS,
  DASH_KEY_EVIDENCE,
];
export const MARKET_INVALIDATION_KEYS = [
  DASH_KEY_MARKET,
  DASH_KEY_EVIDENCE,
  WB_KEY_CAND,
];
