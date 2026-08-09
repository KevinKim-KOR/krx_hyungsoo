// POC3-08 입력 콤마 로직 테스트.
// 핵심: 콤마 표시가 저장 왕복을 깨지 않아야 한다(매입단가 NaN 방지).
import { describe, it, expect } from "vitest";
import { formatWithCommas, stripCommas } from "./HoldingsManageView";

describe("formatWithCommas — 입력 중 콤마 표시", () => {
  it("정수에 천단위 콤마를 넣는다", () => {
    expect(formatWithCommas("84190")).toBe("84,190");
    expect(formatWithCommas("1000000")).toBe("1,000,000");
    expect(formatWithCommas("100")).toBe("100");
  });

  it("빈 문자열은 그대로 빈 문자열", () => {
    expect(formatWithCommas("")).toBe("");
  });

  it("소수점 입력 중 상태를 보존한다", () => {
    expect(formatWithCommas("1234.5")).toBe("1,234.5");
    expect(formatWithCommas("1234.")).toBe("1,234."); // 입력 중 끝 점 보존
    expect(formatWithCommas("0.25")).toBe("0.25");
  });

  it("이미 콤마가 있는 입력도 재포맷(중복 콤마 안 생김)", () => {
    expect(formatWithCommas("84,190")).toBe("84,190");
    expect(formatWithCommas("8,4,1,9,0")).toBe("84,190");
  });

  it("숫자·점·콤마 외 문자는 제거", () => {
    expect(formatWithCommas("84190원")).toBe("84,190");
    expect(formatWithCommas("abc")).toBe("");
  });
});

describe("stripCommas — 저장 전 콤마 제거", () => {
  it("콤마를 모두 제거한다", () => {
    expect(stripCommas("84,190")).toBe("84190");
    expect(stripCommas("1,000,000")).toBe("1000000");
    expect(stripCommas("1,234.5")).toBe("1234.5");
  });

  it("콤마 없는 값은 그대로", () => {
    expect(stripCommas("100")).toBe("100");
    expect(stripCommas("")).toBe("");
  });
});

describe("저장 왕복 — 콤마 표시가 숫자 저장을 깨지 않는다", () => {
  it("표시값을 strip 하면 Number 로 정확히 파싱된다", () => {
    const displayed = formatWithCommas("84190"); // "84,190"
    expect(Number(stripCommas(displayed))).toBe(84190);
  });

  it("소수 수량도 왕복 유지", () => {
    const displayed = formatWithCommas("1234.5"); // "1,234.5"
    expect(Number(stripCommas(displayed))).toBe(1234.5);
  });

  it("큰 매입단가 왕복", () => {
    const displayed = formatWithCommas("301667"); // "301,667"
    expect(Number(stripCommas(displayed))).toBe(301667);
  });
});
