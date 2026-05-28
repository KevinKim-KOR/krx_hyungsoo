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
  MARKET_BASIS_COLUMN_LABEL,
  fetchMarketRefreshStatus,
  fetchMarketTopnLatest,
  postMarketRefresh,
  type MarketBasis,
  type MarketCandidate,
  type MarketContext,
  type MarketOrder,
  type MarketRefreshStartResponse,
  type MarketRefreshStatusResponse,
  type MarketTopNFilterOptions,
  type MarketTopNFilters,
  type MarketTopNResponse,
} from "@/lib/api";
import { buildMarketDiscoveryCopyText } from "@/lib/marketDiscoveryCopyText";
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

function SortStatusLine({ basis, order }: { basis: MarketBasis; order: MarketOrder }) {
  const dir = order === "desc" ? "↓ 내림차순" : "↑ 오름차순";
  return (
    <div className="market-topn-sort-status helper">
      정렬 기준: <strong>{MARKET_BASIS_COLUMN_LABEL[basis]}</strong> {dir}
    </div>
  );
}

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

function FilterCard({
  filters,
  onChange,
}: {
  filters: FilterUiState;
  onChange: (next: FilterUiState) => void;
}) {
  return (
    <div className="card">
      <h2>후보 정제 옵션</h2>
      <p className="helper" style={{ marginBottom: 8 }}>
        기본 화면은 일반 후보 (인버스 / 레버리지 / 합성 / 선물형 제외) 만 표시합니다.
        체크박스를 해제하면 해당 유형이 다시 포함됩니다.
      </p>
      <div className="market-topn-filter-row">
        <label>
          <input
            type="checkbox"
            checked={filters.excludeInverse}
            onChange={(e) =>
              onChange({ ...filters, excludeInverse: e.target.checked })
            }
          />{" "}
          인버스 제외
        </label>
        <label>
          <input
            type="checkbox"
            checked={filters.excludeLeveraged}
            onChange={(e) =>
              onChange({ ...filters, excludeLeveraged: e.target.checked })
            }
          />{" "}
          레버리지 제외
        </label>
        <label>
          <input
            type="checkbox"
            checked={filters.excludeSynthetic}
            onChange={(e) =>
              onChange({ ...filters, excludeSynthetic: e.target.checked })
            }
          />{" "}
          합성 제외
        </label>
        <label>
          <input
            type="checkbox"
            checked={filters.excludeFutures}
            onChange={(e) =>
              onChange({ ...filters, excludeFutures: e.target.checked })
            }
          />{" "}
          선물형 제외
        </label>
      </div>
    </div>
  );
}


// AI 투자세션 복사용 문구 (2026-05-19 STEP).
// - 새 API 호출 없음. 이미 조회된 data.asof / data.filters / data.candidates 로 빌드.
// - AI 직접 호출 / 자동 토론 없음 — 외부 AI 채널에 사용자가 직접 붙여넣는 1차 입력문.
// - 클립보드 복사 실패에 대비해 textarea 를 항상 유지 (지시문 §3.1 + AC-10).
// - asof / filters 는 호출자가 status==='ok' 분기에서만 truthy 보장하고 prop 으로
//   넘긴다 (fail-loud — 검증자 B-1 NOTE 반영, placeholder fallback 금지).
function CopyTextCard({
  asof,
  filters,
  candidates,
  marketContext,
}: {
  asof: string;
  filters: MarketTopNFilters;
  candidates: MarketCandidate[];
  marketContext: MarketContext | null;
}) {
  const [text, setText] = useState<string>("");
  const [copyResult, setCopyResult] = useState<"idle" | "copied" | "failed">(
    "idle",
  );

  const handleGenerate = useCallback(() => {
    setText(
      buildMarketDiscoveryCopyText({ asof, filters, candidates, marketContext }),
    );
    setCopyResult("idle");
  }, [asof, filters, candidates, marketContext]);

  const handleCopy = useCallback(async () => {
    if (!text) return;
    try {
      if (
        typeof navigator !== "undefined" &&
        navigator.clipboard &&
        typeof navigator.clipboard.writeText === "function"
      ) {
        await navigator.clipboard.writeText(text);
        setCopyResult("copied");
        return;
      }
      throw new Error("Clipboard API unavailable");
    } catch {
      setCopyResult("failed");
    }
  }, [text]);

  return (
    <div className="card">
      <h2>AI 투자세션 복사용 문구</h2>
      <p className="helper" style={{ marginBottom: 8 }}>
        ETF명과 기간별 수익률 기반의 1차 시장 해석 요청문을 만듭니다. AI 를 직접
        호출하지 않습니다 — 외부 AI 채널(GPT / Gemini / Claude) 에 직접 붙여넣는
        용도입니다.
      </p>
      <div className="btn-row">
        <button type="button" onClick={handleGenerate}>
          AI 투자세션 문구 생성
        </button>
        <button type="button" onClick={handleCopy} disabled={!text}>
          클립보드 복사
        </button>
      </div>
      <textarea
        className="market-copy-textarea"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setCopyResult("idle");
        }}
        placeholder="문구 생성 버튼을 클릭하면 여기에 표시됩니다. 클립보드 복사가 실패해도 textarea 에서 직접 선택해 복사할 수 있습니다."
        rows={16}
      />
      {copyResult === "copied" ? (
        <div className="message info" style={{ marginTop: 8 }}>
          클립보드에 복사되었습니다.
        </div>
      ) : null}
      {copyResult === "failed" ? (
        <div className="message info" style={{ marginTop: 8 }}>
          클립보드 복사가 실패했습니다. 위 textarea 에서 직접 선택해 복사하세요.
        </div>
      ) : null}
    </div>
  );
}


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

  if (state.phase === "loading") {
    return (
      <section aria-labelledby="market-discovery-h">
        <h1 id="market-discovery-h">Market Discovery</h1>
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
      <p className="subtitle market-discovery-subtitle">
        SQLite 기준 최신 시장 데이터에서 일반 ETF 후보를 보여줍니다. 수익률 컬럼을
        클릭하면 정렬됩니다.
      </p>
      {/* 시장 배경 — 시스템 1차 시장 국면 (KODEX200 필수 / KOSPI 보조). */}
      <MarketContextCard ctx={data.market_context ?? null} />
      {/* GRID 우선 — 통합 테이블이 가장 위 */}
      <CandidateTable
        candidates={data.candidates ?? []}
        basis={basis}
        order={order}
        onSort={handleSort}
      />
      <SortStatusLine basis={basis} order={order} />
      {/* AI 투자세션 복사용 문구 — 새 API 호출 없이 현재 응답 기반으로 빌드.
          asof / filters 누락은 비정상 상태로 fail-loud (검증자 B-1 NOTE 반영). */}
      {data.asof && data.filters ? (
        <>
          <CopyTextCard
            asof={data.asof}
            filters={data.filters}
            candidates={data.candidates ?? []}
            marketContext={data.market_context ?? null}
          />
          {/* 2026-05-21 — AI Sessions 화면으로 draft 전달 (Context Bridge).
              직전 STEP 의 inline 기록 패널은 제거됨 — Market Discovery 의 책임은
              ETF 후보 발굴 + 복사용 문구 + 전달까지 (지시문 §4.1 / §4.2).
              2026-05-22 — marketContext 도 함께 전달 (지시문 §12). */}
          <TransferToAISessionsCard
            asof={data.asof}
            filters={data.filters}
            candidates={data.candidates ?? []}
            linkedMarketRefreshId={data.latest_refresh?.refresh_id ?? null}
            marketContext={data.market_context ?? null}
            onNavigate={onNavigate}
          />
          {/* 2026-05-27 ETF Constituents & Overlap 1차 — ETF Exposure 로 넘기는
              별도 카드. 구성종목 / 중복률 분석은 거기서 진행. */}
          <TransferToETFExposureCard
            asof={data.asof}
            filters={data.filters}
            candidates={data.candidates ?? []}
            marketContext={data.market_context ?? null}
            onNavigate={onNavigate}
          />
        </>
      ) : (
        <div className="card">
          <div className="message error">
            AI 투자세션 문구 / 전달 기능을 사용할 수 없습니다 — 응답에 기준일(asof)
            또는 필터 조건(filters) 이 포함되어 있지 않습니다.
          </div>
        </div>
      )}
      {/* 보조 컨트롤 — 갱신 / 정제 */}
      <RefreshControlCard
        state={refreshUi}
        onStart={handleStartRefresh}
        disabled={buttonDisabled}
        cooldownRemainingSeconds={cooldown}
      />
      <FilterCard filters={filters} onChange={handleFiltersChange} />
      <SummaryHeader data={data} />
    </section>
  );
}
