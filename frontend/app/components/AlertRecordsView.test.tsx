// POC5-03 설계 개정 2 — 「받은 알림 기록」 화면 test.
//
// - 진입 · 날짜 · 종류 변경은 사본 조회만(원장 새로고침 호출 0) · 처음엔 날짜를 보내지 않음.
// - 고른 날짜는 새로고침 · 종류 변경 뒤에도 유지.
// - partial 원문 = '생성된 원문 — 일부만 전달됨' (받은 전문 표현 금지).
// - 평가는 선택 · 실패하면 성공처럼 바꾸지 않음 · 미평가 수 · 완료율 없음.
// - 신호 결과 원장은 평가 여부와 무관하게 결과를 보인다(평가 조건 폐기).
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import type {
  LedgerAlertCard,
  LedgerAlertDetail,
  LedgerAlertList,
  LedgerItem,
} from "@/lib/api";

const fetchLedgerAlerts = vi.fn();
const fetchLedgerAlertDetail = vi.fn();
const syncDecisionLedger = vi.fn();
const postLedgerFeedback = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchLedgerAlerts: (...a: unknown[]) => fetchLedgerAlerts(...a),
    fetchLedgerAlertDetail: (...a: unknown[]) => fetchLedgerAlertDetail(...a),
    syncDecisionLedger: (...a: unknown[]) => syncDecisionLedger(...a),
    postLedgerFeedback: (...a: unknown[]) => postLedgerFeedback(...a),
  };
});

import AlertRecordsView from "./AlertRecordsView";
import { ApiRequestError } from "@/lib/api";
import { DISPOSITION_LABEL, dispositionLabel } from "./alert_records/format";

const SYNC_OK = {
  has_copy: true,
  last_success_at: "2026-10-08T09:37:12+09:00",
  last_failure_at: null,
  last_failure_kind: null,
};

function card(over: Partial<LedgerAlertCard>): LedgerAlertCard {
  return {
    event_id: "E1",
    push_kind: "holdings_briefing",
    time_kst: "09:15",
    schedule_expected: "09:15",
    off_schedule: false,
    delivery_status: "sent",
    key_items: [
      { subject_kind: "ticker", subject_id: "005930", name: "삼성전자" },
      { subject_kind: "ticker", subject_id: "069500", name: "KODEX 200" },
    ],
    latest_feedback: null,
    feedback_count: 0,
    ...over,
  };
}

const CARDS: LedgerAlertCard[] = [
  card({
    event_id: "E2",
    push_kind: "market_briefing",
    time_kst: "08:30",
    key_items: [
      { subject_kind: "market", subject_id: "SP500", name: null },
      { subject_kind: "index_group", subject_id: "KODEX|반도체", name: null },
      { subject_kind: "index_group", subject_id: "TIGER|2차전지", name: null },
    ],
    latest_feedback: {
      feedback_seq: 1,
      helpfulness: "HELPFUL",
      action: "WATCH_ONLY",
      memo: null,
      feedback_at: "2026-10-08T09:40:00+09:00",
    },
    feedback_count: 1,
  }),
  card({ event_id: "E1" }),
  card({
    event_id: "E3",
    push_kind: "holdings_risk_alert",
    time_kst: "10:30",
    delivery_status: "partial",
  }),
  card({
    event_id: "E6",
    push_kind: "holdings_risk_alert",
    time_kst: "13:05",
    off_schedule: true,
  }),
];

function list(over: Partial<LedgerAlertList> = {}): LedgerAlertList {
  return { date: "2026-10-08", kind: "all", sync: SYNC_OK, alerts: CARDS, ...over };
}

function item(over: Partial<LedgerItem>): LedgerItem {
  return {
    item_seq: 1,
    subject_kind: "ticker",
    subject_id: "005930",
    name: "삼성전자",
    held: 1,
    state: "D5_8",
    prev_state: null,
    state_label: "20거래일 하락 5~8%",
    prev_state_label: null,
    disposition: "sent",
    event_type: null,
    t0_price: 71200,
    t0_price_asof: "x",
    evaluable: true,
    outcome_target: true,
    ...over,
  };
}

function detail(eventId: string): LedgerAlertDetail {
  const base = {
    event_id: eventId,
    push_kind: "holdings_briefing",
    time_kst: "09:15",
    runtime_date_kst: "2026-10-08",
    schedule_expected: "09:15",
    off_schedule: false,
    outcome_event_target: true,
    delivery_status: "sent",
    body_text: "보유 브리핑 원문",
    body_withheld: false,
    body_partial_delivery: false,
    items: [item({})],
    feedback: [],
    outcomes: [],
  };
  if (eventId === "E1") {
    return {
      ...base,
      items: [
        item({}),
        item({ item_seq: 2, subject_id: "069500", name: "KODEX 200", t0_price: 35415 }),
      ],
      outcomes: [
        { ...outcome(1, "krx_stock:005930", 1, "MATURED", 0.0123) },
        { ...outcome(1, "krx_stock:005930", 5, "PRICE_MISSING", null) },
        { ...outcome(2, "krx_etf:069500", 1, "T0_MISSING", null) },
      ],
    };
  }
  if (eventId === "E3") {
    return {
      ...base,
      push_kind: "holdings_risk_alert",
      time_kst: "10:30",
      delivery_status: "partial",
      body_text: "장중 급등락 전체 본문(분할 전)",
      body_partial_delivery: true,
      items: [
        item({ subject_id: "091160", name: "KODEX 반도체", state_label: "전일 대비 하락 5~7%" }),
        item({ item_seq: 2, subject_kind: "sector_block", subject_id: "BLOCK", name: null, outcome_target: false, t0_price: null }),
        item({ item_seq: 3, subject_id: "000660", name: "SK하이닉스", evaluable: false, outcome_target: false }),
        item({ item_seq: 4, subject_id: "035420", name: "NAVER" }),
      ],
      outcomes: [
        outcome(1, "krx_etf:091160", 1, "UNTRACKED_AFTER_EXIT", null),
        outcome(4, "unsupported:035420", 1, "UNSUPPORTED_PRICE_SOURCE", null),
      ],
    };
  }
  if (eventId === "E6") {
    return {
      ...base,
      off_schedule: true,
      outcome_event_target: false,
      items: [item({ subject_id: "091160", name: "KODEX 반도체", outcome_target: false })],
    };
  }
  return { ...base, push_kind: "market_briefing", items: [], outcomes: [] };
}

function outcome(
  seq: number,
  series: string,
  horizon: number,
  status: string,
  ret: number | null
) {
  return {
    item_seq: seq,
    series_id: series,
    series_name: series.split(":")[1],
    horizon,
    status,
    t0_price: null,
    t0_price_asof: null,
    eval_date: null,
    eval_price: null,
    return_raw: ret,
    max_up_raw: null,
    max_down_raw: null,
    path_points: null,
  };
}

beforeEach(() => {
  fetchLedgerAlerts.mockReset();
  fetchLedgerAlertDetail.mockReset();
  syncDecisionLedger.mockReset();
  postLedgerFeedback.mockReset();
  fetchLedgerAlerts.mockImplementation((date: string | null) =>
    Promise.resolve(list({ date: date ?? "2026-10-08" }))
  );
  fetchLedgerAlertDetail.mockImplementation((id: string) => Promise.resolve(detail(id)));
});

describe("AlertRecordsView — 받은 알림 기록", () => {
  it("진입은 사본 조회만 · 날짜 없이 요청해 최근 날짜를 받고 · 원장 새로고침은 부르지 않는다", async () => {
    render(<AlertRecordsView />);
    expect(await screen.findByText("시장 브리핑")).toBeTruthy();
    expect(fetchLedgerAlerts).toHaveBeenCalledTimes(1);
    expect(fetchLedgerAlerts).toHaveBeenCalledWith(null, "all");
    expect(syncDecisionLedger).not.toHaveBeenCalled();
    expect((screen.getByLabelText("날짜") as HTMLInputElement).value).toBe("2026-10-08");
    expect(screen.getByTestId("sync-line").textContent).toBe("마지막 성공 동기화 10-08 09:37");
  });

  it("카드: 시각 · 종류 · 전달 상태 · 핵심 item · 내 평가(또는 평가 없음) — 미평가 수 · 완료율 없음", async () => {
    render(<AlertRecordsView />);
    await screen.findByText("시장 브리핑");
    expect(screen.getByText("S&P500 외 2개 항목")).toBeTruthy();
    expect(screen.getAllByText("삼성전자 외 1종목").length).toBe(3);
    expect(screen.getByText("내 평가: 도움됨")).toBeTruthy();
    expect(screen.getAllByText("평가 없음").length).toBe(3);
    expect(screen.getByText("일부 전달")).toBeTruthy();
    expect(screen.getByText("예정 외 실행")).toBeTruthy();
    expect(screen.queryByText(/미평가|완료율|평가하세요/)).toBeNull();
  });

  it("사본이 없으면 '원장 새로고침이 필요합니다' · 실패가 더 최근이면 '기존 기록을 표시 중입니다'", async () => {
    fetchLedgerAlerts.mockResolvedValueOnce(
      list({
        sync: { has_copy: false, last_success_at: null, last_failure_at: null, last_failure_kind: null },
        alerts: [],
      })
    );
    const { unmount } = render(<AlertRecordsView />);
    expect((await screen.findAllByText("원장 새로고침이 필요합니다")).length).toBe(2);
    unmount();
    fetchLedgerAlerts.mockResolvedValueOnce(
      list({
        sync: {
          ...SYNC_OK,
          last_failure_at: "2026-10-08T09:41:00+09:00",
          last_failure_kind: "SSH_FAILED",
        },
      })
    );
    render(<AlertRecordsView />);
    expect(await screen.findByText("기존 기록을 표시 중입니다 · 실패 10-08 09:41")).toBeTruthy();
  });

  it("고른 날짜는 종류 변경 · 원장 새로고침 뒤에도 유지된다 · 이전/다음 날은 달력 ±1일", async () => {
    syncDecisionLedger.mockResolvedValue({ ok: true, failure_kind: null, attempted_at: "x", counts: {} });
    render(<AlertRecordsView />);
    await screen.findByText("시장 브리핑");
    fireEvent.click(screen.getByText("◀ 이전 날"));
    await waitFor(() => expect(fetchLedgerAlerts).toHaveBeenLastCalledWith("2026-10-07", "all"));
    fireEvent.click(screen.getByText("다음 날 ▶"));
    fireEvent.click(screen.getByText("다음 날 ▶"));
    await waitFor(() => expect(fetchLedgerAlerts).toHaveBeenLastCalledWith("2026-10-09", "all"));
    fireEvent.click(within(screen.getByRole("group", { name: "알림 종류" })).getByText("장중"));
    await waitFor(() =>
      expect(fetchLedgerAlerts).toHaveBeenLastCalledWith("2026-10-09", "intraday")
    );
    fireEvent.click(screen.getByText("원장 새로고침"));
    await waitFor(() => expect(syncDecisionLedger).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(fetchLedgerAlerts).toHaveBeenLastCalledWith("2026-10-09", "intraday")
    );
    // 첫 조회만 날짜 없이(기본 날짜) — 그 뒤는 모두 고른 날짜를 보낸다.
    expect(fetchLedgerAlerts.mock.calls.slice(1).every((c) => c[0] !== null)).toBe(true);
  });

  it("원장 새로고침: 실행 중 비활성 · 409 는 '이미 진행 중' · 실패를 완료로 보이지 않는다", async () => {
    let finish: (v: unknown) => void = () => {};
    syncDecisionLedger.mockReturnValueOnce(new Promise((r) => (finish = r)));
    render(<AlertRecordsView />);
    await screen.findByText("시장 브리핑");
    fireEvent.click(screen.getByText("원장 새로고침"));
    const running = screen.getByText("불러오는 중...") as HTMLButtonElement;
    expect(running.disabled).toBe(true);
    finish({ ok: false, failure_kind: "SSH_FAILED", attempted_at: "x", counts: null });
    await waitFor(() => expect(screen.getByTestId("sync-line").textContent).toContain(" · 실패"));
    expect(screen.getByTestId("sync-line").textContent).not.toContain("완료");
    syncDecisionLedger.mockRejectedValueOnce(new ApiRequestError("busy", 409, null));
    fireEvent.click(screen.getByText("원장 새로고침"));
    await waitFor(() =>
      expect(screen.getByTestId("sync-line").textContent).toContain("이미 진행 중")
    );
  });

  it("자세히 보기: partial 은 '생성된 원문 — 일부만 전달됨' · sent 는 '원문' · 당시 판단 근거", async () => {
    render(<AlertRecordsView />);
    await screen.findByText("시장 브리핑");
    const buttons = screen.getAllByText("자세히 보기");
    fireEvent.click(buttons[2]); // E3 partial
    expect(await screen.findByText("생성된 원문 — 일부만 전달됨")).toBeTruthy();
    expect(screen.getByText("실제 수신된 범위는 확인할 수 없습니다.")).toBeTruthy();
    expect(screen.getByText("장중 급등락 전체 본문(분할 전)")).toBeTruthy();
    expect(screen.getByText("전일 대비 하락 5~7%")).toBeTruthy();
    expect(screen.getAllByText("알림 본문에 포함").length).toBe(4); // E3 item 4개 모두 sent
    expect(screen.queryByText(/받은 전문|전달된 원문/)).toBeNull();
    fireEvent.click(screen.getAllByText("자세히 보기")[1]); // E1 sent
    expect(await screen.findByText("보유 브리핑 원문")).toBeTruthy();
    expect(screen.getAllByText("원문").length).toBe(1);
  });

  it("평가: 고르기 전엔 저장 비활성 · 저장 성공 시 목록을 다시 읽고 · 실패하면 성공처럼 보이지 않는다", async () => {
    postLedgerFeedback.mockResolvedValueOnce({});
    render(<AlertRecordsView />);
    await screen.findByText("시장 브리핑");
    fireEvent.click(screen.getAllByText("자세히 보기")[1]); // E1
    await screen.findByText("보유 브리핑 원문");
    const save = screen.getByText("저장") as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.click(screen.getByText("보통"));
    fireEvent.change(screen.getByLabelText("선택 행동"), { target: { value: "WATCH_ONLY" } });
    fireEvent.change(screen.getByLabelText("메모"), { target: { value: "  관찰  " } });
    const before = fetchLedgerAlerts.mock.calls.length;
    fireEvent.click(save);
    await waitFor(() =>
      expect(postLedgerFeedback).toHaveBeenCalledWith("E1", {
        helpfulness: "NEUTRAL",
        action: "WATCH_ONLY",
        memo: "  관찰  ",
      })
    );
    expect(await screen.findByText("저장했습니다")).toBeTruthy();
    await waitFor(() => expect(fetchLedgerAlerts.mock.calls.length).toBe(before + 1));
    postLedgerFeedback.mockRejectedValueOnce(new ApiRequestError("요청 실패", 409, null));
    fireEvent.click(screen.getByText("도움됨"));
    fireEvent.click(screen.getByText("저장"));
    expect(await screen.findByText(/저장하지 못했습니다/)).toBeTruthy();
    expect(screen.queryByText("저장했습니다")).toBeNull();
    expect((screen.getByText("도움됨") as HTMLButtonElement).getAttribute("aria-pressed")).toBe("true");
  });

  it("신호 결과 원장: 펼칠 때만 상세를 읽고 · 평가가 없어도 결과를 보인다", async () => {
    render(<AlertRecordsView />);
    await screen.findByText("시장 브리핑");
    expect(fetchLedgerAlertDetail).not.toHaveBeenCalled();
    const summary = screen.getByText("신호 결과 원장");
    const details = summary.closest("details")!;
    details.open = true;
    fireEvent(details, new Event("toggle"));
    expect(await screen.findByText("+1.23%")).toBeTruthy();
    expect(fetchLedgerAlertDetail).toHaveBeenCalledTimes(4);
    const ledger = within(details);
    expect(ledger.getAllByText("가격 자료 없음").length).toBe(1);
    expect(ledger.getAllByText("기준 가격 없음").length).toBe(1);
    expect(ledger.getAllByText("매도 뒤 추적 중단").length).toBe(1);
    expect(ledger.getAllByText("지원 계열 없음").length).toBe(1);
    expect(ledger.getAllByText("결과 대상 아님").length).toBe(2); // 차단 블록 · 예정 외 실행
    expect(ledger.queryByText("SK하이닉스")).toBeNull(); // 평가 불가 item 은 원장에 없다
    expect(ledger.getByText("KODEX 반도체 (예정 외 실행)")).toBeTruthy();
    expect(ledger.getAllByText("집계 중").length).toBeGreaterThan(0);
    expect(screen.queryByText(/피드백 후 결과 확인/)).toBeNull();
  });

  it("원장 새로고침 뒤 펼친 신호 결과 원장 · 열린 상세를 다시 읽는다(알림 ID · 평가 수가 같아도)", async () => {
    syncDecisionLedger.mockResolvedValue({ ok: true, failure_kind: null, attempted_at: "x", counts: {} });
    render(<AlertRecordsView />);
    await screen.findByText("시장 브리핑");
    fireEvent.click(screen.getAllByText("자세히 보기")[1]); // E1 상세 열어 둠
    await screen.findByText("보유 브리핑 원문");
    const details = screen.getByText("신호 결과 원장").closest("details")!;
    details.open = true;
    fireEvent(details, new Event("toggle"));
    expect(await screen.findByText("+1.23%")).toBeTruthy();
    expect(within(details).queryByText("+0.50%")).toBeNull();
    const e1Calls = () => fetchLedgerAlertDetail.mock.calls.filter((c) => c[0] === "E1").length;
    const before = e1Calls();
    // 새로고침으로 E1 item 1 의 +20 이 성숙했다 — 목록(ID · 평가 수)은 그대로다.
    fetchLedgerAlertDetail.mockImplementation((id: string) => {
      const d = detail(id);
      if (id === "E1") {
        d.outcomes = [...d.outcomes, outcome(1, "krx_stock:005930", 20, "MATURED", 0.005)];
      }
      return Promise.resolve(d);
    });
    fireEvent.click(screen.getByText("원장 새로고침"));
    expect(await within(details).findByText("+0.50%")).toBeTruthy();
    expect(e1Calls()).toBeGreaterThanOrEqual(before + 2); // 결과 원장 + 열린 카드 상세
  });

  it("처리(disposition) 문구는 설계자 확정 표현이다(2026-10-07)", () => {
    expect(DISPOSITION_LABEL).toEqual({
      sent: "알림 본문에 포함",
      suppressed: "반복 알림 생략",
      cut_by_section_cap: "구역별 항목 수 제한으로 제외",
      cut_by_daily_cap: "하루 알림 횟수 제한으로 제외",
      not_selected: "이번 알림에 포함 안 됨",
      data_unavailable: "자료 문제로 판단 보류",
    });
    expect(dispositionLabel("unknown_code")).toBe("unknown_code"); // 모르는 코드는 코드 그대로
  });
});
