// POC6-01 — 시장 흐름 응답 공유 조회(같은 키 · 화면 왕복 · 여러 사용처에서 한 번만 조회).
import { MARKET_FLOW_KEY } from "@/lib/api/dashboardKeys";
import { fetchMarketFlowContext, type MarketFlowContext } from "@/lib/api/marketFlow";
import { useSharedQuery } from "@/lib/api/queryCache";

export function useMarketFlowContext() {
  return useSharedQuery<MarketFlowContext>(MARKET_FLOW_KEY, fetchMarketFlowContext);
}
