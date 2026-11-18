// POC6-32 V2(PLAN §4-3 · §4-4 · §9 I-12 · AC3) — 「AI 투자 세션」 주간 기록: 사용자 판단 '미기록' · 표시 규칙 ·
// 「주간 ETF 점검」 ⑤ [기록 열기] → 그 기록 상세 바로 열기(남은 초안보다 우선).
// 진짜 request 를 쓰고 fetch 만 가짜다(경로별 응답 · 호출 기록). 라이브 서버 · DB 없음 · 이름은 가상 · 금액 없음.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act, within } from "@testing-library/react";
import AISessionsCreateTab from "./AISessionsCreateTab";
import AISessionsListTab from "./AISessionsListTab";
import AISessionsView from "./AISessionsView";
import { WeeklyLast } from "./today/WeeklyRecord";
import { saveAISessionsDraft, verdictText, type AISessionsDraft } from "@/lib/aiSessionsDraft";
import { presetOpenRecord, takeOpenRecord } from "@/lib/detailNav";
import { WEEKLY_REVIEW_SOURCE, type WeeklyLastRecord } from "@/lib/api/weeklyReview";
import { WEEKLY_SAVED } from "@/lib/weeklyReviewTestFixtures";

const FILTERS = { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true };

type Call = { method: string; path: string; body: unknown };
let calls: Call[] = [];
let routes: Record<string, unknown> = {};
// 경로별로 응답을 붙잡아 두기(늦게 오는 응답 시험) — 풀어 줄 때까지 기다린다.
let hold: Record<string, (() => void)[]> = {};
const fetchMock = vi.fn(async (url: string, init?: { method?: string; body?: string }) => {
  const path = url.replace("http://api.test", "");
  const method = init?.method ?? "GET";
  calls.push({ method, path, body: init?.body ? JSON.parse(init.body) : null });
  const key = `${method} ${path.split("?")[0]}`;
  if (hold[key]) await new Promise<void>((r) => hold[key].push(r));
  const b = routes[key];
  if (b === undefined) return { ok: false, status: 404, text: async () => "" };
  return { ok: true, status: 200, text: async () => JSON.stringify(b) };
});

const scrollSpy = vi.fn();
beforeEach(() => {
  calls = [];
  routes = {};
  hold = {};
  fetchMock.mockClear();
  scrollSpy.mockClear();
  window.sessionStorage.clear();
  takeOpenRecord(); // 앞 시험이 남긴 한 번 넘김 비우기
  vi.stubEnv("NEXT_PUBLIC_API_BASE", "http://api.test");
  vi.stubGlobal("fetch", fetchMock);
  // jsdom 에는 scrollIntoView 가 없다 — 불렀는지만 본다.
  (Element.prototype as unknown as { scrollIntoView: unknown }).scrollIntoView = scrollSpy;
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  delete (Element.prototype as unknown as { scrollIntoView?: unknown }).scrollIntoView;
});

function weeklyDraftFixture(over: Partial<AISessionsDraft> = {}): AISessionsDraft {
  return {
    asof: "2026-11-16",
    filters: FILTERS,
    candidate_snapshot: [
      { rank: 1, ticker: "900001", name: "가상 ETF 하나", tags: [] },
      { rank: 2, ticker: "900002", name: "가상 ETF 둘", tags: [] },
    ],
    question_text: "「주간 ETF 점검」 질문 원문",
    linked_market_refresh_id: null,
    draft_created_at: "2026-11-17T21:00:00+09:00",
    market_context_snapshot: { source: WEEKLY_REVIEW_SOURCE, lines: ["시장 줄"] },
    data_quality_snapshot: { condition: { line: "1개월 상위 2개" }, selected: { ticker: "900002" }, evidence_list: [] },
    constituent_snapshot: { selected: { ticker: "900002" }, product: { found: true }, constituents: { state: "full" } },
    overlap_snapshot: { state: "ok", lines: ["겹침 줄"] },
    source_screen: WEEKLY_REVIEW_SOURCE,
    ...over,
  };
}

function marketDraft(): AISessionsDraft {
  return {
    asof: "2026-11-16",
    filters: FILTERS,
    candidate_snapshot: [{ rank: 1, ticker: "900009", name: "가상 후보", tags: [] }],
    question_text: "후보리스트 질문",
    linked_market_refresh_id: null,
    draft_created_at: "2026-11-17T21:00:00+09:00",
  };
}

function optionValues(container: HTMLElement): string[] {
  return Array.from((container.querySelector("#ais-verdict") as HTMLSelectElement).options).map((o) => o.value);
}

async function save(container: HTMLElement) {
  routes["POST /decision/sessions"] = { status: "ok", id: "decision_new", created_at: "t" };
  routes["GET /ml/baseline-v0/evidence-snapshot"] = { status: "ok" };
  await act(async () => {
    fireEvent.click(within(container).getByRole("button", { name: "기록 저장" }));
  });
  await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/decision/sessions")).toBe(true));
  return calls.find((c) => c.method === "POST" && c.path === "/decision/sessions")!.body as Record<string, unknown>;
}

describe("사용자 판단 표시 글자(verdictText · PLAN §9 I-12)", () => {
  it.each([
    [WEEKLY_REVIEW_SOURCE, "unrecorded", "미기록"],
    [WEEKLY_REVIEW_SOURCE, "hold", "보류(직접 고름)"],
    [WEEKLY_REVIEW_SOURCE, "useful", "쓸 만함(직접 고름)"],
    [WEEKLY_REVIEW_SOURCE, "needs_market_compare", "시장 비교 필요(직접 고름)"],
    ["market_discovery", "hold", "보류 · 사용자 판단 미확인"],
    ["holdings_compare_preview", "hold", "보류 · 사용자 판단 미확인"],
    ["market_discovery", "useful", "쓸 만함"],
    ["holdings_compare_preview", "needs_constituents", "구성 종목 필요"],
    [WEEKLY_REVIEW_SOURCE, "모르는값", "모르는값"],
    ["market_discovery", "모르는값", "모르는값"],
    [WEEKLY_REVIEW_SOURCE, null, "-"],
    [null, "hold", "보류 · 사용자 판단 미확인"],
  ])("출처 %s · 값 %s → %s", (src, v, want) => {
    expect(verdictText(src, v)).toBe(want);
  });
});

describe("저장 화면 — 주간 초안은 '미기록'에서 시작 · 주간이 아닌 초안은 지금 그대로", () => {
  it("주간 — 선택지 맨 앞 '미기록' · 처음 값 '미기록' · AI 답 하나 · 메모 · 다음 확인 없이 저장 · 초안 저장 칸 그대로", async () => {
    const d = weeklyDraftFixture();
    const { container } = render(<AISessionsCreateTab draft={d} onSaved={() => {}} />);
    expect(optionValues(container)).toEqual(["unrecorded", "useful", "needs_constituents", "needs_market_compare", "hold"]);
    const sel = container.querySelector("#ais-verdict") as HTMLSelectElement;
    expect(sel.value).toBe("unrecorded");
    expect(sel.options[sel.selectedIndex].textContent).toBe("미기록");
    expect(screen.getByText("사용자 판단")).toBeTruthy();
    expect(screen.getByTestId("ais-verdict-help")).toHaveTextContent(
      "'미기록'에서 시작하고 그대로 저장할 수 있습니다 · 직접 고른 '보류'는 메모 · 다음 확인이 비어도 유효합니다",
    );
    expect(container.textContent).toContain("「주간 ETF 점검」에서 넘어온 목록");
    fireEvent.change(container.querySelector("#ais-claude")!, { target: { value: "Claude 답 하나" } });
    const body = await save(container);
    expect(body.source_screen).toBe(WEEKLY_REVIEW_SOURCE);
    expect(body.user_verdict).toBe("unrecorded");
    expect(body.user_memo).toBe("");
    expect(body.next_checks).toEqual([]);
    expect(body.gpt_answer_text).toBe("");
    expect(body.claude_answer_text).toBe("Claude 답 하나");
    expect(body.data_quality_snapshot).toEqual(d.data_quality_snapshot);
    expect(body.constituent_snapshot).toEqual(d.constituent_snapshot);
    expect(body.overlap_snapshot).toEqual(d.overlap_snapshot);
    expect(body.market_context_snapshot).toEqual(d.market_context_snapshot);
  });

  it("주간 — 직접 고른 '보류'는 메모 · 다음 확인이 비어도 그대로 저장('hold')", async () => {
    const { container } = render(<AISessionsCreateTab draft={weeklyDraftFixture()} onSaved={() => {}} />);
    fireEvent.change(container.querySelector("#ais-verdict")!, { target: { value: "hold" } });
    fireEvent.change(container.querySelector("#ais-gpt")!, { target: { value: "GPT 답" } });
    expect(within(container).getByRole("button", { name: "기록 저장" })).not.toBeDisabled();
    const body = await save(container);
    expect(body.user_verdict).toBe("hold");
    expect(body.user_memo).toBe("");
    expect(body.next_checks).toEqual([]);
  });

  it("주간이 아닌 초안 — '미기록' 선택지 없음 · 처음 값 '보류' · 이름표 그대로 · 'hold' 저장", async () => {
    const { container } = render(<AISessionsCreateTab draft={marketDraft()} onSaved={() => {}} />);
    expect(optionValues(container)).toEqual(["useful", "needs_constituents", "needs_market_compare", "hold"]);
    expect((container.querySelector("#ais-verdict") as HTMLSelectElement).value).toBe("hold");
    expect(screen.getByText("사용자 1차 판정")).toBeTruthy();
    expect(screen.queryByTestId("ais-verdict-help")).toBeNull();
    fireEvent.change(container.querySelector("#ais-gpt")!, { target: { value: "GPT 답" } });
    const body = await save(container);
    expect(body.source_screen).toBe("market_discovery");
    expect(body.user_verdict).toBe("hold");
  });

  it("주간이 아닌 초안 — 상태에 '미기록'이 들어와도 보내지 않는다(그 화면 기본값 '보류')", async () => {
    const { container } = render(<AISessionsCreateTab draft={marketDraft()} onSaved={() => {}} />);
    const sel = container.querySelector("#ais-verdict") as HTMLSelectElement;
    // 선택지에 없는 값을 강제로 넣는 경우(화면 조작) — onChange 가 받는 값을 그대로 흉내
    const opt = document.createElement("option");
    opt.value = "unrecorded";
    sel.appendChild(opt);
    fireEvent.change(sel, { target: { value: "unrecorded" } });
    fireEvent.change(container.querySelector("#ais-gpt")!, { target: { value: "GPT 답" } });
    const body = await save(container);
    expect(body.user_verdict).toBe("hold");
  });
});

function summaryRow(id: string, source: string, verdict: string) {
  return {
    id,
    created_at: "2026-11-17T21:05:00.000000+0900",
    asof: "2026-11-16",
    source_screen: source,
    user_verdict: verdict,
    summary: "요약",
    candidate_count: 2,
    has_gpt_answer: true,
    has_gemini_answer: false,
    has_claude_answer: false,
  };
}

function weeklyRecord(id: string, over: Record<string, unknown> = {}) {
  return {
    id,
    created_at: "2026-11-17T21:05:00.000000+0900",
    updated_at: "2026-11-17T21:05:00.000000+0900",
    asof: "2026-11-16",
    source_screen: WEEKLY_REVIEW_SOURCE,
    filters: FILTERS,
    candidate_snapshot: [{ rank: 1, ticker: "900001", name: "가상 ETF 하나", tags: [] }],
    question_text: "질문 원문 그대로",
    gpt_answer_text: "GPT 원문",
    gemini_answer_text: "",
    claude_answer_text: "",
    user_memo: "",
    user_verdict: "unrecorded",
    next_checks: [],
    linked_market_refresh_id: null,
    market_context_snapshot: { source: WEEKLY_REVIEW_SOURCE },
    constituent_snapshot: {},
    overlap_snapshot: {},
    short_term_momentum_snapshot: {},
    data_quality_snapshot: {},
    ml_baseline_evidence_snapshot: {},
    ...over,
  };
}

describe("기록 조회 — 판정 칸 · 주간 기록 상세", () => {
  it("목록 판정 칸 = 출처별 표시(저장값은 그대로)", async () => {
    routes["GET /decision/sessions"] = {
      status: "ok",
      records: [
        summaryRow("w1", WEEKLY_REVIEW_SOURCE, "unrecorded"),
        summaryRow("w2", WEEKLY_REVIEW_SOURCE, "hold"),
        summaryRow("m1", "market_discovery", "hold"),
        summaryRow("m2", "holdings_compare_preview", "useful"),
      ],
    };
    const { container } = render(<AISessionsListTab reloadTrigger={0} />);
    await waitFor(() => expect(screen.getAllByRole("button", { name: "보기" }).length).toBe(4));
    const cells = Array.from(container.querySelectorAll("tbody tr")).map((tr) => tr.querySelectorAll("td")[2].textContent);
    expect(cells).toEqual(["미기록", "보류(직접 고름)", "보류 · 사용자 판단 미확인", "쓸 만함"]);
    expect(container.textContent).not.toContain("unrecorded");
  });

  it("주간 기록 상세 = '당시 검토' + 접힌 원문(질문 · 저장 칸) · 주간이 아닌 상세는 지금 그대로", async () => {
    routes["GET /decision/sessions"] = {
      status: "ok",
      records: [summaryRow("w1", WEEKLY_REVIEW_SOURCE, "hold"), summaryRow("m1", "market_discovery", "hold")],
    };
    routes["GET /decision/sessions/w1"] = { status: "ok", record: weeklyRecord("w1", { user_verdict: "hold" }) };
    routes["GET /decision/sessions/m1"] = {
      status: "ok",
      record: weeklyRecord("m1", { source_screen: "market_discovery", user_verdict: "hold", question_text: "일반 질문" }),
    };
    const { container } = render(<AISessionsListTab reloadTrigger={0} />);
    await waitFor(() => expect(screen.getAllByRole("button", { name: "보기" }).length).toBe(2));
    await act(async () => {
      fireEvent.click(screen.getAllByRole("button", { name: "보기" })[0]);
    });
    await waitFor(() => expect(screen.getByTestId("wrs")).toBeTruthy());
    expect(screen.getByTestId("wrs-head")).toHaveTextContent("사용자 판단 보류(직접 고름)");
    const raw = screen.getByTestId("wrs-raw") as HTMLDetailsElement;
    expect(raw.open).toBe(false);
    expect(raw).toHaveTextContent("질문 원문 그대로");
    expect(raw).not.toHaveTextContent("GPT 원문"); // AI 답은 '당시 검토' 안에서 AI 별로 접힘
    expect(container.querySelector(".decision-detail-card")!.textContent).not.toContain("화면: today_weekly_review");
    // 주간이 아닌 기록 — 지금 그대로(당시 검토 없음 · 원문 펼쳐 둠) + 판정 표시만 규칙대로
    await act(async () => {
      fireEvent.click(screen.getAllByRole("button", { name: "보기" })[1]);
    });
    await waitFor(() => expect(screen.getByText("기록 상세 — m1")).toBeTruthy());
    expect(screen.queryByTestId("wrs")).toBeNull();
    const card = container.querySelector(".decision-detail-card")!;
    expect(card.textContent).toContain("판정: 보류 · 사용자 판단 미확인");
    expect(card.textContent).toContain("일반 질문");
    expect(card.textContent).toContain("GPT 원문");
    expect(card.querySelector("details")).toBeNull();
    // AI 답 해석 요청은 주간 기록에서만(w1 한 번 · m1 없음)
    expect(calls.filter((c) => c.path.startsWith("/weekly/")).map((c) => c.path)).toEqual(["/weekly/etf-check/records/w1/review"]);
  });

  it("찾지 못한 기록 — 서버 영어 안내 대신 쉬운 한국어 한 줄", async () => {
    routes["GET /decision/sessions"] = { status: "ok", records: [] };
    routes["GET /decision/sessions/gone"] = { status: "not_found", record: null, message: "Decision session not found." };
    render(<AISessionsListTab reloadTrigger={0} openId="gone" />);
    await waitFor(() => expect(screen.getByText("기록을 찾을 수 없습니다.")).toBeTruthy());
    expect(document.body.textContent).not.toContain("Decision session not found.");
  });

  it("넘겨받은 기록을 여는 중에 다른 행 [보기]를 누르면 늦게 온 앞 응답을 버린다", async () => {
    routes["GET /decision/sessions"] = { status: "ok", records: [summaryRow("m1", "market_discovery", "useful")] };
    routes["GET /decision/sessions/w1"] = { status: "ok", record: weeklyRecord("w1") };
    routes["GET /decision/sessions/m1"] = {
      status: "ok",
      record: weeklyRecord("m1", { source_screen: "market_discovery", user_verdict: "useful" }),
    };
    hold["GET /decision/sessions/w1"] = [];
    render(<AISessionsListTab reloadTrigger={0} openId="w1" />);
    await waitFor(() => expect(screen.getAllByRole("button", { name: "보기" }).length).toBe(1));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "보기" }));
    });
    await waitFor(() => expect(screen.getByText("기록 상세 — m1")).toBeTruthy());
    await act(async () => {
      hold["GET /decision/sessions/w1"].forEach((r) => r());
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText("기록 상세 — m1")).toBeTruthy();
    expect(screen.queryByText("기록 상세 — w1")).toBeNull();
  });
});

describe("「주간 ETF 점검」 ⑤ [기록 열기] → 「AI 투자 세션」 그 기록 상세(PLAN §4-4)", () => {
  function last(over: Partial<WeeklyLastRecord> = {}): WeeklyLastRecord {
    return {
      status: "ok",
      message: null,
      id: "rec-w",
      saved_at: "2026-11-17T21:05:00+09:00",
      asof: "2026-11-16",
      verdict: "unrecorded",
      memo: null,
      next_checks: [],
      candidate_count: 30,
      ...over,
    };
  }

  it("기록이 있으면 버튼 · 누르면 그 id 를 넘기고 이동 · 사용자 판단 '미기록' / '(직접 고름)'", () => {
    // 이동 시점에 id 가 이미 넘겨져 있어야 받는 화면이 읽는다 — 이동 함수 안에서 읽어 둔 값을 본다.
    let seen: string | null | undefined;
    const onOpen = vi.fn(() => {
      seen = takeOpenRecord();
    });
    const { rerender } = render(<WeeklyLast last={last()} onOpen={onOpen} />);
    const box = screen.getByTestId("wr-last");
    // 고른 후보 · AI 답 수 칸이 없는 응답 = '기록 없음' · '확인 불가'(고르지 않음 · 0개로 바꾸지 않음)
    expect(box).toHaveTextContent(
      "저장 2026-11-17 21:05 · 원자료 기준일 11/16 · 고른 후보 기록 없음 · 사용자 판단 미기록 · AI 답 수 확인 불가",
    );
    expect(box).toHaveTextContent("새 주간 기록은 판단 '미기록'에서 시작하고 그대로 저장할 수 있습니다");
    fireEvent.click(within(box).getByRole("button", { name: "기록 열기 → AI 투자 세션" }));
    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(seen).toBe("rec-w");
    rerender(<WeeklyLast last={last({ verdict: "hold" })} onOpen={onOpen} />);
    expect(screen.getByTestId("wr-last")).toHaveTextContent("사용자 판단 보류(직접 고름)");
  });

  it.each<[string, Partial<WeeklyLastRecord>, string]>([
    ["고른 후보 있음", { selected: { status: "ok", ticker: "476070", name: "가상 ETF" }, answer_count: 2 }, "고른 후보 476070 가상 ETF · 사용자 판단 미기록 · AI 답 2개"],
    ["이름 없음", { selected: { status: "ok", ticker: "476070", name: null }, answer_count: 0 }, "고른 후보 476070 · 사용자 판단 미기록 · AI 답 0개"],
    ["고르지 않고 넘김", { selected: { status: "none" }, answer_count: 1 }, "고른 후보 없음 · 사용자 판단 미기록 · AI 답 1개"],
  ])("검토 F4(목업 ⑤) — %s", (_n, over, want) => {
    render(<WeeklyLast last={last(over)} onOpen={vi.fn()} />);
    expect(screen.getByTestId("wr-last-line")).toHaveTextContent(`원자료 기준일 11/16 · ${want}`);
  });

  it.each([
    ["기록 없음", { status: "none", message: "이 화면에서 저장한 기록 없음", id: undefined }],
    ["읽기 실패", { status: "error", message: "기록을 읽지 못했습니다 — 「AI 투자 세션」에서 확인", id: undefined }],
    ["id 없는 기록", { id: undefined }],
  ] as [string, Partial<WeeklyLastRecord>][])("%s — 버튼 없음 · 넘긴 id 없음", (_n, over) => {
    render(<WeeklyLast last={last(over)} onOpen={vi.fn()} />);
    expect(within(screen.getByTestId("wr-last")).queryByRole("button")).toBeNull();
    expect(takeOpenRecord()).toBeNull();
  });

  it("넘겨받은 기록 — 남은 초안보다 먼저 [기록 조회]에서 그 상세를 열고 그 카드로 스크롤 · 한 번만 읽음", async () => {
    saveAISessionsDraft(weeklyDraftFixture());
    routes["GET /decision/sessions"] = { status: "ok", records: [summaryRow("other", "market_discovery", "hold")] };
    routes["GET /decision/sessions/rec-w"] = { status: "ok", record: weeklyRecord("rec-w") };
    // AC3 — 저장한 답을 나눈 결과(서버 해석기 출력 모양 · 화면 고정 자료의 합성 답)
    routes["GET /weekly/etf-check/records/rec-w/review"] = WEEKLY_SAVED.last_record;
    presetOpenRecord("rec-w");
    render(<AISessionsView />);
    await waitFor(() => expect(screen.getByText("기록 상세 — rec-w")).toBeTruthy());
    expect(screen.getByRole("button", { name: "기록 조회" }).className).toContain("decision-tab-active");
    expect(screen.getByTestId("wrs-head")).toHaveTextContent("사용자 판단 미기록");
    const ai = screen.getByTestId("wrs-ai");
    await waitFor(() =>
      expect(within(ai).getByTestId("wr-ai-latest")).toHaveTextContent("최신 확인: GPT 같음 · Gemini 확인 불가 · Claude 새 값 있음"),
    );
    expect(within(ai).getAllByTestId("wr-ai-item")[0]).toHaveTextContent("확인 시각 미기재");
    await waitFor(() => expect(scrollSpy).toHaveBeenCalled());
    expect(takeOpenRecord()).toBeNull();
    // 초안은 지우지 않는다 — [새 기록 저장]에 그대로
    fireEvent.click(screen.getByRole("button", { name: "새 기록 저장" }));
    expect(screen.getByText("「주간 ETF 점검」에서 넘어온 목록", { exact: false })).toBeTruthy();
    // 탭을 오가도 같은 기록을 다시 열지 않는다
    fireEvent.click(screen.getByRole("button", { name: "기록 조회" }));
    await waitFor(() => expect(screen.getAllByRole("button", { name: "보기" }).length).toBe(1));
    expect(calls.filter((c) => c.path === "/decision/sessions/rec-w").length).toBe(1);
    expect(screen.queryByText("기록 상세 — rec-w")).toBeNull();
  });

  it("넘겨받은 기록이 없으면 지금 그대로 — 초안이 있으면 [새 기록 저장] · 상세 자동 열기 없음", async () => {
    saveAISessionsDraft(weeklyDraftFixture());
    render(<AISessionsView />);
    await waitFor(() => expect(screen.getByRole("button", { name: "새 기록 저장" }).className).toContain("decision-tab-active"));
    expect(calls.some((c) => c.path.startsWith("/decision/sessions/"))).toBe(false);
    expect(scrollSpy).not.toHaveBeenCalled();
  });
});
