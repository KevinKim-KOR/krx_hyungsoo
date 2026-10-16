// POC5-16 — 가격 흔들림(변동성) 문구 · 도움말(설계 V1 §4 · §5 · PLAN 판정 2026-10-16 §3 · §4 · §5).
import { describe, it, expect } from "vitest";
import type { PriceVolatilityEvidence } from "@/lib/api";
import {
  COMPARISON_TEXT,
  REASON_TEXT,
  VOL_HELP_BASIS,
  VOL_HELP_BASIS_UNCONFIRMED,
  VOL_HELP_DATE,
  VOL_HELP_INSUFFICIENT,
  VOL_HELP_INVALID,
  VOL_HELP_MEANING,
  VOL_HELP_REF,
  cellValue,
  hidesValues,
  periodLine,
  volatilityHelp,
  volatilityNote,
} from "./priceVolatility";

const RECENT = { value_pct: 3.2, start_date: "2026-09-10", end_date: "2026-10-14" };
const PREVIOUS = { value_pct: 2.97, start_date: "2026-08-12", end_date: "2026-09-10" };

function ev(over: Partial<PriceVolatilityEvidence> = {}): PriceVolatilityEvidence {
  return {
    status: "ok",
    recent: RECENT,
    previous: PREVIOUS,
    comparison: "higher",
    recent_reason: null,
    previous_reason: null,
    end_date: "2026-10-14",
    ...over,
  };
}

describe("가격 흔들림 문구 (POC5-16)", () => {
  it("값은 소수 둘째 자리 % · 실제 0% 도 값 · 사유 문구 · 판정 §4 '가격 기준 확인 필요'", () => {
    expect(cellValue(RECENT, null)).toBe("3.20%");
    expect(cellValue({ ...RECENT, value_pct: 0 }, null)).toBe("0.00%");
    expect(cellValue(null, "insufficient_history")).toBe("자료 부족");
    expect(cellValue(null, "invalid_price")).toBe("가격 확인 필요");
    expect(cellValue(null, "basis_unconfirmed")).toBe("가격 기준 확인 필요");
    expect(cellValue(null, null)).toBe("확인 불가");
    expect(Object.values(REASON_TEXT)).not.toContain("가격 기준 변화");
    expect(COMPARISON_TEXT).toEqual({
      higher: "직전보다 커짐",
      lower: "직전보다 작아짐",
      same: "직전과 같음",
    });
  });

  it("짧은 사유 — 정상은 없음 · 상태별 한 문장 · 판정 §3 '마지막 유효 가격일'", () => {
    expect(volatilityNote(ev(), "2026-10-14")).toBeNull();
    expect(volatilityNote(ev({ status: "recent_only" }), "2026-10-14")).toBe(
      "직전 20구간은 계산하지 못해 비교하지 않습니다.",
    );
    expect(volatilityNote(ev({ status: "previous_only" }), "2026-10-14")).toBe(
      "최근 20구간은 계산하지 못해 비교하지 않습니다.",
    );
    expect(volatilityNote(ev({ status: "unavailable" }), "2026-10-14")).toBe(
      "최근 · 직전 20구간 모두 계산하지 못했습니다.",
    );
    const dm = volatilityNote(ev({ status: "date_mismatch", end_date: "2026-10-13" }), "2026-10-14");
    expect(dm).toBe(
      "이 종목의 마지막 유효 가격일(2026-10-13)이 PC 가격 흐름 기준일(2026-10-14)과 달라 값을 보이지 않습니다.",
    );
    expect(dm).not.toContain("최근 저장일");
    expect(volatilityNote(ev({ status: "reference_unavailable" }), null)).toBe(
      "PC 가격 흐름 기준일을 확인할 수 없어 값을 보이지 않습니다.",
    );
  });

  it("값을 숨기는 상태는 기준일 다름 · 기준일 없음 두 가지뿐", () => {
    const hidden = (["ok", "recent_only", "previous_only", "unavailable", "date_mismatch", "reference_unavailable"] as const)
      .filter((s) => hidesValues(ev({ status: s })));
    expect(hidden).toEqual(["date_mismatch", "reference_unavailable"]);
  });

  it("기간 줄 — 있는 기간만 · 둘 다 없으면 마지막 유효 가격일 · 'PC 저장 종가'", () => {
    expect(periodLine(ev())).toBe(
      "최근 2026-09-10 ~ 2026-10-14 · 직전 2026-08-12 ~ 2026-09-10 · PC 저장 종가",
    );
    expect(periodLine(ev({ previous: null }))).toBe("최근 2026-09-10 ~ 2026-10-14 · PC 저장 종가");
    expect(periodLine(ev({ recent: null, previous: null }))).toBe(
      "마지막 유효 가격일 2026-10-14 · PC 저장 종가",
    );
  });

  it("도움말 — 뜻 → 계산 기준 → 지금 해당하는 제한만(순서)", () => {
    expect(volatilityHelp(ev())).toEqual([VOL_HELP_MEANING, VOL_HELP_BASIS]);
    expect(
      volatilityHelp(ev({ status: "recent_only", previous: null, previous_reason: "insufficient_history" })),
    ).toEqual([VOL_HELP_MEANING, VOL_HELP_BASIS, VOL_HELP_INSUFFICIENT]);
    expect(
      volatilityHelp(
        ev({
          status: "unavailable",
          recent: null,
          previous: null,
          recent_reason: "basis_unconfirmed",
          previous_reason: "invalid_price",
        }),
      ),
    ).toEqual([VOL_HELP_MEANING, VOL_HELP_BASIS, VOL_HELP_INVALID, VOL_HELP_BASIS_UNCONFIRMED]);
    expect(volatilityHelp(ev({ status: "date_mismatch" }))).toEqual([
      VOL_HELP_MEANING,
      VOL_HELP_BASIS,
      VOL_HELP_DATE,
    ]);
    expect(volatilityHelp(ev({ status: "reference_unavailable" }))).toEqual([
      VOL_HELP_MEANING,
      VOL_HELP_BASIS,
      VOL_HELP_REF,
    ]);
  });

  it("문장 내용 — 하락 폭 아님 · 분모 20 · 연율화 없음 · 경계 종가 공유 · 표시값 비교 · 실제 가격 변화로 단정하지 않음", () => {
    expect(VOL_HELP_MEANING).toContain("하락 폭을 뜻하는 값은 아닙니다");
    for (const s of ["분모 20", "연율화하지 않음", "경계 종가 하나만", "소수 둘째 자리", "실시간 시세가 아닌 PC 저장 종가"]) {
      expect(VOL_HELP_BASIS).toContain(s);
    }
    expect(VOL_HELP_BASIS).not.toContain("OCI");
    expect(VOL_HELP_BASIS_UNCONFIRMED).toContain("단정하는 뜻은 아닙니다");
    for (const s of ["분배락", "액면"]) expect(VOL_HELP_BASIS_UNCONFIRMED).not.toContain(s);
    expect(VOL_HELP_DATE).toContain("마지막 유효 가격일");
    // E ≠ D 는 어느 쪽이 늦어도 해당 — 숨긴 값을 '오래된 기간'으로 단정하지 않는다.
    expect(VOL_HELP_DATE).toContain("기준일이 다른 기간");
    expect(VOL_HELP_DATE).not.toContain("오래된");
    const all = [
      VOL_HELP_MEANING, VOL_HELP_BASIS, VOL_HELP_INSUFFICIENT, VOL_HELP_INVALID,
      VOL_HELP_BASIS_UNCONFIRMED, VOL_HELP_DATE, VOL_HELP_REF,
      ...Object.values(REASON_TEXT), ...Object.values(COMPARISON_TEXT),
    ].join(" ");
    for (const bad of ["위험", "고위험", "안전", "매수", "매도", "손절", "청산", "BUY", "SELL"]) {
      expect(all).not.toContain(bad);
    }
  });
});
