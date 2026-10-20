// POC5-23 — 판단 근거 미리보기 카드(설계 V1 §2 · §4 · PLAN 판정 2026-10-18 §4).
// 화면 상자 글 = 응답 글 · [복사] = 응답 글 그대로 · 후보 목록 조건 전달 · 종목 / 조건이 바뀌면 비움 ·
// 늦은 응답 버림 · 서버 사유 문구 표시. 진짜 postDecisionDraftPreview · request 를 쓰고 fetch 만 가짜다.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import DecisionDraftPreviewCard, { splitPreviewSections } from "./DecisionDraftPreviewCard";
import { __resetMarketFlowPeriod, setMarketFlowPeriod } from "@/lib/marketFlowPeriod";

const TEXT = [
  "[대상]\n- 후보 장비 ETF (333333) · 후보 ETF · 현재 목록 2위(3개월 기준)",
  "[시장]\n- 시장 국면: 하락장 · 4거래일째 (KODEX200 2026-10-14 기준)\n- VIX 2026-10-13(미국 날짜)",
  "[AI에게 요청]\n- 위 관측값을 ① 함께 확인되는 사실 ② 가능한 다른 해석 ③ 추가로 확인할 사항으로 나눠 정리해 주세요.",
].join("\n\n");

function okBody(text = TEXT) {
  return {
    status: "ok",
    target_kind: "candidate",
    ticker: "333333",
    preview_text: text,
    generated_at: "2026-10-18T14:05:00+09:00",
    evidence_as_of: {
      target_as_of_date: "2026-10-14",
      kodex200_as_of_date: "2026-10-14",
      vix_as_of_date: "2026-10-13",
    },
  };
}

type Pending = { body: unknown; resolve: (b: unknown) => void };
let pending: Pending[] = [];
const fetchMock = vi.fn((_url: string, init?: { body?: string }) => {
  return new Promise((resolve) => {
    pending.push({
      body: init?.body ? JSON.parse(init.body) : null,
      resolve: (b) => resolve({ ok: true, status: 200, text: async () => JSON.stringify(b) }),
    });
  });
});
const writeText = vi.fn();

beforeEach(() => {
  pending = [];
  fetchMock.mockClear();
  writeText.mockReset();
  vi.stubEnv("NEXT_PUBLIC_API_BASE", "http://api.test");
  vi.stubGlobal("fetch", fetchMock);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

async function generate() {
  fireEvent.click(screen.getByRole("button", { name: /판단 근거 미리보기 생성/ }));
  await waitFor(() => expect(pending.length).toBeGreaterThan(0));
}

async function answer(i: number, body: unknown) {
  await act(async () => {
    pending[i].resolve(body);
  });
}

describe("판단 근거 미리보기 카드", () => {
  it("상자 글을 이으면 응답 글 그대로 · [복사]는 응답 글을 그대로 복사한다", async () => {
    writeText.mockResolvedValue(undefined);
    const { container } = render(
      <DecisionDraftPreviewCard targetKind="candidate" ticker="333333" displayName="후보 장비 ETF" />,
    );
    await generate();
    await answer(0, okBody());
    const secs = Array.from(container.querySelectorAll(".ddp-sec"));
    expect(secs.map((s) => s.querySelector(".ddp-sec-t")?.textContent)).toEqual([
      "대상",
      "시장",
      "AI에게 요청",
    ]);
    const rebuilt = secs
      .map((s) => `[${s.querySelector(".ddp-sec-t")?.textContent}]\n${s.querySelector(".ddp-sec-b")?.textContent}`)
      .join("\n\n");
    expect(rebuilt).toBe(TEXT);
    expect(splitPreviewSections(TEXT)).toHaveLength(3);
    // 날짜 줄 = 생성 시각 · 가격 기준일 · KODEX200 · VIX(미국 날짜).
    expect(screen.getByText(/생성 2026-10-18 14:05 · 가격 기준일 2026-10-14/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "복사" }));
    await waitFor(() => expect(screen.getByText(/복사했습니다/)).toBeInTheDocument());
    expect(writeText).toHaveBeenCalledWith(TEXT);
    expect(screen.getByRole("button", { name: "다시 생성" })).toBeInTheDocument();
  });

  it("복사가 막히면 직접 선택하라는 안내(글은 그대로 남는다)", async () => {
    writeText.mockRejectedValue(new Error("denied"));
    const { container } = render(<DecisionDraftPreviewCard targetKind="holding" ticker="111111" />);
    await generate();
    await answer(0, okBody());
    fireEvent.click(screen.getByRole("button", { name: "복사" }));
    await waitFor(() =>
      expect(screen.getByText("복사하지 못했습니다 — 아래 글을 직접 선택해 복사하세요.")).toBeInTheDocument(),
    );
    expect(container.querySelectorAll(".ddp-sec")).toHaveLength(3);
  });

  it("후보 요청에는 화면 목록 조건 · 보유 요청에는 없음", async () => {
    const q = { n: 10, basis: "three_month", order: "desc", exclude_inverse: true };
    const { unmount } = render(
      <DecisionDraftPreviewCard targetKind="candidate" ticker="0223A0" listQuery={q} />,
    );
    await generate();
    expect(pending[0].body).toEqual({ target_kind: "candidate", ticker: "0223A0", flow_period: "6M", ...q });
    unmount();
    render(<DecisionDraftPreviewCard targetKind="holding" ticker="111111" listQuery={q} />);
    await generate();
    expect(pending[1].body).toEqual({ target_kind: "holding", ticker: "111111", flow_period: "6M" });
  });

  it("POC6-01 — 시장 흐름 카드에서 고른 기간을 요청에 싣는다(기본 6개월)", async () => {
    setMarketFlowPeriod("1M");
    try {
      render(<DecisionDraftPreviewCard targetKind="holding" ticker="111111" />);
      await generate();
      expect(pending[0].body).toEqual({ target_kind: "holding", ticker: "111111", flow_period: "1M" });
    } finally {
      __resetMarketFlowPeriod();
    }
  });

  it("종목이 바뀐 뒤 늦게 온 응답은 버린다", async () => {
    const { container, rerender } = render(
      <DecisionDraftPreviewCard targetKind="candidate" ticker="AAA" />,
    );
    await generate();
    rerender(<DecisionDraftPreviewCard targetKind="candidate" ticker="BBB" />);
    await answer(0, okBody());
    expect(container.querySelectorAll(".ddp-sec")).toHaveLength(0);
    expect(screen.getByRole("button", { name: /판단 근거 미리보기 생성/ })).toBeEnabled();
  });

  it("후보 목록 조건이 바뀌면 이전 미리보기를 비운다(같은 조건 새 객체는 유지)", async () => {
    const q1 = { n: 10, basis: "one_month" };
    const { container, rerender } = render(
      <DecisionDraftPreviewCard targetKind="candidate" ticker="333333" listQuery={q1} />,
    );
    await generate();
    await answer(0, okBody());
    expect(container.querySelectorAll(".ddp-sec")).toHaveLength(3);
    rerender(
      <DecisionDraftPreviewCard targetKind="candidate" ticker="333333" listQuery={{ ...q1 }} />,
    );
    expect(container.querySelectorAll(".ddp-sec")).toHaveLength(3);
    rerender(
      <DecisionDraftPreviewCard
        targetKind="candidate"
        ticker="333333"
        listQuery={{ n: 10, basis: "three_month" }}
      />,
    );
    expect(container.querySelectorAll(".ddp-sec")).toHaveLength(0);
  });

  it("서버 사유(현재 목록 조건에 없음)를 그대로 보인다 · 다른 값으로 채우지 않는다", async () => {
    const { container } = render(<DecisionDraftPreviewCard targetKind="candidate" ticker="0223A0" />);
    await generate();
    await answer(0, {
      status: "error",
      message: "현재 목록 조건에서 이 후보를 찾지 못했습니다. 목록을 다시 불러온 뒤 시도하세요.",
    });
    expect(
      screen.getByText("현재 목록 조건에서 이 후보를 찾지 못했습니다. 목록을 다시 불러온 뒤 시도하세요."),
    ).toBeInTheDocument();
    expect(container.querySelectorAll(".ddp-sec")).toHaveLength(0);
    expect(screen.queryByRole("button", { name: "복사" })).not.toBeInTheDocument();
  });
});
