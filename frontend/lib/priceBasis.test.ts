// POC5-09 — 가격 기준일 문구(실제 날짜만 · 판정 §9-4).
import { describe, it, expect } from "vitest";
import type { PriceBasis } from "@/lib/api";
import {
  dateMismatchText,
  describeMismatched,
  priceBasisLine,
  priceFlowLine,
  windowMismatchText,
} from "./priceBasis";

const basis = (over: Partial<PriceBasis> = {}): PriceBasis => ({
  reference_date: "2026-10-08",
  reference_ticker: "069500",
  kodex200_start_date_5d: "2026-09-30",
  kodex200_start_date_20d: "2026-09-07",
  date_mismatch: [],
  ...over,
});

describe("priceBasis 문구 (POC5-09)", () => {
  // POC6-33 RESULT 판정 §2-6 — 종목 자신의 마지막 저장일(end_date)은 '마지막 저장일'(합성 종목).
  it("종목 마지막 저장일별로 묶는다", () => {
    expect(
      describeMismatched([
        { ticker: "TEST01", name: "보유 A", end_date: "2026-08-12" },
        { ticker: "TEST02", name: "보유 B", end_date: "2026-08-12" },
        { ticker: "X1", name: null, end_date: "2026-09-01" },
      ]),
    ).toBe("보유 A · 보유 B(마지막 저장일 2026-08-12) · X1(마지막 저장일 2026-09-01)");
  });

  // POC6-33(판정 Q31 · Q47 · PLAN E1) — 가격 기준일은 목록 위 요약 칸 한 곳에만 이름을 붙인다 · 5 · 20 = 저장일.
  it("「확인 근거」 기준 줄 — KODEX 200 20저장일 비교 기간 · 뺀 종목 · 가격 기준일 이름은 다시 적지 않음", () => {
    expect(priceBasisLine(basis())).toBe(
      "가격 흐름(최근 5 · 20저장일 · KODEX 200 대비) 기준 · KODEX 200 20저장일 비교 기간 2026-09-07 ~ 2026-10-08.",
    );
    expect(
      priceBasisLine(
        basis({ date_mismatch: [{ ticker: "TEST01", name: "보유 A", end_date: "2026-08-12" }] }),
      ),
    ).toBe(
      "가격 흐름(최근 5 · 20저장일 · KODEX 200 대비) 기준 · KODEX 200 20저장일 비교 기간 2026-09-07 ~ 2026-10-08. 마지막 저장일이 가격 기준일과 다른 1종목은 현재 비교에서 뺐습니다: 보유 A(마지막 저장일 2026-08-12).",
    );
    expect(priceBasisLine(basis({ reference_date: null }))).toBe(
      "가격 흐름(최근 5 · 20저장일 · KODEX 200 대비) 기준 · KODEX 200 20저장일 비교 기간 확인 불가.",
    );
    for (const b of [basis(), basis({ reference_date: null })]) {
      expect(priceBasisLine(b)).not.toMatch(/PC 저장 가격 기준일|PC 가격 흐름 기준일|PC 비교 기준일|저장 가격 기준일|5일|20일/);
    }
  });

  it("사유 문구에 실제 날짜를 넣는다", () => {
    expect(dateMismatchText("2026-08-12", "2026-10-08")).toBe(
      "이 종목 마지막 저장일: 2026-08-12 / 가격 기준일: 2026-10-08 — 두 날짜가 달라 현재 비교에 사용하지 않습니다.",
    );
    expect(windowMismatchText(20, "2026-09-06", "2026-10-08", "2026-09-07", "2026-10-08")).toBe(
      "KODEX 200 대비 20저장일: 종목 비교 기간 2026-09-06 ~ 2026-10-08 / KODEX 200 비교 기간 2026-09-07 ~ 2026-10-08 — 기간이 달라 비교값을 비워 두었습니다.",
    );
    expect(priceFlowLine("2026-10-08", "2026-09-30", "2026-09-07")).toBe(
      "마지막 저장일 2026-10-08 · 5저장일 2026-09-30 ~ 2026-10-08 · 20저장일 2026-09-07 ~ 2026-10-08",
    );
    // 이력이 짧아 20일 시작일이 없는 기준일 불일치 종목(검증자 r1 경로) — 날짜를 지어내지 않는다.
    expect(priceFlowLine("2026-08-12", "2026-08-05", null)).toBe(
      "마지막 저장일 2026-08-12 · 5저장일 2026-08-05 ~ 2026-08-12 · 20저장일 확인 불가 ~ 2026-08-12",
    );
  });
});
