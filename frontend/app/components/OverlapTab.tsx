"use client";

// ETF Exposure / 중복률 탭 (POC2 — 2026-05-27).
//
// 표시 항목 (지시문 §6.2):
// - ETF 쌍별 common_count_top10 / weighted_overlap_pct / common_holdings.
// - 반복 등장 핵심 종목 (appears_in_etf_count + per-ETF 비중).
//
// 2026-08-19 카드 전환 (사용자 실화면 직접 지시 · 목업 승인).
// 표 2개(5열 + 4열) → 카드 2벌. 다른 화면과 같은 규칙(좌 2단 + 우 지표)을 쓴다.
// 값·계산은 그대로다 — API 호출·계산 추가 0건.
//
// 사용자 확정 3건:
//   ① ETF 를 티커 대신 **이름 + 티커** 로 식별한다. 이름은 응답이 아니라 화면이
//      이미 들고 있는 draft 에서 온다 (응답의 etf_name 은 현재 캐시에서 전부 null).
//      draft 에 없는 티커는 티커 그대로 둔다 — 이름을 지어내지 않는다.
//   ② 반복 종목 카드 우측에 **최고 비중** 을 둔다 (응답 값 중 최대값 선택).
//   ③ 쌍 정렬 기본값은 **중복률 높은순** (정렬이 없어 93% 짜리가 목록에 묻혔다).

import { useMemo, useState } from "react";
import type { ConstituentsAnalysisResponse, OverlapPair } from "@/lib/api";

const DASH = "-";

type PairSortKey = "overlap" | "common" | "default";

function fmtPctp(value: number | null | undefined): string {
  if (value === null || value === undefined) return DASH;
  return `${value.toFixed(2)}%`;
}

export default function OverlapTab({
  analysis,
  nameByTicker,
}: {
  analysis: ConstituentsAnalysisResponse | null;
  // 티커 → ETF 이름. 없으면 티커만 쓴다 (선택 prop — 호출자가 draft 에서 만든다).
  nameByTicker?: Record<string, string>;
}) {
  const [pairSort, setPairSort] = useState<PairSortKey>("overlap");

  const nm = (t: string): string => nameByTicker?.[t] ?? t;

  const pairs = useMemo(() => {
    const rows = [...(analysis?.overlap_matrix ?? [])];
    if (pairSort === "default") return rows;
    if (pairSort === "common") {
      return rows.sort((a, b) => b.common_count_top10 - a.common_count_top10);
    }
    // 중복률 없는 쌍(겹침 0)은 0 으로 취급하지 않고 항상 뒤로 보낸다.
    return rows.sort((a, b) => {
      const av = a.weighted_overlap_pct;
      const bv = b.weighted_overlap_pct;
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      return bv - av;
    });
  }, [analysis, pairSort]);

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
          <>
            <div className="holdings-sortbar" style={{ margin: "0 0 8px" }}>
              <span className="holdings-sortbar-label">정렬</span>
              <span className="holdings-sort-seg">
                {(
                  [
                    ["overlap", "중복률 높은순"],
                    ["common", "공통 종목 많은순"],
                    ["default", "응답 순서"],
                  ] as [PairSortKey, string][]
                ).map(([k, label]) => (
                  <button
                    key={k}
                    type="button"
                    className={pairSort === k ? "on" : undefined}
                    aria-pressed={pairSort === k}
                    onClick={() => setPairSort(k)}
                  >
                    {label}
                  </button>
                ))}
              </span>
            </div>
            <div className="wb-hlist" data-testid="overlap-pair-list">
              {pairs.map((p, idx) => (
                <PairCard
                  key={`${p.left_ticker}-${p.right_ticker}-${idx}`}
                  pair={p}
                  nm={nm}
                />
              ))}
            </div>
          </>
        )}
      </div>

      <div className="card">
        <h2>반복 등장 핵심 종목</h2>
        {analysis.repeated_core_holdings.length === 0 ? (
          <div className="helper">반복 등장 종목이 없습니다.</div>
        ) : (
          <div className="wb-hlist" data-testid="overlap-core-list">
            {analysis.repeated_core_holdings.map((r, idx) => {
              // 비중 높은 순으로 칩을 놓는다 (값은 그대로, 순서만).
              const items = [...r.items].sort(
                (a, b) => (b.weight_pct ?? 0) - (a.weight_pct ?? 0),
              );
              const top = items.length > 0 ? items[0] : null;
              return (
                <div className="wb-hrow compact" key={`${r.ticker ?? "x"}-${idx}`}>
                  <div className="wb-hcard">
                    <div className="wb-hrow-top">
                      <div className="wb-hrow-name">
                        {r.name ?? DASH}
                        {/* 티커가 없는 종목이 있다 (해외 종목 등). 무엇인지 단정하지
                            않고 "티커 없음" 으로만 적는다. */}
                        {r.ticker ? null : (
                          <span className="wb-hbadges">
                            <span className="wb-hb mute">티커 없음</span>
                          </span>
                        )}
                      </div>
                      <div className="wb-hrow-pnl">
                        <span className="amt">{r.appears_in_etf_count}</span>
                        <span className="rate wb-hmuted">개 ETF</span>
                      </div>
                    </div>
                    <div className="wb-hrow-bot">
                      <div className="wb-hrow-facts">
                        <span className="tk">{r.ticker ?? DASH}</span>
                        <span className="sep">|</span>
                        <span className="ovl-chips">
                          {items.map((it, i) => (
                            <span className="ovl-chip" key={`${it.etf_ticker}-${i}`}>
                              {nm(it.etf_ticker)}{" "}
                              <b>{fmtPctp(it.weight_pct)}</b>
                            </span>
                          ))}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="wb-hmetrics">
                    <div className="wb-hm-cell">
                      <span className="k">최고 비중</span>
                      <span className="v">{fmtPctp(top?.weight_pct)}</span>
                    </div>
                    {top ? (
                      <div className="ovl-cap" title={nm(top.etf_ticker)}>
                        {nm(top.etf_ticker)}
                      </div>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}

function PairCard({
  pair: p,
  nm,
}: {
  pair: OverlapPair;
  nm: (t: string) => string;
}) {
  const w = p.weighted_overlap_pct;
  const names = p.common_holdings
    .map((h) => h.name ?? h.ticker ?? "")
    .filter((s) => s);
  return (
    <div className="wb-hrow compact">
      <div className="wb-hcard">
        <div className="wb-hrow-top">
          <div className="wb-hrow-name">
            {nm(p.left_ticker)}
            <span className="ovl-vs">↔</span>
            {nm(p.right_ticker)}
            {/* 겹치는 종목이 없으면 중복률을 0% 로 쓰지 않는다 — 없는 것과
                0 인 것은 다르다. */}
            {w == null ? (
              <span className="wb-hbadges">
                <span className="wb-hb mute">겹치는 종목 없음</span>
              </span>
            ) : null}
          </div>
          <div className="wb-hrow-pnl">
            <span className={w == null ? "amt wb-hmuted" : "amt"}>
              {w == null ? DASH : fmtPctp(w)}
            </span>
            <span className="rate wb-hmuted">비중 중복</span>
          </div>
        </div>
        <div className="wb-hrow-bot">
          <div className="wb-hrow-facts">
            <span className="tk">{p.left_ticker}</span>
            <span className="sep">/</span>
            <span className="tk">{p.right_ticker}</span>
            <span className="sep">|</span>
            {names.length === 0 ? (
              <span className="wb-hmuted">공통 상위 종목 없음</span>
            ) : (
              <span className="ovl-chips">
                {names.map((n, i) => (
                  <span className="ovl-chip" key={`${n}-${i}`}>
                    {n}
                  </span>
                ))}
              </span>
            )}
          </div>
        </div>
      </div>
      <div className="wb-hmetrics">
        <div className="wb-hm-cell">
          <span className="k">공통 상위 종목</span>
          <span className="v">
            {p.common_count_top10}
            <span className="ovl-den"> / 10</span>
          </span>
        </div>
        <div className="ovl-bar">
          <i style={{ width: `${Math.min(Math.max(w ?? 0, 0), 100)}%` }} />
        </div>
        <div className="ovl-cap">비중 중복률</div>
      </div>
    </div>
  );
}
