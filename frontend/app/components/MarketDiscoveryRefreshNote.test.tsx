// POC5-10 — 「요즘 잘 오르는 ETF」 '최신 시장 데이터 갱신'이 끝났지만 확인할 사유(error_summary)가
// 있으면 완료 줄에 '확인 필요: …'를 붙인다(사용자 결정 2026-10-13). 사유가 없으면 예전 문구 그대로.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";

const fetchMarketTopnLatest = vi.fn();
const postMarketRefresh = vi.fn();
const fetchMarketRefreshStatus = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchMarketTopnLatest: (...a: unknown[]) => fetchMarketTopnLatest(...a),
    postMarketRefresh: (...a: unknown[]) => postMarketRefresh(...a),
    fetchMarketRefreshStatus: (...a: unknown[]) => fetchMarketRefreshStatus(...a),
  };
});

import MarketDiscoveryView from "./MarketDiscoveryView";

function topn() {
  return {
    status: "ok",
    asof: "2026-10-12",
    candidates: [],
    daily_topn: [],
    one_month_topn: [],
    three_month_topn: [],
    market_context: null,
  };
}

async function flush() {
  await act(async () => {
    for (let i = 0; i < 5; i++) await Promise.resolve();
  });
}

async function runRefreshTo(errorSummary: string | null) {
  fetchMarketRefreshStatus.mockResolvedValue({
    status: "completed",
    refresh_id: "r1",
    error_summary: errorSummary,
    cooldown_remaining_seconds: 0,
  });
  render(<MarketDiscoveryView onNavigate={() => undefined} />);
  await flush();
  fireEvent.click(screen.getAllByRole("button", { name: "최신 시장 데이터 갱신" })[0]);
  await flush();
  await act(async () => {
    vi.advanceTimersByTime(4100);
  });
  await flush();
}

describe("시장 데이터 갱신 완료 사유 표시 (POC5-10)", () => {
  beforeEach(() => {
    __resetQueryCache();
    vi.useFakeTimers();
    fetchMarketTopnLatest.mockReset();
    postMarketRefresh.mockReset();
    fetchMarketRefreshStatus.mockReset();
    fetchMarketTopnLatest.mockResolvedValue(topn());
    postMarketRefresh.mockResolvedValue({ status: "accepted", refresh_id: "r1", message: "ok" });
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("완료여도 보유 개별주 가격 갱신 실패 사유가 있으면 '확인 필요'로 보인다", async () => {
    await runRefreshTo("보유 개별주 가격 갱신 일부 실패(1종목)");
    expect(document.body.textContent).toContain(
      "갱신 완료. 확인 필요: 보유 개별주 가격 갱신 일부 실패(1종목)",
    );
  });

  it("사유가 없으면 예전 완료 문구 그대로(확인 필요 없음)", async () => {
    await runRefreshTo(null);
    const text = document.body.textContent ?? "";
    expect(text).toContain("갱신 완료.");
    expect(text).not.toContain("확인 필요");
  });
});
