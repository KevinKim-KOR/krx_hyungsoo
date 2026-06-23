"use client";

// POC2 — 보유·후보 비교 v1 CLOSEOUT 선택 상세 영역 (FIX r1 — B-3 분리).
//
// 순서 고정 (지시문 §3):
//   1. 보유 노출 요약 (직접 보유 / 겹침 보유 ETF 수 / 가장 큰 겹침 대상)
//   2. 후보 흐름 (참고점수 + 근거 + 5/10/20일 + KODEX 초과 + 고점 대비 + 품질)
//   3. 세부 근거 (구성종목 목록 + overlap 수치) — 기본 접힘

import type {
  HoldingsMarketEvidenceItem,
  MarketCandidate,
} from "@/lib/api";
import {
  type ExposureSummary,
  STATE_NO_DATA,
  STATE_UNAVAIL,
  STATE_UNCHECKED,
  candidateDataState,
  fmtPct,
  returnColor,
} from "./helpers";

interface Props {
  candidate: MarketCandidate;
  exposure: ExposureSummary;
  expanded: boolean;
  onToggleExpanded: () => void;
  directHoldingEvidence: HoldingsMarketEvidenceItem | undefined;
}

export default function SelectedDetail({
  candidate,
  exposure,
  expanded,
  onToggleExpanded,
  directHoldingEvidence,
}: Props) {
  const sm = candidate.short_term_momentum;
  const dd =
    candidate.drawdown_20d != null ? candidate.drawdown_20d * 100 : null;
  const isDirectKind =
    exposure.kind === "direct_only" ||
    exposure.kind === "direct_and_overlap";
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
              color: isDirectKind ? "var(--warn)" : undefined,
              fontWeight: isDirectKind ? "bold" : "normal",
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
