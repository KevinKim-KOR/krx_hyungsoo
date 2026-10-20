// POC6-01 — 시장 흐름 카드에서 고른 기간(이 탭 메모리 · 저장하지 않음 · 기본 6개월).
// 카드 · AI 복사문 · 판단 근거 미리보기 요청이 같은 기간을 쓰게 한다(props 를 화면 여러 겹으로 내리지 않음).
import { useSyncExternalStore } from "react";

import { DEFAULT_FLOW_PERIOD, type FlowPeriodCode } from "./api/marketFlow";

let current: FlowPeriodCode = DEFAULT_FLOW_PERIOD;
const subscribers = new Set<() => void>();

export function getMarketFlowPeriod(): FlowPeriodCode {
  return current;
}

export function setMarketFlowPeriod(next: FlowPeriodCode): void {
  if (next === current) return;
  current = next;
  for (const fn of subscribers) fn();
}

function subscribe(fn: () => void): () => void {
  subscribers.add(fn);
  return () => {
    subscribers.delete(fn);
  };
}

export function useMarketFlowPeriod(): FlowPeriodCode {
  return useSyncExternalStore(subscribe, getMarketFlowPeriod, getMarketFlowPeriod);
}

// 시험 전용 — 기본값으로 되돌린다.
export function __resetMarketFlowPeriod(): void {
  current = DEFAULT_FLOW_PERIOD;
  for (const fn of subscribers) fn();
}
