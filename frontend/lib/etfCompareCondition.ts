// POC6-28 — 「ETF 비교하기」 조회 기준(기간 · 제외 4종 · 판정 Q4 (b)).
// POC6-29(PLAN 판정 2026-11-12 Q1 · Q2 · Q13) — 화면마다 조건과 저장된 기본 기간을 따로 쓴다.
//
// - 화면 = 「오늘의 투자 점검」 잘 오르는 ETF(today) · 보유(holdings) · 섹터요약(sector) · 후보리스트(candidates) ·
//   보유와 후보 비교(compare). 같은 탭 안에서 화면 조건은 모듈 메모리에만 있고, 다른 화면 조건을 바꾸지 않는다.
// - 기본 기간만 이 브라우저에 화면별로 저장한다([이 기준을 기본으로] 를 누를 때만 · localStorage).
//   저장값이 없으면 1개월로 시작한다. 제외 조건은 저장하지 않는다(새로 고치면 4종 제외).
// - today 는 제외 4종 고정(판정 Q2). 새 저장값이 비어 있으면 예전 「요즘 잘 오르는 ETF」 저장 기본 기간을
//   한 번 이어받아 today 의 저장값으로 옮긴다(판정 Q13 · 다른 화면은 이어받지 않음).
// - 저장소를 읽거나 쓰지 못하면 지금 조회를 그대로 두고 실패를 알린다(화면은 정상 동작 · PLAN §3-1).
//   저장값 상태는 예전 「요즘 잘 오르는 ETF」 판정 그대로 넷으로 나눈다(검증자 r1 F2): 저장됨 · 없음 ·
//   허용 밖 값 · 읽기 실패. 쓰기는 setItem 뒤 다시 읽어 같을 때만 성공. 다른 탭에서 저장하면 저장 표시만
//   다시 읽는다(지금 조회는 그대로).
import { useSyncExternalStore } from "react";
import type { CompareBasis, CompareCondition } from "@/lib/api/etfCompare";

export type ScreenId = "today" | "holdings" | "sector" | "candidates" | "compare";

export const SCREEN_IDS: readonly ScreenId[] = ["today", "holdings", "sector", "candidates", "compare"];

export const ETF_COMPARE_DEFAULT: CompareCondition = {
  basis: "one_month",
  filters: {
    exclude_inverse: true,
    exclude_leveraged: true,
    exclude_synthetic: true,
    exclude_futures: true,
  },
};

const BASIS_VALUES: readonly CompareBasis[] = ["daily", "one_month", "three_month"];
const KEY_PREFIX = "krx.screenBasis.";
// 예전 「요즘 잘 오르는 ETF」 [이 기준을 기본으로] 칸(today 만 한 번 이어받음).
export const LEGACY_TODAY_BASIS_KEY = "krx.marketDiscovery.defaultBasis.v1";

export function storageKeyOf(id: ScreenId): string {
  return `${KEY_PREFIX}${id}.v1`;
}

function copy(c: CompareCondition): CompareCondition {
  return { basis: c.basis, filters: { ...c.filters } };
}

function asBasis(raw: string | null): CompareBasis | null {
  return BASIS_VALUES.find((v) => v === raw) ?? null;
}

export type SavedBasisStatus = "saved" | "none" | "invalid" | "read_failed";

// basis 는 status = saved 일 때만 값(없음 · 허용 밖 · 읽기 실패 = null → 1개월로 시작).
export interface SavedBasisRead {
  basis: CompareBasis | null;
  status: SavedBasisStatus;
}

const READ_FAILED: SavedBasisRead = { basis: null, status: "read_failed" };

function classify(raw: string | null): SavedBasisRead {
  if (raw === null) return { basis: null, status: "none" };
  const basis = asBasis(raw);
  return basis ? { basis, status: "saved" } : { basis: null, status: "invalid" };
}

// 화면의 저장된 기본 기간. today 는 자기 칸이 비어 있을 때만 예전 값(허용 값일 때만)을 한 번 옮긴다 —
// 옮겨 적기만 실패하면 읽은 예전 값은 그대로 쓰고 다음 읽기 때 다시 옮긴다.
export function readSavedBasis(id: ScreenId): SavedBasisRead {
  let legacy: CompareBasis | null;
  try {
    const own = classify(window.localStorage.getItem(storageKeyOf(id)));
    if (own.status !== "none" || id !== "today") return own;
    legacy = asBasis(window.localStorage.getItem(LEGACY_TODAY_BASIS_KEY));
  } catch {
    return READ_FAILED;
  }
  if (!legacy) return { basis: null, status: "none" };
  try {
    window.localStorage.setItem(storageKeyOf(id), legacy);
  } catch {
    // 옮겨 적기만 실패 — 아래 값은 읽은 그대로다.
  }
  return { basis: legacy, status: "saved" };
}

const current = new Map<ScreenId, CompareCondition>();
const saved = new Map<ScreenId, SavedBasisRead>();
// 화면 조건을 처음 만들 때의 저장값 상태 — 시작 기간이 어디서 왔는지(안내 문구용 · 검증자 r2 F3).
// 다른 탭 저장 뒤 다시 읽어도 바뀌지 않는다(지금 조회 조건도 그대로이므로).
const started = new Map<ScreenId, SavedBasisStatus>();
const subs = new Set<() => void>();

function savedOf(id: ScreenId): SavedBasisRead {
  let r = saved.get(id);
  if (!r) {
    r = readSavedBasis(id);
    saved.set(id, r);
  }
  return r;
}

export function getScreenCondition(id: ScreenId): CompareCondition {
  let c = current.get(id);
  if (!c) {
    const r = savedOf(id);
    c = { basis: r.basis ?? ETF_COMPARE_DEFAULT.basis, filters: { ...ETF_COMPARE_DEFAULT.filters } };
    current.set(id, c);
    started.set(id, r.status);
  }
  return c;
}

export function getStartStatus(id: ScreenId): SavedBasisStatus {
  getScreenCondition(id);
  return started.get(id) ?? "none";
}

export function getSavedBasis(id: ScreenId): CompareBasis | null {
  return savedOf(id).basis;
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

function emit() {
  for (const fn of subs) fn();
}

export function setScreenCondition(id: ScreenId, next: CompareCondition): void {
  // today 는 제외 4종 고정(판정 Q2) — 기간만 바뀐다.
  const fixed = id === "today" ? { basis: next.basis, filters: { ...ETF_COMPARE_DEFAULT.filters } } : next;
  if (sameCondition(getScreenCondition(id), fixed)) return;
  current.set(id, copy(fixed));
  emit();
}

// [이 기준을 기본으로] — 지금 기간을 이 화면의 기본으로 저장. 다시 읽어 같은 값일 때만 성공(true).
export function saveScreenBasis(id: ScreenId): boolean {
  const basis = getScreenCondition(id).basis;
  try {
    window.localStorage.setItem(storageKeyOf(id), basis);
    if (window.localStorage.getItem(storageKeyOf(id)) !== basis) return false;
  } catch {
    return false;
  }
  saved.set(id, { basis, status: "saved" });
  emit();
  return true;
}

// 같은 브라우저 다른 탭의 저장 · 지우기 → 저장 표시만 다시 읽는다(지금 조회 조건은 그대로).
function onStorage(e: StorageEvent) {
  if (e.key !== null && !e.key.startsWith(KEY_PREFIX) && e.key !== LEGACY_TODAY_BASIS_KEY) return;
  saved.clear();
  emit();
}

function subscribe(fn: () => void): () => void {
  if (subs.size === 0) window.addEventListener("storage", onStorage);
  subs.add(fn);
  return () => {
    subs.delete(fn);
    if (subs.size === 0) window.removeEventListener("storage", onStorage);
  };
}

const SERVER_DEFAULT = copy(ETF_COMPARE_DEFAULT);

export function useScreenCondition(id: ScreenId): CompareCondition {
  return useSyncExternalStore(
    subscribe,
    () => getScreenCondition(id),
    () => SERVER_DEFAULT,
  );
}

const SERVER_SAVED: SavedBasisRead = { basis: null, status: "none" };

export function useSavedBasisRead(id: ScreenId): SavedBasisRead {
  return useSyncExternalStore(
    subscribe,
    () => savedOf(id),
    () => SERVER_SAVED,
  );
}

// 테스트용 — 새로 고침과 같은 상태로(다음 읽기 때 저장값부터 다시).
export function __resetEtfCompareCondition(): void {
  current.clear();
  saved.clear();
  started.clear();
  subs.clear();
  window.removeEventListener("storage", onStorage);
}
