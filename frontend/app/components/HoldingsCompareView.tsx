"use client";

// POC2 — 보유 ETF와 시장 후보 비교 v1 (2026-06-21).
// CLOSEOUT (2026-06-23): 사용자가 10초 안에 (1) 실제 보유 ETF·평가 비중,
// (2) 후보의 보유 노출 겹침, (3) 후보의 상대 흐름을 판단 가능하도록 정리.
//
// 변경 핵심:
//   - 보유 ETF 행 단위를 매입 회차가 아닌 **티커별 통합** 으로 변경 (AC-1).
//   - 보유 표 6 컬럼: ETF명 / 평가 비중 / 손익률 / 20일 KODEX 초과 / 고점 대비 / 상태.
//   - 후보 표 6 컬럼: ETF명 / 점수 / 20일 초과 / 고점 대비 / 보유 노출 / 데이터 상태.
//   - 후보 "보유 노출" 1 칸에 직접 보유 / 구성종목 겹침 / 중복 없음 표현 통합.
//   - 후보 선택 상세: 보유 노출 요약 → 후보 흐름 → 세부 근거 (접힘).
//   - raw 상태값 (ok/unavailable/not_loaded) 사용자 화면 미노출.
//
// 신규 API / 신규 계산 0건. 기존 holdings_enriched + market_evidence + topn
// 응답을 client-side 조합.

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

function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return DASH;
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function returnColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return "var(--muted)";
  return value >= 0 ? "var(--ok)" : "var(--danger)";
}

// 보유 표 + 후보 표 사용자 친화 상태 문구 (지시문 — raw 상태값 미노출).
const STATE_NORMAL = "정상";
const STATE_PARTIAL_UNAVAIL = "일부 확인 불가";
const STATE_UNCHECKED = "중복 확인 전";
const STATE_UNAVAIL = "중복 확인 불가";
const STATE_NO_DATA = "데이터 없음";
const STATE_NEED_CHECK = "확인 필요";

// ─── 티커별 통합 보유 (AC-1) ─────────────────────────────────────────

interface AggregatedHolding {
  ticker: string;
  name: string | null;
  // 통합 매입금액 (Σ invested_amount).
  invested_amount: number;
  // 통합 평가금액 (Σ eval_amount). null 행이 1건이라도 있으면 부분 unavail.
  eval_amount: number | null;
  eval_partial_unavail: boolean;
  // 통합 손익률 = Σ pnl / Σ invested (전체 매입금액 기준).
  pnl_rate_pct: number | null;
  // 평가 비중 = ticker eval / 전체 eval. 전체 eval 0 이거나 null 이면 null.
  market_weight_pct: number | null;
  // 행 데이터 미수집 여부 (price_missing | calc_missing 가 1건이라도 true).
  data_missing: boolean;
}

function aggregateHoldingsByTicker(
  rows: EnrichedHolding[],
): AggregatedHolding[] {
  if (rows.length === 0) return [];

  // 전체 평가금액 (Σ eval_amount, null 제외).
  const totalEval = rows.reduce(
    (acc, r) => acc + (r.eval_amount ?? 0),
    0,
  );

  // ticker → rows 그룹화 (순서 유지를 위해 처음 등장 ticker 순).
  const byTicker = new Map<string, EnrichedHolding[]>();
  for (const r of rows) {
    const arr = byTicker.get(r.ticker) ?? [];
    arr.push(r);
    byTicker.set(r.ticker, arr);
  }

  const result: AggregatedHolding[] = [];
  for (const [ticker, group] of byTicker) {
    const invested = group.reduce((acc, r) => acc + r.invested_amount, 0);
    let evalSum: number | null = 0;
    let evalPartial = false;
    let dataMissing = false;
    for (const r of group) {
      if (r.price_missing || r.calc_missing) dataMissing = true;
      if (r.eval_amount === null) {
        evalPartial = true;
      } else if (evalSum !== null) {
        evalSum += r.eval_amount;
      }
    }
    // 1건이라도 eval null 이면 통합 평가 부분 unavail — 합계 null 처리.
    if (evalPartial) evalSum = null;

    const pnlRate =
      evalSum !== null && invested > 0
        ? ((evalSum - invested) / invested) * 100
        : null;
    const marketWeight =
      evalSum !== null && totalEval > 0 ? (evalSum / totalEval) * 100 : null;

    result.push({
      ticker,
      name: group[0].name ?? null,
      invested_amount: invested,
      eval_amount: evalSum,
      eval_partial_unavail: evalPartial,
      pnl_rate_pct: pnlRate,
      market_weight_pct: marketWeight,
      data_missing: dataMissing,
    });
  }
  return result;
}

// ─── 보유 노출 1 칸 표현 (AC-4) ─────────────────────────────────────

type ExposureKind =
  | "direct_only" // 직접 보유 (구성종목 정보 없음)
  | "direct_and_overlap" // 직접 보유 · 구성종목도 겹침
  | "overlap_only" // 구성종목 겹침 · 보유 ETF N개
  | "no_overlap" // 중복 없음 (전부 정상 조회된 경우만)
  | "unchecked" // 중복 확인 전
  | "unavailable"; // 중복 확인 불가

interface ExposureSummary {
  kind: ExposureKind;
  // direct_only / direct_and_overlap 일 때: 직접 보유 ticker.
  directHoldingTicker: string | null;
  directHoldingName: string | null;
  // overlap reverse-lookup — 본 후보 ticker 가 어떤 보유 ETF 의
  // constituents_overlap.overlap_with_market_core 에 들어있는지.
  overlapHoldingCount: number;
  // 가장 weight_pct 가 큰 겹침 대상 (보유 ETF 이름).
  topOverlapHoldingName: string | null;
  topOverlapWeightPct: number | null;
}

function computeExposure(
  candidateTicker: string | null | undefined,
  aggregated: AggregatedHolding[],
  evidenceByTicker: Record<string, HoldingsMarketEvidenceItem>,
  evidenceLoaded: boolean,
  evidenceError: boolean,
): ExposureSummary {
  // 직접 보유 (exact match).
  const direct = candidateTicker
    ? aggregated.find((h) => h.ticker === candidateTicker)
    : undefined;
  const directHoldingTicker = direct?.ticker ?? null;
  const directHoldingName = direct?.name ?? null;

  // overlap reverse-lookup: 본 후보 ticker 가 어떤 보유 ETF 의 overlap_with_
  // market_core 리스트에 들어 있는가.
  let overlapHoldingCount = 0;
  let topOverlapHoldingName: string | null = null;
  let topOverlapWeightPct: number | null = null;
  let constituentsAnyUnavail = false;

  if (evidenceLoaded && candidateTicker) {
    for (const h of aggregated) {
      const ev = evidenceByTicker[h.ticker];
      if (!ev) continue;
      const co = ev.constituents_overlap;
      if (!co) continue;
      if (
        co.status === "constituents_unavailable" ||
        co.status === "market_core_unavailable" ||
        co.status === "unavailable"
      ) {
        constituentsAnyUnavail = true;
        continue;
      }
      const found = (co.overlap_with_market_core ?? []).find(
        (it) => it.ticker === candidateTicker,
      );
      if (found) {
        overlapHoldingCount += 1;
        const w = found.weight_pct ?? 0;
        if (topOverlapWeightPct === null || w > topOverlapWeightPct) {
          topOverlapWeightPct = found.weight_pct ?? null;
          topOverlapHoldingName = h.name;
        }
      }
    }
  }

  // 분류 (지시문 §1 §2 — 6가지).
  if (!evidenceLoaded) {
    if (evidenceError) {
      return {
        kind: "unavailable",
        directHoldingTicker,
        directHoldingName,
        overlapHoldingCount: 0,
        topOverlapHoldingName: null,
        topOverlapWeightPct: null,
      };
    }
    // 직접 보유는 evidence 없이도 enriched 만으로 판단 가능.
    if (direct) {
      return {
        kind: "direct_only",
        directHoldingTicker,
        directHoldingName,
        overlapHoldingCount: 0,
        topOverlapHoldingName: null,
        topOverlapWeightPct: null,
      };
    }
    return {
      kind: "unchecked",
      directHoldingTicker: null,
      directHoldingName: null,
      overlapHoldingCount: 0,
      topOverlapHoldingName: null,
      topOverlapWeightPct: null,
    };
  }

  // evidence 로드된 경우.
  if (direct && overlapHoldingCount > 0) {
    return {
      kind: "direct_and_overlap",
      directHoldingTicker,
      directHoldingName,
      overlapHoldingCount,
      topOverlapHoldingName,
      topOverlapWeightPct,
    };
  }
  if (direct) {
    return {
      kind: "direct_only",
      directHoldingTicker,
      directHoldingName,
      overlapHoldingCount: 0,
      topOverlapHoldingName: null,
      topOverlapWeightPct: null,
    };
  }
  if (overlapHoldingCount > 0) {
    return {
      kind: "overlap_only",
      directHoldingTicker: null,
      directHoldingName: null,
      overlapHoldingCount,
      topOverlapHoldingName,
      topOverlapWeightPct,
    };
  }
  if (constituentsAnyUnavail) {
    // 직접 보유도 없고 overlap 데이터도 일부 unavail → 중복 확인 불가.
    return {
      kind: "unavailable",
      directHoldingTicker: null,
      directHoldingName: null,
      overlapHoldingCount: 0,
      topOverlapHoldingName: null,
      topOverlapWeightPct: null,
    };
  }
  // 모든 보유 ETF 의 overlap 정상 조회됐고 일치 0건 → 진짜 "중복 없음".
  return {
    kind: "no_overlap",
    directHoldingTicker: null,
    directHoldingName: null,
    overlapHoldingCount: 0,
    topOverlapHoldingName: null,
    topOverlapWeightPct: null,
  };
}

function exposureLabel(ex: ExposureSummary): string {
  switch (ex.kind) {
    case "direct_only":
      return "직접 보유";
    case "direct_and_overlap":
      return "직접 보유 · 구성종목도 겹침";
    case "overlap_only":
      return `구성종목 겹침 · 보유 ETF ${ex.overlapHoldingCount}개`;
    case "no_overlap":
      return "중복 없음";
    case "unchecked":
      return STATE_UNCHECKED;
    case "unavailable":
      return STATE_UNAVAIL;
  }
}

function exposureColor(ex: ExposureSummary): string {
  switch (ex.kind) {
    case "direct_only":
    case "direct_and_overlap":
      return "var(--warn)";
    case "overlap_only":
      return "var(--warn)";
    case "no_overlap":
      return "var(--ok)";
    case "unchecked":
    case "unavailable":
    default:
      return "var(--muted)";
  }
}

// ─── 후보 행 데이터 상태 (지시문 — raw 상태 미노출) ─────────────────

function candidateDataState(c: MarketCandidate): string {
  const sm = c.short_term_momentum;
  const dq = c.data_quality;
  const smOk = sm?.status === "ok";
  const dqOk = dq?.status === "ok";
  if (smOk && dqOk) return STATE_NORMAL;
  if (smOk || dqOk) return STATE_PARTIAL_UNAVAIL;
  return STATE_NEED_CHECK;
}

function holdingStateLabel(h: AggregatedHolding): string {
  if (h.eval_partial_unavail || h.data_missing) return STATE_PARTIAL_UNAVAIL;
  if (h.eval_amount === null) return STATE_NO_DATA;
  return STATE_NORMAL;
}

// ─── 정렬 키 ─────────────────────────────────────────────────────────

type CandidateSortKey =
  | "default"
  | "score"
  | "excess_20d"
  | "drawdown"
  | "exposure";
type HoldingSortKey = "default" | "weight" | "pnl" | "excess_20d";
type SortDirection = "desc" | "asc";

function exposureSortRank(kind: ExposureKind): number {
  // 직접 보유 > 직접+겹침 > 겹침만 > 중복 없음 > 확인 전 > 확인 불가.
  switch (kind) {
    case "direct_and_overlap":
      return 5;
    case "direct_only":
      return 4;
    case "overlap_only":
      return 3;
    case "no_overlap":
      return 2;
    case "unchecked":
      return 1;
    case "unavailable":
    default:
      return 0;
  }
}

// ─── 메인 컴포넌트 ───────────────────────────────────────────────────

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

  // 티커별 통합 보유 (AC-1).
  const aggregated = useMemo<AggregatedHolding[]>(
    () => aggregateHoldingsByTicker(enrichedRaw),
    [enrichedRaw],
  );

  // ticker → evidence item 룩업.
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

  // 후보별 노출 (정렬용 사전 계산).
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
  }, [data.candidates, aggregated, evidenceByTicker, evidenceLoaded, evidenceError]);

  // 후보 정렬.
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

  // 보유 정렬.
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

  // 선택 후보 + 노출 요약.
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

  // 중복 정보 상태 헤더 문구 (사용자 친화).
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
          {/* 보유 ETF 표 (AC-1, AC-2) */}
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
                    return (
                      <tr key={h.ticker}>
                        <td>
                          <strong>{h.name ?? h.ticker}</strong>{" "}
                          <code style={{ color: "var(--muted)", fontSize: "0.85em" }}>
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
                          style={{ textAlign: "right", color: returnColor(ex20) }}
                        >
                          {fmtPct(ex20)}
                        </td>
                        {/* 보유 ETF 의 고점 대비 — evidence 응답에 직접 필드 없음. 사용자 친화 표기. */}
                        <td style={{ textAlign: "right", color: "var(--muted)" }}>
                          {evidenceLoaded ? STATE_NEED_CHECK : STATE_UNCHECKED}
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

          {/* 후보 ETF 표 (AC-3, AC-4) */}
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
                      <td>
                        <strong>{c.name ?? c.ticker}</strong>{" "}
                        <code style={{ color: "var(--muted)", fontSize: "0.85em" }}>
                          {c.ticker}
                        </code>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {c.relative_upside_score != null
                          ? c.relative_upside_score.toFixed(1)
                          : DASH}
                      </td>
                      <td style={{ textAlign: "right", color: returnColor(ex20) }}>
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
                              fontWeight:
                                exposure.kind === "direct_only" ||
                                exposure.kind === "direct_and_overlap"
                                  ? "bold"
                                  : "normal",
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

        {/* 우측 30% — 선택 상세 (AC-5, AC-6) */}
        <div
          className="card"
          style={{ padding: 12, height: "fit-content", position: "sticky", top: 12 }}
        >
          <h3 style={{ margin: 0, marginBottom: 8 }}>선택 후보 상세</h3>
          {selectedCandidate && selectedExposure ? (
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
        보유 노출은 직접 보유 여부 (ticker 일치) 와 구성종목 겹침 (보유 ETF 의
        구성종목이 시장 반복 핵심 종목과 겹치는지) 을 합쳐 한 칸에 표시합니다.
        데이터가 없는 값은 임의 채우지 않고 &quot;데이터 없음&quot; / &quot;확인
        필요&quot; / &quot;중복 확인 전&quot; / &quot;중복 확인 불가&quot; 로
        표시합니다.
      </p>
    </section>
  );
}

// 상태 문구 → 색상.
function exposureColorByState(state: string): string {
  if (state === STATE_NORMAL) return "var(--ok)";
  if (state === STATE_UNAVAIL) return "var(--danger)";
  if (state === STATE_UNCHECKED) return "var(--muted)";
  return "var(--muted)";
}

// ─── 선택 상세 ───────────────────────────────────────────────────────

interface SelectedDetailProps {
  candidate: MarketCandidate;
  exposure: ExposureSummary;
  expanded: boolean;
  onToggleExpanded: () => void;
  directHoldingEvidence: HoldingsMarketEvidenceItem | undefined;
}

function SelectedDetail({
  candidate,
  exposure,
  expanded,
  onToggleExpanded,
  directHoldingEvidence,
}: SelectedDetailProps) {
  const sm = candidate.short_term_momentum;
  const dd =
    candidate.drawdown_20d != null ? candidate.drawdown_20d * 100 : null;
  return (
    <div style={{ display: "grid", gap: 10, fontSize: "0.85em" }}>
      <div>
        <strong>{candidate.name ?? candidate.ticker ?? "후보"}</strong>{" "}
        <code style={{ color: "var(--muted)" }}>{candidate.ticker}</code>
      </div>

      {/* 1. 보유 노출 요약 (AC-5) */}
      <section
        style={{
          padding: 8,
          border: "1px solid var(--border)",
          borderRadius: 6,
          backgroundColor: "var(--bg-subtle, #f9fafb)",
        }}
      >
        <div style={{ fontWeight: "bold", marginBottom: 4 }}>보유 노출 요약</div>
        <div>
          <span style={{ color: "var(--muted)" }}>직접 보유: </span>
          <span
            style={{
              color:
                exposure.kind === "direct_only" ||
                exposure.kind === "direct_and_overlap"
                  ? "var(--warn)"
                  : undefined,
              fontWeight:
                exposure.kind === "direct_only" ||
                exposure.kind === "direct_and_overlap"
                  ? "bold"
                  : "normal",
            }}
          >
            {exposure.directHoldingTicker
              ? `${exposure.directHoldingName ?? exposure.directHoldingTicker}`
              : "없음"}
          </span>
        </div>
        <div>
          <span style={{ color: "var(--muted)" }}>구성종목 겹침: </span>
          <span>
            {exposure.kind === "unchecked"
              ? STATE_UNCHECKED
              : exposure.kind === "unavailable"
                ? STATE_UNAVAIL
                : `보유 ETF ${exposure.overlapHoldingCount}개`}
          </span>
        </div>
        {exposure.topOverlapHoldingName ? (
          <div>
            <span style={{ color: "var(--muted)" }}>가장 큰 겹침: </span>
            <span>
              {exposure.topOverlapHoldingName}
              {exposure.topOverlapWeightPct != null
                ? ` (${exposure.topOverlapWeightPct.toFixed(1)}%)`
                : ""}
            </span>
          </div>
        ) : null}
      </section>

      {/* 2. 후보 흐름 */}
      <section>
        <div style={{ fontWeight: "bold", marginBottom: 4 }}>후보 흐름</div>
        <div>
          <span style={{ color: "var(--muted)" }}>참고점수: </span>
          <strong>
            {candidate.relative_upside_score != null
              ? candidate.relative_upside_score.toFixed(1)
              : STATE_NO_DATA}
          </strong>
        </div>
        {candidate.relative_upside_reasons &&
        candidate.relative_upside_reasons.length > 0 ? (
          <ul style={{ margin: "4px 0 0 0", paddingLeft: "1.2em" }}>
            {candidate.relative_upside_reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        ) : null}
        <div style={{ marginTop: 6 }}>
          <span style={{ color: "var(--muted)" }}>최근 수익률: </span>
        </div>
        <div>5d: {fmtPct(sm?.return_5d_pct ?? null)}</div>
        <div>10d: {fmtPct(sm?.return_10d_pct ?? null)}</div>
        <div>20d: {fmtPct(sm?.return_20d_pct ?? null)}</div>
        <div style={{ marginTop: 4 }}>
          <span style={{ color: "var(--muted)" }}>KODEX 대비 초과수익: </span>
        </div>
        <div>5d: {fmtPct(sm?.excess_vs_kodex200_5d_pctp ?? null)}</div>
        <div>10d: {fmtPct(sm?.excess_vs_kodex200_10d_pctp ?? null)}</div>
        <div>20d: {fmtPct(sm?.excess_vs_kodex200_20d_pctp ?? null)}</div>
        <div style={{ marginTop: 4 }}>
          <span style={{ color: "var(--muted)" }}>고점 대비: </span>
          <span style={{ color: returnColor(dd) }}>{fmtPct(dd)}</span>
        </div>
        <div>
          <span style={{ color: "var(--muted)" }}>데이터 품질: </span>
          <span>{candidateDataState(candidate)}</span>
        </div>
      </section>

      {/* 3. 세부 근거 (AC-6 — 기본 접힘) */}
      <section>
        <button
          type="button"
          onClick={onToggleExpanded}
          style={{
            padding: "4px 8px",
            border: "1px solid var(--border)",
            borderRadius: 4,
            backgroundColor: "transparent",
            cursor: "pointer",
            fontSize: "0.85em",
            width: "100%",
            textAlign: "left",
          }}
        >
          {expanded ? "▼ 세부 근거 접기" : "▶ 세부 근거 펼치기"}
        </button>
        {expanded ? (
          <div style={{ marginTop: 8 }}>
            {directHoldingEvidence?.constituents_overlap?.status === "ok" &&
            (directHoldingEvidence.constituents_overlap.overlap_with_market_core
              ?.length ?? 0) > 0 ? (
              <div>
                <div style={{ color: "var(--muted)" }}>
                  직접 보유 ETF 의 구성종목 ↔ 시장 반복 핵심 종목:
                </div>
                <ul style={{ margin: "4px 0 0 0", paddingLeft: "1.2em" }}>
                  {directHoldingEvidence.constituents_overlap.overlap_with_market_core
                    .slice(0, 10)
                    .map((it, i) => (
                      <li key={i}>
                        {it.name ?? it.ticker}
                        {it.weight_pct != null
                          ? ` (${it.weight_pct.toFixed(1)}%)`
                          : ""}
                        {it.market_core_count != null
                          ? ` · 시장 반복 ${it.market_core_count}개`
                          : ""}
                      </li>
                    ))}
                </ul>
              </div>
            ) : exposure.kind === "overlap_only" ? (
              <div style={{ color: "var(--muted)" }}>
                본 후보가 보유 ETF {exposure.overlapHoldingCount}개의 구성종목
                겹침에 포함됩니다. 상세 overlap 수치는 보유 ETF 별 evidence
                응답에서 확인하세요.
              </div>
            ) : (
              <div style={{ color: "var(--muted)" }}>
                추가 세부 근거가 없습니다.
              </div>
            )}
          </div>
        ) : null}
      </section>
    </div>
  );
}
