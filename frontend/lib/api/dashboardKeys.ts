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
// POC6-01 — 시장 흐름(수급 · 환율 · 유가). 「오늘의 투자 점검」 · 「요즘 잘 오르는 ETF」 · 복사문이 같은 키.
export const MARKET_FLOW_KEY = "market:flow-context";
// POC6-16 — 「오늘의 투자 점검」 요약의 연구 줄(GET /ml/forward-comparison · 기준일 지정 없음 = 최근 · 읽기 전용).
//   「예측과 결과 비교」 카드는 기준일을 바꿔 가며 자기 조회를 쓰므로 이 키를 쓰지 않는다.
export const DASH_KEY_FORWARD = "dashboard:ml/forward-comparison";

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
// POC6-28 — 「ETF 비교하기」 요약(조건마다 키 · 앞부분 공통). 시장 갱신(가격 · 국면)과 보유 변경(보유 연결)이
// 모두 이 응답을 바꾸므로 두 무효화 그룹에 넣는다.
export const ETF_COMPARE_KEY_PREFIX = "etf-compare:summary?";
// POC6-28(독립 검토 MEDIUM) — 종목 가격 차트(「ETF 비교하기」 · 「확인 근거」 공용 PriceChart) 조회 키 앞부분.
// 시장 갱신이 저장 가격을 다시 받으므로 함께 지운다(요약의 가격 상태와 차트 마지막 날이 어긋나지 않게).
export const PRICE_SERIES_KEY_PREFIX = "workbench:price-series?";
export const HOLDINGS_INVALIDATION_KEYS = [
  DASH_KEY_HOLDINGS,
  DASH_KEY_EVIDENCE,
  ETF_COMPARE_KEY_PREFIX,
];
// POC6-27 — 「오늘의 투자 점검」은 「요즘 잘 오르는 ETF」와 같은 조건(기간 · 방향 · 제외)으로 읽으므로
// 조건마다 키가 다르다(앞부분은 DASH_KEY_MARKET 과 같음). 무효화는 이 앞부분으로 조건 키를 모두 지운다.
export const DASH_MARKET_KEY_PREFIX = "dashboard:market/topn/latest?";
export const MARKET_INVALIDATION_KEYS = [
  DASH_KEY_MARKET,
  DASH_MARKET_KEY_PREFIX,
  DASH_KEY_EVIDENCE,
  WB_KEY_CAND,
  MARKET_FLOW_KEY, // POC6-01 — 시장 갱신이 수급 · 환율 · 유가를 새로 받는다
  ETF_COMPARE_KEY_PREFIX, // POC6-28
  PRICE_SERIES_KEY_PREFIX, // POC6-28
];
