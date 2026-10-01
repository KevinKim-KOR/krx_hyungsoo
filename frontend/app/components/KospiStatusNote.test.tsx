// POC3-02D-OPS-02 3-4 — KOSPI 최신성 상태 표시 (설계자 확정 문구 2026-09-28).
// 두 화면(「오늘의 투자 점검」 KOSPI 카드 · 「요즘 잘 오르는 ETF」 시장 배경 카드)이
// 같은 생성기를 쓰는지, 상태별 배지 · 기준 줄 · 사유 줄이 확정 문구와 같은지,
// 기술 토큰 · KODEX200 축 지연이 화면에 나오지 않는지 본다.
import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import type { MarketContext, MarketContextKospi, MarketTopNResponse } from "@/lib/api";
import type { QueryState } from "@/lib/api/queryCache";

vi.mock("./today/KospiChart", () => ({ default: () => null }));

import { kospiStatusView } from "@/lib/kospiStatus";
import KospiHeadline from "./today/KospiHeadline";
import MarketContextCard from "./MarketContextCard";

const STALE: MarketContextKospi = {
  status: "stale",
  as_of_date: "2026-09-17",
  display_state: "stale",
  trading_day_lag: 4,
  today_is_trading_day: true,
};

const OK: MarketContextKospi = {
  status: "ok",
  return_20d_pct: 1.2,
  return_60d_pct: 3.4,
  return_1m_pct: 1.1,
  return_3m_pct: 2.2,
  daily_return_pct: 0.5,
  return_1y_pct: 12.3,
  high_52w_gap_pct: -1.5,
  as_of_date: "2026-09-28",
  display_state: "ok",
  trading_day_lag: 0,
  today_is_trading_day: true,
};

function ctxWith(kospi: MarketContextKospi, warnings: string[] = []): MarketContext {
  return {
    status: "partial",
    asof: "2026-09-21",
    primary_benchmark: "KODEX200",
    regime_label: "보합장",
    regime_code: "neutral",
    regime_score: 0,
    regime_reasons: [],
    kodex200: { status: "ok" },
    kospi,
    warnings,
  };
}

function marketState(kospi: MarketContextKospi): QueryState<MarketTopNResponse> {
  return {
    phase: "success",
    stale: false,
    data: { asof: "2026-09-21", market_context: ctxWith(kospi) },
  } as unknown as QueryState<MarketTopNResponse>;
}

function viewText(kospi: MarketContextKospi | null, phase?: "loading" | "error"): string {
  const v = kospiStatusView(kospi, phase);
  if (v.loading) return "";
  return [...v.badges.map((b) => b.text), v.basisLine ?? "", v.reason ?? ""].join(" | ");
}

describe("kospiStatusView — 상태별 확정 문구", () => {
  it("정상: 배지 · 사유 없이 기준일만", () => {
    const v = kospiStatusView(OK);
    expect(v).toEqual({
      loading: false,
      state: "ok",
      badges: [],
      basisLine: "KOSPI 기준일 2026-09-28",
      reason: null,
    });
  });

  it("기준일 지연: 배지 · 'KOSPI 기준일 · N거래일 지연' · 사유 한 줄", () => {
    const v = kospiStatusView(STALE);
    expect(v).toEqual({
      loading: false,
      state: "stale",
      badges: [{ text: "기준일 지연", tone: "warn" }],
      basisLine: "KOSPI 기준일 2026-09-17 · 4거래일 지연",
      reason: "KOSPI 원자료가 최근 거래일까지 갱신되지 않았습니다.",
    });
  });

  it("자료원 확인 실패: 마지막 기준일이 있으면 함께", () => {
    const v = kospiStatusView({ ...STALE, display_state: "source_failed" });
    expect(v).toMatchObject({
      state: "source_failed",
      badges: [{ text: "자료원 확인 실패", tone: "warn" }],
      basisLine: "KOSPI 기준일 2026-09-17 · 4거래일 지연",
      reason: "KOSPI 원자료를 불러오지 못했습니다.",
    });
  });

  it("수집 결과 없음 · 아직 평가되지 않음: 기준일 없이 사유만", () => {
    const base: MarketContextKospi = { status: "unavailable", as_of_date: null };
    expect(kospiStatusView({ ...base, display_state: "no_result" })).toMatchObject({
      badges: [{ text: "수집 결과 없음", tone: "warn" }],
      basisLine: null,
      reason: "저장된 KOSPI 자료가 없습니다.",
    });
    expect(kospiStatusView({ ...base, display_state: "not_evaluated" })).toMatchObject({
      badges: [{ text: "아직 평가되지 않음", tone: "warn" }],
      basisLine: null,
      reason: "KOSPI 최신성 판정이 아직 실행되지 않았습니다.",
    });
  });

  it("M1 수집 결과 없음 — 기준일은 있으나 수익률이 없으면 사유가 다르다", () => {
    const withAsOf: MarketContextKospi = {
      status: "unavailable",
      as_of_date: "2026-09-23",
      display_state: "no_result",
      trading_day_lag: 0,
      today_is_trading_day: true,
    };
    expect(kospiStatusView(withAsOf)).toEqual({
      loading: false,
      state: "no_result",
      badges: [{ text: "수집 결과 없음", tone: "warn" }],
      basisLine: "KOSPI 기준일 2026-09-23",
      reason: "KOSPI 수익률을 계산할 자료가 충분하지 않습니다.",
    });
    // 행 자체가 없으면(기준일 없음) 기존 문장 그대로.
    expect(
      kospiStatusView({ status: "unavailable", as_of_date: null, display_state: "no_result" }),
    ).toMatchObject({ basisLine: null, reason: "저장된 KOSPI 자료가 없습니다." });
    // 이 변경 전 서버(display_state 없음)도 같은 규칙.
    expect(kospiStatusView({ status: "unavailable", as_of_date: "2026-09-23" })).toMatchObject({
      state: "no_result",
      reason: "KOSPI 수익률을 계산할 자료가 충분하지 않습니다.",
    });
  });

  it("휴장일: 중립 배지 · 최근 기준일 · 지연으로 경고하지 않는다", () => {
    const v = kospiStatusView({
      ...OK,
      display_state: "holiday",
      trading_day_lag: 1,
      today_is_trading_day: false,
    });
    expect(v).toMatchObject({
      state: "holiday",
      badges: [{ text: "휴장일", tone: "neutral" }],
      basisLine: "KOSPI 기준일 2026-09-28",
      reason: "오늘은 국내 증시 휴장일입니다.",
    });
    expect(viewText({ ...OK, display_state: "holiday" })).not.toContain("지연");
  });

  it("휴장일에 오래된 자료: '기준일 지연' + 중립 '휴장일' 배지 · 사유는 지연", () => {
    const v = kospiStatusView({ ...STALE, today_is_trading_day: false });
    expect(v).toMatchObject({
      state: "stale",
      badges: [
        { text: "기준일 지연", tone: "warn" },
        { text: "휴장일", tone: "neutral" },
      ],
      reason: "KOSPI 원자료가 최근 거래일까지 갱신되지 않았습니다.",
    });
  });

  it("화면 요청 진행 중은 로딩 — '아직 평가되지 않음'과 합치지 않는다", () => {
    expect(kospiStatusView(null, "loading")).toEqual({ loading: true });
    expect(kospiStatusView(undefined, "idle")).toEqual({ loading: true });
  });

  it("화면 호출 실패 · 응답에 KOSPI 없음 → 자료원 확인 실패", () => {
    expect(kospiStatusView(null, "error")).toMatchObject({
      state: "source_failed",
      basisLine: null,
      reason: "KOSPI 원자료를 불러오지 못했습니다.",
    });
    expect(kospiStatusView(null)).toMatchObject({ state: "source_failed" });
  });

  it("지연 거래일 수는 백엔드 값만 — 모르면 붙이지 않는다(화면 계산 없음)", () => {
    expect(kospiStatusView({ ...STALE, trading_day_lag: null })).toMatchObject({
      basisLine: "KOSPI 기준일 2026-09-17",
    });
    // 이 변경 전 서버(display_state 없음)는 기존 status 로만 고르고 지연 수를 만들지 않는다.
    const legacy: MarketContextKospi = { status: "stale", as_of_date: "2026-09-17" };
    expect(kospiStatusView(legacy)).toMatchObject({
      state: "stale",
      basisLine: "KOSPI 기준일 2026-09-17",
    });
    expect(kospiStatusView({ status: "ok", as_of_date: "2026-09-28" })).toMatchObject({
      state: "ok",
      reason: null,
    });
    expect(kospiStatusView({ status: "unavailable" })).toMatchObject({ state: "no_result" });
  });

  it("기술 토큰 · KODEX200 축 표기가 어떤 상태에도 나오지 않는다", () => {
    const states = [
      "ok",
      "stale",
      "source_failed",
      "no_result",
      "not_evaluated",
      "holiday",
    ] as const;
    const texts = [
      ...states.map((s) => viewText({ ...STALE, display_state: s, today_is_trading_day: false })),
      viewText(null, "error"),
    ].join("\n");
    for (const token of ["source_stale", "stale", "unavailable", "failed", "lag", "KODEX200"]) {
      expect(texts).not.toContain(token);
    }
  });
});

describe("두 화면이 같은 생성기를 쓴다", () => {
  it("「오늘의 투자 점검」 KOSPI 카드 — 지연 상태", () => {
    render(<KospiHeadline market={marketState(STALE)} />);
    const card = screen.getByLabelText("KOSPI 현재 위치");
    const label = within(card).getByText(/코스피 수익률·위치/);
    expect(within(label).getByText("기준일 지연")).toHaveClass("kospi-badge", "warn");
    expect(card.textContent).toContain("KOSPI 기준일 2026-09-17 · 4거래일 지연");
    expect(card.textContent).toContain("KOSPI 원자료가 최근 거래일까지 갱신되지 않았습니다.");
    expect(card.textContent).not.toContain("수익률·위치 자료 없음");
  });

  it("「오늘의 투자 점검」 KOSPI 카드 — 정상은 값 + 기준일만", () => {
    render(<KospiHeadline market={marketState(OK)} />);
    const card = screen.getByLabelText("KOSPI 현재 위치");
    expect(card.textContent).toContain("1개월");
    expect(card.textContent).toContain("KOSPI 기준일 2026-09-28");
    expect(card.querySelector(".kospi-badge")).toBeNull();
    expect(card.querySelector(".kospi-status-reason")).toBeNull();
  });

  it("「오늘의 투자 점검」 KOSPI 카드 — 불러오는 중은 '확인 중'", () => {
    render(<KospiHeadline market={{ phase: "loading" }} />);
    const card = screen.getByLabelText("KOSPI 현재 위치");
    expect(card.textContent).toContain("확인 중");
    expect(card.textContent).not.toContain("아직 평가되지 않음");
    expect(card.querySelector(".kospi-badge")).toBeNull();
  });

  it("「요즘 잘 오르는 ETF」 시장 배경 — 같은 문구 · KOSPI 영문 경고만 숨김", () => {
    const kodexWarn = "KODEX200 benchmark data is insufficient.";
    render(
      <MarketContextCard
        ctx={ctxWith(STALE, [
          "KOSPI benchmark is stale (as_of=2026-09-17, lag=2 trading days). Returns are not computed.",
          kodexWarn,
        ])}
      />,
    );
    const h3 = screen.getByRole("heading", { name: /^KOSPI \(보조\)/ });
    expect(within(h3).getByText("기준일 지연")).toHaveClass("kospi-badge", "warn");
    const body = document.body.textContent ?? "";
    expect(body).toContain("KOSPI 기준일 2026-09-17 · 4거래일 지연");
    expect(body).toContain("KOSPI 원자료가 최근 거래일까지 갱신되지 않았습니다.");
    expect(body).not.toContain("N/A — KOSPI 시계열이 수집되지 않았습니다.");
    expect(body).not.toContain("KOSPI benchmark");
    expect(body).not.toContain("lag=2");
    expect(body).toContain(kodexWarn);
  });

  it.each([
    ["기준일 없음", null, "저장된 KOSPI 자료가 없습니다.", "KOSPI 수익률을 계산할 자료가 충분하지 않습니다."],
    ["기준일 있음", "2026-09-23", "KOSPI 수익률을 계산할 자료가 충분하지 않습니다.", "저장된 KOSPI 자료가 없습니다."],
  ])("M1 두 화면 — 수집 결과 없음 · %s", (_label, asOf, shown, hidden) => {
    const kospi: MarketContextKospi = {
      status: "unavailable",
      as_of_date: asOf,
      display_state: "no_result",
      trading_day_lag: asOf ? 0 : null,
      today_is_trading_day: true,
    };
    const { unmount } = render(<KospiHeadline market={marketState(kospi)} />);
    const today = screen.getByLabelText("KOSPI 현재 위치");
    expect(within(today).getByText("수집 결과 없음")).toHaveClass("kospi-badge", "warn");
    expect(today.textContent).toContain(shown);
    expect(today.textContent).not.toContain(hidden);
    unmount();
    render(<MarketContextCard ctx={ctxWith(kospi)} />);
    const h3 = screen.getByRole("heading", { name: /^KOSPI \(보조\)/ });
    expect(within(h3).getByText("수집 결과 없음")).toHaveClass("kospi-badge", "warn");
    const body = document.body.textContent ?? "";
    expect(body).toContain(shown);
    expect(body).not.toContain(hidden);
    if (asOf) {
      expect(body).toContain(`KOSPI 기준일 ${asOf}`);
    } else {
      expect(body).not.toContain("KOSPI 기준일");
    }
  });

  it("두 화면의 상태 줄 텍스트가 같다", () => {
    const { unmount } = render(<KospiHeadline market={marketState(STALE)} />);
    const a = document.querySelector("[data-kospi-state]")?.textContent;
    unmount();
    render(<MarketContextCard ctx={ctxWith(STALE)} />);
    const b = document.querySelector("[data-kospi-state]")?.textContent;
    expect(a).toBeTruthy();
    expect(a).toBe(b);
  });
});
