// 「OCI 운영 상태」 요약 + 표 (2026-09-27 사용자 직접 지시 · 가독성) test.
//
// 표시만 바꿨다 — 응답은 백엔드 `oci_startup_status` 가 실제로 만드는 모양 그대로
// fixture 로 둔다(job 이름 · 상태값 · detail 문구 · UTC ISO 시각).
//
// 2026-09-27 사용자 직접 지시: 이 패널은 「OCI 운영·적용」 화면의 ① 섹션으로
// 들어갔다(`oci_status` 메뉴 없음). 자기 h1 을 두지 않는다 — 화면 제목 · 섹션
// 제목은 ApprovalTelegramView 가 단다(ApprovalTelegramView.test.tsx).
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, within, waitFor } from "@testing-library/react";

const fetchOciStartupStatus = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchOciStartupStatus: (...a: unknown[]) => fetchOciStartupStatus(...a),
  };
});

import OciStatusPanel, { fmtKst, subtitleOf } from "./OciStatusView";

// POC6-34 O1 — 부제 공통 꼬리(언제 읽은 값인지 · 재시작 포함).
const BASIS = "PC 백엔드가 시작될 때 한 번 읽음(재시작 포함)";
// POC6-34 O2 — 성공 요약.
const OK_TITLE = "예약표에서 필수 3종 표기 확인";
const OK_SUB =
  "시장 브리핑 · 보유 브리핑 · 장중 급등락 예약 표기가 OCI 예약표에 있습니다 · 실제 수신은 Telegram 에서 확인";
const HOLD_TAIL = "보유 적용 상태는 「종목 관리」 맨 아래 ‘OCI 적용’에서 확인";
const DB_TAIL = "(알림 실행 기록도 이 파일에 씀)";

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

    expect(await screen.findByText(OK_TITLE)).toBeInTheDocument();
    // 패널이다 — 화면 제목(h1)은 합친 화면이 단다.
    expect(container.querySelector("h1")).toBeNull();
    expect(screen.getByText(OK_SUB)).toBeInTheDocument();
    // 09:58 UTC = 18:58 KST (2026-09-27 일요일)
    expect(screen.getByText(`확인 시각 9/27(일) 18:58 · ${BASIS}`)).toBeInTheDocument();

    const cron = within(rowOf("자동 발송 예약"));
    expect(cron.getByText("정상")).toBeInTheDocument();
    expect(cron.getByText("시장 브리핑 · 보유 브리핑 · 장중 급등락")).toBeInTheDocument();
    // 14:41 UTC = 23:41 KST · 06:40 UTC = 15:40 KST
    const hold = within(rowOf("보유 종목 파일"));
    expect(hold.getByText("파일 확인")).toBeInTheDocument();
    expect(hold.getByText(`파일 수정 시각 8/9 23:41 · ${HOLD_TAIL}`)).toBeInTheDocument();
    const db = within(rowOf("운영 설정 DB"));
    expect(db.getByText("파일 확인")).toBeInTheDocument();
    expect(db.getByText(`DB 파일 수정 시각 9/25 15:40 ${DB_TAIL}`)).toBeInTheDocument();
    const push = within(rowOf("PUSH 발송 결과"));
    expect(push.getByText("확인 불가")).toBeInTheDocument();
    expect(push.getByText(/Telegram 에서 확인/)).toBeInTheDocument();

    // 읽기 어렵던 원문(영어 job 이름 · 상태 코드 · UTC ISO · 내부 표기)은 보이지 않는다.
    const text = container.textContent ?? "";
    for (const raw of ["crontab", "SUCCESS", "UNKNOWN", "OPERATING", "(Q5)", "T14:41:44", "bytes"]) {
      expect(text).not.toContain(raw);
    }
    // POC6-34 — '지금' · '정상 운영' · '기동 1번' 처럼 넓게 읽히던 옛 문구는 없다.
    for (const old of ["정상 운영 중", "자동 발송 예약이 모두 등록", "PC 백엔드 시작 때 1번 확인", "마지막 수정 "]) {
      expect(text).not.toContain(old);
    }
  });

  it("일부 누락: 빠진 예약을 한국어 이름으로", async () => {
    const s = operating();
    s.overall = "DEGRADED";
    s.jobs[0] = { job: "crontab", status: "STALE", detail: "일부 스케줄 누락: holdings_risk_alert" };
    fetchOciStartupStatus.mockResolvedValue(s);
    render(<OciStatusPanel />);

    expect(await screen.findByText("예약표에서 필수 3종 중 일부 표기 없음")).toBeInTheDocument();
    expect(screen.getByText("빠진 예약: 장중 급등락")).toBeInTheDocument();
    const cron = within(rowOf("자동 발송 예약"));
    expect(cron.getByText("일부 누락")).toBeInTheDocument();
    expect(cron.getByText("빠짐: 장중 급등락")).toBeInTheDocument();
  });

  it("접속 실패: 예약표 확인 불가 + 백엔드 사유 한 줄 · 표 없음 · 마지막 점검 시도", async () => {
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

    expect(await screen.findByText("예약표 확인 불가")).toBeInTheDocument();
    expect(screen.getByText("OCI 상태 미확인 (OCI_SSH_TARGET 미설정)")).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
    // 점검 실패 — 시각은 '확인 시각' 이 아니라 '마지막 점검 시도'.
    expect(screen.getByText(`마지막 점검 시도 9/27(일) 18:58 · ${BASIS}`)).toBeInTheDocument();
    expect(screen.queryByText(/확인 시각/)).toBeNull();
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
    await screen.findByText(OK_TITLE);
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
    await screen.findByText(OK_TITLE);
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
    expect(await screen.findByText(OK_TITLE)).toBeInTheDocument();
    expect(screen.queryByText(/알 수 없는 오류/)).toBeNull();
  });

  it("reloadKey 가 바뀌면 다시 읽는다(② 전달 뒤 · OCI 재조회는 백엔드가 하지 않는다)", async () => {
    fetchOciStartupStatus.mockResolvedValue(operating());
    const { rerender } = render(<OciStatusPanel reloadKey={0} />);
    await screen.findByText(OK_TITLE);
    expect(fetchOciStartupStatus).toHaveBeenCalledTimes(1);
    rerender(<OciStatusPanel reloadKey={1} />);
    await screen.findByText(OK_TITLE);
    expect(fetchOciStartupStatus).toHaveBeenCalledTimes(2);
  });

  it("아래 안내: 마지막 점검 값 · '운영 기준 활성' 행만 ② 적용 때 다시 읽은 값으로 바뀐다(POC5-27 · POC6-34 O4)", async () => {
    fetchOciStartupStatus.mockResolvedValue(operating());
    render(<OciStatusPanel />);
    await screen.findByText(OK_TITLE);
    expect(
      screen.getByText(
        "PC 백엔드가 시작될 때(재시작 포함) 한 번 읽은 마지막 점검 값입니다. 새로고침해도 OCI 를 다시 읽지 않습니다. ‘운영 기준 활성’ 행만 ② [현재 기준 OCI 적용] 때 다시 읽은 값으로 바뀝니다.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/PC 백엔드를 시작할 때 한 번 읽은 값입니다/)).toBeNull();
  });
});

// POC6-34 PLAN O1 ~ O4 · I-1 ~ I-4 · I-8 — 마지막 OCI 점검 · 예약표 범위 · 파일 확인 · 응답 전달.
describe("OciStatusPanel — 마지막 OCI 점검 (POC6-34)", () => {
  it.each([
    // [이름, 응답 변경, 부제]
    ["점검 성공 · 시각 있음", {}, `확인 시각 9/27(일) 18:58 · ${BASIS}`],
    ["점검 실패 · 시각 있음", { reachable: false, overall: "UNKNOWN", jobs: [] }, `마지막 점검 시도 9/27(일) 18:58 · ${BASIS}`],
    ["점검 성공 · 시각 없음", { checked_at: null }, BASIS],
    ["점검 실패 · 시각 없음(기동 읽기 예외)", { checked_at: null, reachable: false, overall: "UNKNOWN", jobs: [] }, BASIS],
    ["시각을 못 읽음", { checked_at: "not-a-date" }, BASIS],
  ])("부제 — %s", async (_name, change, want) => {
    fetchOciStartupStatus.mockResolvedValue({ ...operating(), ...change });
    render(<OciStatusPanel />);
    expect(await screen.findByText(want)).toBeInTheDocument();
    expect(document.querySelectorAll("p.subtitle")).toHaveLength(1);
    expect(document.querySelector("p.subtitle")?.textContent).toBe(want);
  });

  it("부제 — 응답 전 · 조회 오류는 읽는 때만(시각 없음)", async () => {
    let resolve: (v: unknown) => void = () => {};
    fetchOciStartupStatus.mockReturnValue(new Promise((r) => (resolve = r)));
    render(<OciStatusPanel />);
    expect(screen.getByText("확인 중…")).toBeInTheDocument();
    expect(document.querySelector("p.subtitle")?.textContent).toBe(BASIS);
    resolve(operating());
    expect(await screen.findByText(`확인 시각 9/27(일) 18:58 · ${BASIS}`)).toBeInTheDocument();
  });

  it("부제 — 앞서 성공했어도 다시 읽기가 실패하면 앞선 시각을 남기지 않는다", async () => {
    fetchOciStartupStatus.mockResolvedValueOnce(operating());
    const { rerender } = render(<OciStatusPanel reloadKey={0} />);
    expect(await screen.findByText(`확인 시각 9/27(일) 18:58 · ${BASIS}`)).toBeInTheDocument();
    fetchOciStartupStatus.mockRejectedValueOnce(new Error("down"));
    rerender(<OciStatusPanel reloadKey={1} />);
    expect(await screen.findByText("알 수 없는 오류: down")).toBeInTheDocument();
    expect(document.querySelector("p.subtitle")?.textContent).toBe(BASIS);
  });

  it("subtitleOf: 순수 분기(점검 성공 / 실패 / 시각 없음 / 응답 없음)", () => {
    const ok = operating();
    expect(subtitleOf(ok)).toBe(`확인 시각 9/27(일) 18:58 · ${BASIS}`);
    expect(subtitleOf({ ...ok, reachable: false })).toBe(`마지막 점검 시도 9/27(일) 18:58 · ${BASIS}`);
    expect(subtitleOf({ ...ok, checked_at: null })).toBe(BASIS);
    expect(subtitleOf(null)).toBe(BASIS);
  });

  it.each([
    // [overall, reachable, crontab 행, 제목, 부제]
    ["OPERATING", true, true, OK_TITLE, OK_SUB],
    ["DEGRADED", true, true, "예약표에서 필수 3종 중 일부 표기 없음", "빠진 예약: 보유 브리핑 · 장중 급등락"],
    ["DEGRADED", true, false, "예약표에서 필수 3종 중 일부 표기 없음", "백엔드 한 줄"],
    ["UNKNOWN", true, true, "예약표 확인 불가", "OCI 에서 자동 발송 예약을 읽지 못했습니다"],
    ["UNKNOWN", false, false, "예약표 확인 불가", "백엔드 한 줄"],
  ])("요약 — %s · 접속 %s · 예약 행 %s → %s", async (overall, reachable, cronRow, title, sub) => {
    const s = operating();
    s.overall = overall as string;
    s.reachable = reachable as boolean;
    s.summary_line = "백엔드 한 줄";
    s.jobs[0] = { job: "crontab", status: "STALE", detail: "일부 스케줄 누락: holdings_briefing, holdings_risk_alert" };
    if (!cronRow) s.jobs = s.jobs.slice(1);
    fetchOciStartupStatus.mockResolvedValue(s);
    render(<OciStatusPanel />);
    const box = await screen.findByRole("status");
    expect(within(box).getByText(title as string)).toBeInTheDocument();
    expect(within(box).getByText(sub as string)).toBeInTheDocument();
    // 옛 넓은 요약('정상 운영 중' · '일부 예약 누락')은 어느 분기에도 없다.
    expect(box.textContent).not.toContain("정상 운영");
    expect(box.textContent).not.toContain("일부 예약 누락");
  });

  it("요약 — 다른 행이 '확인 불가'여도 예약표 범위만 말한다(판정 로직 그대로)", async () => {
    // 발송 결과 행은 늘 '확인 불가' · 그래도 요약은 예약표 표기 확인(실제 수신은 Telegram).
    fetchOciStartupStatus.mockResolvedValue(operating());
    render(<OciStatusPanel />);
    expect(await screen.findByText(OK_TITLE)).toBeInTheDocument();
    expect(within(rowOf("PUSH 발송 결과")).getByText("확인 불가")).toBeInTheDocument();
  });

  it.each([
    // [job, status, detail, 상태 낱말, 내용]
    ["holdings_source", "SUCCESS", "holdings 소스 최근 수정 2026-08-09T14:41:44+00:00", "파일 확인", `파일 수정 시각 8/9 23:41 · ${HOLD_TAIL}`],
    ["holdings_source", "SUCCESS", "holdings 소스 시각 확인 불가", "파일 확인", "수정 시각 확인 불가"],
    ["holdings_source", "SUCCESS", "holdings 소스 파일 없음/확인 불가", "파일 확인", "수정 시각 확인 불가"],
    ["holdings_source", "UNKNOWN", "holdings 소스 파일 없음/확인 불가", "확인 불가", "파일 없음 또는 확인 불가"],
    ["runtime_state_db", "SUCCESS", "runtime_state.sqlite 최근 수정 2026-09-25T06:40:02+00:00 · 438272 bytes", "파일 확인", `DB 파일 수정 시각 9/25 15:40 ${DB_TAIL}`],
    ["runtime_state_db", "SUCCESS", "runtime_state.sqlite 시각 확인 불가 · 5 bytes", "파일 확인", "수정 시각 확인 불가"],
    // DB 크기 0 · 시각 있음 → 상태 '확인 불가' + 수정 시각(지금 조합 그대로).
    ["runtime_state_db", "UNKNOWN", "runtime_state.sqlite 최근 수정 2026-09-25T06:40:02+00:00 · 0 bytes", "확인 불가", `DB 파일 수정 시각 9/25 15:40 ${DB_TAIL}`],
    ["runtime_state_db", "UNKNOWN", "runtime_state.sqlite 파일 없음/확인 불가 · 0 bytes", "확인 불가", "파일 없음 또는 확인 불가"],
  ])("파일 행 — %s %s '%s' → %s · %s", async (job, status, detail, label, content) => {
    const s = operating();
    s.jobs = s.jobs.map((j) => (j.job === job ? { job, status, detail } : j));
    fetchOciStartupStatus.mockResolvedValue(s);
    const { container } = render(<OciStatusPanel />);
    await screen.findByText(OK_TITLE);
    const row = within(rowOf(job === "holdings_source" ? "보유 종목 파일" : "운영 설정 DB"));
    expect(row.getByText(label)).toBeInTheDocument();
    expect(row.getByText(content)).toBeInTheDocument();
    // 영문이 섞인 원문(holdings 소스 · runtime_state.sqlite · bytes)은 보이지 않는다.
    expect(container.textContent).not.toMatch(/holdings 소스|runtime_state|bytes/);
  });

  it("파일 확인은 두 파일 행만 — 다른 행의 '정상' 은 그대로(I-3)", async () => {
    const s = operating();
    s.jobs.push({ job: "trading_day_basis", status: "SUCCESS", detail: "평일 기본 운영" });
    fetchOciStartupStatus.mockResolvedValue(s);
    render(<OciStatusPanel />);
    await screen.findByText(OK_TITLE);
    expect(within(rowOf("자동 발송 예약")).getByText("정상")).toBeInTheDocument();
    expect(within(rowOf("거래일 기준")).getByText("정상")).toBeInTheDocument();
    expect(screen.getAllByText("파일 확인")).toHaveLength(2);
  });

  it("① 안에는 버튼이 없다 — 「종목 관리」 안내는 글로만", async () => {
    fetchOciStartupStatus.mockResolvedValue(operating());
    const { container } = render(<OciStatusPanel />);
    await screen.findByText(OK_TITLE);
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(screen.queryAllByRole("link")).toHaveLength(0);
    expect(container.textContent).toContain("「종목 관리」 맨 아래 ‘OCI 적용’에서 확인");
  });

  it("onStatus — 받은 응답을 그대로 · 조회 실패면 null · 다시 읽기 때마다", async () => {
    const onStatus = vi.fn();
    const first = operating();
    fetchOciStartupStatus.mockResolvedValueOnce(first);
    const { rerender } = render(<OciStatusPanel reloadKey={0} onStatus={onStatus} />);
    await waitFor(() => expect(onStatus).toHaveBeenCalledTimes(1));
    expect(onStatus.mock.calls[0][0]).toBe(first);

    fetchOciStartupStatus.mockRejectedValueOnce(new Error("down"));
    rerender(<OciStatusPanel reloadKey={1} onStatus={onStatus} />);
    await waitFor(() => expect(onStatus).toHaveBeenCalledTimes(2));
    expect(onStatus.mock.calls[1][0]).toBeNull();

    const third = { ...operating(), overall: "DEGRADED" };
    fetchOciStartupStatus.mockResolvedValueOnce(third);
    rerender(<OciStatusPanel reloadKey={2} onStatus={onStatus} />);
    await waitFor(() => expect(onStatus).toHaveBeenCalledTimes(3));
    expect(onStatus.mock.calls[2][0]).toBe(third);
  });

  it("onStatus — 부모가 새 함수를 넘겨도 다시 조회하지 않고 최신 함수로 알린다", async () => {
    let resolve: (v: unknown) => void = () => {};
    fetchOciStartupStatus.mockReturnValue(new Promise((r) => (resolve = r)));
    const a = vi.fn();
    const b = vi.fn();
    const { rerender } = render(<OciStatusPanel onStatus={a} />);
    rerender(<OciStatusPanel onStatus={b} />);
    const s = operating();
    resolve(s);
    await waitFor(() => expect(b).toHaveBeenCalledWith(s));
    expect(a).not.toHaveBeenCalled();
    expect(fetchOciStartupStatus).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["성공", true],
    ["실패", false],
  ])("onStatus — 화면을 떠난 뒤 늦게 온 %s 응답은 알리지 않는다", async (_name, ok) => {
    let resolve: (v: unknown) => void = () => {};
    let reject: (e: unknown) => void = () => {};
    fetchOciStartupStatus.mockReturnValue(
      new Promise((res, rej) => {
        resolve = res;
        reject = rej;
      }),
    );
    const onStatus = vi.fn();
    const { unmount } = render(<OciStatusPanel onStatus={onStatus} />);
    unmount();
    if (ok) resolve(operating());
    else reject(new Error("late"));
    for (let i = 0; i < 5; i += 1) await Promise.resolve();
    expect(onStatus).not.toHaveBeenCalled();
  });
});
