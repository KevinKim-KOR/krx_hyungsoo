// POC6-33(PLAN §4 D7 · 판정 Q43 · Q45) — 「데이터 상태」 화면 시험.
// POC6-34(PLAN §2-2 N1 ~ N8 · 판정 Q7 ~ Q9) — 이름 「ETF NAV·괴리율 조회」 · [저장 자료 다시 읽기] · 표시 범위 줄.
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

describe("「ETF NAV·괴리율 조회」 화면", () => {
  it("제목 · 첫 NAV 표기(= h1 · I-28) · 부제 · 표 머리가 한국어", async () => {
    const { container } = await renderReady();
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1.textContent).toBe("ETF 순자산가치(NAV)·괴리율 조회");
    expect(h1.textContent).toBe(`ETF ${NAV_TERM}·괴리율 조회`);
    expect(container.textContent).not.toContain("데이터 상태");
    // 화면 글자의 첫 'NAV' = h1 의 '순자산가치(NAV)'(POC6-33 첫 표기 규칙 · 부제에는 NAV 가 없다).
    const shown = visibleText(container);
    expect(shown.indexOf("NAV")).toBe(shown.indexOf(NAV_TERM) + NAV_TERM.indexOf("NAV"));
    expect(shown.indexOf(NAV_TERM)).toBe(shown.indexOf("ETF 순자산가치(NAV)·괴리율 조회") + "ETF ".length);
    expect(container.querySelector("p.subtitle")?.textContent).toBe(
      "전체 ETF 의 저장 자료에서 수집 상태 · 큰 괴리를 찾아보는 조회용 표 — 저장된 자료 기준(이 화면은 새로 받지 않음).",
    );
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
    // 영어 낱말은 NAV · ETF · PC(POC6-34 안내 띠 · 기준일 뜻 줄 · I-31)와 합성 코드(TEST..)뿐.
    const words = new Set(shown.match(/[A-Za-z]+\d*/g) ?? []);
    for (const w of words) expect(["NAV", "ETF", "PC"].includes(w) || /^TEST\d+$/.test(w), `영어 '${w}'`).toBe(true);

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

// POC6-34(PLAN §2-2 N3 · N4 · N5 · N7 · 판정 Q8 · Q9 · I-29 ~ I-33) — 저장 자료 다시 읽기 ↔ 새 자료 경로 · 표시 범위.
// 고정 자료는 합성값(TEST.. · 'ETF n'). 건수(1,212 · 211 · 201 · 200)는 표시 범위 경계를 보기 위한 합성 행 수.
const RELOAD = "저장 자료 다시 읽기";

// 괴리율이 행마다 달라(i × 0.01) 정렬 순서가 하나로 정해진다 · ticker = TEST{base + i}.
function manyRows(n: number, base = 100, over: Partial<NavDiscountItem> = {}): NavDiscountItem[] {
  return Array.from({ length: n }, (_, i) =>
    row({ ticker: `TEST${base + i}`, name: `ETF ${base + i}`, discount_rate_pct: i * 0.01, ...over }),
  );
}

function summaryOf(items: NavDiscountItem[]): NavDiscountLatestResponse["summary"] {
  const ok = items.filter((it) => it.status === "ok").length;
  const un = items.filter((it) => it.status === "unavailable").length;
  return { total_count: items.length, ok_count: ok, unavailable_count: un, failed_count: 0 };
}

async function renderItems(items: NavDiscountItem[]) {
  return renderReady({ items, summary: summaryOf(items) });
}

function rangeText(): string {
  return screen.getByTestId("ds-range").textContent ?? "";
}

function norm(t: string | null | undefined): string {
  return (t ?? "").replace(/\s+/g, " ").trim();
}

describe("POC6-34 — 저장 자료 다시 읽기 · 새 자료 경로 · 표시 범위", () => {
  it("버튼 이름 = [저장 자료 다시 읽기] · 누르면 같은 GET 을 한 번 더 부른다(새로 받지 않음) · 옛 이름 없음", async () => {
    const { container } = await renderReady();
    expect(fetchNavDiscountLatest).toHaveBeenCalledTimes(1);
    const btn = screen.getByRole("button", { name: RELOAD });
    expect(screen.queryByRole("button", { name: "다시 불러오기" })).toBeNull();
    expect(container.textContent).not.toContain("다시 불러오기");
    fireEvent.click(btn);
    expect(fetchNavDiscountLatest).toHaveBeenCalledTimes(2);
    expect(fetchNavDiscountLatest).toHaveBeenLastCalledWith();
    await screen.findByRole("table");
  });

  it("불러오기 실패 문구 전문 · 문구 안 버튼 이름 = 실제 버튼 이름 · 그 버튼으로 다시 읽으면 표가 나온다", async () => {
    fetchNavDiscountLatest.mockRejectedValueOnce(new ApiRequestError("Internal Server Error", 500, null));
    fetchNavDiscountLatest.mockResolvedValueOnce(response());
    const { container } = render(<DataStatusView />);
    const msg = await screen.findByText(/로 다시 시도하세요\.$/);
    expect(msg.textContent).toBe("서버가 오류로 답해 자료를 불러오지 못했습니다. [저장 자료 다시 읽기]로 다시 시도하세요.");
    const named = /\[(.+?)\]로 다시 시도하세요/.exec(msg.textContent ?? "")?.[1];
    const btn = screen.getByRole("button", { name: RELOAD });
    expect(named).toBe(btn.textContent);
    expect(container.textContent).not.toContain("다시 불러오기");
    fireEvent.click(btn);
    expect(await screen.findByRole("table")).toBeInTheDocument();
    expect(fetchNavDiscountLatest).toHaveBeenCalledTimes(2);
  });

  it("안내 띠 — 저장 자료 다시 읽기 = PC 저장값만 · 새 자료 = 「오늘의 투자 점검」 [최신 자료 갱신] · 6시간 안에는 NAV 를 다시 받지 않음", async () => {
    await renderReady();
    expect(norm(screen.getByTestId("ds-banner").textContent)).toBe(
      "[보조 화면 — 자료 조회] 네이버 ETF 목록을 받아 PC 에 저장한 전체 ETF 의 NAV · 시장가 · 괴리율을 한곳에서 검색 · 정렬합니다. " +
        "매수 · 매도 · 교체 판단 화면이 아닙니다. [저장 자료 다시 읽기]는 PC 에 저장된 값만 다시 읽습니다(새로 받지 않음). " +
        "새 자료는 「오늘의 투자 점검」의 [최신 자료 갱신]으로 받습니다. " +
        "마지막 시장 갱신이 성공한 뒤 6시간 안에는 [최신 자료 갱신]을 눌러도 NAV 를 다시 받지 않습니다.",
    );
    // 안내 띠의 버튼 이름 = 실제 버튼 이름.
    expect(screen.getByTestId("ds-banner").textContent).toContain(
      `[${screen.getByRole("button", { name: RELOAD }).textContent}]`,
    );
  });

  it("표 도움말 셋째 줄 — 기준일 = PC 가 목록 갱신을 시작한 날짜 · 이전 목록 재사용 행은 '재저장일'", async () => {
    const { container } = await renderReady();
    const lines = Array.from(container.querySelectorAll(".ds-meaning > div")).map((d) => norm(d.textContent));
    expect(lines).toHaveLength(3);
    expect(lines[2]).toBe(
      "기준일 = PC 가 목록 갱신을 시작한 날짜(원자료의 산정일은 이 화면에서 확인할 수 없음) · 이전 목록 재사용 행은 ‘재저장일’로 표시",
    );
  });

  it("판정 §3 — 한 표에서 '수집됨' + '괴리 주의' 행 · 이전 목록 재사용 행(재저장일) · 범위 줄", async () => {
    await renderReady();
    const both = cellsOf("TEST04");
    expect(both[COL.status]).toHaveTextContent(/^수집됨$/);
    expect(both[COL.rate].querySelector(".nav-flag")?.textContent).toBe("괴리 주의(5% 이상)");
    expect(both[COL.date]).toHaveTextContent(/^2026-11-18$/);
    const reused = cellsOf("TEST08");
    expect(reused[COL.status]).toHaveTextContent(/^이전 목록 재사용$/);
    expect(reused[COL.date]).toHaveTextContent(/^재저장일 2026-11-18$/);
    expect(rangeText()).toBe("전체 12건 · 필터 결과 12건 · 표에 표시 12건");
    expect(screen.queryByTestId("ds-narrow-hint")).toBeNull();
  });

  it("범위 줄은 표 카드 h2 바로 아래 · 표보다 위", async () => {
    await renderReady();
    const range = screen.getByTestId("ds-range");
    const h2 = screen.getByRole("heading", { level: 2, name: "전체 ETF NAV / 괴리율" });
    expect(h2.nextElementSibling).toBe(range);
    expect(range.compareDocumentPosition(screen.getByRole("table")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("1,212건 응답 → '전체 1,212건 · 필터 결과 1,212건 · 표에 표시 200건 (지금 정렬의 앞 200건)' · 표 아래 검색 · 필터 안내 · 옛 안내 없음", async () => {
    const { container } = await renderItems(manyRows(1212, 1000));
    expect(bodyRowCount()).toBe(200);
    expect(rangeText()).toBe("전체 1,212건 · 필터 결과 1,212건 · 표에 표시 200건 (지금 정렬의 앞 200건)");
    expect(screen.getByTestId("ds-narrow-hint").textContent).toBe(
      "필터 · 검색을 좁히면 앞 200건 밖의 ETF 도 표에서 볼 수 있습니다.",
    );
    // 안내는 표 아래.
    expect(
      screen.getByRole("table").compareDocumentPosition(screen.getByTestId("ds-narrow-hint")) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(container.textContent).not.toContain("상위 200건만 표시");
    expect(container.textContent).not.toContain("(전체 ");
    // 「조회 옵션」 요약 줄은 그대로(N8).
    expect(screen.getByTestId("ds-summary")).toHaveTextContent("전체 1,212건 · 수집됨 1,212 · 확인 불가 0 · 기타 0 ·");
    expect(screen.getByTestId("ds-count-filtered").textContent).toBe("1,212");
  });

  it.each([
    [199, false],
    [200, false],
    [201, true],
    [211, true],
  ])("필터 결과 %i건 — 표에 표시 = 실제 그린 행 · 앞 200건 안내는 200건을 넘을 때만(%s)", async (n, over) => {
    await renderItems(manyRows(n));
    const shownRows = bodyRowCount();
    expect(shownRows).toBe(Math.min(n, 200));
    const suffix = over ? " (지금 정렬의 앞 200건)" : "";
    expect(rangeText()).toBe(`전체 ${n}건 · 필터 결과 ${n}건 · 표에 표시 ${shownRows}건${suffix}`);
    if (over) expect(screen.getByTestId("ds-narrow-hint")).toBeInTheDocument();
    else expect(screen.queryByTestId("ds-narrow-hint")).toBeNull();
  });

  it("검색으로 좁힘 → 표에 표시 = 필터 결과 · 앞 200건 문구 · 표 아래 안내 없음 · 전체는 응답 건수 그대로", async () => {
    await renderItems(manyRows(211));
    fireEvent.change(screen.getByPlaceholderText("코드 / ETF명"), { target: { value: "TEST10" } });
    // TEST100 ~ TEST109 = 10건.
    expect(bodyRowCount()).toBe(10);
    expect(rangeText()).toBe("전체 211건 · 필터 결과 10건 · 표에 표시 10건");
    expect(screen.queryByTestId("ds-narrow-hint")).toBeNull();
  });

  it("수집 상태 고르기도 필터 결과에 든다 — 수집됨 211 + 확인 불가 3", async () => {
    const items = [...manyRows(211), ...manyRows(3, 900, { status: "unavailable", nav: null, discount_rate_pct: null })];
    await renderItems(items);
    expect(rangeText()).toBe("전체 214건 · 필터 결과 214건 · 표에 표시 200건 (지금 정렬의 앞 200건)");
    fireEvent.change(statusSelect(), { target: { value: "ok" } });
    expect(rangeText()).toBe("전체 214건 · 필터 결과 211건 · 표에 표시 200건 (지금 정렬의 앞 200건)");
    fireEvent.change(statusSelect(), { target: { value: "unavailable" } });
    expect(bodyRowCount()).toBe(3);
    expect(rangeText()).toBe("전체 214건 · 필터 결과 3건 · 표에 표시 3건");
    expect(screen.queryByTestId("ds-narrow-hint")).toBeNull();
  });

  it("'지금 정렬의 앞 200건' = 지금 정렬 순서의 앞 200행(내림차순 ↔ 오름차순)", async () => {
    await renderItems(manyRows(211));
    // 기본 = 괴리율 절대값 내림차순 → 가장 작은 11건(TEST100 ~ TEST110)이 빠진다.
    expect(screen.queryByText("TEST110")).toBeNull();
    expect(screen.getByText("TEST111")).toBeInTheDocument();
    expect(screen.getByText("TEST310")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "↓ 내림차순" }));
    // 오름차순 → 가장 큰 11건(TEST300 ~ TEST310)이 빠진다.
    expect(screen.getByText("TEST100")).toBeInTheDocument();
    expect(screen.getByText("TEST299")).toBeInTheDocument();
    expect(screen.queryByText("TEST300")).toBeNull();
    expect(bodyRowCount()).toBe(200);
    expect(rangeText()).toBe("전체 211건 · 필터 결과 211건 · 표에 표시 200건 (지금 정렬의 앞 200건)");
  });

  it("고른 결과 0건이면 표 · 범위 줄 없음(안내 한 줄 그대로) · 요약 줄 필터 결과 0건", async () => {
    await renderReady();
    fireEvent.change(screen.getByPlaceholderText("코드 / ETF명"), { target: { value: "없는 이름" } });
    expect(screen.getByText("필터 조건에 맞는 항목이 없습니다.")).toBeInTheDocument();
    expect(screen.queryByTestId("ds-range")).toBeNull();
    expect(screen.getByTestId("ds-count-filtered").textContent).toBe("0");
  });
});
