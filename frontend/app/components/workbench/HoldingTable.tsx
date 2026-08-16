"use client";

// POC3-02 Judgment Workbench — 보유 표 (§7.6 · KS-10 분리).
// 같은 ticker 다계좌 집계(종목당 한 행) + Evidence 기반 1M/3M/KODEX초과/상태.
//
// 2026-08-12 사용자 실화면 직접 지시 — 14컬럼 가로 표 → 하이브리드 행으로 전환.
//   좌측: 보유 현황(.hld-row)과 같은 2단 카드. 우측: 비교 지표 고정 열.
//   상태 4종(후보포함 / NAV / 구성종목 / Evidence)은 배지로 묶는다.
//   집계·상태 판정 로직은 전부 기존 그대로 — 표시 형태만 바뀐다.

import type {
  EnrichedHoldingsResult,
  HoldingsMarketEvidenceResponse,
} from "@/lib/api";
import type { QueryState } from "@/lib/api/queryCache";
import {
  fmtSignedPct,
  fmtPlainPct,
  fmtIndex,
  fmtAmountSummary,
  directionColor,
  evidenceByTicker,
  evidenceReturn,
  evidenceExcess,
  holdingEvidenceState,
  relationState,
  type HoldingEvidenceState,
} from "./helpers";

type QuickFilter = "all" | "held" | "comparable" | "attention";

type AggHolding = {
  ticker: string;
  name: string | null;
  evalAmount: number | null;
  evalOk: number;
  pnlAmount: number | null;
  pnlOk: number;
  currentPrice: number | null;
  weight: number | null;
  weightOk: number;
  count: number;
};

function aggregateHoldings(items: EnrichedHoldingsResult["items"]): AggHolding[] {
  const map = new Map<string, AggHolding>();
  for (const h of items) {
    let a = map.get(h.ticker);
    if (!a) {
      a = {
        ticker: h.ticker,
        name: h.name,
        evalAmount: null,
        evalOk: 0,
        pnlAmount: null,
        pnlOk: 0,
        currentPrice: h.current_price,
        weight: null,
        weightOk: 0,
        count: 0,
      };
      map.set(h.ticker, a);
    }
    a.count += 1;
    if (h.eval_amount != null) {
      a.evalAmount = (a.evalAmount ?? 0) + h.eval_amount;
      a.evalOk += 1;
    }
    if (h.pnl_amount != null) {
      a.pnlAmount = (a.pnlAmount ?? 0) + h.pnl_amount;
      a.pnlOk += 1;
    }
    if (h.market_weight_pct != null) {
      a.weight = (a.weight ?? 0) + h.market_weight_pct;
      a.weightOk += 1;
    }
    if (a.currentPrice == null) a.currentPrice = h.current_price;
  }
  return Array.from(map.values());
}

// 부분 평가 표기 — N개 계좌 중 M개만 계산됨을 값 옆에 붙인다.
// 부분값을 전체값처럼 보이지 않게 하는 기존 계약 (검증자 지적 반영분).
function PartialMark({ ok, count }: { ok: number; count: number }) {
  if (ok <= 0 || ok >= count) return null;
  return (
    <span className="wb-hpartial">
      ({ok}/{count})
    </span>
  );
}

// ── 보유 표 (§7.6) ─────────────────────────────────────────────────────────
export function HoldingTable({
  hold,
  evid,
  evidenceItems,
  candTickers,
  filter,
  query,
  selected,
  onSelect,
}: {
  hold: QueryState<EnrichedHoldingsResult>;
  evid: QueryState<HoldingsMarketEvidenceResponse>;
  evidenceItems: HoldingsMarketEvidenceResponse["holdings"] | undefined;
  candTickers: Set<string> | undefined;
  filter: QuickFilter;
  query: string;
  selected: string | null;
  onSelect: (t: string) => void;
}) {
  if (hold.phase !== "success") {
    if (hold.phase === "error") return <p className="wb-danger">보유 확인 실패</p>;
    return <p className="wb-muted">보유 확인 중...</p>;
  }

  let rows = aggregateHoldings(hold.data.items);
  if (filter === "attention") {
    rows = rows.filter((r) => {
      const ev = evidenceByTicker(evidenceItems, r.ticker);
      // Evidence 부재/실패도 확인 필요 (정상 아님 · A-1). evid 조회 성공인데
      // 이 종목 Evidence 가 없으면 "확인 불가" → 확인 필요 필터에 포함.
      const st = holdingEvidenceState(ev, evid.phase);
      return st === "attention" || st === "unavailable";
    });
  }
  if (query.trim()) {
    const q = query.trim().toLowerCase();
    rows = rows.filter(
      (r) =>
        r.ticker.toLowerCase().includes(q) ||
        (r.name ?? "").toLowerCase().includes(q),
    );
  }

  const stale =
    hold.stale || (evid.phase === "success" && evid.stale) || false;

  return (
    <div className="wb-hlist" data-testid="wb-holding-list">
      {stale && (
        <div className="wb-hstale">⚠ 이전 조회값 (재조회 실패 — 최신 아님)</div>
      )}
      {rows.map((r) => {
        const ev = evidenceByTicker(evidenceItems, r.ticker);
        // 후보 포함 3-state: **현재 후보 목록** ∩ 이 보유 ticker. 후보 조회
        // 실패(candTickers undefined)면 "확인 불가" — "미포함(—)" 아님 (A-1(4)).
        const candSt = relationState(candTickers, r.ticker);
        // 평가수익률: 단일 계좌면 Evidence snapshot 값. 다계좌 집계는 대표값이
        // 애매하므로 "계좌별 상이" 로 표시 (첫 값을 전체처럼 보이지 않게 · B-1).
        const pnlRate = r.count > 1 ? null : ev?.holding?.pnl_rate_pct ?? null;
        const om = evidenceReturn(ev, "one_month");
        const tm = evidenceReturn(ev, "three_month");
        const ex = evidenceExcess(ev);
        // NAV·구성종목 상태를 별도 배지로 분리 (어느 근거가 불가한지 식별 · A-1).
        const navSt = ev?.nav_discount?.status ?? null;
        const conSt = ev?.constituents_overlap?.status ?? null;
        const evState = holdingEvidenceState(ev, evid.phase);
        const evMissing = evState === "unavailable";
        const isSel = selected === r.ticker;
        return (
          <div
            key={r.ticker}
            className={`wb-hrow${isSel ? " sel" : ""}`}
            role="button"
            tabIndex={0}
            aria-pressed={isSel}
            onClick={() => onSelect(r.ticker)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(r.ticker);
              }
            }}
          >
            {/* 좌측 카드 — 보유 현황(.hld-row) 과 같은 2단 × 2열 */}
            <div className="wb-hcard">
              <div className="wb-hrow-top">
                <div className="wb-hrow-name">
                  {r.name ?? "—"}
                  <span className="wb-hbadges">
                    {r.count > 1 && (
                      <span className="wb-hb mute">{r.count}계좌 합산</span>
                    )}
                    <CandidateBadge state={candSt} />
                    <StatusBadge label="NAV" status={navSt} evMissing={evMissing} />
                    <StatusBadge
                      label="구성종목"
                      status={conSt}
                      evMissing={evMissing}
                    />
                    <EvidenceBadge state={evState} />
                  </span>
                </div>
                <div className="wb-hrow-pnl">
                  {r.pnlOk === 0 ? (
                    <span className="amt wb-hmuted">확인 불가</span>
                  ) : (
                    <span
                      className="amt"
                      style={{ color: directionColor(r.pnlAmount) }}
                    >
                      {fmtAmountSummary(r.pnlAmount)}
                    </span>
                  )}
                  <PartialMark ok={r.pnlOk} count={r.count} />
                  {r.count > 1 ? (
                    <span className="rate wb-hmuted">계좌별 상이</span>
                  ) : (
                    <span className="rate" style={{ color: directionColor(pnlRate) }}>
                      {fmtSignedPct(pnlRate)}
                    </span>
                  )}
                </div>
              </div>
              <div className="wb-hrow-bot">
                <div className="wb-hrow-facts">
                  <span className="tk">{r.ticker}</span>
                  <span className="sep">/</span>
                  {r.weightOk === 0 ? (
                    <span className="wb-hmuted">비중 —</span>
                  ) : (
                    <span>
                      비중 <span className="wv">{fmtPlainPct(r.weight)}</span>
                      <PartialMark ok={r.weightOk} count={r.count} />
                    </span>
                  )}
                  <span className="sep">/</span>
                  {r.evalOk === 0 ? (
                    <span className="wb-hmuted">평가액 확인 불가</span>
                  ) : (
                    <span>
                      평가액{" "}
                      <span className="wv">{fmtAmountSummary(r.evalAmount)}</span>
                      <PartialMark ok={r.evalOk} count={r.count} />
                    </span>
                  )}
                </div>
                <div className="wb-hrow-price">
                  {r.currentPrice == null ? (
                    <span className="wb-hmuted">현재 —</span>
                  ) : (
                    <>
                      현재 <b>{fmtIndex(r.currentPrice)}</b>
                    </>
                  )}
                </div>
              </div>
            </div>
            {/* 우측 비교 지표 열 */}
            <div className="wb-hmetrics">
              <div className="wb-hm3">
                {/* 일간 수익률: 현재 Holdings 응답에 일간 필드가 없어 항상 미제공.
                    §7.6 명시 항목이므로 자리는 두되 값 없음(—)을 표시한다. */}
                <div className="wb-hm-cell">
                  <span className="k">일간</span>
                  <span className="v wb-hmuted">—</span>
                </div>
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
              </div>
              <div className="wb-hm-ex">
                <span className="k">KODEX초과</span>
                <span className="v" style={{ color: directionColor(ex) }}>
                  {fmtSignedPct(ex)}
                </span>
              </div>
            </div>
          </div>
        );
      })}
      {rows.length === 0 && (
        <p className="wb-muted">조건에 맞는 보유 종목 없음</p>
      )}
    </div>
  );
}

// 후보 포함 3-state 배지 — 미포함과 확인 불가를 구분해 표시 (A-1(4)).
function CandidateBadge({ state }: { state: ReturnType<typeof relationState> }) {
  if (state === "yes") return <span className="wb-hb ok">후보 포함</span>;
  if (state === "unknown")
    return <span className="wb-hb danger">후보 확인 불가</span>;
  return <span className="wb-hb mute">후보 미포함</span>;
}

// NAV / 구성종목 개별 상태 배지 — 없음/부재=확인 불가.
// 2026-08-16: 정상(ok)이면 배지를 띄우지 않는다. 후보 탭의 데이터 상태 배지와
//   같은 규칙 — 모든 행에 뜨는 "정상" 배지는 정보량이 없고 종목명 줄만 길게 한다.
//   이상이 있을 때만 눈에 띄게 하는 것이 이 화면의 목적에 맞는다.
function StatusBadge({
  label,
  status,
  evMissing,
}: {
  label: string;
  status: string | null;
  evMissing: boolean;
}) {
  if (evMissing || status == null) {
    return <span className="wb-hb danger">{label} 확인 불가</span>;
  }
  if (status === "ok") {
    return null;
  }
  return (
    <span className="wb-hb warn">
      ⚠ {label} {status}
    </span>
  );
}

// Evidence 전체 상태 배지 — 종목별 근거 전반을 한눈에 (A-1).
function EvidenceBadge({ state }: { state: HoldingEvidenceState }) {
  // 정상이면 배지 없음 (StatusBadge 와 동일 규칙).
  if (state === "ok") return null;
  if (state === "attention") return <span className="wb-hb warn">⚠ 근거 확인</span>;
  if (state === "unavailable")
    return <span className="wb-hb danger">근거 확인 불가</span>;
  return <span className="wb-hb mute">근거 확인 중</span>;
}
