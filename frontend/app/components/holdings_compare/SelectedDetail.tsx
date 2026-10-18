"use client";

// POC2 — 보유·후보 비교 v1 CLOSEOUT 선택 상세 영역 (FIX r1 — B-3 분리).
//
// 순서 고정 (지시문 §3):
//   1. 보유 노출 요약 (직접 보유 / 구성종목 중복 = 미리보기에서 비교 — POC5-23 판정 §3)
//   2. 후보 흐름 (5/10/20일 + KODEX 초과 + 품질)
//      2026-08-29 POC3-ML-02 REJECT Closeout — `relative_upside_v0` REJECT 판정으로
//      참고점수와 점수 근거를 뺐다.
//      POC5-23 판정 §3 — '고점 대비'는 폐기된 참고점수 스냅샷 값이고 종목별 날짜를 화면이 받지
//      못해 뺐다(현재값처럼 보이지 않게). 보유 노출은 직접 보유만 확정 · 구성종목 중복은 미리보기에서.
//   3. 세부 근거 (구성종목 목록 + overlap 수치) — 기본 접힘

import type {
  HoldingsMarketEvidenceItem,
  MarketCandidate,
} from "@/lib/api";
import {
  type ExposureSummary,
  STATE_OVERLAP_UNCHECKED,
  candidateDataState,
  exposureLabel,
  fmtPct,
  fmtPctp,
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
  const isDirectKind = exposure.kind === "direct";
  const holdingsKnown = exposure.kind === "direct" || exposure.kind === "overlap_unchecked";
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
            {!holdingsKnown
              ? exposureLabel(exposure)
              : exposure.directHoldingTicker
                ? `${exposure.directHoldingName ?? exposure.directHoldingTicker}`
                : "없음"}
          </span>
        </div>
        <div>
          <span style={{ color: "var(--muted)" }}>구성종목 중복: </span>
          <span>
            {STATE_OVERLAP_UNCHECKED} — 아래 [판단 근거 미리보기]에서 보유 ETF 와 저장
            구성종목으로 비교합니다.
          </span>
        </div>
      </section>

      {/* 2. 후보 흐름 */}
      <section>
        <div style={{ fontWeight: "bold", marginBottom: 4 }}>후보 흐름</div>
        <div style={{ marginTop: 6 }}>
          <span style={{ color: "var(--muted)" }}>최근 수익률: </span>
        </div>
        <div>5d: {fmtPct(sm?.return_5d_pct ?? null)}</div>
        <div>10d: {fmtPct(sm?.return_10d_pct ?? null)}</div>
        <div>20d: {fmtPct(sm?.return_20d_pct ?? null)}</div>
        <div style={{ marginTop: 4 }}>
          <span style={{ color: "var(--muted)" }}>KODEX 대비 초과수익: </span>
        </div>
        <div>5d: {fmtPctp(sm?.excess_vs_kodex200_5d_pctp ?? null)}</div>
        <div>10d: {fmtPctp(sm?.excess_vs_kodex200_10d_pctp ?? null)}</div>
        <div>20d: {fmtPctp(sm?.excess_vs_kodex200_20d_pctp ?? null)}</div>
        <div>
          <span style={{ color: "var(--muted)" }}>데이터 품질: </span>
          <span>{candidateDataState(candidate)}</span>
        </div>
      </section>

      {/* 3. 세부 근거 (AC-6 — 기본 접힘) */}
      <section>
        <button
          type="button"
          className="btn-md"
          onClick={onToggleExpanded}
          style={{
            border: "1px solid var(--border)",
            borderRadius: 4,
            backgroundColor: "transparent",
            // POC5-23 판정 §3 — 기본 버튼 글자색(흰색) 위에 배경만 투명이라 빈 상자로 보였다.
            color: "var(--fg)",
            cursor: "pointer",
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
