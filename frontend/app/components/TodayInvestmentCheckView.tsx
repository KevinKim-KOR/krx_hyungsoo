"use client";

// POC3-01 오늘의 투자 점검 (Today Investment Check) — 새 기본 진입 화면.
//
// 설계서 목표(§2): 새 대시보드만 보고 10초 안에 코스피 현재 위치 / 사용자가 생각할 일
// / 시스템이 처리할 일을 구분한다. 개별 ETF 최종 매수·매도 판단이나 신규 위험 산식은
// 이번 Step 범위가 아니다. 코스피 가격과 KODEX200 판정은 하나로 묶지 않는다(§3.1).
//
// 2026-11-09 POC6-27(설계 · PLAN 판정 PASS_WITH_REQUIRED_CORRECTIONS · 사용자 결정 ① ② ③) — 위에서 아래로:
//   1 제목 · [요약 다시 읽기] [?] … · 읽은 시각 · 결과 줄
//   2 「자료 최신화 필요」(대상 있을 때만) | 3 「OCI 운영 스케줄 확인」 — 기본 접힘 · 함께 펼치고 접음(사용자 결정 ⑤)
//   4 「지금 확인할 내용」: 시장 흐름 → 보유 점검 | 잘 오르는 ETF → 자료 · 연구 상태 · 7 현재 제공 범위와 남은 기능(접힘).
// 2026-11-12 POC6-29(설계 §2 · §5 · PLAN §2-2 · §3-2 · §3-6 · 판정 Q1 · Q2 · Q7 · Q8 · Q10):
//   - 머리 버튼 = [요약 다시 읽기] [최신 자료 갱신](PC 서버 묶음 작업 한 번 · 보유 현재가 → 시장 자료 · useTodayRefresh).
//   - 시장 흐름 카드에 시장 판정(KODEX 200) · VIX 한 줄. 보유 점검 · 잘 오르는 ETF 는 각 한 카드(자세히 구역 없음).
//   - 잘 오르는 ETF = 이 화면 자체 기간(기본 저장)으로 읽은 「ETF 비교하기」 요약의 선정 1 ~ 3위(공통 기간 목록).
//   - 보유 점검 = 같은 요약 응답의 price_flow · 「보유」와 같은 판정 · 종목 단위.
//   - [시장 근거와 다른 변화 보기] = 「자료 · 연구 상태」 바로 위 · 처음엔 접힘(KODEX 200 · VIX · 시장 흐름 상세).
//   - 시장 판정 · VIX · KODEX 200 거래량은 지금처럼 GET /market/topn/latest(기본 조건 · 시장 칸만 씀)에서 읽는다.
// [요약 다시 읽기] = 저장 자료 7개를 받아 둔 뒤 최신성을 대조하고, 늦거나 확인이 필요하면 고르게 한다
//   ([취소] = 화면 · 공유 캐시 · 성공 시각 그대로 · 판정 Q3). 시장 판정 · OCI 는 다시 읽지 않는다.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchBenchmarkSeries,
  type PriceSeriesResponse,
  fetchMarketTopnLatest,
  type MarketTopNResponse,
  fetchEnrichedHoldings,
  type EnrichedHoldingsResult,
  fetchHoldingsMarketEvidence,
  type HoldingsMarketEvidenceResponse,
  fetchNavDiscountLatest,
  type NavDiscountLatestResponse,
} from "@/lib/api";
import type { RefreshAllHoldingsStep } from "@/lib/api/refreshAll";
import { etfDetailKey, fetchEtfDetail, type EtfDetailResponse } from "@/lib/api/etfDetail";
import { fetchQuickQuotes, QUICK_QUOTES_KEY, type QuickQuotesResponse } from "@/lib/api/quickQuotes";
import { fetchMorningBasis, MORNING_BASIS_KEY, type MorningBasisResponse } from "@/lib/api/morningBasis";
import { fetchShortFlows, SHORT_FLOWS_KEY, type ShortFlowsResponse } from "@/lib/api/shortFlows";
import { endLine, prevdayLine, todayBasis } from "@/lib/morningText";
import { quickResultLine } from "@/lib/marketNowText";
import { compareSnapshots, snapshotOf, snapshotText } from "@/lib/refreshCompare";
import { commitQuery, invalidateQueries, markQueryFailed, useSharedQuery, type QueryState } from "@/lib/api/queryCache";
import {
  DASH_KEY_HOLDINGS,
  DASH_KEY_EVIDENCE,
  DASH_KEY_MARKET,
  DASH_KEY_NAV,
  DASH_KEY_FORWARD,
  MARKET_FLOW_KEY,
  MARKET_INVALIDATION_KEYS,
} from "@/lib/api/dashboardKeys";
import { etfCompareKey, fetchEtfCompareSummary } from "@/lib/api/etfCompare";
// 연구 줄 · 시장 흐름 조회는 개별 모듈에서(대시보드 시험이 `@/lib/api` 를 통째로 가짜로 바꾸는 방식과 겹치지 않게).
import { fetchForwardComparison, type ForwardComparisonResponse } from "@/lib/api/mlForwardComparison";
import { fetchMarketFlowContext, type MarketFlowContext } from "@/lib/api/marketFlow";
import {
  freshnessRows,
  kstDate,
  needsAttention,
  refreshFailureLines,
  staleAfterRefreshText,
  type FreshSources,
} from "@/lib/todayFreshness";
import { buildTodayMarketCopyText } from "@/lib/todayMarketCopyText";
import type { MenuKey } from "./LeftSidebar";
import HelpPopover from "./holdings_risk_evidence/HelpPopover";
import KospiDetailSection from "./today/KospiDetailSection";
import MaintenanceQueueSection from "./today/MaintenanceQueueSection";
import InDevelopmentSection from "./today/InDevelopmentSection";
import MarketFlowBlock from "./today/MarketFlowBlock";
import MarketEvidenceFold from "./today/MarketEvidenceFold";
import FreshnessCard from "./today/FreshnessCard";
import OciScheduleCard, { mdHm } from "./today/OciScheduleCard";
import StaleConfirmDialog, { type FailedSource } from "./today/StaleConfirmDialog";
import { CandidatesCheckCard, HoldingsCheckCard, SUMMARY_SOURCE_LABEL } from "./today/CheckCards";
import { collectMaintenance } from "./today/maintenanceQueue";
import { useLightRefreshState } from "./today/useLightRefreshState";
import { useTodayRefresh } from "./today/useTodayRefresh";
import { KOSPI_SERIES_KEY } from "./today/KospiChart";
import { useMarketFlowContext } from "./marketflow/useMarketFlowContext";
import SummarySection from "./today/SummarySection";
import { useEtfCompareSummary } from "./workbench/CompareHead";
import {
  dataRow,
  readRangeText,
  readTimeText,
  researchRow,
  summaryTasks,
  type SummaryAction,
} from "./today/summaryLines";

// [요약 다시 읽기] 결과(이 화면 상태 · 저장 없음).
type ReloadState =
  | { phase: "idle" }
  | { phase: "running" }
  | { phase: "done"; at: number }
  | { phase: "partial"; at: number; failed: string[] }
  | { phase: "cancelled"; at: number }
  | { phase: "superseded"; at: number };

type Confirm = {
  purpose: "reload" | "copy";
  rows: ReturnType<typeof needsAttention>;
  failed: FailedSource[];
  onContinue: () => void;
};

// 설계 §2 · §5 — [?]에 먼저 보일 문장.
export const RELOAD_NOTE =
  "PC 에 저장된 값만 다시 읽습니다(새로 받지 않음). 시장 판정은 이 버튼으로 다시 계산하지 않습니다. 새 자료를 받으려면 [최신 자료 갱신]을 누르세요.";

function scrollToArea(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  el.scrollIntoView?.({ behavior: "smooth", block: "start" });
  el.focus({ preventScroll: true });
}

function errText(e: unknown): string {
  return e instanceof Error && e.message ? e.message : "조회 실패";
}

// POC5-UI-03 — 두 안내 구역(코스피 상세 지표 · 개발 중인 판단 기능)을 화면 아래 한 묶음으로(기본 접힘).
function ScopeSection({ market }: { market: QueryState<MarketTopNResponse> }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="tc-card" aria-label="현재 제공 범위와 남은 기능">
      <div className="tc-fold-head">
        <h2 className="tc-h2" style={{ marginBottom: 0 }}>
          현재 제공 범위와 남은 기능
        </h2>
        <button
          type="button"
          className="btn-md tc-fold-btn"
          aria-expanded={open}
          aria-label={open ? "현재 제공 범위와 남은 기능 접기" : "현재 제공 범위와 남은 기능 펼치기"}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "접기" : "펼치기"}
        </button>
      </div>
      {open ? (
        <div className="tc-fold-body">
          <KospiDetailSection market={market} />
          <InDevelopmentSection />
        </div>
      ) : null}
    </section>
  );
}

// 보유 현재가 단계가 받지 못한 이유(서버 사유 코드 → 화면 글 · 서버 원문은 영어 낱말이 섞여 쓰지 않음).
const HOLD_REASON_TEXT: Record<string, string> = {
  holdings_empty: "저장된 보유 종목이 없어 받지 않았습니다(「종목 관리」에서 입력 · 저장)",
  holdings_invalid: "보유 저장 파일을 읽지 못해 받지 않았습니다",
  error: "받는 중 오류가 났습니다",
  all_failed: "받지 못했습니다",
};

// 보유 현재가 단계 결과 한 줄(묶음 작업의 holdings 단계).
function holdingsLine(step: RefreshAllHoldingsStep, range: string | null): { text: string; warn: boolean } {
  const ok = typeof step.ok_count === "number" ? step.ok_count : null;
  const fail = typeof step.fail_count === "number" ? step.fail_count : 0;
  if (step.status === "failed" && fail > 0) return { text: `보유 현재가를 받지 못했습니다(실패 ${fail}건)`, warn: true };
  if (step.status === "failed" || step.status === "skipped")
    return { text: `보유 현재가: ${HOLD_REASON_TEXT[step.reason ?? ""] ?? "받지 못했습니다"}`, warn: true };
  if (ok === 0 && fail > 0) return { text: `보유 현재가를 받지 못했습니다(실패 ${fail}건)`, warn: true };
  if (fail > 0)
    return { text: `보유 현재가 일부 실패 ${fail}건 · 받은 ${ok ?? "확인 불가"}건${range ? ` · 시세 시각 ${range}` : ""}`, warn: true };
  return { text: `보유 현재가 업데이트 완료${ok != null ? ` ${ok}건` : ""}${range ? ` · 시세 시각 ${range}` : ""}`, warn: false };
}

interface Props {
  onNavigate: (key: MenuKey) => void;
}

// 시장 판정 기준 가격(KODEX 200)의 저장 시각 · 가격 시점 — 흐름 문장의 기준 · 갱신 전후 대조(POC6-29 보완 R1 · R2).
const KODEX_TICKERS = ["069500"];

export default function TodayInvestmentCheckView({ onNavigate }: Props) {
  // POC6-29 — 시장 판정 · VIX · 거래량만 쓰므로 기본 조건 한 키(목록 조건과 무관 · DASH_KEY_MARKET).
  const market = useSharedQuery<MarketTopNResponse>(DASH_KEY_MARKET, () => fetchMarketTopnLatest(10));
  // POC6-29 — 잘 오르는 ETF · 보유 점검 = 이 화면 조건(자체 기간 · 4종 제외 고정)의 공통 기간 요약.
  const { cond: todayCond, q: summary } = useEtfCompareSummary("today");
  const holdings = useSharedQuery<EnrichedHoldingsResult>(DASH_KEY_HOLDINGS, () => fetchEnrichedHoldings());
  const evidence = useSharedQuery<HoldingsMarketEvidenceResponse>(DASH_KEY_EVIDENCE, () =>
    fetchHoldingsMarketEvidence(),
  );
  const nav = useSharedQuery<NavDiscountLatestResponse>(DASH_KEY_NAV, () => fetchNavDiscountLatest());
  const series = useSharedQuery<PriceSeriesResponse>(KOSPI_SERIES_KEY, () => fetchBenchmarkSeries("KOSPI"));
  const flow = useMarketFlowContext();
  const forward = useSharedQuery<ForwardComparisonResponse>(DASH_KEY_FORWARD, () => fetchForwardComparison());
  // POC6-29 보완 — 빠른 시세 저장값(외부 조회 없음 · [최신 자료 갱신] ⓪ 이 받음) · KODEX 200 상세(저장 시각)
  const quick = useSharedQuery<QuickQuotesResponse>(QUICK_QUOTES_KEY, () => fetchQuickQuotes());
  const kodex = useSharedQuery<EtfDetailResponse>(etfDetailKey(KODEX_TICKERS), () => fetchEtfDetail(KODEX_TICKERS));
  // POC6-29 보완 2차 — 아침 요약 기준(준비 상태 · 아침 판정) · 수급 5거래일(저장값만)
  const morning = useSharedQuery<MorningBasisResponse>(MORNING_BASIS_KEY, () => fetchMorningBasis());
  const short = useSharedQuery<ShortFlowsResponse>(SHORT_FLOWS_KEY, () => fetchShortFlows());

  const refreshing = useLightRefreshState();
  const [reload, setReload] = useState<ReloadState>({ phase: "idle" });
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const [holdResult, setHoldResult] = useState<{ text: string; warn: boolean } | null>(null);
  const [quickResult, setQuickResult] = useState<{ text: string; warn: boolean } | null>(null);
  // 갱신 끝 줄 — 다시 읽은 아침 기준 그대로(현재 쓸 수 있는 기준일 · 남은 예외 · 판정서 V2 §3)
  const [basisResult, setBasisResult] = useState<{ text: string; warn: boolean } | null>(null);
  // F1 — 시장 갱신이 끝나 자료를 새로 읽으면 올라간다. 그 전에 받아 둔 [요약 다시 읽기] 결과는 반영하지 않는다(새 값을 옛 값으로 덮지 않음).
  const dataGenRef = useRef(0);
  // 시장 갱신 결과(설계자 2026-11-10) — 기준일 대조 · 갱신 뒤에도 기대일보다 늦은 자료 · ETF 가격 실패 · 그 밖의 확인 필요를 줄을 나눠 보인다.
  const [marketResult, setMarketResult] = useState<{
    compare: string | null;
    behind: string | null;
    etf: string | null;
    other: string | null;
  } | null>(null);
  // 사용자 결정 ⑤(2026-11-09) — 맨 위 두 카드(자료 최신화 필요 · OCI 운영 스케줄 확인)는 함께 펼치고 접는다(화면 안 상태 · 다시 들어오면 접힘).
  const [topOpen, setTopOpen] = useState(false);
  const toggleTop = useCallback(() => setTopOpen((v) => !v), []);
  const [copyState, setCopyState] = useState<{ message: string; fallback: string | null } | null>(null);

  const dataOf = <T,>(q: QueryState<T>): T | null => (q.phase === "success" ? q.data : null);
  const sourcesNow = (): FreshSources => ({
    market: dataOf(market),
    marketPhase: market.phase,
    flow: dataOf(flow),
    flowFailed: flow.phase === "error",
    holdings: dataOf(holdings),
    holdingsFailed: holdings.phase === "error",
    evidence: dataOf(evidence),
    evidenceFailed: evidence.phase === "error",
  });

  const reloadBasis = (extra: Promise<unknown>[] = []) =>
    Promise.allSettled([morning.reloadAsync(), short.reloadAsync(), ...extra]).then(([m]) =>
      setBasisResult(
        m.status === "fulfilled"
          ? endLine(m.value as MorningBasisResponse)
          : { text: "아침 요약 기준을 다시 읽지 못했습니다(표시 중인 값은 이전 기준)", warn: true },
      ),
    );

  // ── [최신 자료 갱신] — PC 서버 묶음 작업(보유 현재가 → 시장 자료) · 시장 단계는 기존 hook 이 따라간다(판정 Q7) ──
  const refresh = useTodayRefresh({
    // ③ 전일 자료 보충이 끝나면(② 대기 때만 돎) 바뀐 자료를 쓰는 응답을 다시 읽는다(판정 · 지표는 서버가 기존 산식으로).
    onPrevdayDone: (step) => {
      if (step.status !== "done") return;
      for (const k of MARKET_INVALIDATION_KEYS) invalidateQueries(k);
      void reloadBasis([market.reloadAsync(), flow.reloadAsync(), series.reloadAsync(), evidence.reloadAsync()]);
    },
    // ⓪ 빠른 시세 — 끝나는 대로 저장값을 먼저 다시 읽어 위 3칸에 반영(보완 PLAN 판정 Q-R2).
    onQuickDone: (step) => {
      quick
        .reloadAsync()
        .then((d) => setQuickResult(quickResultLine(step, (d as QuickQuotesResponse).items)))
        .catch(() =>
          setQuickResult({
            text: `${quickResultLine(step, dataOf(quick)?.items ?? null).text} · 다시 읽기 실패: 빠른 시세(위 3칸 = 이전에 읽은 값)`,
            warn: true,
          }),
        );
    },
    onHoldingsDone: (step) => {
      refreshing.setRunning();
      Promise.allSettled([holdings.reloadAsync(), evidence.reloadAsync(), nav.reloadAsync(), summary.reloadAsync()]).then(
        ([h, e, n, s]) => {
          // 다시 읽기가 하나라도 실패하면 '완료'로 보이지 않는다(r5 A-1 · A-1(4) 거짓 완료 금지 · 기존 계약).
          const reloadFailed = [
            h.status === "rejected" ? "보유" : null,
            e.status === "rejected" ? "보유 근거" : null,
            n.status === "rejected" ? "ETF 기준가" : null,
            s.status === "rejected" ? SUMMARY_SOURCE_LABEL : null,
          ].filter(Boolean);
          if (reloadFailed.length > 0 || h.status !== "fulfilled") {
            refreshing.setFailed();
            setHoldResult({ text: `보유 현재가 업데이트 실패 · 다시 읽기 실패: ${reloadFailed.join(" · ")}`, warn: true });
            return;
          }
          const range = priceAsofRange(h.value);
          const line = holdingsLine(step, range);
          if (step.status !== "done" || (step.ok_count ?? 0) === 0) refreshing.setFailed();
          else refreshing.setDone();
          setHoldResult(line);
        },
      );
    },
    onVixDone: () => {
      // 시장 자료 키를 지우면 이 화면의 같은 키 조회는 스스로 다시 읽지 않는다 — 지운 것을 모두 다시 읽는다(검토 지적).
      for (const k of MARKET_INVALIDATION_KEYS) invalidateQueries(k);
      void Promise.allSettled([
        market.reloadAsync(),
        flow.reloadAsync(),
        series.reloadAsync(),
        evidence.reloadAsync(),
        summary.reloadAsync(),
        morning.reloadAsync(),
      ]);
    },
    onMarketCompleted: () => {
      dataGenRef.current += 1;
      // 끝난 상태 응답(완료 직전 onStatus)의 실패 · 그 밖의 확인 필요는 바로 · 기준일 줄은 다시 읽은 뒤.
      const fails = refreshFailureLines(refresh.lastStatusRef.current);
      setMarketResult({ compare: null, behind: null, ...fails });
      // 열려 있던 확인 창의 자료는 이제 낡았다 — 닫고 알린다(받아 둔 다시 읽기 결과는 버림 · 복사는 다시 누르게).
      if (confirm?.purpose === "reload") setReload({ phase: "superseded", at: Date.now() });
      if (confirm?.purpose === "copy")
        setCopyState({ message: "시장 자료를 새로 읽어 복사를 멈췄습니다 — 다시 눌러 주세요.", fallback: null });
      if (confirm) setConfirm(null);
      // 다시 읽기 전(이 화면이 보던 값)과 다시 읽은 뒤를 자료별로 대조한다(판정 §4) — 날짜 + 저장 시각 + 값
      // (같은 거래일에 다시 받은 값을 '그대로'로 보이지 않게 · 보완 PLAN 판정 '구현에서 확인할 세 가지' 2).
      const oldMarket = dataOf(market);
      const oldFlow = dataOf(flow);
      const oldKodex = dataOf(kodex);
      const before = snapshotOf(oldMarket, oldFlow, oldKodex);
      Promise.allSettled([
        market.reloadAsync(),
        flow.reloadAsync(),
        kodex.reloadAsync(),
        series.reloadAsync(),
        evidence.reloadAsync(),
        nav.reloadAsync(),
        summary.reloadAsync(),
        reloadBasis(),
      ]).then(([m, f, k]) => {
        const newMarket = m.status === "fulfilled" ? (m.value as MarketTopNResponse) : null;
        const newFlow = f.status === "fulfilled" ? (f.value as MarketFlowContext) : null;
        const newKodex = k.status === "fulfilled" ? (k.value as EtfDetailResponse) : null;
        const after = snapshotOf(newMarket, newFlow, newKodex);
        const failed = [
          m.status === "rejected" ? "시장 판정" : null,
          f.status === "rejected" ? "수급 · 환율 · 유가" : null,
          k.status === "rejected" ? "KODEX 200 기준 가격" : null,
        ]
          .filter(Boolean)
          .join(" · ");
        // 다시 읽기에 실패한 자료는 이전 값이 남는다 — 그 기준(날짜 · 저장 시각)을 함께 적는다.
        const shown = snapshotOf(newMarket ?? oldMarket, newFlow ?? oldFlow, newKodex ?? oldKodex);
        // 다시 읽은 자료로 같은 최신성 판정(기준일 판정 그대로) — 기대일보다 늦은 자료만 한 줄로.
        const behind = staleAfterRefreshText(
          freshnessRows(
            {
              market: newMarket,
              marketPhase: newMarket ? "success" : "error",
              flow: newFlow,
              flowFailed: !newFlow,
              holdings: null,
              holdingsFailed: false,
              evidence: null,
              evidenceFailed: false,
            },
            "copy",
          ),
        );
        setMarketResult({
          compare:
            `② 시장 자료 갱신 완료 · ${compareSnapshots(before, after)}` +
            (failed ? ` · 다시 읽기 실패: ${failed}(표시 중인 값 기준: ${snapshotText(shown)})` : ""),
          behind,
          ...fails,
        });
      });
    },
  });
  const marketRefresh = refresh.marketRefresh;
  const vixRetryRunning = refresh.vixRetryRunning;
  const allBusy = refresh.all.busy;

  const onRefreshAll = useCallback(() => {
    if (allBusy || marketRefresh.busy || vixRetryRunning || confirm || reload.phase === "running") return;
    setHoldResult(null);
    setQuickResult(null);
    setMarketResult(null);
    setBasisResult(null);
    void refresh.startAll();
  }, [allBusy, marketRefresh.busy, vixRetryRunning, confirm, reload.phase, refresh]);

  // ── [요약 다시 읽기] — 받아 두기 → 최신성 대조 → (필요하면) 고르기 → 반영 · 버림 ──
  const onSummaryReload = useCallback(async () => {
    if (reload.phase === "running" || allBusy || marketRefresh.busy || confirm) return;
    setReload({ phase: "running" });
    const gen = dataGenRef.current;
    const jobs: { label: string; key: string; run: () => Promise<unknown>; q: QueryState<unknown> }[] = [
      { label: "KOSPI 가격 흐름", key: KOSPI_SERIES_KEY, run: () => fetchBenchmarkSeries("KOSPI"), q: series },
      { label: "수급 · 환율 · 유가", key: MARKET_FLOW_KEY, run: () => fetchMarketFlowContext(), q: flow },
      { label: "보유", key: DASH_KEY_HOLDINGS, run: () => fetchEnrichedHoldings(), q: holdings },
      { label: "보유 근거", key: DASH_KEY_EVIDENCE, run: () => fetchHoldingsMarketEvidence(), q: evidence },
      { label: "ETF 기준가", key: DASH_KEY_NAV, run: () => fetchNavDiscountLatest(), q: nav },
      { label: "연구", key: DASH_KEY_FORWARD, run: () => fetchForwardComparison(), q: forward },
      {
        label: SUMMARY_SOURCE_LABEL,
        key: etfCompareKey(todayCond),
        run: () => fetchEtfCompareSummary(todayCond),
        q: summary as QueryState<unknown>,
      },
      // POC6-29 보완 — 저장값만(빠른 시세 외부 조회 없음 · 보완 PLAN 판정 Q-R1)
      { label: "빠른 시세", key: QUICK_QUOTES_KEY, run: () => fetchQuickQuotes(), q: quick },
      { label: "KODEX 200 기준 가격", key: etfDetailKey(KODEX_TICKERS), run: () => fetchEtfDetail(KODEX_TICKERS), q: kodex },
      // POC6-29 보완 2차 — 저장값만(아침 요약 기준 · 수급 5거래일)
      { label: "아침 요약 기준", key: MORNING_BASIS_KEY, run: () => fetchMorningBasis(), q: morning },
      { label: "수급 5거래일", key: SHORT_FLOWS_KEY, run: () => fetchShortFlows(), q: short },
    ];
    const results = await Promise.allSettled(jobs.map((j) => j.run()));
    const at = Date.now();
    const got = <T,>(i: number): T | null =>
      results[i].status === "fulfilled"
        ? ((results[i] as PromiseFulfilledResult<unknown>).value as T)
        : (dataOf(jobs[i].q) as T | null);
    const rows = needsAttention(
      freshnessRows(
        {
          market: dataOf(market),
          marketPhase: market.phase,
          flow: got<MarketFlowContext>(1),
          flowFailed: results[1].status === "rejected",
          holdings: got<EnrichedHoldingsResult>(2),
          holdingsFailed: results[2].status === "rejected",
          evidence: got<HoldingsMarketEvidenceResponse>(3),
          evidenceFailed: results[3].status === "rejected",
        },
        "reload",
      ),
    );
    const failed: FailedSource[] = jobs.flatMap((j, i) =>
      results[i].status === "rejected"
        ? [
            {
              label: j.label,
              keptAt: j.q.phase === "success" ? readTimeText(j.q.successAt) : null,
              reason: errText((results[i] as PromiseRejectedResult).reason),
            },
          ]
        : [],
    );
    const apply = () => {
      if (gen !== dataGenRef.current) {
        // 받는 동안 시장 갱신이 끝나 자료를 새로 읽었다 — 받아 둔 결과로 새 값을 덮지 않는다.
        setReload({ phase: "superseded", at: Date.now() });
        return;
      }
      jobs.forEach((j, i) => {
        const r = results[i];
        if (r.status === "fulfilled") commitQuery(j.key, r.value, at);
        else markQueryFailed(j.key);
      });
      setReload(failed.length ? { phase: "partial", at, failed: failed.map((f) => f.label) } : { phase: "done", at });
    };
    if (rows.length === 0 && failed.length === 0) {
      apply();
      return;
    }
    // 조회는 끝났고 사용자의 선택을 기다린다(창이 열린 동안 버튼은 막힘 · 글자는 원래대로).
    setReload({ phase: "idle" });
    setConfirm({
      purpose: "reload",
      rows,
      failed,
      onContinue: () => {
        setConfirm(null);
        apply();
      },
    });
    // [취소]는 아래 onCancel — 받아 둔 결과를 버린다(공유 캐시 · 성공 시각을 건드리지 않음).
  }, [
    reload.phase,
    allBusy,
    marketRefresh.busy,
    confirm,
    market,
    flow,
    series,
    holdings,
    evidence,
    nav,
    forward,
    summary,
    todayCond,
    quick,
    kodex,
    morning,
    short,
  ]);

  const onCancelConfirm = useCallback(() => {
    const purpose = confirm?.purpose;
    setConfirm(null);
    if (purpose === "reload") setReload({ phase: "cancelled", at: Date.now() });
  }, [confirm]);

  // ── [AI용 시장 정보 복사] — 화면 값으로만 · 늦은 핵심 자료가 있으면 먼저 고르기 ──
  // 검증자 F11 — 복사 글에 쓰는 원천(시장 판정 · 시장 흐름 · 아침 기준의 응답 · 상태). 확인 창을 연 뒤 이것이 바뀌면 받아 둔
  // 글을 복사하지 않는다(창을 닫고 다시 누르게 · 시장 갱신 완료 때 닫는 기존 보호와 같은 방식).
  const copyBase = () => ({
    market: dataOf(market),
    marketPhase: market.phase,
    flow: dataOf(flow),
    flowPhase: flow.phase,
    morning: dataOf(morning),
    morningPhase: morning.phase,
    morningStale: morning.phase === "success" && morning.stale,
  });
  const copyBaseRef = useRef<ReturnType<typeof copyBase> | null>(null);
  useEffect(() => {
    if (confirm?.purpose !== "copy" || !copyBaseRef.current) return;
    const was = copyBaseRef.current;
    const now = copyBase();
    const changed = (Object.keys(now) as (keyof typeof now)[]).some((k) => was[k] !== now[k]);
    if (!changed) return;
    copyBaseRef.current = null;
    setConfirm(null);
    setCopyState({ message: "복사에 쓰는 시장 자료가 바뀌어 복사를 멈췄습니다 — 다시 눌러 주세요.", fallback: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [confirm, market, flow, morning]);

  const onCopy = useCallback(() => {
    if (confirm || reload.phase === "running" || market.phase === "loading" || flow.phase === "loading") return;
    // 설계자 V3 §3 — 시장 판정 줄 · [자료 상태]의 시장 판정 줄 · 확인 창이 화면 당일 상자 · 표와 같은 선택 결과(todayBasis)
    const verdict = todayBasis(morning, dataOf(market)?.market_context ?? null, market.phase);
    const src = { ...sourcesNow(), verdict };
    const all = freshnessRows(src, "copy");
    const text = buildTodayMarketCopyText({ market: src.market, flow: src.flow, fresh: all, verdict });
    const doCopy = () => {
      const fail = () =>
        setCopyState({ message: "복사하지 못했습니다 — 아래 글을 직접 선택해 복사하세요.", fallback: text });
      try {
        const p = navigator.clipboard?.writeText(text);
        if (!p) {
          fail();
          return;
        }
        p.then(() => setCopyState({ message: "AI용 시장 정보를 복사했습니다(고정 프롬프트 + 시장 근거).", fallback: null })).catch(
          fail,
        );
      } catch {
        fail();
      }
    };
    const rows = needsAttention(all);
    if (rows.length === 0) {
      doCopy();
      return;
    }
    copyBaseRef.current = copyBase();
    setConfirm({
      purpose: "copy",
      rows,
      failed: [],
      onContinue: () => {
        setConfirm(null);
        doCopy();
      },
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [confirm, reload.phase, market, flow, holdings, evidence, morning]);

  const onAction = useCallback(
    (a: SummaryAction) => {
      const t = a.target;
      if (t.kind === "menu") onNavigate(t.key);
      else if (t.kind === "scroll") scrollToArea(t.id);
      else if (t.kind === "market_refresh" || t.kind === "holdings_refresh") onRefreshAll();
      else void onSummaryReload();
    },
    [onNavigate, onRefreshAll, onSummaryReload],
  );

  const maintLoading =
    holdings.phase === "loading" || evidence.phase === "loading" || nav.phase === "loading" || market.phase === "loading";
  const maintenance = collectMaintenance(holdings, evidence, nav, market);
  const tasks = summaryTasks(maintenance, maintLoading, market, holdings, flow, series, forward);
  const unknownSources = [
    holdings.phase === "error" ? "보유" : null,
    market.phase === "error" ? "시장 판정" : null,
  ].filter((x): x is string => !!x);
  const dataRows = [
    dataRow(maintenance, maintLoading, tasks.length > 0, nav, evidence, unknownSources),
    researchRow(forward),
  ];
  const freshRows = needsAttention(freshnessRows(sourcesNow(), "reload"));
  const successAt = (q: { phase: string; successAt?: number }) => (q.phase === "success" ? q.successAt : undefined);
  const readRange = readRangeText([market, series, flow, holdings, evidence, nav, forward, summary].map(successAt));
  const refreshBusy = allBusy || marketRefresh.busy || vixRetryRunning;
  const blocked = reload.phase === "running" || allBusy || refreshing.state === "running" || confirm !== null;
  // 시장 갱신이 도는 동안은 다시 읽지 않는다(끝나면 갱신이 다시 읽음 · F1).
  const reloadBlocked = blocked || marketRefresh.busy;
  const mr = marketRefresh.refreshUi;
  const allStatus = refresh.all.status;
  const holdStep = allStatus?.steps.holdings ?? null;
  const quickStep = allStatus?.steps.quick ?? null;
  const startedAt = allStatus?.started_at ? ` · ${mdHm(allStatus.started_at)} 시작` : "";
  const allLine =
    refresh.all.phase === "failed"
      ? `자료 갱신 상태를 확인하지 못했습니다: ${refresh.all.error ?? "원인 미상"}`
      : allBusy && quickStep && (quickStep.status === "pending" || quickStep.status === "running")
        ? `⓪ 빠른 시세(코스피 · 코스닥 · KODEX 200) 받는 중...${startedAt}(다시 누르거나 다른 탭에서 눌러도 이 갱신을 이어서 보입니다)`
        : allBusy && (!holdStep || holdStep.status === "pending" || holdStep.status === "running")
          ? `① 보유 현재가 받는 중...${startedAt}(다시 누르거나 다른 탭에서 눌러도 이 갱신을 이어서 보입니다)`
          : null;
  const marketLine =
    vixRetryRunning && !marketRefresh.busy
      ? "VIX 다시 받기가 진행 중입니다(시장 자료 갱신은 끝난 뒤 시작할 수 있습니다) · 결과는 아래 [시장 근거와 다른 변화 보기] ①에서 볼 수 있습니다"
      : mr.kind === "starting"
        ? "② 시장 자료 갱신을 시작하는 중..."
        : mr.kind === "running"
          ? "② 시장 자료 갱신 중입니다(약 수 분 · 다른 메뉴에 다녀와도 이어서 보입니다)"
          : mr.kind === "failed"
            ? `② 시장 자료 갱신 실패: ${mr.message}`
            : mr.kind === "blocked"
              ? `② ${mr.message} 끝난 뒤 다시 누르세요`
            : mr.kind === "cooldown"
              ? `② 시장 자료는 대기 중입니다(6시간 간격) — 다음 갱신 가능 ${cooldownUntil(
                  allStatus?.steps.market?.next_available_at ?? null,
                  mr.cooldownRemainingSeconds,
                )} · 지금 표시 = ${snapshotText(snapshotOf(dataOf(market), dataOf(flow), dataOf(kodex)))}(빠른 시세 · 보유 현재가는 이 대기와 별개로 받습니다)`
              : mr.kind === "completed"
                ? (marketResult?.compare ?? "② 시장 자료 갱신 완료 · 자료를 다시 읽는 중...") +
                  (marketResult ? "" : mr.note ? ` · 일부 실패: ${mr.note}` : "")
                : null;
  const pdLine = prevdayLine(allStatus?.steps.prevday);
  // 완료 뒤 줄을 나눠 보이는 것(설계자 2026-11-10): 기대일보다 늦은 자료 · ETF 가격 실패 · 그 밖의 확인 필요.
  const marketExtra =
    mr.kind === "completed" && marketResult
      ? [
          { key: "behind", text: marketResult.behind, warn: false },
          { key: "fail", text: marketResult.etf, warn: true },
          { key: "other", text: marketResult.other, warn: true },
        ].filter((x): x is { key: string; text: string; warn: boolean } => !!x.text)
      : [];

  return (
    <div className="tc-root">
      <header className="tc-header">
        <div className="tc-title-row">
          <h1 className="tc-h1">오늘의 투자 점검</h1>
          <button type="button" className="btn-md" onClick={() => void onSummaryReload()} disabled={reloadBlocked}>
            {reload.phase === "running" ? "다시 읽는 중..." : "요약 다시 읽기"}
          </button>
          <HelpPopover label="요약 다시 읽기" paragraphs={[RELOAD_NOTE]} />
          <button
            type="button"
            className="btn-md tc-fold-btn"
            onClick={onRefreshAll}
            disabled={refreshBusy || confirm !== null || reload.phase === "running"}
          >
            {refreshBusy ? "자료 갱신 중..." : "최신 자료 갱신"}
          </button>
        </div>
        <div className="tc-readline">
          <span className="tc-muted tc-small" data-testid="tc-read-range">
            이 화면이 값을 읽은 시각 <b>{readRange}</b> · 자료 기준일은 줄마다 따로 표시합니다 · [요약 다시 읽기] = PC 저장값만 다시 읽기
          </span>
          {reload.phase === "done" || reload.phase === "partial" || reload.phase === "cancelled" || reload.phase === "superseded" ? (
            <span className={reload.phase === "partial" ? "tc-warn tc-small" : "tc-muted tc-small"} data-testid="tc-reload-state">
              {reload.phase === "done"
                ? `다시 읽기 완료 · ${readTimeText(reload.at)}`
                : reload.phase === "partial"
                  ? `다시 읽기 일부 실패(${reload.failed.join(" · ")}) · 줄마다 상태를 표시합니다 · ${readTimeText(reload.at)}`
                  : reload.phase === "superseded"
                    ? `시장 자료 갱신으로 자료를 새로 읽어, 앞서 받아 둔 다시 읽기 결과는 반영하지 않았습니다 · ${readTimeText(reload.at)}`
                    : `다시 읽기 취소 · 화면 값은 그대로입니다 · ${readTimeText(reload.at)}`}
            </span>
          ) : null}
        </div>
        {allLine ? (
          <p className={refresh.all.phase === "failed" ? "tc-warn tc-small" : "tc-muted tc-small"} data-testid="tc-all-result">
            {allLine}
          </p>
        ) : null}
        {quickResult ? (
          <p className={quickResult.warn ? "tc-warn tc-small" : "tc-muted tc-small"} data-testid="tc-quick-result">
            {quickResult.text}
          </p>
        ) : null}
        {/* 보유 현재가 결과는 잠깐만 보인다(useLightRefreshState · 2026-07-31 정정 '완료/실패 문구가 계속 남지 않게'). */}
        {holdResult && (refreshing.state === "done" || refreshing.state === "failed") ? (
          <p className={holdResult.warn ? "tc-warn tc-small" : "tc-muted tc-small"} data-testid="tc-hold-result">
            ① {holdResult.text}
          </p>
        ) : null}
        {marketLine ? (
          <div data-testid="tc-market-result">
            <p className={mr.kind === "failed" ? "tc-warn tc-small" : "tc-muted tc-small"}>{marketLine}</p>
            {marketExtra.map((x) => (
              <p key={x.key} className={x.warn ? "tc-warn tc-small" : "tc-small"} data-testid={`tc-market-${x.key}`}>
                {x.text}
              </p>
            ))}
          </div>
        ) : null}
        {pdLine ? (
          <p className={pdLine.warn ? "tc-warn tc-small" : "tc-muted tc-small"} data-testid="tc-prevday-result">
            {pdLine.text}
          </p>
        ) : null}
        {basisResult ? (
          <p className={basisResult.warn ? "tc-warn tc-small" : "tc-small"} data-testid="tc-basis-result">
            {basisResult.text}
          </p>
        ) : null}
      </header>

      {confirm ? (
        <StaleConfirmDialog
          purpose={confirm.purpose}
          rows={confirm.rows}
          failed={confirm.failed}
          onContinue={confirm.onContinue}
          onCancel={onCancelConfirm}
        />
      ) : null}

      <div className="tc-top-grid">
        <FreshnessCard
          rows={freshRows}
          tasks={tasks}
          onAction={onAction}
          busy={{ market: refreshBusy, holdings: refreshBusy || blocked, reload: reloadBlocked }}
          open={topOpen}
          onToggle={toggleTop}
        />
        <OciScheduleCard onNavigate={onNavigate} open={topOpen} onToggle={toggleTop} />
      </div>

      <SummarySection
        marketBlock={
          <MarketFlowBlock
            market={market}
            flow={flow}
            series={series}
            quick={quick}
            morning={morning}
            short={short}
            onCopy={onCopy}
            copyDisabled={confirm !== null || reload.phase === "running" || market.phase === "loading" || flow.phase === "loading"}
            copyMessage={copyState?.message ?? null}
            copyFallback={copyState?.fallback ?? null}
          />
        }
        holdingsCard={<HoldingsCheckCard market={market} summary={summary} holdings={holdings} onNavigate={onNavigate} />}
        candidatesCard={<CandidatesCheckCard summary={summary} basis={todayCond.basis} onNavigate={onNavigate} />}
        detailBlock={
          <MarketEvidenceFold
            market={market}
            flow={flow}
            morning={morning}
            short={short}
            vix={refresh.vixRetry.button}
            onVixRetry={() => void refresh.vixRetry.start()}
            vixDisabled={refresh.vixRetry.running || marketRefresh.busy || allBusy}
          />
        }
        dataRows={dataRows}
        dataFold={
          <MaintenanceQueueSection
            items={maintenance}
            loading={maintLoading}
            onNavigate={onNavigate}
            onRefresh={onRefreshAll}
            refreshBusy={refreshBusy}
          />
        }
        onAction={onAction}
      />

      <ScopeSection market={market} />
    </div>
  );
}

// 다음 갱신 가능 시각(판정 Q7) — 서버가 준 시각이 있으면 그것 · 없으면 남은 초로 계산(약 N분 뒤를 함께).
function cooldownUntil(nextAt: string | null, remainSec: number): string {
  const mins = Math.ceil(remainSec / 60);
  const at = nextAt ?? new Date(Date.now() + remainSec * 1000).toISOString();
  return `${mdHm(at)}(약 ${mins}분 뒤)`;
}

// 보유 현재가 시세 시각(네이버 체결 시각) 범위 — 'M/D HH:MM' · 같으면 하나.
function priceAsofRange(h: EnrichedHoldingsResult | null | undefined): string | null {
  const xs = (h?.items ?? [])
    .map((it) => it.price_asof)
    .filter((x): x is string => typeof x === "string" && kstDate(x) !== null)
    .sort((a, b) => new Date(a).getTime() - new Date(b).getTime());
  if (xs.length === 0) return null;
  const lo = mdHm(xs[0]);
  const hi = mdHm(xs[xs.length - 1]);
  return lo === hi ? lo : `${lo} ~ ${hi}`;
}
