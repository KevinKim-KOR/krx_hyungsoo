// POC5-26 — 「요즘 잘 오르는 ETF」 기본 조회 기준(설계 §2 · §3 · §4 · §6 · PLAN §3 · 판정 §2 · §3 · §4).
// 첫 조회 · 명시 저장 · 임시 변경 · 실패 · 메뉴 재진입 · 지금 조건 전달 · POC5-12 다시 읽기 보존.
import { StrictMode } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, fireEvent, within } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";
import type { MarketBasis, MarketOrder } from "@/lib/api";
import { MARKET_BASIS_PREF_KEY } from "@/lib/marketBasisPreference";
import { loadAISessionsDraft } from "@/lib/aiSessionsDraft";

const fetchMarketTopnLatest = vi.fn();
const postMarketRefresh = vi.fn();
const fetchMarketRefreshStatus = vi.fn();
const fetchEnrichedHoldings = vi.fn();
const actualApi = vi.hoisted(() => ({}) as Record<string, unknown>);
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  Object.assign(actualApi, actual);
  return {
    ...actual,
    fetchMarketTopnLatest: (...a: unknown[]) => fetchMarketTopnLatest(...a),
    postMarketRefresh: (...a: unknown[]) => postMarketRefresh(...a),
    fetchMarketRefreshStatus: (...a: unknown[]) => fetchMarketRefreshStatus(...a),
    fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
  };
});

import MarketDiscoveryView from "./MarketDiscoveryView";
import { BASIS_SAVE_FAILED } from "./MarketBasisDefaultRow";

// 기준마다 다른 후보 1개 — 화면 · 전달이 어느 응답을 쓰는지 이름으로 구분한다.
const TICKER: Record<MarketBasis, string> = {
  daily: "100001",
  one_month: "100002",
  three_month: "100003",
};
const NAME: Record<MarketBasis, string> = {
  daily: "일간 순위 ETF",
  one_month: "1개월 순위 ETF",
  three_month: "3개월 순위 ETF",
};

function resp(basis: MarketBasis = "one_month", order: MarketOrder = "desc", empty = false) {
  return {
    status: "ok",
    asof: "2026-10-19",
    n: 10,
    basis,
    order,
    filters: {
      exclude_inverse: true,
      exclude_leveraged: true,
      exclude_synthetic: true,
      exclude_futures: true,
    },
    candidates: empty
      ? []
      : [
      {
        rank: 1,
        ticker: TICKER[basis],
        name: NAME[basis],
        tags: [],
        returns: {
          daily: { return_pct: 1.1 },
          one_month: { return_pct: 2.2 },
          three_month: { return_pct: 3.3 },
        },
      },
    ],
    daily_topn: [],
    one_month_topn: [],
    three_month_topn: [],
    market_context: null,
  };
}

type TopnOpts = { basis?: MarketBasis; order?: MarketOrder; excludeLeveraged?: boolean };
const topnOpts = () => fetchMarketTopnLatest.mock.calls.map((c) => (c[1] ?? {}) as TopnOpts);
const basisCalls = () => topnOpts().map((o) => o.basis);

async function flush() {
  await act(async () => {
    for (let i = 0; i < 8; i++) await Promise.resolve();
  });
}

const text = () => document.body.textContent ?? "";
const row = () => screen.getByTestId("market-basis-default");
const saveButton = () => within(row()).getByRole("button");
const header = (label: "일간" | "1개월" | "3개월") =>
  screen.getByRole("columnheader", { name: new RegExp(`^${label}`) });

async function openView() {
  const view = render(<MarketDiscoveryView onNavigate={() => undefined} />);
  await flush();
  return view;
}

async function toTable() {
  fireEvent.click(screen.getByRole("tab", { name: "표" }));
  await flush();
}

async function clickHeader(label: "일간" | "1개월" | "3개월") {
  fireEvent.click(header(label));
  await flush();
}

const stored = () => window.localStorage.getItem(MARKET_BASIS_PREF_KEY);
const KEY_WRITES = () =>
  vi.mocked(Storage.prototype.setItem).mock.calls.filter((c) => c[0] === MARKET_BASIS_PREF_KEY).length;

// 다른 탭에서 바뀐 것처럼 값을 쓰고 storage 이벤트를 보낸다(같은 탭 쓰기는 이벤트가 없다).
async function otherTab(value: string | null, key: string | null = MARKET_BASIS_PREF_KEY) {
  if (key === null) window.localStorage.clear();
  else if (value === null) window.localStorage.removeItem(key);
  else window.localStorage.setItem(key, value);
  await act(async () => {
    window.dispatchEvent(
      new StorageEvent("storage", { key, newValue: value, storageArea: window.localStorage }),
    );
  });
  await flush();
}

// 모든 API 를 실제 함수로 두고 fetch 만 바꾼다(저장 클릭 전후 네트워크 요청 수를 센다).
function realApiServer() {
  vi.stubEnv("NEXT_PUBLIC_API_BASE", "http://api.test");
  const fetchStub = vi.fn(async (url: string) => {
    const u = String(url);
    let body: unknown = {};
    if (u.includes("/market/topn/latest")) {
      const q = new URL(u).searchParams;
      body = resp(
        (q.get("basis") ?? "one_month") as MarketBasis,
        (q.get("order") ?? "desc") as MarketOrder,
      );
    } else if (u.includes("/market/refresh/status")) {
      body = { status: "idle", refresh_id: null, cooldown_remaining_seconds: 0 };
    } else if (u.includes("/holdings/enriched")) {
      body = { items: [] };
    }
    return { ok: true, status: 200, text: async () => JSON.stringify(body) };
  });
  vi.stubGlobal("fetch", fetchStub);
  for (const [fn, name] of [
    [fetchMarketTopnLatest, "fetchMarketTopnLatest"],
    [postMarketRefresh, "postMarketRefresh"],
    [fetchMarketRefreshStatus, "fetchMarketRefreshStatus"],
    [fetchEnrichedHoldings, "fetchEnrichedHoldings"],
  ] as const) {
    fn.mockImplementation(actualApi[name] as (...a: unknown[]) => unknown);
  }
  return fetchStub;
}

// localStorage 만 막는다(AI 세션 초안의 sessionStorage 는 그대로).
function failLocal(method: "getItem" | "setItem") {
  const real = Storage.prototype[method];
  return vi.spyOn(Storage.prototype, method).mockImplementation(function (
    this: Storage,
    ...args: unknown[]
  ) {
    if (this === window.localStorage) throw new DOMException("blocked", "SecurityError");
    return (real as (...a: unknown[]) => unknown).apply(this, args);
  } as never);
}

beforeEach(() => {
  __resetQueryCache();
  window.localStorage.clear();
  window.sessionStorage.clear();
  fetchMarketTopnLatest
    .mockReset()
    .mockImplementation((_n: unknown, o: TopnOpts = {}) =>
      Promise.resolve(resp(o.basis ?? "one_month", o.order ?? "desc")),
    );
  postMarketRefresh.mockReset();
  fetchMarketRefreshStatus.mockReset().mockResolvedValue({
    status: "idle",
    refresh_id: null,
    cooldown_remaining_seconds: 0,
  });
  fetchEnrichedHoldings.mockReset().mockResolvedValue({ items: [] });
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe("첫 시장 조회 (POC5-26 설계 §3 · 판정 §2)", () => {
  it("저장된 3개월 → 첫 조회 1회가 3개월(1개월을 먼저 부르지 않음) · '기본 조회 기준 3개월' · '이미 기본'", async () => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    await openView();
    expect(basisCalls()).toEqual(["three_month"]);
    expect(within(row()).getByText("3개월")).toBeInTheDocument();
    expect(row().textContent).not.toContain("지금 보는 기준");
    expect(saveButton()).toHaveTextContent("이미 기본");
    expect(saveButton()).toBeDisabled();
    expect(text()).toContain("3개월 수익률 계산 기간");
    expect(text()).toContain(NAME.three_month);
  });

  it.each(["daily", "one_month"] as const)("저장된 %s → 첫 조회가 그 기준", async (v) => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, v);
    await openView();
    expect(basisCalls()).toEqual([v]);
    expect(saveButton()).toBeDisabled();
  });

  it("개발 모드 이중 실행(StrictMode)에도 저장 기준 서버 GET 1회 · 1개월 요청 없음", async () => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    vi.stubEnv("NEXT_PUBLIC_API_BASE", "http://api.test");
    const fetchStub = vi.fn(async (url: string) => {
      const u = String(url);
      const body = u.includes("/market/topn/latest")
        ? resp((new URL(u).searchParams.get("basis") ?? "one_month") as MarketBasis)
        : {};
      return { ok: true, status: 200, text: async () => JSON.stringify(body) };
    });
    vi.stubGlobal("fetch", fetchStub);
    fetchMarketTopnLatest.mockImplementation(
      actualApi.fetchMarketTopnLatest as (...a: unknown[]) => unknown,
    );
    render(
      <StrictMode>
        <MarketDiscoveryView onNavigate={() => undefined} />
      </StrictMode>,
    );
    expect(await screen.findByText(NAME.three_month)).toBeTruthy();
    const topnUrls = fetchStub.mock.calls
      .map((c) => String(c[0]))
      .filter((u) => u.includes("/market/topn/latest"));
    expect(topnUrls).toHaveLength(1);
    expect(topnUrls[0]).toContain("basis=three_month");
  });

  it("저장값 없음 → 1개월 1회 · 안내 없음 · 저장소에 쓰지 않음", async () => {
    await openView();
    expect(basisCalls()).toEqual(["one_month"]);
    expect(row().textContent).toBe("기본 조회 기준1개월이미 기본");
    expect(stored()).toBeNull();
  });

  it.each(["weekly", "", "THREE_MONTH", '"three_month"'])(
    "허용 밖 값 %j → 1개월 1회 · 같은 자리 짧은 안내 · 저장값을 고치지 않음",
    async (v) => {
      window.localStorage.setItem(MARKET_BASIS_PREF_KEY, v);
      await openView();
      expect(basisCalls()).toEqual(["one_month"]);
      expect(row().textContent).toContain("저장된 기본 값을 쓸 수 없어 1개월로 시작했습니다");
      expect(stored()).toBe(v);
      // 1개월은 대신 쓴 값일 뿐 저장된 기본이 아니다 → 저장할 것이 있다('지금 보는 기준'은 붙이지 않음).
      expect(row().textContent).not.toContain("지금 보는 기준");
      expect(saveButton()).toHaveTextContent("이 기준을 기본으로");
      expect(saveButton()).toBeEnabled();
    },
  );

  it("허용 밖 값 → 1개월에서 바로 저장하면 값이 바로잡히고 안내가 사라진다(다음 화면도 안내 없음)", async () => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "weekly");
    const view = await openView();
    const before = fetchMarketTopnLatest.mock.calls.length;
    fireEvent.click(saveButton());
    await flush();
    expect(stored()).toBe("one_month");
    expect(fetchMarketTopnLatest.mock.calls.length).toBe(before);
    expect(row().textContent).toBe("기본 조회 기준1개월이미 기본");
    view.unmount();
    await openView();
    expect(row().textContent).toBe("기본 조회 기준1개월이미 기본");
  });

  it("읽기 실패 → 1개월 1회 · '저장된 기본을 읽지 못해 1개월로 시작했습니다' · 시장 화면은 그대로", async () => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    const spy = failLocal("getItem");
    await openView();
    expect(basisCalls()).toEqual(["one_month"]);
    expect(row().textContent).toContain("저장된 기본을 읽지 못해 1개월로 시작했습니다");
    expect(text()).toContain(NAME.one_month);
    // 읽기 실패 상태(1개월 대체)에서는 저장할 것이 없다(사용자 확인 목업 ⑥ 그대로).
    expect(saveButton()).toHaveTextContent("이미 기본");
    expect(saveButton()).toBeDisabled();
    spy.mockRestore();
    expect(stored()).toBe("three_month"); // 저장된 기본을 1개월로 덮어쓰지 않음
  });

  it.each([
    ["저장 3개월", "three_month"],
    ["저장값 없음", null],
    ["허용 밖 값", "weekly"],
  ] as const)("%s — 기동 · 조회 · 기준 변경 · 필터 · 메뉴 재진입만으로는 저장하지 않는다(쓰기 0)", async (_l, v) => {
    if (v !== null) window.localStorage.setItem(MARKET_BASIS_PREF_KEY, v);
    vi.spyOn(Storage.prototype, "setItem");
    const view = await openView();
    await toTable();
    await clickHeader("일간");
    await clickHeader("일간"); // 방향 전환
    fireEvent.click(screen.getByLabelText("레버리지 제외"));
    await flush();
    fireEvent.click(screen.getByRole("tab", { name: "카드" }));
    await flush();
    view.unmount();
    await openView();
    expect(KEY_WRITES()).toBe(0);
    expect(stored()).toBe(v);
  });

  it("저장 범위 한 문장은 기간 상자 첫 줄 ? 안에(이 줄에 새 도움말 없음)", async () => {
    await openView();
    expect(within(row()).getAllByRole("button")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "수익률 계산 기간 도움말" }));
    expect(screen.getByRole("dialog", { name: "수익률 계산 기간 도움말" })).toHaveTextContent(
      "위 '기본 조회 기준'은 이 브라우저에만 저장됩니다(다른 기기 · 브라우저 · 접속 주소와 공유하지 않음).",
    );
  });

  it("다른 화면 상태(카드/표 보기 · 필터)는 저장하지 않는다 — 기준 값 하나만", async () => {
    await openView();
    await toTable();
    fireEvent.click(screen.getByLabelText("레버리지 제외"));
    await flush();
    await clickHeader("3개월");
    fireEvent.click(saveButton());
    await flush();
    expect(Object.keys(window.localStorage)).toEqual([MARKET_BASIS_PREF_KEY]);
    expect(stored()).toBe("three_month");
  });
});

describe("명시 저장 · 임시 변경 (POC5-26 설계 §2 · §3 · 판정 §2)", () => {
  it("표 머리로 다른 기준을 보면 기본은 그대로 · '지금 보는 기준 1개월' · [이 기준을 기본으로]", async () => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    await openView();
    await toTable();
    await clickHeader("1개월");
    expect(basisCalls()).toEqual(["three_month", "one_month"]);
    expect(stored()).toBe("three_month");
    expect(within(row()).getByText("3개월")).toBeInTheDocument();
    expect(row().textContent).toContain("· 지금 보는 기준 1개월");
    expect(saveButton()).toHaveTextContent("이 기준을 기본으로");
    expect(saveButton()).toBeEnabled();
  });

  it("[이 기준을 기본으로] → 저장만(시장 GET 없음) · 기본 1개월 · '이미 기본'", async () => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    await openView();
    await toTable();
    await clickHeader("1개월");
    const before = fetchMarketTopnLatest.mock.calls.length;
    const statusBefore = fetchMarketRefreshStatus.mock.calls.length;
    const holdingsBefore = fetchEnrichedHoldings.mock.calls.length;
    fireEvent.click(saveButton());
    await flush();
    expect(fetchMarketTopnLatest.mock.calls.length).toBe(before);
    expect(postMarketRefresh).not.toHaveBeenCalled(); // 수집 · 갱신 시작 없음
    expect(fetchMarketRefreshStatus.mock.calls.length).toBe(statusBefore);
    expect(fetchEnrichedHoldings.mock.calls.length).toBe(holdingsBefore);
    expect(stored()).toBe("one_month");
    expect(within(row()).getByText("1개월")).toBeInTheDocument();
    expect(row().textContent).not.toContain("지금 보는 기준");
    expect(saveButton()).toHaveTextContent("이미 기본");
    expect(saveButton()).toBeDisabled();
  });

  it("같은 칸을 다시 눌러 방향만 바꿔도 기본은 그대로 · 저장해도 방향은 남기지 않음", async () => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    const view = await openView();
    await toTable();
    await clickHeader("3개월");
    expect(topnOpts().at(-1)).toMatchObject({ basis: "three_month", order: "asc" });
    expect(stored()).toBe("three_month");
    expect(saveButton()).toBeDisabled();
    await clickHeader("1개월");
    await clickHeader("1개월"); // 1개월 오름차순(지금 기준 ≠ 기본에서 방향만 바꿈)
    expect(topnOpts().at(-1)).toMatchObject({ basis: "one_month", order: "asc" });
    expect(stored()).toBe("three_month");
    expect(row().textContent).toContain("· 지금 보는 기준 1개월");
    expect(saveButton()).toBeEnabled();
    fireEvent.click(saveButton());
    await flush();
    expect(stored()).toBe("one_month");
    view.unmount();
    fetchMarketTopnLatest.mockClear();
    await openView();
    expect(topnOpts()).toHaveLength(1);
    expect(topnOpts()[0]).toMatchObject({ basis: "one_month", order: "desc" });
  });

  it("화면을 새로 올리면(메뉴 재진입) 저장 기본으로 첫 조회 · 임시 선택은 남지 않음", async () => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    const view = await openView();
    await toTable();
    await clickHeader("일간");
    expect(basisCalls()).toEqual(["three_month", "daily"]);
    view.unmount();
    fetchMarketTopnLatest.mockClear();
    await openView();
    expect(basisCalls()).toEqual(["three_month"]);
  });

  it("방금 저장한 기본으로 다음 화면이 시작한다", async () => {
    const view = await openView();
    await toTable();
    await clickHeader("3개월");
    fireEvent.click(saveButton());
    await flush();
    view.unmount();
    fetchMarketTopnLatest.mockClear();
    await openView();
    expect(basisCalls()).toEqual(["three_month"]);
    expect(saveButton()).toBeDisabled();
  });

  it("카드 보기에도 같은 줄 · 표에서 고른 기준을 카드 보기에서 저장할 수 있다", async () => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    await openView();
    expect(screen.getByRole("tab", { name: "카드" })).toHaveAttribute("aria-selected", "true");
    expect(row().textContent).toContain("기본 조회 기준");
    await toTable();
    await clickHeader("1개월");
    fireEvent.click(screen.getByRole("tab", { name: "카드" }));
    await flush();
    expect(row().textContent).toContain("· 지금 보는 기준 1개월");
    fireEvent.click(saveButton());
    await flush();
    expect(stored()).toBe("one_month");
    expect(saveButton()).toBeDisabled();
  });
});

describe("저장 클릭은 저장만 · 빈 목록에도 줄 (POC5-26 설계 §3 · §6 · 판정 §1 · §2)", () => {
  it("[이 기준을 기본으로] 전후 네트워크 요청 수가 같다(시장 GET · 갱신 · 다른 조회 없음)", async () => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    const fetchStub = realApiServer();
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    expect(await screen.findByText(NAME.three_month)).toBeTruthy();
    await toTable();
    await clickHeader("1개월");
    expect(await screen.findByText(NAME.one_month)).toBeTruthy();
    await flush();
    const before = fetchStub.mock.calls.length;
    fireEvent.click(saveButton());
    await flush();
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(stored()).toBe("one_month");
    expect(fetchStub.mock.calls.length).toBe(before);
  });

  it.each(["카드", "표"] as const)("후보가 0개여도 %s 보기 목록 카드 맨 위에 줄이 있다", async (tab) => {
    fetchMarketTopnLatest.mockImplementation((_n: unknown, o: TopnOpts = {}) =>
      Promise.resolve(resp(o.basis ?? "one_month", o.order ?? "desc", true)),
    );
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    await openView();
    fireEvent.click(screen.getByRole("tab", { name: tab }));
    await flush();
    expect(text()).toContain(tab === "표" ? "표시할 항목이 없습니다." : "표시할 후보가 없습니다.");
    expect(within(row()).getByText("3개월")).toBeInTheDocument();
    expect(saveButton()).toBeDisabled();
  });
});

describe("다른 탭에서 바뀐 기본 (POC5-26 설계 §2-3 · §3 저장 위치)", () => {
  it("다른 탭이 3개월을 저장하면 '기본' 표시만 바뀐다(지금 조회 · 시장 GET 그대로)", async () => {
    await openView();
    expect(row().textContent).toBe("기본 조회 기준1개월이미 기본");
    const before = fetchMarketTopnLatest.mock.calls.length;
    await otherTab("three_month");
    expect(within(row()).getByText("3개월")).toBeInTheDocument();
    expect(row().textContent).toContain("· 지금 보는 기준 1개월");
    expect(saveButton()).toBeEnabled();
    expect(fetchMarketTopnLatest.mock.calls.length).toBe(before);
    expect(text()).toContain("1개월 수익률 계산 기간");
    expect(stored()).toBe("three_month");
  });

  it("다른 탭이 허용 밖 값을 쓰면 안내 · 지우면 1개월(안내 없음) · 다른 키는 무시", async () => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    await openView();
    await otherTab("weekly");
    expect(row().textContent).toContain("저장된 기본 값을 쓸 수 없어 1개월로 시작했습니다");
    expect(within(row()).getByText("1개월")).toBeInTheDocument();
    await otherTab(null, null); // 저장소 전체 지움
    expect(row().textContent).toBe("기본 조회 기준1개월· 지금 보는 기준 3개월이 기준을 기본으로");
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "daily"); // 이벤트 없이 바뀐 값
    await otherTab("x", "some.other.key");
    expect(within(row()).getByText("1개월")).toBeInTheDocument(); // 다른 키 이벤트로는 다시 읽지 않음
  });

  it("저장 실패 뒤 다른 탭이 같은 기준을 저장하면 실패 안내가 사라지고 '이미 기본'", async () => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    await openView();
    await toTable();
    await clickHeader("1개월");
    const spy = failLocal("setItem");
    fireEvent.click(saveButton());
    await flush();
    expect(screen.getByRole("alert")).toHaveTextContent(BASIS_SAVE_FAILED);
    spy.mockRestore();
    await otherTab("one_month");
    expect(screen.queryByRole("alert")).toBeNull();
    expect(saveButton()).toHaveTextContent("이미 기본");
  });
});

describe("저장 실패 (POC5-26 설계 §3 · 판정 §3)", () => {
  async function failSaveWith(arrange: () => void) {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    await openView();
    await toTable();
    await clickHeader("1개월");
    const before = fetchMarketTopnLatest.mock.calls.length;
    arrange();
    fireEvent.click(saveButton());
    await flush();
    return before;
  }

  it("쓰기 예외 → '기본값 저장을 확인하지 못했습니다. 현재 조회는 유지됩니다.' · 기본 표시 · 지금 조회 그대로 · GET 없음", async () => {
    const before = await failSaveWith(() => failLocal("setItem"));
    expect(screen.getByRole("alert")).toHaveTextContent(BASIS_SAVE_FAILED);
    expect(BASIS_SAVE_FAILED).toBe("기본값 저장을 확인하지 못했습니다. 현재 조회는 유지됩니다.");
    expect(fetchMarketTopnLatest.mock.calls.length).toBe(before);
    expect(within(row()).getByText("3개월")).toBeInTheDocument();
    expect(row().textContent).toContain("· 지금 보는 기준 1개월");
    expect(saveButton()).toBeEnabled();
    expect(header("1개월")).toHaveClass("basis-active");
    expect(text()).toContain(NAME.one_month);
    vi.restoreAllMocks();
    expect(stored()).toBe("three_month");
  });

  it("다시 읽은 값이 다름(저장 확인 실패) → 같은 안내 · 기본 표시 그대로", async () => {
    await failSaveWith(() => {
      vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => undefined);
    });
    expect(screen.getByRole("alert")).toHaveTextContent(BASIS_SAVE_FAILED);
    expect(within(row()).getByText("3개월")).toBeInTheDocument();
  });

  it("실패 뒤 다시 눌러 성공하면 안내가 사라지고 기본이 바뀐다", async () => {
    const spy = await failSaveWith(() => failLocal("setItem")).then(() =>
      vi.mocked(Storage.prototype.setItem),
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    spy.mockRestore();
    fireEvent.click(saveButton());
    await flush();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(stored()).toBe("one_month");
    expect(saveButton()).toBeDisabled();
  });

  it("실패 안내는 기준을 바꿔 다시 읽으면 사라진다(지난 시도 안내를 남기지 않음)", async () => {
    await failSaveWith(() => failLocal("setItem"));
    expect(screen.getByRole("alert")).toBeInTheDocument();
    await clickHeader("일간");
    expect(screen.queryByRole("alert")).toBeNull();
    await clickHeader("1개월");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("읽기 실패 안내는 저장에 성공하면 사라진다", async () => {
    const spy = failLocal("getItem");
    await openView();
    expect(row().textContent).toContain("저장된 기본을 읽지 못해");
    spy.mockRestore();
    await toTable();
    await clickHeader("3개월");
    fireEvent.click(saveButton());
    await flush();
    expect(row().textContent).not.toContain("저장된 기본을 읽지 못해");
    expect(stored()).toBe("three_month");
  });
});

describe("지금 조회 유지 — 다시 읽기 · 필터 · 표시 · 전달 (POC5-26 설계 §3 · §4 · 판정 §2)", () => {
  it("갱신이 끝난 뒤 다시 읽기는 지금 보는 기준(저장 기본으로 되돌리지 않음)", async () => {
    vi.useFakeTimers();
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    postMarketRefresh.mockResolvedValue({
      status: "accepted",
      refresh_id: "r26",
      message: "",
      cooldown_remaining_seconds: 0,
    });
    await openView();
    await toTable();
    await clickHeader("1개월");
    fetchMarketRefreshStatus.mockResolvedValue({
      status: "running",
      refresh_id: "r26",
      cooldown_remaining_seconds: 0,
    });
    fireEvent.click(screen.getAllByRole("button", { name: "최신 시장 데이터 갱신" })[0]);
    await flush();
    const before = fetchMarketTopnLatest.mock.calls.length;
    fetchMarketRefreshStatus.mockResolvedValue({
      status: "completed",
      refresh_id: "r26",
      cooldown_remaining_seconds: 0,
    });
    await act(async () => {
      vi.advanceTimersByTime(4100);
    });
    await flush();
    expect(text()).toContain("갱신 완료.");
    expect(fetchMarketTopnLatest.mock.calls.length).toBe(before + 1);
    expect(basisCalls().at(-1)).toBe("one_month");
    expect(stored()).toBe("three_month");
    expect(row().textContent).toContain("· 지금 보는 기준 1개월");
  });

  it("'VIX 다시 받기'가 끝난 뒤 다시 읽기도 지금 보는 기준(저장 기본으로 되돌리지 않음)", async () => {
    vi.useFakeTimers();
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    fetchMarketRefreshStatus.mockResolvedValue({
      status: "completed",
      refresh_id: "r1",
      cooldown_remaining_seconds: 3600,
      vix_retry: {
        needed: true,
        status: "needed",
        refresh_id: "r1",
        error_summary: "시장 불안 지표(VIX)를 갱신하지 못했습니다",
      },
    });
    postMarketRefresh.mockResolvedValue({
      status: "accepted",
      refresh_id: "vix_retry_26",
      message: "",
      cooldown_remaining_seconds: 3600,
    });
    await openView();
    await toTable();
    await clickHeader("1개월");
    fireEvent.click(screen.getAllByRole("button", { name: "VIX 다시 받기" })[0]);
    await flush();
    expect(postMarketRefresh).toHaveBeenCalledWith("vix");
    const before = fetchMarketTopnLatest.mock.calls.length;
    fetchMarketRefreshStatus.mockResolvedValue({
      status: "completed",
      refresh_id: "r1",
      cooldown_remaining_seconds: 3600,
      vix_retry: {
        needed: false,
        status: "completed",
        refresh_id: "vix_retry_26",
        vix_as_of_date: "2026-10-19",
      },
    });
    await act(async () => {
      vi.advanceTimersByTime(4100);
    });
    await flush();
    expect(text()).toContain("VIX 다시 받기 완료(기준일 2026-10-19)");
    expect(fetchMarketTopnLatest.mock.calls.length).toBe(before + 1);
    expect(basisCalls().at(-1)).toBe("one_month");
    expect(stored()).toBe("three_month");
    expect(row().textContent).toContain("· 지금 보는 기준 1개월");
  });

  it("필터를 바꿔도 지금 보는 기준 그대로", async () => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    await openView();
    await toTable();
    await clickHeader("1개월");
    fireEvent.click(screen.getByLabelText("레버리지 제외"));
    await flush();
    expect(topnOpts().at(-1)).toMatchObject({ basis: "one_month", excludeLeveraged: false });
    expect(stored()).toBe("three_month");
  });

  it("기본 ≠ 지금 기준일 때 카드 · 기간 상자 · AI 세션 전달 · 「보유와 비교」가 지금 기준 응답을 쓴다", async () => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    const onNavigate = vi.fn();
    render(<MarketDiscoveryView onNavigate={onNavigate} />);
    await flush();
    await toTable();
    await clickHeader("1개월");
    fireEvent.click(screen.getByRole("tab", { name: "카드" }));
    await flush();
    expect(text()).toContain(NAME.one_month);
    expect(text()).not.toContain(NAME.three_month);
    expect(text()).toContain("1개월 수익률 계산 기간");
    fireEvent.click(screen.getAllByRole("button", { name: "AI Sessions로 넘기기" })[0]);
    await flush();
    expect(onNavigate).toHaveBeenCalledWith("ai_sessions");
    const draft = loadAISessionsDraft();
    expect(draft?.candidate_snapshot.map((c) => c.ticker)).toEqual([TICKER.one_month]);
    expect(draft?.question_text).toContain(NAME.one_month);
    expect(draft?.question_text).not.toContain(NAME.three_month);
    expect(JSON.stringify(draft)).not.toContain(TICKER.three_month);
    // 기존 전달에 없던 기준 이름 · 필드를 새로 싣지 않는다(판정 §2).
    expect(draft).not.toHaveProperty("basis");
    expect(draft?.question_text).not.toContain("기본 조회 기준");
    fireEvent.click(screen.getByRole("tab", { name: "보유와 비교" }));
    await flush();
    expect(text()).toContain(NAME.one_month);
    expect(text()).toContain("1개월 1위");
    expect(text()).not.toContain("3개월 1위");
    expect(stored()).toBe("three_month");
  });
});
