// POC6-28 — 「ETF 비교하기」 문장 · 정렬 · 순서 순수 함수(판정 2026-11-11 §3 ~ §5 · PLAN §3-6 · §3-7 · §5).
import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  aiCopyText,
  basisLine,
  bothRanks,
  candidateLinkText,
  commonText,
  comparable,
  criterionOf,
  endPriceText,
  kodexSameNote,
  pointReason,
  priceStateLine,
  priceStateShort,
  reasonText,
  regimeView,
  sectorLine,
  sortLine,
  sortRows,
} from "./etfCompare";
import { BOTTOM, TOP, link, row, summaryOk } from "./etfCompareTestFixtures";
import {
  __resetEtfCompareCondition,
  getSavedBasis,
  getScreenCondition,
  LEGACY_TODAY_BASIS_KEY,
  readSavedBasis,
  saveScreenBasis,
  SCREEN_IDS,
  setScreenCondition,
  storageKeyOf,
} from "./etfCompareCondition";
import {
  ETF_COMPARE_KEY_PREFIX,
  HOLDINGS_INVALIDATION_KEYS,
  MARKET_INVALIDATION_KEYS,
  PRICE_SERIES_KEY_PREFIX,
} from "./api/dashboardKeys";

const tickers = (rows: { ticker: string }[]) => rows.map((r) => r.ticker);

describe("[ETF 순위] 정렬 — 비교 가능 먼저 · 기간 다름 · 값 없음은 양방향 모두 뒤(판정 §5 · Q10 (b))", () => {
  it("선정 순서는 선정 순위 그대로", () => {
    const shuffled = [BOTTOM[2], BOTTOM[0], BOTTOM[1]];
    expect(tickers(sortRows(shuffled, "sel", "asc"))).toEqual(["B00001", "B00002", "B00003"]);
  });

  it("3개월 — 기간 다름 행은 낮은 순 · 높은 순 모두 맨 뒤", () => {
    expect(tickers(sortRows(BOTTOM, "three_month", "asc"))).toEqual(["B00001", "B00002", "B00003"]);
    expect(tickers(sortRows(BOTTOM, "three_month", "desc"))).toEqual(["B00002", "B00001", "B00003"]);
  });

  it("고점 대비 — 0.00% 는 유효값으로 정렬되고 값 없음은 양방향 뒤", () => {
    const zero = criterionOf(BOTTOM[1], "drawdown");
    expect(zero.value).toBe(0);
    expect(comparable(zero)).toBe(true);
    expect(tickers(sortRows(BOTTOM, "drawdown", "desc"))).toEqual(["B00002", "B00001", "B00003"]);
    expect(tickers(sortRows(BOTTOM, "drawdown", "asc"))).toEqual(["B00001", "B00002", "B00003"]);
  });

  it("동률은 선정 순위 · 비교 불가끼리도 선정 순위", () => {
    const a = row({ rank: 2, ticker: "A", name: "a", value: -5 });
    const b = row({ rank: 1, ticker: "B", name: "b", value: -5 });
    const c = row({ rank: 4, ticker: "C", name: "c", value: -1, same: null });
    const d = row({ rank: 3, ticker: "D", name: "d", value: -2, same: null });
    expect(tickers(sortRows([a, b], "one_month", "asc"))).toEqual(["B", "A"]);
    expect(tickers(sortRows([c, d, a], "same", "desc"))).toEqual(["A", "D", "C"]);
  });

  it("사유 문장 — 기간 다름(실제 구간)과 값 없음(사유)을 나눈다", () => {
    expect(reasonText(criterionOf(BOTTOM[2], "three_month"))).toBe("기간 다름 · 9/15 → 11/9");
    expect(reasonText(criterionOf(BOTTOM[2], "drawdown"))).toBe("값 없음 · 20저장일 부족");
    const noKodex = row({ rank: 1, ticker: "X", name: "x", value: -3, same: null });
    expect(reasonText(criterionOf(noKodex, "same"))).toBe("값 없음 · KODEX 200 시작일 가격 없음");
  });

  it("기준 한 줄 — 목록을 고른 기준과 정렬 기준을 나눠 적는다", () => {
    const s = summaryOk();
    expect(sortLine(s, "bottom", "three_month", "asc", s.bottom)).toBe(
      "1개월 하위 3 · 정렬 1개월 선정 · 3개월 수익률 표시 순서(낮은 순) · 8/11 → 11/9 · 비교 가능 2 · 기간 다름 · 값 없음 1(뒤)",
    );
    expect(sortLine(s, "top", "sel", "desc", s.top)).toBe("1개월 상위 3 · 정렬 선정 순서(1개월 높은 순) · 10/12 → 11/9");
    expect(kodexSameNote(s)).toBe(
      "같은 1개월 구간(10/12 → 11/9) KODEX 200 -22.64% · 비교 가능한 행에서는 1개월과 순서가 같습니다",
    );
  });
});

describe("가격 시점(판정 §4 · 종가 단정 안 함)", () => {
  it("한 종목 문장 3상태", () => {
    expect(endPriceText({ date: "2026-11-10", state: "intraday", fetched_at_kst: "2026-11-10T13:18:02+09:00" })).toBe(
      "장중 저장값 · 11/10 13:18 저장",
    );
    expect(endPriceText({ date: "2026-11-09", state: "after_close", fetched_at_kst: "2026-11-10T13:18:02+09:00" })).toBe(
      "마감 뒤 저장(11/10 13:18 저장)",
    );
    expect(endPriceText({ date: "2026-11-09", state: "unknown", fetched_at_kst: null })).toBe(
      "PC 저장 가격 · 마감값 확인 필요",
    );
  });

  it("여러 종목 — 장중이 하나라도 있으면 '장중 저장값 포함 · 잠정'", () => {
    const base = summaryOk().price_state;
    expect(
      priceStateLine({
        ...base,
        end_date: "2026-11-10",
        intraday_count: 964,
        after_close_count: 0,
        provisional: true,
        intraday_fetched_min: "2026-11-10T13:17:11+09:00",
        intraday_fetched_max: "2026-11-10T13:21:00+09:00",
      }),
    ).toBe("11/10 가격 = 장중 저장값 포함 · 잠정(장중 964개 · 11/10 13:17 ~ 13:21 저장)");
    expect(priceStateLine(base)).toBe("11/9 가격 = 마감 뒤 저장(11/10 13:17 ~ 13:21 저장)");
    expect(priceStateLine({ ...base, after_close_count: 0, unknown_count: 961 })).toBe(
      "11/9 가격 = PC 저장 가격 · 마감값 확인 필요",
    );
  });
});

describe("시장 국면 — 표시 순서와 강조만(PLAN §5)", () => {
  const s = summaryOk();
  it("하락장 = 보유 겹침 → 하위 → 상위 · 보유는 하락 판정 먼저", () => {
    const v = regimeView(s.regime, s.end_date, []);
    expect(v.order).toEqual(["holdings", "bottom", "top"]);
    expect(v.holdingsDeclineFirst).toBe(true);
    expect(v.line).toBe("시장 판정(국내시장 · KODEX 200 · 11/9): 하락장 · 22거래일째 — 보유와 겹친 항목 · 하위권부터 보여 줍니다");
  });
  it("상승장 = 상위 먼저 · 서로 다른 지수 수 강조", () => {
    const v = regimeView({ ...s.regime, code: "bull", label: "상승장" }, s.end_date, []);
    expect(v.order).toEqual(["top", "bottom", "holdings"]);
    expect(v.emphasis).toBe("distinct_index");
  });
  it("보합장 = 상·하위에 함께 나온 업종이 있으면 먼저", () => {
    const n = { ...s.regime, code: "neutral", label: "보합장" };
    expect(regimeView(n, s.end_date, ["반도체"]).order).toEqual(["both", "top", "bottom", "holdings"]);
    expect(regimeView(n, s.end_date, []).order).toEqual(["top", "bottom", "holdings"]);
  });
  it("판정불가 · 기준일 다름 = '시장 판정 확인 필요' · 기본 순서", () => {
    for (const r of [
      { ...s.regime, code: "unavailable", label: "판정불가" },
      { ...s.regime, same_end_date: false },
    ]) {
      const v = regimeView(r, s.end_date, []);
      expect(v.ok).toBe(false);
      expect(v.order).toEqual(["top", "bottom", "holdings"]);
      expect(v.line).toContain("시장 판정 확인 필요");
    }
  });
  it("장중 저장값 판정은 '잠정'을 밝힌다", () => {
    const r = { ...s.regime, price: { date: "2026-11-10", state: "intraday" as const, fetched_at_kst: "2026-11-10T13:18:02+09:00" } };
    expect(regimeView(r, s.end_date, []).line).toContain("하락장 · 22거래일째 (잠정 · 장중 저장값 기준)");
  });
});

describe("보유 연결(판정 §4)", () => {
  const s = summaryOk();
  it("점검 사유 = 직접 하위권 + 그 기간 수익률 음수일 때만", () => {
    const br = { start: "2026-10-12", end: "2026-11-09" };
    expect(pointReason(link({ ticker: "A", side: "bottom", side_rank: 27, basis_return: { value: -36.41, ...br } }), s)).toBe(
      "후보 하위 27위 · 1개월 -36.41%(10/12 → 11/9)",
    );
    expect(pointReason(link({ ticker: "A", side: "bottom", side_rank: 27, basis_return: { value: 0, ...br } }), s)).toBeNull();
    expect(pointReason(link({ ticker: "A", side: "bottom", side_rank: 27, basis_return: { value: 1.2, ...br } }), s)).toBeNull();
    expect(pointReason(link({ ticker: "A", side: "top", side_rank: 3, basis_return: { value: -1, ...br } }), s)).toBeNull();
    const intraday = link({
      ticker: "A",
      side: "bottom",
      side_rank: 2,
      basis_return: { value: -3, ...br },
      end_price: { date: "2026-11-10", state: "intraday", fetched_at_kst: "2026-11-10T13:18:02+09:00" },
    });
    expect(pointReason(intraday, s)).toContain("· 장중 저장값 기준");
  });

  it("후보 조회 기간 연결 — 상·하위 밖은 위치 숫자 없이 '상·하위 30 밖'", () => {
    expect(candidateLinkText(s.holdings.items[0], s)).toBe("1개월 -44.92% · 10/12 → 11/9 · 하위 1위");
    expect(candidateLinkText(s.holdings.items[1], s)).toBe("1개월 +3.20% · 10/12 → 11/9 · 상·하위 30 밖");
    expect(candidateLinkText(s.holdings.items[2], s)).toBe("개별 주식 — ETF 비교 목록 대상 아님");
    expect(candidateLinkText(link({ ticker: "Z", in_population: false, out_reason: "filter_excluded", basis_return: null }), s)).toContain(
      "제외 조건",
    );
  });
});

describe("섹터 요약 문장(판정 §3)", () => {
  const s = summaryOk();
  it("사업군 분류 n/30 · 반복된 업종이 없으면 '공통 업종 확인 어려움'", () => {
    expect(sectorLine(s.overview.top)).toBe("사업군 분류 1/3 · 공통 업종 확인 어려움");
    expect(sectorLine(s.overview.bottom)).toBe("사업군 분류 2/3 · 반복된 업종 먼저");
  });

  it("공통 구성종목 — 표본 0개와 겹침 0건을 다른 문장으로", () => {
    const g = s.groups.bottom[0];
    const c = g.constituents;
    const noSample = commonText({ ...g, constituents: { ...c, status: "no_sample", etf_with_data: 0, asof_min: null, asof_max: null } });
    const noOverlap = commonText({ ...g, constituents: { ...c, status: "no_overlap", common: [] } });
    expect(noSample).toBe("구성 자료 있는 ETF 0/2 — 공통 종목 표본 없음");
    expect(noOverlap).toBe("구성 자료 있는 ETF 2/2 · 각 비중 상위 10종목 · 구성 기준일 10/2 — 2개 이상 ETF에 나온 종목 0건");
    expect(commonText(g)).toContain("숫자 = 그 종목이 나온 ETF 수");
  });

  it("기준 줄 — 실제 시작 · 끝 · 제외 조건 · 모집단 · 기간이 달라 뺀 수 · 표시 수", () => {
    expect(basisLine(s)).toBe(
      "1개월 · 10/12 → 11/9 · 인버스 · 레버리지 · 합성 · 선물 제외 · 비교한 ETF 961개 · 기간이 달라 뺀 17개 · 상·하위 각 3개 표시",
    );
  });

  it("AI 복사 = 목록 전체 · 구성 자료 없는 범위 · 세 갈래 질문 · 금액 없음", () => {
    const text = aiCopyText(s, "bottom");
    expect(text.split("\n")[0]).toBe("[같은 기간 ETF 목록 · 1개월 하위 3개 · 10/12 → 11/9]");
    for (const r of BOTTOM) expect(text).toContain(`${r.rank}. ${r.name}(${r.ticker})`);
    expect(text).toContain("구성(10/2 · 비중 상위 2): 주성엔지니어링 8.1%, 마이크론 6.0%");
    expect(text).toContain("구성 자료 없음 1개: 늦은 상장");
    expect(text).toContain("(1) 여러 ETF에 반복해서 나타나는 근거");
    expect(text).toContain("(2) ETF 이름에서 유추한 가설 — 추정이라고 밝혀 주세요");
    expect(text).toContain("(3) 판단하기에 부족한 자료");
    expect(aiCopyText(s, "top")).toContain(`1. ${TOP[0].name}`);
    expect(text).not.toMatch(/평가|매입|손익/);
  });
});

describe("[검증자 r1 F3] 상·하위 공통 — 후보 연결 문장 · AI 복사문", () => {
  it("보유가 상·하위에 모두 들면 두 순위를 함께 · 복사문에도 표시", () => {
    const x = row({ rank: 1, ticker: "X00001", name: "단일 ETF", value: -3 });
    const s = { ...summaryOk(), top: [x], bottom: [x], in_both: ["X00001"] };
    const l = link({ ticker: "X00001", side: "bottom", side_rank: 1, top_rank: 1, basis_return: { value: -3, start: "2026-10-12", end: "2026-11-09" } });
    expect(candidateLinkText(l, s)).toBe("1개월 -3.00% · 10/12 → 11/9 · 하위 1위 · 상위 1위(상·하위 공통)");
    expect(aiCopyText(s, "top")).toContain("1. 단일 ETF(X00001) · 상·하위 공통 · 기초지수");
    expect(bothRanks(s, "X00001")).toEqual({ top: 1, bottom: 1 });
    expect(bothRanks(summaryOk(), "B00001")).toBeNull();
  });
});

describe("독립 검토 정정", () => {
  it("시장 갱신은 요약 · 종목 차트를 지우고, 보유 변경은 요약만 지운다", () => {
    expect(MARKET_INVALIDATION_KEYS).toContain(ETF_COMPARE_KEY_PREFIX);
    expect(MARKET_INVALIDATION_KEYS).toContain(PRICE_SERIES_KEY_PREFIX);
    expect(HOLDINGS_INVALIDATION_KEYS).toContain(ETF_COMPARE_KEY_PREFIX);
    expect(HOLDINGS_INVALIDATION_KEYS).not.toContain(PRICE_SERIES_KEY_PREFIX);
  });

  it("KODEX 200 비교 구간을 못 정하면 '값 없음' 사유 · 여러 종목 상태 짧은 이름", () => {
    const v = { status: "missing" as const, value: null, unit: "%" as const, start: null, end: null, reason: "kodex_window_unknown" };
    expect(reasonText(v)).toBe("값 없음 · KODEX 200 비교 구간 확인 불가");
    const p = summaryOk().price_state;
    expect(priceStateShort(p)).toBe("마감 뒤 저장");
    expect(priceStateShort({ ...p, intraday_count: 3 })).toBe("장중 저장값 포함 · 잠정");
    expect(priceStateShort({ ...p, after_close_count: 0 })).toBe("PC 저장 가격 · 마감값 확인 필요");
  });
});

// POC6-29(판정 Q1 · Q2 · Q11 · Q13) — 다섯 화면이 조건 · 저장된 기본 기간을 따로 쓴다.
describe("화면별 조회 기준 · 기본 기간 저장", () => {
  beforeEach(() => {
    __resetEtfCompareCondition();
    window.localStorage.clear();
  });

  it("기본 = 1개월 · 4종 제외 · 바꾸면 그 화면만 · 새로 고치면(저장 안 했으면) 기본값", () => {
    for (const id of SCREEN_IDS) expect(getScreenCondition(id).basis).toBe("one_month");
    setScreenCondition("candidates", { ...getScreenCondition("candidates"), basis: "three_month" });
    setScreenCondition("sector", { basis: "daily", filters: { ...getScreenCondition("sector").filters, exclude_futures: false } });
    expect(getScreenCondition("candidates").basis).toBe("three_month");
    expect(getScreenCondition("sector")).toEqual({
      basis: "daily",
      filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: false },
    });
    for (const id of ["today", "holdings", "compare"] as const) expect(getScreenCondition(id).basis).toBe("one_month");
    __resetEtfCompareCondition();
    expect(getScreenCondition("candidates").basis).toBe("one_month");
    expect(getScreenCondition("sector").filters.exclude_futures).toBe(true);
  });

  it("오늘 점검(today)은 제외 4종 고정 — 기간만 바뀐다", () => {
    setScreenCondition("today", { basis: "three_month", filters: { exclude_inverse: false, exclude_leveraged: false, exclude_synthetic: false, exclude_futures: false } });
    expect(getScreenCondition("today")).toEqual({
      basis: "three_month",
      filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true },
    });
  });

  it("[이 기준을 기본으로] = 그 화면 키에만 저장 · 다시 열면 그 기간 · 제외 조건은 저장 안 함", () => {
    setScreenCondition("candidates", { basis: "three_month", filters: { ...getScreenCondition("candidates").filters, exclude_inverse: false } });
    expect(saveScreenBasis("candidates")).toBe(true);
    expect(window.localStorage.getItem(storageKeyOf("candidates"))).toBe("three_month");
    for (const id of ["today", "holdings", "sector", "compare"] as const) expect(window.localStorage.getItem(storageKeyOf(id))).toBeNull();
    __resetEtfCompareCondition();
    expect(getScreenCondition("candidates")).toEqual({
      basis: "three_month",
      filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true },
    });
    expect(getSavedBasis("candidates")).toBe("three_month");
    expect(getScreenCondition("sector").basis).toBe("one_month");
  });

  it("판정 Q13 — 예전 「요즘 잘 오르는 ETF」 저장 기간은 today 만 한 번 이어받는다", () => {
    window.localStorage.setItem(LEGACY_TODAY_BASIS_KEY, "three_month");
    expect(getScreenCondition("today").basis).toBe("three_month");
    expect(window.localStorage.getItem(storageKeyOf("today"))).toBe("three_month"); // 옮겨 둠
    for (const id of ["holdings", "sector", "candidates", "compare"] as const) expect(getScreenCondition(id).basis).toBe("one_month");
    // 이어받은 뒤에는 today 자기 저장값이 우선(예전 값이 바뀌어도 따라가지 않음).
    window.localStorage.setItem(LEGACY_TODAY_BASIS_KEY, "daily");
    __resetEtfCompareCondition();
    expect(getScreenCondition("today").basis).toBe("three_month");
  });

  it("예전 저장값이 알 수 없는 값이면 이어받지 않는다 · 저장소를 못 쓰면 저장 실패(조회는 그대로)", () => {
    window.localStorage.setItem(LEGACY_TODAY_BASIS_KEY, "weekly");
    expect(getScreenCondition("today").basis).toBe("one_month");
    expect(window.localStorage.getItem(storageKeyOf("today"))).toBeNull();
    const orig = Storage.prototype.setItem;
    Storage.prototype.setItem = () => {
      throw new Error("blocked");
    };
    try {
      setScreenCondition("holdings", { ...getScreenCondition("holdings"), basis: "daily" });
      expect(saveScreenBasis("holdings")).toBe(false);
      expect(getScreenCondition("holdings").basis).toBe("daily");
      expect(getSavedBasis("holdings")).toBeNull();
    } finally {
      Storage.prototype.setItem = orig;
    }
  });
});

describe("저장 기간 상태 넷 — 저장됨 · 없음 · 허용 밖 · 읽기 실패(검증자 r1 F2 · 예전 C 판정 · PLAN §3-1)", () => {
  const blocked = () => {
    throw new DOMException("blocked", "SecurityError");
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    __resetEtfCompareCondition();
    window.localStorage.clear();
  });

  it("읽기 예외 = read_failed(없음과 구분) · 지금 조회는 1개월 · 저장 기간 null", () => {
    window.localStorage.setItem(storageKeyOf("sector"), "three_month");
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(blocked);
    expect(readSavedBasis("sector")).toEqual({ basis: null, status: "read_failed" });
    expect(readSavedBasis("today")).toEqual({ basis: null, status: "read_failed" });
    expect(getScreenCondition("sector").basis).toBe("one_month");
    expect(getSavedBasis("sector")).toBeNull();
  });

  it("today — 자기 칸은 비었고 예전 칸 읽기만 예외여도 read_failed", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation((k: string) => {
      if (k === LEGACY_TODAY_BASIS_KEY) blocked();
      return null;
    });
    expect(readSavedBasis("today")).toEqual({ basis: null, status: "read_failed" });
  });

  it("자기 칸이 허용 밖 값 = invalid · 읽으면서 고치지 않음 · today 도 이때는 예전 값을 이어받지 않음", () => {
    window.localStorage.setItem(storageKeyOf("today"), "weekly");
    window.localStorage.setItem(LEGACY_TODAY_BASIS_KEY, "three_month");
    window.localStorage.setItem(storageKeyOf("holdings"), "");
    expect(readSavedBasis("today")).toEqual({ basis: null, status: "invalid" });
    expect(window.localStorage.getItem(storageKeyOf("today"))).toBe("weekly");
    expect(getScreenCondition("today").basis).toBe("one_month");
    expect(readSavedBasis("holdings")).toEqual({ basis: null, status: "invalid" });
    expect(readSavedBasis("compare")).toEqual({ basis: null, status: "none" });
  });

  it("today 예전 값 옮겨 적기만 실패 = 읽은 예전 값을 저장됨으로 씀 · 다음 읽기 때 다시 옮김", () => {
    window.localStorage.setItem(LEGACY_TODAY_BASIS_KEY, "three_month");
    const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(blocked);
    expect(readSavedBasis("today")).toEqual({ basis: "three_month", status: "saved" });
    expect(window.localStorage.getItem(storageKeyOf("today"))).toBeNull();
    set.mockRestore();
    expect(readSavedBasis("today")).toEqual({ basis: "three_month", status: "saved" });
    expect(window.localStorage.getItem(storageKeyOf("today"))).toBe("three_month");
  });

  it("저장 = 다시 읽어 같은 값일 때만 성공(조용히 버려지면 실패) · 읽기 실패였던 화면도 저장에 성공하면 저장됨", () => {
    const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => undefined);
    setScreenCondition("candidates", { ...getScreenCondition("candidates"), basis: "daily" });
    expect(saveScreenBasis("candidates")).toBe(false);
    expect(getSavedBasis("candidates")).toBeNull();
    set.mockRestore();
    const get = vi.spyOn(Storage.prototype, "getItem").mockImplementation(blocked);
    expect(getScreenCondition("sector").basis).toBe("one_month"); // 읽기 실패로 시작
    get.mockRestore();
    setScreenCondition("sector", { ...getScreenCondition("sector"), basis: "three_month" });
    expect(saveScreenBasis("sector")).toBe(true);
    expect(getSavedBasis("sector")).toBe("three_month");
  });
});
