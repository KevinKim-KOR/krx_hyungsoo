// POC6-27 — 이 탭에서 시작한 [최신 시장 데이터 갱신]의 id(화면을 오가도 남음 · 새로 고치면 사라짐 · 저장 없음).
// 갱신 hook(useMarketRefresh)이 쓰고 읽는다. API 모듈을 가져오지 않는다 — 시험 설정이 이 파일만 불러
// 초기화해도 각 시험의 API 가짜(vi.mock)가 그대로 적용되게.
let startedRefreshId: string | null = null;

export function getStartedRefreshId(): string | null {
  return startedRefreshId;
}

export function setStartedRefreshId(id: string | null): void {
  startedRefreshId = id;
}

export function __resetMarketRefreshMemory(): void {
  startedRefreshId = null;
}
