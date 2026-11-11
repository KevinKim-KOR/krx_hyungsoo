"use client";

// POC6-28 — 「보유」 목록 · 상세가 함께 쓰는 집계 · 판정(PLAN §2-6 · 판정 §4 · Q6).
// 같은 ticker 다계좌는 한 행(부분 집계 표기는 기존 계약 그대로).

import type {
  EnrichedHoldingsResult,
  HoldingsMarketEvidenceItem,
} from "@/lib/api";
import type { CompareSummaryOk, HoldingLink } from "@/lib/api/etfCompare";

export type AggHolding = {
  ticker: string;
  name: string | null;
  evalAmount: number | null;
  evalOk: number;
  pnlAmount: number | null;
  pnlOk: number;
  pnlRate: number | null;
  currentPrice: number | null;
  weight: number | null;
  weightOk: number;
  count: number;
};

export function aggregateHoldings(items: EnrichedHoldingsResult["items"]): AggHolding[] {
  const map = new Map<string, AggHolding>();
  for (const h of items) {
    let a = map.get(h.ticker);
    if (!a) {
      a = {
        ticker: h.ticker,
        name: h.name,
        evalAmount: null,
        evalOk: 0,
        pnlAmount: null,
        pnlOk: 0,
        pnlRate: h.pnl_rate_pct,
        currentPrice: h.current_price,
        weight: null,
        weightOk: 0,
        count: 0,
      };
      map.set(h.ticker, a);
    }
    a.count += 1;
    if (h.eval_amount != null) {
      a.evalAmount = (a.evalAmount ?? 0) + h.eval_amount;
      a.evalOk += 1;
    }
    if (h.pnl_amount != null) {
      a.pnlAmount = (a.pnlAmount ?? 0) + h.pnl_amount;
      a.pnlOk += 1;
    }
    if (h.market_weight_pct != null) {
      a.weight = (a.weight ?? 0) + h.market_weight_pct;
      a.weightOk += 1;
    }
    if (a.currentPrice == null) a.currentPrice = h.current_price;
  }
  return Array.from(map.values());
}

// 부분 평가 표기 — N개 계좌 중 M개만 계산됨을 값 옆에 붙인다(기존 계약).
export function PartialMark({ ok, count }: { ok: number; count: number }) {
  if (ok <= 0 || ok >= count) return null;
  return (
    <span className="wb-hpartial">
      ({ok}/{count})
    </span>
  );
}

export function linkOf(s: CompareSummaryOk | null, ticker: string): HoldingLink | undefined {
  return s?.holdings.items.find((h) => h.ticker === ticker);
}

// 이 연결에 가격 흐름 칸이 있는가 — 칸 없음(가격 흐름을 싣지 않은 응답 · 예: 백엔드가 아직 다시 시작 전)은
// '저장 가격 없음'(null)과 다르다. 칸이 없으면 가격 흐름을 모르는 것이라 하락 · 부족을 '아님'으로 세지 않는다
// (설계자 RESULT 판정 §3 · 첨부 화면 0 · 26 재현).
export function hasFlowField(link: HoldingLink | undefined): link is HoldingLink {
  return !!link && link.price_flow !== undefined;
}

// 보유 근거 읽기 상태 — 실패 · 이전 조회값 안내가 실제로 화면에 쓰인 출처와 맞게 한곳에서 정한다(검증자 r3 F5).
export type EvPhase = "ok" | "stale" | "error" | "loading";

// 요약의 보유 연결을 쓸 수 있는가 — 요약이 있고 그 응답이 보유 파일을 읽었을 때만 'ok'(독립 검토 · F5 옆칸).
// 'unread' = 요약은 있으나 보유를 읽지 못함(`holdings.status` ≠ ok · 연결 없음) — '이 종목 없음'과 다르다.
export type SumLinks = "ok" | "unread" | "none";

export function sumLinksOf(s: CompareSummaryOk | null): SumLinks {
  if (!s) return "none";
  return s.holdings.status === "ok" ? "ok" : "unread";
}

// 자료가 없을 때 '왜 없는지'를 출처별로 — 요약 없음 / 요약이 보유를 못 읽음 / 요약에 이 종목 없음.
export function sumMissingText(sl: SumLinks): string {
  if (sl === "ok") return "비교 요약에 이 종목 없음";
  if (sl === "unread") return "비교 요약이 보유를 읽지 못함";
  return "비교 요약 없음";
}

export function evMissingText(ev: EvPhase): string {
  if (ev === "error") return "보유 근거 조회 실패";
  if (ev === "loading") return "보유 근거 확인 중";
  return "보유 근거에 이 종목 없음";
}

// 화면 위 보유 근거 안내 — 요약 price_flow 로 이미 보이는 가격 변화 · 하락 판정을 '못 보인다'고 하지 않는다.
// missing = 요약 연결은 있는데 그 응답에 가격 흐름이 없는 보유 수(종목 자체가 없거나 칸이 없음 · 이 종목들만 보유 근거에 기댄다).
// rowsShown = 보유 행이 그려졌는가 — 행이 없으면 무엇이 '보인다'고 말하지 않는다(독립 검토).
export function evidenceNotice(ev: EvPhase, sl: SumLinks, missing: number, rowsShown: boolean): string | null {
  if (ev !== "error" && ev !== "stale") return null;
  if (!rowsShown) return ev === "error" ? "보유 근거 조회 실패" : null;
  const flowPart =
    sl !== "ok"
      ? `가격 변화 · 하락 판정(${sumMissingText(sl)})`
      : missing > 0
        ? `비교 요약에 가격 흐름이 없는 보유 ${missing}종목의 가격 변화 · 하락 판정`
      : null;
  if (ev === "error") {
    return flowPart
      ? `보유 근거 조회 실패 — 월간 수익률(보유 근거)과 ${flowPart}을 보이지 못합니다.`
      : "보유 근거 조회 실패 — 월간 수익률(보유 근거)을 보이지 못합니다. 가격 변화 · 하락 판정은 비교 요약 값으로 보입니다.";
  }
  return flowPart
    ? `보유 근거 다시 조회 실패 — 월간 수익률(보유 근거)과 ${flowPart}은 이전 조회값입니다(최신 아님).`
    : "보유 근거 다시 조회 실패 — 월간 수익률(보유 근거)은 이전 조회값입니다(최신 아님). 가격 변화 · 하락 판정은 비교 요약 값입니다.";
}

// 하락 판정 — 비교 요약이 있으면 그 응답의 price_flow(값 · 저장 상태가 같은 읽기), 없을 때만 보유 근거(검증자 r2 F4).
export function declineOf(
  link: HoldingLink | undefined,
  ev: HoldingsMarketEvidenceItem | undefined,
): { label: string | null; state: string | null; fromSummary: boolean } {
  if (hasFlowField(link)) {
    const b = link.price_flow?.decline_band;
    return { label: b?.label ?? null, state: b?.state ?? null, fromSummary: true };
  }
  return { label: ev?.decline_band?.label ?? null, state: ev?.decline_band?.state ?? null, fromSummary: false };
}

// 하락 판정을 실제로 했는가 — 고른 출처(요약 가격 흐름 칸이 있으면 그것 · 없으면 보유 근거)의 judgeable 로 정한다.
// 객체가 있어도 judgeable=false(이력 부족 · 기준일 다름 · 값 오류)나 price_flow=null(저장 가격 없음)은 '판정 못 함'이다.
// 판정 못 한 보유를 '하락 아님'으로 세지 않기 위한 기준(검증자 F6 · 설계자 RESULT 판정 §3).
export function declineJudged(link: HoldingLink | undefined, ev: HoldingsMarketEvidenceItem | undefined): boolean {
  if (hasFlowField(link)) return link.price_flow?.decline_band?.judgeable === true;
  return ev?.decline_band?.judgeable === true;
}

export function isDecline(link: HoldingLink | undefined, ev: HoldingsMarketEvidenceItem | undefined): boolean {
  return declineJudged(link, ev) && !!declineOf(link, ev).state;
}

export function isWeakContact(link: HoldingLink | undefined): boolean {
  return !!link && (link.side === "bottom" || link.exposure.status === "ok");
}

// 비교 자료 부족 — 개별 주식 제외(해당 없음은 조치 대상 아님).
// linksOk = 요약의 보유 연결을 읽었는가. 읽었는데 이 종목이 없으면 '비교 목록 밖'이라 부족으로 센다(검증자 r3 F5 옆칸).
// 연결이 없으면(요약 없음 · 보유 못 읽음) 확인된 가격 비교 날짜 문제만 표시한다 — 개수는 화면이 '—'로 둔다.
export function lacksCompareData(
  link: HoldingLink | undefined,
  ev: HoldingsMarketEvidenceItem | undefined,
  linksOk: boolean,
): boolean {
  if (!link) {
    if (linksOk) return true;
    // 요약을 못 받았으면 개별 주식 여부를 알 수 없다 — 보유 근거의 가격 비교 날짜 문제만 본다(독립 검토 LOW).
    const pd0 = ev?.price_dates;
    return !!pd0 && pd0.comparison !== "ok";
  }
  if (link.is_stock) return false;
  if (link.exposure.status === "no_constituents") return true;
  if (link.out_reason === "no_price" || link.out_reason === "period_differs") return true;
  if (link.price_flow === undefined) {
    // 요약에 가격 흐름 칸이 없으면 보유 근거의 비교 날짜로 본다 · 그것도 없으면 가격 비교 근거가 없는 것.
    const pd1 = ev?.price_dates;
    return !pd1 || pd1.comparison !== "ok";
  }
  return !link.price_flow || link.price_flow.comparison !== "ok";
}
