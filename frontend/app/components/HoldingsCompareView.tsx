"use client";

// POC2 — 보유 ETF와 시장 후보 비교 v1 (2026-06-21).
// CLOSEOUT (2026-06-24) + FIX r1 (2026-06-24, B-3 분리):
// helper / SelectedDetail 컴포넌트 분리 → 본 파일은 fetch + state + 표 렌더만.

import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  EnrichedHolding,
  HoldingsMarketEvidenceItem,
  HoldingsMarketEvidenceResponse,
  MarketCandidate,
  MarketTopNResponse,
} from "@/lib/api";
import {
  fetchEnrichedHoldings,
  fetchHoldingsMarketEvidence,
} from "@/lib/api/holdings";
import {
  type AggregatedHolding,
  type ExposureSummary,
  DASH,
  STATE_NEED_CHECK,
  STATE_NORMAL,
  STATE_UNAVAIL,
  STATE_UNCHECKED,
  aggregateHoldingsByTicker,
  candidateDataState,
  computeExposure,
  exposureColor,
  exposureColorByState,
  exposureLabel,
  exposureSortRank,
  fmtPct,
  holdingStateLabel,
  returnColor,
} from "./holdings_compare/helpers";
import DecisionDraftPreviewCard from "./holdings_compare/DecisionDraftPreviewCard";
import SelectedDetail from "./holdings_compare/SelectedDetail";

type CandidateSortKey =
  | "default"
  | "score"
  | "excess_20d"
  | "drawdown"
  | "exposure";
type HoldingSortKey = "default" | "weight" | "pnl" | "excess_20d";
type SortDirection = "desc" | "asc";

interface Props {
  data: MarketTopNResponse;
}

export default function HoldingsCompareView({ data }: Props) {
  const [enrichedRaw, setEnrichedRaw] = useState<EnrichedHolding[]>([]);
  const [enrichedLoading, setEnrichedLoading] = useState<boolean>(false);
  const [enrichedError, setEnrichedError] = useState<string | null>(null);

  const [evidence, setEvidence] =
    useState<HoldingsMarketEvidenceResponse | null>(null);
  const [evidenceLoading, setEvidenceLoading] = useState<boolean>(false);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);

  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  // 2026-07-03 Decision Draft Preview v1 — 선택 대상 종류 (보유 vs 후보 상호 배타).
  const [selectedKind, setSelectedKind] = useState<"holding" | "candidate" | null>(
    null,
  );
  const [selectedHoldingTicker, setSelectedHoldingTicker] = useState<string | null>(
    null,
  );
  const [detailsExpanded, setDetailsExpanded] = useState<boolean>(false);

  const [candSortKey, setCandSortKey] = useState<CandidateSortKey>("default");
  const [candSortDir, setCandSortDir] = useState<SortDirection>("desc");
  const [holdSortKey, setHoldSortKey] = useState<HoldingSortKey>("default");
  const [holdSortDir, setHoldSortDir] = useState<SortDirection>("desc");

  useEffect(() => {
    let canceled = false;
    setEnrichedLoading(true);
    setEnrichedError(null);
    fetchEnrichedHoldings()
      .then((res) => {
        if (canceled) return;
        setEnrichedRaw(res.items ?? []);
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

  const handleEvidenceFetch = useCallback(async () => {
    if (evidenceLoading) return;
    setEvidenceLoading(true);
    setEvidenceError(null);
    try {
      const res = await fetchHoldingsMarketEvidence();
      setEvidence(res);
    } catch (e) {
      setEvidenceError((e as Error).message ?? "Evidence 조회 실패");
      // 기존 evidence 유지 (지시문 — 조회 실패 시 기존 값 삭제 X).
    } finally {
      setEvidenceLoading(false);
    }
  }, [evidenceLoading]);

  const aggregated = useMemo<AggregatedHolding[]>(
    () => aggregateHoldingsByTicker(enrichedRaw),
    [enrichedRaw],
  );

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

  const exposureByTicker = useMemo(() => {
    const m: Record<string, ExposureSummary> = {};
    for (const c of data.candidates ?? []) {
      if (!c.ticker) continue;
      m[c.ticker] = computeExposure(
        c.ticker,
        aggregated,
        evidenceByTicker,
        evidenceLoaded,
        evidenceError !== null,
      );
    }
    return m;
  }, [
    data.candidates,
    aggregated,
    evidenceByTicker,
    evidenceLoaded,
    evidenceError,
  ]);

  const sortedCandidates = useMemo<MarketCandidate[]>(() => {
    const list = [...(data.candidates ?? [])];
    if (candSortKey === "default") return list;
    const dirMul = candSortDir === "desc" ? -1 : 1;
    const getKey = (c: MarketCandidate): number | null => {
      switch (candSortKey) {
        case "score":
          return c.relative_upside_score ?? null;
        case "excess_20d":
          return c.short_term_momentum?.excess_vs_kodex200_20d_pctp ?? null;
        case "drawdown":
          return c.drawdown_20d ?? null;
        case "exposure": {
          if (!c.ticker) return null;
          const ex = exposureByTicker[c.ticker];
          return ex ? exposureSortRank(ex.kind) : null;
        }
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
  }, [data.candidates, candSortKey, candSortDir, exposureByTicker]);

  const sortedHoldings = useMemo<AggregatedHolding[]>(() => {
    const list = [...aggregated];
    if (holdSortKey === "default") return list;
    const dirMul = holdSortDir === "desc" ? -1 : 1;
    const getKey = (h: AggregatedHolding): number | null => {
      switch (holdSortKey) {
        case "weight":
          return h.market_weight_pct ?? null;
        case "pnl":
          return h.pnl_rate_pct ?? null;
        case "excess_20d":
          return (
            evidenceByTicker[h.ticker]?.short_term_momentum
              ?.excess_vs_kodex200_20d_pctp ?? null
          );
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
  }, [aggregated, holdSortKey, holdSortDir, evidenceByTicker]);

  const selectedCandidate = useMemo<MarketCandidate | null>(() => {
    if (!selectedTicker) return null;
    return (
      (data.candidates ?? []).find((c) => c.ticker === selectedTicker) ?? null
    );
  }, [selectedTicker, data.candidates]);

  const selectedExposure = useMemo<ExposureSummary | null>(() => {
    if (!selectedCandidate?.ticker) return null;
    return exposureByTicker[selectedCandidate.ticker] ?? null;
  }, [selectedCandidate, exposureByTicker]);

  const evidenceHeaderState = evidenceLoading
    ? "확인 중"
    : evidenceLoaded
      ? STATE_NORMAL
      : evidenceError
        ? STATE_UNAVAIL
        : STATE_UNCHECKED;

  const handleCandSort = useCallback(
    (key: CandidateSortKey) => {
      if (key === candSortKey) {
        setCandSortDir((d) => (d === "desc" ? "asc" : "desc"));
      } else {
        setCandSortKey(key);
        setCandSortDir("desc");
      }
    },
    [candSortKey],
  );
  const handleHoldSort = useCallback(
    (key: HoldingSortKey) => {
      if (key === holdSortKey) {
        setHoldSortDir((d) => (d === "desc" ? "asc" : "desc"));
      } else {
        setHoldSortKey(key);
        setHoldSortDir("desc");
      }
    },
    [holdSortKey],
  );

  return (
    <section style={{ marginTop: 16 }}>
      {/* 기준일 헤더 */}
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
          <span style={{ color: "var(--muted)" }}>보유 기준일: </span>
          <span>{evidence?.holdings_asof ?? DASH}</span>
        </div>
        <div>
          <span style={{ color: "var(--muted)" }}>중복 정보: </span>
          <span style={{ color: exposureColorByState(evidenceHeaderState) }}>
            {evidenceHeaderState}
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
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 12 }}>
        <div style={{ display: "grid", gap: 12 }}>
          {/* 보유 ETF 표 */}
          <div className="card" style={{ padding: 12 }}>
            <h3 style={{ margin: 0, marginBottom: 8 }}>보유 ETF</h3>
            {enrichedLoading ? (
              <p>보유 정보 조회 중...</p>
            ) : enrichedError ? (
              <p style={{ color: "var(--danger)" }}>보유 정보 조회 실패.</p>
            ) : aggregated.length === 0 ? (
              <p style={{ color: "var(--muted)" }}>보유 ETF 가 없습니다.</p>
            ) : (
              <table style={{ width: "100%", fontSize: "0.85em" }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left" }}>ETF명</th>
                    <th
                      style={{ textAlign: "right", cursor: "pointer" }}
                      onClick={() => handleHoldSort("weight")}
                    >
                      평가 비중
                    </th>
                    <th
                      style={{ textAlign: "right", cursor: "pointer" }}
                      onClick={() => handleHoldSort("pnl")}
                    >
                      손익률
                    </th>
                    <th
                      style={{ textAlign: "right", cursor: "pointer" }}
                      onClick={() => handleHoldSort("excess_20d")}
                    >
                      20일 KODEX 초과
                    </th>
                    <th style={{ textAlign: "right" }}>고점 대비</th>
                    <th style={{ textAlign: "left" }}>상태</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedHoldings.map((h) => {
                    const ev = evidenceByTicker[h.ticker];
                    const ex20 =
                      ev?.short_term_momentum?.excess_vs_kodex200_20d_pctp ??
                      null;
                    const isHoldSelected =
                      selectedKind === "holding" && selectedHoldingTicker === h.ticker;
                    return (
                      <tr
                        key={h.ticker}
                        onClick={() => {
                          setSelectedKind("holding");
                          setSelectedHoldingTicker(h.ticker);
                          setSelectedTicker(null);
                        }}
                        style={{
                          cursor: "pointer",
                          backgroundColor: isHoldSelected
                            ? "var(--bg-active, #e0f2fe)"
                            : undefined,
                        }}
                      >
                        <td>
                          <strong>{h.name ?? h.ticker}</strong>{" "}
                          <code
                            style={{ color: "var(--muted)", fontSize: "0.85em" }}
                          >
                            {h.ticker}
                          </code>
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
                        <td
                          style={{
                            textAlign: "right",
                            color: returnColor(ex20),
                          }}
                        >
                          {fmtPct(ex20)}
                        </td>
                        {/* 보유 ETF 의 고점 대비 — evidence 응답에 직접 필드 없음.
                            FIX r1-2 (A-1): 중복 상태 문구 미사용. "확인 필요" 단일 표기. */}
                        <td
                          style={{ textAlign: "right", color: "var(--muted)" }}
                        >
                          {STATE_NEED_CHECK}
                        </td>
                        <td style={{ color: "var(--muted)" }}>
                          {holdingStateLabel(h)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          {/* 후보 ETF 표 */}
          <div className="card" style={{ padding: 12 }}>
            <h3 style={{ margin: 0, marginBottom: 8 }}>후보 ETF</h3>
            <table style={{ width: "100%", fontSize: "0.85em" }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left" }}>ETF명</th>
                  <th
                    style={{ textAlign: "right", cursor: "pointer" }}
                    onClick={() => handleCandSort("score")}
                  >
                    참고점수
                  </th>
                  <th
                    style={{ textAlign: "right", cursor: "pointer" }}
                    onClick={() => handleCandSort("excess_20d")}
                  >
                    20일 KODEX 초과
                  </th>
                  <th
                    style={{ textAlign: "right", cursor: "pointer" }}
                    onClick={() => handleCandSort("drawdown")}
                  >
                    고점 대비
                  </th>
                  <th
                    style={{ textAlign: "left", cursor: "pointer" }}
                    onClick={() => handleCandSort("exposure")}
                  >
                    보유 노출
                  </th>
                  <th style={{ textAlign: "left" }}>데이터 상태</th>
                </tr>
              </thead>
              <tbody>
                {sortedCandidates.map((c, idx) => {
                  const ex20 =
                    c.short_term_momentum?.excess_vs_kodex200_20d_pctp ?? null;
                  const dd =
                    c.drawdown_20d != null ? c.drawdown_20d * 100 : null;
                  const exposure = c.ticker
                    ? exposureByTicker[c.ticker]
                    : undefined;
                  const isSelected = selectedTicker === c.ticker;
                  const isDirectKind =
                    exposure?.kind === "direct_only" ||
                    exposure?.kind === "direct_and_overlap";
                  return (
                    <tr
                      key={`${c.ticker ?? "x"}-${idx}`}
                      onClick={() => {
                        if (!c.ticker) return;
                        setSelectedTicker(c.ticker);
                        setSelectedKind("candidate");
                        setSelectedHoldingTicker(null);
                      }}
                      style={{
                        cursor: "pointer",
                        backgroundColor: isSelected
                          ? "var(--bg-active, #e0f2fe)"
                          : undefined,
                      }}
                    >
                      <td>
                        <strong>{c.name ?? c.ticker}</strong>{" "}
                        <code
                          style={{ color: "var(--muted)", fontSize: "0.85em" }}
                        >
                          {c.ticker}
                        </code>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {c.relative_upside_score != null
                          ? c.relative_upside_score.toFixed(1)
                          : DASH}
                      </td>
                      <td
                        style={{ textAlign: "right", color: returnColor(ex20) }}
                      >
                        {fmtPct(ex20)}
                      </td>
                      <td style={{ textAlign: "right", color: returnColor(dd) }}>
                        {fmtPct(dd)}
                      </td>
                      <td>
                        {exposure ? (
                          <span
                            style={{
                              color: exposureColor(exposure),
                              fontSize: "0.9em",
                              fontWeight: isDirectKind ? "bold" : "normal",
                            }}
                          >
                            {exposureLabel(exposure)}
                          </span>
                        ) : (
                          <span style={{ color: "var(--muted)" }}>
                            {STATE_UNCHECKED}
                          </span>
                        )}
                      </td>
                      <td style={{ color: "var(--muted)" }}>
                        {candidateDataState(c)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* 우측 30% — 선택 상세 (FIX r1 — 별도 컴포넌트) */}
        <div
          className="card"
          style={{
            padding: 12,
            height: "fit-content",
            position: "sticky",
            top: 12,
          }}
        >
          <h3 style={{ margin: 0, marginBottom: 8 }}>
            {selectedKind === "holding" ? "선택 보유 상세" : "선택 후보 상세"}
          </h3>
          {selectedKind === "candidate" && selectedCandidate && selectedExposure ? (
            <>
              <SelectedDetail
                candidate={selectedCandidate}
                exposure={selectedExposure}
                expanded={detailsExpanded}
                onToggleExpanded={() => setDetailsExpanded((v) => !v)}
                directHoldingEvidence={
                  selectedExposure.directHoldingTicker
                    ? evidenceByTicker[selectedExposure.directHoldingTicker]
                    : undefined
                }
              />
              {selectedCandidate.ticker ? (
                <div style={{ marginTop: 12, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
                  <DecisionDraftPreviewCard
                    targetKind="candidate"
                    ticker={selectedCandidate.ticker}
                    displayName={selectedCandidate.name ?? selectedCandidate.ticker}
                  />
                </div>
              ) : null}
            </>
          ) : selectedKind === "holding" && selectedHoldingTicker ? (
            <>
              {(() => {
                const h = aggregated.find((x) => x.ticker === selectedHoldingTicker);
                const ev = evidenceByTicker[selectedHoldingTicker];
                if (!h) {
                  return (
                    <p style={{ color: "var(--muted)", fontSize: "0.85em" }}>
                      보유 정보 조회 실패.
                    </p>
                  );
                }
                return (
                  <div style={{ display: "grid", gap: 8, fontSize: "0.85em" }}>
                    <div>
                      <strong>{h.name ?? h.ticker}</strong>{" "}
                      <code style={{ color: "var(--muted)" }}>{h.ticker}</code>
                    </div>
                    <div>평가 비중: {fmtPct(h.market_weight_pct)}</div>
                    <div>손익률: {fmtPct(h.pnl_rate_pct)}</div>
                    <div>
                      20일 KODEX 초과:{" "}
                      {fmtPct(
                        ev?.short_term_momentum?.excess_vs_kodex200_20d_pctp ??
                          null,
                      )}
                    </div>
                    <div style={{ marginTop: 8, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
                      <DecisionDraftPreviewCard
                        targetKind="holding"
                        ticker={h.ticker}
                        displayName={h.name ?? h.ticker}
                      />
                    </div>
                  </div>
                );
              })()}
            </>
          ) : (
            <p style={{ color: "var(--muted)", fontSize: "0.85em" }}>
              보유 또는 후보 행을 클릭하면 상세 정보가 표시됩니다.
            </p>
          )}
        </div>
      </div>

      <p
        className="helper"
        style={{ marginTop: 12, fontSize: "0.78rem", color: "var(--muted)" }}
      >
        보유 노출은 직접 보유 여부 (ticker 일치) 와 구성종목 겹침 (보유 ETF 의
        구성종목이 시장 반복 핵심 종목과 겹치는지) 을 합쳐 한 칸에 표시합니다.
        데이터가 없는 값은 임의 채우지 않고 &quot;데이터 없음&quot; / &quot;확인
        필요&quot; / &quot;중복 확인 전&quot; / &quot;중복 확인 불가&quot; 로
        표시합니다.
      </p>
    </section>
  );
}
