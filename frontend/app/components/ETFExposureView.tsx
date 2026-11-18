"use client";

// ETF Exposure 화면 — 탭 컨테이너 (POC2 — 2026-05-27).
//
// 책임 (지시문 §5 / §6):
// - Market Discovery 에서 sessionStorage 로 넘어온 ETF Exposure draft 로딩.
// - draft 없으면 안내 + 비활성 상태.
// - [구성종목] / [중복률] 탭 분리.
// - 분석 결과를 AI Sessions 로 넘기는 별도 카드 (copy text 포함 메시지 + draft).
//
// POC6-32 V2(판정 §3 · Q9 (a) 보완 · PLAN S6 · §9 I-9 · I-10) — 두 가지로 연다.
// - 한 ETF 모드: 다른 화면의 [구성종목 보기]가 넘긴 ETF 하나(lib/detailNav 한 번 넘김). 그 ETF 의 구성 표 · 저장 행 수 ·
//   구성 기준일 · 상태 넷 · 기존 집중(Top 1 · 3 · 5 · 10)을 저장 자료로만 보이고, [구성종목 수집]은 그 ETF 하나만 받는다.
//   목록 초안은 읽지도 바꾸지도 않는다. 목록 탭 · 보유 겹침 카드 · AI 넘기기 · NAV 카드 · 고른 후보 줄은 없다.
// - 목록 모드: 「후보리스트」 [이 목록을 ETF 구성종목에서 보기]가 넘긴 목록 전체(지금 그대로 · 머리에 넘겨받은 목록 설명).

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  buildMarketDiscoveryCopyText,
} from "@/lib/marketDiscoveryCopyText";
import {
  ApiConfigError,
  CONSTITUENTS_TOP_K,
  ApiRequestError,
  type ConstituentsAnalysisResponse,
  type ConstituentsSummaryResponse,
  fetchConstituentsAnalysis,
  fetchConstituentsSummary,
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
import ConstituentsTab, {
  CollectButton,
  CollectHelp,
  CollectStatus,
  SingleEtfConstituents,
  useCandidateCollect,
} from "./ConstituentsTab";
import CrossFamilyCard, { signed } from "./CrossFamilyCard";
import { fetchConstituentsCrossFamily, type CrossFamilyResponse } from "@/lib/api/constituentsStatus";
import { BASIS_LABEL, filtersText, md } from "@/lib/etfCompare";
import { presetOneTimeCondition } from "@/lib/etfCompareCondition";
import { type ExposureSinglePreset, takeExposureSingle } from "@/lib/detailNav";
import { splitPairs } from "@/lib/constituentsText";
import { presetCompareCandidate } from "./workbench/compareSelection";
import { directionColor } from "./workbench/helpers";
import HoldingsOverlapBridgeCard, {
  type BridgeState,
} from "./HoldingsOverlapBridgeCard";
import type { MenuKey } from "./LeftSidebar";
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
      // POC6-31 — ETF별 실제 구성일 · 원천 기준일 확인 여부
      asof: c.asof,
      asof_confirmed: c.asof_confirmed ?? null,
      top_holdings: c.top_holdings,
      concentration: c.concentration,
    })),
  };
}

// POC6-31(판정 Q7 · Q21 · §4 M2) — 보낸 범위와 날짜를 적는다: 같은 구성일 쌍(서버 pair_scope · 양쪽 원천일 확인) 중
// 중복률 상위 10쌍 · 남은 쌍 수 · 같은 구성일이 아닌 쌍 수(구성일 다름 · 원천 기준일 미확인 · 한쪽 자료 없음) ·
// 예전 '반복 등장 핵심 종목' 대신 여러 지수 계열이 함께 담은 주식(상위 10 · 범위 · 읽지 못하면 그 사실).
function _toOverlapSnapshot(
  a: ConstituentsAnalysisResponse | null,
  cf: CrossFamilyResponse | null,
  cfError: string | null,
): Record<string, unknown> | null {
  if (!a) return null;
  const split = splitPairs(a.overlap_matrix);
  const same = split.same_date;
  const top = [...same]
    .sort((x, y) => (y.weighted_overlap_pct ?? -1) - (x.weighted_overlap_pct ?? -1))
    .slice(0, 10);
  return {
    asof: a.asof,
    pairs_scope: {
      same_date_pairs: same.length,
      sent: top.length,
      rest: same.length - top.length,
      different_date_pairs: split.different_date.length,
      unconfirmed_pairs: split.unconfirmed.length,
      no_data_pairs: split.no_data.length,
    },
    matrix: top.map((p) => ({
      left_ticker: p.left_ticker,
      right_ticker: p.right_ticker,
      left_asof: p.left_asof ?? null,
      right_asof: p.right_asof ?? null,
      common_count_top10: p.common_count_top10,
      weighted_overlap_pct: p.weighted_overlap_pct,
      common_holdings: p.common_holdings,
    })),
    cross_family: cf
      ? {
          status: cf.status,
          scope: cf.scope,
          total: cf.stocks.length,
          sent: Math.min(10, cf.stocks.length),
          stocks: cf.stocks.slice(0, 10).map((st) => ({
            name: st.name,
            family_count: st.family_count,
            etf_count: st.etf_count,
            max_weight_pct: st.max_weight_pct,
            max_etf: st.max_entry.etf_name ?? st.max_entry.etf,
          })),
        }
      : { status: cfError ? "read_failed" : "not_loaded", error: cfError },
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

// 보낸 화면 이름 — 「…」로 감싼 이름(이미 감쌌으면 그대로).
function fromLabel(from: string): string {
  return /^「.*」$/.test(from) ? from : `「${from}」`;
}

// 한 ETF 를 보낸 화면의 목록 조건(받는 쪽이 해석 · 모양이 다르면 쓰지 않음) — '1개월 상위 · 10/19 → 11/16 · … 제외'.
export function presetConditionText(cond: unknown): string | null {
  if (!cond || typeof cond !== "object") return null;
  const c = cond as Record<string, unknown>;
  const basis = typeof c.basis === "string" ? (BASIS_LABEL as Record<string, string>)[c.basis] : undefined;
  if (!basis) return null;
  const side = c.side === "top" ? " 상위" : c.side === "bottom" ? " 하위" : "";
  const parts = [`${basis}${side}`];
  if (typeof c.start === "string" && typeof c.end === "string") parts.push(`${md(c.start)} → ${md(c.end)}`);
  if (c.filters && typeof c.filters === "object") {
    parts.push(filtersText(c.filters as Parameters<typeof filtersText>[0]));
  }
  return parts.join(" · ");
}

// 목록 모드 머리 — 넘겨받은 목록(조건 · 기간 · 개수)과 이 화면이 보이는 것.
export function listHeadText(draft: ETFExposureDraft): string {
  const n = draft.candidate_snapshot.length;
  const lc = draft.list_condition;
  const what = draft.list_scope
    ? `넘겨받은 목록: ${draft.list_scope}`
    : lc
      ? `넘겨받은 목록: ${BASIS_LABEL[lc.basis]} ${lc.side === "top" ? "상위" : "하위"} · ${md(lc.start)} → ${md(lc.end)} · ${filtersText(lc.filters)}`
      : `넘겨받은 후보 ${n}개 · 목록 기준일 ${md(draft.asof)}`;
  return `${what} · 대상 ${n}개 · 아래 = 그 ETF 들의 저장 구성(ETF 마다 구성일)과 후보끼리 중복률`;
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
  // POC6-32 V2(PLAN S6) — 한 ETF 모드: 처음 그릴 때 한 번 꺼낸다(useState 초기값 · Strict Mode 에서도 첫 호출 값을 씀 ·
  // compareSelection 을 받는 「보유와 후보 비교」와 같은 방식). 없으면 목록 모드.
  const [single] = useState<ExposureSinglePreset | null>(() => takeExposureSingle());
  const [singleData, setSingleData] = useState<ConstituentsSummaryResponse | null>(null);
  const [singleError, setSingleError] = useState<string | null>(null);
  const [draft, setDraft] = useState<ETFExposureDraft | null>(null);
  const [draftLoaded, setDraftLoaded] = useState<boolean>(false);
  const [active, setActive] = useState<TabKey>("constituents");
  const [analysis, setAnalysis] = useState<ConstituentsAnalysisResponse | null>(
    null,
  );
  // POC6-31 — 분석을 못 읽으면 알린다(예전: 조용히 비움) · 여러 지수 계열이 함께 담은 주식 · 고른 후보
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [crossFamily, setCrossFamily] = useState<CrossFamilyResponse | null>(null);
  const [crossError, setCrossError] = useState<string | null>(null);
  const [picked, setPicked] = useState<{ ticker: string; name: string | null } | null>(null);

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

  // 분석 · 공통 주식을 저장 자료로 읽는다(외부 호출 없음) — 화면 진입 · 수집 작업이 끝난 뒤.
  // 검증자 r1 F4 — 읽기마다 순번을 매겨 가장 최근 읽기의 응답만 반영한다(수집 전에 시작한 늦은 응답이 새 결과를
  // 덮지 않게 · 화면 두 탭 · AI 투자 세션으로 넘기는 초안이 같은 최신 응답을 쓴다).
  const loadSeq = useRef(0);
  const loadAll = useCallback((d: ETFExposureDraft) => {
    const tickers = d.candidate_snapshot.map((c) => c.ticker).filter((t): t is string => !!t);
    if (tickers.length === 0) return;
    const my = ++loadSeq.current;
    const latest = () => my === loadSeq.current;
    // 2026-08-19 설계 확정 — 표시 깊이 30. 중복률은 서버가 상위 10건 고정으로 계산한다.
    // POC6-31(판정 Q7) — 30개까지 · ETF별 실제 날짜(서버).
    fetchConstituentsAnalysis(tickers, null, CONSTITUENTS_TOP_K)
      .then((a) => {
        if (!latest()) return;
        setAnalysis(a);
        setAnalysisError(null);
      })
      .catch((e) => {
        if (!latest()) return;
        setAnalysis(null);
        setAnalysisError(e instanceof Error ? e.message : "알 수 없는 오류");
      });
    fetchConstituentsCrossFamily(tickers)
      .then((cf) => {
        if (!latest()) return;
        setCrossFamily(cf);
        setCrossError(null);
      })
      .catch((e) => {
        if (!latest()) return;
        setCrossFamily(null);
        setCrossError(e instanceof Error ? e.message : "알 수 없는 오류");
      });
  }, []);

  // 한 ETF 구성 — 저장 자료 읽기(수집 없음) · 화면 진입 · 이 ETF 수집 작업이 끝난 뒤. 가장 최근 읽기만 반영(같은 순번).
  const loadSingle = useCallback(() => {
    if (!single) return;
    const my = ++loadSeq.current;
    fetchConstituentsSummary(single.ticker)
      .then((r) => {
        if (my !== loadSeq.current) return;
        setSingleData(r);
        setSingleError(null);
      })
      .catch((e) => {
        if (my !== loadSeq.current) return;
        setSingleData(null);
        setSingleError(e instanceof Error ? e.message : "알 수 없는 오류");
      });
  }, [single]);

  useEffect(() => {
    if (single) {
      // 한 ETF 모드 — 목록 초안은 읽지도 바꾸지도 않는다.
      loadSingle();
      return;
    }
    const d = loadETFExposureDraft();
    setDraft(d);
    setDraftLoaded(true);
    // draft 가 있으면 마운트 시점에 캐시 기반 분석 즉시 시도 (외부 fetch 없이
    // SQLite 만 조회 — analysis 는 read-only).
    // 2026-06-01 FIX — asof 는 명시 X. 백엔드가 latest_constituent_asof MAX
    // 사용 (Naver referenceDate 와 draft.asof 불일치로 인한 0건 회피).
    if (d) loadAll(d);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 2026-08-19 중복률 탭 카드 전환 — 티커만으로는 어느 ETF 끼리 겹치는지 못 읽는다.
  // analysis 응답의 etf_name 은 현재 캐시에서 전부 null 이라, 화면이 이미 들고 있는
  // draft 후보 스냅샷에서 이름을 가져온다 (신규 API·백엔드 변경 없음).
  // draft 에 없는 티커는 맵에 넣지 않는다 — 표시 측이 티커 그대로 쓴다.
  const nameByTicker = useMemo(() => {
    const m: Record<string, string> = {};
    for (const c of draft?.candidate_snapshot ?? []) {
      if (c.ticker && c.name) m[c.ticker] = c.name;
    }
    return m;
  }, [draft]);

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
        crossFamily,
        crossFamilyError: crossError,
        // POC6-01 — 넘길 때의 시장 흐름 글(예전 draft 면 구간 없음).
        marketFlowText: draft.market_flow_text,
        // POC6-29 — 「후보리스트」에서 넘긴 목록의 범위(예전 draft 면 없음).
        listScope: draft.list_scope,
      }),
      linked_market_refresh_id: null,
      draft_created_at: new Date().toISOString(),
      market_context_snapshot: draft.market_context_snapshot ?? null,
      constituent_snapshot: _toConstituentSnapshot(analysis),
      overlap_snapshot: _toOverlapSnapshot(analysis, crossFamily, crossError),
      short_term_momentum_snapshot: _toShortTermMomentumSnapshot(draft),
      data_quality_snapshot: _toDataQualitySnapshot(draft),
    };
    saveAISessionsDraft(aiDraft);
    onNavigate?.("ai_sessions");
  }, [draft, analysis, crossFamily, crossError, onNavigate]);

  // POC6-31(판정 Q10) — 후보 한 건 고르기 → 「보유와 후보 비교」(넘긴 목록의 조건을 이번 이동에만 · 시작일 · 끝일을
  // 함께 넘겨 받는 화면이 자기 목록과 대조).
  const pick = useCallback((ticker: string, name: string | null) => setPicked({ ticker, name }), []);
  const goCompare = useCallback(() => {
    if (!picked || !draft) return;
    const lc = draft.list_condition;
    const condition = lc ? { basis: lc.basis, filters: { ...lc.filters } } : null;
    presetCompareCandidate({
      ticker: picked.ticker,
      name: picked.name,
      side: lc?.side ?? "top",
      condition,
      start: lc?.start ?? null,
      end: lc?.end ?? null,
    });
    if (condition) presetOneTimeCondition("compare", condition);
    onNavigate?.("holding_candidate_compare");
  }, [picked, draft, onNavigate]);
  const returnByTicker = useMemo(() => {
    const m: Record<string, number | null> = {};
    for (const c of draft?.candidate_snapshot ?? []) if (c.ticker) m[c.ticker] = c.one_month_return_pct ?? null;
    return m;
  }, [draft]);

  // 화면 역할 설명 띠(POC6-32 V2 PLAN S6 — 낡은 'STEP 2' · 'ML / 위험 감지' 문구를 지금 화면이 하는 일로 고침 ·
  // 판정 §3: 한 ETF 의 집중 = 한 ETF 모드 · 후보끼리 중복 = 목록 모드 · 내 보유 노출 = 「주간 ETF 점검」 ③).
  const roleBanner = (
    <div className="role-banner" data-testid="exposure-role">
      <strong>목록 보기</strong> 「후보리스트」에서 넘긴 ETF 들이 실제로 어떤 종목을 담고 있는지(ETF 마다 구성일)와 후보끼리
      얼마나 겹치는지(중복률 · 여러 지수가 함께 담은 주식)를 저장된 구성으로 봅니다. ETF 하나의 집중은 [구성종목 보기],
      내 보유와 겹치는 정도는 「주간 ETF 점검」 ③에서 봅니다.
    </div>
  );
  const singleBanner = (
    <div className="role-banner" data-testid="exposure-role">
      <strong>한 ETF 보기</strong> 이 ETF 가 실제로 어떤 종목에 얼마나 집중되는지(주요 편입 · 합산 비중)를 저장된 구성으로
      봅니다. 후보끼리 겹치는 정도는 「후보리스트」 [이 목록을 ETF 구성종목에서 보기]로 연 목록에서, 내 보유와 겹치는 정도는
      「주간 ETF 점검」 ③에서 봅니다.
    </div>
  );

  const candidateTickers = useMemo(
    () =>
      (draft?.candidate_snapshot ?? [])
        .map((c) => c.ticker)
        .filter((t): t is string => !!t),
    [draft],
  );
  // POC6-31 — 후보 수집 따라가기는 화면이 든다(탭을 바꿔도 이어짐 · 이 목록의 작업이 끝나면 분석 · 공통 주식 다시 읽기).
  // POC6-32 V2 — 한 ETF 모드는 그 ETF 하나만 대상(끝나면 그 ETF 구성 다시 읽기).
  const collectTickers = useMemo(() => (single ? [single.ticker] : candidateTickers), [single, candidateTickers]);
  const collect = useCandidateCollect(collectTickers, () => {
    if (single) loadSingle();
    else if (draft) loadAll(draft);
  });

  const repeatedCoreTickers = useMemo(
    () =>
      (analysis?.repeated_core_holdings ?? [])
        .map((r) => r.ticker)
        .filter((t): t is string => !!t),
    [analysis],
  );

  if (single) {
    const cond = presetConditionText(single.condition);
    return (
      <section aria-labelledby="etf-exposure-h" data-testid="exposure-single">
        <div className="ec-head">
          <h1 id="etf-exposure-h">ETF 구성종목</h1>
          <CollectButton collect={collect} count={1} />
        </div>
        <p className="subtitle" data-testid="exposure-single-head">
          {fromLabel(single.from)}에서 고른 ETF 하나를 보여 줍니다 · 저장 자료를 먼저 읽고 수집은 [구성종목 수집]을 누를
          때만(이 ETF 하나)
        </p>
        {cond ? (
          <p className="ec-small" data-testid="exposure-single-cond">
            보낸 화면의 목록: {cond} · 아래 구성 기준일은 그 기간과 따로 저장된 구성의 날짜입니다
          </p>
        ) : null}
        <div className="exp-top" data-testid="exposure-top">
          <CollectStatus collect={collect} scope="single" />
          <CollectHelp />
        </div>
        {singleBanner}
        <SingleEtfConstituents ticker={single.ticker} name={single.name} data={singleData} error={singleError} />
      </section>
    );
  }

  if (!draftLoaded) {
    return (
      <section aria-labelledby="etf-exposure-h">
        <h1 id="etf-exposure-h">ETF 구성종목</h1>
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
        <h1 id="etf-exposure-h">ETF 구성종목</h1>
        {roleBanner}
        <div className="card">
          <div className="message info">
            넘겨받은 목록이 없습니다. 목록은 「후보리스트」 [이 목록을 ETF 구성종목에서 보기]로 넘기고, ETF 하나는 「주간 ETF
            점검」 ③ 또는 「후보리스트」 · 「섹터요약」 행 상세의 [구성종목 보기]로 엽니다.
          </div>
        </div>
      </section>
    );
  }

  return (
    <section aria-labelledby="etf-exposure-h">
      {/* POC6-31 사용자 직접 지시(2026-11-16) — 맨 아래에 있던 동작 버튼을 제목 줄로 올린다(형제 화면 「후보리스트」 ·
          「보유와 후보 비교」와 같은 머리 · 중간 버튼 · 흰 바탕 파란 테두리). 수집 상태 · 고른 후보는 탭과 상관없이 그 아래,
          보유 ETF 겹침은 누른 뒤에만 그 아래, 설명 띠는 결론 · 버튼 아래(제목 → 결론 → 버튼 → 설명 → 세부). */}
      <div className="ec-head">
        <h1 id="etf-exposure-h">ETF 구성종목</h1>
        <CollectButton collect={collect} count={candidateTickers.length} />
        <button
          type="button"
          className="wb-btn btn-md"
          onClick={() => void loadBridge()}
          disabled={bridgeState === "loading"}
          data-testid="exposure-bridge-load"
        >
          보유 ETF 겹침 불러오기
        </button>
        <button type="button" className="wb-btn btn-md" onClick={handleTransferToSessions} data-testid="exposure-to-ai">
          AI 투자 세션으로 넘기기
        </button>
      </div>
      <p className="subtitle" data-testid="exposure-list-head">
        {listHeadText(draft)}
      </p>
      {/* POC6-31(형수님 화면 의견 · 목업 확인 2026-11-16) — 고른 후보 줄은 화면을 내려도 위에 붙어 있고(탭과 상관없이),
          고르면 파란 줄로 바뀐다. */}
      <div className={picked ? "exp-picked exp-picked-on" : "exp-picked"} data-testid="exposure-picked">
        {picked ? (
          <>
            <span className="exp-picked-who">
              고른 후보: <b>{picked.name ?? picked.ticker}</b>{" "}
              <span style={{ color: directionColor(returnByTicker[picked.ticker]) }}>
                {signed(returnByTicker[picked.ticker])}
              </span>
            </span>
            {onNavigate ? (
              <button type="button" className="wb-btn btn-md exp-go" onClick={goCompare} data-testid="exposure-compare">
                보유와 후보 비교에서 보기 →
              </button>
            ) : null}
          </>
        ) : (
          <span className="helper">후보는 구성 표의 [후보로 고르기] 또는 공통 주식 카드의 ETF 줄을 눌러 고릅니다</span>
        )}
      </div>
      <div className="exp-top" data-testid="exposure-top">
        <CollectStatus collect={collect} />
        <CollectHelp />
        <p className="helper" style={{ margin: 0 }}>
          [AI 투자 세션으로 넘기기] = 후보 · 시장 문맥 · 구성종목 · 중복률 분석을 「AI 투자 세션」 새 기록으로 넘깁니다(외부 AI
          답변 · 메모는 거기서 저장).
        </p>
      </div>

      {/* 2026-06-06 AC-5/6 — 보유 ETF 겹침. 명시 클릭으로만 읽는다(위 버튼) · 누른 뒤에만 이 자리에 보인다. */}
      {bridgeState !== "not_loaded" ? (
        <HoldingsOverlapBridgeCard
          state={bridgeState}
          data={bridgeData}
          errorMessage={bridgeError}
          candidateTickers={candidateTickers}
          repeatedCoreTickers={repeatedCoreTickers}
          onLoad={loadBridge}
        />
      ) : null}

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

      {analysisError ? (
        <div className="message error" data-testid="exposure-analysis-error">
          구성 자료를 읽지 못했습니다 — {analysisError}
        </div>
      ) : null}
      {active === "constituents" ? (
        <ConstituentsTab
          draft={draft}
          analysis={analysis}
          nameByTicker={nameByTicker}
          collect={collect}
          onPick={pick}
        />
      ) : (
        <OverlapTab
          analysis={analysis}
          nameByTicker={nameByTicker}
          slot={
            <CrossFamilyCard
              cf={crossFamily}
              error={crossError}
              returnByTicker={returnByTicker}
              onPick={pick}
              picked={picked}
            />
          }
        />
      )}

      {/* 2026-06-06 AC-7 — NAV / 괴리율 카드(버튼 없음 · 맨 아래 그대로). */}
      <NavDiscountPlaceholderCard candidates={draft.market_candidates ?? []} />
    </section>
  );
}
