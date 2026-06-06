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
  ApiConfigError,
  ApiRequestError,
  type ConstituentsAnalysisResponse,
  fetchConstituentsAnalysis,
  fetchHoldingsMarketEvidence,
  type HoldingsMarketEvidenceResponse,
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
import HoldingsOverlapBridgeCard, {
  type BridgeState,
} from "./HoldingsOverlapBridgeCard";
import type { MenuKey } from "./LeftSidebar";
import MLTimeseriesReadinessCard from "./MLTimeseriesReadinessCard";
import NavDiscountPlaceholderCard from "./NavDiscountPlaceholderCard";
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

// 2026-06-01 — Market Discovery Evidence Closeout 1차. draft.market_candidates
// 안에 이미 응답으로 받은 short_term_momentum / data_quality 가 포함되어 있어
// AI Sessions snapshot 으로 그대로 추출.
function _toShortTermMomentumSnapshot(
  draft: ETFExposureDraft,
): Record<string, unknown> | null {
  const items = (draft.market_candidates ?? [])
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
  return { asof: draft.asof, benchmark: "KODEX200", items };
}

function _toDataQualitySnapshot(
  draft: ETFExposureDraft,
): Record<string, unknown> | null {
  const items = (draft.market_candidates ?? [])
    .filter((c) => c.data_quality)
    .map((c) => ({
      ticker: c.ticker ?? null,
      name: c.name ?? null,
      daily_return_check: c.data_quality?.daily_return_check ?? null,
      nav_discount: c.data_quality?.nav_discount ?? null,
      warnings: c.data_quality?.warnings ?? [],
    }));
  if (items.length === 0) return null;
  return { asof: draft.asof, items };
}

export default function ETFExposureView({ onNavigate }: Props) {
  const [draft, setDraft] = useState<ETFExposureDraft | null>(null);
  const [draftLoaded, setDraftLoaded] = useState<boolean>(false);
  const [active, setActive] = useState<TabKey>("constituents");
  const [analysis, setAnalysis] = useState<ConstituentsAnalysisResponse | null>(
    null,
  );

  // 2026-06-06 ETF Exposure Data Unfolding 1차 (지시문 §5.6 / AC-5 / AC-6) —
  // Holdings Evidence State Bridge. 컨테이너만 API 호출. 명시 클릭으로만 로딩.
  const [bridgeState, setBridgeState] = useState<BridgeState>("not_loaded");
  const [bridgeData, setBridgeData] =
    useState<HoldingsMarketEvidenceResponse | null>(null);
  const [bridgeError, setBridgeError] = useState<string | null>(null);

  const loadBridge = useCallback(async () => {
    setBridgeState("loading");
    setBridgeError(null);
    try {
      const res = await fetchHoldingsMarketEvidence();
      setBridgeData(res);
      setBridgeState("ok");
    } catch (e) {
      let msg = "알 수 없는 오류";
      if (e instanceof ApiConfigError) msg = e.message;
      else if (e instanceof ApiRequestError) {
        msg = `HTTP ${e.httpStatus}: ${e.message}`;
      } else if (e instanceof Error) msg = e.message;
      setBridgeError(msg);
      setBridgeState("unavailable");
    }
  }, []);

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
      short_term_momentum_snapshot: _toShortTermMomentumSnapshot(draft),
      data_quality_snapshot: _toDataQualitySnapshot(draft),
    };
    saveAISessionsDraft(aiDraft);
    onNavigate?.("ai_sessions");
  }, [draft, analysis, onNavigate]);

  const tickerCount = useMemo(
    () => (draft ? draft.candidate_snapshot.length : 0),
    [draft],
  );

  // 2026-06-06 ETF Exposure Data Unfolding 1차 (지시문 §5.1 / AC-1) —
  // 화면 역할을 펼쳐보기 / 비교 / ML 준비 상태 확인의 프레임으로 명시화.
  const roleBanner = (
    <div className="role-banner">
      <strong>[판단 흐름 STEP 2]</strong> ETF Exposure는 후보 ETF들이 실제로 어떤
      종목을 담고 있는지, 서로 얼마나 겹치는지, 그리고 ML / 위험 감지에 필요한
      데이터가 현재 어디까지 준비됐는지 확인하는 화면입니다. Market Discovery에서
      &lsquo;ETF Exposure로 넘기기&rsquo;를 먼저 실행해야 후보 목록이 이 화면에
      연결됩니다.
    </div>
  );

  const candidateTickers = useMemo(
    () =>
      (draft?.candidate_snapshot ?? [])
        .map((c) => c.ticker)
        .filter((t): t is string => !!t),
    [draft],
  );

  const repeatedCoreTickers = useMemo(
    () =>
      (analysis?.repeated_core_holdings ?? [])
        .map((r) => r.ticker)
        .filter((t): t is string => !!t),
    [analysis],
  );

  if (!draftLoaded) {
    return (
      <section aria-labelledby="etf-exposure-h">
        <h1 id="etf-exposure-h">ETF Exposure</h1>
        {roleBanner}
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
        {roleBanner}
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
      {roleBanner}

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

      {/* 2026-06-06 ETF Exposure Data Unfolding 1차 (AC-5/6) — Holdings Evidence
          State Bridge. 명시 클릭으로만 로딩. 컨테이너만 API 호출. */}
      <HoldingsOverlapBridgeCard
        state={bridgeState}
        data={bridgeData}
        errorMessage={bridgeError}
        candidateTickers={candidateTickers}
        repeatedCoreTickers={repeatedCoreTickers}
        onLoad={loadBridge}
      />

      {/* 2026-06-06 ETF Exposure Data Unfolding 1차 (AC-7) —
          NAV/괴리율 source 미연동 빈자리 표시 (≥2 화면 노출 정책). */}
      <NavDiscountPlaceholderCard />

      {/* 2026-06-06 ETF Exposure Data Unfolding 1차 (AC-8) —
          ML / 위험 감지 시계열 9축 준비 상태 표시. 학습 / threshold / factor 확정 X. */}
      <MLTimeseriesReadinessCard />

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
