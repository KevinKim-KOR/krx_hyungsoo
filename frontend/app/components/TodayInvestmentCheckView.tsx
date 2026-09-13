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
//   흐름 지속 거래일 수 / 최근 고점 대비 위치 / 거래량 = 개발 중 (Q3/Q5).
// - §4.2 오늘 내가 확인할 것 (판단 큐): 요즘 잘 오르는 ETF(건수+진입) / 내가 가진 ETF
//   중 확인할 종목(개발 중). 정비 항목은 여기에 절대 넣지 않는다 (AC-4/AC-5).
// - §4.3 자료 업데이트 필요 (정비 큐): 자료 최신성/미수집/실패 + 경량 갱신(Q7:
//   저장값 재조회 + holdings/market/refresh) + 항목별 대량 갱신 화면 이동(Q8).
// - §4.4 개발 중인 판단 기능: 미구현 기능을 숨기지 않고 정직하게 표시.
//
// 데이터: 모두 기존 경로 재사용 + POC3-01 KOSPI 시계열 read 확장. 신규 산식/소스 없음.
// Dashboard 와 같은 조회 조건은 같은 캐시 키 공유(화면 왕복 재조회 방지).

import { useCallback } from "react";
import {
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
import { useSharedQuery } from "@/lib/api/queryCache";
import {
  DASH_KEY_MARKET,
  DASH_KEY_HOLDINGS,
  DASH_KEY_EVIDENCE,
  DASH_KEY_NAV,
} from "@/lib/api/dashboardKeys";
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

interface Props {
  onNavigate: (key: MenuKey) => void;
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

  // 경량 갱신 상태 (Q7: 저장값 재조회 + holdings/market/refresh 까지만).
  const refreshing = useLightRefreshState();
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

  return (
    <div className="tc-root">
      <header className="tc-header">
        <h1 className="tc-h1">오늘의 투자 점검</h1>
        {/* 부제 괄호 안내는 작은 글씨 (사용자 요청). */}
        <p className="tc-muted tc-subnote">
          코스피 현재 위치 · 오늘 내가 확인할 것 · 시스템이 처리할 자료를 한 화면에서
          구분합니다.
        </p>
        {/* POC3-07 §4.2·§5.1: 기동 시 읽은 OCI 상태를 한 줄로만 표시.
            상세는 진단·상태로. 여기서 OCI 를 재조회하지 않는다(백엔드 캐시). */}
        <OciStatusOneLine onNavigate={onNavigate} />
      </header>

      {/* §4.1: 코스피 대표 영역은 최상단 전체 폭 (사용자 요청 "가로로 제일 길게").
          코스피 헤드라인 + 상세 지표를 위에 붙이고, 그 아래 판단 큐 + 정비 큐 2열. */}
      <KospiHeadline market={market} />
      <KospiDetailSection market={market} />

      <div className="tc-queue-grid">
        <JudgmentQueueSection
          market={market}
          holdings={holdings}
          evidence={evidence}
          onNavigate={onNavigate}
        />
        <MaintenanceQueueSection
          items={maintenance}
          loading={maintLoading}
          refreshing={refreshing.state}
          onLightRefresh={onLightRefresh}
          onNavigate={onNavigate}
        />
      </div>

      <InDevelopmentSection />
    </div>
  );
}
