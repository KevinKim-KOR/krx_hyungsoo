"use client";

// POC3-01 오늘의 투자 점검 (Today Investment Check) — 새 기본 진입 화면.
//
// 설계서 목표(§2): 새 대시보드만 보고 10초 안에 코스피 현재 위치 / 사용자가 생각할 일
// / 시스템이 처리할 일을 구분한다. 개별 ETF 최종 매수·매도 판단이나 신규 위험 산식은
// 이번 Step 범위가 아니다. 코스피 가격과 KODEX200 판정은 하나로 묶지 않는다(§3.1).
//
// 2026-11-09 POC6-27(설계 · PLAN 판정 PASS_WITH_REQUIRED_CORRECTIONS · 사용자 결정 ① ② ③) — 위에서 아래로:
//   1 제목 · [요약 다시 읽기] [?] [보유 현재가 업데이트] [최신 시장 데이터 갱신] · 읽은 시각 · 결과 줄
//   2 「자료 최신화 필요」(대상 있을 때만) | 3 「OCI 운영 스케줄 확인」 — 기본 접힘 · 함께 펼치고 접음(사용자 결정 ⑤)
//   4 「지금 확인할 내용」: 시장 흐름(코스피 수치 → 차트 → 외국인 수급 → 최근 큰 변화) → 보유 점검 | 잘 오르는 ETF
//   5 보유 자세히 | 잘 오르는 ETF 자세히 · 6 자료 · 연구 상태(사용자 결정 ④ · 2026-11-09 순서 바꿈) · 7 현재 제공 범위와 남은 기능(접힘).
// 조회: 기존 8개(시장 판정 · 목록은 「요즘 잘 오르는 ETF」와 같은 탭 공유 조건 · 보유 · 보유 근거 · NAV ·
//   KOSPI 시계열 · 시장 흐름 · 연구 · OCI 기동 상태) + PC 원장 사본 종류별 마지막 실행(읽기 전용).
// [요약 다시 읽기] = 저장 자료 6개를 받아 둔 뒤 최신성을 대조하고, 늦거나 확인이 필요하면 고르게 한다
//   ([취소] = 화면 · 공유 캐시 · 성공 시각 그대로 · 판정 Q3). 시장 판정 · 목록 · OCI 는 다시 읽지 않는다.

import { useCallback, useRef, useState } from "react";
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
  refreshMarket,
  type MarketRefreshStatusResponse,
} from "@/lib/api";
import { commitQuery, markQueryFailed, useSharedQuery, type QueryState } from "@/lib/api/queryCache";
import {
  DASH_KEY_HOLDINGS,
  DASH_KEY_EVIDENCE,
  DASH_KEY_NAV,
  DASH_KEY_FORWARD,
  MARKET_FLOW_KEY,
} from "@/lib/api/dashboardKeys";
// 연구 줄 · 시장 흐름 조회는 개별 모듈에서(대시보드 시험이 `@/lib/api` 를 통째로 가짜로 바꾸는 방식과 겹치지 않게).
import { fetchForwardComparison, type ForwardComparisonResponse } from "@/lib/api/mlForwardComparison";
import { fetchMarketFlowContext, type MarketFlowContext } from "@/lib/api/marketFlow";
import { todayMarketKey, useMarketCondition } from "@/lib/marketConditionStore";
import {
  freshnessRows,
  kstDate,
  needsAttention,
  refreshFailureLines,
  staleAfterRefreshText,
  type FreshSources,
} from "@/lib/todayFreshness";
import { buildTodayMarketCopyText } from "@/lib/todayMarketCopyText";
import { md } from "@/lib/todayMarketLines";
import type { MenuKey } from "./LeftSidebar";
import HelpPopover from "./holdings_risk_evidence/HelpPopover";
import KospiDetailSection from "./today/KospiDetailSection";
import JudgmentQueueSection from "./today/JudgmentQueueSection";
import MaintenanceQueueSection from "./today/MaintenanceQueueSection";
import InDevelopmentSection from "./today/InDevelopmentSection";
import MarketFlowBlock from "./today/MarketFlowBlock";
import FreshnessCard from "./today/FreshnessCard";
import OciScheduleCard, { mdHm } from "./today/OciScheduleCard";
import StaleConfirmDialog, { type FailedSource } from "./today/StaleConfirmDialog";
import { CandidatesCheckCard, HoldingsCheckCard } from "./today/CheckCards";
import { collectMaintenance } from "./today/maintenanceQueue";
import { useLightRefreshState } from "./today/useLightRefreshState";
import { KOSPI_SERIES_KEY } from "./today/KospiChart";
import { useMarketFlowContext } from "./marketflow/useMarketFlowContext";
import SummarySection from "./today/SummarySection";
import { useMarketRefresh } from "./useMarketRefresh";
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

// 설계 §2 — [?]에 먼저 보일 문장.
export const RELOAD_NOTE =
  "저장된 값만 다시 읽습니다. 시장 판정과 요즘 잘 오르는 ETF 목록은 이 버튼으로 다시 계산하지 않습니다.";

const AREA_HOLD_DETAIL = "tc-hold-detail";
const AREA_CAND_DETAIL = "tc-cand-detail";

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

interface Props {
  onNavigate: (key: MenuKey) => void;
}

export default function TodayInvestmentCheckView({ onNavigate }: Props) {
  // POC6-27 — 목록은 「요즘 잘 오르는 ETF」와 같은 탭 공유 조건(기본 조건이면 기존 DASH_KEY_MARKET 과 같은 키).
  const cond = useMarketCondition();
  const market = useSharedQuery<MarketTopNResponse>(todayMarketKey(cond), () =>
    fetchMarketTopnLatest(10, {
      basis: cond.basis,
      order: cond.order,
      excludeInverse: cond.filters.exclude_inverse,
      excludeLeveraged: cond.filters.exclude_leveraged,
      excludeSynthetic: cond.filters.exclude_synthetic,
      excludeFutures: cond.filters.exclude_futures,
    }),
  );
  const holdings = useSharedQuery<EnrichedHoldingsResult>(DASH_KEY_HOLDINGS, () => fetchEnrichedHoldings());
  const evidence = useSharedQuery<HoldingsMarketEvidenceResponse>(DASH_KEY_EVIDENCE, () =>
    fetchHoldingsMarketEvidence(),
  );
  const nav = useSharedQuery<NavDiscountLatestResponse>(DASH_KEY_NAV, () => fetchNavDiscountLatest());
  const series = useSharedQuery<PriceSeriesResponse>(KOSPI_SERIES_KEY, () => fetchBenchmarkSeries("KOSPI"));
  const flow = useMarketFlowContext();
  const forward = useSharedQuery<ForwardComparisonResponse>(DASH_KEY_FORWARD, () => fetchForwardComparison());

  const refreshing = useLightRefreshState();
  const [reload, setReload] = useState<ReloadState>({ phase: "idle" });
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const [holdResult, setHoldResult] = useState<{ text: string; warn: boolean } | null>(null);
  // F1 — 시장 갱신이 끝나 자료를 새로 읽으면 올라간다. 그 전에 받아 둔 [요약 다시 읽기] 결과는 반영하지 않는다(새 값을 옛 값으로 덮지 않음).
  const dataGenRef = useRef(0);
  // 시장 갱신 결과(설계자 2026-11-10) — 기준일 대조 · 갱신 뒤에도 기대일보다 늦은 자료 · ETF 가격 실패 · 그 밖의 확인 필요를 줄을 나눠 보인다.
  const [marketResult, setMarketResult] = useState<{
    compare: string | null;
    behind: string | null;
    etf: string | null;
    other: string | null;
  } | null>(null);
  const lastRefreshStatusRef = useRef<MarketRefreshStatusResponse | null>(null);
  // 'VIX 다시 받기'(「요즘 잘 오르는 ETF」에서 시작)가 도는 중이면 전체 갱신은 서버가 시작하지 않는다 — 실패가 아니라 진행 중으로 보이고 버튼을 막는다.
  const [vixRetryRunning, setVixRetryRunning] = useState(false);
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

  // ── [최신 시장 데이터 갱신] — 「요즘 잘 오르는 ETF」와 같은 작업 · 진행(공용 hook · 판정 Q7) ──
  const marketRefresh = useMarketRefresh({
    probeOnMount: true,
    onStatus: (s) => {
      lastRefreshStatusRef.current = s;
      setVixRetryRunning(s.vix_retry?.status === "running");
    },
    takeOver: (started) => {
      if (started.status !== "vix_retry_running") return false;
      setVixRetryRunning(true);
      return true;
    },
    onCompleted: () => {
      dataGenRef.current += 1;
      // 끝난 상태 응답(완료 직전 onStatus)의 실패 · 그 밖의 확인 필요는 바로 · 기준일 줄은 다시 읽은 뒤.
      const fails = refreshFailureLines(lastRefreshStatusRef.current);
      setMarketResult({ compare: null, behind: null, ...fails });
      // 열려 있던 확인 창의 자료는 이제 낡았다 — 닫고 알린다(받아 둔 다시 읽기 결과는 버림 · 복사는 다시 누르게).
      if (confirm?.purpose === "reload") setReload({ phase: "superseded", at: Date.now() });
      if (confirm?.purpose === "copy")
        setCopyState({ message: "시장 자료를 새로 읽어 복사를 멈췄습니다 — 다시 눌러 주세요.", fallback: null });
      if (confirm) setConfirm(null);
      // 다시 읽기 전 기준일(이 화면이 보던 값)과 다시 읽은 뒤 기준일을 자료별로 대조한다(판정 §4).
      const before = sourceDates(dataOf(market), dataOf(flow));
      Promise.allSettled([
        market.reloadAsync(),
        flow.reloadAsync(),
        series.reloadAsync(),
        evidence.reloadAsync(),
        nav.reloadAsync(),
      ]).then(([m, f]) => {
        const newMarket = m.status === "fulfilled" ? (m.value as MarketTopNResponse) : null;
        const newFlow = f.status === "fulfilled" ? (f.value as MarketFlowContext) : null;
        const after = sourceDates(newMarket, newFlow);
        const failed = [m.status === "rejected" ? "시장 판정 · 목록" : null, f.status === "rejected" ? "수급 · 환율 · 유가" : null]
          .filter(Boolean)
          .join(" · ");
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
          compare: `시장 데이터 갱신 완료 · ${compareDates(before, after)}` + (failed ? ` · 다시 읽기 실패: ${failed}` : ""),
          behind,
          ...fails,
        });
      });
    },
  });

  // ── [보유 현재가 업데이트] — 기존 경량 갱신(POST /holdings/market/refresh → 보유 · 보유 근거 · NAV 다시 읽기) ──
  const onLightRefresh = useCallback(async () => {
    if (refreshing.state === "running" || reload.phase === "running" || confirm) return;
    refreshing.setRunning();
    setHoldResult(null);
    try {
      const r = await refreshMarket();
      const [h] = await Promise.all([holdings.reloadAsync(), evidence.reloadAsync(), nav.reloadAsync()]);
      const ok = typeof r?.ok_count === "number" ? r.ok_count : null;
      const fail = typeof r?.fail_count === "number" ? r.fail_count : 0;
      const range = priceAsofRange(h as EnrichedHoldingsResult);
      // 전건 실패는 실패 표시(경고색) · 일부 실패는 완료 표시지만 경고색(F8) · 결과 줄은 기존 규칙대로 잠깐만.
      if (ok === 0 && fail > 0) refreshing.setFailed();
      else refreshing.setDone();
      setHoldResult(
        ok === 0 && fail > 0
          ? { text: `보유 현재가를 받지 못했습니다(실패 ${fail}건)`, warn: true }
          : fail > 0
            ? { text: `보유 현재가 일부 실패 ${fail}건 · 받은 ${ok ?? "확인 불가"}건${range ? ` · 시세 시각 ${range}` : ""}`, warn: true }
            : { text: `보유 현재가 업데이트 완료${ok != null ? ` ${ok}건` : ""}${range ? ` · 시세 시각 ${range}` : ""}`, warn: false },
      );
    } catch {
      refreshing.setFailed();
      setHoldResult({ text: "보유 현재가 업데이트 실패", warn: true });
    }
  }, [refreshing, reload.phase, confirm, holdings, evidence, nav]);

  // ── [요약 다시 읽기] — 받아 두기 → 최신성 대조 → (필요하면) 고르기 → 반영 · 버림 ──
  const onSummaryReload = useCallback(async () => {
    if (reload.phase === "running" || refreshing.state === "running" || marketRefresh.busy || confirm) return;
    setReload({ phase: "running" });
    const gen = dataGenRef.current;
    const jobs: { label: string; key: string; run: () => Promise<unknown>; q: QueryState<unknown> }[] = [
      { label: "KOSPI 가격 흐름", key: KOSPI_SERIES_KEY, run: () => fetchBenchmarkSeries("KOSPI"), q: series },
      { label: "수급 · 환율 · 유가", key: MARKET_FLOW_KEY, run: () => fetchMarketFlowContext(), q: flow },
      { label: "보유", key: DASH_KEY_HOLDINGS, run: () => fetchEnrichedHoldings(), q: holdings },
      { label: "보유 근거", key: DASH_KEY_EVIDENCE, run: () => fetchHoldingsMarketEvidence(), q: evidence },
      { label: "ETF 기준가", key: DASH_KEY_NAV, run: () => fetchNavDiscountLatest(), q: nav },
      { label: "연구", key: DASH_KEY_FORWARD, run: () => fetchForwardComparison(), q: forward },
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
  }, [reload.phase, refreshing.state, marketRefresh.busy, confirm, market, flow, series, holdings, evidence, nav, forward]);

  const onCancelConfirm = useCallback(() => {
    const purpose = confirm?.purpose;
    setConfirm(null);
    if (purpose === "reload") setReload({ phase: "cancelled", at: Date.now() });
  }, [confirm]);

  // ── [AI용 시장 정보 복사] — 화면 값으로만 · 늦은 핵심 자료가 있으면 먼저 고르기 ──
  const onCopy = useCallback(() => {
    if (confirm || reload.phase === "running" || market.phase === "loading" || flow.phase === "loading") return;
    const src = sourcesNow();
    const all = freshnessRows(src, "copy");
    const text = buildTodayMarketCopyText({ market: src.market, flow: src.flow, fresh: all });
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
  }, [confirm, reload.phase, market, flow, holdings, evidence]);

  const onAction = useCallback(
    (a: SummaryAction) => {
      const t = a.target;
      if (t.kind === "menu") onNavigate(t.key);
      else if (t.kind === "scroll") scrollToArea(t.id);
      else if (t.kind === "market_refresh") void marketRefresh.start();
      else if (t.kind === "holdings_refresh") void onLightRefresh();
      else void onSummaryReload();
    },
    [onNavigate, marketRefresh, onLightRefresh, onSummaryReload],
  );

  const maintLoading =
    holdings.phase === "loading" || evidence.phase === "loading" || nav.phase === "loading" || market.phase === "loading";
  const maintenance = collectMaintenance(holdings, evidence, nav, market);
  const tasks = summaryTasks(maintenance, maintLoading, market, holdings, flow, series, forward);
  const unknownSources = [
    holdings.phase === "error" ? "보유" : null,
    market.phase === "error" ? "시장 판정 · 요즘 잘 오르는 ETF 목록" : null,
  ].filter((x): x is string => !!x);
  const dataRows = [
    dataRow(maintenance, maintLoading, tasks.length > 0, nav, evidence, unknownSources),
    researchRow(forward),
  ];
  const freshRows = needsAttention(freshnessRows(sourcesNow(), "reload"));
  const successAt = (q: { phase: string; successAt?: number }) => (q.phase === "success" ? q.successAt : undefined);
  const readRange = readRangeText([market, series, flow, holdings, evidence, nav, forward].map(successAt));
  const blocked = reload.phase === "running" || refreshing.state === "running" || confirm !== null;
  // 시장 갱신이 도는 동안은 다시 읽지 않는다(끝나면 갱신이 다시 읽음 · F1).
  const reloadBlocked = blocked || marketRefresh.busy;
  const mr = marketRefresh.refreshUi;
  const marketLine =
    vixRetryRunning && !marketRefresh.busy
      ? "VIX 다시 받기가 진행 중이라 시장 데이터 갱신을 시작하지 않았습니다 · 결과는 「요즘 잘 오르는 ETF」에서 볼 수 있습니다(끝난 뒤 이 화면에 다시 들어오면 버튼을 쓸 수 있습니다)"
      : mr.kind === "starting"
      ? "시장 데이터 갱신을 시작하는 중..."
      : mr.kind === "running"
        ? "시장 데이터 갱신 중입니다(약 수 분 · 다른 메뉴에 다녀와도 이어서 보입니다)"
        : mr.kind === "failed"
          ? `시장 데이터 갱신 실패: ${mr.message}`
          : mr.kind === "cooldown"
            ? `최근 시장 데이터가 이미 갱신되어 기존 자료를 표시합니다(재수집 가능까지 약 ${Math.ceil(
                mr.cooldownRemainingSeconds / 60,
              )}분)`
            : mr.kind === "completed"
              ? (marketResult?.compare ?? "시장 데이터 갱신 완료 · 자료를 다시 읽는 중...") +
                (marketResult ? "" : mr.note ? ` · 일부 실패: ${mr.note}` : "")
              : null;
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
            onClick={() => void onLightRefresh()}
            disabled={blocked}
          >
            {refreshing.state === "running" ? "보유 현재가 받는 중..." : "보유 현재가 업데이트"}
          </button>
          <button
            type="button"
            className="btn-md tc-fold-btn"
            onClick={() => void marketRefresh.start()}
            disabled={marketRefresh.busy || vixRetryRunning || confirm !== null}
          >
            {marketRefresh.busy ? "시장 데이터 갱신 중..." : "최신 시장 데이터 갱신"}
          </button>
        </div>
        <div className="tc-readline">
          <span className="tc-muted tc-small" data-testid="tc-read-range">
            이 화면이 값을 읽은 시각 <b>{readRange}</b> · 자료 기준일은 줄마다 따로 표시합니다
          </span>
          {reload.phase === "done" || reload.phase === "partial" || reload.phase === "cancelled" || reload.phase === "superseded" ? (
            <span className={reload.phase === "partial" ? "tc-warn tc-small" : "tc-muted tc-small"} data-testid="tc-reload-state">
              {reload.phase === "done"
                ? `다시 읽기 완료 · ${readTimeText(reload.at)}`
                : reload.phase === "partial"
                  ? `다시 읽기 일부 실패(${reload.failed.join(" · ")}) · 줄마다 상태를 표시합니다 · ${readTimeText(reload.at)}`
                  : reload.phase === "superseded"
                    ? `시장 데이터 갱신으로 자료를 새로 읽어, 앞서 받아 둔 다시 읽기 결과는 반영하지 않았습니다 · ${readTimeText(reload.at)}`
                    : `다시 읽기 취소 · 화면 값은 그대로입니다 · ${readTimeText(reload.at)}`}
            </span>
          ) : null}
        </div>
        {/* 경량 갱신 결과는 잠깐만 보인다(useLightRefreshState · 2026-07-31 정정 '완료/실패 문구가 계속 남지 않게'). */}
        {holdResult && (refreshing.state === "done" || refreshing.state === "failed") ? (
          <p className={holdResult.warn ? "tc-warn tc-small" : "tc-muted tc-small"} data-testid="tc-hold-result">
            {holdResult.text}
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
          busy={{ market: marketRefresh.busy || vixRetryRunning, holdings: blocked, reload: reloadBlocked }}
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
            onCopy={onCopy}
            copyDisabled={confirm !== null || reload.phase === "running" || market.phase === "loading" || flow.phase === "loading"}
            copyMessage={copyState?.message ?? null}
            copyFallback={copyState?.fallback ?? null}
            onNavigate={onNavigate}
          />
        }
        holdingsCard={
          <HoldingsCheckCard
            market={market}
            holdings={holdings}
            evidence={evidence}
            onNavigate={onNavigate}
            onDetail={() => scrollToArea(AREA_HOLD_DETAIL)}
          />
        }
        candidatesCard={
          <CandidatesCheckCard
            market={market}
            condition={cond}
            onNavigate={onNavigate}
            onDetail={() => scrollToArea(AREA_CAND_DETAIL)}
          />
        }
        detailBlock={
          <JudgmentQueueSection
            market={market}
            holdings={holdings}
            evidence={evidence}
            onNavigate={onNavigate}
            holdingsAreaId={AREA_HOLD_DETAIL}
            candAreaId={AREA_CAND_DETAIL}
          />
        }
        dataRows={dataRows}
        dataFold={<MaintenanceQueueSection items={maintenance} loading={maintLoading} onNavigate={onNavigate} />}
        onAction={onAction}
      />

      <ScopeSection market={market} />
    </div>
  );
}

// 시장 갱신 전후 대조에 쓰는 자료별 기준일(실제 응답의 날짜 칸 그대로).
type Dates = Record<string, string | null>;
const DATE_LABELS: [string, string][] = [
  ["kospi", "코스피"],
  ["flows", "외국인 수급"],
  ["usdkrw", "원/달러"],
  ["wti", "WTI"],
  ["vix", "VIX"],
  ["etf", "ETF 가격"],
];

function sourceDates(m: MarketTopNResponse | null, f: MarketFlowContext | null): Dates {
  const st = (k: string) => f?.status?.find((s) => s.key === k)?.E ?? null;
  return {
    kospi: m?.market_context?.kospi?.as_of_date ?? null,
    flows: st("flows"),
    usdkrw: st("usdkrw"),
    wti: st("wti"),
    vix: m?.market_risk_reference?.vix?.as_of_date ?? null,
    etf: m?.asof ?? null,
  };
}

function compareDates(before: Dates, after: Dates): string {
  return DATE_LABELS.map(([k, label]) => {
    const a = before[k];
    const b = after[k];
    if (!b) return `${label} 확인 불가`;
    return a === b ? `${label} ${md(b)} 그대로` : `${label} ${a ? md(a) : "없음"} → ${md(b)}`;
  }).join(" · ");
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
