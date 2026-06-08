"use client";

// 시장 배경 카드 (POC2 — 2026-05-22 Market Regime & Benchmark Context 1차).
//
// 책임:
// - 시스템 1차 시장 국면 라벨 (상승장 / 보합장 / 하락장 / 판정불가) 표시.
// - KODEX200 (필수) 20거래일 / 60거래일 수익률 + MA20/MA60 위치 표시.
// - KOSPI (보조) 20거래일 / 60거래일 수익률 표시 (unavailable 이면 N/A).
// - regime_reasons + warnings 표시.
//
// 별도 파일로 분리한 이유: MarketDiscoveryView.tsx 의 KS-10 회피.

import type { MarketContext } from "@/lib/api";

const DASH = "-";

function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return DASH;
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

// 2026-06-08 — 사용자 요청: 금액 천단위 콤마 (현재가 / MA20 / MA60).
// 정수 / 실수 모두 toLocaleString 으로 콤마 적용. 소수점은 최대 2자리 유지.
function fmtMoney(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return value.toLocaleString("ko-KR", {
    maximumFractionDigits: 2,
  });
}

function regimeClass(code: string): string {
  switch (code) {
    case "bull":
      return "regime-bull";
    case "bear":
      return "regime-bear";
    case "neutral":
      return "regime-neutral";
    default:
      return "regime-unavailable";
  }
}

export default function MarketContextCard({ ctx }: { ctx: MarketContext | null }) {
  if (!ctx) {
    return (
      <div className="card market-context-card">
        <h2>시장 배경</h2>
        <div className="helper">
          시장 데이터가 없습니다. 먼저 시장 데이터 갱신을 실행하세요.
        </div>
      </div>
    );
  }

  const kodex = ctx.kodex200;
  const kospi = ctx.kospi;

  return (
    <div className="card market-context-card">
      <h2>시장 배경</h2>
      <div className="market-regime-headline">
        <span className="market-regime-label-row">
          <span className="market-regime-prefix">시스템 1차 시장 국면:</span>
          <strong className={`market-regime-label ${regimeClass(ctx.regime_code)}`}>
            {ctx.regime_label}
          </strong>
        </span>
        <span className="helper" style={{ marginLeft: 8 }}>
          (기준: {ctx.primary_benchmark}
          {ctx.regime_score !== null && ctx.regime_score !== undefined
            ? ` · 점수 ${ctx.regime_score >= 0 ? "+" : ""}${ctx.regime_score}`
            : ""}
          )
        </span>
      </div>

      <div className="market-regime-benchmarks">
        <div>
          {/* 2026-06-08 — 사용자 요청: 현재가/MA 표시 행에 어느 종목인지 명시.
              KODEX200 시스템 상수 → (069500) KODEX 200 로 표시. */}
          <h3>(069500) KODEX 200 (필수)</h3>
          {kodex.status === "ok" ? (
            <ul className="dashboard-status-list">
              <li>20거래일 수익률: <strong>{fmtPct(kodex.return_20d_pct)}</strong></li>
              <li>60거래일 수익률: <strong>{fmtPct(kodex.return_60d_pct)}</strong></li>
              <li>
                현재가: <strong>{fmtMoney(kodex.close)}</strong>
                {" · "}MA20: {fmtMoney(kodex.ma20)} ({kodex.ma20_position === "above" ? "위" : "아래"})
                {" · "}MA60: {fmtMoney(kodex.ma60)} ({kodex.ma60_position === "above" ? "위" : "아래"})
              </li>
            </ul>
          ) : (
            <div className="message info">N/A — KODEX 200 시계열이 부족합니다.</div>
          )}
        </div>
        <div>
          <h3>(KS11) KOSPI (보조)</h3>
          {kospi.status === "ok" ? (
            <ul className="dashboard-status-list">
              <li>20거래일 수익률: <strong>{fmtPct(kospi.return_20d_pct)}</strong></li>
              <li>60거래일 수익률: <strong>{fmtPct(kospi.return_60d_pct)}</strong></li>
            </ul>
          ) : (
            <div className="helper">N/A — KOSPI 시계열이 수집되지 않았습니다.</div>
          )}
        </div>
      </div>

      {ctx.regime_reasons.length > 0 ? (
        <details className="market-regime-reasons">
          <summary>판정 근거 ({ctx.regime_reasons.length}건)</summary>
          <ul>
            {ctx.regime_reasons.map((r, idx) => (
              <li key={idx}>{r}</li>
            ))}
          </ul>
        </details>
      ) : null}

      {ctx.warnings.length > 0 ? (
        <div className="helper" style={{ marginTop: 8 }}>
          {ctx.warnings.map((w, idx) => (
            <div key={idx}>⚠ {w}</div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
