// ETF Exposure Context Bridge — Market Discovery → ETF Exposure draft 전달 utility.
//
// 정책 (지시문 §5):
// - 서버 draft 저장소를 만들지 않는다.
// - sessionStorage 사용 (브라우저 새로고침으로 사라져도 본 STEP 에서 허용).
// - 영구 기록은 POST /decision/sessions (snapshot 영속화) 만.
//
// 본 draft 는 "후보 ETF 목록 + market_context + filters" 까지만 담는다 —
// 구성종목 / 중복률 분석 결과는 ETF Exposure 화면 안에서 fetch 한다.

import type {
  DecisionCandidateSnapshot,
  DecisionFilters,
  MarketCandidate,
  MarketContext,
} from "./api";

// 2026-05-27 FIX (검증자 A-1 NOTE 반영) — schema v2 로 승격.
// ETF Exposure → AI Sessions 흐름에서 시장 판정 + 후보별 초과수익이 손실되던
// 문제를 차단하기 위해 marketContextFull + marketCandidates 필드 추가. AI 문구
// 생성과 AI Sessions draft 양쪽에서 그대로 재사용 가능한 형태로 보존.
const STORAGE_KEY = "krx_alertor.etf_exposure.draft.v2";

export interface ETFExposureDraft {
  asof: string;
  filters: DecisionFilters;
  // Market Discovery 후보 (AI Sessions draft 와 동일 형태). tags 포함. 저장용
  // lightweight 표현. excess_return 은 marketCandidates 에서 보존.
  candidate_snapshot: DecisionCandidateSnapshot[];
  market_context_snapshot?: Record<string, unknown> | null;
  // 2026-05-27 FIX — 시장 판정 본체 + excess_return 포함 후보 본체.
  // AI 문구 / AI Sessions draft 생성 시 그대로 사용. 직렬화 후 복원 시 type
  // shape 만 안전하면 OK (런타임 typeof 검증 없음 — 호출자 책임).
  market_context_full?: MarketContext | null;
  market_candidates: MarketCandidate[];
  // 본 draft 가 생성된 시각 (디버깅 + "언제 넘긴 후보냐" 안내).
  draft_created_at: string;
}

function safeStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function saveETFExposureDraft(draft: ETFExposureDraft): void {
  const s = safeStorage();
  if (!s) return;
  s.setItem(STORAGE_KEY, JSON.stringify(draft));
}

export function loadETFExposureDraft(): ETFExposureDraft | null {
  const s = safeStorage();
  if (!s) return null;
  const raw = s.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as ETFExposureDraft;
    if (
      !parsed ||
      typeof parsed.asof !== "string" ||
      !Array.isArray(parsed.candidate_snapshot) ||
      !parsed.filters
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function clearETFExposureDraft(): void {
  const s = safeStorage();
  if (!s) return;
  s.removeItem(STORAGE_KEY);
}

// Market Discovery 의 MarketCandidate[] + MarketContext → ETFExposureDraft 변환.
// AI Sessions draft 와 동일 candidate 변환 규칙 사용 (tags 포함).
export function buildETFExposureDraftFromMarketDiscovery({
  asof,
  filters,
  candidates,
  marketContext,
  marketContextSnapshot,
}: {
  asof: string;
  filters: DecisionFilters;
  candidates: MarketCandidate[];
  marketContext: MarketContext | null;
  marketContextSnapshot: Record<string, unknown> | null;
}): ETFExposureDraft {
  return {
    asof,
    filters,
    candidate_snapshot: candidates.map((c) => ({
      rank: c.rank ?? null,
      ticker: c.ticker ?? null,
      name: c.name ?? null,
      daily_return_pct: c.returns?.daily?.return_pct ?? null,
      one_month_return_pct: c.returns?.one_month?.return_pct ?? null,
      three_month_return_pct: c.returns?.three_month?.return_pct ?? null,
      tags: (c.tags ?? []) as string[],
    })),
    market_context_snapshot: marketContextSnapshot,
    market_context_full: marketContext,
    market_candidates: candidates,
    draft_created_at: new Date().toISOString(),
  };
}

// MarketContext (정상 응답) → AI Sessions / ETF Exposure draft 용 최소 요약.
// 직전 STEP 의 TransferToAISessionsCard._toMarketContextSnapshot 와 동일 형태
// (재사용 — frontend 공통 변환).
export function toMarketContextSnapshot(
  ctx: MarketContext | null,
  candidates: MarketCandidate[],
): Record<string, unknown> | null {
  if (!ctx || ctx.status === "unavailable") return null;
  return {
    regime_label: ctx.regime_label,
    regime_code: ctx.regime_code,
    primary_benchmark: ctx.primary_benchmark,
    kodex200: {
      status: ctx.kodex200.status,
      return_20d_pct: ctx.kodex200.return_20d_pct ?? null,
      return_60d_pct: ctx.kodex200.return_60d_pct ?? null,
      ma20_position: ctx.kodex200.ma20_position ?? null,
      ma60_position: ctx.kodex200.ma60_position ?? null,
    },
    kospi: {
      status: ctx.kospi.status,
      return_20d_pct: ctx.kospi.return_20d_pct ?? null,
      return_60d_pct: ctx.kospi.return_60d_pct ?? null,
    },
    candidate_excess_returns: candidates.map((c) => ({
      rank: c.rank ?? null,
      ticker: c.ticker ?? null,
      name: c.name ?? null,
      vs_kodex200_1m_pctp: c.excess_return?.vs_kodex200_1m_pctp ?? null,
      vs_kodex200_3m_pctp: c.excess_return?.vs_kodex200_3m_pctp ?? null,
      vs_kospi_1m_pctp: c.excess_return?.vs_kospi_1m_pctp ?? null,
      vs_kospi_3m_pctp: c.excess_return?.vs_kospi_3m_pctp ?? null,
    })),
  };
}
