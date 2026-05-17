"use client";

// POC2 PC Market Discovery TOP N 최소 표시 (지시문 §3.2).
//
// state/market/etf_universe_topn_latest.json artifact 를 GET /market/topn/latest
// 로 읽어 일간 / 1개월 / 3개월 TOP N 표를 렌더링한다.
//
// 본 화면은 read-only 다 (refresh 버튼 / 필터 / 정렬 / 차트 / SQLite 직접 조회
// / TOP N 재계산 모두 금지 — 지시문 §6).

import { useEffect, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchMarketTopnLatest,
  type MarketTopNEntry,
  type MarketTopNResponse,
} from "@/lib/api";

type LoadState =
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "ready"; data: MarketTopNResponse };

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패(HTTP ${e.httpStatus}): ${e.message}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

// 지시문 §3.2 — artifact 에 없는 값은 "-" 로 표시. 0 / 0.0 으로 가공 금지.
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

function returnPctClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return "var(--muted)";
  return value >= 0 ? "var(--ok)" : "var(--danger)";
}

function TopNTable({
  title,
  entries,
}: {
  title: string;
  entries: MarketTopNEntry[];
}) {
  return (
    <div className="card market-topn-card">
      <h2>{title}</h2>
      {entries.length === 0 ? (
        <div className="message info">표시할 항목이 없습니다.</div>
      ) : (
        <table className="market-topn-table">
          <thead>
            <tr>
              <th style={{ width: 56 }}>순위</th>
              <th style={{ width: 90 }}>티커</th>
              <th>ETF명</th>
              <th style={{ width: 110, textAlign: "right" }}>수익률</th>
              <th style={{ width: 130 }}>기준 시작일</th>
              <th style={{ width: 130 }}>기준 종료일</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e, idx) => (
              <tr key={`${e.rank ?? "x"}-${e.ticker ?? "x"}-${idx}`}>
                <td>{fmtNum(e.rank)}</td>
                <td>
                  {e.ticker ? <code>{e.ticker}</code> : DASH}
                </td>
                <td>{fmt(e.name)}</td>
                <td
                  style={{
                    textAlign: "right",
                    color: returnPctClass(e.return_pct),
                  }}
                >
                  {fmtPct(e.return_pct)}
                </td>
                <td>{fmt(e.basis_start_date)}</td>
                <td>{fmt(e.basis_end_date)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function SummaryHeader({ data }: { data: MarketTopNResponse }) {
  return (
    <div className="card">
      <h2>요약</h2>
      <ul className="dashboard-status-list">
        <li>시장 데이터 기준일: <strong>{fmt(data.asof)}</strong></li>
        <li>데이터 소스: <strong>{fmt(data.source)}</strong></li>
        <li>Universe: <strong>{fmtNum(data.universe_count)}</strong>개</li>
        <li>가격 수집 성공: <strong>{fmtNum(data.price_success_count)}</strong>개</li>
        <li>가격 수집 실패: <strong>{fmtNum(data.price_fail_count)}</strong>개</li>
        <li>기본 N: <strong>{fmtNum(data.n)}</strong></li>
      </ul>
      {data.topn_caveat ? (
        <div className="helper" style={{ marginTop: 8 }}>
          {data.topn_caveat}
        </div>
      ) : null}
    </div>
  );
}

export default function MarketDiscoveryView() {
  const [state, setState] = useState<LoadState>({ phase: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchMarketTopnLatest()
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

  if (state.phase === "loading") {
    return (
      <section aria-labelledby="market-discovery-h">
        <h1 id="market-discovery-h">Market Discovery</h1>
        <div className="card">
          <div className="message info">불러오는 중...</div>
        </div>
      </section>
    );
  }

  if (state.phase === "error") {
    return (
      <section aria-labelledby="market-discovery-h">
        <h1 id="market-discovery-h">Market Discovery</h1>
        <div className="card">
          <div className="message error">{state.message}</div>
        </div>
      </section>
    );
  }

  const { data } = state;

  if (data.status === "missing") {
    return (
      <section aria-labelledby="market-discovery-h">
        <h1 id="market-discovery-h">Market Discovery</h1>
        <div className="card placeholder-card">
          <h2>시장 TOP N 데이터가 아직 생성되지 않았습니다</h2>
          <p>먼저 시장 데이터 refresh 가 필요합니다.</p>
          <p className="helper">
            (이번 단계에서는 본 화면에 refresh 버튼을 추가하지 않습니다 — 지시문 §4.2.)
          </p>
        </div>
      </section>
    );
  }

  if (data.status === "invalid") {
    return (
      <section aria-labelledby="market-discovery-h">
        <h1 id="market-discovery-h">Market Discovery</h1>
        <div className="card">
          <div className="message error">
            시장 TOP N 데이터를 읽을 수 없습니다. 데이터 파일 상태를 확인하세요.
          </div>
          {data.error ? (
            <div className="helper" style={{ marginTop: 8 }}>
              사유: {data.error}
            </div>
          ) : null}
        </div>
      </section>
    );
  }

  return (
    <section aria-labelledby="market-discovery-h">
      <h1 id="market-discovery-h">Market Discovery</h1>
      <p className="subtitle">
        FDR + SQLite 기반 ETF universe / 일간 / 1개월 / 3개월 TOP N 결과.
        본 화면은 artifact 파일을 읽어 표시할 뿐, 새 데이터 수집은 일으키지 않습니다.
      </p>
      <SummaryHeader data={data} />
      <TopNTable title="일간 TOP N" entries={data.daily_topn} />
      <TopNTable title="1개월 TOP N" entries={data.one_month_topn} />
      <TopNTable title="3개월 TOP N" entries={data.three_month_topn} />
    </section>
  );
}
