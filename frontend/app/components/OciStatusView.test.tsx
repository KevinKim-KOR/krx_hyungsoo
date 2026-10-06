// 「OCI 운영 상태」 요약 + 표 (2026-09-27 사용자 직접 지시 · 가독성) test.
//
// 표시만 바꿨다 — 응답은 백엔드 `oci_startup_status` 가 실제로 만드는 모양 그대로
// fixture 로 둔다(job 이름 · 상태값 · detail 문구 · UTC ISO 시각).
//
// 2026-09-27 사용자 직접 지시: 이 패널은 「OCI 운영·적용」 화면의 ① 섹션으로
// 들어갔다(`oci_status` 메뉴 없음). 자기 h1 을 두지 않는다 — 화면 제목 · 섹션
// 제목은 ApprovalTelegramView 가 단다(ApprovalTelegramView.test.tsx).
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";

const fetchOciStartupStatus = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchOciStartupStatus: (...a: unknown[]) => fetchOciStartupStatus(...a),
  };
});

import OciStatusPanel, { fmtKst } from "./OciStatusView";

function operating() {
  return {
    checked_at: "2026-09-27T09:58:02.851055+00:00",
    reachable: true,
    overall: "OPERATING",
    summary_line: "OCI 자동 운영 스케줄 활성 (필수 3종 등록 · 기동 시 확인)",
    crontab_active: true,
    jobs: [
      { job: "crontab", status: "SUCCESS", detail: "필수 스케줄(시장·보유·급등락) 모두 등록됨" },
      {
        job: "holdings_source",
        status: "SUCCESS",
        detail: "holdings 소스 최근 수정 2026-08-09T14:41:44+00:00",
      },
      {
        job: "runtime_state_db",
        status: "SUCCESS",
        detail: "runtime_state.sqlite 최근 수정 2026-09-25T06:40:02+00:00 · 438272 bytes",
      },
      {
        job: "push_job_results",
        status: "UNKNOWN",
        detail: "개별 PUSH job 최신 성공/실패는 기동 읽기 범위 밖 (Q5)",
      },
    ],
    note: "기동 시 1회 읽은 읽기 전용 스냅샷입니다.",
  };
}

function rowOf(label: string) {
  const cell = screen.getByText(label, { selector: "td" });
  return cell.closest("tr") as HTMLElement;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("OciStatusPanel — 요약 + 표", () => {
  it("정상: 요약 한 줄 · 한국어 항목 · 한국 시간", async () => {
    fetchOciStartupStatus.mockResolvedValue(operating());
    const { container } = render(<OciStatusPanel />);

    expect(await screen.findByText("정상 운영 중")).toBeInTheDocument();
    // 패널이다 — 화면 제목(h1)은 합친 화면이 단다.
    expect(container.querySelector("h1")).toBeNull();
    expect(screen.getByText("자동 발송 예약이 모두 등록되어 있습니다")).toBeInTheDocument();
    // 09:58 UTC = 18:58 KST (2026-09-27 일요일)
    expect(screen.getByText("PC 백엔드 시작 때 1번 확인 · 9/27(일) 18:58")).toBeInTheDocument();

    const cron = within(rowOf("자동 발송 예약"));
    expect(cron.getByText("정상")).toBeInTheDocument();
    expect(cron.getByText("시장 브리핑 · 보유 브리핑 · 장중 급등락")).toBeInTheDocument();
    // 14:41 UTC = 23:41 KST · 06:40 UTC = 15:40 KST
    expect(within(rowOf("보유 종목 파일")).getByText("마지막 수정 8/9 23:41")).toBeInTheDocument();
    expect(within(rowOf("운영 설정 DB")).getByText("마지막 수정 9/25 15:40")).toBeInTheDocument();
    const push = within(rowOf("PUSH 발송 결과"));
    expect(push.getByText("확인 불가")).toBeInTheDocument();
    expect(push.getByText(/Telegram 에서 확인/)).toBeInTheDocument();

    // 읽기 어렵던 원문(영어 job 이름 · 상태 코드 · UTC ISO · 내부 표기)은 보이지 않는다.
    const text = container.textContent ?? "";
    for (const raw of ["crontab", "SUCCESS", "UNKNOWN", "OPERATING", "(Q5)", "T14:41:44", "bytes"]) {
      expect(text).not.toContain(raw);
    }
  });

  it("일부 누락: 빠진 예약을 한국어 이름으로", async () => {
    const s = operating();
    s.overall = "DEGRADED";
    s.jobs[0] = { job: "crontab", status: "STALE", detail: "일부 스케줄 누락: holdings_risk_alert" };
    fetchOciStartupStatus.mockResolvedValue(s);
    render(<OciStatusPanel />);

    expect(await screen.findByText("일부 예약 누락")).toBeInTheDocument();
    expect(screen.getByText("빠진 예약: 장중 급등락")).toBeInTheDocument();
    const cron = within(rowOf("자동 발송 예약"));
    expect(cron.getByText("일부 누락")).toBeInTheDocument();
    expect(cron.getByText("빠짐: 장중 급등락")).toBeInTheDocument();
  });

  it("접속 실패: 확인 불가 + 백엔드 사유 한 줄 · 표 없음", async () => {
    fetchOciStartupStatus.mockResolvedValue({
      checked_at: "2026-09-27T09:58:02+00:00",
      reachable: false,
      overall: "UNKNOWN",
      summary_line: "OCI 상태 미확인 (OCI_SSH_TARGET 미설정)",
      crontab_active: null,
      jobs: [],
      note: "OCI 접속 대상이 설정되지 않아 기동 시 조회를 건너뛰었습니다.",
    });
    render(<OciStatusPanel />);

    expect(await screen.findByText("확인 불가")).toBeInTheDocument();
    expect(screen.getByText("OCI 상태 미확인 (OCI_SSH_TARGET 미설정)")).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("거래일 기준(한국 · 고정 문구 · 정상) · 미국 휴장일 달력(준비 필요) 행을 따로 보인다", async () => {
    const s = operating();
    s.jobs.push(
      {
        job: "trading_day_basis",
        status: "SUCCESS",
        detail: "평일 기본 운영 · 등록된 공휴일·명절·5월 1일·12월 31일 제외",
      },
      {
        job: "trading_calendar",
        status: "STALE",
        detail: "2027년 파일 없음: 미국 — 준비 필요",
      },
    );
    fetchOciStartupStatus.mockResolvedValue(s);
    const { container } = render(<OciStatusPanel />);

    const kr = within(await screen.findByText("거래일 기준", { selector: "td" }).then((c) => c.closest("tr") as HTMLElement));
    expect(kr.getByText("정상")).toBeInTheDocument();
    expect(kr.getByText("평일 기본 운영 · 등록된 공휴일·명절·5월 1일·12월 31일 제외")).toBeInTheDocument();
    const us = within(screen.getByText("미국 휴장일 달력", { selector: "td" }).closest("tr") as HTMLElement);
    expect(us.getByText("준비 필요")).toBeInTheDocument();
    expect(us.getByText("2027년 파일 없음: 미국 — 준비 필요")).toBeInTheDocument();
    const text = container.textContent ?? "";
    expect(text).not.toContain("trading_calendar");
    expect(text).not.toContain("trading_day_basis");
    expect(text).not.toContain("한국 — 준비 필요");
  });

  it("모르는 job · 상태 · 문구는 원문 그대로 보인다(숨기지 않는다)", async () => {
    const s = operating();
    s.jobs.push({ job: "new_job", status: "WEIRD", detail: "새 항목 원문" });
    fetchOciStartupStatus.mockResolvedValue(s);
    render(<OciStatusPanel />);

    const row = within(await screen.findByText("new_job", { selector: "td" }).then((c) => c.closest("tr") as HTMLElement));
    expect(row.getByText("WEIRD")).toBeInTheDocument();
    expect(row.getByText("새 항목 원문")).toBeInTheDocument();
  });

  it("조회 실패: 기존 오류 문구 그대로", async () => {
    fetchOciStartupStatus.mockRejectedValue(new Error("down"));
    render(<OciStatusPanel />);
    expect(await screen.findByText("알 수 없는 오류: down")).toBeInTheDocument();
  });

  it("fmtKst: 자정은 24시가 아니라 00시 · 못 읽는 값은 null", () => {
    expect(fmtKst("2026-09-27T15:05:00+00:00", false)).toBe("9/28 00:05");
    expect(fmtKst("2026-09-27T15:05:00+00:00", true)).toBe("9/28(월) 00:05");
    expect(fmtKst("not-a-date", false)).toBeNull();
    expect(fmtKst(null, true)).toBeNull();
  });
});

// POC3-02D-OPS-04 항목 3 · 6(사용자 목업 확정 2026-10-06) — 새 2행 · ② 전달 뒤 다시 읽기.
describe("OciStatusPanel — 장중 대표 ETF · 운영 기준 활성 행", () => {
  function withRows(reps: { status: string; detail: string }, param: { status: string; detail: string }) {
    const s = operating();
    return {
      ...s,
      jobs: [
        ...s.jobs,
        { job: "intraday_representatives", ...reps },
        { job: "param_active", ...param },
      ],
    };
  }

  it.each([
    ["SUCCESS", "정상", "SUCCESS", "일치"],
    ["STALE", "확인 필요", "STALE", "다름"],
    ["UNKNOWN", "확인 불가", "UNKNOWN", "확인 불가"],
  ])("상태 %s → %s · %s → %s", async (rs, rl, ps, pl) => {
    fetchOciStartupStatus.mockResolvedValue(
      withRows({ status: rs, detail: "기준일 10/2 · 26/27 준비됨" }, { status: ps, detail: "값 비교 문구" }),
    );
    const { container } = render(<OciStatusPanel />);
    await screen.findByText("정상 운영 중");
    const reps = within(rowOf("장중 대표 ETF"));
    expect(reps.getByText(rl)).toBeInTheDocument();
    expect(reps.getByText("기준일 10/2 · 26/27 준비됨")).toBeInTheDocument();
    const param = within(rowOf("운영 기준 활성"));
    expect(param.getByText(pl)).toBeInTheDocument();
    expect(param.getByText("값 비교 문구")).toBeInTheDocument();
    // 영어 job 이름 · 내부 상태값을 그대로 보이지 않는다.
    expect(container.textContent).not.toMatch(/intraday_representatives|param_active|SUCCESS|STALE/);
  });

  it("확인 불가 행은 백엔드 문구만 보인다(숫자 · 0/27 을 만들지 않는다)", async () => {
    fetchOciStartupStatus.mockResolvedValue(
      withRows(
        { status: "UNKNOWN", detail: "기록을 읽지 못함" },
        { status: "UNKNOWN", detail: "OCI 에서 쓰는 값을 읽지 못함" },
      ),
    );
    render(<OciStatusPanel />);
    await screen.findByText("정상 운영 중");
    const reps = rowOf("장중 대표 ETF");
    expect(within(reps).getByText("기록을 읽지 못함")).toBeInTheDocument();
    expect(reps.textContent).not.toMatch(/\d+\/\d+/);
    expect(within(rowOf("운영 기준 활성")).getByText("OCI 에서 쓰는 값을 읽지 못함")).toBeInTheDocument();
  });

  it("처음 조회가 실패해도 다시 읽기가 성공하면 오류를 지우고 표를 보인다", async () => {
    fetchOciStartupStatus.mockRejectedValueOnce(new Error("backend restarting"));
    const { rerender } = render(<OciStatusPanel reloadKey={0} />);
    expect(await screen.findByText(/알 수 없는 오류/)).toBeInTheDocument();
    fetchOciStartupStatus.mockResolvedValue(operating());
    rerender(<OciStatusPanel reloadKey={1} />);
    expect(await screen.findByText("정상 운영 중")).toBeInTheDocument();
    expect(screen.queryByText(/알 수 없는 오류/)).toBeNull();
  });

  it("reloadKey 가 바뀌면 다시 읽는다(② 전달 뒤 · OCI 재조회는 백엔드가 하지 않는다)", async () => {
    fetchOciStartupStatus.mockResolvedValue(operating());
    const { rerender } = render(<OciStatusPanel reloadKey={0} />);
    await screen.findByText("정상 운영 중");
    expect(fetchOciStartupStatus).toHaveBeenCalledTimes(1);
    rerender(<OciStatusPanel reloadKey={1} />);
    await screen.findByText("정상 운영 중");
    expect(fetchOciStartupStatus).toHaveBeenCalledTimes(2);
  });
});
