// jest-dom matchers (toBeInTheDocument 등) 등록.
import "@testing-library/jest-dom/vitest";

// POC5-12 — 시장 TOP N 진행 중 공유는 모듈 상태라 테스트 사이에 남지 않게 매번 비운다.
import { beforeEach } from "vitest";
import { __resetMarketTopnInflight } from "@/lib/api/market";
// POC6-27 — 탭 공유 목록 조건 · 이 탭에서 시작한 시장 갱신 id 도 모듈 상태라 시험마다 비운다(새로 고침과 같음).
import { __resetMarketCondition } from "@/lib/marketConditionStore";
import { __resetMarketRefreshMemory } from "@/lib/marketRefreshMemory";

beforeEach(() => {
  __resetMarketTopnInflight();
  __resetMarketCondition();
  __resetMarketRefreshMemory();
});
