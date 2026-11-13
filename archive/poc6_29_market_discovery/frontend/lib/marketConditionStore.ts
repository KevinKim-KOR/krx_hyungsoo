// POC6-27 — 「오늘의 투자 점검」과 「요즘 잘 오르는 ETF」의 목록 조건(기간 · 방향 · 제외 4종) 공유
// (설계 §4 · PLAN 판정 §4).
//
// - 같은 브라우저 탭에서 메뉴를 오가는 동안만 공유한다(모듈 메모리 · 저장 없음).
// - 새로 고치면 기존에 저장한 기본 기간(「요즘 잘 오르는 ETF」 [이 기준을 기본으로] · localStorage)과
//   기존 기본 방향(높은 순) · 제외 조건(4종 제외)으로 시작한다.
// - 두 화면은 이 조건으로 같은 GET /market/topn/latest(n=10)를 읽는다. 오늘 화면 키는 조건마다 다르고
//   앞부분은 DASH_KEY_MARKET 과 같다(기본 조건이면 같은 키).
// `@/lib/api` 를 통째로 가짜로 바꾸는 시험과 겹치지 않게 상수는 개별 모듈에서 읽는다.
import { useSyncExternalStore } from "react";
import {
  DEFAULT_MARKET_BASIS,
  DEFAULT_MARKET_ORDER,
  DEFAULT_MARKET_TOPN_FILTERS,
  type MarketBasis,
  type MarketOrder,
  type MarketTopNFilters,
} from "@/lib/api/market";
import { DASH_MARKET_KEY_PREFIX } from "@/lib/api/dashboardKeys";

export interface MarketCondition {
  basis: MarketBasis;
  order: MarketOrder;
  filters: MarketTopNFilters;
}

// 「요즘 잘 오르는 ETF」 기본 기간 저장 칸(marketBasisPreference 와 같은 키 · 같은 허용 값).
const PREF_KEY = "krx.marketDiscovery.defaultBasis.v1";
const BASIS_VALUES: readonly MarketBasis[] = ["daily", "one_month", "three_month"];

function savedBasis(): MarketBasis {
  try {
    const raw = window.localStorage.getItem(PREF_KEY);
    const hit = BASIS_VALUES.find((v) => v === raw);
    return hit ?? DEFAULT_MARKET_BASIS;
  } catch {
    return DEFAULT_MARKET_BASIS;
  }
}

function initial(): MarketCondition {
  return {
    basis: savedBasis(),
    order: DEFAULT_MARKET_ORDER,
    filters: { ...DEFAULT_MARKET_TOPN_FILTERS },
  };
}

const SERVER_DEFAULT: MarketCondition = {
  basis: DEFAULT_MARKET_BASIS,
  order: DEFAULT_MARKET_ORDER,
  filters: { ...DEFAULT_MARKET_TOPN_FILTERS },
};

let current: MarketCondition | null = null;
const subs = new Set<() => void>();

export function getMarketCondition(): MarketCondition {
  if (current === null) current = initial();
  return current;
}

function same(a: MarketCondition, b: MarketCondition): boolean {
  return (
    a.basis === b.basis &&
    a.order === b.order &&
    a.filters.exclude_inverse === b.filters.exclude_inverse &&
    a.filters.exclude_leveraged === b.filters.exclude_leveraged &&
    a.filters.exclude_synthetic === b.filters.exclude_synthetic &&
    a.filters.exclude_futures === b.filters.exclude_futures
  );
}

export function setMarketCondition(next: MarketCondition): void {
  if (same(getMarketCondition(), next)) return;
  current = { basis: next.basis, order: next.order, filters: { ...next.filters } };
  for (const fn of subs) fn();
}

function subscribe(fn: () => void): () => void {
  subs.add(fn);
  return () => {
    subs.delete(fn);
  };
}

export function useMarketCondition(): MarketCondition {
  return useSyncExternalStore(subscribe, getMarketCondition, () => SERVER_DEFAULT);
}

// 오늘 화면의 목록 조회 키 — 기본 조건이면 DASH_KEY_MARKET 과 같은 글자다.
export function todayMarketKey(c: MarketCondition): string {
  return (
    `${DASH_MARKET_KEY_PREFIX}n=10&basis=${c.basis}&order=${c.order}` +
    `&exclude_inverse=${c.filters.exclude_inverse}&exclude_leveraged=${c.filters.exclude_leveraged}` +
    `&exclude_synthetic=${c.filters.exclude_synthetic}&exclude_futures=${c.filters.exclude_futures}`
  );
}

// 테스트용 — 새로 고침과 같은 상태로(다음 읽기 때 저장 기본 기간부터 다시 시작).
export function __resetMarketCondition(): void {
  current = null;
  subs.clear();
}
