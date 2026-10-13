// POC5-09 — PC 가격 흐름 기준일 문구(실제 날짜만 · 판정 §9-4).
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
  it("기준일별로 묶는다", () => {
    expect(
      describeMismatched([
        { ticker: "005930", name: "삼성전자", end_date: "2026-08-12" },
        { ticker: "000660", name: "SK하이닉스", end_date: "2026-08-12" },
        { ticker: "X1", name: null, end_date: "2026-09-01" },
      ]),
    ).toBe("삼성전자 · SK하이닉스(저장 가격 기준일 2026-08-12) · X1(저장 가격 기준일 2026-09-01)");
  });

  it("「확인 근거」 기준 줄 — 기준일 · KODEX200 20일 비교 기간 · 뺀 종목", () => {
    expect(priceBasisLine(basis())).toBe(
      "가격 흐름(5일 · 20일 · KODEX200 대비) 기준: PC 저장 가격 기준일 2026-10-08 · KODEX200 20일 비교 기간 2026-09-07 ~ 2026-10-08.",
    );
    expect(
      priceBasisLine(
        basis({ date_mismatch: [{ ticker: "000660", name: "SK하이닉스", end_date: "2026-08-12" }] }),
      ),
    ).toBe(
      "가격 흐름(5일 · 20일 · KODEX200 대비) 기준: PC 저장 가격 기준일 2026-10-08 · KODEX200 20일 비교 기간 2026-09-07 ~ 2026-10-08. 기준일이 다른 1종목은 현재 비교에서 뺐습니다: SK하이닉스(저장 가격 기준일 2026-08-12).",
    );
    expect(priceBasisLine(basis({ reference_date: null }))).toBe(
      "가격 흐름(5일 · 20일 · KODEX200 대비) 기준: PC 저장 가격 기준일 확인 불가.",
    );
  });

  it("사유 문구에 실제 날짜를 넣는다", () => {
    expect(dateMismatchText("2026-08-12", "2026-10-08")).toBe(
      "저장 가격 기준일: 2026-08-12 / PC 비교 기준일: 2026-10-08 — 기준일이 달라 현재 비교에 사용하지 않습니다.",
    );
    expect(windowMismatchText(20, "2026-09-06", "2026-10-08", "2026-09-07", "2026-10-08")).toBe(
      "KODEX200 대비 20일: 종목 비교 기간 2026-09-06 ~ 2026-10-08 / KODEX200 비교 기간 2026-09-07 ~ 2026-10-08 — 기간이 달라 비교값을 비워 두었습니다.",
    );
    expect(priceFlowLine("2026-10-08", "2026-09-30", "2026-09-07")).toBe(
      "기준일 2026-10-08 · 5일 2026-09-30 ~ 2026-10-08 · 20일 2026-09-07 ~ 2026-10-08",
    );
    // 이력이 짧아 20일 시작일이 없는 기준일 불일치 종목(검증자 r1 경로) — 날짜를 지어내지 않는다.
    expect(priceFlowLine("2026-08-12", "2026-08-05", null)).toBe(
      "기준일 2026-08-12 · 5일 2026-08-05 ~ 2026-08-12 · 20일 확인 불가 ~ 2026-08-12",
    );
  });
});
