"use client";

// Data Status 화면 — 2026-06-08 NAV / Discount Display FIX.
//
// 책임:
// - 저장된 etf_nav_daily (Naver universe 1회 호출 결과) 의 전체 ETF NAV /
//   시장가 / 괴리율 / asof / source / status 를 한 곳에서 조회.
// - 검색 (ticker / 이름) + status filter + 괴리율 기준 정렬.
// - 화면 진입 시 1회 GET /market/nav-discount/latest 호출 (외부 source 호출 X).
// - 매수/매도 판단 X — 조회 영역.
//
// 이전 정책 (2026-06-06 placeholder): "시장 데이터 / refresh 상태 들어갈 자리".
// 변경 사유: NAV / Discount Display FIX 의 전체 ETF 조회 위치를 Data Status 로 채택.

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchNavDiscountLatest,
  type NavDiscountItem,
  type NavDiscountLatestResponse,
} from "@/lib/api";
import MLBaselineV0Card from "./MLBaselineV0Card";
import MLEvidenceRefreshCard from "./MLEvidenceRefreshCard";
import MLFeatureSanityCard from "./MLFeatureSanityCard";

type LoadState =
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "ready"; data: NavDiscountLatestResponse };

type StatusFilter = "all" | "ok" | "unavailable" | "other";
type SortKey = "ticker" | "discount" | "absdiscount";
type SortOrder = "asc" | "desc";

const DASH = "-";

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패(HTTP ${e.httpStatus}): ${e.message}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

function fmtNumber(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return DASH;
  return Math.round(value).toLocaleString();
}

function fmtPct(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return DASH;
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function pctColor(value: number | null): string {
  if (value == null) return "var(--muted)";
  const abs = Math.abs(value);
  if (abs >= 5) return "var(--danger)";
  if (abs >= 3) return "var(--warn)";
  return "var(--fg)";
}

function statusBadgeClass(status: string): string {
  if (status === "ok") return "constituent-status-badge constituent-status-ok";
  if (status === "unavailable") {
    return "constituent-status-badge constituent-status-unavailable";
  }
  if (status === "partial") {
    return "constituent-status-badge constituent-status-timeout";
  }
  return "constituent-status-badge";
}

export default function DataStatusView() {
  const [state, setState] = useState<LoadState>({ phase: "loading" });
  const [query, setQuery] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [sortKey, setSortKey] = useState<SortKey>("absdiscount");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");

  const load = useCallback(() => {
    setState({ phase: "loading" });
    fetchNavDiscountLatest()
      .then((data) => setState({ phase: "ready", data }))
      .catch((e) => setState({ phase: "error", message: describeError(e) }));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filteredSorted = useMemo<NavDiscountItem[]>(() => {
    if (state.phase !== "ready") return [];
    const q = query.trim().toLowerCase();
    let items = state.data.items;
    if (q) {
      items = items.filter(
        (it) =>
          it.ticker.toLowerCase().includes(q) ||
          (it.name ?? "").toLowerCase().includes(q),
      );
    }
    if (statusFilter !== "all") {
      items = items.filter((it) => {
        if (statusFilter === "ok") return it.status === "ok";
        if (statusFilter === "unavailable") return it.status === "unavailable";
        return it.status !== "ok" && it.status !== "unavailable";
      });
    }
    const compareNumber = (a: number | null, b: number | null) => {
      const av = a ?? -Infinity;
      const bv = b ?? -Infinity;
      return av === bv ? 0 : av < bv ? -1 : 1;
    };
    const sorted = [...items].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "ticker") cmp = a.ticker.localeCompare(b.ticker);
      else if (sortKey === "discount") {
        cmp = compareNumber(a.discount_rate_pct, b.discount_rate_pct);
      } else {
        const aa = a.discount_rate_pct == null ? null : Math.abs(a.discount_rate_pct);
        const bb = b.discount_rate_pct == null ? null : Math.abs(b.discount_rate_pct);
        cmp = compareNumber(aa, bb);
      }
      return sortOrder === "desc" ? -cmp : cmp;
    });
    return sorted;
  }, [state, query, statusFilter, sortKey, sortOrder]);

  return (
    <section aria-labelledby="data-status-h">
      <h1 id="data-status-h">Data Status</h1>
      <p className="subtitle">
        전체 ETF NAV / 시장가 / 괴리율 조회 — 저장된 데이터 기준 (외부 source 호출 0).
      </p>
      <div className="role-banner">
        <strong>[보조 화면 — 데이터 조회]</strong> Naver ETF universe 1회 호출 결과로 SQLite{" "}
        <code>etf_nav_daily</code> 에 저장된 전체 ETF NAV / 시장가 / 괴리율을 한곳에서
        검색·정렬합니다. 본 화면은 데이터 조회 영역이며 매수·매도·교체 판단이 아닙니다.
        값 갱신은 Market Discovery 화면의 &lsquo;최신 시장 데이터 갱신&rsquo; 버튼을 사용합니다.
      </div>

      <NavDiscountControls
        state={state}
        query={query}
        statusFilter={statusFilter}
        sortKey={sortKey}
        sortOrder={sortOrder}
        onQueryChange={setQuery}
        onStatusFilterChange={setStatusFilter}
        onSortKeyChange={setSortKey}
        onSortOrderToggle={() =>
          setSortOrder((p) => (p === "desc" ? "asc" : "desc"))
        }
        onReload={load}
        filteredCount={filteredSorted.length}
      />

      {state.phase === "loading" && (
        <div className="card">
          <div className="message info">불러오는 중...</div>
        </div>
      )}

      {state.phase === "error" && (
        <div className="card">
          <div className="message error">{state.message}</div>
        </div>
      )}

      {state.phase === "ready" && state.data.status === "empty" && (
        <div className="card placeholder-card">
          <h2>저장된 NAV 데이터가 없습니다</h2>
          <p>
            Market Discovery 화면에서 &lsquo;최신 시장 데이터 갱신&rsquo; 버튼을 한 번
            실행하면 Naver ETF universe NAV 가 적재됩니다.
          </p>
        </div>
      )}

      {state.phase === "ready" && state.data.status === "ok" && (
        <NavDiscountTable items={filteredSorted} />
      )}

      {/* 2026-06-11 UI 안전실행 (지시문 §5.1) — 화면 상단에서 ML evidence
          갱신을 background 로 시작 + 단계별 상태 확인. 본 카드는 baseline 산식 /
          매수·매도 판단 0건 (§8 금지사항 준수). */}
      <MLEvidenceRefreshCard />

      {/* 2026-06-08 ML Feature Sanity Check (지시문 §4.7) — ML 최소 데이터 레인
          상태 아래에 sanity 요약 표시. read-only API 호출만 (재계산 X). */}
      <MLFeatureSanityCard />

      {/* 2026-06-11 ML Baseline v0 룩백 검증 (지시문 §12) — sanity 카드 아래에
          후보 발굴 / 위험 패턴 baseline 의 룩백 검증 결과 요약 표시. read-only. */}
      <MLBaselineV0Card />
    </section>
  );
}

function NavDiscountControls({
  state,
  query,
  statusFilter,
  sortKey,
  sortOrder,
  onQueryChange,
  onStatusFilterChange,
  onSortKeyChange,
  onSortOrderToggle,
  onReload,
  filteredCount,
}: {
  state: LoadState;
  query: string;
  statusFilter: StatusFilter;
  sortKey: SortKey;
  sortOrder: SortOrder;
  onQueryChange: (v: string) => void;
  onStatusFilterChange: (v: StatusFilter) => void;
  onSortKeyChange: (v: SortKey) => void;
  onSortOrderToggle: () => void;
  onReload: () => void;
  filteredCount: number;
}) {
  const summary = state.phase === "ready" ? state.data.summary : null;
  const asof = state.phase === "ready" ? state.data.asof : null;
  const source = state.phase === "ready" ? state.data.source : null;
  return (
    <div className="card">
      <h2>조회 옵션</h2>
      {summary && (
        <p className="helper" style={{ marginBottom: 8 }}>
          전체 {summary.total_count}건 · ok {summary.ok_count} · unavailable{" "}
          {summary.unavailable_count} · 기타 {summary.failed_count} · asof{" "}
          {asof ?? "-"} · source {source ?? "-"} · 필터 결과 {filteredCount}건
        </p>
      )}
      <div
        style={{
          display: "flex",
          gap: 12,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
          검색
          <input
            type="text"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="ticker / ETF명"
            style={{ minWidth: 160 }}
          />
        </label>
        <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
          상태
          <select
            value={statusFilter}
            onChange={(e) => onStatusFilterChange(e.target.value as StatusFilter)}
          >
            <option value="all">전체</option>
            <option value="ok">ok</option>
            <option value="unavailable">unavailable</option>
            <option value="other">기타</option>
          </select>
        </label>
        <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
          정렬
          <select
            value={sortKey}
            onChange={(e) => onSortKeyChange(e.target.value as SortKey)}
          >
            <option value="absdiscount">괴리율 |abs|</option>
            <option value="discount">괴리율 (부호 포함)</option>
            <option value="ticker">ticker</option>
          </select>
        </label>
        <button type="button" onClick={onSortOrderToggle}>
          {sortOrder === "desc" ? "↓ 내림차순" : "↑ 오름차순"}
        </button>
        <button type="button" onClick={onReload}>
          다시 불러오기
        </button>
      </div>
    </div>
  );
}

function NavDiscountTable({ items }: { items: NavDiscountItem[] }) {
  if (items.length === 0) {
    return (
      <div className="card">
        <div className="message info">필터 조건에 맞는 항목이 없습니다.</div>
      </div>
    );
  }
  // 너무 많으면 상위 200건만 렌더링 (검색/필터 후에도 1000+ 인 경우 대비).
  const visible = items.slice(0, 200);
  return (
    <div className="card market-topn-card">
      <h2>전체 ETF NAV / 괴리율</h2>
      <table className="market-topn-table">
        <thead>
          <tr>
            <th style={{ width: 90 }}>ticker</th>
            <th>ETF명</th>
            <th style={{ textAlign: "right", width: 110 }}>NAV</th>
            <th style={{ textAlign: "right", width: 110 }}>시장가</th>
            <th style={{ textAlign: "right", width: 100 }}>괴리율</th>
            <th style={{ width: 110 }}>asof</th>
            <th style={{ width: 160 }}>source</th>
            <th style={{ width: 110 }}>status</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((it) => (
            <tr key={`${it.ticker}-${it.asof}-${it.source}`}>
              <td>
                <code>{it.ticker}</code>
              </td>
              <td>{it.name ?? DASH}</td>
              <td style={{ textAlign: "right" }}>{fmtNumber(it.nav)}</td>
              <td style={{ textAlign: "right" }}>{fmtNumber(it.market_price)}</td>
              <td
                style={{
                  textAlign: "right",
                  color: pctColor(it.discount_rate_pct),
                }}
              >
                {fmtPct(it.discount_rate_pct)}
                {it.flag && (
                  <>
                    {" "}
                    <span style={{ fontSize: "0.75rem", color: "var(--warn)" }}>
                      {it.flag}
                    </span>
                  </>
                )}
              </td>
              <td>{it.asof || DASH}</td>
              <td style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
                {it.source || DASH}
              </td>
              <td>
                <span className={statusBadgeClass(it.status)}>{it.status}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {items.length > visible.length && (
        <p className="helper" style={{ marginTop: 8 }}>
          상위 {visible.length}건만 표시. 필터 / 검색을 좁히면 더 정확히 확인할 수
          있습니다 (전체 {items.length}건).
        </p>
      )}
    </div>
  );
}
