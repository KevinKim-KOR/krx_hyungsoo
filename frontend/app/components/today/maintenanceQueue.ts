// POC3-OPS-02B-2-KS10-TRIGGER-FILE-SPLIT (2026-09-13)
// `TodayInvestmentCheckView.tsx` 가 907줄로 KS-10 프론트 임계(>900)를 넘어
// 책임별로 분리했다. **JSX·문구·className·핸들러·호출 조건을 고치지 않았다** —
// 바뀐 것은 파일 배치와 import/export 줄뿐이다.

import type { QueryState } from "@/lib/api/queryCache";
import type {
  EnrichedHoldingsResult,
  HoldingsMarketEvidenceResponse,
  MarketTopNResponse,
  NavDiscountLatestResponse,
} from "@/lib/api";
import type { MenuKey } from "../LeftSidebar";

// ── §4.3 정비 큐 항목 (자료 상태) ────────────────────────────────────────────
// 판단 큐와 절대 섞이지 않도록 별도 타입/수집 함수로 분리.
// kind (§4.3): "light" = 대시보드에서 바로 "지금 다시 불러오기" 로 해소 가능(저장값
// 재조회). "heavy" = 전체 수집·재계산이 필요해 상세 화면에서 실행해야 함(Q8).
export type MaintenanceItem = {
  text: string; // 사용자 언어 (내부 용어 비노출)
  kind: "light" | "heavy";
  target: MenuKey; // heavy 일 때 이동할 상세 화면 (Q8: 항목별 직접)
  actionLabel: string;
  // ⓘ 근거: 무엇과 무엇을 비교/확인해 최신이 아닌지 (실제 값 기반 · 임시 숫자 없음).
  // 정비 큐 판정 근거의 정식 표준은 후속 설계에서 확정 (임시 문구).
  reason?: string;
};

export function collectMaintenance(
  holdings: QueryState<EnrichedHoldingsResult>,
  evidence: QueryState<HoldingsMarketEvidenceResponse>,
  nav: QueryState<NavDiscountLatestResponse>,
  market: QueryState<MarketTopNResponse>,
): MaintenanceItem[] {
  const list: MaintenanceItem[] = [];

  // light 는 "지금 다시 불러오기"(POST /holdings/market/refresh)로 실제 해소되는
  // 것만 — 이 API 는 보유 종목의 "현재가" 만 갱신한다. 현재가 결측 보유 종목이
  // 있으면 그 건수를 light 항목으로 노출 (갱신 후 실제로 사라짐 → 계약·동작 일치).
  if (holdings.phase === "success") {
    const missing = holdings.data.items.filter((h) => h.price_missing).length;
    if (missing > 0) {
      list.push({
        text: `보유 종목 현재가를 불러오지 못했습니다 (${missing}건)`,
        kind: "light",
        target: "holdings",
        actionLabel: "지금 다시 불러오기",
        reason:
          "보유 종목의 저장된 현재가(시세)를 불러오지 못한 상태입니다. '업데이트' 로 저장된 시세를 다시 불러옵니다.",
      });
    }
  }

  // VIX stale (시장 불안 지표가 오래됨) — 시장 응답의 risk reference 로 판정.
  if (market.phase === "success") {
    const risk = market.data.market_risk_reference;
    const vix = risk?.vix;
    const kodex = risk?.kodex200;
    if (
      vix?.availability === "available" &&
      kodex?.availability === "available" &&
      vix.as_of_date &&
      kodex.as_of_date &&
      vix.as_of_date < kodex.as_of_date
    ) {
      // 시장 불안 지표(VIX) 갱신은 전체 시장 자료 수집 필요 → heavy.
      list.push({
        text: `시장 불안 지표가 오래되었습니다 (기준일 ${vix.as_of_date})`,
        kind: "heavy",
        target: "market_discovery",
        actionLabel: "시장 자료 업데이트로",
        reason: `시장 불안 지표(VIX)의 기준일(${vix.as_of_date})이 시장 기준일(${kodex.as_of_date})보다 이전입니다. 두 기준일을 비교해 더 이전이면 오래된 것으로 봅니다.`,
      });
    }
    if (vix?.availability === "unavailable") {
      list.push({
        text: "시장 불안 지표 자료가 없습니다",
        kind: "heavy",
        target: "market_discovery",
        actionLabel: "시장 자료 업데이트로",
        reason: "시장 불안 지표(VIX) 자료가 아직 수집되지 않았습니다.",
      });
    }
  }

  // 보유 ETF 관련 자료 상태.
  if (evidence.phase === "success") {
    const s = evidence.data.summary;
    if (s.constituents_unavailable_count > 0) {
      // 구성종목 수집은 대량 작업 → heavy (상세 화면).
      list.push({
        text: `ETF가 담고 있는 종목 자료가 없습니다 (${s.constituents_unavailable_count}건)`,
        kind: "heavy",
        target: "etf_exposure",
        actionLabel: "구성종목 업데이트로",
        reason:
          "이 ETF가 담고 있는 종목·비중(구성종목) 자료가 아직 수집되지 않았습니다. 구성종목 화면에서 수집합니다.",
      });
    }
    if (s.evidence_unavailable_count > 0) {
      // 시장 비교 evidence 는 시장 자료 갱신이 필요 → 경량 갱신(현재가)으로 해소
      // 안 됨 → heavy (상세 화면). (2026-07-30 재분류: light→heavy)
      list.push({
        text: `내가 가진 ETF와 시장 비교 자료가 오래되었습니다 (${s.evidence_unavailable_count}건)`,
        kind: "heavy",
        target: "market_discovery",
        actionLabel: "시장 자료 업데이트로",
        reason:
          "보유 ETF가 현재 시장에서 어떤 위치인지(요즘 잘 오르는 ETF 목록에 드는지·KODEX200 대비 초과수익·단기 흐름) 비교한 자료가 최신 시장 기준으로 재계산되지 않았습니다.",
      });
    }
    if (s.nav_discount_unavailable_count > 0) {
      list.push({
        text: `ETF 기준가 비교 자료가 없습니다 (${s.nav_discount_unavailable_count}건)`,
        kind: "heavy",
        target: "etf_exposure",
        actionLabel: "구성종목 업데이트로",
        reason:
          "ETF의 순자산가치(NAV)와 시장가격을 비교한 괴리 자료가 없습니다. NAV보다 비싸게/싸게 거래되는지 확인하는 값입니다.",
      });
    }
  } else if (evidence.phase === "error") {
    list.push({
      text: "보유 ETF 비교 자료를 불러오지 못했습니다",
      kind: "heavy",
      target: "market_discovery",
      actionLabel: "시장 자료 업데이트로",
      reason: "보유 ETF의 시장 비교 자료를 조회하지 못했습니다.",
    });
  }

  // NAV 미연동/실패 — 기준가 자료는 구성종목/시장 갱신 필요 → heavy (재분류).
  if (nav.phase === "success") {
    const s = nav.data.summary;
    // B-1: 필수 집계 필드가 숫자가 아니면(손상 응답) 0 으로 위장하지 않고 "확인 불가".
    const uc = s?.unavailable_count;
    const fc = s?.failed_count;
    if (typeof uc !== "number" || typeof fc !== "number") {
      list.push({
        text: "ETF 기준가 자료 상태를 확인할 수 없습니다",
        kind: "heavy",
        target: "etf_exposure",
        actionLabel: "구성종목 업데이트로",
        reason:
          "ETF 기준가(NAV) 자료의 상태 집계가 응답에 없어 정상 여부를 확인할 수 없습니다.",
      });
    } else if (uc + fc > 0) {
      list.push({
        text: `ETF 기준가 자료가 일부 없습니다 (${uc + fc}건)`,
        kind: "heavy",
        target: "etf_exposure",
        actionLabel: "구성종목 업데이트로",
        reason:
          "일부 ETF의 순자산가치(NAV)·시장가격 괴리 자료가 없습니다. NAV 대비 현재 가격 수준을 확인하는 값입니다.",
      });
    }
  } else if (nav.phase === "error") {
    list.push({
      text: "ETF 기준가 자료를 불러오지 못했습니다",
      kind: "heavy",
      target: "etf_exposure",
      actionLabel: "구성종목 업데이트로",
      reason: "ETF 순자산가치(NAV) 자료를 조회하지 못했습니다.",
    });
  }

  return list;
}
