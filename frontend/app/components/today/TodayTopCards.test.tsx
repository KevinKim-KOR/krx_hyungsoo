// POC6-27 — 상단 「자료 최신화 필요」 · 「OCI 운영 스케줄 확인」(사용자 결정 ② · PLAN 판정 §2 · Q6 · §4).
// - 둘 다 기본 접힘 · 화면에 다시 들어오면 다시 접힘(저장 없음).
// - OCI 예약: 기동 스냅샷의 schedule — 확인 실패(unknown)는 누락으로 세지 않음 · 옛 응답이면 요약 문장 + 확인 불가.
// - 발송: '오늘 기록'은 사본 동기화가 오늘이고 실행 발생일도 오늘일 때만 · 조회 실패 ≠ 사본 없음 · 모르면 받은 알림 기록 이동.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";

const fetchOciStartupStatus = vi.fn();
const fetchLedgerLatestByKind = vi.fn();
vi.mock("@/lib/api", () => ({ fetchOciStartupStatus: (...a: unknown[]) => fetchOciStartupStatus(...a) }));
vi.mock("@/lib/api/decisionLedger", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchLedgerLatestByKind: (...a: unknown[]) => fetchLedgerLatestByKind(...a),
}));

import OciScheduleCard, { mdHm, sendSummary, todayRecords } from "./OciScheduleCard";
import FreshnessCard from "./FreshnessCard";
import type { LedgerLatestByKind } from "@/lib/api/decisionLedger";
import type { FreshRow } from "@/lib/todayFreshness";

const OCI = (schedule?: { kind: string; label: string; state: string }[]) => ({
  checked_at: "2026-11-08T00:44:17+00:00",
  reachable: true,
  overall: "OPERATING",
  summary_line: "OCI 자동 운영 스케줄 활성 (필수 3종 등록 · 기동 시 확인)",
  crontab_active: true,
  jobs: [],
  note: "",
  ...(schedule ? { schedule } : {}),
});
const SCHED = (states: [string, string, string]) => [
  { kind: "market_briefing", label: "시장 브리핑", state: states[0] },
  { kind: "holdings_briefing", label: "보유 브리핑", state: states[1] },
  { kind: "holdings_risk_alert", label: "장중 급등락", state: states[2] },
];
function ledger(syncAt: string | null, runDate: string, today = "2026-11-09", hasCopy = true): LedgerLatestByKind {
  return {
    today_kst: today,
    sync: { has_copy: hasCopy, last_success_at: syncAt, last_failure_at: null, last_failure_kind: null },
    kinds: [
      { kind: "market_briefing", label: "시장 브리핑", time_kst: `${runDate}T08:30:02+09:00`, run_date_kst: runDate, delivery_status: "sent", run_status: "sent" },
      { kind: "holdings_briefing", label: "보유 브리핑", time_kst: `${runDate}T12:30:02+09:00`, run_date_kst: runDate, delivery_status: "sent", run_status: "sent" },
      { kind: "holdings_risk_alert", label: "장중 급등락", time_kst: `${runDate}T13:30:01+09:00`, run_date_kst: runDate, delivery_status: "skipped", run_status: "skipped" },
    ],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  fetchOciStartupStatus.mockResolvedValue(OCI(SCHED(["registered", "registered", "registered"])));
  fetchLedgerLatestByKind.mockResolvedValue(ledger("2026-10-23T14:27:25+09:00", "2026-10-23"));
});

describe("OCI 운영 스케줄 확인 카드", () => {
  it("기본 접힘 · 접힌 줄 = '예약 3/3 확인' · '발송 확인 불가'(10/23 사본) · 펼치면 실제 날짜 · 시각 · 결과 · 동기화 시각", async () => {
    const nav = vi.fn();
    render(<OciScheduleCard onNavigate={nav} />);
    await waitFor(() => expect(screen.getByTestId("tc-oci-summary").textContent).toBe("예약 3/3 확인"));
    await waitFor(() => expect(screen.getByTestId("tc-send-summary").textContent).toBe("발송 확인 불가"));
    expect(screen.queryByTestId("tc-oci-body")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "OCI 운영 스케줄 확인 펼치기" }));
    const body = screen.getByTestId("tc-oci-body");
    expect(body.textContent).toContain("기동 확인 11/8 09:44");
    expect(body.querySelector('[data-kind="holdings_risk_alert"]')?.textContent).toBe("장중 급등락예약 확인");
    const send = screen.getByTestId("tc-oci-send");
    expect(send.textContent).toContain("최근 PUSH 발송 확인 불가 · 사본 10/23 14:27");
    expect(within(send).getByText("시장 브리핑 · 10/23 08:30 보냄")).toBeInTheDocument();
    expect(within(send).getByText("장중 급등락 · 10/23 13:30 건너뜀")).toBeInTheDocument();
    expect(within(send).getByText("사본 동기화 10/23 14:27")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "받은 알림 기록 →" }));
    expect(nav).toHaveBeenCalledWith("alert_records");
  });

  it("다시 들어오면 다시 접힘(펼침은 화면 안 상태만)", async () => {
    const { unmount } = render(<OciScheduleCard onNavigate={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "OCI 운영 스케줄 확인 펼치기" }));
    expect(screen.getByTestId("tc-oci-body")).toBeInTheDocument();
    unmount();
    render(<OciScheduleCard onNavigate={vi.fn()} />);
    expect(screen.getByRole("button", { name: "OCI 운영 스케줄 확인 펼치기" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByTestId("tc-oci-body")).toBeNull();
  });

  it.each([
    ["하나 누락", ["registered", "missing", "registered"], "예약 2/3 확인 · 누락 1"],
    ["확인 불가는 누락으로 세지 않음", ["unknown", "unknown", "unknown"], "예약 0/3 확인 · 확인 불가 3"],
  ] as const)("예약 상태 — %s", async (_n, states, text) => {
    fetchOciStartupStatus.mockResolvedValue(OCI(SCHED(states as unknown as [string, string, string])));
    render(<OciScheduleCard onNavigate={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId("tc-oci-summary").textContent).toBe(text));
  });

  it("옛 응답(schedule 없음)이면 '예약 확인 불가' · 펼치면 기존 요약 문장", async () => {
    fetchOciStartupStatus.mockResolvedValue(OCI());
    render(<OciScheduleCard onNavigate={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId("tc-oci-summary").textContent).toBe("예약 확인 불가"));
    fireEvent.click(screen.getByRole("button", { name: "OCI 운영 스케줄 확인 펼치기" }));
    expect(screen.getByTestId("tc-oci-body").textContent).toContain("알림별 예약 상태는 확인 불가(서버 응답에 예약 목록 없음)");
  });

  it("발송 — 조회 실패와 사본 없음은 다른 상태 · 둘 다 받은 알림 기록 이동은 그대로", async () => {
    fetchLedgerLatestByKind.mockRejectedValue(new Error("x"));
    const { unmount } = render(<OciScheduleCard onNavigate={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId("tc-send-summary").textContent).toBe("발송 기록 불러오지 못함"));
    unmount();
    fetchLedgerLatestByKind.mockResolvedValue(ledger(null, "2026-10-23", "2026-11-09", false));
    render(<OciScheduleCard onNavigate={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId("tc-send-summary").textContent).toBe("발송 사본 없음"));
    fireEvent.click(screen.getByRole("button", { name: "OCI 운영 스케줄 확인 펼치기" }));
    expect(screen.getByRole("button", { name: "받은 알림 기록 →" })).toBeInTheDocument();
  });
});

describe("판정 Q6 — 당일 동기화와 과거 실행 구분", () => {
  it.each([
    ["동기화 · 실행 모두 오늘", ledger("2026-11-09T10:00:00+09:00", "2026-11-09"), 3, "오늘 기록 3/3"],
    ["오늘 동기화했지만 실행은 과거(과거 날짜의 기록)", ledger("2026-11-09T10:00:00+09:00", "2026-11-06"), 0, "발송 확인 불가"],
    ["실행은 오늘 날짜인데 동기화가 과거", ledger("2026-11-08T22:00:00+09:00", "2026-11-09"), 0, "발송 확인 불가"],
    ["UTC 동기화 시각도 KST 날짜로(11/9 01:00 KST = 11/8 16:00Z)", ledger("2026-11-08T16:00:00Z", "2026-11-09"), 3, "오늘 기록 3/3"],
    // 검증자 r1 F2 — 달력에 없는 날짜끼리 같아도 '오늘'이 아니다
    ["서버 오늘 · 실행일 · 동기화일이 모두 깨진 같은 값", ledger("2026-13-01", "2026-13-01", "2026-13-01"), 0, "발송 확인 불가"],
    ["동기화 시각이 넘어가는 날짜(2/30)", ledger("2026-02-30T10:00:00+09:00", "2026-11-09"), 0, "발송 확인 불가"],
  ] as const)("%s", (_n, d, n, text) => {
    expect(todayRecords(d)).toHaveLength(n);
    expect(sendSummary({ phase: "ok", data: d })).toBe(text);
  });
});

describe("시각 표시(F2)", () => {
  it("읽을 수 있는 시각만 'M/D HH:MM' · 아니면 받은 글자 그대로(3/2 로 넘기지 않음)", () => {
    expect(mdHm("2026-10-23T14:27:25+09:00")).toBe("10/23 14:27");
    expect(mdHm("2026-02-30T14:27:25+09:00")).toBe("2026-02-30T14:27:25+09:00");
  });
});

describe("자료 최신화 필요 카드", () => {
  const ROWS: FreshRow[] = [
    { key: "flows", label: "외국인 수급", lastDate: "2026-11-05", expected: "2026-11-06", basis: "국내 직전 거래일", state: "late", behind: 1, reason: "", action: "market" },
    { key: "usdkrw", label: "원/달러", lastDate: "2026-11-05", expected: "2026-11-06", basis: "국내 직전 거래일 대비", state: "late", behind: 1, reason: "", action: "market" },
  ];
  const BUSY = { market: false, holdings: false, reload: false };

  it("대상이 없으면 그리지 않는다", () => {
    const { container } = render(<FreshnessCard rows={[]} tasks={[]} onAction={vi.fn()} busy={BUSY} />);
    expect(container.textContent).toBe("");
  });

  it("기본 접힘 · 접힌 줄 '2건 · 1거래일 늦음' · 펼치면 자료별 줄과 같은 작업 버튼 하나 · 다시 들어오면 접힘", () => {
    const onAction = vi.fn();
    const { unmount } = render(<FreshnessCard rows={ROWS} tasks={[]} onAction={onAction} busy={BUSY} />);
    expect(screen.getByTestId("tc-fresh-summary").textContent).toBe("2건 · 1거래일 늦음");
    expect(screen.queryByTestId("tc-fresh-body")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "자료 최신화 필요 펼치기" }));
    const body = screen.getByTestId("tc-fresh-body");
    expect(body.querySelector('[data-fresh="usdkrw"]')?.textContent).toContain("1거래일 늦음");
    const btns = within(body).getAllByRole("button", { name: "최신 시장 데이터 갱신" });
    expect(btns).toHaveLength(1);
    fireEvent.click(btns[0]);
    expect(onAction).toHaveBeenCalledWith({ label: "최신 시장 데이터 갱신", target: { kind: "market_refresh" }, primary: false });
    unmount();
    render(<FreshnessCard rows={ROWS} tasks={[]} onAction={onAction} busy={BUSY} />);
    expect(screen.queryByTestId("tc-fresh-body")).toBeNull();
  });

  it("진행 중인 작업 버튼은 막는다(중복 실행 없음)", () => {
    render(<FreshnessCard rows={ROWS} tasks={[]} onAction={vi.fn()} busy={{ ...BUSY, market: true }} />);
    fireEvent.click(screen.getByRole("button", { name: "자료 최신화 필요 펼치기" }));
    expect(screen.getByRole("button", { name: "최신 시장 데이터 갱신" })).toBeDisabled();
  });
});
