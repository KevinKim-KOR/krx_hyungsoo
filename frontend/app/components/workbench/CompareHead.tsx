"use client";

// POC6-28 — 「ETF 비교하기」 「후보」 · 「보유」 공통: 요약 조회 · 기준 줄 · 가격 시점 줄 · 시장 판정 줄 · 조회 기준 패널.
// PLAN §2-2 · §2-7 · §3-7 · §5 · 판정 Q3 · Q4 (b) · Q5.
// POC6-29(PLAN 판정 Q1 · Q2 · Q11) — 화면마다 자기 조건으로 읽고([조회 기준] = 그 화면에만 적용), 기본 기간을 화면별로 저장한다.

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
  getSavedBasis,
  getStartStatus,
  saveScreenBasis,
  setScreenCondition,
  useSavedBasisRead,
  useScreenCondition,
  type SavedBasisStatus,
  type ScreenId,
} from "@/lib/etfCompareCondition";
import { BASIS_LABEL, basisLine, filtersText, priceStateLine, regimeView } from "@/lib/etfCompare";

export function useEtfCompareSummary(screen: ScreenId) {
  const cond = useScreenCondition(screen);
  const q = useSharedQuery<CompareSummary>(etfCompareKey(cond), () => fetchEtfCompareSummary(cond));
  return { cond, q };
}

// 화면 이름(조회 기준 패널 · 저장 줄 글자).
export const SCREEN_LABEL: Record<ScreenId, string> = {
  today: "「오늘의 투자 점검」 잘 오르는 ETF",
  holdings: "「보유」",
  sector: "「섹터요약」",
  candidates: "「후보리스트」",
  compare: "「보유와 후보 비교」",
};

// 저장값을 확인하지 못한 경우의 안내(예전 「요즘 잘 오르는 ETF」 문구 · PLAN §3-1 · 검증자 r1 F2 · r2 F3).
const BASIS_READ_NOTICE: Partial<Record<SavedBasisStatus, { start: string; now: string }>> = {
  read_failed: { start: "저장된 기본을 읽지 못해 1개월로 시작했습니다", now: "저장된 기본을 읽지 못했습니다" },
  invalid: { start: "저장된 기본 값을 쓸 수 없어 1개월로 시작했습니다", now: "저장된 기본 값을 쓸 수 없습니다" },
};

// '…해 1개월로 시작했습니다'는 이 화면이 바로 그 이유로 1개월로 시작했고 지금도 1개월일 때만 쓴다.
// 그 밖(다른 탭 저장 뒤 다시 읽기 · 기간을 바꾼 뒤)은 지금 조회 기간을 그대로 적는다.
export function basisReadNotice(
  status: SavedBasisStatus,
  started: SavedBasisStatus,
  basis: CompareBasis,
): string | null {
  const t = BASIS_READ_NOTICE[status];
  if (!t) return null;
  return started === status && basis === ETF_COMPARE_DEFAULT.basis
    ? t.start
    : `${t.now} — 지금 조회(${BASIS_LABEL[basis]})는 그대로입니다`;
}

// [이 기준을 기본으로] 줄(판정 Q1) — 지금 기간을 이 화면의 기본으로 저장. 새로 고치면 저장한 기간으로 시작.
export function BasisSaveRow({ screen, basis }: { screen: ScreenId; basis: CompareBasis }) {
  const { basis: saved, status } = useSavedBasisRead(screen);
  // 저장에 실패한 기간 — 그 뒤 이 기간이 저장된 것으로 다시 읽히면(다른 탭) 실패 안내를 내린다.
  const [failedBasis, setFailedBasis] = useState<CompareBasis | null>(null);
  const notice = basisReadNotice(status, getStartStatus(screen), basis);
  const same = saved === basis;
  // 실패한 기간을 문구에 적는다 — 그 뒤 기간을 바꿔도 어느 저장이 실패했는지 맞게 읽힌다.
  const failed = failedBasis !== null && saved !== failedBasis;
  return (
    <div className="ec-small ec-save-row" data-testid={`ec-save-${screen}`}>
      기본 기간:{" "}
      {notice ? (
        <span className="wb-warn" data-testid={`ec-save-notice-${screen}`}>
          {notice}
        </span>
      ) : (
        <>
          <b>{saved ? BASIS_LABEL[saved] : BASIS_LABEL[ETF_COMPARE_DEFAULT.basis]}</b>
          {saved ? " (이 화면에 저장됨)" : " (저장 없음 · 새로 고치면 1개월로 시작)"}
        </>
      )}{" "}
      ·{" "}
      <button
        type="button"
        className="ec-more"
        disabled={same}
        onClick={() => setFailedBasis(saveScreenBasis(screen) ? null : basis)}
      >
        {same ? "이미 기본" : `이 기준을 기본으로(${BASIS_LABEL[basis]})`}
      </button>
      {failed && failedBasis && (
        <span className="wb-warn"> 기본값({BASIS_LABEL[failedBasis]}) 저장을 확인하지 못했습니다 — 지금 조회는 그대로입니다</span>
      )}
    </div>
  );
}

export function okSummary(q: QueryState<CompareSummary>): CompareSummaryOk | null {
  return q.phase === "success" && q.data.status === "ok" ? q.data : null;
}

const NOT_OK_TEXT: Record<string, string> = {
  missing: "시장 DB 가 없습니다. 「오늘의 투자 점검」 [최신 자료 갱신]을 먼저 실행하세요.",
  empty: "저장된 가격이 없습니다. 「오늘의 투자 점검」 [최신 자료 갱신]을 먼저 실행하세요.",
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

// 「조회 기준」 — 이 화면에만 적용(POC6-29 판정 Q1 · Q2 · Q11) · 새로 고치면 이 화면의 저장 기본 기간 · 4종 제외.
export function ConditionPanel({
  screen,
  cond,
  onClose,
  applies,
}: {
  screen: ScreenId;
  cond: CompareCondition;
  onClose: () => void;
  applies: string;
}) {
  const [draft, setDraft] = useState<CompareCondition>(cond);
  const setBasis = (b: CompareBasis) => setDraft({ ...draft, basis: b });
  const toggle = (k: keyof CompareFilters) =>
    setDraft({ ...draft, filters: { ...draft.filters, [k]: !draft.filters[k] } });
  return (
    <div className="ec-panel" role="dialog" aria-label="조회 기준" data-testid="ec-condition-panel">
      <div className="ec-panel-title">{SCREEN_LABEL[screen]} 조회 기준</div>
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
        표시 수 = 상·하위 각 최대 30개(고정) · 정렬 방향은 여기서 고르지 않습니다(목록의 정렬 줄).
      </div>
      <div className="ec-small">
        적용되는 곳: {applies} — 이 화면에만 적용합니다. 다른 화면의 조건은 바뀌지 않고, 새로 고치면 이 화면의 기본
        기간 · 4종 제외로 시작합니다.
      </div>
      <div className="ec-btn-row">
        <button
          type="button"
          className="wb-btn btn-md ec-primary"
          onClick={() => {
            setScreenCondition(screen, draft);
            onClose();
          }}
        >
          적용
        </button>
        {/* '기본' = 이 화면에 저장한 기본 기간(없으면 1개월) · 4종 제외(검토 지적 — 저장값과 같은 뜻) */}
        <button
          type="button"
          className="wb-btn btn-md"
          onClick={() =>
            setDraft({ basis: getSavedBasis(screen) ?? ETF_COMPARE_DEFAULT.basis, filters: { ...ETF_COMPARE_DEFAULT.filters } })
          }
        >
          기본값으로
        </button>
        <button type="button" className="wb-btn btn-md" onClick={onClose}>
          닫기
        </button>
      </div>
    </div>
  );
}
