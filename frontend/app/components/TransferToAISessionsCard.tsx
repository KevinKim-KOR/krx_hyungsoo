"use client";

// "AI Sessions로 넘기기" 카드 (POC2 — 2026-05-21).
//
// Market Discovery 의 책임:
// - 현재 응답 (asof / filters / candidates / latest_refresh.refresh_id) 을
//   sessionStorage 에 draft 로 저장.
// - 부모 (MainPanel) 의 setActive("ai_sessions") 를 호출해 화면 전환.
//
// 별도 파일로 분리한 이유:
// MarketDiscoveryView.tsx 가 KS-10 near 850 라인을 넘어 891 라인까지 갔다.
// 본 카드를 분리해서 라인 수를 다시 near 미만으로 낮춘다 (지시문 §18 / KS-10).

import { useCallback } from "react";
import {
  type MarketCandidate,
  type MarketContext,
  type MarketTopNFilters,
} from "@/lib/api";
import {
  saveAISessionsDraft,
  type AISessionsDraft,
} from "@/lib/aiSessionsDraft";
import { buildMarketDiscoveryCopyText } from "@/lib/marketDiscoveryCopyText";
import type { MenuKey } from "./LeftSidebar";

interface Props {
  asof: string;
  filters: MarketTopNFilters;
  candidates: MarketCandidate[];
  linkedMarketRefreshId: string | null;
  // 2026-05-22 — Market Regime & Benchmark Context 1차 (지시문 §12). null 허용.
  marketContext: MarketContext | null;
  onNavigate?: (key: MenuKey) => void;
  // 2026-06-08 — compact 모드: 카드 wrapper / 설명 텍스트 없이 버튼만 렌더.
  // 사용자 요청 (Market Discovery 화면 정리) — 본 모드로 하단 한 줄에 배치.
  compact?: boolean;
}


// 2026-05-22 — POST /decision/sessions 의 market_context_snapshot 으로 영속될
// 요약 dict 를 만든다. 지시문 §12 명시:
// - 시장 국면 / KODEX200 / KOSPI 보조 지표
// - **후보별 KODEX200 대비 초과수익**
// - **후보별 KOSPI 대비 초과수익, 있으면 포함**
//
// 2026-05-27 FIX (검증자 A-1 NOTE 반영): 1차 구현이 시장 국면 요약만 포함하고
// 후보별 초과수익을 누락했음. candidate_excess_returns 배열로 명시 추가 —
// AI Sessions 상세 화면에서 저장 시점의 후보별 alpha 가 그대로 복기되도록.
function _toMarketContextSnapshot(
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

// 2026-06-01 Market Discovery Evidence Closeout 1차 — 지시문 §11.1.
function _toShortTermMomentumSnapshot(
  asof: string,
  candidates: MarketCandidate[],
): Record<string, unknown> | null {
  const items = candidates
    .filter((c) => c.short_term_momentum)
    .map((c) => ({
      ticker: c.ticker ?? null,
      name: c.name ?? null,
      return_5d_pct: c.short_term_momentum?.return_5d_pct ?? null,
      return_10d_pct: c.short_term_momentum?.return_10d_pct ?? null,
      return_20d_pct: c.short_term_momentum?.return_20d_pct ?? null,
      excess_vs_kodex200_5d_pctp:
        c.short_term_momentum?.excess_vs_kodex200_5d_pctp ?? null,
      excess_vs_kodex200_10d_pctp:
        c.short_term_momentum?.excess_vs_kodex200_10d_pctp ?? null,
      excess_vs_kodex200_20d_pctp:
        c.short_term_momentum?.excess_vs_kodex200_20d_pctp ?? null,
    }));
  if (items.length === 0) return null;
  return { asof, benchmark: "KODEX200", items };
}

// 2026-06-01 Market Discovery Evidence Closeout 1차 — 지시문 §11.2.
function _toDataQualitySnapshot(
  asof: string,
  candidates: MarketCandidate[],
): Record<string, unknown> | null {
  const items = candidates
    .filter((c) => c.data_quality)
    .map((c) => ({
      ticker: c.ticker ?? null,
      name: c.name ?? null,
      daily_return_check: c.data_quality?.daily_return_check ?? null,
      nav_discount: c.data_quality?.nav_discount ?? null,
      warnings: c.data_quality?.warnings ?? [],
    }));
  if (items.length === 0) return null;
  return { asof, items };
}

export default function TransferToAISessionsCard({
  asof,
  filters,
  candidates,
  linkedMarketRefreshId,
  marketContext,
  onNavigate,
  compact = false,
}: Props) {
  const handleTransfer = useCallback(() => {
    if (candidates.length === 0) return;
    const draft: AISessionsDraft = {
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
      // CopyTextCard 와 동일 모듈을 사용해 question_text 자동 생성 — 두 카드의
      // 결과 텍스트가 항상 동일하다 (시스템 시장 판정 + 후보 강도 포함).
      question_text: buildMarketDiscoveryCopyText({
        asof,
        filters,
        candidates,
        marketContext,
      }),
      linked_market_refresh_id: linkedMarketRefreshId,
      draft_created_at: new Date().toISOString(),
      // 2026-05-22 — AI Sessions 저장 payload 의 market_context_snapshot 으로
      // 그대로 영속화된다 (지시문 §13). 2026-05-27 FIX — 후보별 초과수익 포함.
      market_context_snapshot: _toMarketContextSnapshot(marketContext, candidates),
      // 2026-06-01 Market Discovery Evidence Closeout 1차 — 단기 흐름 + 데이터 품질.
      short_term_momentum_snapshot: _toShortTermMomentumSnapshot(asof, candidates),
      data_quality_snapshot: _toDataQualitySnapshot(asof, candidates),
    };
    saveAISessionsDraft(draft);
    onNavigate?.("ai_sessions");
  }, [
    asof,
    filters,
    candidates,
    linkedMarketRefreshId,
    marketContext,
    onNavigate,
  ]);

  if (compact) {
    return (
      <button
        type="button"
        onClick={handleTransfer}
        disabled={candidates.length === 0}
      >
        AI Sessions로 넘기기
      </button>
    );
  }
  return (
    <div className="card">
      <h2>AI Sessions 전달</h2>
      <p className="helper" style={{ marginBottom: 8 }}>
        현재 후보 + 필터 + 복사용 문구를 AI Sessions 화면의 새 기록 저장 탭으로
        넘깁니다. 외부 AI 채널에서 받은 답변과 사용자 메모 / 1차 판정은 거기서
        저장합니다.
      </p>
      <div className="btn-row">
        <button
          type="button"
          onClick={handleTransfer}
          disabled={candidates.length === 0}
        >
          AI Sessions로 넘기기
        </button>
      </div>
    </div>
  );
}
