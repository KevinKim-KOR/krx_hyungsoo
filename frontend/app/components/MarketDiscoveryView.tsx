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
  DEFAULT_MARKET_TOPN_FILTERS,
  fetchMarketRefreshStatus,
  fetchMarketTopnLatest,
  postMarketRefresh,
  type MarketProductTag,
  type MarketRefreshStartResponse,
  type MarketRefreshStatusResponse,
  type MarketTopNEntry,
  type MarketTopNFilterOptions,
  type MarketTopNResponse,
} from "@/lib/api";

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
const POLL_MAX_TICKS = 90; // 6분 안전 상한

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

function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return DASH;
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function returnPctColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return "var(--muted)";
  return value >= 0 ? "var(--ok)" : "var(--danger)";
}

const TAG_LABELS: Record<MarketProductTag, string> = {
  inverse: "인버스",
  leveraged: "레버리지",
  synthetic: "합성",
  futures: "선물형",
};

function TagBadges({ tags }: { tags: MarketProductTag[] | undefined }) {
  if (!tags || tags.length === 0) return null;
  return (
    <span className="market-topn-tags">
      {tags.map((t) => (
        <span key={t} className={`market-topn-tag tag-${t}`}>
          {TAG_LABELS[t] ?? t}
        </span>
      ))}
    </span>
  );
}

function fmtCooldown(seconds: number): string {
  if (seconds <= 0) return "0";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}시간 ${m}분`;
  return `${m}분`;
}

function TopNTable({
  title,
  entries,
}: {
  title: string;
  entries: MarketTopNEntry[];
}) {
  return (
    <div className="card market-topn-card">
      <h2>{title}</h2>
      {entries.length === 0 ? (
        <div className="message info">표시할 항목이 없습니다.</div>
      ) : (
        <table className="market-topn-table">
          <thead>
            <tr>
              <th style={{ width: 56 }}>순위</th>
              <th style={{ width: 90 }}>티커</th>
              <th>ETF명</th>
              <th style={{ width: 110, textAlign: "right" }}>수익률</th>
              <th style={{ width: 130 }}>기준 시작일</th>
              <th style={{ width: 130 }}>기준 종료일</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e, idx) => (
              <tr key={`${e.rank ?? "x"}-${e.ticker ?? "x"}-${idx}`}>
                <td>{fmtNum(e.rank)}</td>
                <td>{e.ticker ? <code>{e.ticker}</code> : DASH}</td>
                <td>
                  {fmt(e.name)}
                  <TagBadges tags={e.tags as MarketProductTag[] | undefined} />
                </td>
                <td
                  style={{
                    textAlign: "right",
                    color: returnPctColor(e.return_pct),
                  }}
                >
                  {fmtPct(e.return_pct)}
                </td>
                <td>{fmt(e.basis_start_date)}</td>
                <td>{fmt(e.basis_end_date)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
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


export default function MarketDiscoveryView() {
  const [state, setState] = useState<LoadState>({ phase: "loading" });
  const [refreshUi, setRefreshUi] = useState<RefreshUiState>({ kind: "idle" });
  const [filters, setFilters] = useState<FilterUiState>(DEFAULT_FILTER_UI);
  const pollTickRef = useRef<number>(0);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // loadTopn 은 현재 filters state 를 캡처해서 fetch.
  // 검증자 B-6 NOTE 반영 — filters 변경 시 한 번만 fetch 되도록 처리:
  //   handleFiltersChange 는 setFilters 만 호출 → filters 변경 → loadTopn useCallback
  //   재생성 → useEffect 가 단 한 번 재실행 → fetch 1회.
  const loadTopn = useCallback(() => {
    setState({ phase: "loading" });
    fetchMarketTopnLatest(10, toOptions(filters))
      .then((data) => setState({ phase: "ready", data }))
      .catch((e) => setState({ phase: "error", message: describeError(e) }));
  }, [filters]);

  useEffect(() => {
    loadTopn();
  }, [loadTopn]);

  const handleFiltersChange = useCallback((next: FilterUiState) => {
    // state 변경만 — useEffect 가 단일 fetch 트리거.
    setFilters(next);
  }, []);

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
        stopPolling();
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
      <p className="subtitle">
        이 화면은 <strong>SQLite 에 저장된 시장 데이터</strong> 기준입니다. 새 데이터
        수집은 아래 &lsquo;최신 시장 데이터 갱신&rsquo; 버튼으로만 실행됩니다
        (single-flight + 6h cooldown).
      </p>
      <RefreshControlCard
        state={refreshUi}
        onStart={handleStartRefresh}
        disabled={buttonDisabled}
        cooldownRemainingSeconds={cooldown}
      />
      <FilterCard filters={filters} onChange={handleFiltersChange} />
      <SummaryHeader data={data} />
      <TopNTable title="일간 TOP N" entries={data.daily_topn} />
      <TopNTable title="1개월 TOP N" entries={data.one_month_topn} />
      <TopNTable title="3개월 TOP N" entries={data.three_month_topn} />
    </section>
  );
}
