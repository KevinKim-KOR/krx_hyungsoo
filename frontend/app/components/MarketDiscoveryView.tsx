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
  ApiConfigError,
  ApiRequestError,
  DEFAULT_MARKET_BASIS,
  DEFAULT_MARKET_ORDER,
  DEFAULT_MARKET_TOPN_FILTERS,
  fetchMarketRefreshStatus,
  fetchMarketTopnLatest,
  postMarketRefresh,
  type MarketBasis,
  type MarketOrder,
  type MarketRefreshStartResponse,
  type MarketRefreshStatusResponse,
  type MarketTopNFilterOptions,
  type MarketTopNResponse,
} from "@/lib/api";
import type { MenuKey } from "./LeftSidebar";
import CandidateTable from "./CandidateTable";
import MarketContextCard from "./MarketContextCard";
import TransferToAISessionsCard from "./TransferToAISessionsCard";
import TransferToETFExposureCard from "./TransferToETFExposureCard";

type LoadState =
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "ready"; data: MarketTopNResponse };

type RefreshUiState =
  | { kind: "idle" }
  | { kind: "starting" }
  | { kind: "running"; refreshId: string | null }
  | { kind: "completed"; refreshId: string | null }
  | { kind: "failed"; message: string }
  | { kind: "cooldown"; cooldownRemainingSeconds: number };

const POLL_INTERVAL_MS = 4000;
// 2026-05-22 — 운영 사고 1건 후 90 → 120 으로 상향. 1115 ETF 가격 수집이
// 약 6분 8초 (368s) 걸려 90 × 4s = 360s 상한을 8초 초과했고, 그 결과 frontend
// 가 fail 표시했지만 백엔드는 그 사이 정상 완료한 사례를 차단.
const POLL_MAX_TICKS = 120; // 8분 안전 상한

const DASH = "-";

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패(HTTP ${e.httpStatus}): ${e.message}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

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
        <li>시장 데이터 기준일: <strong>{fmt(data.asof)}</strong></li>
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
}: {
  state: RefreshUiState;
  onStart: () => void;
  disabled: boolean;
  cooldownRemainingSeconds: number;
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
            : "최신 시장 데이터 갱신"}
        </button>
      </div>
      {statusLine}
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

const DEFAULT_FILTER_UI: FilterUiState = {
  excludeInverse: DEFAULT_MARKET_TOPN_FILTERS.exclude_inverse,
  excludeLeveraged: DEFAULT_MARKET_TOPN_FILTERS.exclude_leveraged,
  excludeSynthetic: DEFAULT_MARKET_TOPN_FILTERS.exclude_synthetic,
  excludeFutures: DEFAULT_MARKET_TOPN_FILTERS.exclude_futures,
};

function toOptions(s: FilterUiState): MarketTopNFilterOptions {
  return {
    excludeInverse: s.excludeInverse,
    excludeLeveraged: s.excludeLeveraged,
    excludeSynthetic: s.excludeSynthetic,
    excludeFutures: s.excludeFutures,
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
  const [state, setState] = useState<LoadState>({ phase: "loading" });
  const [refreshUi, setRefreshUi] = useState<RefreshUiState>({ kind: "idle" });
  const [filters, setFilters] = useState<FilterUiState>(DEFAULT_FILTER_UI);
  const [basis, setBasis] = useState<MarketBasis>(DEFAULT_MARKET_BASIS);
  const [order, setOrder] = useState<MarketOrder>(DEFAULT_MARKET_ORDER);
  const pollTickRef = useRef<number>(0);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // loadTopn 은 현재 filters + basis + order state 를 캡처해서 fetch.
  // 모든 핸들러는 state 변경만 — useEffect 가 단일 fetch 트리거 (B-6 NOTE 반영).
  const loadTopn = useCallback(() => {
    setState({ phase: "loading" });
    fetchMarketTopnLatest(10, { ...toOptions(filters), basis, order })
      .then((data) => setState({ phase: "ready", data }))
      .catch((e) => setState({ phase: "error", message: describeError(e) }));
  }, [filters, basis, order]);

  useEffect(() => {
    loadTopn();
  }, [loadTopn]);

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

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current !== null) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    pollTickRef.current = 0;
  }, []);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const applyStatus = useCallback(
    (status: MarketRefreshStatusResponse) => {
      if (status.status === "running") {
        setRefreshUi({ kind: "running", refreshId: status.refresh_id ?? null });
        return;
      }
      if (status.status === "completed") {
        stopPolling();
        setRefreshUi({ kind: "completed", refreshId: status.refresh_id ?? null });
        loadTopn();
        return;
      }
      if (status.status === "failed") {
        stopPolling();
        setRefreshUi({
          kind: "failed",
          message: status.error_summary ?? "원인 미상",
        });
        return;
      }
      if (status.status === "skipped_cooldown") {
        stopPolling();
        setRefreshUi({
          kind: "cooldown",
          cooldownRemainingSeconds: status.cooldown_remaining_seconds,
        });
        return;
      }
      // idle — 폴링 종료
      stopPolling();
      setRefreshUi({ kind: "idle" });
    },
    [stopPolling, loadTopn],
  );

  const startPolling = useCallback(() => {
    stopPolling();
    pollTimerRef.current = setInterval(async () => {
      pollTickRef.current += 1;
      if (pollTickRef.current > POLL_MAX_TICKS) {
        // 2026-05-22 — 운영 사고 1건 후 polling 상한 진입 시점에 한 번 더 status
        // 명시 조회. 백엔드가 polling tick 사이의 짧은 틈에 완료했지만 frontend
        // 가 fail 표시로 가버리는 케이스 차단. applyStatus 가 completed / failed /
        // cooldown / idle 모두 처리하므로 결과를 그대로 신뢰한다.
        stopPolling();
        try {
          const finalStatus = await fetchMarketRefreshStatus();
          applyStatus(finalStatus);
          if (
            finalStatus.status === "completed" ||
            finalStatus.status === "failed" ||
            finalStatus.status === "skipped_cooldown" ||
            finalStatus.status === "idle"
          ) {
            return;
          }
        } catch {
          // 마지막 조회마저 실패하면 아래 fallback fail 표시.
        }
        setRefreshUi({
          kind: "failed",
          message: "상태 확인 시간이 너무 길어졌습니다. 잠시 후 다시 시도하세요.",
        });
        return;
      }
      try {
        const status = await fetchMarketRefreshStatus();
        applyStatus(status);
      } catch (e) {
        stopPolling();
        setRefreshUi({ kind: "failed", message: describeError(e) });
      }
    }, POLL_INTERVAL_MS);
  }, [stopPolling, applyStatus]);

  const handleStartRefresh = useCallback(async () => {
    setRefreshUi({ kind: "starting" });
    let started: MarketRefreshStartResponse;
    try {
      started = await postMarketRefresh();
    } catch (e) {
      setRefreshUi({ kind: "failed", message: describeError(e) });
      return;
    }
    if (started.status === "accepted" || started.status === "running") {
      setRefreshUi({ kind: "running", refreshId: started.refresh_id ?? null });
      startPolling();
      return;
    }
    if (started.status === "skipped_cooldown") {
      setRefreshUi({
        kind: "cooldown",
        cooldownRemainingSeconds: started.cooldown_remaining_seconds,
      });
      return;
    }
    setRefreshUi({ kind: "failed", message: started.message });
  }, [startPolling]);

  const buttonDisabled =
    refreshUi.kind === "starting" || refreshUi.kind === "running";

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
          onStart={handleStartRefresh}
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
          onStart={handleStartRefresh}
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
          onStart={handleStartRefresh}
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
          onStart={handleStartRefresh}
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
      <TopControlsRow
        refreshUi={refreshUi}
        onStartRefresh={handleStartRefresh}
        refreshDisabled={buttonDisabled}
        cooldownRemainingSeconds={cooldown}
        filters={filters}
        onFiltersChange={handleFiltersChange}
      />
      {/* 시장 배경 — 시스템 1차 시장 국면 (KODEX200 필수 / KOSPI 보조). */}
      <MarketContextCard ctx={data.market_context ?? null} />
      {/* 통합 테이블 */}
      <CandidateTable
        candidates={data.candidates ?? []}
        basis={basis}
        order={order}
        onSort={handleSort}
      />
      <SummaryHeader data={data} />
      {/* 2026-06-08 UI 정리 (사용자 요청 라운드 2) — AI Sessions 전달 / ETF
          Exposure 전달 / AI 투자세션 복사용 문구 섹션 모두 삭제.
          버튼 2개만 화면 맨 아래 한 줄로 배치 (compact 모드). */}
      {data.asof && data.filters ? (
        <div
          className="btn-row"
          style={{ gap: 12, flexWrap: "wrap", margin: "12px 0" }}
        >
          <TransferToAISessionsCard
            asof={data.asof}
            filters={data.filters}
            candidates={data.candidates ?? []}
            linkedMarketRefreshId={data.latest_refresh?.refresh_id ?? null}
            marketContext={data.market_context ?? null}
            onNavigate={onNavigate}
            compact
          />
          <TransferToETFExposureCard
            asof={data.asof}
            filters={data.filters}
            candidates={data.candidates ?? []}
            marketContext={data.market_context ?? null}
            onNavigate={onNavigate}
            compact
          />
        </div>
      ) : (
        <div className="card">
          <div className="message error">
            AI Sessions / ETF Exposure 전달 기능을 사용할 수 없습니다 — 응답에
            기준일(asof) 또는 필터 조건(filters) 이 포함되어 있지 않습니다.
          </div>
        </div>
      )}
    </section>
  );
}

// 2026-06-08 UI 정리 — 최신 시장 데이터 갱신 + 후보 정제 옵션을 한 줄로 묶는다.
// 시장배경 위쪽에 배치. 기존 별도 카드 2개 (갱신 / 필터) 는 본 컴포넌트가 흡수.
function TopControlsRow({
  refreshUi,
  onStartRefresh,
  refreshDisabled,
  cooldownRemainingSeconds,
  filters,
  onFiltersChange,
}: {
  refreshUi: RefreshUiState;
  onStartRefresh: () => void;
  refreshDisabled: boolean;
  cooldownRemainingSeconds: number;
  filters: FilterUiState;
  onFiltersChange: (next: FilterUiState) => void;
}) {
  let refreshMessage: React.ReactNode = null;
  if (refreshUi.kind === "starting" || refreshUi.kind === "running") {
    refreshMessage = (
      <span className="helper">갱신 중... ({refreshUi.kind === "running" ? (refreshUi.refreshId ?? "-") : "starting"})</span>
    );
  } else if (refreshUi.kind === "completed") {
    refreshMessage = <span className="helper">갱신 완료.</span>;
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
            : "최신 시장 데이터 갱신"}
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
    </div>
  );
}
