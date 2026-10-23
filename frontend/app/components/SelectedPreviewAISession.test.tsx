// POC5-24 — 선택 근거(「보유와 비교」 판단 근거 미리보기)의 AI 투자 세션 연결(설계 V1 · PLAN 판정 2026-10-18).
// 미리보기 → [AI 세션에서 검토] → 초안(원문 · 날짜 그대로) → 작성 화면 → 저장 요청 · 기록 조회 표시.
// 진짜 request 를 쓰고 fetch 만 가짜다(경로별 응답 · 호출 기록). 라이브 서버 · DB 없음.
import { useEffect } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import DecisionDraftPreviewCard from "./holdings_compare/DecisionDraftPreviewCard";
import AISessionsCreateTab from "./AISessionsCreateTab";
import AISessionsListTab from "./AISessionsListTab";
import {
  SELECTED_PREVIEW_SOURCE,
  describeDraftOrigin,
  isSelectedPreviewRecord,
  kstDateOf,
  kstDateTimeLabel,
  loadAISessionsDraft,
  saveAISessionsDraft,
  type AISessionsDraft,
} from "@/lib/aiSessionsDraft";

const FILTERS = {
  exclude_inverse: true,
  exclude_leveraged: false,
  exclude_synthetic: true,
  exclude_futures: true,
};
// 원문 — 줄바꿈 · 공백 · 부호 · %p · 쉼표를 그대로 넘겨야 한다.
const TEXT =
  "[대상]\n- KODEX AI반도체TOP2플러스 (395160) · 보유 종목(ETF)\n- 평가비중 +4.47% · 손익률 -34.83%  \n\n" +
  "[가격 흐름 · PC 저장 종가]\n- 단기 KODEX200 차이(저장일 수 기준) 5저장일 -4.70%p\n- 거래량 4,655,670주";

function okBody(over: Record<string, unknown> = {}) {
  return {
    status: "ok",
    target_kind: "holding",
    ticker: "395160",
    preview_text: TEXT,
    generated_at: "2026-10-18T22:44:05+09:00",
    evidence_as_of: {
      target_as_of_date: "2026-10-14",
      kodex200_as_of_date: "2026-10-14",
      vix_as_of_date: "2026-10-13",
    },
    ...over,
  };
}

type Call = { method: string; path: string; body: unknown };
let calls: Call[] = [];
let routes: Record<string, unknown> = {};
// 미리보기 응답을 붙잡아 두기(생성 중 상태 시험) — 켜면 풀어 줄 때까지 기다린다.
let holdPreview = false;
let release: (() => void)[] = [];
const fetchMock = vi.fn(async (url: string, init?: { method?: string; body?: string }) => {
  const path = url.replace("http://api.test", "");
  const method = init?.method ?? "GET";
  calls.push({ method, path, body: init?.body ? JSON.parse(init.body) : null });
  if (holdPreview && path === "/decision-draft/preview") {
    await new Promise<void>((r) => release.push(r));
  }
  const b = routes[`${method} ${path.split("?")[0]}`];
  if (b === undefined) return { ok: false, status: 404, text: async () => "" };
  return { ok: true, status: 200, text: async () => JSON.stringify(b) };
});

const ORIGINAL_TZ = process.env.TZ;
beforeEach(() => {
  calls = [];
  holdPreview = false;
  release = [];
  routes = { "POST /decision-draft/preview": okBody() };
  fetchMock.mockClear();
  window.sessionStorage.clear();
  vi.stubEnv("NEXT_PUBLIC_API_BASE", "http://api.test");
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  process.env.TZ = ORIGINAL_TZ;
});

function oldDraft(): AISessionsDraft {
  return {
    asof: "2026-10-14",
    filters: { ...FILTERS, exclude_leveraged: true },
    candidate_snapshot: Array.from({ length: 10 }, (_, i) => ({
      rank: i + 1,
      ticker: `T${i}`,
      name: `후보 ${i + 1}`,
      tags: [],
    })),
    question_text: "이전에 넘긴 후보 목록 질문",
    linked_market_refresh_id: null,
    draft_created_at: "2026-10-18T04:52:00.000Z", // KST 13:52
  };
}

async function generate() {
  fireEvent.click(screen.getByRole("button", { name: /판단 근거 미리보기 생성|다시 생성/ }));
  await waitFor(() => expect(screen.getByRole("button", { name: "다시 생성" })).toBeTruthy());
}

function card(over: Partial<Parameters<typeof DecisionDraftPreviewCard>[0]> = {}) {
  const onNavigate = vi.fn();
  const props = {
    targetKind: "holding" as const,
    ticker: "395160",
    displayName: "KODEX AI반도체TOP2플러스",
    screenFilters: FILTERS,
    onNavigate,
    ...over,
  };
  const r = render(<DecisionDraftPreviewCard {...props} />);
  return { ...r, onNavigate: (over.onNavigate as typeof onNavigate) ?? onNavigate, props };
}

describe("[AI 세션에서 검토] — 미리보기 → 초안", () => {
  it("보유 — 지금 보이는 응답 그대로 초안 · 질문 = 원문 · 가격 기준일 = 기록 기준일 · 이동", async () => {
    const { onNavigate } = card();
    expect(screen.queryByRole("button", { name: "AI 세션에서 검토" })).toBeNull(); // 생성 전 없음
    await generate();
    const before = fetchMock.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "AI 세션에서 검토" }));
    expect(fetchMock.mock.calls.length).toBe(before); // 다시 생성 · 재조회 없음
    const d = loadAISessionsDraft();
    expect(d).not.toBeNull();
    expect(d!.source_screen).toBe(SELECTED_PREVIEW_SOURCE);
    expect(d!.question_text).toBe(TEXT);
    expect(d!.asof).toBe("2026-10-14");
    expect(d!.filters).toEqual(FILTERS);
    expect(d!.candidate_snapshot).toEqual([
      {
        rank: null,
        ticker: "395160",
        name: "KODEX AI반도체TOP2플러스",
        tags: [],
        selected_preview: {
          target_kind: "holding",
          generated_at: "2026-10-18T22:44:05+09:00",
          evidence_as_of: okBody().evidence_as_of,
          preview_text: TEXT,
        },
      },
    ]);
    expect(d!.ml_baseline_evidence_snapshot ?? null).toBeNull();
    expect(onNavigate).toHaveBeenCalledWith("ai_sessions");
  });

  it("후보 — 전달 당시 목록 순위 · 종류 candidate", async () => {
    routes["POST /decision-draft/preview"] = okBody({ target_kind: "candidate", ticker: "475300" });
    card({ targetKind: "candidate", ticker: "475300", displayName: "SOL 반도체전공정", rank: 9 });
    await generate();
    fireEvent.click(screen.getByRole("button", { name: "AI 세션에서 검토" }));
    const c = loadAISessionsDraft()!.candidate_snapshot[0];
    expect(c.rank).toBe(9);
    expect(c.selected_preview?.target_kind).toBe("candidate");
  });

  it("가격 기준일 없음 — 기록 기준일 = 생성 시각의 KST 날짜 · 가격 기준일 칸은 비운 그대로", async () => {
    routes["POST /decision-draft/preview"] = okBody({
      generated_at: "2026-10-18T16:30:00+00:00", // KST 2026-10-19 01:30
      evidence_as_of: { target_as_of_date: null, kodex200_as_of_date: "2026-10-14", vix_as_of_date: null },
    });
    card();
    await generate();
    fireEvent.click(screen.getByRole("button", { name: "AI 세션에서 검토" }));
    const d = loadAISessionsDraft()!;
    expect(d.asof).toBe("2026-10-19");
    expect(d.candidate_snapshot[0].selected_preview?.evidence_as_of?.target_as_of_date).toBeNull();
  });

  it("넘길 수 없으면 버튼 없음 — 화면 필터 · 이동 함수 · 생성 시각 없음", async () => {
    const a = card({ screenFilters: undefined });
    await generate();
    expect(screen.queryByRole("button", { name: "AI 세션에서 검토" })).toBeNull();
    a.unmount();
    const b = card({ onNavigate: undefined });
    await generate();
    expect(screen.queryByRole("button", { name: "AI 세션에서 검토" })).toBeNull();
    b.unmount();
    routes["POST /decision-draft/preview"] = okBody({ generated_at: null });
    card();
    await generate();
    expect(screen.getByRole("button", { name: "복사" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "AI 세션에서 검토" })).toBeNull();
  });
});

describe("저장하지 않은 기존 초안 — 확인 줄(Q2 (a))", () => {
  it("조용히 덮지 않는다 · 출처와 KST 시각 · [취소]는 초안 · 미리보기 보존", async () => {
    saveAISessionsDraft(oldDraft());
    const { onNavigate } = card();
    await generate();
    fireEvent.click(screen.getByRole("button", { name: "AI 세션에서 검토" }));
    const row = screen.getByRole("alert");
    expect(row.textContent).toContain("「요즘 잘 오르는 ETF」 · 후보 10개 · 2026-10-18 13:52");
    expect(loadAISessionsDraft()).toEqual(oldDraft());
    expect(onNavigate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "취소" }));
    expect(screen.queryByRole("alert")).toBeNull();
    expect(loadAISessionsDraft()).toEqual(oldDraft());
    expect(screen.getByRole("button", { name: "AI 세션에서 검토" })).toBeTruthy(); // 미리보기 그대로
  });

  it("[바꾸고 이동]에서만 교체하고 이동", async () => {
    saveAISessionsDraft(oldDraft());
    const { onNavigate } = card();
    await generate();
    fireEvent.click(screen.getByRole("button", { name: "AI 세션에서 검토" }));
    fireEvent.click(screen.getByRole("button", { name: "바꾸고 이동" }));
    expect(loadAISessionsDraft()!.question_text).toBe(TEXT);
    expect(onNavigate).toHaveBeenCalledWith("ai_sessions");
  });

  it("확인 중 종목이 바뀌면 확인 줄을 닫고 전달 취소 · 예전 원문을 새 종목에 붙이지 않음", async () => {
    saveAISessionsDraft(oldDraft());
    const { rerender, props, onNavigate } = card();
    await generate();
    fireEvent.click(screen.getByRole("button", { name: "AI 세션에서 검토" }));
    expect(screen.getByRole("alert")).toBeTruthy();
    rerender(<DecisionDraftPreviewCard {...props} ticker="005930" displayName="삼성전자" />);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByRole("button", { name: "바꾸고 이동" })).toBeNull();
    expect(screen.queryByRole("button", { name: "AI 세션에서 검토" })).toBeNull();
    expect(loadAISessionsDraft()).toEqual(oldDraft());
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it("대상이 바뀐 바로 그 그림에도 예전 원문 버튼이 없다(비우기 효과 전)", async () => {
    // Probe 는 카드보다 앞 형제라 같은 그림에서 카드의 비우기 효과보다 먼저 실행된다.
    const seen: { name: boolean; button: boolean }[] = [];
    function Probe() {
      useEffect(() => {
        seen.push({
          name: (document.body.textContent ?? "").includes("대상: 삼성전자"),
          button: screen.queryByRole("button", { name: "AI 세션에서 검토" }) !== null,
        });
      });
      return null;
    }
    const onNavigate = vi.fn();
    const view = (tk: string, nm: string) => (
      <>
        <Probe />
        <DecisionDraftPreviewCard
          targetKind="holding"
          ticker={tk}
          displayName={nm}
          screenFilters={FILTERS}
          onNavigate={onNavigate}
        />
      </>
    );
    const { rerender } = render(view("395160", "KODEX AI반도체TOP2플러스"));
    await generate();
    expect(screen.getByRole("button", { name: "AI 세션에서 검토" })).toBeTruthy();
    seen.length = 0;
    rerender(view("005930", "삼성전자"));
    const first = seen.find((x) => x.name);
    expect(first).toBeDefined();
    expect(first!.button).toBe(false);
  });

  it("확인 중 후보 목록 조건이 바뀌어도 닫는다", async () => {
    saveAISessionsDraft(oldDraft());
    routes["POST /decision-draft/preview"] = okBody({ target_kind: "candidate", ticker: "475300" });
    const { rerender, props } = card({
      targetKind: "candidate",
      ticker: "475300",
      rank: 9,
      listQuery: { basis: "one_month" },
    });
    await generate();
    fireEvent.click(screen.getByRole("button", { name: "AI 세션에서 검토" }));
    rerender(<DecisionDraftPreviewCard {...props} listQuery={{ basis: "three_month" }} />);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(loadAISessionsDraft()).toEqual(oldDraft());
  });

  it("확인 중 [다시 생성]을 누르면 닫는다", async () => {
    saveAISessionsDraft(oldDraft());
    card();
    await generate();
    fireEvent.click(screen.getByRole("button", { name: "AI 세션에서 검토" }));
    expect(screen.getByRole("alert")).toBeTruthy();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "다시 생성" }));
    });
    expect(screen.queryByRole("alert")).toBeNull();
    expect(loadAISessionsDraft()).toEqual(oldDraft());
  });
});

describe("생성 중 · 새 결과 도착 · 초안 출처", () => {
  it("다시 생성 중에는 [AI 세션에서 검토]가 없고, 새 결과가 오면 확인 줄은 닫혀 있다", async () => {
    saveAISessionsDraft(oldDraft());
    card();
    await generate();
    holdPreview = true;
    fireEvent.click(screen.getByRole("button", { name: "다시 생성" }));
    await waitFor(() => expect(release.length).toBe(1));
    expect(screen.queryByRole("button", { name: "AI 세션에서 검토" })).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    await act(async () => {
      release[0]();
    });
    await waitFor(() => expect(screen.getByRole("button", { name: "AI 세션에서 검토" })).toBeTruthy());
    expect(screen.queryByRole("alert")).toBeNull();
    expect(loadAISessionsDraft()).toEqual(oldDraft());
  });

  it("확인 줄이 떠 있을 때 [다시 생성] — 생성 중에도 닫혀 있고, 실패해도 다시 열리지 않는다", async () => {
    saveAISessionsDraft(oldDraft());
    card();
    await generate();
    fireEvent.click(screen.getByRole("button", { name: "AI 세션에서 검토" }));
    expect(screen.getByRole("alert")).toBeTruthy();
    holdPreview = true;
    routes["POST /decision-draft/preview"] = { status: "error", message: "자료 없음" };
    fireEvent.click(screen.getByRole("button", { name: "다시 생성" }));
    await waitFor(() => expect(release.length).toBe(1));
    expect(screen.queryByRole("button", { name: "바꾸고 이동" })).toBeNull(); // 생성 중
    await act(async () => {
      release[0]();
    });
    await waitFor(() => expect(screen.getByText("자료 없음")).toBeTruthy());
    expect(screen.queryByRole("button", { name: "바꾸고 이동" })).toBeNull(); // 실패 뒤
    expect(screen.queryByRole("button", { name: "AI 세션에서 검토" })).toBeNull();
    expect(loadAISessionsDraft()).toEqual(oldDraft());
  });

  it("「ETF 구성종목」 초안은 분석 전(null)이어도 그 출처 · 시각이 없으면 시각 생략", () => {
    const etf = { ...oldDraft(), constituent_snapshot: null, overlap_snapshot: null };
    expect(describeDraftOrigin(etf)).toBe("「ETF 구성종목」 · 후보 10개 · 2026-10-18 13:52");
    expect(describeDraftOrigin(oldDraft())).toBe("「요즘 잘 오르는 ETF」 · 후보 10개 · 2026-10-18 13:52");
    const noTime = { ...oldDraft(), draft_created_at: undefined as unknown as string };
    expect(describeDraftOrigin(noTime)).toBe("「요즘 잘 오르는 ETF」 · 후보 10개");
    expect(describeDraftOrigin(selectedDraft())).toBe(
      "「보유와 비교」 판단 근거 미리보기 · KODEX AI반도체TOP2플러스 · 2026-10-18 22:44",
    );
  });
});

describe("KST 표시 — 브라우저 시간대와 무관", () => {
  it.each([
    ["2026-10-18T04:52:00.000Z", "2026-10-18 13:52", "2026-10-18"],
    ["2026-10-18T15:30:00.000Z", "2026-10-19 00:30", "2026-10-19"],
    ["2026-10-18T22:44:05+09:00", "2026-10-18 22:44", "2026-10-18"],
  ])("%s → %s", (iso, label, date) => {
    for (const tz of ["America/New_York", "UTC", "Asia/Seoul"]) {
      process.env.TZ = tz;
      expect(kstDateTimeLabel(iso)).toBe(label);
      expect(kstDateOf(iso)).toBe(date);
    }
  });

  it.each([
    ["2026-10-18T20:00:00", "2026-10-18 20:00", "2026-10-18"], // 시간대 없음 = KST(백엔드와 같은 규칙)
    ["2026-10-18 20:00:00", "2026-10-18 20:00", "2026-10-18"],
    ["2026-10-18", "2026-10-18 00:00", "2026-10-18"],
    [" 2026-10-18T22:44:05+09:00 ", "2026-10-18 22:44", "2026-10-18"],
  ])("시간대 없는 값 · 공백 %s → KST 로 읽음", (iso, label, date) => {
    for (const tz of ["America/New_York", "UTC", "Asia/Seoul"]) {
      process.env.TZ = tz;
      expect(kstDateTimeLabel(iso)).toBe(label);
      expect(kstDateOf(iso)).toBe(date);
    }
  });

  it("해석 못 하면 원문(라벨) · null(날짜)", () => {
    expect(kstDateTimeLabel("어제 저녁")).toBe("어제 저녁");
    expect(kstDateOf("어제 저녁")).toBeNull();
    expect(kstDateOf(null)).toBeNull();
  });
});

function selectedDraft(over: Partial<AISessionsDraft> = {}, sp: Record<string, unknown> = {}): AISessionsDraft {
  return {
    asof: "2026-10-14",
    filters: FILTERS,
    candidate_snapshot: [
      {
        rank: null,
        ticker: "395160",
        name: "KODEX AI반도체TOP2플러스",
        tags: [],
        selected_preview: {
          target_kind: "holding",
          generated_at: "2026-10-18T22:44:05+09:00",
          evidence_as_of: okBody().evidence_as_of,
          preview_text: TEXT,
          ...sp,
        } as never,
      },
    ],
    question_text: TEXT,
    linked_market_refresh_id: null,
    draft_created_at: "2026-10-18T13:44:10.000Z",
    source_screen: SELECTED_PREVIEW_SOURCE,
    ...over,
  };
}

describe("작성 화면 — 선택 근거 모드", () => {
  it("선택 종목 묶음 · 질문 = 원문 · 저장 = 화면 값 · 원문 그대로 · ML 자동 보충 없음", async () => {
    routes["POST /decision/sessions"] = { status: "ok", id: "decision_x", created_at: "t" };
    const onSaved = vi.fn();
    const { container } = render(<AISessionsCreateTab draft={selectedDraft()} onSaved={onSaved} />);
    const box = container.querySelector(".ais-selected")!;
    expect(box.textContent).toContain("KODEX AI반도체TOP2플러스 (395160) · 보유");
    expect(box.textContent).toContain("미리보기 생성 2026-10-18 22:44");
    expect(box.textContent).toContain("가격 기준일 2026-10-14");
    expect(box.textContent).toContain("당시 화면의 후보 목록 필터 인버스 제외 · 합성 제외 · 선물형 제외");
    expect(box.textContent).not.toContain("미리보기 생성일 사용");
    expect(screen.queryByText("기준일 (asof)")).toBeNull();
    expect(screen.queryByText("후보 스냅샷")).toBeNull();
    expect(screen.getByText(/「보유와 비교」 판단 근거 미리보기에서 넘어온 선택 종목/)).toBeTruthy();
    const q = container.querySelector("#ais-question") as HTMLTextAreaElement;
    expect(q.value).toBe(TEXT);
    fireEvent.change(q, { target: { value: "(내 질문)\n\n" + TEXT } });
    fireEvent.change(container.querySelector("#ais-gpt")!, { target: { value: "GPT 답변" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "기록 저장" }));
    });
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(calls.some((c) => c.path.startsWith("/ml/"))).toBe(false);
    const post = calls.find((c) => c.method === "POST" && c.path === "/decision/sessions")!;
    const body = post.body as Record<string, unknown>;
    expect(body.source_screen).toBe(SELECTED_PREVIEW_SOURCE);
    expect(body.asof).toBe("2026-10-14");
    expect(body.filters).toEqual(FILTERS);
    expect(body.question_text).toBe("(내 질문)\n\n" + TEXT);
    expect(body.candidate_snapshot).toEqual(selectedDraft().candidate_snapshot);
    for (const k of [
      "market_context_snapshot",
      "constituent_snapshot",
      "overlap_snapshot",
      "short_term_momentum_snapshot",
      "data_quality_snapshot",
      "ml_baseline_evidence_snapshot",
    ]) {
      expect(body[k]).toBeNull();
    }
  });

  it("가격 기준일 없음 — '미확인' · 기록 기준일 = 미리보기 생성일 사용", () => {
    const d = selectedDraft(
      { asof: "2026-10-19" },
      { evidence_as_of: { target_as_of_date: null, kodex200_as_of_date: "2026-10-14", vix_as_of_date: null } },
    );
    const { container } = render(<AISessionsCreateTab draft={d} onSaved={() => {}} />);
    const box = container.querySelector(".ais-selected")!;
    expect(box.textContent).toContain("가격 기준일 미확인");
    expect(box.textContent).toContain("기록 기준일 2026-10-19 — 미리보기 생성일 사용");
  });

  it("가격 기준일이 빈 글자여도 '미확인'(공백 표시 아님)", () => {
    const d = selectedDraft(
      { asof: "2026-10-18" },
      { evidence_as_of: { target_as_of_date: "", kodex200_as_of_date: "2026-10-14", vix_as_of_date: null } },
    );
    const { container } = render(<AISessionsCreateTab draft={d} onSaved={() => {}} />);
    const box = container.querySelector(".ais-selected")!;
    expect(box.textContent).toContain("가격 기준일 미확인");
    expect(box.textContent).toContain("기록 기준일 2026-10-18 — 미리보기 생성일 사용");
  });

  it("기존 전체 후보 전달 초안은 그대로 — 기준일 · 필터 · 후보 · ML 보충 · market_discovery", async () => {
    routes["POST /decision/sessions"] = { status: "ok", id: "decision_y", created_at: "t" };
    routes["GET /ml/baseline-v0/evidence-snapshot"] = { status: "ok" };
    const onSaved = vi.fn();
    const { container } = render(<AISessionsCreateTab draft={oldDraft()} onSaved={onSaved} />);
    expect(container.querySelector(".ais-selected")).toBeNull();
    expect(screen.getByText("기준일 (asof)")).toBeTruthy();
    expect(screen.getByText("후보 스냅샷")).toBeTruthy();
    fireEvent.change(container.querySelector("#ais-gpt")!, { target: { value: "GPT 답변" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "기록 저장" }));
    });
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    const body = calls.find((c) => c.method === "POST" && c.path === "/decision/sessions")!
      .body as Record<string, unknown>;
    expect(body.source_screen).toBe("market_discovery");
    expect(body.ml_baseline_evidence_snapshot).toEqual({ status: "ok" });
    expect((body.candidate_snapshot as unknown[]).length).toBe(10);
  });

  it("화면 값만 같고 후보가 2건이면 선택 근거 모드가 아니다", () => {
    const d = selectedDraft();
    d.candidate_snapshot = [d.candidate_snapshot[0], { rank: 2, ticker: "X", name: "x", tags: [] }];
    expect(isSelectedPreviewRecord(d.source_screen, d.candidate_snapshot)).toBe(false);
    const { container } = render(<AISessionsCreateTab draft={d} onSaved={() => {}} />);
    expect(container.querySelector(".ais-selected")).toBeNull();
  });
});

function record(over: Record<string, unknown> = {}, sp: Record<string, unknown> = {}) {
  return {
    id: "decision_sel",
    created_at: "2026-10-18T22:50:00.000000+0900",
    updated_at: "2026-10-18T22:50:00.000000+0900",
    asof: "2026-10-14",
    source_screen: SELECTED_PREVIEW_SOURCE,
    filters: FILTERS,
    candidate_snapshot: [
      {
        rank: null,
        ticker: "395160",
        name: "KODEX AI반도체TOP2플러스",
        tags: [],
        selected_preview: {
          target_kind: "holding",
          generated_at: "2026-10-18T22:44:05+09:00",
          evidence_as_of: okBody().evidence_as_of,
          preview_text: TEXT,
          ...sp,
        },
      },
    ],
    question_text: TEXT,
    gpt_answer_text: "GPT 답변",
    gemini_answer_text: "",
    claude_answer_text: "",
    user_memo: "다음 주 확인",
    user_verdict: "needs_market_compare",
    next_checks: [],
    linked_market_refresh_id: null,
    ...over,
  };
}

async function openList(rec: Record<string, unknown>, rows: Record<string, unknown>[]) {
  routes["GET /decision/sessions"] = { status: "ok", records: rows };
  routes[`GET /decision/sessions/${rec.id}`] = { status: "ok", record: rec };
  const r = render(<AISessionsListTab reloadTrigger={0} />);
  await waitFor(() => expect(screen.getAllByRole("button", { name: "보기" }).length).toBe(rows.length));
  await act(async () => {
    fireEvent.click(screen.getAllByRole("button", { name: "보기" })[0]);
  });
  await waitFor(() => expect(screen.getByText(`기록 상세 — ${rec.id}`)).toBeTruthy());
  return r;
}

function row(id: string, over: Record<string, unknown> = {}) {
  return {
    id,
    created_at: "2026-10-18T22:50:00.000000+0900",
    asof: "2026-10-14",
    source_screen: SELECTED_PREVIEW_SOURCE,
    user_verdict: "hold",
    summary: "다음 주 확인",
    candidate_count: 1,
    has_gpt_answer: true,
    has_gemini_answer: false,
    has_claude_answer: false,
    ...over,
  };
}

describe("기록 조회 — 목록 대상 · 상세 선택 종목 · 넘겨받은 원문", () => {
  it("목록 요약 앞 [이름(티커)] · 없는 기록은 그대로 · 상세(질문 그대로 = 원문 한 번)", async () => {
    const { container } = await openList(record(), [
      row("decision_sel", { target_label: "KODEX AI반도체TOP2플러스(395160)" }),
      row("decision_old", { source_screen: "market_discovery", candidate_count: 10, summary: "옛 기록" }),
    ]);
    const cells = Array.from(container.querySelectorAll("tbody tr")).map((tr) => tr.textContent ?? "");
    expect(cells[0]).toContain("[KODEX AI반도체TOP2플러스(395160)] 다음 주 확인");
    expect(cells[1]).not.toContain("[");
    const detail = container.querySelector(".decision-detail-card")!;
    const t = detail.textContent ?? "";
    expect(t).toContain("기록 기준일: 2026-10-14");
    expect(t).not.toContain("미리보기 생성일 사용");
    expect(t).toContain("당시 화면의 후보 목록 필터");
    expect(t).not.toContain("필터 조건");
    expect(t).toContain("선택 종목 (저장 시점)");
    expect(t).toContain("보유 · KODEX AI반도체TOP2플러스 (395160)");
    expect(t).not.toContain("1. KODEX");
    expect(t).toContain("넘겨받은 판단 근거 (원문)");
    expect(t).toContain("보유 · 미리보기 생성 2026-10-18 22:44 · 가격 기준일 2026-10-14 · 아래 AI 질문과 같은 글");
    const pres = Array.from(detail.querySelectorAll("pre")).map((p) => p.textContent);
    expect(pres.filter((p) => p === TEXT).length).toBe(1); // 같은 글 두 번 안 보임
  });

  it("질문을 고쳐 저장한 후보 — 원문을 따로 · 당시 목록 n위", async () => {
    const rec = record(
      {
        id: "decision_c",
        question_text: "(내 질문)\n\n" + TEXT,
        candidate_snapshot: [
          {
            rank: 9,
            ticker: "475300",
            name: "SOL 반도체전공정",
            tags: [],
            selected_preview: { ...record().candidate_snapshot[0].selected_preview, target_kind: "candidate" },
          },
        ],
      },
      {},
    );
    const { container } = await openList(rec, [row("decision_c")]);
    const detail = container.querySelector(".decision-detail-card")!;
    const t = detail.textContent ?? "";
    expect(t).toContain("후보 · 당시 화면 목록 9위 · SOL 반도체전공정 (475300)");
    expect(t).toContain("아래 AI 질문은 저장 때 편집됨");
    const pres = Array.from(detail.querySelectorAll("pre")).map((p) => p.textContent);
    expect(pres).toContain(TEXT);
    expect(pres).toContain("(내 질문)\n\n" + TEXT);
  });

  it("가격 기준일 없는 기록 — 기록 기준일 · 미리보기 생성일 사용 · 가격 기준일 미확인", async () => {
    const rec = record(
      { id: "decision_n", asof: "2026-10-19" },
      { evidence_as_of: { target_as_of_date: null, kodex200_as_of_date: "2026-10-14", vix_as_of_date: null } },
    );
    const { container } = await openList(rec, [row("decision_n")]);
    const t = container.querySelector(".decision-detail-card")!.textContent ?? "";
    expect(t).toContain("기록 기준일: 2026-10-19 — 미리보기 생성일 사용 · 가격 기준일 미확인");
    expect(t).toContain("가격 기준일 미확인 · 아래 AI 질문과 같은 글");
  });

  it("일반 후보 1건 기록은 선택 근거 모드가 아니다 — 기존 표시 그대로", async () => {
    const rec = record({
      id: "decision_plain",
      source_screen: "market_discovery",
      candidate_snapshot: [{ rank: 1, ticker: "139260", name: "TIGER 200 IT", tags: [] }],
    });
    const { container } = await openList(rec, [row("decision_plain", { source_screen: "market_discovery" })]);
    const t = container.querySelector(".decision-detail-card")!.textContent ?? "";
    expect(t).toContain("기준일: 2026-10-14");
    expect(t).not.toContain("기록 기준일");
    expect(t).toContain("필터 조건");
    expect(t).toContain("후보 스냅샷 (저장 시점)");
    expect(t).toContain("1. TIGER 200 IT (139260)");
    expect(t).not.toContain("넘겨받은 판단 근거");
  });
});

// POC6-07 — 이동평균 세 줄 · [검토 질문] 이 든 원문(10개 묶음)도 화면 · [복사] · 초안 · 저장이 같은 글.
// 화면은 응답 선택 필드(moving_average)로 숫자 글을 다시 만들지 않는다 · 과거(이동평균 없는) 기록은 그대로.
const TEXT_607 = [
  "[대상]\n- 시험 ETF (0015K0) · 보유 종목(ETF)\n- 평가비중 +1.00% · 손익률 -2.00%",
  "[시장]\n- 시장 국면: 하락장 · 8거래일째 (KODEX200 2026-10-20 기준)",
  "[시장 흐름 — 수급 · 환율 · 유가 · 기간 6개월 · 2026-04-20 ~ 2026-10-19]\n- 코스피 6,191.92 → 5,768.01 (-6.85%)",
  "[가격 흐름 · PC 저장 종가]\n- 변화율 5저장일 -10.37% · 10저장일 -14.67% · 20저장일 -7.17% (2026-09-16 → 2026-10-20)\n" +
    "- 종목 이동평균: MA20 18,896.75원 · MA60 18,769.25원\n" +
    "- 표시값 기준 위치: MA20 > MA60 > 종가 (종가 16,775.00원)\n" +
    "- 이동평균 계산 구간: MA20 = 저장 종가 20개(2026-09-17 → 2026-10-20) · MA60 = 저장 종가 60개(2026-07-22 → 2026-10-20)\n" +
    "- 단기 KODEX200 차이(저장일 수 기준) 5저장일 -1.45%p",
  "[KODEX200 동일 기간 비교]\n- 1개월 · 3개월: 값 없음",
  "[거래량]\n- 2026-10-20 거래량 210,255주",
  "[가격 흔들림]\n- 최근 20구간 2.35% · 직전 20구간 1.70% · 직전보다 커짐",
  "[중복 · 자료 상태]\n- NAV 괴리율 -0.46% (NAV 16,852 · 시장가 16,775 · 2026-10-20)",
  "[AI에게 요청]\n- 위 관측값을 ① 함께 확인되는 사실 ② 가능한 다른 해석 ③ 추가로 확인할 사항으로 나눠 정리해 주세요.",
  "[검토 질문]\n- 진입 검토: 이 ETF를 검토할 때 유리한 근거와 반대 근거는 무엇인가요?\n" +
    "- 보유 점검: 이미 보유 중이라면 어떤 변화와 주의 요인을 확인해야 하나요?\n" +
    "- 판단 한계: 지금 자료로 판단할 수 없는 부분과 추가 확인할 정보는 무엇인가요?",
].join("\n\n");
// 원문과 일부러 다른 숫자 — 화면이 이 필드로 글을 만들면 드러난다.
const MA_FIELD = { status: "ok", d: "2026-10-20", close: 1, close_shown: "1.00", relation: "종가 > MA20 > MA60" };

describe("POC6-07 — 이동평균 줄 · 검토 질문이 든 원문", () => {
  it("상자 10개 · 상자 글 = 원문 · [복사] = 원문 · 초안 질문 · 원문 보관 = 같은 글 · 선택 필드는 쓰지 않음", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    routes["POST /decision-draft/preview"] = okBody({ ticker: "0015K0", preview_text: TEXT_607, moving_average: MA_FIELD });
    const { container } = card({ ticker: "0015K0", displayName: "시험 ETF" });
    await generate();
    const secs = Array.from(container.querySelectorAll(".ddp-sec"));
    expect(secs).toHaveLength(10);
    expect(secs.map((s) => s.querySelector(".ddp-sec-t")?.textContent).slice(-2)).toEqual(["AI에게 요청", "검토 질문"]);
    const rebuilt = secs
      .map((s) => `[${s.querySelector(".ddp-sec-t")?.textContent}]\n${s.querySelector(".ddp-sec-b")?.textContent}`)
      .join("\n\n");
    expect(rebuilt).toBe(TEXT_607);
    expect(container.textContent).not.toContain("1.00원"); // 선택 필드 숫자를 그리지 않음
    fireEvent.click(screen.getByRole("button", { name: "복사" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(TEXT_607));
    fireEvent.click(screen.getByRole("button", { name: "AI 세션에서 검토" }));
    const d = loadAISessionsDraft()!;
    expect(d.question_text).toBe(TEXT_607);
    expect(d.candidate_snapshot[0].selected_preview?.preview_text).toBe(TEXT_607);
    expect(JSON.stringify(d)).not.toContain("moving_average"); // 세션 구조 그대로(새 필드 없음)
  });

  it("작성 화면 — 질문을 고쳐 저장해도 넘겨받은 원문(이동평균 · 질문 포함)은 그대로 보관", async () => {
    routes["POST /decision/sessions"] = { status: "ok", id: "decision_607", created_at: "t" };
    const draft = selectedDraft({ question_text: TEXT_607 }, { preview_text: TEXT_607 });
    const { container } = render(<AISessionsCreateTab draft={draft} onSaved={vi.fn()} />);
    const q = container.querySelector("#ais-question") as HTMLTextAreaElement;
    expect(q.value).toBe(TEXT_607);
    fireEvent.change(q, { target: { value: "진입 검토만 해 주세요." } });
    fireEvent.change(container.querySelector("#ais-gpt")!, { target: { value: "GPT 답변" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "기록 저장" }));
    });
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/decision/sessions")).toBe(true));
    const body = calls.find((c) => c.method === "POST" && c.path === "/decision/sessions")!.body as {
      question_text: string;
      candidate_snapshot: { selected_preview: { preview_text: string } }[];
    };
    expect(body.question_text).toBe("진입 검토만 해 주세요.");
    expect(body.candidate_snapshot[0].selected_preview.preview_text).toBe(TEXT_607);
  });

  it("이동평균 없는 과거 기록 — 당시 원문 그대로 · 현재 값으로 보충하지 않음", async () => {
    const { container } = await openList(record({ id: "decision_old607" }), [row("decision_old607")]);
    const detail = container.querySelector(".decision-detail-card")!;
    const pres = Array.from(detail.querySelectorAll("pre")).map((p) => p.textContent);
    expect(pres).toContain(TEXT);
    expect(detail.textContent).not.toContain("종목 이동평균");
    expect(detail.textContent).not.toContain("검토 질문");
    expect(calls.some((c) => c.path.startsWith("/decision-draft"))).toBe(false); // 다시 만들지 않음
  });
});
