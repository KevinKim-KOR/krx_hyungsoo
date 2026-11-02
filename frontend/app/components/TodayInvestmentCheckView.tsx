"use client";

// POC3-01 오늘의 투자 점검 (Today Investment Check) — 새 기본 진입 화면.
//
// 설계서 목표(§2): 새 대시보드만 보고 10초 안에 코스피 현재 위치 / 사용자가 생각할 일
// / 시스템이 처리할 일을 구분한다. 개별 ETF 최종 매수·매도 판단이나 신규 위험 산식은
// 이번 Step 범위가 아니다.
//
// 화면 계약:
// - §4.1 코스피는 지금 어디쯤인가: 코스피 차트(대표) + [별도 영역] 기존 시장 판정
//   (KODEX200 기준) + KODEX200 MA20/MA60 대비 거리. 두 기준을 하나로 묶어
//   "코스피 시장 상태" 라고 표기하지 않는다 (설계자 Q2/Q4 강제 분리 · FAIL 조건).
//   흐름 지속 거래일 수 · 최근 고점 대비 위치 = 실제값(POC3-06) · KODEX200 저장 거래량 = KospiHeadline
//   'KODEX200 거래량' 칸(POC5-09) · KOSPI 지수 거래량은 미저장(「코스피 상세 지표」 '미제공').
// - §4.2 오늘 내가 확인할 것 (판단 큐): 요즘 잘 오르는 ETF(건수+진입) / 내가 가진 ETF
//   중 확인할 종목(개발 중). 정비 항목은 여기에 절대 넣지 않는다 (AC-4/AC-5).
// - §4.3 자료 업데이트 필요 (정비 큐): 자료 최신성/미수집/실패 + 경량 갱신(Q7:
//   저장값 재조회 + holdings/market/refresh) + 항목별 대량 갱신 화면 이동(Q8).
// - §4.4 개발 중인 판단 기능: 미구현 기능을 숨기지 않고 정직하게 표시.
// - POC5-UI-03 정보 배치: 「코스피 상세 지표」 · 「개발 중인 판단 기능」은 화면 아래
//   「현재 제공 범위와 남은 기능」 한 묶음(기본 접힘 · 항목 · 배지 · 설명 그대로).
//
// 데이터: 모두 기존 경로 재사용 + POC3-01 KOSPI 시계열 read 확장. 신규 산식/소스 없음.
// Dashboard 와 같은 조회 조건은 같은 캐시 키 공유(화면 왕복 재조회 방지).
//
// 2026-11-02 POC6-16(설계 V1 · PLAN 판정 V1.1 · 사용자 목업 확인): 맨 위 「지금 확인할 내용」(SummarySection ·
//   「지금 할 일」 + 요약 5줄) → KOSPI 카드(전체 폭 그대로) → 보유 · 후보 자세히 | 자료 최신화 필요 → 제공 범위.
//   조회 = 기존 7개 + 연구 1개(`/ml/forward-comparison` · 공유 캐시). [요약 다시 읽기] = 저장 자료 6개만
//   강제 다시 읽기(KOSPI 시계열 · 시장 흐름 · 보유 · 보유 근거 · NAV · 연구) — 후보 목록 · 시장 판정
//   (`/market/topn/latest`) · OCI 기동 상태는 다시 읽지 않는다(판정 §2). 갱신 · 계산 명령은 부르지 않는다.

import { useCallback, useState } from "react";
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
} from "@/lib/api";
import { useSharedQuery, type QueryState } from "@/lib/api/queryCache";
import {
  DASH_KEY_MARKET,
  DASH_KEY_HOLDINGS,
  DASH_KEY_EVIDENCE,
  DASH_KEY_NAV,
  DASH_KEY_FORWARD,
} from "@/lib/api/dashboardKeys";
// 연구 줄 조회는 개별 모듈에서(대시보드 시험이 `@/lib/api` 를 통째로 가짜로 바꾸는 방식과 겹치지 않게 · 시장 흐름과 같음).
import {
  fetchForwardComparison,
  type ForwardComparisonResponse,
} from "@/lib/api/mlForwardComparison";
import type { MenuKey } from "./LeftSidebar";

// POC3-OPS-02B-2-KS10-TRIGGER-FILE-SPLIT (2026-09-13) — 907줄이 KS-10 프론트
// 임계(>900)를 넘어 화면 구역별로 `today/` 로 분리했다. 이 파일은 조회·상태·배치만
// 맡는다. default export 와 파일 경로는 그대로다 (MainPanel import 무변경).
import KospiHeadline from "./today/KospiHeadline";
import KospiDetailSection from "./today/KospiDetailSection";
import JudgmentQueueSection from "./today/JudgmentQueueSection";
import MaintenanceQueueSection from "./today/MaintenanceQueueSection";
import InDevelopmentSection from "./today/InDevelopmentSection";
import OciStatusOneLine from "./today/OciStatusOneLine";
import { collectMaintenance } from "./today/maintenanceQueue";
import { useLightRefreshState } from "./today/useLightRefreshState";
import { KOSPI_SERIES_KEY } from "./today/KospiChart";
import { useMarketFlowContext } from "./marketflow/useMarketFlowContext";
import SummarySection from "./today/SummarySection";
import {
  SCROLL_KOSPI,
  SCROLL_MAINT,
  candidatesRow,
  dataRow,
  holdingsRow,
  marketRow,
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
  | { phase: "partial"; at: number; failed: string[] };

// 같은 화면 안 이동 — 목적 구역으로 스크롤하고 그 구역에 포커스(키보드 사용 · 판정 §3).
function scrollToArea(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  el.scrollIntoView?.({ behavior: "smooth", block: "start" });
  el.focus({ preventScroll: true });
}

interface Props {
  onNavigate: (key: MenuKey) => void;
}

// POC5-UI-03 — 두 안내 구역(코스피 상세 지표 · 개발 중인 판단 기능)을 화면 아래 한 묶음으로.
// 기본 접힘 · 화면 안 상태만(저장소 · 설정 없음). 요구사항 폐기 · 기능 삭제가 아니다(설계 §4).
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

export default function TodayInvestmentCheckView({ onNavigate }: Props) {
  // Dashboard 와 같은 조회 조건 → 같은 캐시 키 공유 (화면 왕복 재조회 방지).
  const market = useSharedQuery<MarketTopNResponse>(DASH_KEY_MARKET, () =>
    fetchMarketTopnLatest(10),
  );
  const holdings = useSharedQuery<EnrichedHoldingsResult>(DASH_KEY_HOLDINGS, () =>
    fetchEnrichedHoldings(),
  );
  const evidence = useSharedQuery<HoldingsMarketEvidenceResponse>(
    DASH_KEY_EVIDENCE,
    () => fetchHoldingsMarketEvidence(),
  );
  const nav = useSharedQuery<NavDiscountLatestResponse>(DASH_KEY_NAV, () =>
    fetchNavDiscountLatest(),
  );
  // POC6-16 — 요약 줄 · [요약 다시 읽기]용. KOSPI 시계열 · 시장 흐름은 아래 카드와 같은 키(조회 1번 · 공유).
  const series = useSharedQuery<PriceSeriesResponse>(KOSPI_SERIES_KEY, () =>
    fetchBenchmarkSeries("KOSPI"),
  );
  const flow = useMarketFlowContext();
  const forward = useSharedQuery<ForwardComparisonResponse>(DASH_KEY_FORWARD, () =>
    fetchForwardComparison(),
  );

  // [요약 다시 읽기] — 저장 자료 6개를 원천별 한 번씩(판정 §2). 다 끝난 뒤 완료 / 일부 실패.
  //   실패한 원천은 공유 캐시가 이전 값과 그 시각을 남긴다(줄마다 표시) · 새로 성공한 값은 그대로 쓴다.
  // 경량 갱신 상태 (Q7: 저장값 재조회 + holdings/market/refresh 까지만).
  const refreshing = useLightRefreshState();
  const [reload, setReload] = useState<ReloadState>({ phase: "idle" });
  const onSummaryReload = useCallback(async () => {
    // 이미 도는 중이거나 [업데이트](POST 뒤 다시 읽기)가 도는 중이면 시작하지 않는다(검토 지적 4).
    if (reload.phase === "running" || refreshing.state === "running") return;
    setReload({ phase: "running" });
    const jobs: [string, () => Promise<unknown>][] = [
      ["KOSPI 가격 흐름", series.reloadAsync],
      ["수급 · 환율 · 유가", flow.reloadAsync],
      ["보유", holdings.reloadAsync],
      ["보유 근거", evidence.reloadAsync],
      ["ETF 기준가", nav.reloadAsync],
      ["연구", forward.reloadAsync],
    ];
    const results = await Promise.allSettled(jobs.map(([, run]) => run()));
    const failed = jobs.filter((_, i) => results[i].status === "rejected").map(([name]) => name);
    const at = Date.now();
    setReload(failed.length ? { phase: "partial", at, failed } : { phase: "done", at });
  }, [reload.phase, refreshing.state, series, flow, holdings, evidence, nav, forward]);

  const onSummaryAction = useCallback(
    (a: SummaryAction) => {
      if (a.target.kind === "menu") onNavigate(a.target.key);
      else if (a.target.kind === "scroll") scrollToArea(a.target.id);
      else void onSummaryReload();
    },
    [onNavigate, onSummaryReload],
  );

  const onLightRefresh = useCallback(async () => {
    refreshing.setRunning();
    try {
      await refreshMarket(); // POST /holdings/market/refresh (Q7)
      // 완료 후 light 로 분류한 자료를 실제로 모두 재조회하고 그 결과를 기다린다
      // (r5 A-1 정정). Holdings·Evidence·NAV 세 소스 reloadAsync. 하나라도 실패하면
      // catch 로 "실패" · 모두 성공해야 "완료" (거짓 완료 금지 · B-1).
      await Promise.all([
        holdings.reloadAsync(),
        evidence.reloadAsync(),
        nav.reloadAsync(),
      ]);
      refreshing.setDone();
    } catch {
      refreshing.setFailed();
    }
  }, [refreshing, holdings, evidence, nav]);

  const maintLoading =
    holdings.phase === "loading" ||
    evidence.phase === "loading" ||
    nav.phase === "loading" ||
    market.phase === "loading";
  const maintenance = collectMaintenance(holdings, evidence, nav, market);
  const tasks = summaryTasks(maintenance, maintLoading, market, holdings, flow, series, forward);
  // 정비 점검에 쓰는 원천 중 첫 조회 실패라 정비 항목에 나타나지 않는 것(빈 목록을 '갱신 필요 없음'으로 정리하지 않게)
  const unknownSources = [
    holdings.phase === "error" ? "보유" : null,
    market.phase === "error" ? "시장 판정 · 요즘 잘 오르는 ETF 목록" : null,
  ].filter((x): x is string => !!x);
  const judgeRows = [marketRow(market, flow, series), holdingsRow(holdings, evidence), candidatesRow(market)];
  const dataRows = [
    dataRow(maintenance, maintLoading, tasks.length > 0, nav, evidence, unknownSources),
    researchRow(forward),
  ];
  const successAt = (q: { phase: string; successAt?: number }) =>
    q.phase === "success" ? q.successAt : undefined;
  const readRange = readRangeText(
    [market, series, flow, holdings, evidence, nav, forward].map(successAt),
  );

  return (
    <div className="tc-root">
      <header className="tc-header">
        <h1 className="tc-h1">오늘의 투자 점검</h1>
        {/* 부제 괄호 안내는 작은 글씨 (사용자 요청). */}
        <p className="tc-muted tc-subnote">
          지금 확인할 내용을 먼저 보고, 필요한 근거 화면으로 이동합니다.
        </p>
        {/* POC6-16 — 이 화면이 값을 읽은 시각(값마다 다름) · [요약 다시 읽기](저장 자료만 · 판정 §2 · §3 · §4). */}
        <div className="tc-readline">
          <span className="tc-muted tc-small" data-testid="tc-read-range">
            이 화면이 값을 읽은 시각 <b>{readRange}</b> · 자료 기준일은 줄마다 따로 표시합니다
          </span>
          <button
            type="button"
            className="btn-md"
            onClick={() => void onSummaryReload()}
            disabled={reload.phase === "running" || refreshing.state === "running"}
          >
            {reload.phase === "running" ? "다시 읽는 중..." : "요약 다시 읽기"}
          </button>
          {reload.phase === "done" || reload.phase === "partial" ? (
            <span className={reload.phase === "partial" ? "tc-warn tc-small" : "tc-muted tc-small"} data-testid="tc-reload-state">
              {reload.phase === "done"
                ? `다시 읽기 완료 · ${readTimeText(reload.at)}`
                : `다시 읽기 일부 실패(${reload.failed.join(" · ")}) · 줄마다 상태를 표시합니다 · ${readTimeText(reload.at)}`}
            </span>
          ) : null}
        </div>
        {/* 안내 문장은 늘 보인다(다시 읽기 뒤에도 · 검토 지적 1 · 판정 §3). */}
        <p className="tc-muted tc-small" data-testid="tc-reload-note">
          저장된 값만 다시 읽습니다. 시장 판정 · 요즘 잘 오르는 ETF 목록은 다시 계산하지 않습니다. 최신 시세는 시장 자료 갱신 화면에서 받습니다.
        </p>
        {/* POC3-07 §4.2·§5.1: 기동 시 읽은 OCI 상태를 한 줄로만 표시.
            상세는 「OCI 운영·적용」으로. 여기서 OCI 를 재조회하지 않는다(백엔드 캐시). */}
        <OciStatusOneLine onNavigate={onNavigate} />
      </header>

      {/* §4.1: 코스피 대표 영역은 최상단 전체 폭 (사용자 요청 "가로로 제일 길게").
          POC5-UI-03 — 코스피 헤드라인(시장 수치와 거래량은 카드 안에서 펼침) → 판단 큐 + 정비 큐 2열
          → 맨 아래 「현재 제공 범위와 남은 기능」(코스피 상세 지표 · 개발 중인 판단 기능 묶음). */}
      {/* POC6-16 — 맨 위 「지금 확인할 내용」(판정 Q1 · KOSPI 카드는 아래 전체 폭 그대로). */}
      <SummarySection
        tasks={tasks}
        judgeRows={judgeRows}
        dataRows={dataRows}
        onAction={onSummaryAction}
        reloading={reload.phase === "running"}
      />

      <KospiHeadline market={market} areaId={SCROLL_KOSPI} />

      <div className="tc-queue-grid">
        <JudgmentQueueSection
          market={market}
          holdings={holdings}
          evidence={evidence}
          onNavigate={onNavigate}
        />
        <MaintenanceQueueSection
          areaId={SCROLL_MAINT}
          blocked={reload.phase === "running"}
          items={maintenance}
          loading={maintLoading}
          refreshing={refreshing.state}
          onLightRefresh={onLightRefresh}
          onNavigate={onNavigate}
        />
      </div>

      <ScopeSection market={market} />
    </div>
  );
}
