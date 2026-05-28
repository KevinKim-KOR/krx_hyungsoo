"use client";

// ETF Exposure / 중복률 탭 (POC2 — 2026-05-27).
//
// 표시 항목 (지시문 §6.2):
// - ETF 쌍별 common_count_top10 / weighted_overlap_pct / common_holdings.
// - 반복 등장 핵심 종목 (appears_in_etf_count + per-ETF 비중).

import type { ConstituentsAnalysisResponse } from "@/lib/api";

const DASH = "-";

function fmtPctp(value: number | null | undefined): string {
  if (value === null || value === undefined) return DASH;
  return `${value.toFixed(2)}%`;
}

interface Props {
  analysis: ConstituentsAnalysisResponse | null;
}

export default function OverlapTab({ analysis }: Props) {
  if (!analysis) {
    return (
      <div className="card">
        <div className="message info">
          [구성종목] 탭에서 수집을 먼저 실행하세요. 분석 결과가 있어야 중복률을
          계산할 수 있습니다.
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="card">
        <h2>ETF 쌍별 중복률 (Top 10 기준)</h2>
        {analysis.overlap_matrix.length === 0 ? (
          <div className="helper">표시할 쌍이 없습니다.</div>
        ) : (
          <table className="market-topn-table">
            <thead>
              <tr>
                <th>ETF A</th>
                <th>ETF B</th>
                <th style={{ textAlign: "right", width: 110 }}>공통 종목 수</th>
                <th style={{ textAlign: "right", width: 120 }}>비중 중복률</th>
                <th>공통 핵심 종목</th>
              </tr>
            </thead>
            <tbody>
              {analysis.overlap_matrix.map((p, idx) => (
                <tr key={`${p.left_ticker}-${p.right_ticker}-${idx}`}>
                  <td><code>{p.left_ticker}</code></td>
                  <td><code>{p.right_ticker}</code></td>
                  <td style={{ textAlign: "right" }}>{p.common_count_top10}</td>
                  <td style={{ textAlign: "right" }}>{fmtPctp(p.weighted_overlap_pct)}</td>
                  <td>
                    {p.common_holdings.length === 0
                      ? DASH
                      : p.common_holdings
                          .map((h) => h.name ?? h.ticker ?? "")
                          .filter((s) => s)
                          .join(", ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h2>반복 등장 핵심 종목</h2>
        {analysis.repeated_core_holdings.length === 0 ? (
          <div className="helper">반복 등장 종목이 없습니다.</div>
        ) : (
          <table className="market-topn-table">
            <thead>
              <tr>
                <th style={{ width: 90 }}>티커</th>
                <th>종목명</th>
                <th style={{ textAlign: "right", width: 120 }}>등장 ETF 수</th>
                <th>각 ETF 내 비중</th>
              </tr>
            </thead>
            <tbody>
              {analysis.repeated_core_holdings.map((r, idx) => (
                <tr key={`${r.ticker ?? "x"}-${idx}`}>
                  <td>{r.ticker ? <code>{r.ticker}</code> : DASH}</td>
                  <td>{r.name ?? DASH}</td>
                  <td style={{ textAlign: "right" }}>{r.appears_in_etf_count}</td>
                  <td>
                    {r.items
                      .map((it) => `${it.etf_ticker}:${fmtPctp(it.weight_pct)}`)
                      .join(", ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
