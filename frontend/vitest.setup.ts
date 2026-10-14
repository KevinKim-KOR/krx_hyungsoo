// jest-dom matchers (toBeInTheDocument 등) 등록.
import "@testing-library/jest-dom/vitest";

// POC5-12 — 시장 TOP N 진행 중 공유는 모듈 상태라 테스트 사이에 남지 않게 매번 비운다.
import { beforeEach } from "vitest";
import { __resetMarketTopnInflight } from "@/lib/api/market";

beforeEach(() => {
  __resetMarketTopnInflight();
});
