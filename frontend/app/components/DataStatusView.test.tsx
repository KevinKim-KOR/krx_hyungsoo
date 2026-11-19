// POC6-33(PLAN §4 D7 · 판정 Q43 · Q45) — 「데이터 상태」 화면 시험.
// @/lib/api 의 fetchNavDiscountLatest 만 바꿔 끼운다(실제 네트워크 · 운영 DB 미사용).
// 고정 자료의 코드 · 이름 · 가격은 모두 합성값(TEST01 · 'ETF 가' …).
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import type { NavDiscountItem, NavDiscountLatestResponse } from "@/lib/api";
import type { EtfDetailItem } from "@/lib/api/etfDetail";

const fetchNavDiscountLatest = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchNavDiscountLatest: (...a: unknown[]) => fetchNavDiscountLatest(...a),
  };
});

import DataStatusView from "./DataStatusView";
import { ApiRequestError } from "@/lib/api";
import { navText } from "./workbench/DetailNumbers";
import {
  NAV_TERM,
  discountFlagClass,
  discountFlagLabel,
  discountPctText,
  discountRateColor,
  navDateCell,
  navDateLabel,
  navSourceLabel,
  navStatusLabel,
} from "@/lib/navLabels";

// ── 고정 자료 ─────────────────────────────────────────────────────────────
function row(over: Partial<NavDiscountItem>): NavDiscountItem {
  return {
    ticker: "TEST00",
    name: "ETF 가",
    nav: 10000,
    market_price: 10000,
    discount_rate_pct: 0,
    flag: null,
    asof: "2026-11-18",
    source: "naver_etf_item_list",
    status: "ok",
    message: null,
    ...over,
  };
}

// 수집됨 9 · 확인 불가 1 · 기타 2(이전 목록 재사용 1 + 사전 밖 1) = 12.
const ITEMS: NavDiscountItem[] = [
  row({ ticker: "TEST01", name: "ETF 가", discount_rate_pct: 2.99 }),
  row({ ticker: "TEST02", name: "ETF 나", discount_rate_pct: 3, flag: "discount_check_needed" }),
  row({ ticker: "TEST03", name: "ETF 다", discount_rate_pct: 4.99, flag: "discount_check_needed" }),
  row({ ticker: "TEST04", name: "ETF 라", discount_rate_pct: 5, flag: "discount_warning" }),
  row({ ticker: "TEST05", name: "ETF 마", discount_rate_pct: -3, flag: "discount_check_needed" }),
  row({ ticker: "TEST06", name: "ETF 바", discount_rate_pct: -5, flag: "discount_warning" }),
  row({ ticker: "TEST07", name: "ETF 사", discount_rate_pct: -2.99 }),
  row({ ticker: "TEST08", name: "ETF 아", discount_rate_pct: 1, status: "partial", message: "stale cache reused" }),
  row({
    ticker: "TEST09",
    name: "ETF 자",
    nav: null,
    discount_rate_pct: null,
    status: "unavailable",
    message: "nav or market_price missing",
  }),
  row({ ticker: "TEST10", name: "ETF 차", discount_rate_pct: 0.5, status: "weird_status", source: "other_src" }),
  row({ ticker: "TEST11", name: "ETF 카", discount_rate_pct: 0.1, asof: "2026-06-23" }),
  row({ ticker: "TEST12", name: "ETF 타", discount_rate_pct: 0.2, source: "" }),
];

function response(over: Partial<NavDiscountLatestResponse> = {}): NavDiscountLatestResponse {
  return {
    status: "ok",
    asof: "2026-11-18",
    source: null,
    // 백엔드 failed_count 는 partial 을 빼고 센다(1) — 화면 '기타'(2)는 이 값을 쓰지 않는다.
    summary: { total_count: 12, ok_count: 9, unavailable_count: 1, failed_count: 1 },
    items: ITEMS,
    ...over,
  };
}

const COL = { code: 0, name: 1, nav: 2, price: 3, rate: 4, date: 5, source: 6, status: 7 } as const;

function cellsOf(ticker: string): HTMLElement[] {
  const tr = screen.getByText(ticker).closest("tr");
  if (!tr) throw new Error(`행 없음: ${ticker}`);
  return within(tr as HTMLElement).getAllByRole("cell");
}

function bodyRowCount(): number {
  const table = screen.queryByRole("table");
  if (!table) return 0;
  return within(table).getAllByRole("row").length - 1; // 머리 줄 제외
}

function statusSelect(): HTMLSelectElement {
  return screen.getAllByRole("combobox")[0] as HTMLSelectElement;
}

async function renderReady(over: Partial<NavDiscountLatestResponse> = {}) {
  fetchNavDiscountLatest.mockResolvedValue(response(over));
  const view = render(<DataStatusView />);
  await screen.findByRole("table");
  return view;
}

// [자세히](details)를 뺀 화면 글자.
function visibleText(container: HTMLElement): string {
  const copy = container.cloneNode(true) as HTMLElement;
  copy.querySelectorAll("details").forEach((d) => d.remove());
  return copy.textContent ?? "";
}

beforeEach(() => {
  fetchNavDiscountLatest.mockReset();
});

describe("공용 사전(lib/navLabels)", () => {
  it("수집 상태 — ok · partial · unavailable · 사전 밖", () => {
    expect(navStatusLabel("ok")).toBe("수집됨");
    expect(navStatusLabel("partial")).toBe("이전 목록 재사용");
    expect(navStatusLabel("unavailable")).toBe("확인 불가");
    for (const v of ["OK", "failed", "", null, undefined, "toString"]) {
      expect(navStatusLabel(v)).toBe("상태 확인 필요");
    }
  });

  it("출처 — 네이버 · 사전 밖 = 기타 출처 · 값 없음 = '-'", () => {
    expect(navSourceLabel("naver_etf_item_list")).toBe("네이버");
    expect(navSourceLabel("other_src")).toBe("기타 출처");
    expect(navSourceLabel("toString")).toBe("기타 출처");
    expect(navSourceLabel("")).toBe("-");
    expect(navSourceLabel(null)).toBe("-");
  });

  it("괴리율 표시 글자 · class · 숫자 색(3 · 5 경계 · 음수)", () => {
    expect(discountFlagLabel("discount_check_needed")).toBe("괴리 확인 필요(3% 이상)");
    expect(discountFlagLabel("discount_warning")).toBe("괴리 주의(5% 이상)");
    expect(discountFlagLabel(null)).toBeNull();
    expect(discountFlagLabel("other_flag")).toBeNull();
    expect(discountFlagClass("discount_warning")).toBe("nav-flag");
    expect(discountFlagClass("discount_check_needed")).toBe("nav-flag");
    expect(discountFlagClass(null)).toBe("");
    const cases: [number | null, string][] = [
      [null, "var(--muted)"],
      [0, "var(--fg)"],
      [2.99, "var(--fg)"],
      [-2.99, "var(--fg)"],
      [3, "var(--warn)"],
      [-3, "var(--warn)"],
      [4.99, "var(--warn)"],
      [-4.99, "var(--warn)"],
      [5, "var(--danger)"],
      [-5, "var(--danger)"],
    ];
    for (const [v, color] of cases) expect(discountRateColor(v)).toBe(color);
  });

  it("날짜 칸 — 이전 목록 재사용 행만 '재저장일'", () => {
    expect(navDateLabel("partial")).toBe("재저장일");
    expect(navDateLabel("ok")).toBe("기준일");
    expect(navDateCell("partial", "2026-11-18")).toBe("재저장일 2026-11-18");
    expect(navDateCell("ok", "2026-11-18")).toBe("2026-11-18");
    expect(navDateCell("unavailable", "2026-11-18")).toBe("2026-11-18");
    expect(navDateCell("partial", "")).toBe("-");
  });

  it("ETF 비교하기(DetailNumbers)도 같은 괴리율 표시 글자를 쓴다", () => {
    const base = { status: "ok", nav: 10000, market_price: 10500, asof: "2026-11-18" };
    const item = (nav: Record<string, unknown>) => ({ nav: { ...base, ...nav } }) as unknown as EtfDetailItem;
    expect(navText(item({ discount_rate_pct: 5, flag: "discount_warning" }))).toContain("· 괴리 주의(5% 이상)");
    expect(navText(item({ discount_rate_pct: 3, flag: "discount_check_needed" }))).toContain(
      "· 괴리 확인 필요(3% 이상)",
    );
    expect(navText(item({ discount_rate_pct: 1, flag: null }))).not.toContain("괴리");
  });
});

describe("「데이터 상태」 화면", () => {
  it("제목 · 첫 NAV 표기 · 표 머리가 한국어", async () => {
    await renderReady();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("데이터 상태");
    expect(screen.getByText(new RegExp(`전체 ETF의 ${NAV_TERM.replace(/[()]/g, "\\$&")}`))).toBeInTheDocument();
    const heads = within(screen.getByRole("table"))
      .getAllByRole("columnheader")
      .map((h) => h.textContent);
    expect(heads).toEqual(["코드", "ETF명", "NAV", "시장가", "괴리율", "기준일", "출처", "수집 상태"]);
  });

  it("수집 상태 · 출처 · 날짜 칸 — 수집됨 · 이전 목록 재사용(재저장일) · 확인 불가 · 사전 밖", async () => {
    await renderReady();
    const ok = cellsOf("TEST01");
    expect(ok[COL.status]).toHaveTextContent(/^수집됨$/);
    expect(ok[COL.source]).toHaveTextContent(/^네이버$/);
    expect(ok[COL.date]).toHaveTextContent(/^2026-11-18$/);

    const partial = cellsOf("TEST08");
    expect(partial[COL.status]).toHaveTextContent(/^이전 목록 재사용$/);
    expect(partial[COL.date]).toHaveTextContent(/^재저장일 2026-11-18$/);

    const na = cellsOf("TEST09");
    expect(na[COL.status]).toHaveTextContent(/^확인 불가$/);
    expect(na[COL.nav]).toHaveTextContent(/^-$/);
    expect(na[COL.rate]).toHaveTextContent(/^-$/);

    const unknown = cellsOf("TEST10");
    expect(unknown[COL.status]).toHaveTextContent(/^상태 확인 필요$/);
    expect(unknown[COL.source]).toHaveTextContent(/^기타 출처$/);

    // 각 행은 그 행의 날짜(요약의 가장 최근 기준일과 다를 수 있음).
    expect(cellsOf("TEST11")[COL.date]).toHaveTextContent(/^2026-06-23$/);
    // 출처 값 없음 → '-'.
    expect(cellsOf("TEST12")[COL.source]).toHaveTextContent(/^-$/);
  });

  it("반올림해 0 인 괴리율은 부호 없이 '0.00%'(「확인 근거」 NAV 묶음과 같은 함수) · 재저장일 칸은 한 줄", async () => {
    await renderReady({
      items: [
        row({ ticker: "TEST21", name: "ETF 음영", discount_rate_pct: -0.004 }),
        row({ ticker: "TEST22", name: "ETF 양영", discount_rate_pct: 0.004 }),
        row({ ticker: "TEST23", name: "ETF 재저장", discount_rate_pct: 0.01, status: "partial" }),
      ],
      summary: { total_count: 3, ok_count: 2, unavailable_count: 0, failed_count: 0 },
    });
    expect(cellsOf("TEST21")[COL.rate]).toHaveTextContent(/^0\.00%$/);
    expect(cellsOf("TEST22")[COL.rate]).toHaveTextContent(/^0\.00%$/);
    expect(cellsOf("TEST23")[COL.rate]).toHaveTextContent(/^\+0\.01%$/);
    expect(discountPctText(-0.004)).toBe("0.00%");
    const date = cellsOf("TEST23")[COL.date];
    expect(date).toHaveTextContent(/^재저장일 2026-11-18$/);
    expect(date.style.whiteSpace).toBe("nowrap");
  });

  it("괴리율 표시 — 3% · 5% 경계와 음수 · 숫자 색 · 표시 글자", async () => {
    await renderReady();
    const cases: [string, string, string | null, string][] = [
      ["TEST01", "+2.99%", null, "var(--fg)"],
      ["TEST02", "+3.00%", "괴리 확인 필요(3% 이상)", "var(--warn)"],
      ["TEST03", "+4.99%", "괴리 확인 필요(3% 이상)", "var(--warn)"],
      ["TEST04", "+5.00%", "괴리 주의(5% 이상)", "var(--danger)"],
      ["TEST05", "-3.00%", "괴리 확인 필요(3% 이상)", "var(--warn)"],
      ["TEST06", "-5.00%", "괴리 주의(5% 이상)", "var(--danger)"],
      ["TEST07", "-2.99%", null, "var(--fg)"],
      ["TEST09", "-", null, "var(--muted)"],
    ];
    for (const [ticker, pctText, flag, color] of cases) {
      const cell = cellsOf(ticker)[COL.rate];
      expect(cell.textContent?.startsWith(pctText), `${ticker} 괴리율 글자`).toBe(true);
      expect(cell.getAttribute("style") ?? "", `${ticker} 숫자 색`).toContain(color);
      const flagSpan = cell.querySelector(".nav-flag");
      if (flag == null) {
        expect(flagSpan, `${ticker} 표시 없음`).toBeNull();
        expect(cell.textContent).toBe(pctText);
      } else {
        expect(flagSpan?.textContent, `${ticker} 표시 글자`).toBe(flag);
      }
    }
  });

  it("요약 '기타' 건수 = 고르기 '기타' 결과 건수(이전 목록 재사용 포함 · 같은 전체 목록 · 같은 조건)", async () => {
    await renderReady();
    const summary = screen.getByTestId("ds-summary");
    expect(summary).toHaveTextContent("전체 12건 · 수집됨 9 · 확인 불가 1 · 기타 2 ·");
    const other = screen.getByTestId("ds-count-other").textContent;
    // 백엔드 failed_count(1 · partial 제외)가 아니라 화면이 전체 목록에서 센 값.
    expect(other).toBe("2");
    expect(screen.getByTestId("ds-count-filtered").textContent).toBe("12");
    expect(bodyRowCount()).toBe(12);

    fireEvent.change(statusSelect(), { target: { value: "other" } });
    expect(bodyRowCount()).toBe(Number(other));
    expect(screen.getByTestId("ds-count-filtered").textContent).toBe(other);
    expect(screen.getByText("TEST08")).toBeInTheDocument();
    expect(screen.getByText("TEST10")).toBeInTheDocument();
    // 요약 건수(전체 · 수집됨 · 확인 불가 · 기타)는 고르기와 무관하게 전체 목록 기준 그대로.
    expect(screen.getByTestId("ds-summary")).toHaveTextContent("전체 12건 · 수집됨 9 · 확인 불가 1 · 기타 2 ·");

    fireEvent.change(statusSelect(), { target: { value: "ok" } });
    expect(bodyRowCount()).toBe(9);
    fireEvent.change(statusSelect(), { target: { value: "unavailable" } });
    expect(bodyRowCount()).toBe(1);
    expect(screen.getByText("TEST09")).toBeInTheDocument();
    expect(screen.getByTestId("ds-summary")).toHaveTextContent("전체 12건 · 수집됨 9 · 확인 불가 1 · 기타 2 ·");
  });

  it("조회 옵션 라벨(검색 · 수집 상태 · 정렬)은 한 줄", async () => {
    await renderReady();
    const labels = Array.from(document.querySelectorAll(".ds-controls label")) as HTMLElement[];
    expect(labels.map((l) => l.firstChild?.textContent?.trim())).toEqual(["검색", "수집 상태", "정렬"]);
    for (const l of labels) expect(l.style.whiteSpace).toBe("nowrap");
  });

  it("고르기 선택지 · 정렬 선택지 · 검색 안내가 한국어", async () => {
    await renderReady();
    const statusOptions = within(statusSelect())
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(statusOptions).toEqual(["전체", "수집됨", "확인 불가", "기타"]);
    const sortOptions = within(screen.getAllByRole("combobox")[1])
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(sortOptions).toEqual(["괴리율 절대값", "괴리율(부호 포함)", "코드"]);
    expect(screen.getByPlaceholderText("코드 / ETF명")).toBeInTheDocument();
  });

  it("요약 — 날짜 · 출처(둘 이상이면 '-' · 하나면 사전 글자)", async () => {
    // ITEMS 에는 최댓값 날짜(2026-11-18)의 이전 목록 재사용 행(TEST08)이 있어 '목록 날짜(재저장일 포함)'.
    const view = await renderReady();
    expect(screen.getByTestId("ds-summary")).toHaveTextContent(
      "가장 최근 목록 날짜(재저장일 포함) 2026-11-18 · 출처 - ·",
    );
    view.unmount();
    await renderReady({ source: "naver_etf_item_list" });
    expect(screen.getByTestId("ds-summary")).toHaveTextContent(
      "가장 최근 목록 날짜(재저장일 포함) 2026-11-18 · 출처 네이버 ·",
    );
  });

  // RESULT 판정 §3 I-9 — 값은 응답 asof 그대로 · 그 날짜에 이전 목록 재사용 행이 있을 때만 라벨이 바뀐다.
  describe("요약 날짜 라벨(I-9)", () => {
    const NEW_LABEL = "가장 최근 목록 날짜(재저장일 포함)";
    const OLD_LABEL = "가장 최근 기준일";

    it("최댓값 날짜에 이전 목록 재사용 행 → '가장 최근 목록 날짜(재저장일 포함)' · 고르기 · 검색으로 그 행이 숨어도 그대로", async () => {
      await renderReady({
        items: [
          row({ ticker: "TEST31", name: "ETF 하나", discount_rate_pct: 1 }),
          row({ ticker: "TEST32", name: "ETF 둘", discount_rate_pct: 0.5, status: "partial" }),
          row({ ticker: "TEST33", name: "ETF 셋", discount_rate_pct: 0.2, asof: "2026-11-17" }),
        ],
        summary: { total_count: 3, ok_count: 2, unavailable_count: 0, failed_count: 0 },
      });
      const summary = screen.getByTestId("ds-summary");
      expect(summary).toHaveTextContent(`· ${NEW_LABEL} 2026-11-18 · 출처`);
      expect(summary).not.toHaveTextContent(OLD_LABEL);
      // 행은 '재저장일 YYYY-MM-DD' 그대로.
      expect(cellsOf("TEST32")[COL.date]).toHaveTextContent(/^재저장일 2026-11-18$/);

      fireEvent.change(statusSelect(), { target: { value: "ok" } });
      expect(screen.queryByText("TEST32")).toBeNull();
      expect(screen.getByTestId("ds-summary")).toHaveTextContent(`· ${NEW_LABEL} 2026-11-18 · 출처`);

      fireEvent.change(statusSelect(), { target: { value: "all" } });
      fireEvent.change(screen.getByPlaceholderText("코드 / ETF명"), { target: { value: "TEST31" } });
      expect(screen.queryByText("TEST32")).toBeNull();
      expect(screen.getByTestId("ds-summary")).toHaveTextContent(`· ${NEW_LABEL} 2026-11-18 · 출처`);
    });

    it("이전 목록 재사용 행이 더 옛 날짜에만 → '가장 최근 기준일'(확인 불가 · 사전 밖 상태가 최댓값 날짜에 있어도)", async () => {
      await renderReady({
        items: [
          row({ ticker: "TEST41", name: "ETF 하나", discount_rate_pct: 1 }),
          row({ ticker: "TEST42", name: "ETF 둘", discount_rate_pct: 0.5, status: "partial", asof: "2026-11-17" }),
          row({ ticker: "TEST43", name: "ETF 셋", nav: null, discount_rate_pct: null, status: "unavailable" }),
          row({ ticker: "TEST44", name: "ETF 넷", discount_rate_pct: 0.3, status: "weird_status" }),
        ],
        summary: { total_count: 4, ok_count: 1, unavailable_count: 1, failed_count: 1 },
      });
      const summary = screen.getByTestId("ds-summary");
      expect(summary).toHaveTextContent(`· ${OLD_LABEL} 2026-11-18 · 출처`);
      expect(summary).not.toHaveTextContent(NEW_LABEL);
      expect(cellsOf("TEST42")[COL.date]).toHaveTextContent(/^재저장일 2026-11-17$/);
    });

    it("이전 목록 재사용 행이 없으면 '가장 최근 기준일'", async () => {
      await renderReady({ items: ITEMS.filter((it) => it.status !== "partial") });
      const summary = screen.getByTestId("ds-summary");
      expect(summary).toHaveTextContent(`· ${OLD_LABEL} 2026-11-18 · 출처`);
      expect(summary).not.toHaveTextContent(NEW_LABEL);
    });

    it("표시 200건 밖의 이전 목록 재사용 행도 센다(응답 items 전체)", async () => {
      const many = Array.from({ length: 210 }, (_, i) =>
        row({ ticker: `TEST${String(100 + i)}`, name: `ETF ${i}`, discount_rate_pct: 1 }),
      );
      // 괴리율 절대값 내림차순(기본 정렬)에서 맨 끝 → 표시 200건 밖.
      const reused = row({ ticker: "TEST999", name: "ETF 끝", discount_rate_pct: 0, status: "partial" });
      await renderReady({
        items: [...many, reused],
        summary: { total_count: 211, ok_count: 210, unavailable_count: 0, failed_count: 0 },
      });
      expect(bodyRowCount()).toBe(200);
      expect(screen.queryByText("TEST999")).toBeNull();
      const summary = screen.getByTestId("ds-summary");
      expect(summary).toHaveTextContent(`· ${NEW_LABEL} 2026-11-18 · 출처`);
      expect(summary).not.toHaveTextContent(OLD_LABEL);
    });
  });

  it("원문(기계값)은 [자세히] 안에만 · 사전 밖 원문 · 건수", async () => {
    const { container } = await renderReady({
      items: [...ITEMS, row({ ticker: "TEST13", name: "ETF 파", discount_rate_pct: 3.5, flag: "other_flag" })],
      summary: { total_count: 13, ok_count: 10, unavailable_count: 1, failed_count: 1 },
    });
    const shown = visibleText(container);
    for (const raw of [
      "naver_etf_item_list",
      "partial",
      "unavailable",
      "discount_check_needed",
      "discount_warning",
      "weird_status",
      "other_src",
      "other_flag",
      "stale cache reused",
      "Data Status",
      "asof",
      "source",
      "ticker",
      "status",
      "SQLite",
      "universe",
      "Naver",
    ]) {
      expect(shown, `화면에 '${raw}'`).not.toContain(raw);
    }
    // 영어 낱말은 NAV · ETF 와 합성 코드(TEST..)뿐.
    const words = new Set(shown.match(/[A-Za-z]+\d*/g) ?? []);
    for (const w of words) expect(["NAV", "ETF"].includes(w) || /^TEST\d+$/.test(w), `영어 '${w}'`).toBe(true);

    // 사전 밖 표시 = 표 칸에는 없음(숫자 · 색은 그대로).
    const unknownFlagCell = cellsOf("TEST13")[COL.rate];
    expect(unknownFlagCell.textContent).toBe("+3.50%");
    expect(unknownFlagCell.getAttribute("style") ?? "").toContain("var(--warn)");

    const raw = screen.getByTestId("ds-raw");
    expect(raw).toHaveTextContent("출처 원문 other_src · 1건");
    expect(raw).toHaveTextContent("수집 상태 원문 weird_status · 1건");
    expect(raw).toHaveTextContent("괴리율 표시 원문 other_flag · 1건");
    // 이전 목록 재사용 · 확인 불가 · 네이버는 사전 안 → 원문 목록에 없음.
    expect(raw).not.toHaveTextContent("partial");
    expect(raw).not.toHaveTextContent("naver_etf_item_list");
  });

  it("사전 밖 값이 없으면 [자세히] 원문 칸이 없다 · 고르기 결과가 없어도 원문 칸은 남는다", async () => {
    const plain = ITEMS.filter((it) => it.ticker !== "TEST10");
    const view = await renderReady({ items: plain });
    expect(screen.queryByTestId("ds-raw")).toBeNull();
    view.unmount();

    await renderReady();
    fireEvent.change(screen.getByPlaceholderText("코드 / ETF명"), { target: { value: "없는 이름" } });
    expect(screen.getByText("필터 조건에 맞는 항목이 없습니다.")).toBeInTheDocument();
    expect(screen.getByTestId("ds-raw")).toHaveTextContent("수집 상태 원문 weird_status · 1건");
  });

  it("빈 자료 카드 · 불러오기 실패 카드가 쉬운 한국어(원문은 [자세히])", async () => {
    fetchNavDiscountLatest.mockResolvedValue(
      response({
        status: "empty",
        asof: null,
        items: [],
        summary: { total_count: 0, ok_count: 0, unavailable_count: 0, failed_count: 0 },
      }),
    );
    const empty = render(<DataStatusView />);
    expect(await screen.findByText("저장된 NAV 자료가 없습니다")).toBeInTheDocument();
    expect(visibleText(empty.container)).not.toMatch(/universe|Naver/);
    empty.unmount();

    fetchNavDiscountLatest.mockRejectedValue(new ApiRequestError("Internal Server Error", 500, null));
    const failed = render(<DataStatusView />);
    expect(await screen.findByText(/서버가 오류로 답해 자료를 불러오지 못했습니다/)).toBeInTheDocument();
    expect(visibleText(failed.container)).not.toContain("HTTP");
    expect(failed.container.querySelector("details")).toHaveTextContent("요청 실패(HTTP 500): Internal Server Error");
  });
});
