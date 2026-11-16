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
//
// POC6-31(판정 Q7 · Q21 · §4 M2) — 같은 구성일 쌍(양쪽 원천 기준일 확인 · 같은 날짜 · 서버 pair_scope) 중 정렬 상위 10쌍 +
//   남은 쌍 수(펼쳐 보기). 구성일이 다르거나 원천 기준일이 확인되지 않은 쌍은 참고로 따로(이유 · 양쪽 날짜).
//   한쪽 구성 자료가 없는 쌍은 세지 않고 개수만 밝힌다(30개 중 29개만 자료 → 같은 구성일 쌍 최대 406).
//   예전 '반복 등장 핵심 종목' 자리에는 '여러 지수 계열이 함께 담은 주식' 카드(slot)를 둔다.

import { useMemo, useState, type ReactNode } from "react";
import type { ConstituentsAnalysisResponse, OverlapPair } from "@/lib/api";
import { pairDateText, pairRestText, splitPairs } from "@/lib/constituentsText";

const DASH = "-";

type PairSortKey = "overlap" | "common" | "default";

function fmtPctp(value: number | null | undefined): string {
  if (value === null || value === undefined) return DASH;
  return `${value.toFixed(2)}%`;
}

const TOP_PAIRS = 10;

export default function OverlapTab({
  analysis,
  nameByTicker,
  slot,
}: {
  analysis: ConstituentsAnalysisResponse | null;
  // 티커 → ETF 이름. 없으면 티커만 쓴다 (선택 prop — 호출자가 draft 에서 만든다).
  nameByTicker?: Record<string, string>;
  // 예전 '반복 등장 핵심 종목' 자리(POC6-31 · 판정 Q21)
  slot?: ReactNode;
}) {
  const [pairSort, setPairSort] = useState<PairSortKey>("overlap");
  const [showRest, setShowRest] = useState(false);

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
  // 서버 쌍 범위(pair_scope) 기준 · 칸 없는 예전 서버 응답은 한 날짜로 읽은 것이라 같은 구성일로 본다.
  const split = splitPairs(pairs);
  const samePairs = split.same_date;
  const refPairs = [...split.different_date, ...split.unconfirmed];
  const restText = pairRestText(split);

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
            <p className="helper" data-testid="overlap-pair-scope">
              같은 구성일 쌍 {samePairs.length}개 중 {Math.min(TOP_PAIRS, samePairs.length)}쌍
              {samePairs.length > TOP_PAIRS && !showRest ? ` · 나머지 ${samePairs.length - TOP_PAIRS}쌍은 아래에서 펼칩니다` : ""}
              {restText ? ` · 같은 구성일이 아닌 쌍(${restText})은 세지 않음` : ""}
            </p>
            <div className="wb-hlist" data-testid="overlap-pair-list">
              {(showRest ? samePairs : samePairs.slice(0, TOP_PAIRS)).map((p, idx) => (
                <PairCard
                  key={`${p.left_ticker}-${p.right_ticker}-${idx}`}
                  pair={p}
                  nm={nm}
                />
              ))}
            </div>
            {samePairs.length > TOP_PAIRS ? (
              <button type="button" className="wb-btn btn-md" onClick={() => setShowRest(!showRest)} data-testid="overlap-rest">
                {showRest ? `상위 ${TOP_PAIRS}쌍만 보기` : `나머지 ${samePairs.length - TOP_PAIRS}쌍 보기`}
              </button>
            ) : null}
            {refPairs.length > 0 ? (
              <details data-testid="overlap-ref-pairs">
                <summary>
                  같은 구성일이 아닌 쌍 {refPairs.length}개(참고 · 구성일 다름 {split.different_date.length} · 원천 기준일 미확인{" "}
                  {split.unconfirmed.length})
                </summary>
                <div className="wb-hlist">
                  {refPairs.map((p, idx) => (
                    <PairCard key={`r-${p.left_ticker}-${p.right_ticker}-${idx}`} pair={p} nm={nm} note={pairDateText(p)} />
                  ))}
                </div>
              </details>
            ) : null}
          </>
        )}
      </div>

      {slot}
    </>
  );
}

function PairCard({
  pair: p,
  nm,
  note,
}: {
  pair: OverlapPair;
  nm: (t: string) => string;
  note?: string; // 참고 쌍 — 같은 구성일이 아닌 이유 · 양쪽 날짜
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
            {note ? (
              <span className="wb-hbadges">
                <span className="wb-hb mute" data-testid="overlap-ref-note">
                  {note}
                </span>
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
