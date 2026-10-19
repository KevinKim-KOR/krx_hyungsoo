// POC5-26 — 「요즘 잘 오르는 ETF」 기본 조회 기준(설계 §3 · PLAN §2 · 판정 §2).
// - 이 브라우저 localStorage 의 전용 값 하나(키 MARKET_BASIS_PREF_KEY · 값 = API 조회 기준 값 그대로).
//   정렬 방향 · 필터 · 보기 방식은 저장하지 않는다.
// - 읽기: 없음 · 허용 밖 값 · 읽기 실패는 기존 기본(1개월)으로 시작한다. 읽으면서 저장값을 고치거나 지우지 않는다.
// - 쓰기: [이 기준을 기본으로]를 눌렀을 때만. setItem 뒤 다시 읽어 같은 값일 때만 성공(예외 · 다른 값 = 실패).
import { DEFAULT_MARKET_BASIS, type MarketBasis } from "@/lib/api";

export const MARKET_BASIS_PREF_KEY = "krx.marketDiscovery.defaultBasis.v1";
export const MARKET_BASIS_VALUES: readonly MarketBasis[] = ["daily", "one_month", "three_month"];

export type MarketBasisPrefStatus = "saved" | "none" | "invalid" | "read_failed";

export interface MarketBasisPref {
  basis: MarketBasis;
  status: MarketBasisPrefStatus;
}

export function readMarketBasisPref(): MarketBasisPref {
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(MARKET_BASIS_PREF_KEY);
  } catch {
    return { basis: DEFAULT_MARKET_BASIS, status: "read_failed" };
  }
  if (raw === null) return { basis: DEFAULT_MARKET_BASIS, status: "none" };
  const hit = MARKET_BASIS_VALUES.find((v) => v === raw);
  return hit ? { basis: hit, status: "saved" } : { basis: DEFAULT_MARKET_BASIS, status: "invalid" };
}

export function writeMarketBasisPref(basis: MarketBasis): boolean {
  try {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, basis);
    return window.localStorage.getItem(MARKET_BASIS_PREF_KEY) === basis;
  } catch {
    return false;
  }
}
