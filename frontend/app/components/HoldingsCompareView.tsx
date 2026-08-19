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
  STATE_NORMAL,
  STATE_UNAVAIL,
  STATE_UNCHECKED,
  aggregateHoldingsByTicker,
  computeExposure,
  exposureColorByState,
  exposureSortRank,
} from "./holdings_compare/helpers";
import DecisionDraftPreviewCard from "./holdings_compare/DecisionDraftPreviewCard";
import {
  HoldingCompareCards,
  CandidateCompareCards,
} from "./holdings_compare/CompareCards";
import SelectedDetail from "./holdings_compare/SelectedDetail";
import SelectedHoldingDetail from "./holdings_compare/SelectedHoldingDetail";

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

  // 2026-07-03 FIX r5 (사용자 지적 대응) — 컴포넌트 마운트 시 evidence 자동 로드.
  // 이전에는 "보유 비교 evidence 조회" 버튼을 눌러야만 short_term_momentum 등이
  // 화면에 표시되어 preview endpoint 가 자동 재계산한 값과 불일치했다.
  // 이제 화면 로드 시점에도 서버 preview 와 동일한 canonical 값을 표시한다.
  useEffect(() => {
    handleEvidenceFetch();
    // handleEvidenceFetch 는 evidenceLoading 에만 의존 — 한 번만 fetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

      {/* 2026-08-19 배치 정정 — 이 화면의 목적은 *보유와 후보를 나란히 견주는 것*이라
          목업도 좌우 2열이었고 `.wb-hrow.compact` CSS 도 2열 전제로 쓰여 있었는데,
          컨테이너만 이전 세로 배치(1fr 360px)로 남아 있었다. 승인받은 목업대로
          좌우 2열로 바꾸고 선택 상세를 아래 전체 폭으로 내린다. */}
      <div className="cmp-twocol">
        {/* 보유 ETF */}
        <div className="card" style={{ padding: 12 }}>
          <h3 style={{ margin: 0, marginBottom: 8 }}>보유 ETF</h3>
          {enrichedLoading ? (
            <p>보유 정보 조회 중...</p>
          ) : enrichedError ? (
            <p style={{ color: "var(--danger)" }}>보유 정보 조회 실패.</p>
          ) : aggregated.length === 0 ? (
            <p style={{ color: "var(--muted)" }}>보유 ETF 가 없습니다.</p>
          ) : (
            <>
              {/* 2026-08-16 카드 전환 — 정렬은 헤더 클릭 → 세그먼트 바로 이동.
                  정렬 키(비중·손익률·20일 초과)는 그대로다. */}
              <div className="holdings-sortbar" style={{ margin: "0 0 8px" }}>
                <span className="holdings-sortbar-label">정렬</span>
                <span className="holdings-sort-seg">
                  {(
                    [
                      ["weight", "비중"],
                      ["pnl", "손익률"],
                      ["excess_20d", "20일 초과"],
                    ] as [HoldingSortKey, string][]
                  ).map(([k, label]) => (
                    <button
                      key={k}
                      type="button"
                      className={holdSortKey === k ? "on" : undefined}
                      aria-pressed={holdSortKey === k}
                      onClick={() => handleHoldSort(k)}
                    >
                      {label}
                      {holdSortKey === k
                        ? holdSortDir === "asc"
                          ? " ▲"
                          : " ▼"
                        : ""}
                    </button>
                  ))}
                </span>
              </div>
              <HoldingCompareCards
                rows={sortedHoldings}
                evidenceByTicker={evidenceByTicker}
                selectedTicker={
                  selectedKind === "holding" ? selectedHoldingTicker : null
                }
                onSelect={(tk) => {
                  setSelectedKind("holding");
                  setSelectedHoldingTicker(tk);
                  setSelectedTicker(null);
                }}
              />
            </>
          )}
        </div>

        {/* 후보 ETF 표 */}
        <div className="card" style={{ padding: 12 }}>
          <h3 style={{ margin: 0, marginBottom: 8 }}>후보 ETF</h3>
          {/* 2026-08-16 카드 전환 — 정렬 키(참고점수·20일 초과·고점 대비·보유 노출)
              는 그대로 두고 헤더 클릭 → 세그먼트 바로 옮긴다. */}
          <div className="holdings-sortbar" style={{ margin: "0 0 8px" }}>
            <span className="holdings-sortbar-label">정렬</span>
            <span className="holdings-sort-seg">
              {(
                [
                  ["score", "참고점수"],
                  ["excess_20d", "20일 초과"],
                  ["drawdown", "고점 대비"],
                  ["exposure", "보유 노출"],
                ] as [CandidateSortKey, string][]
              ).map(([k, label]) => (
                <button
                  key={k}
                  type="button"
                  className={candSortKey === k ? "on" : undefined}
                  aria-pressed={candSortKey === k}
                  onClick={() => handleCandSort(k)}
                >
                  {label}
                  {candSortKey === k
                    ? candSortDir === "asc"
                      ? " ▲"
                      : " ▼"
                    : ""}
                </button>
              ))}
            </span>
          </div>
          <CandidateCompareCards
            rows={sortedCandidates}
            basis={data.basis ?? "one_month"}
            exposureByTicker={exposureByTicker}
            selectedTicker={selectedKind === "candidate" ? selectedTicker : null}
            onSelect={(tk) => {
              setSelectedKind("candidate");
              setSelectedTicker(tk);
              setSelectedHoldingTicker(null);
            }}
          />
        </div>
      </div>

      {/* 선택 상세 (FIX r1 — 별도 컴포넌트). 2026-08-19 배치 정정으로 우측
          360px 열에서 2열 아래 전체 폭으로 내려왔다. 내용은 손대지 않는다. */}
      <div className="card" style={{ padding: 12, marginTop: 12 }}>
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
              if (!h) {
                return (
                  <p style={{ color: "var(--muted)", fontSize: "0.85em" }}>
                    보유 정보 조회 실패.
                  </p>
                );
              }
              return (
                <div style={{ display: "grid", gap: 8, fontSize: "0.85em" }}>
                  {/* 2026-08-16 에 평가 비중·손익률·20일 초과 3줄을 뺐고(카드와 중복)
                      2026-08-19 사용자 지적으로 **카드에 없는 값**을 채운다.
                      계좌별 원본 행을 함께 넘겨 수량·평균단가를 계좌 계약대로 쓴다. */}
                  <SelectedHoldingDetail
                    holding={h}
                    rows={enrichedRaw.filter((r) => r.ticker === h.ticker)}
                    evidence={evidenceByTicker[h.ticker]}
                    evidenceLoaded={evidenceLoaded}
                  />
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
