// POC6-01 — AI 복사문(「요즘 잘 오르는 ETF」 · 「ETF 구성종목」 → AI 세션)에 붙일 시장 흐름 구간.
// 서버 글(`ai_text[기간]`)을 그대로 쓴다 — 화면 · 판단 근거 미리보기와 같은 숫자 · 기간 · 문구.
// 자료를 아직 못 받았거나 실패하면 그 사실을 적는다(빈 구간 · 다른 숫자로 채우지 않음).
import type { FlowPeriodCode, MarketFlowContext } from "./api/marketFlow";

export const MARKET_FLOW_TEXT_UNAVAILABLE =
  "[시장 흐름 — 수급 · 환율 · 유가]\n- 시장 흐름 자료를 불러오지 못해 이 글에 넣지 못했습니다";

export function marketFlowCopySection(
  data: MarketFlowContext | null | undefined,
  period: FlowPeriodCode,
): string {
  const text = data?.ai_text?.[period];
  return text && text.length > 0 ? text : MARKET_FLOW_TEXT_UNAVAILABLE;
}
