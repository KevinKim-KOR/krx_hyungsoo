"use client";

// POC6-28 — 「ETF 비교하기」 「후보」 · 「보유」 공통: 요약 조회 · 기준 줄 · 가격 시점 줄 · 시장 판정 줄 · 조회 기준 패널.
// PLAN §2-2 · §2-7 · §3-7 · §5 · 판정 Q3 · Q4 (b) · Q5.

import { useState } from "react";
import {
  etfCompareKey,
  fetchEtfCompareSummary,
  type CompareBasis,
  type CompareCondition,
  type CompareFilters,
  type CompareSummary,
  type CompareSummaryOk,
} from "@/lib/api/etfCompare";
import { useSharedQuery, type QueryState } from "@/lib/api/queryCache";
import {
  ETF_COMPARE_DEFAULT,
  setEtfCompareCondition,
  useEtfCompareCondition,
} from "@/lib/etfCompareCondition";
import { BASIS_LABEL, basisLine, filtersText, priceStateLine, regimeView } from "@/lib/etfCompare";

export function useEtfCompareSummary() {
  const cond = useEtfCompareCondition();
  const q = useSharedQuery<CompareSummary>(etfCompareKey(cond), () => fetchEtfCompareSummary(cond));
  return { cond, q };
}

export function okSummary(q: QueryState<CompareSummary>): CompareSummaryOk | null {
  return q.phase === "success" && q.data.status === "ok" ? q.data : null;
}

const NOT_OK_TEXT: Record<string, string> = {
  missing: "시장 DB 가 없습니다. [최신 시장 데이터 갱신]을 먼저 실행하세요.",
  empty: "저장된 가격이 없습니다. [최신 시장 데이터 갱신]을 먼저 실행하세요.",
  invalid: "시장 DB 를 읽지 못했습니다.",
  no_common_period: "KODEX 200 저장 가격으로 공통 기간을 정하지 못해 비교 목록을 만들지 않았습니다.",
};

// 요약을 쓸 수 없을 때 한 줄(조회 중 · 실패 · 상태별 사유).
export function SummaryStatus({ q }: { q: QueryState<CompareSummary> }) {
  if (q.phase === "loading" || q.phase === "idle") return <p className="wb-muted">비교 자료 확인 중...</p>;
  if (q.phase === "error") return <p className="wb-danger">비교 자료 조회 실패 — [다시 불러오기]로 다시 시도하세요.</p>;
  if (q.data.status !== "ok") {
    return (
      <p className="wb-warn" data-testid="ec-not-ok">
        {NOT_OK_TEXT[q.data.status] ?? "비교 자료를 만들 수 없습니다."}
      </p>
    );
  }
  return null;
}

export function CompareLines({
  s,
  stale,
  showRegime = true,
}: {
  s: CompareSummaryOk;
  stale: boolean;
  showRegime?: boolean;
}) {
  const rv = regimeView(s.regime, s.end_date, s.both_side_sectors);
  return (
    <>
      <div className="ec-basis" data-testid="ec-basis">
        <div className="ec-basis-main">{basisLine(s)}</div>
        <div className="ec-small" data-testid="ec-price-state">
          {priceStateLine(s.price_state)}
        </div>
        {stale && <div className="wb-hstale">⚠ 이전 조회값 (재조회 실패 — 최신 아님)</div>}
      </div>
      {showRegime && (
        <div className={rv.ok ? "ec-regime" : "ec-regime check"} data-testid="ec-regime">
          {rv.line}
        </div>
      )}
    </>
  );
}

const FILTER_KEYS: [keyof CompareFilters, string][] = [
  ["exclude_inverse", "인버스"],
  ["exclude_leveraged", "레버리지"],
  ["exclude_synthetic", "합성"],
  ["exclude_futures", "선물"],
];

// 「후보 조회 기준」 — 이 화면 안(후보 · 보유)에서만 공유 · 새로 고치면 기본값(판정 Q4 (b)).
export function ConditionPanel({ cond, onClose }: { cond: CompareCondition; onClose: () => void }) {
  const [draft, setDraft] = useState<CompareCondition>(cond);
  const setBasis = (b: CompareBasis) => setDraft({ ...draft, basis: b });
  const toggle = (k: keyof CompareFilters) =>
    setDraft({ ...draft, filters: { ...draft.filters, [k]: !draft.filters[k] } });
  return (
    <div className="ec-panel" role="dialog" aria-label="후보 조회 기준" data-testid="ec-condition-panel">
      <div className="ec-panel-title">후보 조회 기준</div>
      <div className="ec-small">
        지금 적용: {BASIS_LABEL[cond.basis]} · {filtersText(cond.filters)} · 상·하위 각 최대 30개
      </div>
      <div className="ec-panel-row">
        <span className="ec-panel-k">기간</span>
        <span className="holdings-sort-seg" role="group" aria-label="조회 기간">
          {(Object.keys(BASIS_LABEL) as CompareBasis[]).map((b) => (
            <button
              key={b}
              type="button"
              className={draft.basis === b ? "on" : undefined}
              aria-pressed={draft.basis === b}
              onClick={() => setBasis(b)}
            >
              {BASIS_LABEL[b]}
            </button>
          ))}
        </span>
      </div>
      <div className="ec-panel-row">
        <span className="ec-panel-k">제외 조건</span>
        {FILTER_KEYS.map(([k, label]) => (
          <label key={k} className="ec-check">
            <input type="checkbox" checked={draft.filters[k]} onChange={() => toggle(k)} /> {label}
          </label>
        ))}
      </div>
      <div className="ec-small">
        표시 수 = 상·하위 각 최대 30개(고정) · 정렬 방향은 여기서 고르지 않습니다([ETF 순위] 정렬 줄).
      </div>
      <div className="ec-small">
        적용되는 목록: 「후보」 섹터 요약 · ETF 순위 · 「보유」 약세 묶음 접점 — 이 화면 안에서만 함께 쓰고, 새로
        고치면 1개월 · 4종 제외로 시작합니다. 「오늘의 투자 점검」 · 「요즘 잘 오르는 ETF」 조건과는 따로입니다.
      </div>
      <div className="ec-btn-row">
        <button
          type="button"
          className="wb-btn btn-md ec-primary"
          onClick={() => {
            setEtfCompareCondition(draft);
            onClose();
          }}
        >
          적용
        </button>
        <button type="button" className="wb-btn btn-md" onClick={() => setDraft(ETF_COMPARE_DEFAULT)}>
          기본값으로
        </button>
        <button type="button" className="wb-btn btn-md" onClick={onClose}>
          닫기
        </button>
      </div>
    </div>
  );
}
