// POC6-15(2026-11-01) — 「이전 자료와 실험 다시 만들기」 카드 시험(가짜 응답 · 서버 없음).
//
// - 순서: 결론 한 줄 → 버튼 → 설명 → 단계 표 → 접힌 개발 정보.
// - 상태마다 다른 쉬운 한국어 결론(조회 실패 · 기록 없음 · 손상 · 모르는 값 포함).
// - 숫자 · 날짜 · 시각은 같은 값(건수만 쉼표).
// - 버튼은 같은 API 를 부르고 막힘 조건(시작 중 · 실행 중)은 그대로 · 실행 중 5초 다시 읽기 그대로.
// - 작업 번호 · 요청 위치 · 신호 시각 · 원문 · 파일 경로는 접힌 개발 정보 안.
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import type { MlJobLatestResponse, MlJobState, MlJobStepState } from "@/lib/api";

const fetchMlJobsLatest = vi.fn();
const startMlEvidenceRefresh = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchMlJobsLatest: (...a: unknown[]) => fetchMlJobsLatest(...a),
    startMlEvidenceRefresh: (...a: unknown[]) => startMlEvidenceRefresh(...a),
  };
});

import MLEvidenceRefreshCard from "./MLEvidenceRefreshCard";
import { ApiRequestError } from "@/lib/api";

type StepKey = keyof MlJobState["steps"];

// 2026-11-01 GET /ml/jobs/latest 실제 응답(읽기만 · 값 그대로).
const REAL: MlJobLatestResponse = {
  status: "ok",
  job_status_path: "state/ml/ml_job_status_latest.json",
  job: {
    job_id: "ml-evidence-refresh-20260830233833-17599",
    status: "success",
    started_at: "2026-08-30T23:38:33.859412+0900",
    finished_at: "2026-08-30T23:38:54.226270+0900",
    requested_by: "ui",
    pid: 17599,
    last_heartbeat_at: "2026-08-30T23:38:54.226281+0900",
    steps: {
      feature_generation: {
        status: "success",
        started_at: "2026-08-30T23:38:33.863859+0900",
        finished_at: "2026-08-30T23:38:37.934241+0900",
        message: '{"last_asof": "2026-08-27", "etf_upserted": 68872, "market_upserted": 60}',
        artifact_path: "state/ml/ml_feature_snapshot_latest.json",
      },
      sanity_check: {
        status: "success",
        started_at: "2026-08-30T23:38:37.934769+0900",
        finished_at: "2026-08-30T23:38:39.909372+0900",
        message:
          '{"sanity_status": "warn", "etf_feature_rows": 1382327, "warnings": 4, "errors": 0}',
        artifact_path: "state/ml/ml_feature_sanity_latest.json",
      },
      baseline_lookback: {
        status: "success",
        started_at: "2026-08-30T23:38:39.909848+0900",
        finished_at: "2026-08-30T23:38:54.225803+0900",
        message:
          '{"feature_asof_end": "2026-08-27", "evaluated_days": 2998, "baseline_report_status": "ok"}',
        artifact_path: "state/ml/ml_baseline_v0_report_latest.json",
      },
    },
    last_success_summary: {
      feature_asof_end: "2026-08-27",
      evaluated_days: 2998,
      baseline_report_status: "ok",
    },
    message: "all steps succeeded",
    error: null,
  },
  message: null,
};

const QUEUED_STEP: MlJobStepState = {
  status: "queued",
  started_at: null,
  finished_at: null,
  message: "",
  artifact_path: "",
};

function withJob(
  over: Partial<MlJobState>,
  steps: Partial<Record<StepKey, Partial<MlJobStepState>>> = {},
): MlJobLatestResponse {
  const base = REAL.job as MlJobState;
  const merged = { ...base.steps };
  for (const k of Object.keys(steps) as StepKey[]) {
    merged[k] = { ...base.steps[k], ...steps[k] };
  }
  return { ...REAL, job: { ...base, ...over, steps: merged } };
}

const RUNNING = withJob(
  { status: "running", finished_at: null, last_success_summary: null, message: "" },
  {
    sanity_check: { status: "running", finished_at: null, message: "" },
    baseline_lookback: { ...QUEUED_STEP },
  },
);

const QUEUED = withJob(
  { status: "queued", finished_at: null, last_success_summary: null, message: "" },
  {
    feature_generation: { ...QUEUED_STEP },
    sanity_check: { ...QUEUED_STEP },
    baseline_lookback: { ...QUEUED_STEP },
  },
);

const FAILED_KNOWN = withJob(
  {
    status: "failed",
    last_success_summary: null,
    message: "",
    error: "sanity_check: sanity_status=error / errors=2 warnings=5",
  },
  {
    sanity_check: { status: "failed", message: "sanity_status=error / errors=2 warnings=5" },
    baseline_lookback: { ...QUEUED_STEP, status: "skipped", message: "이전 단계 실패" },
  },
);

const FAILED_UNKNOWN = withJob(
  {
    status: "failed",
    last_success_summary: null,
    message: "",
    error: "feature_generation: database is locked",
  },
  {
    feature_generation: { status: "failed", message: "database is locked" },
    sanity_check: { ...QUEUED_STEP, status: "skipped", message: "이전 단계 실패" },
    baseline_lookback: { ...QUEUED_STEP, status: "skipped", message: "이전 단계 실패" },
  },
);

const UNKNOWN_JOB = withJob({ status: "paused" });

const EMPTY: MlJobLatestResponse = {
  status: "empty",
  job_status_path: "state/ml/ml_job_status_latest.json",
  job: null,
  message:
    "ML evidence 갱신 job 이 아직 한 번도 실행되지 않았습니다. 'ML evidence 갱신 실행' 버튼을 누르면 background 로 시작됩니다.",
};

const CORRUPT: MlJobLatestResponse = {
  status: "error",
  job_status_path: "state/ml/ml_job_status_latest.json",
  job: null,
  message:
    "ml_job_status 파일이 손상되어 읽을 수 없습니다: Expecting value: line 1 column 1 (char 0). 파일을 삭제하거나 직접 확인 후 재시도하세요.",
};

const OK_NO_JOB: MlJobLatestResponse = { ...REAL, job: null };
const UNKNOWN_RESP = { ...REAL, status: "weird", job: null } as unknown as MlJobLatestResponse;

function card(): HTMLElement {
  return document.querySelector(".card") as HTMLElement;
}
function conclusion(): HTMLElement {
  return document.querySelector('[data-role="conclusion"]') as HTMLElement;
}
function devDetails(): HTMLElement | null {
  return document.querySelector("details.ml-dev-details");
}
function before(a: Node, b: Node): boolean {
  return Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
}
const startBtn = () => screen.getByRole("button", { name: "이전 자료와 실험 다시 만들기" });
const reloadBtn = () => screen.getByRole("button", { name: "상태 다시 읽기" });

beforeEach(() => {
  fetchMlJobsLatest.mockReset();
  startMlEvidenceRefresh.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("MLEvidenceRefreshCard", () => {
  it("순서 — 결론 → 버튼 → 설명 → 단계 표 → 개발 정보", async () => {
    fetchMlJobsLatest.mockResolvedValue(REAL);
    render(<MLEvidenceRefreshCard />);
    await screen.findByRole("table");
    const h2 = screen.getByRole("heading", { level: 2, name: "이전 자료와 실험 다시 만들기" });
    const desc = screen.getByText(/한 번에 다시/);
    expect(desc).toHaveTextContent("현재 예측 비교의 입력이나 모델은 바뀌지 않습니다.");
    const order = [h2, conclusion(), startBtn(), reloadBtn(), desc, screen.getByRole("table"), devDetails()!];
    for (let i = 0; i + 1 < order.length; i++) expect(before(order[i], order[i + 1])).toBe(true);
    expect(devDetails()).not.toHaveAttribute("open");
  });

  const CASES: Array<[string, MlJobLatestResponse | "fetch-error" | "loading", string, RegExp]> = [
    ["불러오는 중", "loading", "불러오는 중", /실행 기록을 읽는 중입니다/],
    ["조회 실패", "fetch-error", "불러오지 못함", /서버에서 받지 못했습니다 · 원인 확인 필요/],
    ["기록 없음", EMPTY, "실행 기록 없음", /아직 한 번도 실행하지 않았습니다/],
    ["상태 기록 손상", CORRUPT, "상태 기록 손상", /읽을 수 없습니다 · 원인 확인 필요/],
    ["정상 응답 · 기록 내용 없음", OK_NO_JOB, "기록 내용 없음", /원인 확인 필요/],
    ["모르는 응답 상태", UNKNOWN_RESP, "알 수 없는 응답", /응답 상태 'weird' · 원인 확인 필요/],
    [
      "완료",
      REAL,
      "완료",
      /^2026-08-30 23:38 실행 · 3단계 모두 완료 · 약 20초 · 완료는 실험 채택을 뜻하지 않음$/,
    ],
    ["실행 중", RUNNING, "실행 중", /^2026-08-30 23:38 시작 · 지금 「자료 점검」 단계$/],
    ["시작 대기", QUEUED, "시작 대기", /^2026-08-30 23:38 요청 · 첫 단계 시작을 기다리는 중$/],
    [
      "실패(알려진 문장)",
      FAILED_KNOWN,
      "실패",
      /「자료 점검」 단계에서 실패 · 점검 결과 '오류' · 오류 2건 · 경고 5건/,
    ],
    [
      "실패(모르는 사유)",
      FAILED_UNKNOWN,
      "실패",
      /「이전 학습용 값 만들기」 단계에서 실패 · 원인 확인 필요$/,
    ],
    ["모르는 작업 상태", UNKNOWN_JOB, "알 수 없는 상태", /상태 값 'paused' · 원인 확인 필요/],
  ];

  it.each(CASES)("상태별 결론 — %s", async (_name, input, label, text) => {
    if (input === "loading") fetchMlJobsLatest.mockReturnValue(new Promise(() => {}));
    else if (input === "fetch-error")
      fetchMlJobsLatest.mockRejectedValue(new ApiRequestError("boom", 500, null));
    else fetchMlJobsLatest.mockResolvedValue(input);
    render(<MLEvidenceRefreshCard />);
    await waitFor(() => expect(conclusion().querySelector(".ml-readiness-badge")).toHaveTextContent(label));
    const body = conclusion().querySelector(".ml-conclusion-text") as HTMLElement;
    expect(body.textContent).toMatch(text);
  });

  it("상태마다 결론 문장이 서로 다름(합치지 않음)", async () => {
    const seen = new Set<string>();
    for (const [, input] of CASES) {
      fetchMlJobsLatest.mockReset();
      if (input === "loading") fetchMlJobsLatest.mockReturnValue(new Promise(() => {}));
      else if (input === "fetch-error")
        fetchMlJobsLatest.mockRejectedValue(new ApiRequestError("boom", 500, null));
      else fetchMlJobsLatest.mockResolvedValue(input);
      const { unmount } = render(<MLEvidenceRefreshCard />);
      if (input !== "loading") {
        await waitFor(() => expect(conclusion()).not.toHaveTextContent("불러오는 중"));
      }
      seen.add(conclusion().textContent ?? "");
      unmount();
    }
    expect(seen.size).toBe(CASES.length);
  });

  it("본문 — 조회 실패 · 손상 · 기록 없음 · 모르는 실패 사유는 원문(또는 쉬운 말)이 보임", async () => {
    fetchMlJobsLatest.mockRejectedValue(new ApiRequestError("boom", 500, null));
    const a = render(<MLEvidenceRefreshCard />);
    expect(await screen.findByText("상태를 읽지 못했습니다 — 요청 실패(HTTP 500): boom")).toBeInTheDocument();
    a.unmount();

    fetchMlJobsLatest.mockResolvedValue(CORRUPT);
    const b = render(<MLEvidenceRefreshCard />);
    expect(await screen.findByText(/실행 상태 기록 파일이 손상되어 읽을 수 없습니다/)).toBeInTheDocument();
    expect(devDetails()).toHaveTextContent("Expecting value: line 1 column 1 (char 0)");
    b.unmount();

    fetchMlJobsLatest.mockResolvedValue(EMPTY);
    const c = render(<MLEvidenceRefreshCard />);
    expect(await screen.findByText(/「이전 자료와 실험 다시 만들기」 버튼을 누르면 뒤에서 시작합니다/)).toBeInTheDocument();
    expect(devDetails()).toHaveTextContent("'ML evidence 갱신 실행' 버튼을 누르면 background 로 시작됩니다.");
    c.unmount();

    fetchMlJobsLatest.mockResolvedValue(FAILED_UNKNOWN);
    render(<MLEvidenceRefreshCard />);
    expect(await screen.findByText("실패 내용: 원인 확인 필요 · 원문 feature_generation: database is locked")).toBeInTheDocument();
    expect(screen.getByText("원인 확인 필요 · 원문 database is locked")).toBeInTheDocument();
    expect(screen.getAllByText("건너뜀")).toHaveLength(2);
    expect(screen.getAllByText("이전 단계가 실패해 실행하지 않음")).toHaveLength(2);
  });

  it("숫자 · 날짜 · 시각 — 같은 값(건수만 쉼표)", async () => {
    fetchMlJobsLatest.mockResolvedValue(REAL);
    render(<MLEvidenceRefreshCard />);
    expect(
      await screen.findByText("마지막 자료일 2026-08-27 · ETF 68,872줄 · 시장 60줄 저장"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("점검 결과 '주의' · ETF 학습용 값 1,382,327줄 · 경고 4건 · 오류 0건"),
    ).toBeInTheDocument();
    expect(screen.getByText("자료 끝 2026-08-27 · 평가 2,998거래일 · 보고 있음")).toBeInTheDocument();
    expect(
      screen.getByText("시작 2026-08-30 23:38:33 · 끝 2026-08-30 23:38:54 (한국 시각)"),
    ).toBeInTheDocument();
    const rows = screen.getAllByRole("row").slice(1) as HTMLTableRowElement[];
    const times = rows.map((r) => [r.cells[2].textContent, r.cells[3].textContent]);
    expect(times).toEqual([
      ["23:38:33", "23:38:37"],
      ["23:38:37", "23:38:39"],
      ["23:38:39", "23:38:54"],
    ]);
    expect(rows.map((r) => r.cells[1].textContent)).toEqual(["완료", "완료", "완료"]);
  });

  it("자료 저장 0건 실패 — 한쪽만 0 이어도 '둘 다 0' 으로 쓰지 않음(서버 조건 = 또는)", async () => {
    const msg =
      "feature generation upsert 0건 — etf=68872 market=0. 두 산출물 모두 필수이며 DB 가 비어있거나 universe coverage 0 이다";
    fetchMlJobsLatest.mockResolvedValue(
      withJob(
        { status: "failed", last_success_summary: null, message: "", error: `feature_generation: ${msg}` },
        {
          feature_generation: { status: "failed", message: msg },
          sanity_check: { ...QUEUED_STEP, status: "skipped", message: "이전 단계 실패" },
          baseline_lookback: { ...QUEUED_STEP, status: "skipped", message: "이전 단계 실패" },
        },
      ),
    );
    render(<MLEvidenceRefreshCard />);
    await waitFor(() => expect(conclusion()).toHaveTextContent("실패"));
    expect(conclusion()).toHaveTextContent(
      "「이전 학습용 값 만들기」 단계에서 실패 · ETF · 시장 값 중 저장된 줄이 0건인 쪽이 있음(ETF 68,872줄 · 시장 0줄)",
    );
    expect(conclusion()).not.toHaveTextContent("원인 확인 필요");
    expect(devDetails()).toHaveTextContent(`실패 원문: feature_generation: ${msg}`);
  });

  it("틀에 안 맞는 단계 메시지는 원문 그대로", async () => {
    fetchMlJobsLatest.mockResolvedValue(
      withJob({}, { feature_generation: { message: "rows=12 (new format)" } }),
    );
    render(<MLEvidenceRefreshCard />);
    expect(await screen.findByText("rows=12 (new format)")).toBeInTheDocument();
  });

  it("개발 정보 — 작업 번호 · 요청 위치 · 신호 · 원문 · 파일 경로는 접힌 칸 안에만", async () => {
    fetchMlJobsLatest.mockResolvedValue(REAL);
    render(<MLEvidenceRefreshCard />);
    await screen.findByRole("table");
    const dev = devDetails()!;
    const inside = dev.textContent ?? "";
    const outside = (card().textContent ?? "").replace(inside, "");
    const moved = [
      "ml-evidence-refresh-20260830233833-17599",
      "요청 위치 ui",
      "2026-08-30T23:38:54.226281+0900",
      "2026-08-30T23:38:33.863859+0900", // 단계 시작 원문(표에는 한국 시각 초까지만)
      '{"last_asof": "2026-08-27", "etf_upserted": 68872, "market_upserted": 60}',
      "state/ml/ml_feature_snapshot_latest.json",
      "state/ml/ml_baseline_v0_report_latest.json",
      "all steps succeeded",
      '"evaluated_days": 2998',
    ];
    for (const s of moved) {
      expect(inside).toContain(s);
      expect(outside).not.toContain(s);
    }
    expect(outside).not.toContain("17599");
  });

  it("버튼 — 같은 API 호출 · 시작 중이면 둘 다 막힘 · 끝나면 다시 읽기", async () => {
    fetchMlJobsLatest.mockResolvedValue(REAL);
    let resolveStart!: (v: unknown) => void;
    startMlEvidenceRefresh.mockReturnValue(new Promise((r) => (resolveStart = r)));
    render(<MLEvidenceRefreshCard />);
    await screen.findByRole("table");
    expect(startBtn()).toBeEnabled();
    expect(reloadBtn()).toBeEnabled();
    fireEvent.click(startBtn());
    expect(startMlEvidenceRefresh).toHaveBeenCalledTimes(1);
    expect(startBtn()).toBeDisabled();
    expect(reloadBtn()).toBeDisabled();
    await act(async () => {
      resolveStart({ status: "accepted", job_status_path: "x", job: null, message: "ML evidence refresh job 이 background 로 시작되었습니다." });
    });
    expect(await screen.findByText("이전 자료와 실험 다시 만들기를 시작했습니다. 뒤에서 이어서 실행됩니다.")).toBeInTheDocument();
    expect(fetchMlJobsLatest).toHaveBeenCalledTimes(2);
    expect(startBtn()).toBeEnabled();

    fireEvent.click(reloadBtn());
    await waitFor(() => expect(fetchMlJobsLatest).toHaveBeenCalledTimes(3));
    expect(startMlEvidenceRefresh).toHaveBeenCalledTimes(1);
  });

  it("실행 중 · 시작 대기 — 시작 버튼만 막힘 · 다시 읽기는 열림", async () => {
    for (const input of [RUNNING, QUEUED]) {
      fetchMlJobsLatest.mockResolvedValue(input);
      const { unmount } = render(<MLEvidenceRefreshCard />);
      await screen.findByRole("table");
      expect(startBtn()).toBeDisabled();
      expect(reloadBtn()).toBeEnabled();
      expect(screen.getByText("실행 중 · 5초마다 상태를 자동으로 다시 읽습니다.")).toBeInTheDocument();
      unmount();
    }
    for (const input of [REAL, FAILED_KNOWN, UNKNOWN_JOB, EMPTY, CORRUPT]) {
      fetchMlJobsLatest.mockResolvedValue(input);
      const { unmount } = render(<MLEvidenceRefreshCard />);
      await waitFor(() => expect(conclusion()).not.toHaveTextContent("불러오는 중"));
      expect(startBtn()).toBeEnabled();
      unmount();
    }
  });

  it("실행 중이면 5초마다 다시 읽고, 끝나면 멈춤", async () => {
    vi.useFakeTimers();
    fetchMlJobsLatest.mockResolvedValueOnce(RUNNING).mockResolvedValueOnce(RUNNING).mockResolvedValue(REAL);
    render(<MLEvidenceRefreshCard />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(fetchMlJobsLatest).toHaveBeenCalledTimes(1);
    await act(async () => {
      vi.advanceTimersByTime(4999);
    });
    expect(fetchMlJobsLatest).toHaveBeenCalledTimes(1);
    await act(async () => {
      vi.advanceTimersByTime(1);
    });
    expect(fetchMlJobsLatest).toHaveBeenCalledTimes(2);
    await act(async () => {
      vi.advanceTimersByTime(5000);
    });
    expect(fetchMlJobsLatest).toHaveBeenCalledTimes(3);
    expect(conclusion()).toHaveTextContent("완료");
    await act(async () => {
      vi.advanceTimersByTime(20000);
    });
    expect(fetchMlJobsLatest).toHaveBeenCalledTimes(3);
  });

  it("시작 요청 결과 — 버튼 옆에 쉬운 말 + 원문", async () => {
    const cases: Array<[unknown, string]> = [
      [
        { status: "error", job_status_path: "x", job: null, message: "시계열 최신화가 완료되지 않았습니다. PC에서 시계열 최신화 배치를 실행한 뒤 다시 시도하세요." },
        "시작하지 못했습니다: 시계열 최신화가 완료되지 않았습니다. PC에서 시계열 최신화 배치를 실행한 뒤 다시 시도하세요.",
      ],
      [
        { status: "already_running", job_status_path: "x", job: null, message: "ML evidence refresh is already running" },
        "이미 실행 중인 작업이 있어 새로 시작하지 않았습니다.",
      ],
      [
        {
          status: "error",
          job_status_path: "x",
          job: null,
          message:
            "ml_job_status 파일 손상 (state/ml/ml_job_status_latest.json): Expecting value: line 1 column 1 (char 0)",
        },
        "시작하지 못했습니다: 실행 상태 기록 파일이 손상되어 새로 시작하지 않았습니다 · 원인 확인 필요(원문은 아래 자세한 정보)",
      ],
      [
        { status: "error", job_status_path: "x", job: null, message: null },
        "시작하지 못했습니다: 서버가 사유를 보내지 않았습니다 · 원인 확인 필요",
      ],
      [
        { status: "deferred", job_status_path: "x", job: null, message: null },
        "시작 요청 결과를 알 수 없습니다(응답 상태 'deferred') · 원인 확인 필요",
      ],
    ];
    for (const [res, text] of cases) {
      fetchMlJobsLatest.mockResolvedValue(REAL);
      startMlEvidenceRefresh.mockReset();
      startMlEvidenceRefresh.mockResolvedValue(res);
      const { unmount } = render(<MLEvidenceRefreshCard />);
      await screen.findByRole("table");
      fireEvent.click(startBtn());
      const note = await screen.findByText(text);
      expect(before(reloadBtn(), note)).toBe(true);
      expect(before(note, screen.getByText(/한 번에 다시/))).toBe(true);
      const r = res as { status: string; message: string | null };
      expect(devDetails()).toHaveTextContent(`시작 요청 응답 원문: status=${r.status} · message=${r.message ?? "-"}`);
      unmount();
    }
    expect(devDetails()).toBeNull();

    fetchMlJobsLatest.mockResolvedValue(REAL);
    startMlEvidenceRefresh.mockRejectedValue(new ApiRequestError("down", 503, null));
    render(<MLEvidenceRefreshCard />);
    await screen.findByRole("table");
    fireEvent.click(startBtn());
    expect(
      await screen.findByText("시작 요청을 보내지 못했습니다 — 요청 실패(HTTP 503): down"),
    ).toBeInTheDocument();
    expect(devDetails()).not.toHaveTextContent("시작 요청 응답 원문");
  });
});
