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
  onNavigate?: (key: MenuKey) => void;
}

export default function TransferToAISessionsCard({
  asof,
  filters,
  candidates,
  linkedMarketRefreshId,
  onNavigate,
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
      // 결과 텍스트가 항상 동일하다.
      question_text: buildMarketDiscoveryCopyText({
        asof,
        filters,
        candidates,
      }),
      linked_market_refresh_id: linkedMarketRefreshId,
      draft_created_at: new Date().toISOString(),
    };
    saveAISessionsDraft(draft);
    onNavigate?.("ai_sessions");
  }, [asof, filters, candidates, linkedMarketRefreshId, onNavigate]);

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
