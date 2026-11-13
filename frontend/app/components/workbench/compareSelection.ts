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
