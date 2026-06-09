"use client";

// POC2 ML 최소 데이터 레인 (2026-06-08) — Readiness 카드 갱신.
//
// 이전 (2026-06-06): 정적 9축 표 (NAV/구성종목/거래량/시장지수/시장 폭/외국인·기관 수급/
//   변동성/Fear&Greed/CNN 등). 실제 적재 여부와 무관한 보수적 표기.
// 현재 (2026-06-08): GET /ml/readiness/latest 응답 기반 7축. 실제 etf_ml_feature_daily
//   / market_risk_feature_daily row 수 + latest asof 로 status 결정.
//
// 본 STEP 에서 표시하지 않는 (지시문 §6.6 '제외'):
//   - CNN Fear & Greed / VKOSPI / 외국인·기관 수급 / KOSPI 전체 시장 폭 /
//     구성종목 가격 시계열. BACKLOG 후보로만 별도 관리.

import { useEffect, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchMlReadinessLatest,
  type MlReadinessAxis,
  type MlReadinessResponse,
} from "@/lib/api";

type LoadState =
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "ready"; data: MlReadinessResponse };

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패(HTTP ${e.httpStatus}): ${e.message}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

function statusBadgeClass(status: string): string {
  if (status === "available") {
    return "ml-readiness-badge ml-readiness-available";
  }
  if (status === "partial") {
    return "ml-readiness-badge ml-readiness-partial";
  }
  return "ml-readiness-badge ml-readiness-missing";
}

export default function MLTimeseriesReadinessCard() {
  const [state, setState] = useState<LoadState>({ phase: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchMlReadinessLatest()
      .then((data) => {
        if (!cancelled) setState({ phase: "ready", data });
      })
      .catch((e) => {
        if (!cancelled) setState({ phase: "error", message: describeError(e) });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="card">
      <h2>ML 최소 데이터 레인 — feature 적재 상태</h2>
      <p className="helper" style={{ marginBottom: 8 }}>
        본 STEP 에서 ML / 위험 감지 모델은 만들지 않습니다. 학습에 필요한 daily
        feature 가 SQLite (<code>etf_ml_feature_daily</code> /{" "}
        <code>market_risk_feature_daily</code>) 에 적재된 상태만 표시합니다. 위험
        감지는 &lsquo;하락 예측&rsquo;이 아니라 &lsquo;위험 구간 분류&rsquo;로
        정의합니다 (factor / threshold / label 미확정).
      </p>
      {state.phase === "loading" && (
        <div className="message info">불러오는 중...</div>
      )}
      {state.phase === "error" && (
        <div className="message error">{state.message}</div>
      )}
      {state.phase === "ready" && (
        <ReadinessTable
          axes={state.data.axes}
          etfRowCount={state.data.etf_feature_row_count}
          etfDistinctAsof={state.data.etf_distinct_asof_count}
          etfLatestAsof={state.data.etf_latest_asof}
          marketRowCount={state.data.market_risk_row_count}
          marketLatestAsof={state.data.market_risk_latest_asof}
        />
      )}
    </div>
  );
}

function ReadinessTable({
  axes,
  etfRowCount,
  etfDistinctAsof,
  etfLatestAsof,
  marketRowCount,
  marketLatestAsof,
}: {
  axes: MlReadinessAxis[];
  etfRowCount: number;
  etfDistinctAsof: number;
  etfLatestAsof: string | null;
  marketRowCount: number;
  marketLatestAsof: string | null;
}) {
  return (
    <>
      <p className="helper" style={{ marginBottom: 8 }}>
        ETF feature: <strong>{etfRowCount}</strong> row /{" "}
        <strong>{etfDistinctAsof}</strong> 거래일 · latest asof{" "}
        <strong>{etfLatestAsof ?? "-"}</strong>. Market risk feature:{" "}
        <strong>{marketRowCount}</strong> row · latest asof{" "}
        <strong>{marketLatestAsof ?? "-"}</strong>.
      </p>
      <table className="market-topn-table">
        <thead>
          <tr>
            <th>feature 축</th>
            <th style={{ width: 140 }}>상태</th>
            <th>설명</th>
          </tr>
        </thead>
        <tbody>
          {axes.map((axis) => (
            <tr key={axis.label}>
              <td>{axis.label}</td>
              <td>
                <span className={statusBadgeClass(axis.status)}>
                  {axis.status}
                </span>
              </td>
              <td style={{ color: "var(--muted)" }}>{axis.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p
        className="helper"
        style={{ marginTop: 8, fontSize: "0.78rem" }}
      >
        feature 생성은 CLI (<code>scripts/generate_ml_features.py</code>) 로만
        수행됩니다 — 화면 조회 / refresh 흐름에 연결되지 않습니다 (지시문 §4).
        CNN Fear &amp; Greed / VKOSPI / 외국인·기관 수급 / KOSPI 전체 시장 폭 /
        구성종목 가격 시계열은 본 STEP 범위가 아니라 본 카드에 표시하지 않습니다 —
        BACKLOG 후보.
      </p>
    </>
  );
}
