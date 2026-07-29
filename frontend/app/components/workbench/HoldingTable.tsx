"use client";

// POC3-02 Judgment Workbench — 보유 표 (§7.6 · KS-10 분리).
// 같은 ticker 다계좌 집계(종목당 한 행) + Evidence 기반 1M/3M/KODEX초과/상태.

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

  const COLS = 14;
  return (
    <table className="wb-table">
      <thead>
        <tr>
          <th>ETF</th>
          <th>평가액</th>
          <th>비중</th>
          <th>평가손익</th>
          <th>평가수익률</th>
          <th>현재가</th>
          <th>일간</th>
          <th>1M</th>
          <th>3M</th>
          <th>KODEX초과</th>
          <th>후보포함</th>
          <th>NAV</th>
          <th>구성종목</th>
          <th>Evidence</th>
        </tr>
      </thead>
      <tbody>
        {stale && (
          <tr>
            <td colSpan={COLS} style={{ color: "var(--warn)", fontSize: 12 }}>
              ⚠ 이전 조회값 (재조회 실패 — 최신 아님)
            </td>
          </tr>
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
          // NAV·구성종목 상태를 별도 열로 분리 (어느 근거가 불가한지 식별 · A-1).
          const navSt = ev?.nav_discount?.status ?? null;
          const conSt = ev?.constituents_overlap?.status ?? null;
          const evState = holdingEvidenceState(ev, evid.phase);
          const evMissing = evState === "unavailable";
          const isSel = selected === r.ticker;
          return (
            <tr
              key={r.ticker}
              className={isSel ? "wb-row-sel" : ""}
              onClick={() => onSelect(r.ticker)}
              style={{ cursor: "pointer" }}
            >
              <td>
                {r.name ?? "—"}{" "}
                <code style={{ color: "var(--muted)" }}>{r.ticker}</code>
                {r.count > 1 && (
                  <span style={{ color: "var(--muted)", fontSize: 11 }}>
                    {" "}
                    ({r.count}계좌 합산)
                  </span>
                )}
              </td>
              <td>
                {r.evalOk === 0 ? "확인 불가" : fmtAmountSummary(r.evalAmount)}
                {r.evalOk > 0 && r.evalOk < r.count && (
                  <span style={{ color: "var(--warn)", fontSize: 11 }}>
                    {" "}
                    ({r.evalOk}/{r.count})
                  </span>
                )}
              </td>
              <td>
                {r.weightOk === 0 ? "—" : fmtPlainPct(r.weight)}
                {r.weightOk > 0 && r.weightOk < r.count && (
                  <span style={{ color: "var(--warn)", fontSize: 11 }}>
                    {" "}
                    ({r.weightOk}/{r.count})
                  </span>
                )}
              </td>
              <td style={{ color: directionColor(r.pnlAmount) }}>
                {r.pnlOk === 0 ? "확인 불가" : fmtAmountSummary(r.pnlAmount)}
                {r.pnlOk > 0 && r.pnlOk < r.count && (
                  <span style={{ color: "var(--warn)", fontSize: 11 }}>
                    {" "}
                    ({r.pnlOk}/{r.count})
                  </span>
                )}
              </td>
              <td style={{ color: directionColor(pnlRate) }}>
                {r.count > 1 ? (
                  <span style={{ color: "var(--muted)", fontSize: 12 }}>계좌별 상이</span>
                ) : (
                  fmtSignedPct(pnlRate)
                )}
              </td>
              <td>{r.currentPrice == null ? "—" : fmtIndex(r.currentPrice)}</td>
              {/* 일간 수익률: 현재 Holdings 응답에 일간 필드가 없어 항상 미제공.
                  §7.6 명시 열이므로 열은 두되 값 없음 사유(—)를 표시한다. */}
              <td style={{ color: "var(--muted)" }}>—</td>
              <td style={{ color: directionColor(om) }}>{fmtSignedPct(om)}</td>
              <td style={{ color: directionColor(tm) }}>{fmtSignedPct(tm)}</td>
              <td style={{ color: directionColor(ex) }}>{fmtSignedPct(ex)}</td>
              <td>
                {candSt === "yes" ? (
                  <span style={{ color: "var(--ok)" }}>◆ 후보</span>
                ) : candSt === "unknown" ? (
                  <span style={{ color: "var(--danger)", fontSize: 12 }}>확인 불가</span>
                ) : (
                  "—"
                )}
              </td>
              <td>{statusCell(navSt, evMissing)}</td>
              <td>{statusCell(conSt, evMissing)}</td>
              <td>{evidenceBadge(evState)}</td>
            </tr>
          );
        })}
        {rows.length === 0 && (
          <tr>
            <td colSpan={COLS} className="wb-muted">
              조건에 맞는 보유 종목 없음
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

// NAV / 구성종목 개별 상태 셀 — ok=정상, 없음/부재=확인 불가.
function statusCell(status: string | null, evMissing: boolean) {
  if (evMissing || status == null) {
    return <span style={{ color: "var(--danger)" }}>확인 불가</span>;
  }
  if (status === "ok") {
    return <span style={{ color: "var(--muted)" }}>정상</span>;
  }
  return <span style={{ color: "var(--warn)", fontWeight: 600 }}>⚠ {status}</span>;
}

// Evidence 전체 상태 배지 — 종목별 근거 전반을 한눈에 (A-1).
function evidenceBadge(state: HoldingEvidenceState) {
  if (state === "ok")
    return <span style={{ color: "var(--muted)" }}>정상</span>;
  if (state === "attention")
    return <span style={{ color: "var(--warn)", fontWeight: 600 }}>⚠ 확인</span>;
  if (state === "unavailable")
    return <span style={{ color: "var(--danger)", fontWeight: 600 }}>확인 불가</span>;
  return <span style={{ color: "var(--muted)" }}>확인 중</span>;
}

