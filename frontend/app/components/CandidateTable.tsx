"use client";

// Market Discovery 통합 후보 테이블 (POC2 — 2026-05-22 KS-10 회피 분리).
//
// 별도 파일로 분리한 이유:
// MarketDiscoveryView.tsx 가 KS-10 near 850 라인 (856) 에 진입했고,
// 본 STEP 의 KODEX200 대비 1m/3m 컬럼 추가가 직접 원인. 통합 테이블 책임을
// 분리해 MD 라인 수를 다시 near 미만으로 낮춘다 (지시문 §20 / KS-10).
//
// 본 컴포넌트는 표시 책임만 — 정렬 / fetch / state 는 부모 (MarketDiscoveryView)
// 가 보유한다 (lift state up).

import type {
  MarketBasis,
  MarketCandidate,
  MarketOrder,
  MarketProductTag,
} from "@/lib/api";

const DASH = "-";

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

function SortableHeader({
  label,
  column,
  basis,
  order,
  onSort,
}: {
  label: string;
  column: MarketBasis;
  basis: MarketBasis;
  order: MarketOrder;
  onSort: (column: MarketBasis) => void;
}) {
  const active = basis === column;
  const indicator = active ? (order === "desc" ? "↓" : "↑") : "";
  return (
    <th
      style={{ width: 130, textAlign: "right", cursor: "pointer" }}
      className={`market-topn-sortable ${active ? "basis-active" : ""}`}
      onClick={() => onSort(column)}
      title="클릭하여 정렬"
    >
      {label}
      {active ? <span className="market-topn-sort-indicator">{indicator}</span> : null}
    </th>
  );
}

export default function CandidateTable({
  candidates,
  basis,
  order,
  onSort,
}: {
  candidates: MarketCandidate[];
  basis: MarketBasis;
  order: MarketOrder;
  onSort: (column: MarketBasis) => void;
}) {
  if (candidates.length === 0) {
    return (
      <div className="card market-topn-card">
        <div className="message info">표시할 항목이 없습니다.</div>
      </div>
    );
  }
  return (
    <div className="card market-topn-card">
      <table className="market-topn-table market-candidate-table">
        <thead>
          <tr>
            <th style={{ width: 56 }}>순위</th>
            <th style={{ width: 90 }}>티커</th>
            <th>ETF명</th>
            <SortableHeader
              label="일간 수익률"
              column="daily"
              basis={basis}
              order={order}
              onSort={onSort}
            />
            <SortableHeader
              label="1개월 수익률"
              column="one_month"
              basis={basis}
              order={order}
              onSort={onSort}
            />
            <SortableHeader
              label="3개월 수익률"
              column="three_month"
              basis={basis}
              order={order}
              onSort={onSort}
            />
            <th style={{ width: 110, textAlign: "right" }}>KODEX 200 대비 1m (%p)</th>
            <th style={{ width: 110, textAlign: "right" }}>KODEX 200 대비 3m (%p)</th>
            {/* 2026-06-08 NAV / Discount Display FIX (지시문 §4.1 / §5 매트릭스) —
                후보 row 에 NAV 직접 표시. asof / source / status 도 tooltip 이 아닌
                직접 컬럼으로 노출 (검증자 A-1 FIX, 2026-06-08 라운드 2). */}
            <th style={{ width: 95, textAlign: "right" }}>NAV</th>
            <th style={{ width: 95, textAlign: "right" }}>시장가</th>
            <th style={{ width: 100, textAlign: "right" }}>괴리율</th>
            <th style={{ width: 100 }}>asof</th>
            <th style={{ width: 130 }}>source</th>
            <th style={{ width: 90 }}>status</th>
            <th style={{ width: 200 }}>정렬 기준 기간</th>
            <th style={{ width: 160 }}>태그</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c, idx) => {
            const dailyRet = c.returns?.daily?.return_pct ?? null;
            const oneRet = c.returns?.one_month?.return_pct ?? null;
            const threeRet = c.returns?.three_month?.return_pct ?? null;
            const selStart = c.selected_basis_start_date;
            const selEnd = c.selected_basis_end_date;
            const tags = (c.tags ?? []) as MarketProductTag[];
            const exKodex1m = c.excess_return?.vs_kodex200_1m_pctp ?? null;
            const exKodex3m = c.excess_return?.vs_kodex200_3m_pctp ?? null;
            const nav = c.data_quality?.nav_discount ?? null;
            const navVal = nav?.nav ?? null;
            const priceVal = nav?.market_price ?? null;
            const discountVal = nav?.discount_rate_pct ?? null;
            const navStatus = nav?.status ?? "unavailable";
            const asofVal = nav?.asof ?? null;
            const sourceVal = nav?.source ?? null;
            const flagVal = nav?.flag ?? null;
            return (
              <tr key={`${c.rank ?? "x"}-${c.ticker ?? "x"}-${idx}`}>
                <td>{fmtNum(c.rank)}</td>
                <td>{c.ticker ? <code>{c.ticker}</code> : DASH}</td>
                <td>{fmt(c.name)}</td>
                <td
                  style={{ textAlign: "right", color: returnPctColor(dailyRet) }}
                  className={basis === "daily" ? "basis-active" : undefined}
                >
                  {fmtPct(dailyRet)}
                </td>
                <td
                  style={{ textAlign: "right", color: returnPctColor(oneRet) }}
                  className={basis === "one_month" ? "basis-active" : undefined}
                >
                  {fmtPct(oneRet)}
                </td>
                <td
                  style={{ textAlign: "right", color: returnPctColor(threeRet) }}
                  className={basis === "three_month" ? "basis-active" : undefined}
                >
                  {fmtPct(threeRet)}
                </td>
                <td style={{ textAlign: "right", color: returnPctColor(exKodex1m) }}>
                  {fmtPct(exKodex1m)}
                </td>
                <td style={{ textAlign: "right", color: returnPctColor(exKodex3m) }}>
                  {fmtPct(exKodex3m)}
                </td>
                <td style={{ textAlign: "right" }}>
                  {navVal != null ? Math.round(navVal).toLocaleString() : DASH}
                </td>
                <td style={{ textAlign: "right" }}>
                  {priceVal != null
                    ? Math.round(priceVal).toLocaleString()
                    : DASH}
                </td>
                <td style={{ textAlign: "right" }}>
                  {discountVal != null ? (
                    <span style={{ color: returnPctColor(discountVal) }}>
                      {fmtPct(discountVal)}
                      {flagVal ? (
                        <>
                          {" "}
                          <span
                            style={{
                              fontSize: "0.75rem",
                              color: "var(--warn)",
                            }}
                          >
                            {flagVal}
                          </span>
                        </>
                      ) : null}
                    </span>
                  ) : (
                    <span style={{ color: "var(--muted)" }}>-</span>
                  )}
                </td>
                <td style={{ fontSize: "0.78rem" }}>{asofVal ?? DASH}</td>
                <td style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
                  {sourceVal ?? DASH}
                </td>
                <td style={{ fontSize: "0.78rem" }}>{navStatus}</td>
                <td>{selStart && selEnd ? `${selStart} → ${selEnd}` : DASH}</td>
                <td>
                  {tags.length > 0 ? (
                    <TagBadges tags={tags} />
                  ) : (
                    <span className="market-topn-tag-none">일반</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p
        className="helper"
        style={{ marginTop: 6, fontSize: "0.78rem" }}
      >
        NAV / 시장가 / 괴리율 / asof / source / status 는 모두 직접 컬럼으로 표시됩니다.
        전체 ETF 조회는 Data Status 화면에서 가능합니다.
      </p>
    </div>
  );
}
