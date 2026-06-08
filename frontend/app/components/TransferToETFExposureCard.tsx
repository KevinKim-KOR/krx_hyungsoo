"use client";

// Market Discovery → ETF Exposure 전달 카드 (POC2 — 2026-05-27).
//
// 책임 (지시문 §5):
// - 현재 Market Discovery 응답 (asof + filters + candidates + market_context)
//   을 sessionStorage 에 ETF Exposure draft 로 저장.
// - 부모 (MainPanel) 의 setActive("etf_exposure") 호출로 화면 전환.
//
// 별도 파일로 분리해 MarketDiscoveryView KS-10 영향 최소화.

import { useCallback } from "react";
import {
  type MarketCandidate,
  type MarketContext,
  type MarketTopNFilters,
} from "@/lib/api";
import {
  buildETFExposureDraftFromMarketDiscovery,
  saveETFExposureDraft,
  toMarketContextSnapshot,
} from "@/lib/etfExposureDraft";
import type { MenuKey } from "./LeftSidebar";

interface Props {
  asof: string;
  filters: MarketTopNFilters;
  candidates: MarketCandidate[];
  marketContext: MarketContext | null;
  onNavigate?: (key: MenuKey) => void;
  // 2026-06-08 — compact 모드: 카드 wrapper / 설명 텍스트 없이 버튼만 렌더.
  compact?: boolean;
}

export default function TransferToETFExposureCard({
  asof,
  filters,
  candidates,
  marketContext,
  onNavigate,
  compact = false,
}: Props) {
  const handleTransfer = useCallback(() => {
    if (candidates.length === 0) return;
    const draft = buildETFExposureDraftFromMarketDiscovery({
      asof,
      filters,
      candidates,
      marketContext,
      marketContextSnapshot: toMarketContextSnapshot(marketContext, candidates),
    });
    saveETFExposureDraft(draft);
    onNavigate?.("etf_exposure");
  }, [asof, filters, candidates, marketContext, onNavigate]);

  if (compact) {
    return (
      <button
        type="button"
        onClick={handleTransfer}
        disabled={candidates.length === 0}
      >
        ETF Exposure 로 넘기기
      </button>
    );
  }
  return (
    <div className="card">
      <h2>ETF Exposure 전달</h2>
      <p className="helper" style={{ marginBottom: 8 }}>
        현재 후보 ETF 목록을 ETF Exposure 화면으로 넘깁니다. 거기서 외부 KRX
        데이터로 상위 구성종목과 ETF 간 중복률을 분석합니다 (1회 최대 10개 후보).
      </p>
      <div className="btn-row">
        <button
          type="button"
          onClick={handleTransfer}
          disabled={candidates.length === 0}
        >
          ETF Exposure 로 넘기기
        </button>
      </div>
    </div>
  );
}
