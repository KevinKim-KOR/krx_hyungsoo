"use client";

// POC3-02 UI-2 Judgment Workbench (2026-07-28).
//
// 읽기 전용 판단 화면. 후보·보유·확인 필요를 한 경로에서 검토하고, 종목 선택 시
// 실제 저장 가격 차트 + 상세 Evidence 를 같은 화면에 펼친다.
//
// - 기존 API 재사용 (candidates/holdings/evidence/nav). 신규 API 는 가격 시계열 1건만.
// - queryCache 공유 (화면 왕복 재호출 X · 가격 시계열은 선택 ticker lazy).
// - 결측/​stale/unavailable 정직성 유지. 신규 추천·위험 등급·BUY/SELL 없음.
// - Dashboard 데이터 조회 계약 미변경 (§11). 후보 조회는 Workbench 전용 키.

import { useState } from "react";
import {
  fetchMarketTopnLatest,
  type MarketTopNResponse,
  fetchEnrichedHoldings,
  type EnrichedHoldingsResult,
  fetchHoldingsMarketEvidence,
  type HoldingsMarketEvidenceResponse,
  fetchNavDiscountLatest,
  type NavDiscountLatestResponse,
} from "@/lib/api";
import { useSharedQuery, type QueryState } from "@/lib/api/queryCache";
import {
  WB_KEY_CAND,
  WB_KEY_HOLD,
  WB_KEY_EVID,
  WB_KEY_NAV,
} from "@/lib/api/dashboardKeys";
import type { MenuKey } from "./LeftSidebar";
import PriceChart from "./workbench/PriceChart";
import { HoldingTable } from "./workbench/HoldingTable";
import {
  fmtAsofKst,
  fmtSignedPct,
  fmtPlainPct,
  fmtScore,
  directionColor,
  candReturn,
  candExcess,
  candDrawdown,
  candDataState,
  evidenceByTicker,
  heldTickerSet,
  evidenceReturn,
  evidenceExcess,
  isHeld,
  relationState,
  type RelationState,
} from "./workbench/helpers";

interface Props {
  onNavigate: (key: MenuKey) => void;
}


type Tab = "candidate" | "holding" | "attention";
type QuickFilter = "all" | "held" | "comparable" | "attention";

function fmtAsof(
  q: QueryState<{ asof?: string | null; holdings_asof?: string | null }>,
  field: "asof" | "holdings_asof",
): string {
  if (q.phase === "idle") return "미조회";
  if (q.phase === "loading") return "확인 중";
  if (q.phase === "error") return "확인 실패";
  const v = (q.data as Record<string, string | null | undefined>)[field];
  // ISO datetime 은 KST 로 변환해 표시 (raw 원문 미노출 · A-1(8)).
  return `${fmtAsofKst(v)}${q.stale ? " ⚠stale" : ""}`;
}

export default function JudgmentWorkbenchView({ onNavigate }: Props) {
  // 후보 조회는 Workbench 전용 (n=30). Dashboard 는 topn 자동 호출 안 하지만,
  // Workbench 는 후보 표가 핵심이므로 마운트 시 조회한다 (사용자 명시 진입).
  const cand = useSharedQuery<MarketTopNResponse>(WB_KEY_CAND, () =>
    fetchMarketTopnLatest(30),
  );
  const hold = useSharedQuery<EnrichedHoldingsResult>(WB_KEY_HOLD, () =>
    fetchEnrichedHoldings(),
  );
  const evid = useSharedQuery<HoldingsMarketEvidenceResponse>(WB_KEY_EVID, () =>
    fetchHoldingsMarketEvidence(),
  );
  const nav = useSharedQuery<NavDiscountLatestResponse>(WB_KEY_NAV, () =>
    fetchNavDiscountLatest(),
  );

  const [tab, setTab] = useState<Tab>("candidate");
  const [filter, setFilter] = useState<QuickFilter>("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const evidenceItems =
    evid.phase === "success" ? evid.data.holdings : undefined;
  // 현재 보유/후보 ticker 집합 (LIST_DIRECT). 후보·보유 일치 판정의 단일 소스 —
  // 과거 Evidence 대신 이 집합으로 요약·후보표·보유표를 정합시킨다.
  const heldTickers =
    hold.phase === "success" ? heldTickerSet(hold.data.items) : undefined;
  const candTickers =
    cand.phase === "success" && cand.data.status === "ok"
      ? new Set(
          cand.data.candidates
            .map((c) => c.ticker)
            .filter((t): t is string => !!t),
        )
      : undefined;

  const reloadAll = () => {
    cand.reload();
    hold.reload();
    evid.reload();
    nav.reload();
  };

  return (
    <section aria-labelledby="wb-h" className="wb-root">
      <h1 id="wb-h">Judgment Workbench</h1>

      <StatusLine
        cand={cand}
        hold={hold}
        evid={evid}
        nav={nav}
        onReloadAll={reloadAll}
        onNavigate={onNavigate}
      />

      <SummaryRow cand={cand} hold={hold} evid={evid} />

      <TabBar tab={tab} setTab={setTab} />
      <div className="wb-controls">
        <QuickFilters filter={filter} setFilter={setFilter} />
        <input
          type="text"
          className="wb-search"
          placeholder="ticker 또는 ETF명 검색"
          aria-label="종목 검색"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="wb-table-wrap">
        {tab === "candidate" && (
          <CandidateTable
            cand={cand}
            heldTickers={heldTickers}
            filter={filter}
            query={query}
            selected={selected}
            onSelect={setSelected}
          />
        )}
        {tab === "holding" && (
          <HoldingTable
            hold={hold}
            evid={evid}
            evidenceItems={evidenceItems}
            candTickers={candTickers}
            filter={filter}
            query={query}
            selected={selected}
            onSelect={setSelected}
          />
        )}
        {tab === "attention" && (
          <AttentionTab
            cand={cand}
            hold={hold}
            evid={evid}
            nav={nav}
            onNavigate={onNavigate}
          />
        )}
      </div>

      {selected && (
        <SelectedDetail
          ticker={selected}
          cand={cand}
          evidenceItems={evidenceItems}
          heldTickers={heldTickers}
          candTickers={candTickers}
          onNavigate={onNavigate}
        />
      )}
    </section>
  );
}

// ── 상단 상태줄 (§7.2) ─────────────────────────────────────────────────────
function StatusLine({
  cand,
  hold,
  evid,
  nav,
  onReloadAll,
  onNavigate,
}: {
  cand: QueryState<MarketTopNResponse>;
  hold: QueryState<EnrichedHoldingsResult>;
  evid: QueryState<HoldingsMarketEvidenceResponse>;
  nav: QueryState<NavDiscountLatestResponse>;
  onReloadAll: () => void;
  onNavigate: (k: MenuKey) => void;
}) {
  const holdState =
    hold.phase === "success"
      ? hold.stale
        ? "이전값 ⚠stale"
        : "사용 가능"
      : hold.phase === "error"
        ? "확인 실패"
        : "확인 중";
  const cells: { label: string; asof: string; phase: string }[] = [
    { label: "후보", asof: fmtAsof(cand, "asof"), phase: cand.phase },
    { label: "보유", asof: holdState, phase: hold.phase },
    { label: "보유 Evidence", asof: fmtAsof(evid, "holdings_asof"), phase: evid.phase },
    { label: "NAV", asof: fmtAsof(nav, "asof"), phase: nav.phase },
  ];
  return (
    <div className="wb-status-line">
      {cells.map((c) => (
        <span key={c.label} className="wb-status-cell">
          <span style={{ color: "var(--muted)" }}>{c.label}: </span>
          <span
            style={{
              color: c.phase === "error" ? "var(--danger)" : "var(--muted)",
            }}
          >
            기준일 {c.asof}
          </span>
        </span>
      ))}
      <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
        <button type="button" className="wb-btn" onClick={onReloadAll}>
          다시 불러오기
        </button>
        <button
          type="button"
          className="wb-btn"
          onClick={() => onNavigate("market_discovery")}
        >
          Market Discovery →
        </button>
        {/* §7·AC-14: 보유 평가 → 보유 현황, 근거 확인 → 확인 근거. */}
        <button
          type="button"
          className="wb-btn"
          onClick={() => onNavigate("holdings")}
        >
          보유 현황 →
        </button>
        <button
          type="button"
          className="wb-btn"
          onClick={() => onNavigate("holdings_evidence")}
        >
          확인 근거 →
        </button>
      </span>
    </div>
  );
}

// ── 요약 (§7.3) ────────────────────────────────────────────────────────────
function SummaryRow({
  cand,
  hold,
  evid,
}: {
  cand: QueryState<MarketTopNResponse>;
  hold: QueryState<EnrichedHoldingsResult>;
  evid: QueryState<HoldingsMarketEvidenceResponse>;
}) {
  const candOk = cand.phase === "success" && cand.data.status === "ok";
  const candCount = candOk ? cand.data.candidates.length : null;
  // 보유 종목 수: 계좌별 원본 행이 아니라 고유 ticker 수 (표 집계와 일치 · A-1).
  const holdTickers =
    hold.phase === "success"
      ? new Set(hold.data.items.map((h) => h.ticker))
      : null;
  const holdCount = holdTickers ? holdTickers.size : null;
  // 후보에 포함된 보유: 과거 Evidence 의 matched_topn_count 가 아니라 **현재**
  // 후보 목록 ∩ 현재 보유 종목의 실제 교집합 (화면 내부 수치 정합 · A-1).
  const matchCount =
    candOk && holdTickers
      ? cand.data.candidates.filter(
          (c) => c.ticker && holdTickers.has(c.ticker),
        ).length
      : null;
  const attnCount =
    evid.phase === "success"
      ? evid.data.summary.evidence_unavailable_count +
        evid.data.summary.constituents_unavailable_count +
        evid.data.summary.nav_discount_unavailable_count
      : null;
  const cell = (label: string, v: number | null) => (
    <span className="wb-summary-cell">
      <span style={{ color: "var(--muted)" }}>{label} </span>
      <strong>{v == null ? "—" : v}</strong>
    </span>
  );
  return (
    <div className="wb-summary-row">
      {cell("후보", candCount)}
      {cell("보유", holdCount)}
      {cell("후보에 포함된 보유", matchCount)}
      {cell("확인 필요", attnCount)}
    </div>
  );
}

// ── 탭 / 필터 ──────────────────────────────────────────────────────────────
function TabBar({ tab, setTab }: { tab: Tab; setTab: (t: Tab) => void }) {
  const tabs: { key: Tab; label: string }[] = [
    { key: "candidate", label: "후보" },
    { key: "holding", label: "보유" },
    { key: "attention", label: "확인 필요" },
  ];
  return (
    <div className="wb-tabs" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.key}
          type="button"
          role="tab"
          aria-selected={tab === t.key}
          className={tab === t.key ? "wb-tab wb-tab-active" : "wb-tab"}
          onClick={() => setTab(t.key)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

function QuickFilters({
  filter,
  setFilter,
}: {
  filter: QuickFilter;
  setFilter: (f: QuickFilter) => void;
}) {
  const opts: { key: QuickFilter; label: string }[] = [
    { key: "all", label: "전체" },
    { key: "held", label: "보유 중" },
    { key: "comparable", label: "비교 가능" },
    { key: "attention", label: "확인 필요" },
  ];
  return (
    <div className="wb-filters">
      {opts.map((o) => (
        <button
          key={o.key}
          type="button"
          className={filter === o.key ? "wb-filter wb-filter-active" : "wb-filter"}
          onClick={() => setFilter(o.key)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ── 후보 표 (§7.5) ─────────────────────────────────────────────────────────
type SortDir = "asc" | "desc";
function useSort(defaultKey: string) {
  const [sortKey, setSortKey] = useState<string>(defaultKey);
  const [dir, setDir] = useState<SortDir>("asc");
  const toggle = (k: string) => {
    if (k === sortKey) setDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(k);
      setDir("asc");
    }
  };
  return { sortKey, dir, toggle };
}

function CandidateTable({
  cand,
  heldTickers,
  filter,
  query,
  selected,
  onSelect,
}: {
  cand: QueryState<MarketTopNResponse>;
  heldTickers: Set<string> | undefined;
  filter: QuickFilter;
  query: string;
  selected: string | null;
  onSelect: (t: string) => void;
}) {
  const { sortKey, dir, toggle } = useSort("rank");
  if (cand.phase !== "success") {
    if (cand.phase === "error") return <p className="wb-danger">후보 확인 실패</p>;
    return <p className="wb-muted">후보 확인 중...</p>;
  }
  if (cand.data.status !== "ok") {
    return <p className="wb-warn">후보 데이터 확인 불가 ({cand.data.status})</p>;
  }

  const stale = cand.stale;
  let rows = cand.data.candidates.slice();
  // 필터 (정렬·필터는 원본 순위·데이터 변경 안 함 · §7.4).
  if (filter === "held") {
    rows = rows.filter((c) => isHeld(heldTickers, c.ticker));
  } else if (filter === "comparable") {
    rows = rows.filter((c) => candDataState(c) === "ok" || candReturn(c, "one_month") != null);
  } else if (filter === "attention") {
    rows = rows.filter((c) => candDataState(c) !== "ok" && candDataState(c) !== "—");
  }
  if (query.trim()) {
    const q = query.trim().toLowerCase();
    rows = rows.filter(
      (c) =>
        (c.ticker ?? "").toLowerCase().includes(q) ||
        (c.name ?? "").toLowerCase().includes(q),
    );
  }

  // 로컬 정렬 (복제본 · 원본 미변경).
  const val = (c: (typeof rows)[number]): number | string => {
    switch (sortKey) {
      case "rank":
        return c.rank ?? 9999;
      case "one_month":
        return candReturn(c, "one_month") ?? -Infinity;
      case "three_month":
        return candReturn(c, "three_month") ?? -Infinity;
      case "excess":
        return candExcess(c) ?? -Infinity;
      case "score":
        return c.relative_upside_score ?? -Infinity;
      case "drawdown":
        return candDrawdown(c) ?? -Infinity;
      default:
        return c.rank ?? 9999;
    }
  };
  rows.sort((a, b) => {
    const va = val(a);
    const vb = val(b);
    const cmp = va < vb ? -1 : va > vb ? 1 : 0;
    return dir === "asc" ? cmp : -cmp;
  });

  // 2026-08-12 카드 전환 — 표 헤더가 사라지므로 정렬을 세그먼트 바로 옮긴다.
  //   정렬 키·동작(같은 키 재클릭 시 asc/desc 전환)은 기존 그대로.
  //   보유 현황(.holdings-sortbar)과 같은 표기를 재사용한다.
  const S = (key: string, label: string) => (
    <button
      type="button"
      className={sortKey === key ? "on" : undefined}
      onClick={() => toggle(key)}
      aria-pressed={sortKey === key}
    >
      {label}
      {sortKey === key ? (dir === "asc" ? " ▲" : " ▼") : ""}
    </button>
  );

  return (
    <>
      <div className="holdings-sortbar">
        <span className="holdings-sortbar-label">정렬</span>
        <span className="holdings-sort-seg">
          {S("rank", "순위")}
          {S("one_month", "1M")}
          {S("three_month", "3M")}
          {S("excess", "KODEX초과")}
          {S("score", "참고점수")}
          {S("drawdown", "고점대비")}
        </span>
        <span className="holdings-sortbar-hint">
          같은 항목을 다시 누르면 오름/내림 전환
        </span>
      </div>
      <div className="wb-hlist" data-testid="wb-candidate-list">
        {stale && (
          <div className="wb-hstale">⚠ 이전 조회값 (재조회 실패 — 최신 아님)</div>
        )}
        {rows.map((c) => {
          // 보유 여부 3-state: heldTickers 미로드(보유 조회 실패)면 확인 불가 —
          // "미보유(—)" 로 축약하지 않는다 (A-1(4)).
          const heldSt = relationState(heldTickers, c.ticker);
          const om = candReturn(c, "one_month");
          const tm = candReturn(c, "three_month");
          const ex = candExcess(c);
          const dd = candDrawdown(c);
          const isSel = selected === c.ticker;
          return (
            <div
              key={c.ticker ?? String(c.rank)}
              className={`wb-hrow${isSel ? " sel" : ""}`}
              role="button"
              tabIndex={0}
              aria-pressed={isSel}
              onClick={() => c.ticker && onSelect(c.ticker)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  if (c.ticker) onSelect(c.ticker);
                }
              }}
            >
              {/* 좌측 카드 — 보유 표와 같은 2단 × 2열 */}
              <div className="wb-hcard">
                <div className="wb-hrow-top">
                  <div className="wb-hrow-name">
                    {c.name ?? "—"}
                    <span className="wb-hbadges">
                      {/* 보유 여부 3-state: 미보유와 확인 불가를 구분 (A-1(4)). */}
                      {heldSt === "yes" ? (
                        <span className="wb-hb hold">보유</span>
                      ) : heldSt === "unknown" ? (
                        <span className="wb-hb danger">보유 확인 불가</span>
                      ) : (
                        <span className="wb-hb mute">미보유</span>
                      )}
                      <span className="wb-hb mute">{candDataState(c)}</span>
                    </span>
                  </div>
                  <div className="wb-hrow-pnl">
                    <span className="amt">{fmtScore(c.relative_upside_score)}</span>
                    <span className="rate wb-hmuted">참고점수</span>
                  </div>
                </div>
                <div className="wb-hrow-bot">
                  <div className="wb-hrow-facts">
                    <span>순위 {c.rank ?? "—"}</span>
                    <span className="sep">/</span>
                    <span className="tk">{c.ticker}</span>
                  </div>
                </div>
              </div>
              {/* 우측 비교 지표 열 */}
              <div className="wb-hmetrics">
                <div className="wb-hm3">
                  <div className="wb-hm-cell">
                    <span className="k">1M</span>
                    <span className="v" style={{ color: directionColor(om) }}>
                      {fmtSignedPct(om)}
                    </span>
                  </div>
                  <div className="wb-hm-cell">
                    <span className="k">3M</span>
                    <span className="v" style={{ color: directionColor(tm) }}>
                      {fmtSignedPct(tm)}
                    </span>
                  </div>
                  <div className="wb-hm-cell">
                    <span className="k">KODEX초과</span>
                    <span className="v" style={{ color: directionColor(ex) }}>
                      {fmtSignedPct(ex)}
                    </span>
                  </div>
                </div>
                <div className="wb-hm-ex">
                  <span className="k">고점대비</span>
                  <span className="v" style={{ color: directionColor(dd) }}>
                    {fmtPlainPct(dd)}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
        {rows.length === 0 && <p className="wb-muted">조건에 맞는 후보 없음</p>}
      </div>
    </>
  );
}

// ── 확인 필요 탭 (§7.7) ────────────────────────────────────────────────────
type AttnKind = "unavailable" | "warn" | "neutral";
function AttentionTab({
  cand,
  hold,
  evid,
  nav,
  onNavigate,
}: {
  cand: QueryState<MarketTopNResponse>;
  hold: QueryState<EnrichedHoldingsResult>;
  evid: QueryState<HoldingsMarketEvidenceResponse>;
  nav: QueryState<NavDiscountLatestResponse>;
  onNavigate: (k: MenuKey) => void;
}) {
  const rows: { text: string; kind: AttnKind; action: MenuKey; actionLabel: string }[] = [];

  // stale 통합 표시 (§7.7): 재조회 실패로 이전 성공값을 보여주는 영역을 예외로.
  const staleAreas: string[] = [];
  if (cand.phase === "success" && cand.stale) staleAreas.push("후보");
  if (hold.phase === "success" && hold.stale) staleAreas.push("보유");
  if (evid.phase === "success" && evid.stale) staleAreas.push("보유 Evidence");
  if (nav.phase === "success" && nav.stale) staleAreas.push("NAV");
  if (staleAreas.length > 0) {
    rows.push({
      text: `이전 조회값 (재조회 실패): ${staleAreas.join(", ")}`,
      kind: "warn",
      action: "diagnostics",
      actionLabel: "진단·상태 확인",
    });
  }

  if (cand.phase === "success") {
    const risk = cand.data.market_risk_reference;
    const vix = risk?.vix;
    const kodex = risk?.kodex200;
    if (
      vix?.availability === "available" &&
      kodex?.availability === "available" &&
      vix.as_of_date &&
      kodex.as_of_date &&
      vix.as_of_date < kodex.as_of_date
    ) {
      rows.push({
        text: `VIX stale — 기준일 ${vix.as_of_date} (시장 ${kodex.as_of_date}보다 이전)`,
        kind: "warn",
        action: "diagnostics",
        actionLabel: "진단·상태 확인",
      });
    }
    if (cand.data.status !== "ok") {
      rows.push({
        text: `후보 데이터 확인 불가 (${cand.data.status})`,
        kind: "unavailable",
        action: "market_discovery",
        actionLabel: "Market Discovery 확인",
      });
    }
  } else if (cand.phase === "error") {
    rows.push({
      text: "후보 조회 실패",
      kind: "unavailable",
      action: "market_discovery",
      actionLabel: "Market Discovery 확인",
    });
  }

  if (evid.phase === "success") {
    const s = evid.data.summary;
    if (s.evidence_unavailable_count > 0)
      rows.push({
        // 근거 확인은 "확인 근거" 화면으로 (§7·AC-14).
        text: `보유 Evidence 확인 필요 ${s.evidence_unavailable_count}건`,
        kind: "unavailable",
        action: "holdings_evidence",
        actionLabel: "해당 근거 확인",
      });
    if (s.constituents_unavailable_count > 0)
      rows.push({
        text: `구성종목 비교 불가 ${s.constituents_unavailable_count}건`,
        kind: "unavailable",
        action: "etf_exposure",
        actionLabel: "구성종목 확인",
      });
    if (s.nav_discount_unavailable_count > 0)
      rows.push({
        text: `Evidence NAV 미연동 ${s.nav_discount_unavailable_count}건`,
        kind: "warn",
        action: "diagnostics",
        actionLabel: "NAV 상태 확인",
      });
  } else if (evid.phase === "error") {
    rows.push({
      text: "보유 Evidence 조회 실패",
      kind: "unavailable",
      action: "holdings_evidence",
      actionLabel: "확인 근거 열기",
    });
  }

  if (nav.phase === "success") {
    const s = nav.data.summary;
    const bad = (s.unavailable_count ?? 0) + (s.failed_count ?? 0);
    if (bad > 0)
      rows.push({
        text: `NAV 미연동/실패 ${bad}건`,
        kind: "warn",
        action: "diagnostics",
        actionLabel: "NAV 상태 확인",
      });
  } else if (nav.phase === "error") {
    rows.push({
      text: "NAV 조회 실패",
      kind: "unavailable",
      action: "diagnostics",
      actionLabel: "진단·상태 확인",
    });
  }

  if (rows.length === 0) {
    const loading =
      cand.phase === "loading" ||
      evid.phase === "loading" ||
      nav.phase === "loading";
    return <p className="wb-muted">{loading ? "확인 중..." : "확인된 예외 없음"}</p>;
  }

  const color = (k: AttnKind) =>
    k === "unavailable" ? "var(--danger)" : k === "warn" ? "var(--warn)" : "var(--muted)";
  return (
    <ul className="wb-attn-list">
      {rows.map((r, i) => (
        <li key={i} className={`wb-attn-${r.kind}`}>
          <span style={{ color: color(r.kind), fontWeight: 600 }}>{r.text}</span>
          <button
            type="button"
            className="wb-attn-btn"
            onClick={() => onNavigate(r.action)}
          >
            {r.actionLabel} →
          </button>
        </li>
      ))}
    </ul>
  );
}

// ── 선택 상세 (§7.8) ───────────────────────────────────────────────────────
function SelectedDetail({
  ticker,
  cand,
  evidenceItems,
  heldTickers,
  candTickers,
  onNavigate,
}: {
  ticker: string;
  cand: QueryState<MarketTopNResponse>;
  evidenceItems: HoldingsMarketEvidenceResponse["holdings"] | undefined;
  heldTickers: Set<string> | undefined;
  candTickers: Set<string> | undefined;
  onNavigate: (k: MenuKey) => void;
}) {
  const c =
    cand.phase === "success"
      ? cand.data.candidates.find((x) => x.ticker === ticker)
      : undefined;
  const ev = evidenceByTicker(evidenceItems, ticker);
  // 보유 여부·후보 포함을 **현재 목록** 기준 3-state 로 (표·요약과 동일 소스 · A-1).
  // 과거 Evidence(topn_match) 아님. 집합 미로드면 "확인 불가".
  const heldSt = relationState(heldTickers, ticker);
  const candSt = relationState(candTickers, ticker);
  const relLabel = (s: RelationState, yes: string, no: string) =>
    s === "yes" ? yes : s === "no" ? no : "확인 불가";

  return (
    <div className="card wb-detail">
      <h2>
        {c?.name ?? ev?.name ?? "선택 종목"}{" "}
        <code style={{ color: "var(--muted)" }}>{ticker}</code>
      </h2>

      {/* 실제 저장 가격 시계열 차트 (§5.8·§6). */}
      <div style={{ marginBottom: 8 }}>
        <PriceChart ticker={ticker} />
      </div>

      {/* 수치 근거 (기존 응답). */}
      <div className="wb-detail-grid">
        {/* 후보에 있으면 후보 수치, 보유만 선택 시 Evidence 수치로 fallback (A-1(9)). */}
        <DetailCell
          label="1개월"
          v={fmtSignedPct(candReturn(c, "one_month") ?? evidenceReturn(ev, "one_month"))}
        />
        <DetailCell
          label="3개월"
          v={fmtSignedPct(
            candReturn(c, "three_month") ?? evidenceReturn(ev, "three_month"),
          )}
        />
        <DetailCell
          label="KODEX 초과"
          v={fmtSignedPct(candExcess(c) ?? evidenceExcess(ev))}
        />
        <DetailCell label="참고점수" v={fmtScore(c?.relative_upside_score)} />
        <DetailCell label="고점 대비" v={fmtPlainPct(candDrawdown(c))} />
        <DetailCell label="보유 여부" v={relLabel(heldSt, "보유 중", "미보유")} />
        <DetailCell
          label="후보 포함"
          v={relLabel(candSt, "후보 포함", "후보 아님")}
        />
        <DetailCell label="데이터 상태" v={candDataState(c)} />
      </div>

      {/* NAV / 구성종목 (Evidence 기반 · 기본 접힘) */}
      {ev && (
        <details style={{ marginTop: 8 }}>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>
            NAV · 구성종목 · 중복률 상세
          </summary>
          <div className="wb-detail-grid" style={{ marginTop: 8 }}>
            <DetailCell
              label="NAV 상태"
              v={ev.nav_discount?.status ?? "—"}
            />
            <DetailCell
              label="괴리율"
              v={fmtPlainPct(ev.nav_discount?.discount_rate_pct)}
            />
            <DetailCell
              label="구성종목 상태"
              v={ev.constituents_overlap?.status ?? "—"}
            />
          </div>
        </details>
      )}

      <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button
          type="button"
          className="wb-btn"
          onClick={() => onNavigate("etf_exposure")}
        >
          ETF Exposure 상세 →
        </button>
        <button
          type="button"
          className="wb-btn"
          onClick={() => onNavigate("market_discovery")}
        >
          Market Discovery →
        </button>
      </div>
    </div>
  );
}

function DetailCell({ label, v }: { label: string; v: string }) {
  return (
    <div className="wb-detail-cell">
      <span style={{ color: "var(--muted)", fontSize: 12 }}>{label}</span>
      <span style={{ fontWeight: 600 }}>{v}</span>
    </div>
  );
}
