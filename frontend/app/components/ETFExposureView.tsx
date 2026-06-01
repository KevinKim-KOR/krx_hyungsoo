"use client";

// ETF Exposure 화면 — 탭 컨테이너 (POC2 — 2026-05-27).
//
// 책임 (지시문 §5 / §6):
// - Market Discovery 에서 sessionStorage 로 넘어온 ETF Exposure draft 로딩.
// - draft 없으면 안내 + 비활성 상태.
// - [구성종목] / [중복률] 탭 분리.
// - 분석 결과를 AI Sessions 로 넘기는 별도 카드 (copy text 포함 메시지 + draft).

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  buildMarketDiscoveryCopyText,
} from "@/lib/marketDiscoveryCopyText";
import {
  type ConstituentsAnalysisResponse,
  fetchConstituentsAnalysis,
} from "@/lib/api";
import {
  type AISessionsDraft,
  saveAISessionsDraft,
} from "@/lib/aiSessionsDraft";
import {
  type ETFExposureDraft,
  loadETFExposureDraft,
} from "@/lib/etfExposureDraft";
import ConstituentsTab from "./ConstituentsTab";
import type { MenuKey } from "./LeftSidebar";
import OverlapTab from "./OverlapTab";

type TabKey = "constituents" | "overlap";

interface Props {
  onNavigate?: (key: MenuKey) => void;
}

function _toConstituentSnapshot(
  a: ConstituentsAnalysisResponse | null,
): Record<string, unknown> | null {
  if (!a) return null;
  return {
    asof: a.asof,
    top_k: a.top_k,
    coverage: a.coverage,
    items: a.constituents.map((c) => ({
      etf_ticker: c.etf_ticker,
      etf_name: c.etf_name,
      status: c.status,
      source: c.source,
      top_holdings: c.top_holdings,
      concentration: c.concentration,
    })),
  };
}

function _toOverlapSnapshot(
  a: ConstituentsAnalysisResponse | null,
): Record<string, unknown> | null {
  if (!a) return null;
  return {
    asof: a.asof,
    matrix: a.overlap_matrix.map((p) => ({
      left_ticker: p.left_ticker,
      right_ticker: p.right_ticker,
      common_count_top10: p.common_count_top10,
      weighted_overlap_pct: p.weighted_overlap_pct,
      common_holdings: p.common_holdings,
    })),
    repeated_core: a.repeated_core_holdings,
  };
}

export default function ETFExposureView({ onNavigate }: Props) {
  const [draft, setDraft] = useState<ETFExposureDraft | null>(null);
  const [draftLoaded, setDraftLoaded] = useState<boolean>(false);
  const [active, setActive] = useState<TabKey>("constituents");
  const [analysis, setAnalysis] = useState<ConstituentsAnalysisResponse | null>(
    null,
  );

  useEffect(() => {
    const d = loadETFExposureDraft();
    setDraft(d);
    setDraftLoaded(true);
    // draft 가 있으면 마운트 시점에 캐시 기반 분석 즉시 시도 (외부 fetch 없이
    // SQLite 만 조회 — analysis 는 read-only).
    // 2026-06-01 FIX — asof 는 명시 X. 백엔드가 latest_constituent_asof MAX
    // 사용 (Naver referenceDate 와 draft.asof 불일치로 인한 0건 회피).
    if (d) {
      const tickers = d.candidate_snapshot
        .map((c) => c.ticker)
        .filter((t): t is string => !!t);
      if (tickers.length > 0) {
        fetchConstituentsAnalysis(tickers, null, 10)
          .then((a) => setAnalysis(a))
          .catch(() => setAnalysis(null));
      }
    }
  }, []);

  const handleTransferToSessions = useCallback(() => {
    if (!draft) return;
    // 2026-05-27 FIX (검증자 A-1 NOTE 반영) — 시장 판정 + 후보 excess_return 을
    // 반드시 함께 전달. draft.market_context_full / market_candidates 가 정답
    // source (Market Discovery 시점의 전체 MarketContext + excess_return 포함
    // MarketCandidate[]).
    const aiDraft: AISessionsDraft = {
      asof: draft.asof,
      filters: draft.filters,
      candidate_snapshot: draft.candidate_snapshot,
      question_text: buildMarketDiscoveryCopyText({
        asof: draft.asof,
        filters: draft.filters,
        candidates: draft.market_candidates,
        marketContext: draft.market_context_full ?? null,
        constituentsAnalysis: analysis,
      }),
      linked_market_refresh_id: null,
      draft_created_at: new Date().toISOString(),
      market_context_snapshot: draft.market_context_snapshot ?? null,
      constituent_snapshot: _toConstituentSnapshot(analysis),
      overlap_snapshot: _toOverlapSnapshot(analysis),
    };
    saveAISessionsDraft(aiDraft);
    onNavigate?.("ai_sessions");
  }, [draft, analysis, onNavigate]);

  const tickerCount = useMemo(
    () => (draft ? draft.candidate_snapshot.length : 0),
    [draft],
  );

  if (!draftLoaded) {
    return (
      <section aria-labelledby="etf-exposure-h">
        <h1 id="etf-exposure-h">ETF Exposure</h1>
        <div className="card">
          <div className="message info">불러오는 중...</div>
        </div>
      </section>
    );
  }

  if (!draft) {
    return (
      <section aria-labelledby="etf-exposure-h">
        <h1 id="etf-exposure-h">ETF Exposure</h1>
        <div className="card">
          <div className="message info">
            Market Discovery 에서 후보를 조회한 뒤 &ldquo;ETF Exposure 로
            넘기기&rdquo; 를 먼저 실행하세요. 구성종목 / 중복률 분석은 후보 ETF
            목록이 필요합니다.
          </div>
        </div>
      </section>
    );
  }

  return (
    <section aria-labelledby="etf-exposure-h">
      <h1 id="etf-exposure-h">ETF Exposure</h1>
      <p className="subtitle">
        Market Discovery 후보 {tickerCount}개 ETF 의 구성종목과 중복 노출을
        분석합니다. asof {draft.asof}.
      </p>

      <div className="decision-tab-row">
        <button
          type="button"
          className={
            active === "constituents"
              ? "decision-tab-btn decision-tab-active"
              : "decision-tab-btn"
          }
          onClick={() => setActive("constituents")}
        >
          구성종목
        </button>
        <button
          type="button"
          className={
            active === "overlap"
              ? "decision-tab-btn decision-tab-active"
              : "decision-tab-btn"
          }
          onClick={() => setActive("overlap")}
        >
          중복률
        </button>
      </div>

      {active === "constituents" ? (
        <ConstituentsTab
          draft={draft}
          analysis={analysis}
          setAnalysis={setAnalysis}
        />
      ) : (
        <OverlapTab analysis={analysis} />
      )}

      <div className="card">
        <h2>AI Sessions 전달</h2>
        <p className="helper" style={{ marginBottom: 8 }}>
          현재 후보 + 시장 문맥 + 구성종목/중복률 분석을 AI Sessions 새 기록 저장
          탭으로 넘깁니다. 외부 AI 채널 답변과 사용자 메모는 거기서 저장합니다.
        </p>
        <div className="btn-row">
          <button type="button" onClick={handleTransferToSessions}>
            AI Sessions 로 넘기기
          </button>
        </div>
      </div>
    </section>
  );
}
