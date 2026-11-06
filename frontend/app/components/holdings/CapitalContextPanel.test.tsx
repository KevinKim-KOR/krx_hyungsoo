// POC6-24 — 자금 기준 카드 · 종목 행 둘째 줄 · 미리보기 버튼 근처 금액 안내(가상 금액).
// 상태별 글(미입력 · 0원 · 미정 · 계산 안 함 · 확인 불가) · 저장 실패 때 입력 유지 · 편집 중 값 미사용 ·
// 저장 요청 = 원 단위 정수. 진짜 saveCapitalContext · request 를 쓰고 fetch 만 가짜다.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CapitalContextPanel, { parseWon, refusedBeforeWrite } from "./CapitalContextPanel";
import { ApiRequestError } from "@/lib/api";
import EnrichedSection from "../EnrichedHoldingsSection";
import DecisionDraftPreviewCard, { AMOUNT_NOTE } from "../holdings_compare/DecisionDraftPreviewCard";
import type { CapitalView, EnrichedHolding } from "@/lib/api";

function view(over: Partial<CapitalView> = {}): CapitalView {
  return {
    status: "ENTERED",
    cash_krw: 400000,
    limit_krw: 100000,
    confirmed_on: "2026-11-05",
    saved_at: "2026-11-05T10:00:00+09:00",
    holdings_value: 600000,
    holdings_rows: 2,
    priced_rows: 2,
    complete: true,
    price_date: { state: "KNOWN", min: "2026-11-05", max: "2026-11-05" },
    total_krw: 1000000,
    total_reason: null,
    holdings_share_pct: 60,
    cash_share_pct: 40,
    same_day: true,
    ...over,
  };
}

const NOT_ENTERED = view({
  status: "NOT_ENTERED",
  cash_krw: null,
  limit_krw: null,
  confirmed_on: null,
  saved_at: null,
  total_krw: null,
  total_reason: "NO_CASH",
  holdings_share_pct: null,
  cash_share_pct: null,
  same_day: null,
});

type Call = { url: string; method?: string; body: unknown };
let calls: Call[] = [];
let reply: { status: number; body: unknown } = { status: 200, body: {} };
const fetchMock = vi.fn(async (url: string, init?: { method?: string; body?: string }) => {
  calls.push({ url, method: init?.method, body: init?.body ? JSON.parse(init.body) : null });
  return {
    ok: reply.status < 400,
    status: reply.status,
    text: async () => JSON.stringify(reply.body),
  };
});

beforeEach(() => {
  calls = [];
  reply = { status: 200, body: {} };
  fetchMock.mockClear();
  vi.stubEnv("NEXT_PUBLIC_API_BASE", "http://api.test");
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

const panel = () => screen.getByTestId("capital-panel");

describe("자금 기준 카드 — 상태별 글", () => {
  it("미입력: 0원이 아니라 '미입력' · 합계는 현금을 넣으면 계산", () => {
    render(<CapitalContextPanel capital={NOT_ENTERED} onSaved={() => {}} />);
    const t = panel().textContent ?? "";
    expect(t).toContain("아직 입력하지 않음");
    expect(t).toContain("현금 미입력 — 보유 + 입력 현금 합계");
    expect(screen.getAllByText("미입력")).toHaveLength(2);
    const cells = Array.from(panel().querySelectorAll(".cap-grid > div")).map((c) => c.textContent);
    expect(cells.slice(0, 3)).toEqual(["검토에 포함할 현금미입력", "이번 검토의 추가 투입 한도미입력", "현금 · 한도 확인일—"]);
    expect(screen.getByRole("button", { name: "입력" })).toBeTruthy();
  });

  it("입력됨: 합계 · 구성 · 한도는 합계에 더하지 않음 · 확인일 · 자동 반영 안 됨", () => {
    render(<CapitalContextPanel capital={view()} onSaved={() => {}} />);
    const t = panel().textContent ?? "";
    expect(t).toContain("보유 + 입력 현금 합계 1,000,000원");
    expect(t).toContain("보유 60% · 현금 40%");
    expect(t).toContain("400,000원");
    expect(t).toContain("100,000원");
    expect(t).toContain("합계에 더하지 않음");
    expect(t).toContain("직접 입력 · 확인일 2026-11-05");
    expect(t).toContain("거래 · 입출금 뒤 자동으로 바뀌지 않습니다");
    expect(t).toContain("투자 총예산 · 전체 재산이 아닙니다");
    expect(t).not.toContain("기준일이 다른 참고 합계"); // 같은 기준일
  });

  it("한도 비움 = 미정(현금 전액을 한도로 보지 않음) · 0원은 '직접 입력한 0원'", () => {
    render(
      <CapitalContextPanel
        capital={view({ cash_krw: 0, limit_krw: null, total_krw: 600000, holdings_share_pct: 100, cash_share_pct: 0 })}
        onSaved={() => {}}
      />,
    );
    const t = panel().textContent ?? "";
    expect(t).toContain("미정");
    expect(t).toContain("현금 전액을 한도로 보지 않음");
    expect(t).toContain("직접 입력한 0원");
    expect(t).toContain("보유 100% · 현금 0%");
  });

  it("합계 0원은 알려진 금액 · 구성만 계산 불가 · 보유 없음 = 가격 기준일 대상 없음", () => {
    render(
      <CapitalContextPanel
        capital={view({
          cash_krw: 0,
          limit_krw: null,
          holdings_value: 0,
          holdings_rows: 0,
          priced_rows: 0,
          price_date: { state: "NO_HOLDINGS", min: null, max: null },
          total_krw: 0,
          holdings_share_pct: null,
          cash_share_pct: null,
          same_day: null,
        })}
        onSaved={() => {}}
      />,
    );
    const t = panel().textContent ?? "";
    expect(t).toContain("보유 + 입력 현금 합계 0원");
    expect(t).toContain("보유 · 현금 구성 계산 불가(합계 0원)");
    expect(t).toContain("보유 없음 · 가격 기준일 대상 없음");
  });

  it("부분 평가: 합계 · 구성을 그리지 않고 부분 합계라고 적음 · 현금 · 한도는 보임", () => {
    render(
      <CapitalContextPanel
        capital={view({
          holdings_value: 500000,
          priced_rows: 1,
          complete: false,
          total_krw: null,
          total_reason: "PARTIAL",
          holdings_share_pct: null,
          cash_share_pct: null,
          same_day: null,
        })}
        onSaved={() => {}}
      />,
    );
    const t = panel().textContent ?? "";
    expect(t).toContain("보유 1/2종목만 시세 확인");
    expect(t).not.toContain("보유 + 입력 현금 합계 ");
    expect(t).toContain("부분 합계 · 1/2종목");
    expect(t).toContain("400,000원");
  });

  it("기준일이 다르면 기본 화면에 '기준일이 다른 참고 합계'", () => {
    render(
      <CapitalContextPanel
        capital={view({ confirmed_on: "2026-11-06", same_day: false })}
        onSaved={() => {}}
      />,
    );
    const t = panel().textContent ?? "";
    expect(t).toContain("가격 기준일(2026-11-05)과 현금 확인일(2026-11-06)이 달라 기준일이 다른 참고 합계 · 비중");
    expect(t).toContain("‘입력 현금 포함’ 비중 포함");
  });

  it.each([
    [
      "자금 기준 읽기 실패",
      view({ status: "READ_FAILED", cash_krw: null, limit_krw: null, total_krw: null }),
      "자금 기준을 불러오지 못했습니다",
      true,
    ],
    ["보유 응답 실패", null, "보유 현황을 불러오지 못해 자금 기준도 확인할 수 없습니다", false],
  ])("%s: '확인 불가' · 0원으로 보지 않음 · 입력 버튼 잠금", (_l, cap, head, usable) => {
    render(<CapitalContextPanel capital={cap} onSaved={() => {}} />);
    const t = panel().textContent ?? "";
    expect(t).toContain("확인 불가");
    expect(t).toContain(head);
    expect(t).toContain("0원으로 보지 않습니다");
    // 보유 응답이 실패했을 때는 '보유 조회는 그대로 쓸 수 있다'고 안내하지 않는다
    expect(t.includes("그대로 쓸 수 있습니다")).toBe(usable);
    expect((screen.getByRole("button", { name: "입력·수정" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("가격 기준일 확인 불가면 합계 · 비중을 같은 기준일로 보지 않는다고 적음", () => {
    render(
      <CapitalContextPanel
        capital={view({ price_date: { state: "UNKNOWN", min: null, max: null }, same_day: null })}
        onSaved={() => {}}
      />,
    );
    expect(panel().textContent).toContain("같은 기준일의 합계 · 비중으로 보지 않습니다");
  });

  it("보유가 있으면 화면 행(계좌 행)과 미리보기(종목 합산)의 집계 단위를 기본 화면에 적음", () => {
    const { unmount } = render(<CapitalContextPanel capital={view()} onSaved={() => {}} />);
    expect(panel().textContent).toContain("종목 행의 비중은 계좌 행마다 따로 계산합니다");
    expect(panel().textContent).toContain("같은 종목의 모든 계좌 합산");
    unmount();
    render(
      <CapitalContextPanel
        capital={view({ holdings_rows: 0, priced_rows: 0, price_date: { state: "NO_HOLDINGS", min: null, max: null } })}
        onSaved={() => {}}
      />,
    );
    expect(panel().textContent).not.toContain("계좌 행마다");
  });
});

describe("자금 기준 카드 — 편집 · 저장", () => {
  function openEdit(cap: CapitalView = view(), onSaved = vi.fn()) {
    render(<CapitalContextPanel capital={cap} onSaved={onSaved} />);
    fireEvent.click(screen.getByRole("button", { name: /입력/ }));
    return onSaved;
  }
  const cash = () => screen.getByLabelText("검토에 포함할 현금(원)") as HTMLInputElement;
  const limit = () => screen.getByLabelText("이번 검토의 추가 투입 한도(원)") as HTMLInputElement;
  const day = () => screen.getByLabelText("현금 · 한도 확인일") as HTMLInputElement;

  it("저장값으로 채워 열고 · 저장 = 원 단위 정수 한 묶음 · 성공 뒤 onSaved", async () => {
    const onSaved = openEdit();
    expect(cash().value).toBe("400,000");
    expect(limit().value).toBe("100,000");
    expect(day().value).toBe("2026-11-05");
    expect(panel().textContent).toContain("편집 중 — 저장 전 값은 합계 · 비중 · AI 근거에 쓰지 않음");
    fireEvent.change(cash(), { target: { value: "500,000" } });
    reply = { status: 200, body: { status: "ENTERED", cash_krw: 500000, limit_krw: 100000, confirmed_on: "2026-11-05", saved_at: null } };
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
    expect(calls).toHaveLength(1);
    expect(calls[0].method).toBe("PUT");
    expect(calls[0].url).toBe("http://api.test/holdings/capital-context");
    expect(calls[0].body).toEqual({ cash_krw: 500000, limit_krw: 100000, confirmed_on: "2026-11-05" });
    // 화면 숫자는 다시 읽은 서버 값으로만 바뀐다(이 시험에선 prop 그대로).
    expect(panel().textContent).toContain("400,000원");
  });

  it("저장 실패: 서버 사유 · 입력값 유지 · onSaved 없음", async () => {
    const onSaved = openEdit();
    fireEvent.change(limit(), { target: { value: "500000" } });
    reply = { status: 422, body: { detail: "추가 투입 한도가 검토에 포함할 현금보다 클 수 없습니다." } };
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("클 수 없습니다"));
    expect(screen.getByRole("alert").textContent).toContain("저장된 값은 바뀌지 않았습니다");
    expect(limit().value).toBe("500000");
    expect(onSaved).not.toHaveBeenCalled();
  });

  // 검증자 r1 F1 — 요청을 보낸 뒤 결과를 받지 못하면 서버에 이미 저장됐을 수 있다:
  //   '저장된 값은 바뀌지 않았습니다'로 단정하지 않고 서버 값을 다시 읽는다 · 입력값은 유지.
  it.each([
    ["최초 입력 · 응답 유실", "first", "network"],
    ["수정 · 응답 유실", "modify", "network"],
    ["비우기 · 응답 유실", "clear", "network"],
    ["수정 · 예상 밖 서버 오류(500)", "modify", "500"],
    ["수정 · 중계 오류(502)", "modify", "502"],
  ])("%s: 결과 모름 안내 · 다시 읽기 · 입력 유지", async (_l, mode, fail) => {
    const clear = mode === "clear";
    const fetchSaveThenFail = vi.fn(async (url: string, init?: { method?: string; body?: string }) => {
      calls.push({ url, method: init?.method, body: init?.body ? JSON.parse(init.body) : null }); // 서버 저장 완료 시점
      if (fail === "network") throw new TypeError("응답 유실(시험)");
      return { ok: false, status: Number(fail), text: async () => "Internal Server Error" };
    });
    vi.stubGlobal("fetch", fetchSaveThenFail);
    const onSaved = openEdit(mode === "first" ? NOT_ENTERED : view());
    if (!clear) fireEvent.change(cash(), { target: { value: "500,000" } });
    fireEvent.click(screen.getByRole("button", { name: clear ? "비우기" : "저장" }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
    const alert = screen.getByRole("alert").textContent ?? "";
    expect(alert).toContain("저장 결과를 확인하지 못했습니다");
    expect(alert).toContain("서버에 이미 저장됐을 수도 있어");
    expect(alert).not.toContain("저장된 값은 바뀌지 않았습니다");
    expect(alert).toContain(fail === "network" ? "서버 응답을 받지 못함" : `서버 오류 HTTP ${fail}`);
    expect(calls).toHaveLength(1);
    expect(calls[0].body).toEqual(
      clear
        ? { cash_krw: null, limit_krw: null, confirmed_on: null }
        : expect.objectContaining({ cash_krw: 500000 }),
    );
    // 편집 상태 · 입력값 유지(성공으로 오인하지 않음)
    if (!clear) expect(cash().value).toBe("500,000");
  });

  it("손상 파일 거절(500 + 손상 문구)은 쓰기 전 거절 — '바뀌지 않았습니다' · 다시 읽지 않음", async () => {
    const onSaved = openEdit();
    reply = { status: 500, body: { detail: "자금 기준 파일 손상: 자금 기준 파일을 읽지 못했습니다: JSONDecodeError" } };
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("저장된 값은 바뀌지 않았습니다"));
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("저장 성공 뒤 다시 읽기가 실패해도 '저장 결과 모름'으로 바꾸지 않음", async () => {
    const onSaved = vi.fn().mockRejectedValue(new Error("다시 읽기 실패(시험)"));
    render(<CapitalContextPanel capital={view()} onSaved={onSaved} />);
    fireEvent.click(screen.getByRole("button", { name: "입력·수정" }));
    reply = { status: 200, body: { status: "ENTERED", cash_krw: 400000, limit_krw: 100000, confirmed_on: "2026-11-05", saved_at: null } };
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("button", { name: "입력·수정" })).toBeTruthy(); // 보기 화면으로 돌아감
  });

  it("refusedBeforeWrite — 422 · 손상 500 만 '쓰기 전 거절'", () => {
    expect(refusedBeforeWrite(new ApiRequestError("x", 422, { detail: "추가 투입 한도가 …" }))).toBe(true);
    expect(refusedBeforeWrite(new ApiRequestError("x", 500, { detail: "자금 기준 파일 손상: …" }))).toBe(true);
    expect(refusedBeforeWrite(new ApiRequestError("x", 500, "Internal Server Error"))).toBe(false);
    expect(refusedBeforeWrite(new ApiRequestError("x", 500, { detail: "다른 오류" }))).toBe(false);
    expect(refusedBeforeWrite(new ApiRequestError("x", 0, null))).toBe(false);
    expect(refusedBeforeWrite(new ApiRequestError("x", 502, null))).toBe(false);
    expect(refusedBeforeWrite(new TypeError("x"))).toBe(false);
  });

  it("취소하면 편집 값은 버려지고 요청 없음(미저장 값 미사용)", () => {
    openEdit();
    fireEvent.change(cash(), { target: { value: "999,999" } });
    fireEvent.click(screen.getByRole("button", { name: "취소" }));
    expect(calls).toHaveLength(0);
    const t = panel().textContent ?? "";
    expect(t).toContain("400,000원");
    expect(t).not.toContain("999,999");
  });

  it("소수 · 문자 · 모두 빈칸은 보내지 않고 사유 표시", () => {
    openEdit();
    fireEvent.change(cash(), { target: { value: "12.5" } });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(screen.getByRole("alert").textContent).toContain("원 단위 숫자(정수)만");
    fireEvent.change(cash(), { target: { value: "" } });
    fireEvent.change(limit(), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(screen.getByRole("alert").textContent).toContain("[비우기]");
    expect(calls).toHaveLength(0);
  });

  it("[비우기] = 세 칸 null 저장", async () => {
    const onSaved = openEdit();
    reply = { status: 200, body: { status: "NOT_ENTERED", cash_krw: null, limit_krw: null, confirmed_on: null, saved_at: null } };
    fireEvent.click(screen.getByRole("button", { name: "비우기" }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(calls[0].body).toEqual({ cash_krw: null, limit_krw: null, confirmed_on: null });
  });

  it("첫 입력의 확인일 기본값 = 오늘(KST) · 미래 날짜는 고를 수 없게 max", () => {
    openEdit(NOT_ENTERED);
    expect(day().value).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(day().max).toBe(day().value);
    expect(cash().value).toBe("");
  });

  it("parseWon — 쉼표 · 공백 허용 · 안전 정수 상한", () => {
    expect(parseWon("1,000")).toEqual({ ok: true, value: 1000 });
    expect(parseWon(" ")).toEqual({ ok: true, value: null });
    expect(parseWon("0")).toEqual({ ok: true, value: 0 });
    expect(parseWon("-1").ok).toBe(false);
    expect(parseWon("9007199254740991")).toEqual({ ok: true, value: 9007199254740991 });
    expect(parseWon("9007199254740992").ok).toBe(false);
  });
});

function row(over: Partial<EnrichedHolding> = {}): EnrichedHolding {
  return {
    ticker: "069500",
    name: "시험 069500",
    quantity: 10,
    avg_buy_price: 11000,
    invested_amount: 110000,
    current_price: 12000,
    price_asof: "2026-11-05T16:10:16+09:00",
    price_source: "TEST",
    eval_amount: 120000,
    pnl_amount: 10000,
    pnl_rate_pct: 9.09,
    buy_weight_pct: 50,
    market_weight_pct: 20,
    price_missing: false,
    calc_missing: false,
    account_group: "일반",
    source_index: 0,
    ...over,
  };
}

describe("종목 행 비중 · 배너 아래 카드 자리", () => {
  it("계산되면 둘째 줄 '입력 현금 포함' · 없으면 한 줄 · 첫 줄은 '보유 내 비중'", () => {
    const { container } = render(
      <EnrichedSection
        items={[
          row({ cash_inclusive_weight_pct: 12 }),
          row({ ticker: "360750", source_index: 1, cash_inclusive_weight_pct: null }),
          row({
            ticker: "133690",
            source_index: 2,
            current_price: null,
            eval_amount: null,
            pnl_amount: null,
            pnl_rate_pct: null,
            market_weight_pct: null,
            price_missing: true,
            calc_missing: true,
            cash_inclusive_weight_pct: null,
          }),
        ]}
        capitalSlot={<div data-testid="slot">자금 카드</div>}
      />,
    );
    const facts = Array.from(container.querySelectorAll(".hld-row-facts"));
    expect(facts).toHaveLength(3);
    expect(facts.filter((f) => (f.textContent ?? "").includes("보유 내 비중 20%"))).toHaveLength(2);
    // 값 없음(null)은 '0%'가 아니라 '비중 계산 불가'
    const unpriced = facts.find((f) => (f.textContent ?? "").includes("133690"));
    expect(unpriced?.textContent).toContain("비중 계산 불가");
    expect(unpriced?.textContent).not.toContain("0%");
    expect(facts.filter((f) => (f.textContent ?? "").includes("입력 현금 포함 12%"))).toHaveLength(1);
    expect(container.querySelectorAll(".hld-wv2")).toHaveLength(1);
    // 카드 자리 = 보유 배너 바로 다음 · 구성 막대 제목 = 현금 제외
    const hero = container.querySelector(".hld-hero") as Element;
    expect(hero.nextElementSibling?.getAttribute("data-testid")).toBe("slot");
    expect(container.textContent).toContain("계좌별 구성 (보유 평가액 기준 · 현금 제외)");
  });
});

describe("판단 근거 미리보기 — 버튼 근처 금액 안내(판정 Q1)", () => {
  it("미리보기가 생기면 [복사] 옆에 기본 안내가 보인다(도움말을 열지 않아도)", async () => {
    reply = {
      status: 200,
      body: {
        status: "ok",
        target_kind: "holding",
        ticker: "069500",
        preview_text: "[대상]\n- 시험\n\n[보유 · 자금 기준]\n- 보유 평가액 600,000원",
        generated_at: "2026-11-06T10:00:00+09:00",
        evidence_as_of: { target_as_of_date: "2026-11-05", kodex200_as_of_date: null, vix_as_of_date: null },
      },
    };
    render(<DecisionDraftPreviewCard targetKind="holding" ticker="069500" displayName="시험" />);
    expect(screen.queryByText(AMOUNT_NOTE)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /판단 근거 미리보기 생성/ }));
    await waitFor(() => expect(screen.getByText(AMOUNT_NOTE)).toBeTruthy());
    expect(AMOUNT_NOTE).toBe(
      "복사·AI 세션 원문에 보유 평가액·현금·한도·합계 금액이 포함됩니다. 외부 AI에 붙여 넣으면 해당 금액도 전달됩니다.",
    );
    expect(screen.getByRole("button", { name: "복사" })).toBeTruthy();
  });
});
