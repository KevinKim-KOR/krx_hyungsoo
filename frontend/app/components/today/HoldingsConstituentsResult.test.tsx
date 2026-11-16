// POC6-31 STEP 2 — '보유 구성종목' 결과 줄 · ETF별 보기 · 할 일 · 「지금 할 일」 문장(판정 §4 M1 · Q16 · Q20).
import { describe, it, expect } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import HoldingsConstituentsResult, { countsText, dateMixText } from "./HoldingsConstituentsResult";
import { collectMaintenance } from "./maintenanceQueue";
import { summaryTasks } from "./summaryLines";
import type { ConstituentItem, HoldingsConstituentsStatus } from "@/lib/api/constituentsStatus";
import type { QueryState } from "@/lib/api/queryCache";

const it_ = (p: Partial<ConstituentItem> & { ticker: string; result: ConstituentItem["result"] }): ConstituentItem => ({
  name: `보유 ${p.ticker}`,
  label: p.result,
  reason: "이유",
  source_asof: null,
  kept_asof: null,
  kept_confirmed: false,
  ...p,
});

// 판정 §4 M1 — 예정 22 중 성공 20(새로 받음 19 · 목표일 자료 대기 1) · 받기 실패 1 · 조회 전 시간 초과 1 · 기존 4 → 실제 호출 21
const M1_ITEMS: ConstituentItem[] = [
  ...Array.from({ length: 4 }, (_, i) => it_({ ticker: `X${i}`, result: "existing", source_asof: "2026-11-13", label: "기존 자료" })),
  ...Array.from({ length: 19 }, (_, i) => it_({ ticker: `F${i}`, result: "fetched", source_asof: "2026-11-13", label: "새로 받음" })),
  it_({ ticker: "W", result: "target_wait", source_asof: "2026-11-12", label: "목표일 자료 대기" }),
  it_({ ticker: "Q", result: "failed", kept_asof: "2026-06-22", kept_confirmed: false, label: "받기 실패" }),
  it_({ ticker: "T", result: "timeout", label: "시간 초과로 조회 안 함" }),
];
const M1_COUNTS = { existing: 4, fetched: 19, target_wait: 1, failed: 1, timeout: 1 };

const idle = { phase: "idle" } as unknown as QueryState<HoldingsConstituentsStatus>;
const ok = (d: Partial<HoldingsConstituentsStatus>) =>
  ({ phase: "success", data: { status: "ok", reason: null, target_date: "2026-11-13", running: false, total: 0, needs_check: 0, counts: {}, items: [], ...d }, successAt: 1 }) as unknown as QueryState<HoldingsConstituentsStatus>;

describe("보유 구성종목 결과 줄", () => {
  it("M1 완료 — 기존 · 새로 받음 · 목표일 자료 대기 · 갱신 실패(사유별) · 실제 호출 · 구성 기준일 분포", () => {
    expect(countsText(M1_COUNTS, 26, { calls: 21 })).toBe(
      "보유 ETF 26개 · 기존 자료 4 · 새로 받음 19 · 목표일 자료 대기 1 · 갱신 실패 2(받기 실패 1 · 시간 초과로 조회 안 함 1) · 실제 호출 21회",
    );
    expect(dateMixText(M1_ITEMS)).toBe("11/13 23개 · 11/12 1개 · 6/22 1개 · 없음 1개");
    render(<HoldingsConstituentsResult step={{ status: "done", total: 26, calls: 21, counts: M1_COUNTS, items: M1_ITEMS }} status={idle} />);
    const line = screen.getByTestId("tc-constituents-result");
    expect(line.textContent).toContain("보유 구성종목 — 보유 ETF 26개 · 기존 자료 4 · 새로 받음 19");
    expect(line.textContent).toContain("구성 기준일 11/13 23개 · 11/12 1개 · 6/22 1개 · 없음 1개");
    expect(line.querySelector("p")?.className).toContain("tc-warn");
  });

  it("ETF별 보기 — 결과 · 실제 구성일(마지막 보존 · 원천 기준일 미확인) · 이유", () => {
    render(<HoldingsConstituentsResult step={{ status: "done", total: 26, calls: 21, counts: M1_COUNTS, items: M1_ITEMS }} status={idle} />);
    expect(screen.queryByTestId("tc-constituents-table")).toBeNull();
    fireEvent.click(screen.getByTestId("tc-constituents-toggle"));
    const table = screen.getByTestId("tc-constituents-table");
    const rowOf = (t: string) => within(table).getByText(t).closest("tr") as HTMLElement;
    expect(rowOf("W").textContent).toContain("목표일 자료 대기");
    expect(rowOf("W").textContent).toContain("11/12");
    expect(rowOf("Q").textContent).toContain("6/22(마지막 보존 · 원천 기준일 미확인)");
    expect(rowOf("T").textContent).toContain("없음");
  });

  it("진행 중 — 묶음 진행", () => {
    render(
      <HoldingsConstituentsResult
        step={{ status: "running", total: 22, done: 10, batch_index: 2, batch_total: 3, items: [] }}
        status={idle}
      />,
    );
    expect(screen.getByTestId("tc-constituents-result").textContent).toBe(
      "보유 구성종목 받는 중 — 2/3 묶음 · 받을 ETF 22개 중 10개 끝",
    );
  });

  it("건너뜀 · 실패 — 사유", () => {
    const { rerender } = render(<HoldingsConstituentsResult step={{ status: "skipped", reason: "보유 종목이 없습니다" }} status={idle} />);
    expect(screen.getByTestId("tc-constituents-result").textContent).toBe("보유 구성종목 — 보유 종목이 없습니다");
    rerender(<HoldingsConstituentsResult step={{ status: "failed", reason: "오류" }} status={idle} />);
    expect(screen.getByTestId("tc-constituents-result").querySelector("p")?.className).toContain("tc-warn");
  });

  it("이번에 갱신하지 않았으면 저장 자료 상태 · 다시 확인 필요 · 읽기 실패", () => {
    const { rerender } = render(
      <HoldingsConstituentsResult
        step={null}
        status={ok({ total: 3, needs_check: 1, counts: { existing: 2, not_checked: 1 }, items: [it_({ ticker: "A", result: "not_checked" })] })}
      />,
    );
    expect(screen.getByTestId("tc-constituents-result").textContent).toContain(
      // 저장 자료 상태엔 '새로 받음'이 생기지 않으므로 늘 0 인 칸을 쓰지 않는다(지적 frontend#8)
      "보유 구성종목(목표일 11/13) — 보유 ETF 3개 · 목표일 이상 구성 2 · 아직 확인 안 함 1 · 다시 확인 필요 1 — [최신 자료 갱신]에서 받습니다",
    );
    rerender(<HoldingsConstituentsResult step={null} status={{ phase: "error" } as unknown as QueryState<HoldingsConstituentsStatus>} />);
    expect(screen.getByTestId("tc-constituents-result").textContent).toContain("보유 구성종목 상태를 읽지 못했습니다");
  });

  it("완료 줄 · 진행 줄에 수집 목표일 · ETF별 보기 머리에 목표일 규칙(지적 frontend#9)", () => {
    const { rerender } = render(
      <HoldingsConstituentsResult
        step={{ status: "done", target_date: "2026-11-13", total: 26, calls: 21, counts: M1_COUNTS, items: M1_ITEMS }}
        status={idle}
      />,
    );
    expect(screen.getByTestId("tc-constituents-result").textContent).toContain("보유 구성종목(목표일 11/13) — 보유 ETF 26개");
    fireEvent.click(screen.getByTestId("tc-constituents-toggle"));
    expect(screen.getByTestId("tc-constituents-rule").textContent).toBe(
      "수집 목표일 11/13 · 목표일 = 거래일 15:30 이후면 그날, 그 전이나 휴장일이면 직전 거래일 · 실제 구성일 = 원천이 준 날짜",
    );
    rerender(
      <HoldingsConstituentsResult
        step={{ status: "running", target_date: "2026-11-13", total: 22, done: 1, batch_index: 1, batch_total: 3, items: [] }}
        status={idle}
      />,
    );
    expect(screen.getByTestId("tc-constituents-result").textContent).toBe(
      "보유 구성종목 받는 중(목표일 11/13) — 1/3 묶음 · 받을 ETF 22개 중 1개 끝",
    );
  });

  it("함께 받음 · 못 쓴 확인 기록 · 오류 상세(지적 frontend#11 · backend#3)", () => {
    const items = [it_({ ticker: "S", result: "fetched", source_asof: "2026-11-13", shared: true, reason: "원천에서 새로 받음" })];
    render(
      <HoldingsConstituentsResult
        step={{
          status: "done",
          total: 1,
          calls: 0,
          shared: 1,
          unlogged_logs: 2,
          counts: { fetched: 1 },
          reason: "작업 중 오류로 멈췄습니다 — 남은 ETF는 다음 갱신 때 다시 확인합니다",
          reason_detail: "OperationalError",
          items,
        }}
        status={idle}
      />,
    );
    const line = screen.getByTestId("tc-constituents-result");
    expect(line.textContent).toContain("새로 받음 1 · 다른 작업과 함께 받음 1 · 실제 호출 0회");
    expect(line.textContent).toContain("확인 기록 2줄을 저장하지 못했습니다(저장소 잠김)");
    expect(line.querySelector("p")?.textContent).not.toContain("OperationalError"); // 예외 이름은 '자세히' 안
    expect(within(line).getByText("자세히")).toBeTruthy();
    fireEvent.click(screen.getByTestId("tc-constituents-toggle"));
    expect(within(screen.getByTestId("tc-constituents-table")).getByText("원천에서 새로 받음 · 다른 작업과 함께 받음")).toBeTruthy();
  });

  it("저장소 잠김으로 상태를 못 읽으면 '할 일 없음'이 아니라 읽지 못함(지적 backend#1)", () => {
    render(
      <HoldingsConstituentsResult
        step={null}
        status={ok({ status: "read_failed", reason: "자료 저장소가 잠겨 구성 상태를 읽지 못했습니다 — 잠시 뒤 다시 읽어 주세요" })}
      />,
    );
    const line = screen.getByTestId("tc-constituents-result");
    expect(line.textContent).toBe("보유 구성종목 — 자료 저장소가 잠겨 구성 상태를 읽지 못했습니다 — 잠시 뒤 다시 읽어 주세요");
    expect(line.querySelector("p")?.className).toContain("tc-warn");
  });

  it("상태를 아직 읽는 중이면 줄을 그리지 않는다", () => {
    render(<HoldingsConstituentsResult step={null} status={idle} />);
    expect(screen.queryByTestId("tc-constituents-result")).toBeNull();
  });
});

describe("할 일 · 지금 할 일(판정 Q16)", () => {
  const none = { phase: "idle" } as never;
  const market = { phase: "idle" } as never;
  const flow = { phase: "idle" } as never;

  it("다시 확인 필요 = 보유 ETF 종목 단위 · 사유별 개수 · [최신 자료 갱신] · 0이면 항목 없음", () => {
    const st = ok({
      total: 26,
      needs_check: 3,
      items: [it_({ ticker: "A", result: "target_wait" }), it_({ ticker: "B", result: "failed" }), it_({ ticker: "C", result: "timeout" })],
    });
    const list = collectMaintenance(none, none, none, market, st);
    const item = list.find((i) => i.source === "constituents");
    expect(item?.text).toBe(
      "구성종목 자료가 없거나 목표일(11/13)에 못 미친 보유 ETF 3개 — [최신 자료 갱신]에서 받습니다 · 마지막 시도 없음",
    );
    expect(item?.target).toBe("today_check");
    expect(item?.actionLabel).toBe("최신 자료 갱신");
    expect(item?.reason).toContain("목표일 자료 대기 1 · 받기 실패 1 · 시간 초과로 조회 안 함 1");
    expect(collectMaintenance(none, none, none, market, ok({ total: 26, needs_check: 0 })).some((i) => i.source === "constituents")).toBe(false);
    expect(collectMaintenance(none, none, none, market).some((i) => i.source === "constituents")).toBe(false);
  });

  it("할 일 문장 끝에 마지막 시도 시각(PLAN C13 · 지적 frontend#9)", () => {
    const st = ok({
      total: 3,
      needs_check: 2,
      items: [
        it_({ ticker: "A", result: "failed", needs_check: true, last_checked_at: "2026-11-14T06:07:00.000000Z" }),
        it_({ ticker: "B", result: "target_wait", needs_check: true, last_checked_at: "2026-11-14T05:00:00.000000Z" }),
        it_({ ticker: "C", result: "existing", needs_check: false, last_checked_at: "2026-11-14T07:00:00.000000Z" }),
      ],
    });
    const item = collectMaintenance(none, none, none, market, st).find((i) => i.source === "constituents");
    // 다시 확인이 필요한 것 중 가장 늦은 시도(C 의 기록은 '기존 자료'라 세지 않음) · 한국 시각
    expect(item?.text).toContain("— [최신 자료 갱신]에서 받습니다 · 마지막 시도 11/14 15:07");
  });

  it("구성종목만 남으면 '보유 ETF 구성종목을 받아야 합니다' · 섞이면 시장 제목 + 같은 작업 안내", () => {
    const cons = collectMaintenance(none, none, none, market, ok({ total: 2, needs_check: 1, items: [it_({ ticker: "A", result: "not_checked" })] }));
    const t1 = summaryTasks(cons, false, market, none, flow).find((t) => t.id === "market_refresh");
    expect(t1?.title).toBe("보유 ETF 구성종목을 받아야 합니다.");
    expect(t1?.doText).toContain("보유 현재가 → 시장 자료 → 보유 구성종목");
    const mixed = [...cons, { task: "market_refresh" as const, text: "시장", kind: "heavy" as const, target: "today_check" as const, actionLabel: "최신 자료 갱신" }];
    const t2 = summaryTasks(mixed, false, market, none, flow).find((t) => t.id === "market_refresh");
    expect(t2?.title).toBe("시장 자료 갱신이 필요합니다.");
    expect(t2?.doText).toContain("→ 보유 구성종목");
  });
});
