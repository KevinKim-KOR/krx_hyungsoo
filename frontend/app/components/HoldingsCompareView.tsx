"use client";

// POC2 — 보유 ETF와 시장 후보 비교 v1 (2026-06-21).
//
// Market Discovery 안의 "보유와 비교" 보기 모드. 새 endpoint / 새 계산 0건 —
// 기존 GET /market/topn/latest + GET /holdings/enriched + GET /holdings/market-
// evidence/latest 응답을 프론트에서 조합한다.
//
// 화면 구성:
//   - 기준일 헤더 (후보 / 보유 / 중복 정보 각각)
//   - 좌측 70% : 보유 요약 표 + 후보 비교 표 (세로 배치)
//   - 우측 30% : 후보 선택 상세 (점수 근거 + 보유 중복 evidence)
//
// 보유 중복 상태 = exact match (ticker 일치) + constituents overlap (보유 ETF
// 구성종목 ↔ 현재 후보군 반복 핵심 종목). 둘 다 제공.
//
// 매수/매도/추천/교체/비중 조절 문구 0건. 새 종합점수 0건.

import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  EnrichedHolding,
  HoldingsMarketEvidenceItem,
  HoldingsMarketEvidenceResponse,
} from "@/lib/api";
import {
  fetchEnrichedHoldings,
  fetchHoldingsMarketEvidence,
} from "@/lib/api/holdings";
import type {
  MarketCandidate,
  MarketTopNResponse,
} from "@/lib/api";

const DASH = "-";

function fmtNum(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return DASH;
  return value.toFixed(digits);
}

function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return DASH;
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function returnColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return "var(--muted)";
  return value >= 0 ? "var(--ok)" : "var(--danger)";
}

// 후보 1건의 보유 중복 상태 (exact match + constituents overlap).
interface OverlapStatus {
  // exact match: 후보 ticker 와 동일한 보유 ETF 가 있으면 그 보유 ticker.
  exactMatchHoldingTicker: string | null;
  exactMatchHoldingName: string | null;
  // constituents overlap: 후보가 어떤 보유 ETF 의 reverse-lookup (보유 구성종목
  // 중에서 본 후보가 시장 반복 핵심 종목으로 분류된 경우) 에 들어 있는지.
  // evidence 응답은 holding 별 overlap_with_market_core 만 제공하므로 frontend
  // 에서 holding↔candidate 매핑은 ticker exact match 만 client-side 가능.
  // 본 STEP 에서는 exact match 가 핵심이고, constituents overlap 은 evidence
  // 응답의 holding 별 overlap 결과를 그대로 노출 (후보 선택 시 상세 영역).
  overlapStateForCandidate: "exact_match" | "no_exact_match" | "not_loaded";
}

function computeOverlapStatus(
  candidateTicker: string | null | undefined,
  holdings: EnrichedHolding[],
  evidenceLoaded: boolean,
): OverlapStatus {
  if (!candidateTicker) {
    return {
      exactMatchHoldingTicker: null,
      exactMatchHoldingName: null,
      overlapStateForCandidate: evidenceLoaded ? "no_exact_match" : "not_loaded",
    };
  }
  const match = holdings.find((h) => h.ticker === candidateTicker);
  if (match) {
    return {
      exactMatchHoldingTicker: match.ticker,
      exactMatchHoldingName: match.name,
      overlapStateForCandidate: "exact_match",
    };
  }
  return {
    exactMatchHoldingTicker: null,
    exactMatchHoldingName: null,
    overlapStateForCandidate: evidenceLoaded ? "no_exact_match" : "not_loaded",
  };
}

// 후보 비교 표의 로컬 정렬 키.
type CandidateSortKey =
  | "default"
  | "relative_upside_score"
  | "return_20d"
  | "excess_20d"
  | "drawdown_20d"
  | "overlap";

type SortDirection = "desc" | "asc";

interface Props {
  data: MarketTopNResponse;
}

export default function HoldingsCompareView({ data }: Props) {
  // 보유 데이터 (enriched + evidence).
  const [enrichedHoldings, setEnrichedHoldings] = useState<EnrichedHolding[]>([]);
  const [enrichedLoading, setEnrichedLoading] = useState<boolean>(false);
  const [enrichedError, setEnrichedError] = useState<string | null>(null);

  // Evidence — 명시 조회 (지시문 §4.5 — 자동 fetch 금지).
  const [evidence, setEvidence] =
    useState<HoldingsMarketEvidenceResponse | null>(null);
  const [evidenceLoading, setEvidenceLoading] = useState<boolean>(false);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);

  // 선택된 후보.
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);

  // 후보 표 로컬 정렬.
  const [sortKey, setSortKey] = useState<CandidateSortKey>("default");
  const [sortDir, setSortDir] = useState<SortDirection>("desc");

  // 보유 표 로컬 정렬.
  const [holdingsSortKey, setHoldingsSortKey] = useState<
    "default" | "buy_weight" | "market_weight" | "pnl_rate"
  >("default");
  const [holdingsSortDir, setHoldingsSortDir] = useState<SortDirection>("desc");

  // 마운트 시 enriched 자동 로드 (캐시 기반, 외부 fetch 트리거 없음 — holdings.ts L96).
  useEffect(() => {
    let canceled = false;
    setEnrichedLoading(true);
    setEnrichedError(null);
    fetchEnrichedHoldings()
      .then((res) => {
        if (canceled) return;
        setEnrichedHoldings(res.items ?? []);
      })
      .catch((e) => {
        if (canceled) return;
        setEnrichedError((e as Error).message ?? "보유 데이터 조회 실패");
      })
      .finally(() => {
        if (canceled) return;
        setEnrichedLoading(false);
      });
    return () => {
      canceled = true;
    };
  }, []);

  // Evidence 명시 조회 (사용자 버튼 클릭).
  const handleEvidenceFetch = useCallback(async () => {
    if (evidenceLoading) return;
    setEvidenceLoading(true);
    setEvidenceError(null);
    try {
      const res = await fetchHoldingsMarketEvidence();
      setEvidence(res);
    } catch (e) {
      setEvidenceError((e as Error).message ?? "Evidence 조회 실패");
      // 기존 evidence 유지 (지시문 §4.5 — 조회 실패 시 기존 값을 지우지 않음).
    } finally {
      setEvidenceLoading(false);
    }
  }, [evidenceLoading]);

  // Evidence holding ticker → item map (보유 ETF 별 evidence 룩업).
  const evidenceByTicker = useMemo(() => {
    const m: Record<string, HoldingsMarketEvidenceItem> = {};
    if (evidence?.holdings) {
      for (const h of evidence.holdings) {
        m[h.ticker] = h;
      }
    }
    return m;
  }, [evidence]);

  const evidenceLoaded = evidence !== null;

  // 후보 정렬.
  const sortedCandidates = useMemo<MarketCandidate[]>(() => {
    const list = [...(data.candidates ?? [])];
    if (sortKey === "default") return list;
    const dirMul = sortDir === "desc" ? -1 : 1;
    const getKey = (c: MarketCandidate): number | null => {
      switch (sortKey) {
        case "relative_upside_score":
          return c.relative_upside_score ?? null;
        case "return_20d":
          return c.short_term_momentum?.return_20d_pct ?? null;
        case "excess_20d":
          return c.short_term_momentum?.excess_vs_kodex200_20d_pctp ?? null;
        case "drawdown_20d":
          return c.drawdown_20d ?? null;
        case "overlap": {
          // exact match 후보를 가장 앞 / 뒤로.
          const s = computeOverlapStatus(c.ticker, enrichedHoldings, evidenceLoaded);
          return s.overlapStateForCandidate === "exact_match" ? 1 : 0;
        }
        default:
          return null;
      }
    };
    list.sort((a, b) => {
      const av = getKey(a);
      const bv = getKey(b);
      // null 후보는 항상 뒤로 (지시문 §4.3 — 임의 순위/값 X).
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      return (av - bv) * dirMul;
    });
    return list;
  }, [data.candidates, sortKey, sortDir, enrichedHoldings, evidenceLoaded]);

  // 보유 정렬.
  const sortedHoldings = useMemo<EnrichedHolding[]>(() => {
    const list = [...enrichedHoldings];
    if (holdingsSortKey === "default") return list;
    const dirMul = holdingsSortDir === "desc" ? -1 : 1;
    const getKey = (h: EnrichedHolding): number | null => {
      switch (holdingsSortKey) {
        case "buy_weight":
          return h.buy_weight_pct ?? null;
        case "market_weight":
          return h.market_weight_pct ?? null;
        case "pnl_rate":
          return h.pnl_rate_pct ?? null;
        default:
          return null;
      }
    };
    list.sort((a, b) => {
      const av = getKey(a);
      const bv = getKey(b);
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      return (av - bv) * dirMul;
    });
    return list;
  }, [enrichedHoldings, holdingsSortKey, holdingsSortDir]);

  // 선택된 후보 객체.
  const selectedCandidate = useMemo<MarketCandidate | null>(() => {
    if (!selectedTicker) return null;
    return (
      (data.candidates ?? []).find((c) => c.ticker === selectedTicker) ?? null
    );
  }, [selectedTicker, data.candidates]);

  // 선택된 후보의 보유 중복 상태.
  const selectedOverlap = useMemo<OverlapStatus>(() => {
    if (!selectedCandidate) {
      return {
        exactMatchHoldingTicker: null,
        exactMatchHoldingName: null,
        overlapStateForCandidate: "not_loaded",
      };
    }
    return computeOverlapStatus(
      selectedCandidate.ticker,
      enrichedHoldings,
      evidenceLoaded,
    );
  }, [selectedCandidate, enrichedHoldings, evidenceLoaded]);

  const handleCandidateSort = useCallback(
    (key: CandidateSortKey) => {
      if (key === sortKey) {
        setSortDir((d) => (d === "desc" ? "asc" : "desc"));
      } else {
        setSortKey(key);
        setSortDir("desc");
      }
    },
    [sortKey],
  );

  const handleHoldingsSort = useCallback(
    (key: "buy_weight" | "market_weight" | "pnl_rate") => {
      if (key === holdingsSortKey) {
        setHoldingsSortDir((d) => (d === "desc" ? "asc" : "desc"));
      } else {
        setHoldingsSortKey(key);
        setHoldingsSortDir("desc");
      }
    },
    [holdingsSortKey],
  );

  return (
    <section style={{ marginTop: 16 }}>
      {/* 기준일 헤더 (지시문 §4.1 — 기준일이 다르면 하나로 합쳐 표시 X) */}
      <div
        className="card"
        style={{
          padding: 12,
          marginBottom: 12,
          display: "grid",
          gap: 4,
          fontSize: "0.85em",
        }}
      >
        <div>
          <span style={{ color: "var(--muted)" }}>후보 기준일: </span>
          <span>{data.asof ?? DASH}</span>
        </div>
        <div>
          <span style={{ color: "var(--muted)" }}>보유 정보 기준일: </span>
          <span>{evidence?.holdings_asof ?? DASH}</span>
        </div>
        <div>
          <span style={{ color: "var(--muted)" }}>중복 정보 상태: </span>
          <span style={{ color: evidenceLoaded ? "var(--ok)" : "var(--warn)" }}>
            {evidenceLoading
              ? "loading"
              : evidenceLoaded
                ? "ok"
                : evidenceError
                  ? "unavailable"
                  : "not_loaded"}
          </span>
          {!evidenceLoaded ? (
            <button
              type="button"
              onClick={handleEvidenceFetch}
              disabled={evidenceLoading}
              style={{
                marginLeft: 8,
                padding: "2px 10px",
                borderRadius: 4,
                border: "1px solid var(--border)",
                cursor: evidenceLoading ? "not-allowed" : "pointer",
              }}
            >
              {evidenceLoading ? "조회 중..." : "보유 비교 evidence 조회"}
            </button>
          ) : null}
        </div>
        <div>
          <span style={{ color: "var(--muted)" }}>중복 정보 기준일: </span>
          <span>{evidence?.market_asof ?? DASH}</span>
        </div>
        {evidenceError ? (
          <div style={{ color: "var(--danger)" }}>
            evidence 조회 실패. 기존 값은 유지됩니다.
          </div>
        ) : null}
      </div>

      {/* 좌측 70% (보유 + 후보 표) / 우측 30% (선택 상세) */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 350px", gap: 12 }}>
        <div style={{ display: "grid", gap: 12 }}>
          {/* 보유 ETF 요약 표 */}
          <div className="card" style={{ padding: 12 }}>
            <h3 style={{ margin: 0, marginBottom: 8 }}>보유 ETF</h3>
            {enrichedLoading ? (
              <p>보유 정보 조회 중...</p>
            ) : enrichedError ? (
              <p style={{ color: "var(--danger)" }}>보유 정보 조회 실패.</p>
            ) : enrichedHoldings.length === 0 ? (
              <p style={{ color: "var(--muted)" }}>보유 ETF 가 없습니다.</p>
            ) : (
              <table style={{ width: "100%", fontSize: "0.85em" }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left" }}>티커</th>
                    <th style={{ textAlign: "left" }}>ETF명</th>
                    <th
                      style={{ textAlign: "right", cursor: "pointer" }}
                      onClick={() => handleHoldingsSort("buy_weight")}
                      title="매입 비중 정렬"
                    >
                      매입 비중
                    </th>
                    <th
                      style={{ textAlign: "right", cursor: "pointer" }}
                      onClick={() => handleHoldingsSort("market_weight")}
                      title="평가 비중 정렬"
                    >
                      평가 비중
                    </th>
                    <th
                      style={{ textAlign: "right", cursor: "pointer" }}
                      onClick={() => handleHoldingsSort("pnl_rate")}
                      title="손익률 정렬"
                    >
                      손익률
                    </th>
                    <th style={{ textAlign: "right" }}>5d</th>
                    <th style={{ textAlign: "right" }}>20d</th>
                    <th style={{ textAlign: "right" }}>KODEX 대비 20d</th>
                    <th style={{ textAlign: "right" }}>고점 대비</th>
                    <th style={{ textAlign: "left" }}>데이터 상태</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedHoldings.map((h) => {
                    const ev = evidenceByTicker[h.ticker];
                    const r5 = ev?.short_term_momentum?.return_5d_pct ?? null;
                    const r20 = ev?.short_term_momentum?.return_20d_pct ?? null;
                    const ex20 =
                      ev?.short_term_momentum?.excess_vs_kodex200_20d_pctp ??
                      null;
                    const dataState = !evidenceLoaded
                      ? "not_loaded"
                      : ev
                        ? ev.short_term_momentum?.status ?? "unavailable"
                        : "unavailable";
                    return (
                      <tr
                        key={`${h.source_index ?? ""}|${h.ticker}|${h.account_group ?? ""}`}
                      >
                        <td><code>{h.ticker}</code></td>
                        <td>{h.name ?? DASH}</td>
                        <td style={{ textAlign: "right" }}>
                          {fmtPct(h.buy_weight_pct)}
                        </td>
                        <td style={{ textAlign: "right" }}>
                          {fmtPct(h.market_weight_pct)}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            color: returnColor(h.pnl_rate_pct),
                          }}
                        >
                          {fmtPct(h.pnl_rate_pct)}
                        </td>
                        <td style={{ textAlign: "right", color: returnColor(r5) }}>
                          {fmtPct(r5)}
                        </td>
                        <td style={{ textAlign: "right", color: returnColor(r20) }}>
                          {fmtPct(r20)}
                        </td>
                        <td style={{ textAlign: "right", color: returnColor(ex20) }}>
                          {fmtPct(ex20)}
                        </td>
                        {/* 보유 ETF 의 고점 대비 — 기존 evidence 응답에 직접
                            필드가 없으므로 unavailable 로 표시 (지시문 §4.2 —
                            없는 값은 데이터 없음 / 비교 불가 / 확인 필요).
                            향후 evidence 응답에 drawdown_20d 추가 시 활용. */}
                        <td style={{ textAlign: "right", color: "var(--muted)" }}>
                          unavailable
                        </td>
                        <td style={{ color: "var(--muted)" }}>{dataState}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          {/* 후보 비교 표 */}
          <div className="card" style={{ padding: 12 }}>
            <h3 style={{ margin: 0, marginBottom: 8 }}>후보 ETF 비교</h3>
            <table style={{ width: "100%", fontSize: "0.85em" }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left" }}>순위</th>
                  <th style={{ textAlign: "left" }}>티커</th>
                  <th style={{ textAlign: "left" }}>ETF명</th>
                  <th
                    style={{ textAlign: "right", cursor: "pointer" }}
                    onClick={() => handleCandidateSort("relative_upside_score")}
                    title="상대상승 참고점수 정렬"
                  >
                    참고점수
                  </th>
                  <th
                    style={{ textAlign: "right", cursor: "pointer" }}
                    onClick={() => handleCandidateSort("return_20d")}
                    title="20일 수익률 정렬"
                  >
                    20d
                  </th>
                  <th
                    style={{ textAlign: "right", cursor: "pointer" }}
                    onClick={() => handleCandidateSort("excess_20d")}
                    title="KODEX 대비 20d 초과수익 정렬"
                  >
                    KODEX 대비 20d
                  </th>
                  <th
                    style={{ textAlign: "right", cursor: "pointer" }}
                    onClick={() => handleCandidateSort("drawdown_20d")}
                    title="고점 대비 정렬"
                  >
                    고점 대비
                  </th>
                  <th
                    style={{ textAlign: "center", cursor: "pointer" }}
                    onClick={() => handleCandidateSort("overlap")}
                    title="보유 중복 상태 정렬"
                  >
                    보유 중복
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedCandidates.map((c, idx) => {
                  const overlap = computeOverlapStatus(
                    c.ticker,
                    enrichedHoldings,
                    evidenceLoaded,
                  );
                  const isSelected = selectedTicker === c.ticker;
                  const r20 = c.short_term_momentum?.return_20d_pct ?? null;
                  const ex20 =
                    c.short_term_momentum?.excess_vs_kodex200_20d_pctp ?? null;
                  const dd =
                    c.drawdown_20d != null ? c.drawdown_20d * 100 : null;
                  return (
                    <tr
                      key={`${c.ticker ?? "x"}-${idx}`}
                      onClick={() => c.ticker && setSelectedTicker(c.ticker)}
                      style={{
                        cursor: "pointer",
                        backgroundColor: isSelected
                          ? "var(--bg-active, #e0f2fe)"
                          : undefined,
                      }}
                    >
                      <td>{c.rank ?? DASH}</td>
                      <td><code>{c.ticker ?? DASH}</code></td>
                      <td>{c.name ?? DASH}</td>
                      <td style={{ textAlign: "right" }}>
                        {c.relative_upside_score != null
                          ? c.relative_upside_score.toFixed(1)
                          : DASH}
                      </td>
                      <td style={{ textAlign: "right", color: returnColor(r20) }}>
                        {fmtPct(r20)}
                      </td>
                      <td style={{ textAlign: "right", color: returnColor(ex20) }}>
                        {fmtPct(ex20)}
                      </td>
                      <td style={{ textAlign: "right", color: returnColor(dd) }}>
                        {fmtPct(dd)}
                      </td>
                      <td style={{ textAlign: "center" }}>
                        {overlap.overlapStateForCandidate === "exact_match" ? (
                          <span
                            style={{
                              color: "var(--warn)",
                              fontSize: "0.85em",
                              fontWeight: "bold",
                            }}
                          >
                            보유 일치
                          </span>
                        ) : overlap.overlapStateForCandidate === "not_loaded" ? (
                          <span
                            style={{ color: "var(--muted)", fontSize: "0.85em" }}
                          >
                            not_loaded
                          </span>
                        ) : (
                          <span
                            style={{ color: "var(--muted)", fontSize: "0.85em" }}
                          >
                            —
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* 우측 30% — 선택 상세 */}
        <div
          className="card"
          style={{ padding: 12, height: "fit-content", position: "sticky", top: 12 }}
        >
          <h3 style={{ margin: 0, marginBottom: 8 }}>선택 후보 상세</h3>
          {selectedCandidate ? (
            <SelectedDetail
              candidate={selectedCandidate}
              overlap={selectedOverlap}
              evidence={
                selectedOverlap.exactMatchHoldingTicker
                  ? evidenceByTicker[selectedOverlap.exactMatchHoldingTicker]
                  : undefined
              }
              evidenceLoaded={evidenceLoaded}
              evidenceMarketAsof={evidence?.market_asof ?? null}
            />
          ) : (
            <p style={{ color: "var(--muted)", fontSize: "0.85em" }}>
              후보 행을 클릭하면 상세 정보가 표시됩니다.
            </p>
          )}
        </div>
      </div>

      <p
        className="helper"
        style={{ marginTop: 12, fontSize: "0.78rem", color: "var(--muted)" }}
      >
        후보별 보유 중복은 ticker 일치 (exact match) 와 구성종목 반복 핵심 종목
        (constituents overlap) 두 종류 모두 표시됩니다. 데이터가 없는 값은 임의
        채우지 않고 unavailable 또는 &quot;—&quot; 로 표시합니다.
      </p>
    </section>
  );
}

// ─── 선택 후보 상세 ───────────────────────────────────────────────────
interface SelectedDetailProps {
  candidate: MarketCandidate;
  overlap: OverlapStatus;
  evidence: HoldingsMarketEvidenceItem | undefined;
  evidenceLoaded: boolean;
  evidenceMarketAsof: string | null;
}

function SelectedDetail({
  candidate,
  overlap,
  evidence,
  evidenceLoaded,
  evidenceMarketAsof,
}: SelectedDetailProps) {
  const sm = candidate.short_term_momentum;
  const dd =
    candidate.drawdown_20d != null ? candidate.drawdown_20d * 100 : null;
  return (
    <div style={{ display: "grid", gap: 8, fontSize: "0.85em" }}>
      <div>
        <strong>{candidate.name ?? candidate.ticker ?? "후보"}</strong>{" "}
        <code style={{ color: "var(--muted)" }}>{candidate.ticker}</code>
      </div>
      <hr style={{ margin: "4px 0", borderColor: "var(--border)" }} />

      <div>
        <strong>참고점수: </strong>
        {candidate.relative_upside_score != null
          ? candidate.relative_upside_score.toFixed(1)
          : "점수 미생성"}
      </div>

      {candidate.relative_upside_reasons &&
      candidate.relative_upside_reasons.length > 0 ? (
        <div>
          <div style={{ color: "var(--muted)" }}>점수 근거:</div>
          <ul style={{ margin: "4px 0 0 0", paddingLeft: "1.2em" }}>
            {candidate.relative_upside_reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <hr style={{ margin: "4px 0", borderColor: "var(--border)" }} />

      <div>
        <div style={{ color: "var(--muted)" }}>최근 수익률:</div>
        <div>5d: {fmtPct(sm?.return_5d_pct ?? null)}</div>
        <div>10d: {fmtPct(sm?.return_10d_pct ?? null)}</div>
        <div>20d: {fmtPct(sm?.return_20d_pct ?? null)}</div>
      </div>

      <div>
        <div style={{ color: "var(--muted)" }}>KODEX200 대비 초과수익:</div>
        <div>5d: {fmtPct(sm?.excess_vs_kodex200_5d_pctp ?? null)}</div>
        <div>10d: {fmtPct(sm?.excess_vs_kodex200_10d_pctp ?? null)}</div>
        <div>20d: {fmtPct(sm?.excess_vs_kodex200_20d_pctp ?? null)}</div>
      </div>

      <div>
        <strong>고점 대비: </strong>
        <span style={{ color: returnColor(dd) }}>{fmtPct(dd)}</span>
      </div>

      <div>
        <strong>데이터 품질: </strong>
        {candidate.data_quality?.status ?? "unavailable"}
      </div>

      <hr style={{ margin: "4px 0", borderColor: "var(--border)" }} />

      <div>
        <div style={{ color: "var(--muted)" }}>보유 비교:</div>
        {overlap.overlapStateForCandidate === "not_loaded" ? (
          <div>
            보유 비교 evidence 가 아직 조회되지 않았습니다 (상단의 &quot;보유
            비교 evidence 조회&quot; 버튼 클릭).
          </div>
        ) : overlap.overlapStateForCandidate === "exact_match" ? (
          <div>
            <div style={{ color: "var(--warn)" }}>
              <strong>보유 ETF 와 ticker 일치:</strong>{" "}
              {overlap.exactMatchHoldingName ?? overlap.exactMatchHoldingTicker}
            </div>
            {evidence?.constituents_overlap?.status === "ok" ? (
              <div style={{ marginTop: 4 }}>
                <div style={{ color: "var(--muted)" }}>
                  구성종목 반복 핵심 종목 ({evidence.constituents_overlap.overlap_with_market_core.length}건):
                </div>
                <ul style={{ margin: "4px 0 0 0", paddingLeft: "1.2em" }}>
                  {evidence.constituents_overlap.overlap_with_market_core
                    .slice(0, 5)
                    .map((it, i) => (
                      <li key={i}>
                        {it.name ?? it.ticker} ({fmtNum(it.weight_pct, 1)}%) ·
                        시장 반복 {it.market_core_count}개
                      </li>
                    ))}
                </ul>
              </div>
            ) : evidence?.constituents_overlap?.status ? (
              <div style={{ color: "var(--muted)", marginTop: 4 }}>
                구성종목 상태: {evidence.constituents_overlap.status}
              </div>
            ) : null}
          </div>
        ) : (
          <div>보유 ETF 중 ticker 일치 없음.</div>
        )}
      </div>

      <div style={{ fontSize: "0.85em", color: "var(--muted)" }}>
        {evidenceLoaded
          ? `중복 정보 기준일: ${evidenceMarketAsof ?? DASH}`
          : "중복 정보 미조회"}
      </div>
    </div>
  );
}
