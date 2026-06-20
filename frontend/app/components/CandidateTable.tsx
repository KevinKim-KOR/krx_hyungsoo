"use client";

// Market Discovery 통합 후보 테이블 (POC2 — 2026-05-22 KS-10 회피 분리 / 2026-06-08 UI 정리).
//
// 2026-06-08 UI 정리 (사용자 요청):
// - 티커 / ETF명 컬럼은 이전처럼 분리 유지 (라운드 2 — 사용자 정정: 티커/ETF명
//   합치기는 MarketContextCard 의 KODEX200/KOSPI 표기 정정을 의도한 것이었음).
// - source / status / 정렬 기준 기간 / 태그 컬럼 제거.
// - 6개월 / 12개월 / 1년 / 3년 수익률 컬럼 추가 (표시 전용, 정렬 X).
// - asof 컬럼 제거 (사용자 요청 — NAV/시장가/괴리율만 노출).
//
// 본 컴포넌트는 표시 책임만 — 정렬 / fetch / state 는 부모 (MarketDiscoveryView)
// 가 보유한다 (lift state up).

import { useState } from "react";
import type {
  MarketBasis,
  MarketCandidate,
  MarketOrder,
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
      style={{ width: 110, textAlign: "right", cursor: "pointer" }}
      className={`market-topn-sortable ${active ? "basis-active" : ""}`}
      onClick={() => onSort(column)}
      title="클릭하여 정렬"
    >
      {label}
      {active ? <span className="market-topn-sort-indicator">{indicator}</span> : null}
    </th>
  );
}

// 2026-06-20 ML 축1 — 상대상승 참고점수 정렬 (지시문 §9). frontend 로컬 정렬만
// (신규 API 정렬 파라미터 추가 금지). 점수 null 후보는 항상 점수 있는 후보 뒤로.
type ScoreSort = "off" | "desc" | "asc";

function sortByRelativeUpside(
  candidates: MarketCandidate[],
  direction: "desc" | "asc",
): MarketCandidate[] {
  const withScore: MarketCandidate[] = [];
  const withoutScore: MarketCandidate[] = [];
  for (const c of candidates) {
    if (
      c.relative_upside_score !== null &&
      c.relative_upside_score !== undefined
    ) {
      withScore.push(c);
    } else {
      withoutScore.push(c);
    }
  }
  withScore.sort((a, b) => {
    const av = a.relative_upside_score as number;
    const bv = b.relative_upside_score as number;
    return direction === "desc" ? bv - av : av - bv;
  });
  return [...withScore, ...withoutScore];
}

export default function CandidateTable({
  candidates,
  basis,
  order,
  onSort,
  relativeUpsideScoreStatus,
  relativeUpsideScoreUserNotice,
}: {
  candidates: MarketCandidate[];
  basis: MarketBasis;
  order: MarketOrder;
  onSort: (column: MarketBasis) => void;
  // 2026-06-20 ML 축1 — 상대상승 참고점수 top-level 상태 / 사용자 고지.
  relativeUpsideScoreStatus?: string | null;
  relativeUpsideScoreUserNotice?: string | null;
}) {
  const [scoreSort, setScoreSort] = useState<ScoreSort>("off");
  if (candidates.length === 0) {
    return (
      <div className="card market-topn-card">
        <div className="message info">표시할 항목이 없습니다.</div>
      </div>
    );
  }
  const displayed =
    scoreSort === "off"
      ? candidates
      : sortByRelativeUpside(candidates, scoreSort);
  const onScoreHeaderClick = () => {
    setScoreSort((prev) =>
      prev === "off" ? "desc" : prev === "desc" ? "asc" : "off",
    );
  };
  const scoreIndicator =
    scoreSort === "desc" ? "↓" : scoreSort === "asc" ? "↑" : "";
  return (
    <div className="card market-topn-card">
      <table className="market-topn-table market-candidate-table">
        <thead>
          <tr>
            <th style={{ width: 56 }}>순위</th>
            <th style={{ width: 90 }}>티커</th>
            <th>ETF명</th>
            <SortableHeader
              label="일간"
              column="daily"
              basis={basis}
              order={order}
              onSort={onSort}
            />
            <SortableHeader
              label="1개월"
              column="one_month"
              basis={basis}
              order={order}
              onSort={onSort}
            />
            <SortableHeader
              label="3개월"
              column="three_month"
              basis={basis}
              order={order}
              onSort={onSort}
            />
            {/* 2026-06-08 신규 (표시 전용) — 정렬 X */}
            <th style={{ width: 100, textAlign: "right" }}>6개월</th>
            <th style={{ width: 100, textAlign: "right" }}>12개월</th>
            <th style={{ width: 100, textAlign: "right" }}>1년</th>
            <th style={{ width: 100, textAlign: "right" }}>3년</th>
            <th style={{ width: 110, textAlign: "right" }}>KODEX200 대비 1m</th>
            <th style={{ width: 110, textAlign: "right" }}>KODEX200 대비 3m</th>
            {/* 2026-06-08 NAV / Discount Display FIX — 후보 row 에 NAV 직접 노출 */}
            <th style={{ width: 95, textAlign: "right" }}>NAV</th>
            <th style={{ width: 95, textAlign: "right" }}>시장가</th>
            <th style={{ width: 100, textAlign: "right" }}>괴리율</th>
            {/* 2026-06-20 ML 축1 — 상대상승 참고점수 v0 (지시문 §9). 로컬 정렬
                토글: off → desc → asc → off. 점수 null 후보는 항상 뒤로. */}
            <th
              style={{ width: 120, textAlign: "right", cursor: "pointer" }}
              className={`market-topn-sortable ${scoreSort !== "off" ? "basis-active" : ""}`}
              onClick={onScoreHeaderClick}
              title="클릭하여 상대상승 참고점수 기준 정렬 (off → 내림차 → 오름차)"
            >
              상대상승 참고점수
              {scoreSort !== "off" ? (
                <span className="market-topn-sort-indicator">
                  {scoreIndicator}
                </span>
              ) : null}
            </th>
            <th style={{ width: 95, textAlign: "right" }}>고점 대비</th>
            <th style={{ width: 280 }}>점수 근거</th>
          </tr>
        </thead>
        <tbody>
          {displayed.map((c, idx) => {
            const dailyRet = c.returns?.daily?.return_pct ?? null;
            const oneRet = c.returns?.one_month?.return_pct ?? null;
            const threeRet = c.returns?.three_month?.return_pct ?? null;
            // 2026-06-08 신규 기간 (표시 전용)
            const sixRet = c.returns?.six_month?.return_pct ?? null;
            const twelveRet = c.returns?.twelve_month?.return_pct ?? null;
            // "1년" = backend twelve_month 와 동의어. 동일 값 또 표시.
            const oneYearRet = c.returns?.twelve_month?.return_pct ?? null;
            const threeYearRet = c.returns?.three_year?.return_pct ?? null;
            const exKodex1m = c.excess_return?.vs_kodex200_1m_pctp ?? null;
            const exKodex3m = c.excess_return?.vs_kodex200_3m_pctp ?? null;
            const nav = c.data_quality?.nav_discount ?? null;
            const navVal = nav?.nav ?? null;
            const priceVal = nav?.market_price ?? null;
            const discountVal = nav?.discount_rate_pct ?? null;
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
                <td style={{ textAlign: "right", color: returnPctColor(sixRet) }}>
                  {fmtPct(sixRet)}
                </td>
                <td style={{ textAlign: "right", color: returnPctColor(twelveRet) }}>
                  {fmtPct(twelveRet)}
                </td>
                <td style={{ textAlign: "right", color: returnPctColor(oneYearRet) }}>
                  {fmtPct(oneYearRet)}
                </td>
                <td style={{ textAlign: "right", color: returnPctColor(threeYearRet) }}>
                  {fmtPct(threeYearRet)}
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
                {/* 2026-06-20 ML 축1 — 상대상승 참고점수 / 고점 대비 / 점수 근거 */}
                <td style={{ textAlign: "right" }}>
                  {c.relative_upside_score !== null &&
                  c.relative_upside_score !== undefined ? (
                    <strong>{c.relative_upside_score.toFixed(1)}</strong>
                  ) : (
                    <span style={{ color: "var(--muted)" }}>점수 미생성</span>
                  )}
                </td>
                <td
                  style={{
                    textAlign: "right",
                    color: returnPctColor(
                      c.drawdown_20d != null ? c.drawdown_20d * 100 : null,
                    ),
                  }}
                >
                  {c.drawdown_20d != null
                    ? fmtPct(c.drawdown_20d * 100)
                    : DASH}
                </td>
                <td style={{ fontSize: "0.82rem" }}>
                  {c.relative_upside_reasons &&
                  c.relative_upside_reasons.length > 0 ? (
                    <ul style={{ margin: 0, paddingLeft: "1.1em" }}>
                      {c.relative_upside_reasons.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  ) : (
                    <span style={{ color: "var(--muted)" }}>-</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {/* 2026-06-20 ML 축1 — 사용자 고지 (지시문 §9 끝). 점수 미생성 상태에서는
          backend 가 보낸 status / notice 를 그대로 표시. */}
      {relativeUpsideScoreUserNotice ? (
        <p
          className="helper"
          style={{
            marginTop: 8,
            fontSize: "0.78rem",
            color: "var(--muted)",
            borderTop: "1px dashed var(--border)",
            paddingTop: 6,
          }}
        >
          {relativeUpsideScoreUserNotice}
          {relativeUpsideScoreStatus && relativeUpsideScoreStatus !== "ok" ? (
            <>
              {" "}
              <span style={{ color: "var(--warn)" }}>
                (현재 상태: {relativeUpsideScoreStatus} — 점수 미생성)
              </span>
            </>
          ) : null}
        </p>
      ) : null}
      <p
        className="helper"
        style={{ marginTop: 6, fontSize: "0.78rem" }}
      >
        일간 / 1개월 / 3개월 컬럼 헤더는 클릭으로 정렬됩니다. 6개월 / 12개월 / 1년 /
        3년은 표시 전용 (정렬 X — 신규 상장 ETF 는 시계열 미적재로 빈 값일 수 있습니다).
        전체 ETF NAV 조회는 Data Status 화면에서 가능합니다.
      </p>
    </div>
  );
}
