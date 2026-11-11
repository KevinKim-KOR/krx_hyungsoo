// POC6-28 — 「ETF 비교하기」 조회 기준(기간 · 제외 4종 · 판정 Q4 (b)).
//
// - 같은 브라우저 탭에서 「후보」 ↔ 「보유」만 공유한다(모듈 메모리 · 저장 없음).
// - 새로 고치면 이 화면 기본값(1개월 · 4종 제외)으로 시작한다. 「요즘 잘 오르는 ETF」의 저장 기본 기간은 읽지 않는다.
// - 「오늘의 투자 점검」 · 「요즘 잘 오르는 ETF」의 공유 조건(marketConditionStore · POC6-27)과는 따로다.
import { useSyncExternalStore } from "react";
import type { CompareCondition } from "@/lib/api/etfCompare";

export const ETF_COMPARE_DEFAULT: CompareCondition = {
  basis: "one_month",
  filters: {
    exclude_inverse: true,
    exclude_leveraged: true,
    exclude_synthetic: true,
    exclude_futures: true,
  },
};

function copy(c: CompareCondition): CompareCondition {
  return { basis: c.basis, filters: { ...c.filters } };
}

let current: CompareCondition = copy(ETF_COMPARE_DEFAULT);
const subs = new Set<() => void>();

export function getEtfCompareCondition(): CompareCondition {
  return current;
}

export function sameCondition(a: CompareCondition, b: CompareCondition): boolean {
  return (
    a.basis === b.basis &&
    a.filters.exclude_inverse === b.filters.exclude_inverse &&
    a.filters.exclude_leveraged === b.filters.exclude_leveraged &&
    a.filters.exclude_synthetic === b.filters.exclude_synthetic &&
    a.filters.exclude_futures === b.filters.exclude_futures
  );
}

export function setEtfCompareCondition(next: CompareCondition): void {
  if (sameCondition(current, next)) return;
  current = copy(next);
  for (const fn of subs) fn();
}

function subscribe(fn: () => void): () => void {
  subs.add(fn);
  return () => {
    subs.delete(fn);
  };
}

const SERVER_DEFAULT = copy(ETF_COMPARE_DEFAULT);

export function useEtfCompareCondition(): CompareCondition {
  return useSyncExternalStore(subscribe, getEtfCompareCondition, () => SERVER_DEFAULT);
}

// 테스트용 — 새로 고침과 같은 상태로.
export function __resetEtfCompareCondition(): void {
  current = copy(ETF_COMPARE_DEFAULT);
  subs.clear();
}
