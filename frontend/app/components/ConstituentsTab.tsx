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

// 2026-08-19 — 다른 화면과 같은 배지를 쓴다(`.wb-hb` + 상태 변형). 이전에는 이
// 화면만 테두리 있는 알약(`.constituent-status-badge`)이라 형태가 달랐다.
function statusBadge(status: string): string {
  switch (status) {
    case "ok":
      return "ok";
    case "unavailable":
      return "mute";
    case "skipped_timeout":
      return "warn";
    default:
      return "mute";
  }
}

interface Props {
  // 2026-08-19 — 티커 → ETF 이름. 응답의 etf_name 은 네이버 구성종목 API 가 ETF
  // 자기 이름을 주지 않아 **저장 시점부터 전부 null** 이다(DB 실측). 그래서 화면이
  // 이미 들고 있는 draft 후보 스냅샷의 이름을 쓴다. 없으면 티커만 — 지어내지 않는다.
  nameByTicker?: Record<string, string>;
  draft: ETFExposureDraft;
  analysis: ConstituentsAnalysisResponse | null;
  setAnalysis: (a: ConstituentsAnalysisResponse | null) => void;
}

export default function ConstituentsTab({
  draft,
  analysis,
  setAnalysis,
  nameByTicker,
}: Props) {
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
          <h2>상위 구성종목</h2>
          <p className="helper" style={{ marginBottom: 8 }}>
            가용 {analysis.coverage.available_count} / 요청{" "}
            {analysis.coverage.requested_count} · asof {analysis.asof}. ETF별
            상위 구성종목이 접히지 않고 바로 보입니다 — 후보 ETF 간 종목 비교용.
            중복률은 이 표시 깊이와 무관하게 상위{" "}
            {analysis.overlap_top_k ?? 10}건 기준으로 계산합니다.
          </p>
          {/* 2026-06-06 ETF Exposure Data Unfolding 1차 (지시문 §5.2 / AC-2) —
              구성종목 details 를 자동 펼침(open) 으로 표시. ETF별 종목이 한눈에
              비교 가능하도록 한다.
              2026-08-19 설계 확정 — **등락률 열 제거.** 값을 못 가져온 게 아니라
              연결한 적 없는 자리였고, 채우려면 개별주 시세 수집이라는 새 데이터
              계약이 필요하다. 항상 `unavailable` 인 열은 고장으로 읽히므로 열과
              안내문을 함께 뺀다(0%·ETF 등락률·추정값으로 대체하지 않는다).
              개별주 등락률 수집은 BACKLOG. */}
          {analysis.constituents.map((c: ConstituentItem) => (
            <details
              key={c.etf_ticker}
              className="card"
              style={{ marginBottom: 8 }}
              open
            >
              {/* 2026-08-19 사용자 지시 — 다른 화면 카드와 같은 줄 규칙으로 맞춘다.
                  이름 먼저(굵게) · 티커는 뒤에 작게 · 배지는 공용 `.wb-hb` 사용.
                  source(`naver_stock_etf_component`)는 화면에서 뺐다 — 내부 코드
                  문자열이고 현재 값이 한 종류뿐이다(펼친 안쪽 상단에 남긴다). */}
              <summary className="cst-summary">
                <b className="cst-name">
                  {c.etf_name ?? nameByTicker?.[c.etf_ticker] ?? c.etf_ticker}
                </b>
                <span className={`wb-hb ${statusBadge(c.status)}`}>{c.status}</span>
                <code className="cst-tk">{c.etf_ticker}</code>
                {refreshByTicker[c.etf_ticker]?.from_cache ? (
                  <span className="cst-cache">캐시</span>
                ) : null}
              </summary>
              {c.status === "ok" ? (
                <>
                  {/* summary 줄에서 뺀 source 를 여기 남긴다 — 어디서 온 값인지는
                      필요할 때 확인할 수 있어야 한다. */}
                  <div className="cst-src">
                    {c.source ?? DASH}
                    {c.asof ? ` · asof ${c.asof}` : ""}
                  </div>
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
                            <td style={{ textAlign: "right" }}>
                              {fmtPct(h.weight_pct)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  {/* 2026-08-19 설계 확정 표시 계약 — 확보된 건수만 적는다.
                      "전체 구성종목" 이라고 쓰지 않는다(ETF 전체는 더 많다). */}
                  <p
                    className="helper"
                    style={{ marginTop: 4, fontSize: "0.78rem" }}
                  >
                    상위 {c.top_holdings.length}개 표시 · 표시 비중 합계{" "}
                    {fmtPct(
                      c.top_holdings.reduce(
                        (acc, h) => acc + (h.weight_pct ?? 0),
                        0,
                      ),
                    )}
                  </p>
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
