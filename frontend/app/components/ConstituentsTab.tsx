"use client";

// ETF Exposure / 구성종목 탭 (POC2 — 2026-05-27).
//
// 책임:
// - draft 의 후보 ETF 목록을 표시 + 수집 버튼.
// - POST /market/constituents/refresh 호출 (1회 최대 10개 — service-level cap).
// - GET /market/constituents/analysis 호출 → 상위 holdings + 집중도 표시.
//
// AI Sessions 로 넘기는 흐름은 별도 TransferToAISessionsFromExposureCard 가 담당.

import { useCallback, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  type ConstituentItem,
  type ConstituentsAnalysisResponse,
  fetchConstituentsAnalysis,
  refreshConstituents,
  type RefreshConstituentsItem,
} from "@/lib/api";
import type { ETFExposureDraft } from "@/lib/etfExposureDraft";

const DASH = "-";

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패(HTTP ${e.httpStatus}): ${e.message}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return DASH;
  return `${value.toFixed(2)}%`;
}

function statusBadge(status: string): string {
  switch (status) {
    case "ok":
      return "constituent-status-ok";
    case "unavailable":
      return "constituent-status-unavailable";
    case "skipped_timeout":
      return "constituent-status-timeout";
    default:
      return "constituent-status-other";
  }
}

interface Props {
  draft: ETFExposureDraft;
  analysis: ConstituentsAnalysisResponse | null;
  setAnalysis: (a: ConstituentsAnalysisResponse | null) => void;
}

export default function ConstituentsTab({ draft, analysis, setAnalysis }: Props) {
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [refreshItems, setRefreshItems] = useState<RefreshConstituentsItem[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const tickers = draft.candidate_snapshot
    .map((c) => c.ticker)
    .filter((t): t is string => !!t);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    setErrorMessage(null);
    setStatusMessage(null);
    try {
      const r = await refreshConstituents({
        asof: draft.asof,
        tickers,
        top_k: 10,
        force: false,
      });
      setRefreshItems(r.items);
      if (r.status === "rejected") {
        setErrorMessage(r.message ?? "수집이 거부되었습니다.");
      } else {
        setStatusMessage(
          `수집 완료: 성공 ${r.success_count} / 실패 ${r.fail_count} / 캐시 ${r.cached_count} / skip ${r.skipped_count}`,
        );
        // 수집 직후 analysis 재호출.
        // 2026-06-01 FIX (검증자 A-1 NOTE 반영) — asof 는 omit. 백엔드가
        // latest_constituent_asof MAX 를 사용 → Naver 의 referenceDate (예:
        // 2026-06-01) 와 draft.asof (예: 2026-05-28) 불일치로 인한 0건 회피.
        const a = await fetchConstituentsAnalysis(tickers, null, 10);
        setAnalysis(a);
      }
    } catch (e) {
      setErrorMessage(describeError(e));
    } finally {
      setRefreshing(false);
    }
  }, [draft.asof, tickers, setAnalysis]);

  const refreshByTicker: Record<string, RefreshConstituentsItem> = {};
  for (const it of refreshItems) {
    refreshByTicker[it.ticker] = it;
  }

  return (
    <>
      <div className="card">
        <h2>후보 ETF 구성종목 수집</h2>
        <p className="helper" style={{ marginBottom: 8 }}>
          Naver Stock ETFComponent 기준 구성종목 데이터에서 후보 ETF 의 상위
          10개 구성종목 + 비중을 수집합니다. 1회 최대 10개 후보까지 가능.
          캐시가 있으면 외부 호출 없이 기존 데이터를 사용합니다.
        </p>
        <ul className="dashboard-status-list">
          <li>기준일 (asof): <strong>{draft.asof}</strong></li>
          <li>대상 ticker: <strong>{tickers.length}</strong>개</li>
        </ul>
        <div className="btn-row">
          <button type="button" onClick={handleRefresh} disabled={refreshing || tickers.length === 0}>
            {refreshing ? "수집 중..." : "구성종목 수집"}
          </button>
        </div>
        {statusMessage ? (
          <div className="message info" style={{ marginTop: 8 }}>
            {statusMessage}
          </div>
        ) : null}
        {errorMessage ? (
          <div className="message error" style={{ marginTop: 8 }}>
            {errorMessage}
          </div>
        ) : null}
      </div>

      {analysis ? (
        <div className="card">
          <h2>구성종목 (상위 10) + 집중도</h2>
          <p className="helper" style={{ marginBottom: 8 }}>
            가용 {analysis.coverage.available_count} /
            요청 {analysis.coverage.requested_count} ·
            asof {analysis.asof}
          </p>
          {analysis.constituents.map((c: ConstituentItem) => (
            <details key={c.etf_ticker} className="card" style={{ marginBottom: 8 }}>
              <summary>
                <span className={`constituent-status-badge ${statusBadge(c.status)}`}>
                  {c.status}
                </span>{" "}
                <code>{c.etf_ticker}</code> · {c.etf_name ?? "-"} ·{" "}
                {c.source ?? DASH} ·{" "}
                {refreshByTicker[c.etf_ticker]?.from_cache ? "(캐시)" : ""}
              </summary>
              {c.status === "ok" ? (
                <>
                  <ul className="dashboard-status-list" style={{ marginTop: 6 }}>
                    <li>Top 1 집중도: <strong>{fmtPct(c.concentration.top1_weight_pct)}</strong></li>
                    <li>Top 3 집중도: <strong>{fmtPct(c.concentration.top3_weight_pct)}</strong></li>
                    <li>Top 5 집중도: <strong>{fmtPct(c.concentration.top5_weight_pct)}</strong></li>
                    <li>Top 10 집중도: <strong>{fmtPct(c.concentration.top10_weight_pct)}</strong></li>
                  </ul>
                  <table className="market-topn-table">
                    <thead>
                      <tr>
                        <th style={{ width: 50 }}>순위</th>
                        <th style={{ width: 90 }}>티커</th>
                        <th>종목명</th>
                        <th style={{ width: 90, textAlign: "right" }}>비중</th>
                      </tr>
                    </thead>
                    <tbody>
                      {c.top_holdings.map((h) => {
                        // 2026-05-31 — Naver 통합. 해외형 종목 (ticker=null) 은
                        // reuters code 또는 ISIN 으로 식별 노출.
                        const displayId =
                          h.ticker ||
                          h.constituent_reuters_code ||
                          h.constituent_isin ||
                          null;
                        return (
                          <tr key={`${c.etf_ticker}-${h.rank}`}>
                            <td>{h.rank}</td>
                            <td>{displayId ? <code>{displayId}</code> : DASH}</td>
                            <td>{h.name ?? DASH}</td>
                            <td style={{ textAlign: "right" }}>{fmtPct(h.weight_pct)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </>
              ) : (
                <div className="helper" style={{ marginTop: 6 }}>
                  구성종목 데이터가 없습니다 (unavailable). 외부 source 가 응답하지
                  않았거나 데이터가 없습니다.
                </div>
              )}
            </details>
          ))}
        </div>
      ) : null}
    </>
  );
}
