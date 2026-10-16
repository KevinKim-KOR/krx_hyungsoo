// POC5-16 — 「확인 근거」 종목 상세의 접힌 구역 '가격 흔들림(변동성)'(설계 V1 §5 · PLAN Q4 (a) · 판정 §5).
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { PriceVolatilityEvidence } from "@/lib/api";
import PriceVolatilityBlock from "./PriceVolatilityBlock";
import { VOL_HELP_BASIS, VOL_HELP_INSUFFICIENT, VOL_HELP_MEANING } from "./priceVolatility";

const OK: PriceVolatilityEvidence = {
  status: "ok",
  recent: { value_pct: 3.2, start_date: "2026-09-10", end_date: "2026-10-14" },
  previous: { value_pct: 2.97, start_date: "2026-08-12", end_date: "2026-09-10" },
  comparison: "higher",
  recent_reason: null,
  previous_reason: null,
  end_date: "2026-10-14",
};
const toggle = () => screen.getByRole("button", { name: /가격 흔들림\(변동성\)/ });

describe("가격 흔들림 접힌 구역 (POC5-16)", () => {
  it("정상 — 접힘엔 버튼 · ? 만 · 펼치면 두 칸 · 비교 · 기간 줄 · 다시 접힘", () => {
    render(<PriceVolatilityBlock ev={OK} flowDate="2026-10-14" />);
    expect(toggle().textContent).toBe("가격 흔들림(변동성) 보기");
    expect(toggle()).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: "가격 흔들림 도움말" })).toBeInTheDocument();
    expect(screen.queryByTestId("price-volatility-body")).toBeNull();
    expect(screen.queryByTestId("price-volatility-note")).toBeNull();

    fireEvent.click(toggle());
    expect(toggle().textContent).toBe("가격 흔들림(변동성) 접기");
    expect(toggle()).toHaveAttribute("aria-expanded", "true");
    const body = screen.getByTestId("price-volatility-body");
    const cells = Array.from(body.querySelectorAll(".wb-detail-cell")).map((c) => c.textContent);
    expect(cells).toEqual(["최근 20구간3.20%", "직전 20구간2.97%"]);
    expect(screen.getByTestId("price-volatility-cmp").textContent).toBe("직전보다 커짐");
    expect(body.textContent).toContain(
      "최근 2026-09-10 ~ 2026-10-14 · 직전 2026-08-12 ~ 2026-09-10 · PC 저장 종가",
    );
    fireEvent.click(toggle());
    expect(screen.queryByTestId("price-volatility-body")).toBeNull();
  });

  it("색은 중립 — 수익 색(인라인 색) · 경보 배지 없음", () => {
    const { container } = render(<PriceVolatilityBlock ev={OK} flowDate="2026-10-14" />);
    fireEvent.click(toggle());
    expect(container.querySelectorAll("[style]").length).toBe(0);
    expect(container.querySelector(".wb-hb, .warn, .up, .down")).toBeNull();
  });

  it("최근만 — 접혀 있어도 짧은 사유 · 펼치면 '자료 부족' 칸 · 비교 문구 없음", () => {
    const ev: PriceVolatilityEvidence = {
      ...OK, status: "recent_only", previous: null, comparison: null, previous_reason: "insufficient_history",
    };
    render(<PriceVolatilityBlock ev={ev} flowDate="2026-10-14" />);
    expect(screen.getByTestId("price-volatility-note").textContent).toBe(
      "직전 20구간은 계산하지 못해 비교하지 않습니다.",
    );
    fireEvent.click(toggle());
    expect(screen.getByTestId("price-volatility-body").textContent).toContain("직전 20구간자료 부족");
    expect(screen.queryByTestId("price-volatility-cmp")).toBeNull();
    // ? 는 지금 해당하는 제한만 붙인다.
    fireEvent.click(screen.getByRole("button", { name: "가격 흔들림 도움말" }));
    const paras = Array.from(
      screen.getByRole("dialog", { name: "가격 흔들림 도움말" }).querySelectorAll(".help-pop-p"),
    ).map((p) => p.textContent);
    expect(paras).toEqual([VOL_HELP_MEANING, VOL_HELP_BASIS, VOL_HELP_INSUFFICIENT]);
  });

  it.each([
    [
      "date_mismatch" as const,
      "이 종목의 마지막 유효 가격일(2026-10-13)이 PC 가격 흐름 기준일(2026-10-14)과 달라 값을 보이지 않습니다.",
    ],
    ["reference_unavailable" as const, "PC 가격 흐름 기준일을 확인할 수 없어 값을 보이지 않습니다."],
  ])("%s — 접혀 있어도 사유 · 펼쳐도 칸 · 비교 · 기간 줄 없음", (status, note) => {
    const ev: PriceVolatilityEvidence = {
      status, recent: null, previous: null, comparison: null,
      recent_reason: null, previous_reason: null, end_date: "2026-10-13",
    };
    render(<PriceVolatilityBlock ev={ev} flowDate={status === "date_mismatch" ? "2026-10-14" : null} />);
    expect(screen.getByTestId("price-volatility-note").textContent).toBe(note);
    fireEvent.click(toggle());
    expect(screen.queryByTestId("price-volatility-body")).toBeNull();
  });

  it("근거가 없으면(선택 필드 없음 · null) 그리지 않는다", () => {
    const { container, rerender } = render(<PriceVolatilityBlock ev={undefined} flowDate="2026-10-14" />);
    expect(container.innerHTML).toBe("");
    rerender(<PriceVolatilityBlock ev={null} flowDate="2026-10-14" />);
    expect(container.innerHTML).toBe("");
  });
});
