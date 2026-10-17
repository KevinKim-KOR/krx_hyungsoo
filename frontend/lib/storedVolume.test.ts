// POC5-09 — 저장 거래량 표시 형식(단위 주 · 평균 · 배수 소수 둘째 자리 · 상태 문구 · 판정 §9-2).
import { describe, it, expect } from "vitest";
import type { StoredVolumeEvidence } from "@/lib/api";
import { pastVolumeNote, volumeCells, volumeSourceParts } from "./storedVolume";

function ev(over: Partial<StoredVolumeEvidence> = {}): StoredVolumeEvidence {
  return {
    ticker: "069500",
    status: "ok",
    asof_date: "2026-10-08",
    source: "FinanceDataReader",
    volume: 23162524,
    window_size: 20,
    window_start_date: "2026-09-07",
    window_end_date: "2026-10-07",
    window_date_count: 20,
    valid_count: 20,
    avg_prev20: 23710207.85,
    avg_status: "ok",
    ratio: 0.9769009258179067,
    ratio_status: "ok",
    ...over,
  };
}
const values = (e: StoredVolumeEvidence) => volumeCells(e).map((c) => c.value);

describe("storedVolume 표시 (POC5-09)", () => {
  // POC5-19 검증 r1(P2) — 저장된 거래량 자체는 반올림하지 않는다(0 이 아닌 소수가 '0주'로 보이지 않게).
  it("저장된 거래량 그대로: 소수 · 아주 작은 값 · 0 · 정수", () => {
    expect(values(ev({ volume: 0.4 }))[1]).toBe("0.4주");
    expect(values(ev({ volume: 0.0004 }))[1]).toBe("0.0004주");
    expect(values(ev({ volume: 0 }))[1]).toBe("0주");
    expect(values(ev({ volume: 1234.5678 }))[1]).toBe("1,234.5678주");
    expect(values(ev())[1]).toBe("23,162,524주");
  });

  it("정상: 기준일 · 거래량(주) · 직전 20개 저장일 평균 · 평균 대비(배 · 소수 둘째 자리)", () => {
    expect(volumeCells(ev()).map((c) => c.label)).toEqual([
      "기준일",
      "거래량",
      "직전 20개 저장일 평균",
      "평균 대비",
    ]);
    expect(values(ev())).toEqual([
      "2026-10-08",
      "23,162,524주",
      "23,710,207.85주",
      "0.98배",
    ]);
    // 설계 예시: 150만 / 100만 = 1.50배.
    expect(values(ev({ volume: 1500000, avg_prev20: 1000000, ratio: 1.5 }))[3]).toBe("1.50배");
  });

  it("상태별 문구: 자료 부족 (N/20) · 자료 없음 · 계산 불가 · 0 거래량은 0.00배", () => {
    expect(
      values(ev({ avg_prev20: null, avg_status: "insufficient", valid_count: 12, ratio: null, ratio_status: "avg_insufficient" })),
    ).toEqual(["2026-10-08", "23,162,524주", "자료 부족 (12/20)", "자료 부족"]);
    expect(values(ev({ volume: null, ratio: null, ratio_status: "volume_missing" }))).toEqual([
      "2026-10-08",
      "자료 없음",
      "23,710,207.85주",
      "자료 없음",
    ]);
    expect(values(ev({ avg_prev20: 0, ratio: null, ratio_status: "avg_zero" })).slice(2)).toEqual([
      "0.00주",
      "계산 불가",
    ]);
    expect(values(ev({ volume: 0, ratio: 0 }))[3]).toBe("0.00배");
  });

  it("설명 줄: 출처 · 비교 구간 · 유효 N/20 (비교 구간이 없으면 '없음')", () => {
    expect(volumeSourceParts(ev())).toEqual([
      "출처 FinanceDataReader",
      "비교 구간 2026-09-07 ~ 2026-10-07 · 유효 20/20",
    ]);
    expect(
      volumeSourceParts(ev({ source: null, window_date_count: 0, window_start_date: null, window_end_date: null, valid_count: 0 })),
    ).toEqual(["출처 확인 불가", "비교 구간 없음 · 유효 0/20"]);
  });

  it("거래량 기준일이 PC 비교 기준일과 다를 때만 '과거 저장 자료'", () => {
    expect(pastVolumeNote(ev({ asof_date: "2026-08-12" }), "2026-10-08")).toBe(
      "과거 저장 자료 · PC 비교 기준일은 2026-10-08",
    );
    expect(pastVolumeNote(ev(), "2026-10-08")).toBeNull();
    // 기준일보다 늦은 자료는 '과거'라고 부르지 않는다.
    expect(pastVolumeNote(ev({ asof_date: "2026-10-12" }), "2026-10-08")).toBe(
      "PC 비교 기준일(2026-10-08)보다 늦은 날짜의 자료",
    );
    expect(pastVolumeNote(ev({ asof_date: "2026-08-12" }), null)).toBeNull();
  });
});
