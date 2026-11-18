import type { CompareCondition } from "@/lib/api/etfCompare";

// POC6-29 — 「보유」 행의 [보유와 후보 비교에서 보기 →]가 고른 보유 종목을 「보유와 후보 비교」 화면에 넘긴다
// (같은 탭 · 모듈 메모리 · 한 번 읽으면 비움 · 저장 없음).
let pendingHolding: string | null = null;

export function presetCompareHolding(ticker: string): void {
  pendingHolding = ticker;
}

export function takePresetHolding(): string | null {
  const t = pendingHolding;
  pendingHolding = null;
  return t;
}

// POC6-31(판정 Q10 · PLAN C18 · C23) — 「ETF 구성종목」에서 고른 후보 한 건과 그 목록의 조건을 이 화면에 넘긴다
// (같은 탭 · 모듈 메모리 · 한 번 읽으면 비움 · 저장 없음). 조건은 이번 이동에만 쓰고(etfCompareCondition 의
// '이동 한 번' 조건) 화면 조건 · 저장된 기본값은 바꾸지 않는다. 넘긴 목록의 시작일 · 끝일은 받는 화면이 자기 목록과 대조한다.
export interface PresetCandidate {
  ticker: string;
  name: string | null;
  side: "top" | "bottom";
  condition: CompareCondition | null; // null = 넘긴 목록 조건 없음(예전 draft)
  start?: string | null; // 넘긴 목록의 공통 기간 시작일
  end?: string | null; // 넘긴 목록의 끝일
  origin?: string; // 보낸 화면 이름(POC6-32 · 없으면 「ETF 구성종목」)
}

let pendingCandidate: PresetCandidate | null = null;

export function presetCompareCandidate(p: PresetCandidate): void {
  pendingCandidate = p;
}

export function takePresetCandidate(): PresetCandidate | null {
  const p = pendingCandidate;
  pendingCandidate = null;
  return p;
}
