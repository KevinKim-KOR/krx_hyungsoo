// POC6-29 보완 R3 — 「보유와 후보 비교」 차이 줄 규칙(보완 PLAN 판정 2026-11-12 '구현에서 확인할 세 가지' 3).
// 차이는 두 쪽이 모두 계산되고 · 시작 · 끝일이 같고 · 확인된 가격 상태가 같을 때만. 판정 순서까지 조합으로 본다.
// 보완 2차 S3(PLAN §10-6 · S 판정 Q-S6) — 최근 5 · 20구간 · 고점 대비(20저장일 창 · 하락폭 작음/큼)도 같은 순서로.
import { describe, it, expect } from "vitest";
import type { EtfDetailItem } from "@/lib/api/etfDetail";
import { diffLine, diffSideOf, type DiffKind, type DiffPeriod, type DiffSide } from "@/lib/compareDiff";
import { detailItem, period } from "@/lib/etfCompareTestFixtures";

const S = "2026-10-12";
const E = "2026-11-09";
const REASON: Record<string, string> = { insufficient_history: "저장 이력 부족", no_start_row: "시작일 가격 없음", end_differs: "끝일 다름" };
const reasonText = (c: string | null) => (c ? (REASON[c] ?? c) : "자료 없음");

type St = "intraday" | "after_close" | "unknown" | null;

function side(p: DiffPeriod, state: St = "after_close", priceDate: string | null = p.end): DiffSide {
  return { period: p, priceState: state, priceDate };
}

const ok = (v: number, start = S, end = E) => period(v, start, end);
const missing = (reason = "insufficient_history") => period(null, null, E, "missing", reason);
const differs = (start: string, end: string) => ({ ...period(null, start, end, "period_differs", "start_differs") });

describe("차이 줄 — 차이를 적는 경우", () => {
  it("둘 다 마감 뒤 저장 · 같은 기간 = 보통 비교(후보가 높음 · 보유가 높음 · 같음)", () => {
    const a = diffLine("m1", side(ok(-3.2)), side(ok(14.55)), reasonText);
    expect(a).toEqual({ kind: "compared", text: "1개월(10/12 → 11/9 · 같은 기간): 후보가 17.75%p 높음", diffPctp: 17.75 });
    const b = diffLine("m3", side(ok(5.5, "2026-08-11")), side(ok(-1.25, "2026-08-11")), reasonText);
    expect(b.text).toBe("3개월(8/11 → 11/9 · 같은 기간): 보유가 6.75%p 높음");
    expect(b.diffPctp).toBe(-6.75);
    const c = diffLine("m1", side(ok(2)), side(ok(2)), reasonText);
    expect(c.text).toBe("1개월(10/12 → 11/9 · 같은 기간): 같음");
    expect(c.diffPctp).toBe(0);
  });

  it("보이는 두 숫자(소수 둘째 자리)끼리 뺀다 — -10.25% 와 -10.25% 로 보이면 같음", () => {
    const l = diffLine("m1", side(ok(-10.254)), side(ok(-10.246)), reasonText);
    expect(l.text).toBe("1개월(10/12 → 11/9 · 같은 기간): 같음");
    const m = diffLine("m1", side(ok(1.004)), side(ok(1.016)), reasonText);
    expect(m.text).toContain("후보가 0.02%p 높음");
  });

  it("둘 다 장중 저장값 = 같은 줄이지만 잠정 비교로 적는다", () => {
    const l = diffLine("m1", side(ok(1), "intraday"), side(ok(3.5), "intraday"), reasonText);
    expect(l.kind).toBe("provisional");
    expect(l.text).toBe("잠정 비교 · 1개월(10/12 → 11/9 · 같은 기간): 후보가 2.50%p 높음(두 쪽 모두 장중 저장값)");
  });

  it("3개월 시작일이 지난해면 연도까지 적는다", () => {
    const l = diffLine("m3", side(ok(1, "2025-10-13", "2026-01-12")), side(ok(2, "2025-10-13", "2026-01-12")), reasonText);
    expect(l.text).toBe("3개월(2025-10-13 → 1/12 · 같은 기간): 후보가 1.00%p 높음");
  });
});

describe("차이 줄 — 비교하지 않는 경우(사유 · 자료 상태 · 0 으로 채우지 않음)", () => {
  it("가격 상태가 다름(장중 ↔ 마감 뒤) = 양쪽 상태를 적는다", () => {
    const a = diffLine("m1", side(ok(1), "intraday"), side(ok(2), "after_close"), reasonText);
    expect(a).toEqual({ kind: "not_compared", text: "1개월(10/12 → 11/9): 가격 상태가 달라 비교하지 않음(보유 장중 · 후보 마감 뒤)", diffPctp: null });
    const b = diffLine("m1", side(ok(1), "after_close"), side(ok(2), "intraday"), reasonText);
    expect(b.text).toContain("(보유 마감 뒤 · 후보 장중)");
  });

  it("기간이 다름(둘 다 계산됐지만 시작일 · 끝일이 다름) = 양쪽 실제 날짜", () => {
    const a = diffLine("m1", side(ok(1, "2026-10-12")), side(ok(2, "2026-10-13")), reasonText);
    expect(a.text).toBe("1개월: 기간이 달라 비교하지 않음(보유 10/12 → 11/9 · 후보 10/13 → 11/9)");
    expect(a.kind).toBe("not_compared");
    const b = diffLine("m1", side(ok(1, S, "2026-11-07")), side(ok(2, S, E)), reasonText);
    expect(b.text).toBe("1개월: 기간이 달라 비교하지 않음(보유 10/12 → 11/7 · 후보 10/12 → 11/9)");
  });

  it("한쪽이 '기간 다름' 상태 = 그 쪽 실제 날짜(값은 쓰지 않음)", () => {
    const l = diffLine("m3", side(differs("2026-08-20", E)), side(ok(7.9, "2026-08-11")), reasonText);
    expect(l.text).toBe("3개월: 기간이 달라 비교하지 않음(보유 8/20 → 11/9 · 후보 8/11 → 11/9)");
    expect(l.diffPctp).toBeNull();
  });

  it("값 없음 = 그 쪽 · 사유(둘 다면 둘 다) · 0.00 을 만들지 않는다", () => {
    const a = diffLine("m1", side(missing()), side(ok(2)), reasonText);
    expect(a).toEqual({ kind: "not_compared", text: "1개월: 비교하지 않음 — 보유 값 없음 · 저장 이력 부족", diffPctp: null });
    expect(a.text).not.toContain("0.00");
    const b = diffLine("m1", side(missing()), side(missing("no_start_row")), reasonText);
    expect(b.text).toBe("1개월: 비교하지 않음 — 보유 값 없음 · 저장 이력 부족 / 후보 값 없음 · 시작일 가격 없음");
    // 상태는 ok 인데 값이 비어 있으면 계산된 0 으로 보지 않는다.
    const c = diffLine("m1", side(ok(1)), side({ ...ok(2), value: null }), reasonText);
    expect(c.text).toBe("1개월: 비교하지 않음 — 후보 값 없음 · 자료 없음");
  });

  it("가격 시점을 확인할 수 없음(상태 확인 필요 · 가격 자료 없음 · 가격 날짜 ≠ 기간 끝일)", () => {
    const a = diffLine("m1", side(ok(1), "unknown"), side(ok(2)), reasonText);
    expect(a.text).toBe("1개월(10/12 → 11/9): 비교하지 않음 — 가격 시점 확인 필요(보유)");
    const b = diffLine("m1", side(ok(1), null, null), side(ok(2), "unknown"), reasonText);
    expect(b.text).toContain("가격 시점 확인 필요(보유 · 후보)");
    const c = diffLine("m1", side(ok(1)), side(ok(2), "after_close", "2026-11-08"), reasonText);
    expect(c.text).toContain("가격 시점 확인 필요(후보)");
  });

  it("상세 수치 자체가 없음(고른 종목 없음 · 응답에 없음)", () => {
    expect(diffLine("m1", null, side(ok(2)), reasonText).text).toBe("1개월: 비교하지 않음 — 보유 상세 수치 없음");
    expect(diffLine("m3", null, null, reasonText).text).toBe("3개월: 비교하지 않음 — 보유 상세 수치 없음 / 후보 상세 수치 없음");
  });
});

describe("차이 줄 — 판정 순서(사유가 겹칠 때 앞 사유가 이긴다)", () => {
  const cases: [string, DiffSide, DiffSide, string][] = [
    ["값 없음 + 가격 상태 다름 → 값 없음", side(missing(), "intraday"), side(ok(2)), "보유 값 없음"],
    ["값 없음 + 기간 다름 → 값 없음", side(missing()), side(differs("2026-10-13", E)), "보유 값 없음"],
    ["기간 다름 + 가격 상태 다름 → 기간", side(ok(1, "2026-10-13"), "intraday"), side(ok(2)), "기간이 달라"],
    ["기간 다름 + 확인 필요 → 기간", side(ok(1, "2026-10-13"), "unknown"), side(ok(2)), "기간이 달라"],
    ["확인 필요 + 반대쪽 장중 → 확인 필요", side(ok(1), "unknown"), side(ok(2), "intraday"), "가격 시점 확인 필요"],
    ["가격 상태 다름 → 상태", side(ok(1), "intraday"), side(ok(2), "after_close"), "가격 상태가 달라"],
  ];
  it.each(cases)("%s", (_name, h, c, expected) => {
    const l = diffLine("m1", h, c, reasonText);
    expect(l.kind).toBe("not_compared");
    expect(l.diffPctp).toBeNull();
    expect(l.text).toContain(expected);
    expect(l.text).not.toMatch(/%p 높음|같음/);
  });
});

describe("diffSideOf — 상세 응답에서 기간 · 끝일 가격 상태를 꺼낸다", () => {
  it("end_price 가 없으면 상태 없음(확인 필요로 판정)", () => {
    const it0: EtfDetailItem = detailItem("A", { end_price: null });
    const s = diffSideOf(it0, "m1");
    expect(s).toMatchObject({ priceState: null, priceDate: null });
    expect(diffLine("m1", s, diffSideOf(detailItem("B"), "m1"), reasonText).text).toContain("가격 시점 확인 필요(보유)");
    expect(diffSideOf(null, "m3")).toBeNull();
  });

  it("고정 자료 두 종목(같은 기간 · 마감 뒤 저장) = 보통 비교", () => {
    const l = diffLine("m3", diffSideOf(detailItem("A"), "m3"), diffSideOf(detailItem("B", { m3: period(-2.5, "2026-08-11") }), "m3"), reasonText);
    expect(l.text).toBe("3개월(8/11 → 11/9 · 같은 기간): 후보가 3.00%p 높음");
  });
});

// ── 보완 2차 S3 — 새 줄(최근 5 · 20구간 · 고점 대비) ─────────────────────────────

const WINDOW_ROWS: ["w5" | "w20", string, string, string][] = [
  ["w5", "최근 5구간", "2026-11-02", "11/2"],
  ["w20", "최근 20구간", "2026-10-13", "10/13"],
];

describe.each(WINDOW_ROWS)("차이 줄 — %s(%s) · 1 · 3개월과 같은 규칙", (key, label, start, sd) => {
  const cases: [string, DiffSide, DiffSide, DiffKind, string][] = [
    ["같은 기간 · 둘 다 마감 뒤 = 후보가 높음", side(ok(-1.1, start)), side(ok(-0.82, start)), "compared", `${label}(${sd} → 11/9 · 같은 기간): 후보가 0.28%p 높음`],
    ["같은 기간 · 보유가 높음", side(ok(2, start)), side(ok(-0.5, start)), "compared", `${label}(${sd} → 11/9 · 같은 기간): 보유가 2.50%p 높음`],
    ["같은 기간 · 같음", side(ok(1.5, start)), side(ok(1.5, start)), "compared", `${label}(${sd} → 11/9 · 같은 기간): 같음`],
    [
      "둘 다 장중 = 잠정 비교",
      side(ok(1, start), "intraday"),
      side(ok(3.5, start), "intraday"),
      "provisional",
      `잠정 비교 · ${label}(${sd} → 11/9 · 같은 기간): 후보가 2.50%p 높음(두 쪽 모두 장중 저장값)`,
    ],
    ["시작일 다름", side(ok(1, start)), side(ok(2, "2026-10-01")), "not_compared", `${label}: 기간이 달라 비교하지 않음(보유 ${sd} → 11/9 · 후보 10/1 → 11/9)`],
    [
      "끝일 다름(보유 '기간 다름' 상태 · 값 비어 있음)",
      side(differs(start, "2026-11-07")),
      side(ok(2, start)),
      "not_compared",
      `${label}: 기간이 달라 비교하지 않음(보유 ${sd} → 11/7 · 후보 ${sd} → 11/9)`,
    ],
    [
      "가격 상태 다름",
      side(ok(1, start), "intraday"),
      side(ok(2, start), "after_close"),
      "not_compared",
      `${label}(${sd} → 11/9): 가격 상태가 달라 비교하지 않음(보유 장중 · 후보 마감 뒤)`,
    ],
    ["가격 시점 확인 필요", side(ok(1, start), "unknown"), side(ok(2, start)), "not_compared", `${label}(${sd} → 11/9): 비교하지 않음 — 가격 시점 확인 필요(보유)`],
    ["값 없음", side(missing()), side(ok(2, start)), "not_compared", `${label}: 비교하지 않음 — 보유 값 없음 · 저장 이력 부족`],
  ];
  it.each(cases)("%s", (_n, h, c, kind, text) => {
    const l = diffLine(key, h, c, reasonText);
    expect(l.text).toBe(text);
    expect(l.kind).toBe(kind);
    if (kind === "not_compared") expect(l.diffPctp).toBeNull();
    else expect(l.diffPctp).not.toBeNull();
  });
});

// 고점 대비 칸(20저장일 창). 기본 = 창 10/13 → 11/9 · 계산됨.
const DW = "2026-10-13";
function ddp(
  value: number | null,
  start: string | null = DW,
  end: string | null = E,
  status: DiffPeriod["status"] = "ok",
  reason: string | null = null,
): DiffPeriod {
  return { status, value, start, end, reason };
}
// KODEX 200 창과 다른 창(서버 상태 '기간 다름' · 그 종목 창 값은 있음 · 가격 날짜 = 창 끝일).
const stale = (v: number, start = "2026-10-10") => side(ddp(v, start, "2026-11-07", "period_differs", "end_differs"), "after_close", "2026-11-07");
const DDR = "고점 대비(20저장일 10/13 → 11/9 · 같은 기간)";

describe("차이 줄 — 고점 대비(두 종목 20저장일 창 시작 · 끝일과 확인된 가격 상태가 같을 때만 · Q-S6)", () => {
  const cases: [string, DiffSide, DiffSide, DiffKind, string, number | null][] = [
    ["후보 하락폭이 작음(보유 -6.20 · 후보 -0.82)", side(ddp(-6.2)), side(ddp(-0.82)), "compared", `${DDR}: 후보 하락폭이 5.38%p 작음`, 5.38],
    ["후보 하락폭이 큼(보유 -1.00 · 후보 -4.50)", side(ddp(-1)), side(ddp(-4.5)), "compared", `${DDR}: 후보 하락폭이 3.50%p 큼`, -3.5],
    ["하락폭 같음(둘 다 고점 = 0.00)", side(ddp(0)), side(ddp(0)), "compared", `${DDR}: 하락폭 같음`, 0],
    ["보이는 값(소수 둘째 자리)끼리 — -3.004 · -2.996 은 -3.00 · -3.00 이라 같음", side(ddp(-3.004)), side(ddp(-2.996)), "compared", `${DDR}: 하락폭 같음`, 0],
    [
      "둘 다 장중 = 잠정 비교",
      side(ddp(-3), "intraday"),
      side(ddp(-1), "intraday"),
      "provisional",
      `잠정 비교 · ${DDR}: 후보 하락폭이 2.00%p 작음(두 쪽 모두 장중 저장값)`,
      2,
    ],
    [
      "창 시작일 다름",
      side(ddp(-3, "2026-10-10")),
      side(ddp(-1)),
      "not_compared",
      "고점 대비: 기간이 달라 비교하지 않음(보유 20저장일 10/10 → 11/9 · 후보 20저장일 10/13 → 11/9)",
      null,
    ],
    [
      "창 끝일 다름(보유는 KODEX 200 창과 달라 '기간 다름' · 값은 있음)",
      stale(-3),
      side(ddp(-1)),
      "not_compared",
      "고점 대비: 기간이 달라 비교하지 않음(보유 20저장일 10/10 → 11/7 · 후보 20저장일 10/13 → 11/9)",
      null,
    ],
    ["두 창이 같으면 KODEX 200 창과 달라도 비교(둘 다 '기간 다름' 상태)", stale(-3), stale(-1), "compared", "고점 대비(20저장일 10/10 → 11/7 · 같은 기간): 후보 하락폭이 2.00%p 작음", 2],
    ["둘 다 '기간 다름'이어도 창 시작일이 다르면 비교하지 않음", stale(-3), stale(-1, "2026-10-09"), "not_compared", "고점 대비: 기간이 달라 비교하지 않음(보유 20저장일 10/10 → 11/7 · 후보 20저장일 10/9 → 11/7)", null],
    [
      "가격 상태 다름",
      side(ddp(-3), "intraday"),
      side(ddp(-1), "after_close"),
      "not_compared",
      "고점 대비(20저장일 10/13 → 11/9): 가격 상태가 달라 비교하지 않음(보유 장중 · 후보 마감 뒤)",
      null,
    ],
    [
      "가격 시점 확인 필요(가격 날짜 ≠ 창 끝일)",
      side(ddp(-3)),
      side(ddp(-1), "after_close", "2026-11-08"),
      "not_compared",
      "고점 대비(20저장일 10/13 → 11/9): 비교하지 않음 — 가격 시점 확인 필요(후보)",
      null,
    ],
    [
      "값 없음(저장 이력 부족)",
      side(ddp(-3)),
      side(ddp(null, null, null, "missing", "insufficient_history"), "after_close", E),
      "not_compared",
      "고점 대비: 비교하지 않음 — 후보 값 없음 · 저장 이력 부족",
      null,
    ],
    [
      "'기간 다름'인데 값이 비어 있음 = 값 없음(0 으로 채우지 않음)",
      side(ddp(null, "2026-10-10", "2026-11-07", "period_differs", "end_differs")),
      side(ddp(-1)),
      "not_compared",
      "고점 대비: 비교하지 않음 — 보유 값 없음 · 끝일 다름",
      null,
    ],
  ];
  it.each(cases)("%s", (_n, h, c, kind, text, diff) => {
    const l = diffLine("drawdown", h, c, reasonText);
    expect(l).toEqual({ kind, text, diffPctp: diff });
    expect(l.text).not.toContain("높음");
  });

  const order: [string, DiffSide, DiffSide, string][] = [
    ["값 없음 + 창 다름 → 값 없음", side(ddp(null, null, null, "missing", "insufficient_history")), side(ddp(-1, "2026-10-10")), "보유 값 없음"],
    ["창 다름 + 가격 상태 다름 → 기간", side(ddp(-3, "2026-10-10"), "intraday"), side(ddp(-1)), "기간이 달라"],
    ["창 다름 + 확인 필요 → 기간", side(ddp(-3, "2026-10-10"), "unknown"), side(ddp(-1)), "기간이 달라"],
    ["확인 필요 + 반대쪽 장중 → 확인 필요", side(ddp(-3), "unknown"), side(ddp(-1), "intraday"), "가격 시점 확인 필요"],
    ["가격 상태 다름 → 상태", side(ddp(-3), "after_close"), side(ddp(-1), "intraday"), "가격 상태가 달라"],
  ];
  it.each(order)("판정 순서 — %s", (_n, h, c, expected) => {
    const l = diffLine("drawdown", h, c, reasonText);
    expect(l.kind).toBe("not_compared");
    expect(l.diffPctp).toBeNull();
    expect(l.text).toContain(expected);
    expect(l.text).not.toMatch(/%p (작음|큼)|같음/);
  });
});

describe("diffSideOf — 최근 5 · 20구간 · 고점 대비도 상세 응답 그대로", () => {
  it("고정 자료에서 칸을 그대로 꺼내 같은 규칙으로 비교한다", () => {
    const a = detailItem("A");
    expect(diffSideOf(a, "w5")?.period).toBe(a.w5);
    expect(diffSideOf(a, "w20")?.period).toBe(a.w20);
    expect(diffSideOf(a, "drawdown")).toEqual({ period: a.drawdown, priceState: "after_close", priceDate: E });
    const b = detailItem("B", { drawdown: { ...a.drawdown, value: -1.25 }, w5: period(0.3, "2026-11-02") });
    expect(diffLine("drawdown", diffSideOf(a, "drawdown"), diffSideOf(b, "drawdown"), reasonText).text).toBe(`${DDR}: 후보 하락폭이 1.75%p 작음`);
    expect(diffLine("w5", diffSideOf(a, "w5"), diffSideOf(b, "w5"), reasonText).text).toBe("최근 5구간(11/2 → 11/9 · 같은 기간): 후보가 1.50%p 높음");
  });
});
