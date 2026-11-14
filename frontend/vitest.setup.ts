// jest-dom matchers (toBeInTheDocument 등) 등록.
import "@testing-library/jest-dom/vitest";

// POC5-12 — 시장 TOP N 진행 중 공유는 모듈 상태라 테스트 사이에 남지 않게 매번 비운다.
import { beforeEach } from "vitest";
import { __resetMarketTopnInflight } from "@/lib/api/market";
// POC6-27 — 이 탭에서 시작한 시장 갱신 id 도 모듈 상태라 시험마다 비운다(새로 고침과 같음).
import { __resetMarketRefreshMemory } from "@/lib/marketRefreshMemory";
// POC6-29 — 화면별 조회 조건(모듈 메모리)과 화면별 저장 기본 기간(localStorage)도 시험마다 비운다(새로 고침 · 저장 없음).
import { LEGACY_TODAY_BASIS_KEY, SCREEN_IDS, __resetEtfCompareCondition, storageKeyOf } from "@/lib/etfCompareCondition";

// 2026-11-14 — 화면 전환 때 맨 위로 올리는 MainPanel 의 window.scrollTo 를 jsdom 은 구현하지 않아(Not implemented 오류 글)
// 메뉴를 옮기는 시험마다 오류 글이 남는다. 아무 일도 안 하는 대역으로 둔다(맨 위 이동 자체는 MainPanel.test 가 spy 로 확인).
window.scrollTo = (() => {}) as typeof window.scrollTo;

beforeEach(() => {
  __resetMarketTopnInflight();
  __resetMarketRefreshMemory();
  try {
    for (const id of SCREEN_IDS) window.localStorage.removeItem(storageKeyOf(id));
    window.localStorage.removeItem(LEGACY_TODAY_BASIS_KEY);
  } catch {
    // 저장소가 없는 환경이면 비울 것도 없다.
  }
  __resetEtfCompareCondition();
});
