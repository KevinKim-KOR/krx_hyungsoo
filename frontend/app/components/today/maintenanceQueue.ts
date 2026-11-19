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
import type { HoldingsConstituentsStatus } from "@/lib/api/constituentsStatus";
import { md } from "@/lib/etfCompare";
import { kospiStatusText, kospiStatusView } from "@/lib/kospiStatus";
import { kstMdHm } from "@/lib/marketNowText";
import { vixFreshnessNotice } from "@/lib/vixFreshness";
import type { MenuKey } from "../LeftSidebar";

// ── §4.3 정비 큐 항목 (자료 상태) ────────────────────────────────────────────
// 판단 큐와 절대 섞이지 않도록 별도 타입/수집 함수로 분리.
// kind (§4.3): "light" = 대시보드에서 바로 "지금 다시 불러오기" 로 해소 가능(저장값
// 재조회). "heavy" = 전체 수집·재계산이 필요해 상세 화면에서 실행해야 함(Q8).
// POC6-16 판정 §3-1 — 「지금 할 일」 안내용 분류(기존 항목 · 문구 · 버튼 · 이동은 그대로).
//   market_refresh = 시장 자료 갱신으로 해소(POC6-29: 예전 시장 화면 이동 대신 이 화면 [최신 자료 갱신]을
//                    바로 실행 · target = today_check 이면 이동 대신 갱신)
//   holdings_price = 이 화면 [업데이트](POST /holdings/market/refresh)로 다시 받는 보유 현재가
//   read_failed    = 조회 실패 · 응답 손상으로 자료 상태 자체를 모름(미갱신으로 단정하지 않음)
//   market_unknown = 시장 목록 응답이 정상이 아니거나 시장 배경이 없어 KOSPI 상태를 모름(다시 읽기 대상 아님 · 새로 고침)
//   other          = 해결 동선이 이 화면에서 확인되지 않은 정비 항목(목록에서 기존 버튼으로)
export type MaintenanceTask =
  | "market_refresh"
  | "holdings_price"
  | "read_failed"
  | "market_unknown"
  | "other";

export type MaintenanceItem = {
  task: MaintenanceTask;
  text: string; // 사용자 언어 (내부 용어 비노출)
  kind: "light" | "heavy";
  target: MenuKey; // heavy 일 때 이동할 상세 화면 (Q8: 항목별 직접)
  actionLabel: string;
  // ⓘ 근거: 무엇과 무엇을 비교/확인해 최신이 아닌지 (실제 값 기반 · 임시 숫자 없음).
  // 정비 큐 판정 근거의 정식 표준은 후속 설계에서 확정 (임시 문구).
  reason?: string;
  // POC6-27 — 위 「자료 최신화 필요」의 코스피 줄과 같은 항목(「자료 확인」 목록에서는 겹치지 않게 뺀다).
  // POC6-31 — constituents = 보유 ETF 구성종목(같은 [최신 자료 갱신]으로 해소 · 「지금 할 일」 문장을 나눠 쓴다).
  source?: "kospi" | "constituents";
};

// POC6-32 V2(판정 Q2 (b) · PLAN S5) — NAV 항목 4개의 이동 = 「진단·상태 › 데이터 상태」(읽기 전용 · 전체 ETF NAV · 괴리율).
// 버튼 글자는 POC6-32 때 「확인 근거」 상세에 있던 같은 곳 이동 버튼 낱말이다. POC6-33(PLAN E11)에서 그 상세
// 버튼은 뺐고, 이 이동(「오늘의 투자 점검」)은 그대로 둔다.
// NAV 를 다시 받는 일은 「오늘의 투자 점검」 [최신 자료 갱신]의 시장 단계다(「데이터 상태」는 보기만).
export const NAV_TARGET: MenuKey = "data_status";
export const NAV_ACTION_LABEL = "전체 ETF NAV·괴리율 보기 →";

export function collectMaintenance(
  holdings: QueryState<EnrichedHoldingsResult>,
  evidence: QueryState<HoldingsMarketEvidenceResponse>,
  nav: QueryState<NavDiscountLatestResponse>,
  market: QueryState<MarketTopNResponse>,
  // POC6-31(판정 Q16) — 보유 ETF 구성 상태. 없으면(예전 호출) 구성종목 항목을 만들지 않는다.
  constituents?: QueryState<HoldingsConstituentsStatus>,
): MaintenanceItem[] {
  const list: MaintenanceItem[] = [];

  // light 는 "지금 다시 불러오기"(POST /holdings/market/refresh)로 실제 해소되는
  // 것만 — 이 API 는 보유 종목의 "현재가" 만 갱신한다. 현재가 결측 보유 종목이
  // 있으면 그 건수를 light 항목으로 노출 (갱신 후 실제로 사라짐 → 계약·동작 일치).
  if (holdings.phase === "success") {
    const missing = holdings.data.items.filter((h) => h.price_missing).length;
    if (missing > 0) {
      list.push({
        task: "holdings_price",
        text: `보유 종목 현재가를 불러오지 못했습니다 (${missing}건)`,
        kind: "light",
        target: "holdings",
        actionLabel: "지금 다시 불러오기",
        reason:
          "보유 종목의 저장된 현재가(시세)를 불러오지 못한 상태입니다. '업데이트' 로 저장된 시세를 다시 불러옵니다.",
      });
    }
  }

  // VIX 최신성 — POC5-12 PC 서버의 미국 장 마감 기준 판정(vix.freshness)만 읽는다.
  if (market.phase === "success") {
    const risk = market.data.market_risk_reference;
    const vix = risk?.vix;
    const vixNotice = vixFreshnessNotice(vix);
    if (vixNotice) {
      // 시장 불안 지표(VIX) 갱신은 전체 시장 자료 수집 필요 → heavy.
      list.push({
        task: "market_refresh",
        text: vixNotice.text,
        kind: "heavy",
        target: "today_check",
        actionLabel: "최신 자료 갱신",
        reason: vixNotice.reason,
      });
    }
    if (vix?.availability === "unavailable") {
      list.push({
        task: "market_refresh",
        text: "시장 불안 지표 자료가 없습니다",
        kind: "heavy",
        target: "today_check",
        actionLabel: "최신 자료 갱신",
        reason: "시장 불안 지표(VIX) 자료가 아직 수집되지 않았습니다.",
      });
    }
    // POC3-02D-OPS-03 설계자 RESULT STEP 4 · PLAN STEP 7-4 — KOSPI 가 정상 · 휴장일이 아니면
    // VIX 지연과 같은 모양의 항목 하나(PC 화면만 · Telegram 없음). 판정 · 문구는 KOSPI
    // 카드와 같은 생성기(lib/kospiStatus) — 사유 문장(끝 마침표 뺌) + 기준 줄, ⓘ 는 상태 한 줄.
    const kospi = kospiStatusView(market.data.market_context?.kospi);
    if (!kospi.loading && kospi.state !== "ok" && kospi.state !== "holiday" && kospi.reason) {
      const head = kospi.reason.replace(/\.$/, "");
      list.push({
        // 시장 목록 응답이 정상이 아니거나 시장 배경이 없으면 '갱신 필요'가 아니라 '상태 모름'(검토 지적 8b)
        task:
          market.data.status !== "ok" || !market.data.market_context ? "market_unknown" : "market_refresh",
        text: kospi.basisLine ? `${head} (${kospi.basisLine})` : head,
        kind: "heavy",
        target: "today_check",
        actionLabel: "최신 자료 갱신",
        reason: kospiStatusText(market.data.market_context?.kospi),
        source: "kospi",
      });
    }
  }

  // POC6-31(판정 Q16) — 보유 ETF 구성종목: 보유 ETF 를 종목 단위로 센 '다시 확인 필요' 수
  // (직접 보유 주식 · 계좌 행 · 시장 후보 자료 상태 뺌) · 해소 = 이 화면 [최신 자료 갱신](보유 구성종목 단계).
  if (constituents?.phase === "success" && constituents.data.status === "ok" && constituents.data.needs_check > 0) {
    const c = constituents.data;
    const by = (k: string) => c.items.filter((i) => i.result === k).length;
    const parts = [
      ["not_checked", "아직 확인 안 함"],
      ["target_wait", "목표일 자료 대기"],
      ["failed", "받기 실패"],
      ["timeout", "시간 초과로 조회 안 함"],
      ["locked", "저장 잠김"],
      ["no_source_date", "원천 기준일 미확인"],
    ]
      .filter(([k]) => by(k) > 0)
      .map(([k, label]) => `${label} ${by(k)}`);
    // PLAN C13 — 마지막 시도 시각(다시 확인이 필요한 보유 ETF 의 마지막 확인 기록 중 가장 늦은 것 · 없으면 '없음')
    const lastTried = c.items
      .filter((i) => i.needs_check && i.last_checked_at)
      .map((i) => i.last_checked_at as string)
      .sort()
      .pop();
    list.push({
      task: "market_refresh",
      text: `구성종목 자료가 없거나 목표일(${md(c.target_date)})에 못 미친 보유 ETF ${c.needs_check}개 — [최신 자료 갱신]에서 받습니다 · ${
        lastTried ? `마지막 시도 ${kstMdHm(lastTried)}` : "마지막 시도 없음"
      }`,
      kind: "heavy",
      target: "today_check",
      actionLabel: "최신 자료 갱신",
      reason: `보유 ETF ${c.total}개 중 ${parts.join(" · ")} · ETF별 사유는 위 '보유 구성종목' 줄의 [ETF별 보기]에서 봅니다.`,
      source: "constituents",
    });
  }

  // 보유 ETF 관련 자료 상태.
  if (evidence.phase === "success") {
    const s = evidence.data.summary;
    if (s.evidence_unavailable_count > 0) {
      // 시장 비교 evidence 는 시장 자료 갱신이 필요 → 경량 갱신(현재가)으로 해소
      // 안 됨 → heavy (상세 화면). (2026-07-30 재분류: light→heavy)
      list.push({
        task: "market_refresh",
        text: `내가 가진 ETF와 시장 비교 자료가 오래되었습니다 (${s.evidence_unavailable_count}건)`,
        kind: "heavy",
        target: "today_check",
        actionLabel: "최신 자료 갱신",
        reason:
          "보유 ETF가 현재 시장에서 어떤 위치인지(1개월 상위 10에 드는지·KODEX200 대비 초과수익·단기 흐름) 비교한 자료가 최신 시장 기준으로 재계산되지 않았습니다.",
      });
    }
    if (s.nav_discount_unavailable_count > 0) {
      list.push({
        task: "other",
        text: `ETF 기준가 비교 자료가 없습니다 (${s.nav_discount_unavailable_count}건)`,
        kind: "heavy",
        target: NAV_TARGET,
        actionLabel: NAV_ACTION_LABEL,
        reason:
          "ETF의 순자산가치(NAV)와 시장가격을 비교한 괴리 자료가 없습니다. NAV보다 비싸게/싸게 거래되는지 확인하는 값입니다.",
      });
    }
  } else if (evidence.phase === "error") {
    list.push({
      task: "read_failed",
      text: "보유 ETF 비교 자료를 불러오지 못했습니다",
      kind: "heavy",
      target: "today_check",
      actionLabel: "최신 자료 갱신",
      reason: "보유 ETF의 시장 비교 자료를 조회하지 못했습니다.",
    });
  }

  // NAV 미연동/실패 → heavy (재분류) · 버튼 = 「데이터 상태」(NAV_TARGET · 판정 Q2 (b)).
  if (nav.phase === "success") {
    const s = nav.data.summary;
    // B-1: 필수 집계 필드가 숫자가 아니면(손상 응답) 0 으로 위장하지 않고 "확인 불가".
    const uc = s?.unavailable_count;
    const fc = s?.failed_count;
    if (typeof uc !== "number" || typeof fc !== "number") {
      list.push({
        task: "read_failed",
        text: "ETF 기준가 자료 상태를 확인할 수 없습니다",
        kind: "heavy",
        target: NAV_TARGET,
        actionLabel: NAV_ACTION_LABEL,
        reason:
          "ETF 기준가(NAV) 자료의 상태 집계가 응답에 없어 정상 여부를 확인할 수 없습니다.",
      });
    } else if (uc + fc > 0) {
      list.push({
        task: "other",
        text: `ETF 기준가 자료가 일부 없습니다 (${uc + fc}건)`,
        kind: "heavy",
        target: NAV_TARGET,
        actionLabel: NAV_ACTION_LABEL,
        reason:
          "일부 ETF의 순자산가치(NAV)·시장가격 괴리 자료가 없습니다. NAV 대비 현재 가격 수준을 확인하는 값입니다.",
      });
    }
  } else if (nav.phase === "error") {
    list.push({
      task: "read_failed",
      text: "ETF 기준가 자료를 불러오지 못했습니다",
      kind: "heavy",
      target: NAV_TARGET,
      actionLabel: NAV_ACTION_LABEL,
      reason: "ETF 순자산가치(NAV) 자료를 조회하지 못했습니다.",
    });
  }

  return list;
}
