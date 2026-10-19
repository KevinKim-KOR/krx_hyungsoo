// POC5-25 — '20저장일 종가 고점 대비' 공통 도우미(두 화면 · 정렬이 같은 판정).
import { describe, it, expect } from "vitest";
import type { MarketCandidate } from "./api";
import {
  DD_HELP,
  DD_REASON,
  ddColor,
  ddDetail,
  ddGroup,
  ddNote,
  ddPct,
  ddSortValue,
  ddSummary,
  ddView,
} from "./storedDrawdown";

function c(sd: Record<string, unknown> | null | undefined, old = -0.5): MarketCandidate {
  return { ticker: "X", drawdown_20d: old, stored_drawdown_20: sd } as unknown as MarketCandidate;
}
const ok = (v: number, start = "2026-09-16", end = "2026-10-14", peak = "2026-10-06") => ({
  status: "ok",
  value_pct: v,
  start_date: start,
  end_date: end,
  peak_date: peak,
  peak_close: 28550,
  rows: 20,
});

describe("ddView · ddSortValue — 새 객체만 읽는다(옛 drawdown_20d 대체 없음 · 100배 없음)", () => {
  it("ok 는 % 그대로", () => {
    const v = ddView(c(ok(-13.8354)));
    expect(v).toEqual({
      kind: "ok",
      value: -13.8354,
      start: "2026-09-16",
      end: "2026-10-14",
      peakDate: "2026-10-06",
      peakClose: 28550,
    });
    expect(ddSortValue(c(ok(-13.8354)))).toBe(-13.8354);
  });

  it.each([
    ["insufficient_history", "저장 종가 20개 미만"],
    ["invalid_price", "기간 안 비정상 종가"],
    ["basis_unconfirmed", "가격 기준 확인 필요"],
    ["end_date_unknown", "기준일 확인 불가"],
  ])("사유 %s → %s · 옛 값으로 채우지 않음", (reason, text) => {
    const x = c({ status: "unavailable", reason, rows: 18 });
    expect(ddView(x)).toEqual({ kind: "none", reason: text });
    expect(ddSortValue(x)).toBeNull();
    expect(DD_REASON[reason]).toBe(text);
  });

  it("객체가 없으면(옛 응답) 값 없음 — 옛 drawdown_20d −50% 를 쓰지 않는다", () => {
    expect(ddView(c(undefined))).toEqual({ kind: "none", reason: "자료 없음" });
    expect(ddSortValue(c(null))).toBeNull();
  });
});

describe("ddGroup · ddSummary · ddNote — 공통 기간은 한 번 · 다른 종목만 기간", () => {
  it("모두 같으면 한 줄 · 값 아래는 고점 날짜만", () => {
    const cs = [c(ok(-1)), c(ok(0, "2026-09-16", "2026-10-14", "2026-10-14"))];
    const g = ddGroup(cs);
    expect(ddSummary(g)).toBe("2026-09-16 ~ 2026-10-14 저장 종가 20개 · 표시 후보 2개 모두 같음");
    expect(ddNote(ddView(cs[0]), g)).toBe("고점 2026-10-06");
  });

  it("값 없음은 개수만 덧붙인다", () => {
    const g = ddGroup([c(ok(-1)), c({ status: "unavailable", reason: "insufficient_history" })]);
    expect(ddSummary(g)).toBe("2026-09-16 ~ 2026-10-14 저장 종가 20개 · 표시 후보 1개 모두 같음 · 값 없음 1개");
  });

  it("기간이 다르면 다수 날짜를 기준으로 삼지 않고 끝일을 모두 적고 값 아래에 각자 기간", () => {
    const a = c(ok(-1));
    const b = c(ok(-2, "2026-09-15", "2026-10-13"));
    const g = ddGroup([a, a, b]);
    expect(ddSummary(g)).toBe("종목별 기간 다름 · 끝일 2026-10-13 · 2026-10-14 · 기간은 값 아래");
    expect(ddNote(ddView(a), g)).toBe("2026-09-16 ~ 2026-10-14 · 고점 2026-10-06");
    expect(ddNote(ddView(b), g)).toBe("2026-09-15 ~ 2026-10-13 · 고점 2026-10-06");
  });

  it("값이 하나도 없으면 '값 없음 n개'", () => {
    const g = ddGroup([c({ status: "unavailable", reason: "invalid_price" })]);
    expect(ddSummary(g)).toBe("값 없음 1개");
    expect(ddNote(ddView(c({ status: "unavailable" })), g)).toBeNull();
  });
});

describe("ddDetail · ddColor · 도움말", () => {
  it("상세 = 화면 % 함수 · 기간 · 고점(날짜 · 종가 천 단위)", () => {
    expect(ddDetail(ddView(c(ok(-13.8354))), (x) => `${x.toFixed(2)}%`)).toBe(
      "-13.84% (2026-09-16 ~ 2026-10-14 · 고점 2026-10-06 28,550)",
    );
    expect(ddDetail(ddView(c({ status: "unavailable", reason: "invalid_price" })), String)).toBe(
      "기간 안 비정상 종가",
    );
  });

  it("0 은 화면 % 함수가 '+'를 붙여도 '0.00%' · 음수는 그대로", () => {
    const plus = (x: number) => `${x >= 0 ? "+" : ""}${x.toFixed(2)}%`;
    expect(ddPct(0, plus)).toBe("0.00%");
    expect(ddPct(-3.5, plus)).toBe("-3.50%");
    expect(ddDetail(ddView(c(ok(0))), plus)).toMatch(/^0\.00% \(/);
  });

  it("고점과 같은 0% 는 중립 색 · 음수만 하락 색 · 값 없음은 흐린 색", () => {
    const neg = () => "BLUE";
    expect(ddColor(ddView(c(ok(0))), neg)).toBe("var(--fg)");
    expect(ddColor(ddView(c(ok(-3))), neg)).toBe("BLUE");
    expect(ddColor(ddView(c(null)), neg)).toBe("var(--muted)");
  });

  it("도움말은 뜻 · 예 · 값 없음 사유 · MDD · 옛 값과의 구분을 담는다", () => {
    const t = DD_HELP.join(" ");
    for (const k of ["최근 저장 종가 20개", "−25%", "장중 고가가 아닌 종가", "20개 미만", "MDD", "2026-08-27"]) {
      expect(t).toContain(k);
    }
  });
});
