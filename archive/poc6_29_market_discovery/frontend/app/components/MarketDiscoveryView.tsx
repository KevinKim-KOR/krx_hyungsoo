"use client";

// PC Market Discovery — SQLite 직접 계산 기준 TOP N 표시 + 수동 refresh.
//
// 2026-05-18 변경 (Market Discovery SQLite Direct Refresh):
// - GET /market/topn/latest 응답은 이제 SQLite 직접 계산 결과 (artifact 폐기).
// - "최신 시장 데이터 갱신" 버튼 → POST /market/refresh →
//   GET /market/refresh/status polling → 완료 시 TOP N 재로드.
// - cooldown (6h) / running / failed 모두 화면에서 안내.
//
// 결측 필드는 0%로 보정하지 않고 "-" 로 표시 (지시문 §6).

import { useCallback, useEffect, useRef, useState } from "react";
import {
  type MarketBasis,
  type MarketOrder,
  type MarketRefreshStatusResponse,
  type MarketTopNResponse,
} from "@/lib/api";
import { invalidateQueries, useSharedQuery } from "@/lib/api/queryCache";
// POC6-27 — 목록 조건(기간 · 방향 · 제외)은 「오늘의 투자 점검」과 같은 탭 안에서 공유한다(판정 §4).
import { getMarketCondition, setMarketCondition } from "@/lib/marketConditionStore";
// POC6-27 — 시장 갱신 시작 · 상태 확인 · 완료 처리는 두 화면 공용 hook(판정 Q7 · 코드는 그대로 옮김).
import { describeError, useMarketRefresh, type RefreshUiState } from "./useMarketRefresh";
import {
  MARKET_INVALIDATION_KEYS,
  DASH_KEY_HOLDINGS,
} from "@/lib/api/dashboardKeys";
import type { MenuKey } from "./LeftSidebar";
import CandidateTable from "./CandidateTable";
import CandidateCards from "./CandidateCards";
import MarketBasisDefaultRow, { useMarketBasisDefault } from "./MarketBasisDefaultRow";
import {
  fetchEnrichedHoldings,
  type EnrichedHoldingsResult,
} from "@/lib/api";
import { heldTickerSet } from "./workbench/helpers";
import MarketContextCard from "./MarketContextCard";
import MarketRiskReferenceCard from "./MarketRiskReferenceCard";
import MarketFlowCard from "./marketflow/MarketFlowCard";
import HoldingsCompareView from "./HoldingsCompareView";
// 2026-08-01 승인·알림 역할 분리 C구간 — 신규 ETF 관찰 후보 갱신을 이 화면으로 이동.
import UniverseRefreshPanel from "./UniverseRefreshPanel";

// 2026-06-21 보유와 비교 보기 모드 (지시문 §4.1) — 탭 토글.
// 2026-08-16 사용자 지시 — 후보를 카드(기본)/표 두 보기로 나눈다.
//   기존 "default"(표) → "card"(기본) + "table" 로 분리.
type CompareViewMode = "card" | "table" | "holdings_compare";
import TransferToAISessionsCard from "./TransferToAISessionsCard";
import { useMarketVixRetry, type VixButton } from "./useMarketVixRetry";
import { useMarketTopnLoad } from "./useMarketTopnLoad";
import TransferToETFExposureCard from "./TransferToETFExposureCard";

const DASH = "-";

function fmt(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return DASH;
  return value;
}

function fmtNum(value: number | null | undefined): string {
  if (value === null || value === undefined) return DASH;
  return String(value);
}

function fmtCooldown(seconds: number): string {
  if (seconds <= 0) return "0";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}시간 ${m}분`;
  return `${m}분`;
}

// 2026-06-08 — SortStatusLine 제거 (사용자 요청: 정렬 기준 안내 문구 삭제).

function SummaryHeader({ data }: { data: MarketTopNResponse }) {
  return (
    <div className="card">
      <h2>요약</h2>
      <ul className="dashboard-status-list">
        <li>
          데이터 기준: <strong>SQLite 단일 SSOT</strong> (state/market/market_data.sqlite)
        </li>
        <li>시장 저장 최신일: <strong>{fmt(data.asof)}</strong> (저장된 전체 종목 가격 중 가장 늦은 저장일)</li>
        <li>데이터 소스: <strong>{fmt(data.source)}</strong></li>
        <li>Universe: <strong>{fmtNum(data.universe_count)}</strong>개</li>
        <li>가격 수집 성공: <strong>{fmtNum(data.price_success_count)}</strong>개</li>
        <li>가격 수집 실패: <strong>{fmtNum(data.price_fail_count)}</strong>개</li>
        <li>기본 N: <strong>{fmtNum(data.n)}</strong> (query parameter `n` 으로 변경 가능)</li>
        {data.latest_refresh ? (
          <li>
            마지막 refresh: <strong>{fmt(data.latest_refresh.created_at)}</strong>
            {data.latest_refresh.refresh_id ? ` (${data.latest_refresh.refresh_id})` : ""}
          </li>
        ) : null}
      </ul>
      {data.topn_caveat ? (
        <div className="helper" style={{ marginTop: 8 }}>
          {data.topn_caveat}
        </div>
      ) : null}
      <span className="helper" style={{ marginTop: 8, display: "block" }}>
        NAV / 괴리율은 Naver ETF universe(`etfItemList.nhn`) 1회 호출 결과를
        SQLite `etf_nav_daily` 에 저장한 값입니다. 후보 ETF 행에서 표시되며,
        unavailable 인 종목은 Naver 응답에서 누락된 것입니다 (매수·매도 판단 아님).
      </span>
    </div>
  );
}

function RefreshControlCard({
  state,
  onStart,
  disabled,
  cooldownRemainingSeconds,
  vix,
}: {
  state: RefreshUiState;
  onStart: () => void;
  disabled: boolean;
  cooldownRemainingSeconds: number;
  vix: VixButton;
}) {
  let statusLine: React.ReactNode = null;
  switch (state.kind) {
    case "idle":
      statusLine = (
        <div className="helper">
          시장 데이터를 즉시 갱신할 수 있습니다 (FDR → SQLite upsert).
        </div>
      );
      break;
    case "starting":
      statusLine = <div className="message info">갱신을 시작하는 중...</div>;
      break;
    case "running":
      statusLine = (
        <div className="message info">
          갱신 중입니다. 약 수 분이 소요됩니다 ({state.refreshId ?? "-"}).
        </div>
      );
      break;
    case "completed":
      statusLine = (
        <div className="message info">
          갱신 완료. 최신 SQLite 기준으로 TOP N 을 재로드했습니다.
          {state.note ? ` 확인 필요: ${state.note}` : ""}
        </div>
      );
      break;
    case "failed":
      statusLine = <div className="message error">갱신 실패: {state.message}</div>;
      break;
    case "cooldown":
      statusLine = (
        <div className="message info">
          최근 시장 데이터가 이미 갱신되어 기존 데이터를 표시합니다 (재수집 가능까지{" "}
          {fmtCooldown(state.cooldownRemainingSeconds)}).
        </div>
      );
      break;
  }
  return (
    <div className="card">
      <h2>최신 시장 데이터 갱신</h2>
      <div className="btn-row">
        <button type="button" onClick={onStart} disabled={disabled}>
          {state.kind === "running" || state.kind === "starting"
            ? "갱신 중..."
            : (vix.label ?? "최신 시장 데이터 갱신")}
        </button>
      </div>
      {vix.line ? (
        <div className={vix.line.error ? "message error" : "message info"}>
          {vix.line.text}
        </div>
      ) : (
        statusLine
      )}
      {cooldownRemainingSeconds > 0 && state.kind !== "cooldown" ? (
        <div className="helper" style={{ marginTop: 4 }}>
          (cooldown {fmtCooldown(cooldownRemainingSeconds)} 남음 — 그 사이 클릭은
          무시되고 기존 데이터를 그대로 표시합니다.)
        </div>
      ) : null}
    </div>
  );
}

interface FilterUiState {
  excludeInverse: boolean;
  excludeLeveraged: boolean;
  excludeSynthetic: boolean;
  excludeFutures: boolean;
}

// POC6-27 — 첫 조건은 탭 공유 저장소에서(탭을 처음 열면 저장 기본 기간 · 기본 방향 · 기본 제외 4종).
function sharedFilterUi(): FilterUiState {
  const f = getMarketCondition().filters;
  return {
    excludeInverse: f.exclude_inverse,
    excludeLeveraged: f.exclude_leveraged,
    excludeSynthetic: f.exclude_synthetic,
    excludeFutures: f.exclude_futures,
  };
}

// 2026-06-08 — FilterCard 제거 (사용자 요청: 후보 정제 옵션 별도 카드 삭제,
// TopControlsRow 가 갱신 버튼 옆에 체크박스를 함께 배치).


// 2026-06-08 — CopyTextCard 제거 (사용자 요청 라운드 2: AI 투자세션 복사용 문구
// 섹션 삭제). AI Sessions 화면에서 별도 입력문 생성 흐름 유지.


interface MarketDiscoveryViewProps {
  // 2026-05-21 — "AI Sessions로 넘기기" 클릭 시 호출 (MainPanel 이 setActive 전달).
  onNavigate?: (key: MenuKey) => void;
}


export default function MarketDiscoveryView({
  onNavigate,
}: MarketDiscoveryViewProps = {}) {
  const [filters, setFilters] = useState<FilterUiState>(sharedFilterUi);
  // POC5-26 — 기본 조회 기준(이 브라우저 저장)을 상태 초기값에서 한 번 읽는다 → 첫 조회부터 그 기준.
  // POC6-27 — 같은 탭에서 이미 고른 조건이 있으면 그 조건(공유 저장소 · 처음이면 저장 기본 기간과 같음).
  const basisDefault = useMarketBasisDefault();
  const [basis, setBasis] = useState<MarketBasis>(() => getMarketCondition().basis);
  const [order, setOrder] = useState<MarketOrder>(() => getMarketCondition().order);
  useEffect(() => {
    setMarketCondition({
      basis,
      order,
      filters: {
        exclude_inverse: filters.excludeInverse,
        exclude_leveraged: filters.excludeLeveraged,
        exclude_synthetic: filters.excludeSynthetic,
        exclude_futures: filters.excludeFutures,
      },
    });
  }, [basis, order, filters]);
  // POC5-12 — 시장 TOP N 조회 · 순번 · 받은 화면 유지 · 최신 입력으로 다시 읽기(hook).
  const { state, reloadError, reloadLatest } = useMarketTopnLoad(filters, basis, order, describeError);
  // 2026-08-16 — RelativeUpsideRunCard 를 ML 실험 메뉴로 옮기면서 이 화면이 들고 있던
  // 결과·오류 상태(lift state up)도 함께 제거했다. 카드가 없으므로 참조도 없다.
  // 2026-06-21 보유와 비교 보기 모드 (지시문 §4.1).
  const [compareViewMode, setCompareViewMode] =
    useState<CompareViewMode>("card");
  // 후보 카드의 "보유 여부" 배지용. Dashboard·Workbench 와 같은 캐시 키를 쓰므로
  // 이미 조회됐으면 재호출하지 않는다. 실패/미완이면 집합이 undefined → 3-state
  // 의 "확인 불가"(미보유로 축약하지 않음).
  const holdingsQ = useSharedQuery<EnrichedHoldingsResult>(
    DASH_KEY_HOLDINGS,
    () => fetchEnrichedHoldings(),
  );
  const heldTickers =
    holdingsQ.phase === "success"
      ? heldTickerSet(holdingsQ.data.items)
      : undefined;
  const [selectedCandidate, setSelectedCandidate] = useState<string | null>(null);

  const handleFiltersChange = useCallback((next: FilterUiState) => {
    setFilters(next);
  }, []);

  // 컬럼 클릭 정렬 (지시문 §4.3) — API 재호출 기반, 프론트 로컬 정렬 금지.
  // - 같은 컬럼 재클릭: order asc/desc 전환
  // - 다른 컬럼 클릭: basis 변경 + order=desc 리셋
  const handleSort = useCallback(
    (column: MarketBasis) => {
      if (column === basis) {
        setOrder((prev) => (prev === "desc" ? "asc" : "desc"));
      } else {
        setBasis(column);
        setOrder("desc");
      }
    },
    [basis],
  );

  // POC6-27 — VIX 다시 받기 hook 과 갱신 hook 이 서로의 상태를 쓴다(받은 상태 · 넘겨받기는 ref 로 잇는다).
  const vixSinkRef = useRef<{
    absorb: (st: MarketRefreshStatusResponse) => void;
    takeOver: ReturnType<typeof useMarketVixRetry>["takeOver"];
  } | null>(null);
  const { refreshUi, start: handleStartRefresh } = useMarketRefresh({
    onCompleted: reloadLatest,
    onStatus: (st) => vixSinkRef.current?.absorb(st),
    takeOver: (started) => vixSinkRef.current?.takeOver(started) ?? false,
  });

  const vixRetry = useMarketVixRetry({
    fullRefreshBusy: refreshUi.kind === "starting" || refreshUi.kind === "running",
    onRetrySucceeded: () => {
      for (const k of MARKET_INVALIDATION_KEYS) invalidateQueries(k);
      reloadLatest();
    },
  });
  vixSinkRef.current = { absorb: vixRetry.absorbStatus, takeOver: vixRetry.takeOver };

  const buttonDisabled =
    refreshUi.kind === "starting" ||
    refreshUi.kind === "running" ||
    vixRetry.running;
  const onStartButton = vixRetry.vixMode ? vixRetry.start : handleStartRefresh;

  const roleBanner = (
    <div className="role-banner">
      <strong>[판단 흐름 STEP 1–2]</strong> 시장 데이터를 갱신하고 수익률 기반
      ETF 후보를 확인합니다. 후보 확인 후 구성종목 중복 분석(ETF Exposure)이나
      AI 투자세션 문구 복사로 이어갑니다.
    </div>
  );

  if (state.phase === "loading") {
    return (
      <section aria-labelledby="market-discovery-h">
        <h1 id="market-discovery-h">Market Discovery</h1>
        {roleBanner}
        <div className="card">
          <div className="message info">불러오는 중...</div>
        </div>
      </section>
    );
  }

  if (state.phase === "error") {
    return (
      <section aria-labelledby="market-discovery-h">
        <h1 id="market-discovery-h">Market Discovery</h1>
        {roleBanner}
        <RefreshControlCard
          state={refreshUi}
          onStart={onStartButton}
          vix={vixRetry.button}
          disabled={buttonDisabled}
          cooldownRemainingSeconds={0}
        />
        <div className="card">
          <div className="message error">{state.message}</div>
        </div>
      </section>
    );
  }

  const { data } = state;
  const cooldown =
    data.latest_refresh && refreshUi.kind === "cooldown"
      ? refreshUi.cooldownRemainingSeconds
      : 0;

  // status별 분기 — 표시 정책 (지시문 §7).
  if (data.status === "missing") {
    return (
      <section aria-labelledby="market-discovery-h">
        <h1 id="market-discovery-h">Market Discovery</h1>
        <p className="subtitle">
          이 화면은 SQLite 에 저장된 시장 데이터 기준입니다.
        </p>
        {roleBanner}
        <RefreshControlCard
          state={refreshUi}
          onStart={onStartButton}
          vix={vixRetry.button}
          disabled={buttonDisabled}
          cooldownRemainingSeconds={cooldown}
        />
        <div className="card placeholder-card">
          <h2>시장 데이터가 아직 없습니다</h2>
          <p>최신 시장 데이터 갱신을 실행하세요.</p>
        </div>
      </section>
    );
  }

  if (data.status === "empty") {
    return (
      <section aria-labelledby="market-discovery-h">
        <h1 id="market-discovery-h">Market Discovery</h1>
        <p className="subtitle">
          이 화면은 SQLite 에 저장된 시장 데이터 기준입니다.
        </p>
        {roleBanner}
        <RefreshControlCard
          state={refreshUi}
          onStart={onStartButton}
          vix={vixRetry.button}
          disabled={buttonDisabled}
          cooldownRemainingSeconds={cooldown}
        />
        <div className="card placeholder-card">
          <h2>가격 데이터가 부족합니다</h2>
          <p>{data.error ?? "etf_daily_price 테이블에 가격 시계열이 없습니다."}</p>
          <p className="helper">최신 시장 데이터 갱신을 실행하세요.</p>
        </div>
      </section>
    );
  }

  if (data.status === "invalid") {
    return (
      <section aria-labelledby="market-discovery-h">
        <h1 id="market-discovery-h">Market Discovery</h1>
        <p className="subtitle">
          이 화면은 SQLite 에 저장된 시장 데이터 기준입니다.
        </p>
        {roleBanner}
        <RefreshControlCard
          state={refreshUi}
          onStart={onStartButton}
          vix={vixRetry.button}
          disabled={buttonDisabled}
          cooldownRemainingSeconds={cooldown}
        />
        <div className="card">
          <div className="message error">
            SQLite 시장 데이터를 읽을 수 없습니다. 데이터 파일 상태를 확인하세요.
          </div>
          {data.error ? (
            <div className="helper" style={{ marginTop: 8 }}>
              사유: {data.error}
            </div>
          ) : null}
        </div>
      </section>
    );
  }

  return (
    <section aria-labelledby="market-discovery-h">
      <h1 id="market-discovery-h">Market Discovery</h1>
      {/* 2026-06-08 UI 정리 (사용자 요청) — subtitle / role banner / 정렬 기준 안내 문구 제거.
          최상단: 시장 데이터 갱신 + 후보 정제 옵션 (한 줄). 그 아래 시장 배경 / 그리드. */}
      {/* 2026-06-08 UI 정리 라운드 4 (사용자 요청) — TopControlsRow 카드 안에서
          최신 시장 데이터 갱신 + 필터 (1행) / AI Sessions·ETF Exposure 버튼 (2행)
          을 모두 같은 카드 안에 묶어서 표시. 별도 카드 분리 X. */}
      {reloadError ? (
        <div className="message error">
          시장 자료를 다시 불러오지 못해 이전에 받은 자료(기준일 {fmt(data.asof)})를
          표시합니다: {reloadError}
        </div>
      ) : null}
      <TopControlsRow
        refreshUi={refreshUi}
        onStartRefresh={onStartButton}
        vix={vixRetry.button}
        refreshDisabled={buttonDisabled}
        cooldownRemainingSeconds={cooldown}
        filters={filters}
        onFiltersChange={handleFiltersChange}
        transferAvailable={Boolean(data.asof && data.filters)}
        transferAISessions={
          data.asof && data.filters ? (
            <TransferToAISessionsCard
              asof={data.asof}
              filters={data.filters}
              candidates={data.candidates ?? []}
              linkedMarketRefreshId={data.latest_refresh?.refresh_id ?? null}
              marketContext={data.market_context ?? null}
              onNavigate={onNavigate}
              compact
            />
          ) : null
        }
        transferETFExposure={
          data.asof && data.filters ? (
            <TransferToETFExposureCard
              asof={data.asof}
              filters={data.filters}
              candidates={data.candidates ?? []}
              marketContext={data.market_context ?? null}
              onNavigate={onNavigate}
              compact
            />
          ) : null
        }
      />
      {/* 2026-08-01 승인·알림 역할 분리 C구간 — 신규 ETF 관찰 후보 갱신을 여기로 이동.
          위 "최신 시장 데이터 갱신"(TopControlsRow)은 시세·시장 데이터 최신화이고,
          아래 "신규 ETF 관찰 후보"는 수집된 데이터로 관찰 후보를 재계산한다 —
          두 갱신은 다른 기능이며 합치지 않는다 (Q6). 이 화면에 정확히 1회만 둔다. */}
      <UniverseRefreshPanel />
      {/* 시장 배경 — 시스템 1차 시장 국면 (KODEX200 필수 / KOSPI 보조). */}
      <MarketContextCard ctx={data.market_context ?? null} />
      {/* 2026-07-03 Market Risk Reference v1 — KODEX200 + VIX 일별 맥락. */}
      <MarketRiskReferenceCard reference={data.market_risk_reference ?? null} />
      {/* POC6-01 — 시장 흐름(수급 · 환율 · 유가 · 기간 요약 · 최근 큰 변화 · 같은 날짜 축 차트 · 해석). */}
      <MarketFlowCard />
      {/* 2026-06-21 ML 축1 — 상대상승 참고점수 계산 실행 카드. 성공 시
          loadTopn() 으로 후보 표 재조회 (지시문 — 성공 후 후보 목록 갱신).
          result / errorMessage 는 부모가 보유 — 카드 unmount/remount 와 무관하게
          결과 유지 (2026-06-21 운영 회귀 수정). */}
      {/* 2026-06-21 보유와 비교 보기 모드 (지시문 §4.1) — 상단 탭 토글. */}
      <CompareViewTabs
        mode={compareViewMode}
        onChange={setCompareViewMode}
      />
      {compareViewMode === "card" ? (
        <>
          {/* 기본 보기 — 카드 (2026-08-16). 표 보기는 옆 탭에 그대로 남는다. */}
          <div className="card market-topn-card">
            <MarketBasisDefaultRow current={basis} pref={basisDefault} />
            <CandidateCards
              candidates={data.candidates ?? []}
              heldTickers={heldTickers}
              selected={selectedCandidate}
              onSelect={setSelectedCandidate}
              basis={basis}
              marketAsof={data.asof}
            />
          </div>
          <SummaryHeader data={data} />
        </>
      ) : compareViewMode === "table" ? (
        <>
          {/* 통합 테이블 (기존) */}
          <CandidateTable
            top={<MarketBasisDefaultRow current={basis} pref={basisDefault} />}
            candidates={data.candidates ?? []}
            basis={basis}
            order={order}
            onSort={handleSort}
            marketAsof={data.asof}
          />
          <SummaryHeader data={data} />
        </>
      ) : (
        <HoldingsCompareView data={data} onNavigate={onNavigate} />
      )}
    </section>
  );
}

// 2026-06-21 보유와 비교 보기 모드 (지시문 §4.1) — 상단 탭 토글.
function CompareViewTabs({
  mode,
  onChange,
}: {
  mode: CompareViewMode;
  onChange: (m: CompareViewMode) => void;
}) {
  const tabStyle = (active: boolean): React.CSSProperties => ({
    padding: "8px 16px",
    border: "none",
    borderBottom: active ? "2px solid #0284c7" : "2px solid transparent",
    backgroundColor: "transparent",
    color: active ? "#0284c7" : "var(--muted)",
    fontWeight: active ? "bold" : "normal",
    cursor: "pointer",
  });
  return (
    <div
      role="tablist"
      style={{
        display: "flex",
        gap: 0,
        borderBottom: "1px solid var(--border)",
        marginTop: 12,
        marginBottom: 12,
      }}
    >
      <button
        role="tab"
        type="button"
        aria-selected={mode === "card"}
        onClick={() => onChange("card")}
        style={tabStyle(mode === "card")}
      >
        카드
      </button>
      <button
        role="tab"
        type="button"
        aria-selected={mode === "table"}
        onClick={() => onChange("table")}
        style={tabStyle(mode === "table")}
      >
        표
      </button>
      <button
        role="tab"
        type="button"
        aria-selected={mode === "holdings_compare"}
        onClick={() => onChange("holdings_compare")}
        style={tabStyle(mode === "holdings_compare")}
      >
        보유와 비교
      </button>
    </div>
  );
}

// 2026-06-08 UI 정리 — 최신 시장 데이터 갱신 + 후보 정제 옵션 + AI Sessions /
// ETF Exposure 버튼을 모두 같은 카드 안에 묶는다 (사용자 요청 라운드 4).
// 1행: 갱신 버튼 + 필터 체크박스 4개
// 2행: AI Sessions로 넘기기 / ETF Exposure 로 넘기기 버튼 2개 (또는 안내)
function TopControlsRow({
  refreshUi,
  onStartRefresh,
  vix,
  refreshDisabled,
  cooldownRemainingSeconds,
  filters,
  onFiltersChange,
  transferAvailable,
  transferAISessions,
  transferETFExposure,
}: {
  refreshUi: RefreshUiState;
  onStartRefresh: () => void;
  vix: VixButton;
  refreshDisabled: boolean;
  cooldownRemainingSeconds: number;
  filters: FilterUiState;
  onFiltersChange: (next: FilterUiState) => void;
  transferAvailable: boolean;
  transferAISessions: React.ReactNode;
  transferETFExposure: React.ReactNode;
}) {
  let refreshMessage: React.ReactNode = null;
  if (vix.line) {
    refreshMessage = (
      <span className="helper" style={vix.line.error ? { color: "var(--danger)" } : undefined}>
        {vix.line.text}
      </span>
    );
  } else if (refreshUi.kind === "starting" || refreshUi.kind === "running") {
    refreshMessage = (
      <span className="helper">갱신 중... ({refreshUi.kind === "running" ? (refreshUi.refreshId ?? "-") : "starting"})</span>
    );
  } else if (refreshUi.kind === "completed") {
    refreshMessage = (
      <span className="helper">
        갱신 완료.{refreshUi.note ? ` 확인 필요: ${refreshUi.note}` : ""}
      </span>
    );
  } else if (refreshUi.kind === "failed") {
    refreshMessage = <span className="helper" style={{ color: "var(--danger)" }}>실패: {refreshUi.message}</span>;
  } else if (refreshUi.kind === "cooldown") {
    refreshMessage = (
      <span className="helper">
        cooldown 중 ({fmtCooldown(refreshUi.cooldownRemainingSeconds)} 남음)
      </span>
    );
  } else if (cooldownRemainingSeconds > 0) {
    refreshMessage = (
      <span className="helper">
        (cooldown {fmtCooldown(cooldownRemainingSeconds)} 남음)
      </span>
    );
  }
  return (
    <div className="card">
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
          alignItems: "center",
        }}
      >
        <button type="button" onClick={onStartRefresh} disabled={refreshDisabled}>
          {refreshUi.kind === "running" || refreshUi.kind === "starting"
            ? "갱신 중..."
            : (vix.label ?? "최신 시장 데이터 갱신")}
        </button>
        <div
          className="market-topn-filter-row"
          style={{ display: "flex", gap: 12, flexWrap: "wrap" }}
        >
          <label>
            <input
              type="checkbox"
              checked={filters.excludeInverse}
              onChange={(e) =>
                onFiltersChange({ ...filters, excludeInverse: e.target.checked })
              }
            />{" "}
            인버스 제외
          </label>
          <label>
            <input
              type="checkbox"
              checked={filters.excludeLeveraged}
              onChange={(e) =>
                onFiltersChange({ ...filters, excludeLeveraged: e.target.checked })
              }
            />{" "}
            레버리지 제외
          </label>
          <label>
            <input
              type="checkbox"
              checked={filters.excludeSynthetic}
              onChange={(e) =>
                onFiltersChange({ ...filters, excludeSynthetic: e.target.checked })
              }
            />{" "}
            합성 제외
          </label>
          <label>
            <input
              type="checkbox"
              checked={filters.excludeFutures}
              onChange={(e) =>
                onFiltersChange({ ...filters, excludeFutures: e.target.checked })
              }
            />{" "}
            선물형 제외
          </label>
        </div>
        {refreshMessage}
      </div>
      {/* 2행 — AI Sessions / ETF Exposure 전달 버튼 */}
      <div
        className="btn-row"
        style={{
          display: "flex",
          gap: 12,
          flexWrap: "wrap",
          marginTop: 12,
        }}
      >
        {transferAvailable ? (
          <>
            {transferAISessions}
            {transferETFExposure}
          </>
        ) : (
          <span className="helper" style={{ color: "var(--danger)" }}>
            AI Sessions / ETF Exposure 전달 기능을 사용할 수 없습니다 —
            응답에 기준일(asof) 또는 필터 조건(filters) 이 포함되어 있지 않습니다.
          </span>
        )}
      </div>
    </div>
  );
}
