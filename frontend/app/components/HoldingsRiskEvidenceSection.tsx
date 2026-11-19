"use client";

// POC3-05 보유 ETF 확인 근거 — 읽기 전용 확인 영역 (B구간).
//
// 기존 evidence 재사용만: enriched(평가·비중·손익) + market-evidence(5 · 20저장일 · KODEX 200 대비).
// 입력·저장 기능처럼 보이지 않는다(수정 버튼·저장 없음). 위험 점수/등급/매도 문구 없음.
// 급락 신호는 자동 조회 GET 계약 부재로 이번 Step 제외(PLAN §1.3·§6).
// POC5-UI-02: 사용자 선택 정렬 네 가지(평가 비중 · 손익률 · 5저장일 변화(기본) · 20저장일 변화 — 화면 숫자 그대로 ·
// 순서만 바꿈 · 재조회 0) · 선택 상세 '필요한 자료 안내'(그 종목의 기존 사유).
// POC5-09: 가격 흐름 기준 줄 · 기준일이 다른 종목은 5 · 20저장일 · KODEX 200 대비 '—'
// (backend 응답 사본이 값을 비움) · 상세에 실제 날짜 사유 · 가격 흐름 기준 · 저장 거래량(판정 §9-4).
// POC5-15: 요약 맨 위 상태 + ?(시장 · 보유 조합 · 오늘 띠와 같은 함수) · 긴 안내는 ? 도움말 ·
// 실패 · 빈 보유 안내 앞에 같은 상태 문구.
// POC5-13: 목록 위 요약(시장 국면 · PC 최근 20저장일 하락 구간 · 판정 범위) · 보기 '하락 구간' ·
// 행의 확인 사유 배지(파란 계열) · 상세 'PC 20저장일 하락 구간' 줄. 구간 판정은 backend 응답 사본이 한다.
// 조회는 Dashboard 와 같은 캐시 키(DASH_KEY_HOLDINGS/EVIDENCE)를 공유한다(Q6 · N+1 없음).
// POC6-33(PLAN §3 · 판정 §3 · §4):
// - 상세는 누른 행 바로 아래에 펼친다. 같은 행을 다시 누르면 닫힌다. 위 상세가 닫혀 행이 밀려도 누른 행의 화면 위치를
//   지킨다(누르기 전 위치를 재고, 그린 뒤 차이만큼 스크롤).
// - 상세 순서 = 가격 방향 → 주간 후보 여부 · 순위 → 필요한 자료 안내 → 가격 · 거래량 · 흔들림 요약(+ 날짜 역할) →
//   차트 → 주요 편입 · 구성종목 중복 → 순자산가치(NAV) · 괴리율. 개별 주식이 확인되면 구성 · NAV 대신 '해당 없음' 한 줄.
// - 주간 순위 = 화면에 들어올 때 GET /market/etf-compare/summary(「주간 ETF 점검」과 같은 인자) 한 번. 이 조회가 늦거나
//   실패해도 보유 · 가격 근거는 그대로 읽힌다(화면의 불러오는 중 · 실패 판정에 넣지 않음).
// - 주요 편입 = 상세를 열 때 GET /market/constituents/summary?ticker= 한 번(읽기 전용 · 수집 없음).
// - [전체 ETF NAV·괴리율 보기] 이동 버튼은 뺐다(전체 표 = 메뉴 「진단·상태 › 데이터 상태」).

import { type ReactNode, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  fetchConstituentsSummary,
  fetchEnrichedHoldings,
  fetchHoldingsMarketEvidence,
  type ConstituentsSummaryResponse,
  type EnrichedHoldingsResult,
  type HoldingsMarketEvidenceItem,
  type HoldingsMarketEvidenceResponse,
  type HoldingsTopnBasis,
  type PriceBasis,
} from "@/lib/api";
import { etfCompareKey, fetchEtfCompareSummary, type CompareSummary } from "@/lib/api/etfCompare";
import { useSharedQuery, type QueryState } from "@/lib/api/queryCache";
import { DASH_KEY_HOLDINGS, DASH_KEY_EVIDENCE } from "@/lib/api/dashboardKeys";
import { NAV_TERM } from "@/lib/navLabels";
import { priceBasisLine } from "@/lib/priceBasis";
import {
  DEFAULT_EVIDENCE_SORT,
  EVIDENCE_SORT_OPTIONS,
  NAV_HELP,
  OVERLAP_CAP_TEXT,
  OVERLAP_LIST_PREFIX,
  OVERLAP_SCOPE_UNKNOWN,
  OVERLAP_STATUS_TEXT,
  OVERLAP_UNAVAILABLE_TEXT,
  STOCK_NA_TEXT,
  WEEKLY_CHECK_CONDITION,
  buildRiskEvidenceRows,
  dateRoleLines,
  diffText,
  directionText,
  evidenceGuidance,
  mainHoldingsText,
  navCells,
  navRawLines,
  overlapFoundText,
  shownValue,
  sortEvidenceRows,
  weeklyRankView,
  type EvidenceSortKey,
  type RiskEvidenceRow,
} from "./holdings_risk_evidence/helpers";
import DeclineSummaryBlock from "./holdings_risk_evidence/DeclineSummaryBlock";
import DetailFlows from "./holdings_risk_evidence/DetailFlows";
import EvidenceGroups from "./holdings_risk_evidence/EvidenceGroups";
import HelpPopover from "./holdings_risk_evidence/HelpPopover";
import {
  FAILURE_TEXT,
  riskStateFromQueries,
} from "./holdings_risk_evidence/riskCombination";
import { topnBasisText } from "./HoldingsOverlapBridgeCard";
import PriceChart from "./workbench/PriceChart";
// 손익·수익률 방향 색은 ETF 비교하기와 같은 함수를 쓴다 — 국내 관례 전환 시
// 한 곳만 고치면 두 화면이 함께 바뀐다.
import { directionColor } from "./workbench/helpers";

type QuickView = "all" | "decline" | "need_check";

function fmtPct(v: number | null): string {
  if (v === null) return "자료 확인 필요";
  const s = v >= 0 ? "+" : "";
  return `${s}${v.toFixed(2)}%`;
}
function fmtPctp(v: number | null): string {
  if (v === null) return "자료 확인 필요";
  const s = v >= 0 ? "+" : "";
  return `${s}${v.toFixed(2)}%p`;
}
// POC5-09 — 기준일이 PC 비교 기준일과 달라 현재 비교에서 뺀 행은 값 칸을 '—'로 둔다(판정 §9-4-2).
function stale(r: RiskEvidenceRow): boolean {
  return r.price_dates?.comparison === "date_mismatch";
}
function fmtMoney(v: number | null): string {
  if (v === null) return "자료 확인 필요";
  return v.toLocaleString("ko-KR") + "원";
}

// POC6-33 E3 — 행 찾기 · 스크롤 보정(누른 행의 화면 위치 유지). 가장 가까운 스크롤 상자, 없으면 창을 움직인다.
function rowElement(list: HTMLElement | null, ticker: string): HTMLElement | null {
  if (!list) return null;
  return (
    Array.from(list.querySelectorAll<HTMLElement>("[data-row-ticker]")).find(
      (e) => e.dataset.rowTicker === ticker,
    ) ?? null
  );
}
function scrollByDelta(el: HTMLElement, delta: number): void {
  for (let p = el.parentElement; p; p = p.parentElement) {
    const oy = getComputedStyle(p).overflowY;
    if ((oy === "auto" || oy === "scroll") && p.scrollHeight > p.clientHeight) {
      p.scrollTop += delta;
      return;
    }
  }
  window.scrollBy(0, delta);
}

function DetailLine({
  label,
  testId,
  children,
}: {
  label: string;
  testId?: string;
  children: ReactNode;
}) {
  return (
    <div className="hre-detail-line" data-testid={testId}>
      <span className="k">{label}</span>
      <span className="v">{children}</span>
    </div>
  );
}

// ⑥ 주요 편입(E8) — 상세를 열 때 그 ETF 한 번 읽기. 상세는 행마다 새로 그려져(누른 행 아래) 종목이 바뀌면 다시 읽는다.
type ConsState =
  | { phase: "loading" }
  | { phase: "error" }
  | { phase: "ok"; data: ConstituentsSummaryResponse };

function MainHoldingsLine({ ticker }: { ticker: string }) {
  const [st, setSt] = useState<ConsState>({ phase: "loading" });
  useEffect(() => {
    let alive = true;
    fetchConstituentsSummary(ticker)
      .then((data) => {
        if (alive) setSt({ phase: "ok", data });
      })
      .catch(() => {
        if (alive) setSt({ phase: "error" });
      });
    return () => {
      alive = false;
    };
  }, [ticker]);
  if (st.phase === "loading") {
    return <DetailLine label="주요 편입" testId="hre-main-holdings">구성 자료 불러오는 중...</DetailLine>;
  }
  if (st.phase === "error") {
    return (
      <DetailLine label="주요 편입" testId="hre-main-holdings">
        구성 자료를 읽지 못함 — 조회 실패
      </DetailLine>
    );
  }
  const t = mainHoldingsText(st.data);
  return (
    <DetailLine label="주요 편입" testId="hre-main-holdings">
      {t.head}
      {t.stocks ? <span className="hre-detail-sub">{t.stocks}</span> : null}
    </DetailLine>
  );
}

// ⑥ 구성종목 중복(E7) — 비교 목록 범위(주간 순위와 별도인 후보 목록 · 그 목록의 기간 · 제외 조건)와 실제 비교 범위를 나눠 적는다.
function OverlapLine({
  item,
  topnBasis,
}: {
  item: HoldingsMarketEvidenceItem | null;
  topnBasis: HoldingsTopnBasis | null | undefined;
}) {
  if (!item) {
    return (
      <DetailLine label="구성종목 중복" testId="hre-overlap">
        시장 근거 자료가 없어 구성종목 중복을 표시할 수 없습니다.
      </DetailLine>
    );
  }
  const o = item.constituents_overlap;
  if (o.status !== "ok") {
    return (
      <DetailLine label="구성종목 중복" testId="hre-overlap">
        {OVERLAP_STATUS_TEXT[o.status] ?? OVERLAP_UNAVAILABLE_TEXT}
      </DetailLine>
    );
  }
  const found = o.overlap_with_market_core;
  return (
    <DetailLine label="구성종목 중복" testId="hre-overlap">
      <strong>{OVERLAP_SCOPE_UNKNOWN}</strong>
      <span className="hre-detail-sub" data-testid="hre-overlap-list-basis">
        {OVERLAP_LIST_PREFIX}
        {topnBasisText(topnBasis)}
      </span>
      <span className="hre-detail-sub hre-detail-note">{OVERLAP_CAP_TEXT}</span>
      {found.length > 0 ? (
        <span className="hre-detail-sub" data-testid="hre-overlap-found">
          확인된 겹침:
          <ul className="hre-overlap-list">
            {found.map((x, i) => (
              <li key={`${x.ticker ?? "na"}-${i}`}>{overlapFoundText(x)}</li>
            ))}
          </ul>
        </span>
      ) : null}
    </DetailLine>
  );
}

// ⑦ 순자산가치(NAV) · 괴리율(E10) — 여섯 칸을 늘 보이고, 받은 안내 원문 · 사전 밖 원문은 [자세히] 안에만.
function NavBlock({ item }: { item: HoldingsMarketEvidenceItem | null }) {
  const title = `${NAV_TERM} · 괴리율`;
  if (!item) {
    return (
      <DetailLine label={title} testId="hre-nav">
        시장 근거 자료가 없어 NAV 를 표시할 수 없습니다.
      </DetailLine>
    );
  }
  const cells = navCells(item.nav_discount);
  const raw = navRawLines(item.nav_discount);
  return (
    <div className="hre-detail-line hre-nav" data-testid="hre-nav">
      <span className="k">
        <span>{title}</span>
        <HelpPopover label={title} paragraphs={[...NAV_HELP]} />
      </span>
      <span className="v">
        <span className="hre-nav-grid">
          {cells.map((c) => (
            <span key={c.label} className="hre-nav-cell" data-nav-label={c.label}>
              <span className="k">{c.label}</span>
              <span className="v" style={c.color ? { color: c.color } : undefined}>
                {c.value}
              </span>
              {c.flag ? <span className={c.flagClass}>{c.flag}</span> : null}
            </span>
          ))}
        </span>
        {raw.length > 0 ? (
          <details className="hre-raw" data-testid="hre-nav-raw">
            <summary>자세히</summary>
            <div className="hre-raw-body">
              {raw.map((l) => (
                <div key={l}>{l}</div>
              ))}
            </div>
          </details>
        ) : null}
      </span>
    </div>
  );
}

// 누른 행 바로 아래 상세(E3 · 판정 Q1 순서).
function EvidenceDetail({
  row,
  item,
  basis,
  weekly,
  topnBasis,
}: {
  row: RiskEvidenceRow;
  item: HoldingsMarketEvidenceItem | null;
  basis: PriceBasis | null;
  weekly: QueryState<CompareSummary>;
  topnBasis: HoldingsTopnBasis | null | undefined;
}) {
  const rank = weeklyRankView(weekly, row.ticker);
  const guidance = evidenceGuidance(row, basis);
  const roles = dateRoleLines(row, item);
  const r20 = stale(row) ? null : row.return_20d_pct;
  const ex = stale(row) ? null : row.excess_vs_kodex200_20d_pctp;
  return (
    <div className="hre-rdetail" data-testid="hre-detail">
      {/* POC5-19 개정(2026-10-17 §2) — [세부 흐름 보기]는 상세 머리 하나(창으로 열림 · 아래 펼침 없음). */}
      <div className="hre-detail-head">
        <h3>
          {row.name ?? row.ticker} · {row.ticker}
        </h3>
        <DetailFlows key={`df-${row.ticker}`} row={row} item={item} basis={basis} />
      </div>
      {/* ① 가격 방향 · 같은 기간 시장 대비(E4) */}
      <div className="hre-dir" data-testid="hre-direction">
        최근 20저장일{" "}
        <b style={{ color: directionColor(shownValue(r20)) }}>{directionText(r20)}</b> · 같은 기간 KODEX 200
        대비 <b style={{ color: directionColor(shownValue(ex)) }}>{diffText(ex)}</b>
      </div>
      {/* ② 주간 후보 여부 · 순위(E5) */}
      <DetailLine label="주간 후보 여부 · 순위" testId="hre-weekly-rank">
        <strong>{rank.main}</strong>
        {rank.basis ? <span className="hre-detail-sub hre-detail-note">{rank.basis}</span> : null}
      </DetailLine>
      {/* ③ 필요한 자료 안내(E6 · 거른 뒤 남는 문장이 있을 때만) */}
      {guidance.length > 0 ? (
        <DetailLine label="필요한 자료 안내" testId="hre-guidance">
          {guidance.map((t) => (
            <span key={t} className="hre-guidance-item">
              {t}
              <br />
            </span>
          ))}
        </DetailLine>
      ) : null}
      {/* ④ 가격 · 거래량 · 가격 흔들림 세 묶음 + 날짜 역할(E9) */}
      <EvidenceGroups row={row} item={item} basis={basis} />
      {roles.length > 0 ? (
        <div className="hre-roles" data-testid="hre-date-roles">
          {roles.map((t) => (
            <div key={t}>{t}</div>
          ))}
        </div>
      ) : null}
      {/* ⑤ 가격 차트(기존 그대로) */}
      <PriceChart ticker={row.ticker} />
      {/* ⑥ 구성 · ⑦ NAV — 개별 주식이 확인되면 한 줄(E12) */}
      {rank.stock ? (
        <DetailLine label="구성 · NAV" testId="hre-stock-na">
          {STOCK_NA_TEXT}
        </DetailLine>
      ) : (
        <>
          <MainHoldingsLine ticker={row.ticker} />
          <OverlapLine item={item} topnBasis={topnBasis} />
          <NavBlock item={item} />
        </>
      )}
    </div>
  );
}

export default function HoldingsRiskEvidenceSection() {
  const holdings = useSharedQuery<EnrichedHoldingsResult>(
    DASH_KEY_HOLDINGS,
    () => fetchEnrichedHoldings(),
  );
  const evidence = useSharedQuery<HoldingsMarketEvidenceResponse>(
    DASH_KEY_EVIDENCE,
    () => fetchHoldingsMarketEvidence(),
  );
  // POC6-33 E5 — 주간 순위(「주간 ETF 점검」과 같은 인자 · 같은 조건이면 「ETF 비교하기」와 같은 캐시 키).
  const weekly = useSharedQuery<CompareSummary>(etfCompareKey(WEEKLY_CHECK_CONDITION), () =>
    fetchEtfCompareSummary(WEEKLY_CHECK_CONDITION),
  );
  // 판정 Q22 · PLAN E5(검증자 r1 F1) — 화면에 들어올 때마다 같은 키로 한 번 새로 읽는다(공유 캐시에 성공값이 있어도).
  // 이번 진입의 조회가 끝나기 전에는 이전 순위를 보이지 않고 '불러오는 중'. 끝난 뒤 실패(이전 성공값만 남음 = stale)는
  // weeklyRankView 가 '조회 실패'로 보인다. 같은 키의 진행 중 요청이 있으면 그 요청을 같이 쓴다(요청 한 번).
  const [weeklyEntryDone, setWeeklyEntryDone] = useState(false);
  const reloadWeekly = weekly.reloadAsync;
  useEffect(() => {
    let alive = true;
    const settle = () => {
      if (alive) setWeeklyEntryDone(true);
    };
    reloadWeekly().then(settle, settle);
    return () => {
      alive = false;
    };
  }, [reloadWeekly]);
  const weeklyShown: QueryState<CompareSummary> = weeklyEntryDone ? weekly : { phase: "loading" };

  const [quickView, setQuickView] = useState<QuickView>("all");
  const [sortKey, setSortKey] = useState<EvidenceSortKey>(DEFAULT_EVIDENCE_SORT);
  const [selected, setSelected] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const anchor = useRef<{ ticker: string; top: number } | null>(null);

  // 행을 누르면 열고, 같은 행을 다시 누르면 닫는다. 누르기 전 그 행의 화면 위치를 적어 둔다(E3).
  const toggle = (ticker: string) => {
    const el = rowElement(listRef.current, ticker);
    anchor.current = el ? { ticker, top: el.getBoundingClientRect().top } : null;
    setSelected((cur) => (cur === ticker ? null : ticker));
  };
  // 그린 뒤(그리기 전 화면 반영 전) 누른 행이 움직인 만큼 되돌린다 — 위 행 상세가 닫혀 행이 밀려도 같은 자리.
  useLayoutEffect(() => {
    const a = anchor.current;
    anchor.current = null;
    if (!a) return;
    const el = rowElement(listRef.current, a.ticker);
    if (!el) return;
    const delta = el.getBoundingClientRect().top - a.top;
    if (delta !== 0) scrollByDelta(el, delta);
  }, [selected]);

  // 선택 ticker 의 evidence item (NAV·구성종목 선택 상세용). 통합 전 원본 item 에서
  // 첫 항목을 사용 — 목록 표는 이미 ticker 통합(helpers)되어 있으나 NAV·구성종목은
  // 선택 상세에서만 원본 그대로 보여준다(§4.4·§6.2 목록 판정에는 미포함).
  const selectedEvidence: HoldingsMarketEvidenceItem | null = useMemo(() => {
    if (!selected || evidence.phase !== "success") return null;
    return (
      evidence.data.holdings.find((h) => h.ticker === selected) ?? null
    );
  }, [selected, evidence]);

  const built = useMemo(() => {
    if (holdings.phase !== "success" || evidence.phase !== "success") return null;
    return buildRiskEvidenceRows(
      holdings.data.items,
      evidence.data.holdings,
    );
  }, [holdings, evidence]);

  const loading = holdings.phase === "loading" || evidence.phase === "loading";
  const failed = holdings.phase === "error" || evidence.phase === "error";

  const shownRows: RiskEvidenceRow[] = useMemo(() => {
    if (!built) return [];
    // POC5-13 — '하락 구간' 보기 = PC 20저장일 하락 구간에 든 종목(받은 자료로 거름 · 정렬 유지).
    const rows =
      quickView === "need_check"
        ? built.rows.filter((r) => r.need_check)
        : quickView === "decline"
          ? built.rows.filter((r) => r.decline_band?.state)
          : built.rows;
    return sortEvidenceRows(rows, sortKey);
  }, [built, quickView, sortKey]);

  // POC5-13 · POC5-15 — 현재 상태 · 하락 구간 요약(오늘 화면 띠와 같은 공통 판정 함수 · 같은 입력 → 같은 문구).
  // 목록용으로 이미 만든 행을 넘겨 다시 만들지 않는다.
  const risk = useMemo(
    () => riskStateFromQueries(holdings, evidence, built?.rows),
    [holdings, evidence, built],
  );
  const declineSummary = risk?.summary ?? null;

  // POC5-09 — PC 비교 기준일 · 기준일이 달라 현재 비교에서 뺀 종목(응답 선택 필드).
  const basis =
    evidence.phase === "success" ? (evidence.data.price_basis ?? null) : null;

  return (
    <section aria-labelledby="hre-h" className="hre-section card">
      <h2 id="hre-h">보유 ETF 확인 근거</h2>
      <p className="helper">
        보유 ETF 를 하나씩 이어서, 최근 5 · 20저장일 흐름과 같은 기간 KODEX 200 대비, 평가
        정보를 한 화면에서 확인합니다. 값을 수정하거나 저장하지 않는 읽기 전용
        확인 영역입니다.
      </p>

      {loading ? (
        <div className="message info">불러오는 중...</div>
      ) : risk?.combo.holdings === "no_holdings" ? (
        // POC5-15 — 정상 응답의 빈 보유가 실패보다 먼저(PLAN 판정 Q1).
        <div className="message info" data-testid="hre-risk-state-empty">
          <strong>{risk.combo.text}</strong> — 표시할 보유 ETF 가 없습니다.
        </div>
      ) : failed ? (
        // POC5-15 — 오늘 띠와 같은 상태 문구 + 실제 실패한 조회 한 문장(PLAN 판정 Q1).
        <div className="message info" data-testid="hre-risk-state-failed">
          <strong>{risk?.combo.text ?? "자료 확인 필요"}</strong> —{" "}
          {risk?.failed ? FAILURE_TEXT[risk.failed] : "보유 확인 근거 자료를 불러오지 못했습니다."}
        </div>
      ) : !built || built.rows.length === 0 ? (
        <div className="message info">표시할 보유 ETF 가 없습니다.</div>
      ) : (
        <>
          {/* 요약 — 현재 보유 점검 상태 · 하락 구간 · 자료 확인 필요 · 가격 기준일 · 보유 저장 시각 · 계산 가능(E1) */}
          {risk?.summary ? (
            <DeclineSummaryBlock
              v={risk}
              needCheck={built.coverage.need_check}
              calcOk={built.coverage.ok}
              calcTotal={built.coverage.total}
              holdingsAsof={evidence.phase === "success" ? evidence.data.holdings_asof : null}
              marketAsof={evidence.phase === "success" ? evidence.data.market_asof : null}
            />
          ) : null}
          {basis ? (
            <p className="helper" data-testid="hre-price-basis">
              {priceBasisLine(basis)}
            </p>
          ) : null}

          {/* 빠른 보기 — 전체 / 하락 구간 / 자료 확인 필요 (POC5-13 · 급락 신호 빠른보기 없음) */}
          <div className="hre-quickview">
            <button
              type="button"
              className={quickView === "all" ? "active" : ""}
              onClick={() => setQuickView("all")}
            >
              전체
            </button>
            <button
              type="button"
              className={quickView === "decline" ? "active" : ""}
              onClick={() => setQuickView("decline")}
            >
              하락 구간 ({declineSummary?.inBand ?? 0})
            </button>
            <button
              type="button"
              className={quickView === "need_check" ? "active" : ""}
              onClick={() => setQuickView("need_check")}
            >
              자료 확인 필요 ({built.coverage.need_check})
            </button>
          </div>

          {/* POC5-UI-02 — 「보유 현황」 정렬과 같은 양식(선택 묶음 · UI-01 크기 예외). */}
          <div className="holdings-sortbar">
            <span className="holdings-sortbar-label">정렬</span>
            <div className="holdings-sort-seg" role="group" aria-label="확인 근거 정렬 기준">
              {EVIDENCE_SORT_OPTIONS.map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  className={sortKey === key ? "on" : ""}
                  aria-pressed={sortKey === key}
                  onClick={() => setSortKey(key)}
                >
                  {label}
                </button>
              ))}
            </div>
            <span className="holdings-sortbar-hint">
              {sortKey === "weight" ? "큰 값부터" : "작은 값부터"} · 값이 없는 종목은 맨 뒤
              {sortKey === "ret5" || sortKey === "ret20"
                ? " · 이 목록 정렬 = 저장일 변화 기준(「주간 ETF 점검」 순위와 다름)"
                : ""}
            </span>
          </div>

          {/* 2026-08-15 사용자 실화면 직접 지시 — 8컬럼 표 → 하이브리드 행.
              ETF 비교하기(.wb-hrow)와 같은 규칙: 좌측 2단 카드 + 우측 지표 열.
              지표가 5 · 20저장일 둘뿐이라 우측은 2칸 + 라벨이 긴 KODEX 200 대비는
              아랫줄. 데이터 상태는 "확인됨" 이면 배지를 띄우지 않고 "자료 확인 필요"
              일 때만 표시한다(ETF 비교하기 ok 배지와 동일 방침).
              값이 없는 칸을 임의로 채우지 않는 기존 계약(자료 확인 필요 / —)은 그대로.
              POC6-33 E3 — 행마다 묶음(.hre-row-wrap) 안에 행 + 그 행의 상세(누른 행 바로 아래). */}
          <div className="wb-hlist hre-evlist" data-testid="hre-evidence-list" ref={listRef}>
            {shownRows.map((r) => {
              const isSel = selected === r.ticker;
              return (
                <div
                  key={r.ticker}
                  className={`hre-row-wrap${isSel ? " sel" : ""}`}
                  data-row-ticker={r.ticker}
                >
                  <div
                    className={`wb-hrow${isSel ? " sel" : ""}`}
                    role="button"
                    tabIndex={0}
                    aria-expanded={isSel}
                    /* 접근가능 이름을 종목으로 고정한다. 없으면 행 안의 "자료 확인 필요"
                       배지 문구까지 이름에 섞여, 같은 문구를 쓰는 빠른보기 버튼 조회와
                       충돌한다(getByRole 다중 매치). */
                    aria-label={`${r.name ?? r.ticker} 상세 보기`}
                    onClick={() => toggle(r.ticker)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        toggle(r.ticker);
                      }
                    }}
                  >
                    <div className="wb-hcard">
                      <div className="wb-hrow-top">
                        <div className="wb-hrow-name">
                          <span className="hre-name">{r.name ?? r.ticker}</span>
                        </div>
                        <div className="wb-hrow-pnl">
                          <span
                            className="amt"
                            style={{ color: directionColor(r.pnl_rate_pct) }}
                          >
                            {fmtPct(r.pnl_rate_pct)}
                          </span>
                          <span className="rate wb-hmuted">손익률(계좌 합산)</span>
                        </div>
                      </div>
                      <div className="wb-hrow-bot">
                        <div className="wb-hrow-facts">
                          <span className="tk hre-ticker">{r.ticker}</span>
                          <span className="sep">/</span>
                          {r.market_weight_pct === null ? (
                            <span className="wb-hmuted">평가 비중 자료 확인 필요</span>
                          ) : (
                            <span>
                              평가 비중(계좌 합산){" "}
                              <span className="wv">
                                {r.market_weight_pct.toFixed(1)}%
                              </span>
                            </span>
                          )}
                          <span className="sep">/</span>
                          {r.eval_amount === null ? (
                            <span className="wb-hmuted">평가 자료 확인 필요</span>
                          ) : (
                            <span>
                              평가 <span className="wv">{fmtMoney(r.eval_amount)}</span>
                            </span>
                          )}
                        </div>
                      </div>
                      {/* E2 — 기존 하락 구간 · 자료 확인 필요 판정을 '확인 사유' 한 줄로(판정 무변경). */}
                      {r.decline_band?.label || r.need_check ? (
                        <div className="hre-reason">
                          <span className="k">확인 사유 · </span>
                          <span className="wb-hbadges">
                            {r.decline_band?.label ? (
                              <span className="wb-hb band">{r.decline_band.label}</span>
                            ) : null}
                            {r.need_check ? (
                              <span className="wb-hb warn">자료 확인 필요</span>
                            ) : null}
                          </span>
                        </div>
                      ) : null}
                    </div>
                    <div className="wb-hmetrics">
                      <div className="wb-hm2">
                        <div className="wb-hm-cell">
                          <span className="k">최근 5저장일</span>
                          <span
                            className="v"
                            style={{ color: directionColor(r.return_5d_pct) }}
                          >
                            {stale(r) ? "—" : fmtPct(r.return_5d_pct)}
                          </span>
                        </div>
                        <div className="wb-hm-cell">
                          <span className="k">20저장일</span>
                          <span
                            className="v"
                            style={{ color: directionColor(r.return_20d_pct) }}
                          >
                            {stale(r) ? "—" : fmtPct(r.return_20d_pct)}
                          </span>
                        </div>
                      </div>
                      <div className="wb-hm-ex">
                        <span className="k">같은 기간 KODEX 200 대비(%p)</span>
                        <span
                          className="v"
                          style={{
                            color: directionColor(r.excess_vs_kodex200_20d_pctp),
                          }}
                        >
                          {stale(r) ? "—" : fmtPctp(r.excess_vs_kodex200_20d_pctp)}
                        </span>
                      </div>
                    </div>
                  </div>
                  {isSel ? (
                    <EvidenceDetail
                      row={r}
                      item={selectedEvidence}
                      basis={basis}
                      weekly={weeklyShown}
                      topnBasis={
                        evidence.phase === "success" ? evidence.data.topn_basis : null
                      }
                    />
                  ) : null}
                </div>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
