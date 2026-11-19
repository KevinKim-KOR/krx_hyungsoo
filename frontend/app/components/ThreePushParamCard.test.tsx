// 「현재 운영 기준」 카드 — 행 표시 계약 (2026-09-27 배치 정리 · 검토 반영).
//
// '마지막 적용 요청' 의 시각은 `YYYY-MM-DD HH:MM`(없으면 '—') 그대로다 — POC2 지시문 §5.2 의
// 표시 계약이라 한국식 짧은 날짜(9/22(화) 등)로 바꾸지 않는다. 버튼 문구 · 버튼 하나를 고정한다.
//
// 2026-10-20 POC5-27(PLAN 판정 · 사용자 목업 확인): 버튼 = [현재 기준 OCI 적용](실제 활성화 +
// 다시 읽어 확인). 결과 4종 · 예전 전달 기록 표시 · 적용 뒤 ① 다시 읽기(onDelivered)를 고정한다.
//
// 2026-11-19 POC6-34(PLAN 판정 Q4 · PLAN O5 ~ O7 · I-9 ~ I-12): 머리 배지 = 지금 적용할 일
// (GET /oci/startup-status 의 'param_active' 행 상태 + param_read_at) · 'OCI 활성값 마지막 확인' ·
// '마지막 적용 요청 {applied_at} · 결과 {낱말}' · 일치일 때만 버튼이 [자세히 보기] 안.
// POC6-34 r1(검증자 R1-F2) + RESULT 판정 C3: 적용 응답을 못 받았거나 HTTP 오류 응답이면 줄 이름이
// '최근 적용 시도'(값 = 버튼 누른 한국 시각 · 고정 시계 · '결과 확인 불가(…)')이고, 그 바로 아래
// ('요청 결과' 앞)에 '이전에 확인한 서버 요청 기록'(마지막으로 확인된 서버 기록) 줄이 온다.
// 정상 서버 기록은 그대로 '마지막 적용 요청'이다.
// 모든 값은 시험용 고정 자료다. 실제 적용 요청은 대역(mock)만 부른다.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";

vi.mock("@/lib/api/threePushParam", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/threePushParam")>(
    "@/lib/api/threePushParam",
  );
  return {
    ...actual,
    fetchThreePushParamState: vi.fn(),
    applyThreePushParamToOci: vi.fn(),
  };
});

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, fetchOciStartupStatus: vi.fn() };
});

import ThreePushParamCard, { paramVerdict, type OciStatusInput } from "./ThreePushParamCard";
import {
  ApiConfigError,
  ApiRequestError,
  fetchOciStartupStatus,
  type OciJobStatus,
  type OciStartupStatus,
} from "@/lib/api";
import {
  applyThreePushParamToOci,
  fetchThreePushParamState,
  type ThreePushParamState,
} from "@/lib/api/threePushParam";

function rowValue(container: HTMLElement, label: string): string | null {
  const dt = Array.from(container.querySelectorAll("dt")).find(
    (d) => d.textContent === label,
  );
  return dt ? (dt.nextElementSibling?.textContent ?? null) : null;
}
function headBadge(container: HTMLElement): HTMLElement | null {
  return container.querySelector(".ops-card-head .oci-state");
}

// ── 고정 자료 ───────────────────────────────────────────────────────────────
const APPLIED: ThreePushParamState = {
  status: "active_same",
  display_label: "기본 운영 기준",
  applied_at: "2026-10-20 13:14",
  oci_verified: true,
  message: "OCI 활성값이 이미 지금 기준과 같습니다 (14/14). 새로 바꾼 것은 없습니다.",
};
const NOTE =
  "OCI 러너가 이후 실행에서 읽는 기준을 적용합니다. 이미 시작한 실행은 그때 읽은 기준으로 끝납니다. 지금 OCI 활성값과의 차이는 위 ① 표 ‘운영 기준 활성’ 행에 있습니다.";
const DETAILS_NOTE =
  "확인값 기준으로 지금 적용할 변경은 없습니다. 다시 적용하면 먼저 OCI 활성값을 읽고, 같으면 OCI 에 쓰지 않습니다.";

const NONE = "확인값 기준으로 적용할 변경 없음";
const CHANGES = "적용할 변경 있음";
const UNKNOWN = "적용할 변경 확인 불가";
const CHECKING = "적용할 변경 확인 중…";

// 점검 시각 = 2026-11-19 09:04 KST(목) · 적용 요청 때 읽은 시각 = 2026-11-19 10:30 KST(목)
const CHECKED = "2026-11-19T00:04:57.202350+00:00";
const APPLY_READ = "2026-11-19T01:30:05+00:00";
const CRON: OciJobStatus = {
  job: "crontab",
  status: "SUCCESS",
  detail: "필수 스케줄(시장·보유·급등락) 모두 등록됨",
};
const ROW_OK: OciJobStatus = {
  job: "param_active",
  status: "SUCCESS",
  detail: "지금 PC 기준과 OCI 활성값이 같음 (14/14) · 기동 때 확인 11/19 09:04",
};
const ROW_STALE: OciJobStatus = {
  job: "param_active",
  status: "STALE",
  detail: "OCI 는 다른 값으로 동작 중 (14개 중 2개 다름 · 실행 정책 2) · 기동 때 확인 11/19 09:04",
};
const ROW_UNKNOWN: OciJobStatus = {
  job: "param_active",
  status: "UNKNOWN",
  detail: "OCI 활성값을 읽지 못함",
};

function oci(
  jobs: OciJobStatus[],
  extra: Partial<OciStartupStatus> = {},
): OciStartupStatus {
  return {
    checked_at: CHECKED,
    reachable: true,
    overall: "OPERATING",
    summary_line: "OCI 자동 운영 스케줄 활성 (필수 3종 등록 · 기동 시 확인)",
    crontab_active: true,
    jobs,
    note: "",
    param_read_at: CHECKED,
    param_source: "startup",
    ...extra,
  };
}
const MATCHED = oci([CRON, ROW_OK]);
const DIFFERENT = oci([CRON, ROW_STALE]);
// 점검 실패(접속 실패): 표가 비고 운영 기준 활성 행도 빠진다 · 두 새 칸은 null.
const CHECK_FAILED: OciStartupStatus = {
  checked_at: CHECKED,
  reachable: false,
  overall: "UNKNOWN",
  summary_line: "OCI 상태 미확인 (접속 실패)",
  crontab_active: null,
  jobs: [],
  note: "",
  param_read_at: null,
  param_source: null,
};
// 옛 서버: 두 새 칸 자체가 없다.
const { param_read_at: _a, param_source: _b, ...OLD_SERVER } = MATCHED;
void _a;
void _b;

function setOci(...values: Array<OciStartupStatus | Error>) {
  const m = vi.mocked(fetchOciStartupStatus);
  for (const v of values) {
    if (v instanceof Error) m.mockRejectedValueOnce(v);
    else m.mockResolvedValueOnce(v);
  }
}

async function renderWith(
  state: Partial<ThreePushParamState> = {},
  ociValue: OciStartupStatus | Error = MATCHED,
) {
  vi.mocked(fetchThreePushParamState).mockResolvedValue({ ...APPLIED, ...state });
  setOci(ociValue);
  const r = render(<ThreePushParamCard />);
  await screen.findByText(state.display_label ?? APPLIED.display_label);
  await waitFor(() => expect(headBadge(r.container)?.textContent).not.toBe(CHECKING));
  return r;
}

function applyButton(): HTMLElement {
  return screen.getByRole("button", { name: "현재 기준 OCI 적용" });
}

// R1-F2 — 이번 시도 시각은 버튼 누른 때의 한국 시각이다. 날짜만 고정한다(setTimeout 은 진짜 그대로).
// 2026-11-19T01:45:30Z = 한국 2026-11-19 10:45 · 02:05Z = 11:05 · 전날 15:30Z = 한국 다음 날 00:30.
const PRESS_1 = "2026-11-19T01:45:30Z";
const PRESS_2 = "2026-11-19T02:05:00Z";
const LOST_1 = "2026-11-19 10:45 · 결과 확인 불가(응답을 받지 못함)";
const LOST_2 = "2026-11-19 11:05 · 결과 확인 불가(응답을 받지 못함)";
// RESULT 판정 C3 — 결과를 확인할 수 없는 이번 시도의 줄 이름 · 그 아래 서버 기록 줄 이름 · 옛 이름.
const ATTEMPT = "최근 적용 시도";
const SERVER_PREV = "이전에 확인한 서버 요청 기록";
const OLD_PREV = "이전 요청 기록";
function dtLabels(container: HTMLElement): Array<string | null> {
  return Array.from(container.querySelectorAll("dt")).map((d) => d.textContent);
}
function fixNow(iso: string) {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(iso));
}

beforeEach(() => {
  vi.mocked(fetchOciStartupStatus).mockReset();
  vi.mocked(fetchThreePushParamState).mockReset();
  vi.mocked(applyThreePushParamToOci).mockReset();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
});

// ── 머리 배지: 지금 적용할 일 ─────────────────────────────────────────────────
describe("ThreePushParamCard — 머리 배지 · OCI 활성값 마지막 확인 (POC6-34 Q4)", () => {
  const TABLE = [
    ["일치 + 시각(점검 때)", MATCHED, NONE, "ok", "11/19(목) 09:04 · 마지막 OCI 점검 때 읽음"],
    [
      "일치 + 시각(적용 요청 때)",
      oci([CRON, ROW_OK], { param_read_at: APPLY_READ, param_source: "apply" }),
      NONE,
      "ok",
      "11/19(목) 10:30 · 적용 요청 때 읽음",
    ],
    ["다름 + 시각", DIFFERENT, CHANGES, "warn", "11/19(목) 09:04 · 마지막 OCI 점검 때 읽음"],
    [
      "다름 + 시각(적용 요청 때)",
      oci([CRON, ROW_STALE], { param_read_at: APPLY_READ, param_source: "apply" }),
      CHANGES,
      "warn",
      "11/19(목) 10:30 · 적용 요청 때 읽음",
    ],
    ["일치 · 시각 없음", oci([CRON, ROW_OK], { param_read_at: null, param_source: null }), UNKNOWN, "unknown", "확인 불가"],
    ["다름 · 시각 없음", oci([CRON, ROW_STALE], { param_read_at: null, param_source: null }), UNKNOWN, "unknown", "확인 불가"],
    ["확인 불가 행 + 시각", oci([CRON, ROW_UNKNOWN]), UNKNOWN, "unknown", "11/19(목) 09:04 · 마지막 OCI 점검 때 읽음"],
    ["모르는 상태 낱말", oci([CRON, { ...ROW_OK, status: "OK" }]), UNKNOWN, "unknown", "11/19(목) 09:04 · 마지막 OCI 점검 때 읽음"],
    ["운영 기준 활성 행 없음", oci([CRON]), UNKNOWN, "unknown", "11/19(목) 09:04 · 마지막 OCI 점검 때 읽음"],
    ["점검 실패(행 없음 · 시각 없음)", CHECK_FAILED, UNKNOWN, "unknown", "확인 불가"],
    ["옛 서버(새 칸 없음)", OLD_SERVER as OciStartupStatus, UNKNOWN, "unknown", "확인 불가"],
    ["시각 칸이 읽히지 않는 글", oci([CRON, ROW_OK], { param_read_at: "11/19 09:04" }), UNKNOWN, "unknown", "확인 불가"],
    ["운영 기준 활성 행이 둘", oci([CRON, ROW_OK, ROW_STALE]), UNKNOWN, "unknown", "11/19(목) 09:04 · 마지막 OCI 점검 때 읽음"],
    ["조회 실패", new ApiRequestError("네트워크 호출 실패", 0, null), UNKNOWN, "unknown", "확인 불가"],
  ] as const;

  it.each(TABLE)("%s → 머리 배지 · 확인 줄", async (_name, value, text, tone, readLine) => {
    const { container } = await renderWith({}, value as OciStartupStatus | Error);
    const badge = headBadge(container);
    expect(badge?.textContent).toBe(text);
    expect(badge?.className).toBe(`oci-state ${tone}`);
    expect(rowValue(container, "OCI 활성값 마지막 확인")).toBe(readLine);
    // 차이 건수는 머리에 쓰지 않는다(구조 필드 없음).
    expect(badge?.textContent).not.toMatch(/\d/);
    // 화면을 그리는 것만으로는 적용 요청을 보내지 않는다.
    expect(applyThreePushParamToOci).not.toHaveBeenCalled();
  });

  it("응답 전에는 '확인 중' — 판정하지 않는다", async () => {
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(fetchOciStartupStatus).mockReturnValue(new Promise(() => undefined));
    const { container } = render(<ThreePushParamCard />);
    await screen.findByText(APPLIED.display_label);
    expect(headBadge(container)?.textContent).toBe(CHECKING);
    expect(headBadge(container)?.className).toBe("oci-state unknown");
    expect(rowValue(container, "OCI 활성값 마지막 확인")).toBe("확인 중…");
    // 응답 전 버튼은 지금 자리(접힘 밖)
    expect(applyButton().closest("details")).toBeNull();
  });

  it("상태 기록 조회가 실패해도 머리 배지 · 확인 줄은 OCI 응답대로 보인다", async () => {
    vi.mocked(fetchThreePushParamState).mockRejectedValue(
      new ApiRequestError("네트워크 호출 실패", 0, null),
    );
    setOci(DIFFERENT);
    const { container } = render(<ThreePushParamCard />);
    await screen.findByText("요청 실패 (HTTP 0)");
    await waitFor(() => expect(headBadge(container)?.textContent).toBe(CHANGES));
    expect(rowValue(container, "OCI 활성값 마지막 확인")).toBe(
      "11/19(목) 09:04 · 마지막 OCI 점검 때 읽음",
    );
    expect(rowValue(container, "마지막 적용 요청")).toBeNull();
  });

  it("GET /oci/startup-status 는 마운트 때 1번만 부른다", async () => {
    await renderWith();
    expect(fetchOciStartupStatus).toHaveBeenCalledTimes(1);
  });
});

// PLAN I-8 — 부모(「OCI 운영·적용」)가 ① 이 받은 같은 응답을 넘기면 카드는 따로 부르지 않는다.
describe("ThreePushParamCard — ① 의 같은 응답 쓰기 (POC6-34 I-8)", () => {
  function Parent({ first, afterApply }: { first: OciStatusInput; afterApply: OciStatusInput }) {
    const [s, setS] = useState<OciStatusInput>(first);
    return <ThreePushParamCard ociStatus={s} onDelivered={() => setS(afterApply)} />;
  }

  it("넘긴 값만 따른다 · GET /oci/startup-status 0번 · 응답 전(undefined) = 확인 중", async () => {
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    const { container, rerender } = render(<ThreePushParamCard ociStatus={undefined} />);
    await screen.findByText(APPLIED.display_label);
    expect(headBadge(container)?.textContent).toBe(CHECKING);
    rerender(<ThreePushParamCard ociStatus={MATCHED} />);
    expect(headBadge(container)?.textContent).toBe(NONE);
    expect(applyButton().closest("details")).not.toBeNull();
    rerender(<ThreePushParamCard ociStatus={DIFFERENT} />);
    expect(headBadge(container)?.textContent).toBe(CHANGES);
    expect(applyButton().closest("details")).toBeNull();
    rerender(<ThreePushParamCard ociStatus={null} />);
    expect(headBadge(container)?.textContent).toBe(UNKNOWN);
    expect(rowValue(container, "OCI 활성값 마지막 확인")).toBe("확인 불가");
    expect(fetchOciStartupStatus).not.toHaveBeenCalled();
  });

  it("적용이 끝나면 따로 부르지 않고 onDelivered 로 부모가 다시 읽은 값을 따른다", async () => {
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci).mockResolvedValue({ ...APPLIED, status: "activated" });
    const after = oci([CRON, ROW_OK], { param_read_at: APPLY_READ, param_source: "apply" });
    const { container } = render(<Parent first={DIFFERENT} afterApply={after} />);
    await screen.findByText(APPLIED.display_label);
    expect(headBadge(container)?.textContent).toBe(CHANGES);
    fireEvent.click(applyButton());
    await waitFor(() => expect(headBadge(container)?.textContent).toBe(NONE));
    expect(rowValue(container, "OCI 활성값 마지막 확인")).toBe("11/19(목) 10:30 · 적용 요청 때 읽음");
    expect(fetchOciStartupStatus).not.toHaveBeenCalled();
    expect(applyThreePushParamToOci).toHaveBeenCalledTimes(1);
  });

  it("칸을 넘기지 않으면 카드가 직접 부른다(대조군)", async () => {
    await renderWith({}, DIFFERENT);
    expect(fetchOciStartupStatus).toHaveBeenCalledTimes(1);
  });
});

describe("paramVerdict — 순수 판정", () => {
  it.each([
    ["응답 전", undefined, "checking"],
    ["조회 실패", null, "unknown"],
    ["일치 + 시각", MATCHED, "none"],
    ["다름 + 시각", DIFFERENT, "changes"],
    ["일치 · 시각 null", oci([ROW_OK], { param_read_at: null }), "unknown"],
    ["일치 · 시각 빈 글", oci([ROW_OK], { param_read_at: "" }), "unknown"],
    ["일치 · 시각이 숫자", oci([ROW_OK], { param_read_at: 1700000000000 as unknown as string }), "unknown"],
    ["일치 · 시간대 없는 시각", oci([ROW_OK], { param_read_at: "2026-11-19T00:04:57" }), "unknown"],
    ["일치 · 날짜가 아닌 시각", oci([ROW_OK], { param_read_at: "2026-13-45T99:99:99+00:00" }), "unknown"],
    ["시각 Z 꼴", oci([ROW_OK], { param_read_at: "2026-11-19T00:04:57Z" }), "none"],
    ["출처 모름이어도 상태 · 시각으로 판정", oci([ROW_OK], { param_source: null }), "none"],
    ["jobs 가 배열 아님", { ...MATCHED, jobs: null } as unknown as OciStartupStatus, "unknown"],
    ["jobs 안 빈 칸", oci([null as unknown as OciJobStatus, ROW_STALE]), "changes"],
    ["응답이 객체 아님", "OPERATING" as unknown as OciStartupStatus, "unknown"],
  ] as const)("%s → %s", (_name, value, expected) => {
    expect(paramVerdict(value)).toBe(expected);
  });
});

// ── 버튼 자리 ─────────────────────────────────────────────────────────────────
describe("ThreePushParamCard — 버튼 자리 (POC6-34 O7 · I-12)", () => {
  it("일치 + 시각: 버튼은 [자세히 보기 (필요할 때 다시 적용)] 안 · 기본 닫힘 · 안내 문장", async () => {
    await renderWith({}, MATCHED);
    const details = applyButton().closest("details");
    expect(details).not.toBeNull();
    expect(details?.open).toBe(false);
    expect(details?.querySelector("summary")?.textContent).toBe("자세히 보기 (필요할 때 다시 적용)");
    expect(details?.textContent).toContain(DETAILS_NOTE);
    expect(applyThreePushParamToOci).not.toHaveBeenCalled();
  });

  it.each([
    ["다름", DIFFERENT],
    ["확인 불가 행", oci([CRON, ROW_UNKNOWN])],
    ["행 없음", oci([CRON])],
    ["시각 없음", oci([CRON, ROW_OK], { param_read_at: null, param_source: null })],
    ["점검 실패", CHECK_FAILED],
    ["조회 실패", new Error("down")],
  ] as const)("%s: 버튼은 지금 자리(접힘 밖) · 접힘 없음", async (_name, value) => {
    const { container } = await renderWith({}, value as OciStartupStatus | Error);
    expect(applyButton().closest("details")).toBeNull();
    expect(container.querySelector("details")).toBeNull();
    expect(screen.queryByText(DETAILS_NOTE)).toBeNull();
  });

  it("버튼은 어느 자리든 하나 · 문구 '현재 기준 OCI 적용' · 눌러야만 적용 요청", async () => {
    for (const value of [MATCHED, DIFFERENT]) {
      await renderWith({}, value);
      const buttons = screen.getAllByRole("button");
      expect(buttons).toHaveLength(1);
      expect(buttons[0].textContent).toBe("현재 기준 OCI 적용");
      cleanup();
    }
    expect(applyThreePushParamToOci).not.toHaveBeenCalled();
  });
});

// ── 마지막 적용 요청 · 요청 결과 ─────────────────────────────────────────────
describe("ThreePushParamCard — 마지막 적용 요청 · 요청 결과 (POC6-34 O6 · I-11)", () => {
  it("네 행: 적용 기준 · OCI 활성값 마지막 확인 · 마지막 적용 요청 · 요청 결과 (옛 이름 없음)", async () => {
    const { container } = await renderWith();
    const labels = Array.from(container.querySelectorAll("dt")).map((d) => d.textContent);
    expect(labels).toEqual(["적용 기준", "OCI 활성값 마지막 확인", "마지막 적용 요청", "요청 결과"]);
    expect(rowValue(container, "적용 기준")).toBe("기본 운영 기준");
    expect(rowValue(container, "마지막 적용 요청")).toBe("2026-10-20 13:14 · 결과 이미 일치");
    expect(rowValue(container, "요청 결과")).toBe(APPLIED.message);
    expect(container.textContent).not.toContain("일치 · 변경 없음");
  });

  it.each([
    ["active_same", "2026-10-20 13:14", "2026-10-20 13:14 · 결과 이미 일치"],
    ["activated", "2026-10-20 13:14", "2026-10-20 13:14 · 결과 적용 완료"],
    ["failed", "2026-10-20 13:14", "2026-10-20 13:14 · 결과 적용 실패"],
    ["unconfirmed", "2026-10-20 13:14", "2026-10-20 13:14 · 결과 확인 불가"],
    ["busy", null, "— · 결과 적용 중"],
    ["verification_required", null, "— · 결과 확인 필요"],
    ["delivered_only", "2026-10-04 11:09", "2026-10-04 11:09 · 결과 이전 전달 기록"],
    ["not_applied", null, "요청 기록 없음"],
  ] as const)("결과 낱말: %s → '%s' 시각 · '%s'", async (status, appliedAt, text) => {
    const { container } = await renderWith({ status, applied_at: appliedAt });
    expect(rowValue(container, "마지막 적용 요청")).toBe(text);
    // 머리 배지는 요청 결과가 아니라 지금 적용할 일이다(OCI 응답 = 일치 + 시각).
    expect(headBadge(container)?.textContent).toBe(NONE);
  });

  it("모르는 결과 값은 '미적용'", async () => {
    const { container } = await renderWith({
      status: "something_new" as ThreePushParamState["status"],
    });
    expect(rowValue(container, "마지막 적용 요청")).toBe("2026-10-20 13:14 · 결과 미적용");
  });

  it("예전 전달 기록은 '미적용'으로 단정하지 않는다(판정 §5) · 서버 문구는 '요청 결과' 그대로", async () => {
    const msg =
      "이전 전달 기록(2026-10-04 11:09) · 활성화 확인 없음. 지금 OCI 활성값과의 일치 여부는 위 ① '운영 기준 활성' 행에서 확인하세요.";
    const { container } = await renderWith({
      status: "delivered_only",
      applied_at: "2026-10-04 11:09",
      oci_verified: false,
      message: msg,
    });
    expect(rowValue(container, "요청 결과")).toBe(msg);
    expect(container.textContent).not.toContain("미적용");
  });

  // PLAN 판정 Q4 대조 사례 — 두 날짜는 각자의 줄에 붙는다.
  it("Q4 사례 1: 11/19 09:04 점검 일치 + 10/20 13:14 요청 '이미 일치' → 적용할 변경 없음", async () => {
    const { container } = await renderWith({}, MATCHED);
    expect(headBadge(container)?.textContent).toBe(NONE);
    expect(rowValue(container, "OCI 활성값 마지막 확인")).toBe(
      "11/19(목) 09:04 · 마지막 OCI 점검 때 읽음",
    );
    expect(rowValue(container, "마지막 적용 요청")).toBe("2026-10-20 13:14 · 결과 이미 일치");
    expect(applyButton().closest("details")).not.toBeNull();
  });

  it("Q4 사례 2: 점검 실패 + 10/20 요청 '이미 일치' → 확인 불가 · 지난 '이미 일치'는 요청 기록에서만", async () => {
    const { container } = await renderWith({}, CHECK_FAILED);
    expect(headBadge(container)?.textContent).toBe(UNKNOWN);
    expect(rowValue(container, "OCI 활성값 마지막 확인")).toBe("확인 불가");
    expect(rowValue(container, "마지막 적용 요청")).toBe("2026-10-20 13:14 · 결과 이미 일치");
    // '이미 일치'는 요청 기록 줄에만 있다(머리 · 확인 줄에 없음).
    expect(headBadge(container)?.textContent).not.toContain("일치");
    expect(applyButton().closest("details")).toBeNull();
  });

  it("요청 기록만 있음(OCI 응답 전) → 확인 중 · 요청 기록 줄은 그대로", async () => {
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(fetchOciStartupStatus).mockReturnValue(new Promise(() => undefined));
    const { container } = render(<ThreePushParamCard />);
    await screen.findByText(APPLIED.display_label);
    expect(headBadge(container)?.textContent).toBe(CHECKING);
    expect(rowValue(container, "마지막 적용 요청")).toBe("2026-10-20 13:14 · 결과 이미 일치");
  });
});

// ── 적용 흐름(기존 계약 그대로) ──────────────────────────────────────────────
describe("ThreePushParamCard — 적용 흐름 (POC5-27 계약 그대로)", () => {
  it("안내 1줄은 늘 보인다(이후 실행에서 읽는 기준 · 차이는 ① 행)", async () => {
    await renderWith();
    expect(screen.getByText(NOTE)).toBeTruthy();
    cleanup();
    await renderWith({ status: "failed" });
    expect(screen.getByText(NOTE)).toBeTruthy();
  });

  it("실패 · 확인 불가는 각자 안내 1줄(기존 값 그대로 / 자동으로 되돌리거나 다시 적용 안 함)", async () => {
    await renderWith({ status: "failed" });
    expect(screen.getByText(/OCI 활성값은 바뀌지 않았습니다/)).toBeTruthy();
    expect(screen.queryByText(/자동으로 되돌리거나/)).toBeNull();
    cleanup();
    await renderWith({ status: "unconfirmed" });
    expect(screen.getByText(/자동으로 되돌리거나 다시 적용하지 않습니다/)).toBeTruthy();
    expect(screen.queryByText(/OCI 활성값은 바뀌지 않았습니다/)).toBeNull();
  });

  it("일치 상태에서도 [자세히 보기] 안 버튼으로 적용할 수 있다 · 끝나면 onDelivered 1번 · OCI 상태 다시 읽기", async () => {
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci).mockResolvedValue({ ...APPLIED });
    setOci(MATCHED, oci([CRON, ROW_OK], { param_read_at: APPLY_READ, param_source: "apply" }));
    const onDelivered = vi.fn();
    const { container } = render(<ThreePushParamCard onDelivered={onDelivered} />);
    await waitFor(() => expect(headBadge(container)?.textContent).toBe(NONE));
    fireEvent.click(applyButton());
    await waitFor(() => expect(onDelivered).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(rowValue(container, "OCI 활성값 마지막 확인")).toBe(
        "11/19(목) 10:30 · 적용 요청 때 읽음",
      ),
    );
    expect(fetchOciStartupStatus).toHaveBeenCalledTimes(2);
    expect(applyThreePushParamToOci).toHaveBeenCalledTimes(1);
  });

  it("적용 뒤 다시 읽은 응답이 판정을 바꾼다(다름 → 일치 · 버튼은 접힘 안으로)", async () => {
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci).mockResolvedValue({
      ...APPLIED,
      status: "activated",
      message: "OCI 활성값을 지금 기준으로 바꾸고 다시 읽어 같음을 확인했습니다 (14/14). 다음 실행부터 이 기준을 씁니다.",
    });
    setOci(DIFFERENT, oci([CRON, ROW_OK], { param_read_at: APPLY_READ, param_source: "apply" }));
    const { container } = render(<ThreePushParamCard />);
    await waitFor(() => expect(headBadge(container)?.textContent).toBe(CHANGES));
    expect(applyButton().closest("details")).toBeNull();
    fireEvent.click(applyButton());
    await waitFor(() => expect(headBadge(container)?.textContent).toBe(NONE));
    expect(rowValue(container, "마지막 적용 요청")).toBe("2026-10-20 13:14 · 결과 적용 완료");
    expect(applyButton().closest("details")).not.toBeNull();
  });

  it("적용 뒤 다시 읽기가 실패하면 앞선 '변경 없음'을 남기지 않고 '확인 불가'", async () => {
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci).mockResolvedValue({ ...APPLIED });
    setOci(MATCHED, new ApiRequestError("요청 실패", 502, null));
    const { container } = render(<ThreePushParamCard />);
    await waitFor(() => expect(headBadge(container)?.textContent).toBe(NONE));
    fireEvent.click(applyButton());
    await waitFor(() => expect(headBadge(container)?.textContent).toBe(UNKNOWN));
    expect(rowValue(container, "OCI 활성값 마지막 확인")).toBe("확인 불가");
    expect(applyButton().closest("details")).toBeNull();
  });

  it("적용 뒤 다시 읽는 동안은 '확인 중'(적용 전 판정을 보이지 않음)", async () => {
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci).mockResolvedValue({ ...APPLIED });
    setOci(MATCHED);
    vi.mocked(fetchOciStartupStatus).mockReturnValueOnce(new Promise(() => undefined));
    const { container } = render(<ThreePushParamCard />);
    await waitFor(() => expect(headBadge(container)?.textContent).toBe(NONE));
    fireEvent.click(applyButton());
    await waitFor(() => expect(fetchOciStartupStatus).toHaveBeenCalledTimes(2));
    expect(headBadge(container)?.textContent).toBe(CHECKING);
    expect(rowValue(container, "OCI 활성값 마지막 확인")).toBe("확인 중…");
  });

  it("늦게 온 첫 응답(적용 전)이 적용 뒤 응답을 덮지 않는다", async () => {
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci).mockResolvedValue({ ...APPLIED });
    let resolveFirst: (v: OciStartupStatus) => void = () => undefined;
    vi.mocked(fetchOciStartupStatus)
      .mockReturnValueOnce(
        new Promise<OciStartupStatus>((r) => {
          resolveFirst = r;
        }),
      )
      .mockResolvedValueOnce(oci([CRON, ROW_OK], { param_read_at: APPLY_READ, param_source: "apply" }));
    const { container } = render(<ThreePushParamCard />);
    await screen.findByText(APPLIED.display_label);
    fireEvent.click(applyButton());
    await waitFor(() => expect(headBadge(container)?.textContent).toBe(NONE));
    await act(async () => {
      resolveFirst(DIFFERENT);
      await Promise.resolve();
    });
    expect(headBadge(container)?.textContent).toBe(NONE);
    expect(rowValue(container, "OCI 활성값 마지막 확인")).toBe("11/19(목) 10:30 · 적용 요청 때 읽음");
  });

  it("적용 실패 응답: 결과 '적용 실패' · 실패 안내 · OCI 상태 다시 읽기", async () => {
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci).mockResolvedValue({
      ...APPLIED,
      status: "failed",
      applied_at: "2026-11-19 10:31",
      oci_verified: false,
      message: "OCI 에 적용하지 못했습니다 (OCI 활성값을 먼저 읽지 못함). 기존 OCI 활성값이 그대로입니다.",
    });
    setOci(DIFFERENT, DIFFERENT);
    const { container } = render(<ThreePushParamCard />);
    await waitFor(() => expect(headBadge(container)?.textContent).toBe(CHANGES));
    fireEvent.click(applyButton());
    await waitFor(() =>
      expect(rowValue(container, "마지막 적용 요청")).toBe("2026-11-19 10:31 · 결과 적용 실패"),
    );
    expect(screen.getByText(/OCI 활성값은 바뀌지 않았습니다/)).toBeInTheDocument();
    await waitFor(() => expect(fetchOciStartupStatus).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(headBadge(container)?.textContent).toBe(CHANGES));
  });

  it("응답이 빨리 와도 끝난 뒤 '진행 중' 문구가 다시 나타나지 않는다(남은 타이머 정리)", async () => {
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci).mockResolvedValue({
      ...APPLIED,
      status: "busy",
      message: "이미 적용이 진행 중입니다. 끝난 뒤 이 화면을 다시 열어 결과를 확인하세요.",
    });
    setOci(DIFFERENT, DIFFERENT);
    const { container } = render(<ThreePushParamCard />);
    await waitFor(() => expect(headBadge(container)?.textContent).toBe(CHANGES));
    fireEvent.click(applyButton());
    await screen.findByRole("button", { name: "현재 기준 OCI 적용" });
    await new Promise((r) => setTimeout(r, 1300)); // 400ms · 1200ms 타이머가 지난 뒤
    expect(screen.queryByText(/진행 중:/)).toBeNull();
  });

  // 검증자 F1 — 적용 요청의 응답을 받지 못하면 이번 결과는 '확인 불가'. 지난 성공 기록(GET)으로
  // 다시 읽어 덮지 않고, 이번 오류 안내도 남는다(설계 §4 · 응답 단절 = 결과 미확인).
  // POC6-34 r1(R1-F2) · C3: 이번 시도는 '최근 적용 시도' 줄에 이번 시각으로, 지난 기록은 '이전에 확인한
  // 서버 요청 기록' 줄에 제 시각 · 제 결과로.
  it.each([
    ["activated", "적용 완료", new ApiRequestError("요청 시간 초과", 0, null), "요청 실패 (HTTP 0)", LOST_1],
    ["active_same", "이미 일치", new ApiRequestError("네트워크 호출 실패", 0, null), "요청 실패 (HTTP 0)", LOST_1],
    // r1 검증 V-1 — 서버가 오류로 응답했으면 '응답을 받지 못함'이 아니라 '서버가 오류로 응답 · HTTP n'.
    [
      "activated",
      "적용 완료",
      new ApiRequestError("요청 실패", 502, null),
      "요청 실패 (HTTP 502)",
      "2026-11-19 10:45 · 결과 확인 불가(서버가 오류로 응답 · HTTP 502)",
    ],
    ["active_same", "이미 일치", new Error("body"), "알 수 없는 오류가 발생했습니다.", LOST_1],
  ] as const)(
    "응답 단절: 이전 %s('%s') 뒤에도 이번 결과는 '확인 불가' · 오류 안내 유지",
    async (prevStatus, prevWord, err, errText, lostLine) => {
      fixNow(PRESS_1);
      vi.mocked(fetchThreePushParamState).mockResolvedValue({
        ...APPLIED,
        status: prevStatus,
      });
      vi.mocked(applyThreePushParamToOci).mockRejectedValue(err);
      setOci(DIFFERENT, DIFFERENT);
      const onDelivered = vi.fn();
      const { container } = render(<ThreePushParamCard onDelivered={onDelivered} />);
      await waitFor(() =>
        expect(rowValue(container, "마지막 적용 요청")).toBe(`2026-10-20 13:14 · 결과 ${prevWord}`),
      );
      expect(rowValue(container, SERVER_PREV)).toBeNull();
      expect(rowValue(container, ATTEMPT)).toBeNull();
      await waitFor(() => expect(headBadge(container)?.textContent).toBe(CHANGES));
      fireEvent.click(applyButton());
      await waitFor(() => expect(rowValue(container, ATTEMPT)).toBe(lostLine));
      expect(rowValue(container, "마지막 적용 요청")).toBeNull();
      expect(rowValue(container, SERVER_PREV)).toBe(`2026-10-20 13:14 · 결과 ${prevWord}`);
      expect(container.textContent).not.toContain("2026-10-20 13:14 · 결과 확인 불가");
      expect(rowValue(container, "요청 결과")).toBe(
        "적용 결과를 확인하지 못했습니다. OCI 활성값이 바뀌었는지 알 수 없습니다.",
      );
      expect(screen.getByText(errText)).toBeInTheDocument();
      expect(screen.getByText(/자동으로 되돌리거나 다시 적용하지 않습니다/)).toBeInTheDocument();
      // 지난 기록을 다시 읽어 덮지 않는다(처음 1회만) · ① 은 다시 읽게 한다.
      expect(fetchThreePushParamState).toHaveBeenCalledTimes(1);
      await waitFor(() => expect(onDelivered).toHaveBeenCalledTimes(1));
    },
  );

  // r3(검증자 F1-NULL) — 이전 상태의 모든 종류(첫 상태 조회 실패로 '없음' 포함) × 응답을 못 받은
  // 오류 종류. 어느 조합이든 이번 결과는 '확인 불가' + 안내 + 이번 오류 줄이다(설계 §4).
  // POC6-34 r1(R1-F2) · C3: '최근 적용 시도' = 이번 시도 시각 · '결과 확인 불가(응답을 받지 못함)'.
  // '이전에 확인한 서버 요청 기록' = 이전 서버 기록에 요청 기록(not_applied 아님)과 시각이 있을 때만
  // 제 시각 · 제 결과.
  // [이름, 이전 상태, 이전 시각, 누르기 전 '마지막 적용 요청', 누른 뒤 '이전에 확인한 서버 요청 기록']
  const PRIORS = [
    ["없음(첫 조회 실패)", null, null, null, null],
    ["not_applied", "not_applied", null, "요청 기록 없음", null],
    ["not_applied · 시각 남음", "not_applied", "2026-10-20 13:14", "요청 기록 없음", null],
    [
      "delivered_only",
      "delivered_only",
      "2026-10-04 11:09",
      "2026-10-04 11:09 · 결과 이전 전달 기록",
      "2026-10-04 11:09 · 결과 이전 전달 기록",
    ],
    ["active_same", "active_same", "2026-10-20 13:14", "2026-10-20 13:14 · 결과 이미 일치", "2026-10-20 13:14 · 결과 이미 일치"],
    ["activated", "activated", "2026-10-20 13:14", "2026-10-20 13:14 · 결과 적용 완료", "2026-10-20 13:14 · 결과 적용 완료"],
    ["failed", "failed", "2026-10-20 13:14", "2026-10-20 13:14 · 결과 적용 실패", "2026-10-20 13:14 · 결과 적용 실패"],
    // 서버가 저장한 '확인 불가' 기록은 제 시각에 붙은 제 결과다(이번 시도와 섞지 않음).
    ["unconfirmed", "unconfirmed", "2026-10-20 13:14", "2026-10-20 13:14 · 결과 확인 불가", "2026-10-20 13:14 · 결과 확인 불가"],
    ["busy", "busy", "2026-10-20 13:14", "2026-10-20 13:14 · 결과 적용 중", "2026-10-20 13:14 · 결과 적용 중"],
    ["busy · 시각 없음", "busy", null, "— · 결과 적용 중", null],
    [
      "verification_required",
      "verification_required",
      "2026-10-20 13:14",
      "2026-10-20 13:14 · 결과 확인 필요",
      "2026-10-20 13:14 · 결과 확인 필요",
    ],
    ["verification_required · 시각 없음", "verification_required", null, "— · 결과 확인 필요", null],
  ] as const;
  const LOST = [
    ["HTTP 0", () => new ApiRequestError("요청 시간 초과", 0, null), "요청 실패 (HTTP 0)"],
    ["본문 오류", () => new Error("body"), "알 수 없는 오류가 발생했습니다."],
  ] as const;
  const TABLE = PRIORS.flatMap((p) => LOST.map((l) => [...p, ...l] as const));

  it.each(TABLE)(
    "응답 단절 조합: 이전 %s × %s → '확인 불가'",
    async (_name, prevStatus, prevAt, prevLine, prevRecord, _lost, makeErr, errText) => {
      fixNow(PRESS_1);
      if (prevStatus === null) {
        vi.mocked(fetchThreePushParamState).mockRejectedValue(
          new ApiRequestError("네트워크 호출 실패", 0, null),
        );
      } else {
        vi.mocked(fetchThreePushParamState).mockResolvedValue({
          ...APPLIED,
          status: prevStatus,
          applied_at: prevAt,
        });
      }
      vi.mocked(applyThreePushParamToOci).mockRejectedValue(makeErr());
      setOci(DIFFERENT, DIFFERENT);
      const { container } = render(<ThreePushParamCard />);
      if (prevLine === null) {
        await screen.findByText("요청 실패 (HTTP 0)");
        expect(rowValue(container, "마지막 적용 요청")).toBeNull();
      } else {
        await waitFor(() => expect(rowValue(container, "마지막 적용 요청")).toBe(prevLine));
      }
      await waitFor(() => expect(headBadge(container)?.textContent).toBe(CHANGES));
      fireEvent.click(applyButton());
      await waitFor(() => expect(applyThreePushParamToOci).toHaveBeenCalledTimes(1));
      await screen.findByRole("button", { name: "현재 기준 OCI 적용" });
      await waitFor(() =>
        expect(rowValue(container, "요청 결과")).toBe(
          "적용 결과를 확인하지 못했습니다. OCI 활성값이 바뀌었는지 알 수 없습니다.",
        ),
      );
      expect(screen.getByText(/자동으로 되돌리거나 다시 적용하지 않습니다/)).toBeInTheDocument();
      // 이전 기록이 '적용 실패'여도 이번 시도는 결과를 모른다 — 실패 안내('바뀌지 않았습니다')를 보이지 않는다.
      expect(screen.queryByText(/OCI 활성값은 바뀌지 않았습니다/)).toBeNull();
      expect(screen.getByText(errText)).toBeInTheDocument();
      // 적용 기준은 모르면 카드의 기존 빈 값 표기 '—'.
      expect(rowValue(container, "적용 기준")).toBe(
        prevStatus === null ? "—" : APPLIED.display_label,
      );
      // 이번 시도는 이번 시각 · 이번 결과 — 이전 시각을 다시 쓰지 않는다.
      expect(rowValue(container, ATTEMPT)).toBe(LOST_1);
      if (prevAt !== null) {
        expect(rowValue(container, ATTEMPT)).not.toContain(prevAt);
      }
      expect(rowValue(container, SERVER_PREV)).toBe(prevRecord);
      // 줄 순서(C3): 이번 시도 줄 바로 아래 서버 기록 줄(있을 때만), 그다음 요청 결과.
      expect(dtLabels(container)).toEqual([
        "적용 기준",
        "OCI 활성값 마지막 확인",
        ATTEMPT,
        ...(prevRecord === null ? [] : [SERVER_PREV]),
        "요청 결과",
      ]);
      expect(fetchThreePushParamState).toHaveBeenCalledTimes(1); // 지난 기록으로 다시 읽지 않는다
    },
  );

  it.each([
    ["없음(첫 조회 실패)", null],
    ["active_same", "2026-10-20 13:14 · 결과 이미 일치"],
  ] as const)(
    "구성 오류 조합: 이전 %s → 상태 그대로 · '확인 불가' 없음",
    async (_name, prevLine) => {
      if (prevLine === null) {
        vi.mocked(fetchThreePushParamState).mockRejectedValue(
          new ApiConfigError("NEXT_PUBLIC_API_BASE 없음"),
        );
      } else {
        vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
      }
      vi.mocked(applyThreePushParamToOci).mockRejectedValue(
        new ApiConfigError("NEXT_PUBLIC_API_BASE 없음"),
      );
      setOci(DIFFERENT, DIFFERENT);
      const { container } = render(<ThreePushParamCard />);
      if (prevLine === null) await screen.findByText("구성 오류: NEXT_PUBLIC_API_BASE 없음");
      else await waitFor(() => expect(rowValue(container, "마지막 적용 요청")).toBe(prevLine));
      await waitFor(() => expect(headBadge(container)?.textContent).toBe(CHANGES));
      fireEvent.click(applyButton());
      await waitFor(() => expect(applyThreePushParamToOci).toHaveBeenCalledTimes(1));
      await screen.findByRole("button", { name: "현재 기준 OCI 적용" });
      expect(screen.getByText("구성 오류: NEXT_PUBLIC_API_BASE 없음")).toBeInTheDocument();
      expect(rowValue(container, "마지막 적용 요청")).toBe(prevLine);
      expect(rowValue(container, SERVER_PREV)).toBeNull();
      expect(rowValue(container, ATTEMPT)).toBeNull();
      expect(container.textContent).not.toContain("결과 확인 불가");
    },
  );

  it("첫 조회 실패 뒤 적용 성공이면 그 결과를 보인다(대조군)", async () => {
    vi.mocked(fetchThreePushParamState).mockRejectedValue(
      new ApiRequestError("네트워크 호출 실패", 0, null),
    );
    vi.mocked(applyThreePushParamToOci).mockResolvedValue({
      ...APPLIED,
      status: "activated",
      message: "OCI 활성값을 지금 기준으로 바꾸고 다시 읽어 같음을 확인했습니다 (14/14). 다음 실행부터 이 기준을 씁니다.",
    });
    setOci(DIFFERENT, DIFFERENT);
    const { container } = render(<ThreePushParamCard />);
    await screen.findByText("요청 실패 (HTTP 0)");
    await waitFor(() => expect(headBadge(container)?.textContent).toBe(CHANGES));
    fireEvent.click(applyButton());
    await waitFor(() =>
      expect(rowValue(container, "마지막 적용 요청")).toBe("2026-10-20 13:14 · 결과 적용 완료"),
    );
    expect(rowValue(container, ATTEMPT)).toBeNull();
    expect(screen.queryByText("요청 실패 (HTTP 0)")).toBeNull();
    expect(container.textContent).not.toContain("결과 확인 불가");
  });

  it("적용 중에는 버튼이 막히고 문구가 바뀐다(두 번 누름 방지)", async () => {
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci).mockReturnValue(new Promise(() => undefined));
    setOci(DIFFERENT);
    const { container } = render(<ThreePushParamCard />);
    await waitFor(() => expect(headBadge(container)?.textContent).toBe(CHANGES));
    fireEvent.click(applyButton());
    const busy = await screen.findByRole("button", { name: "적용 진행 중..." });
    expect(busy).toHaveProperty("disabled", true);
    // 첫 단계는 OCI 실제 활성값 읽기(같으면 바꾸지 않는다) — 예전 '운영 기준 생성 중' 이 아니다.
    expect(screen.getByText("진행 중: OCI 활성값 읽는 중")).toBeInTheDocument();
    fireEvent.click(busy);
    expect(applyThreePushParamToOci).toHaveBeenCalledTimes(1);
  });
});

// ── POC6-34 r1(검증자 R1-F2) · RESULT 판정 C3: 결과를 확인할 수 없는 이번 시도와 서버 기록을 가른다 ──
// 이전 시각(10/20 13:14)에 이번 결과('확인 불가')를 붙이지 않는다. 이번 시도 = 버튼 누른 한국 시각.
// C3 줄 이름 · 자리: 이번 시도 = '최근 적용 시도' → 바로 아래 '이전에 확인한 서버 요청 기록'(마지막으로
// 확인된 서버 기록 · 없으면 줄 없음) → '요청 결과'. 정상 서버 기록 = '마지막 적용 요청'(서버 종료 시각).
describe("ThreePushParamCard — 최근 적용 시도와 이전에 확인한 서버 요청 기록 (POC6-34 r1 R1-F2 · C3)", () => {
  const UNCONFIRMED_TEXT = "적용 결과를 확인하지 못했습니다. OCI 활성값이 바뀌었는지 알 수 없습니다.";
  const PREV_RECORD = "2026-10-20 13:14 · 결과 이미 일치";
  const TIMEOUT = () => new ApiRequestError("요청 시간 초과", 0, null);
  const HTTP_502 = () => new ApiRequestError("요청 실패", 502, null);
  const NORMAL_LABELS = ["적용 기준", "OCI 활성값 마지막 확인", "마지막 적용 요청", "요청 결과"];
  const LOST_LABELS = ["적용 기준", "OCI 활성값 마지막 확인", ATTEMPT, SERVER_PREV, "요청 결과"];
  // 「OCI 운영·적용」 처럼 ① 응답을 넘기고 onDelivered 로 ① 을 다시 읽는 부모(검증자 재현 방식).
  function Parent({ first, afterApply }: { first: OciStatusInput; afterApply: OciStatusInput }) {
    const [s, setS] = useState<OciStatusInput>(first);
    return <ThreePushParamCard ociStatus={s} onDelivered={() => setS(afterApply)} />;
  }
  // 응답을 못 받은 적용 뒤 ① 다시 읽기: 서버는 확인 불가 때 읽은 시각을 싣지 않는다(I-7).
  const AFTER_LOST = oci([CRON, ROW_UNKNOWN], { param_read_at: null, param_source: null });

  it("사례: 이전 '10/20 13:14 · 이미 일치' + 시간 초과 → '최근 적용 시도' 이번 시각 · 확인 불가 / 바로 아래 서버 기록은 제 시각 · 제 결과", async () => {
    fixNow(PRESS_1);
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci).mockRejectedValue(TIMEOUT());
    const { container } = render(<Parent first={DIFFERENT} afterApply={AFTER_LOST} />);
    await waitFor(() => expect(rowValue(container, "마지막 적용 요청")).toBe(PREV_RECORD));
    expect(rowValue(container, SERVER_PREV)).toBeNull();
    fireEvent.click(applyButton());
    await waitFor(() => expect(rowValue(container, ATTEMPT)).toBe(LOST_1));
    expect(rowValue(container, "마지막 적용 요청")).toBeNull();
    expect(rowValue(container, SERVER_PREV)).toBe(PREV_RECORD);
    expect(dtLabels(container)).toEqual(LOST_LABELS);
    expect(rowValue(container, "요청 결과")).toBe(UNCONFIRMED_TEXT);
    expect(container.textContent).not.toContain("2026-10-20 13:14 · 결과 확인 불가");
    expect(screen.getByText("요청 실패 (HTTP 0)")).toBeInTheDocument();
    expect(screen.getByText(/자동으로 되돌리거나 다시 적용하지 않습니다/)).toBeInTheDocument();
    // ① 은 onDelivered 로 다시 읽고(카드는 따로 부르지 않음) 머리 배지는 그 응답을 따른다.
    await waitFor(() => expect(headBadge(container)?.textContent).toBe(UNKNOWN));
    expect(rowValue(container, "OCI 활성값 마지막 확인")).toBe("확인 불가");
    expect(fetchOciStartupStatus).not.toHaveBeenCalled();
    // POC5-27 — 지난 기록(GET)을 다시 읽어 이번 결과를 덮지 않는다.
    expect(fetchThreePushParamState).toHaveBeenCalledTimes(1);
  });

  it("이전 상태 없음(첫 상태 조회 실패) + 시간 초과 → 서버 기록 줄 없음 · 적용 기준 '—'", async () => {
    fixNow(PRESS_1);
    vi.mocked(fetchThreePushParamState).mockRejectedValue(
      new ApiRequestError("네트워크 호출 실패", 0, null),
    );
    vi.mocked(applyThreePushParamToOci).mockRejectedValue(TIMEOUT());
    const { container } = render(<Parent first={DIFFERENT} afterApply={AFTER_LOST} />);
    await screen.findByText("요청 실패 (HTTP 0)");
    expect(rowValue(container, "마지막 적용 요청")).toBeNull();
    fireEvent.click(applyButton());
    await waitFor(() => expect(rowValue(container, ATTEMPT)).toBe(LOST_1));
    expect(rowValue(container, "적용 기준")).toBe("—");
    expect(rowValue(container, SERVER_PREV)).toBeNull();
    expect(dtLabels(container)).toEqual([
      "적용 기준",
      "OCI 활성값 마지막 확인",
      ATTEMPT,
      "요청 결과",
    ]);
    expect(rowValue(container, "요청 결과")).toBe(UNCONFIRMED_TEXT);
    expect(container.textContent).not.toContain("— · 결과 확인 불가");
  });

  it("이번 시각은 응답이 끝난 때가 아니라 버튼을 누른 때다", async () => {
    fixNow(PRESS_1);
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    let rejectApply: (e: unknown) => void = () => undefined;
    vi.mocked(applyThreePushParamToOci).mockReturnValue(
      new Promise((_resolve, reject) => {
        rejectApply = reject;
      }),
    );
    const { container } = render(<Parent first={DIFFERENT} afterApply={AFTER_LOST} />);
    await waitFor(() => expect(rowValue(container, "마지막 적용 요청")).toBe(PREV_RECORD));
    fireEvent.click(applyButton());
    await screen.findByRole("button", { name: "적용 진행 중..." });
    vi.setSystemTime(new Date(PRESS_2)); // 응답(시간 초과)은 20분 뒤에 끝났다
    await act(async () => {
      rejectApply(TIMEOUT());
    });
    await waitFor(() => expect(rowValue(container, ATTEMPT)).toBe(LOST_1));
    expect(container.textContent).not.toContain("11:05");
  });

  it("이번 시각은 한국 시각이다(세계 표준시 전날 15:30 → 한국 다음 날 00:30)", async () => {
    fixNow("2026-11-18T15:30:00Z");
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci).mockRejectedValue(TIMEOUT());
    const { container } = render(<Parent first={DIFFERENT} afterApply={AFTER_LOST} />);
    await waitFor(() => expect(rowValue(container, "마지막 적용 요청")).toBe(PREV_RECORD));
    fireEvent.click(applyButton());
    await waitFor(() =>
      expect(rowValue(container, ATTEMPT)).toBe(
        "2026-11-19 00:30 · 결과 확인 불가(응답을 받지 못함)",
      ),
    );
  });

  // C3 — 줄 이름은 '결과를 확인할 수 없는 이번 시도'가 있을 때만 바뀐다(응답 없음 · HTTP 오류 응답).
  it.each([
    ["응답 없음(시간 초과)", TIMEOUT, LOST_1, "요청 실패 (HTTP 0)"],
    [
      "HTTP 오류 응답(502)",
      HTTP_502,
      "2026-11-19 10:45 · 결과 확인 불가(서버가 오류로 응답 · HTTP 502)",
      "요청 실패 (HTTP 502)",
    ],
  ] as const)(
    "C3 줄 이름: %s → '최근 적용 시도' · 바로 아래 서버 기록 · 그다음 요청 결과",
    async (_name, makeErr, attemptLine, errText) => {
      fixNow(PRESS_1);
      vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
      vi.mocked(applyThreePushParamToOci).mockRejectedValue(makeErr());
      const { container } = render(<Parent first={DIFFERENT} afterApply={AFTER_LOST} />);
      await waitFor(() => expect(rowValue(container, "마지막 적용 요청")).toBe(PREV_RECORD));
      // 누르기 전(정상 서버 기록) = '마지막 적용 요청' · 새 두 줄 이름 없음.
      expect(dtLabels(container)).toEqual(NORMAL_LABELS);
      fireEvent.click(applyButton());
      await screen.findByText(errText);
      // 줄 순서: 이번 시도 줄 → 바로 아래 서버 기록 줄 → 요청 결과(DOM 에서 이웃).
      expect(dtLabels(container)).toEqual(LOST_LABELS);
      const dts = Array.from(container.querySelectorAll("dt"));
      const attemptDt = dts.find((d) => d.textContent === ATTEMPT);
      const serverDt = dts.find((d) => d.textContent === SERVER_PREV);
      expect(attemptDt?.nextElementSibling?.nextElementSibling).toBe(serverDt);
      expect(serverDt?.nextElementSibling?.nextElementSibling?.textContent).toBe("요청 결과");
      expect(rowValue(container, ATTEMPT)).toBe(attemptLine);
      expect(rowValue(container, SERVER_PREV)).toBe(PREV_RECORD);
      expect(rowValue(container, "요청 결과")).toBe(UNCONFIRMED_TEXT);
      expect(rowValue(container, "마지막 적용 요청")).toBeNull();
      // 옛 줄 이름은 화면에 없다.
      expect(rowValue(container, OLD_PREV)).toBeNull();
      expect(container.textContent).not.toContain(OLD_PREV);
    },
  );

  // C3 — 응답을 받은 서버 기록은 결과 낱말과 상관없이 '마지막 적용 요청' + 서버 종료 시각이다
  // (서버가 저장한 'unconfirmed' 기록도 서버 기록이다 · 이번 시도 줄이 아님).
  it.each([
    ["activated", "적용 완료"],
    ["active_same", "이미 일치"],
    ["failed", "적용 실패"],
    ["unconfirmed", "확인 불가"],
    ["busy", "적용 중"],
  ] as const)(
    "C3 줄 이름: 정상 서버 기록(%s) → '마지막 적용 요청' + 서버 종료 시각 · '최근 적용 시도' 없음",
    async (status, word) => {
      fixNow(PRESS_1);
      vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
      vi.mocked(applyThreePushParamToOci).mockResolvedValue({
        ...APPLIED,
        status,
        applied_at: "2026-11-19 10:47",
        message: "서버 기록 문구(시험용)",
      });
      const { container } = render(<Parent first={DIFFERENT} afterApply={DIFFERENT} />);
      await waitFor(() => expect(rowValue(container, "마지막 적용 요청")).toBe(PREV_RECORD));
      fireEvent.click(applyButton());
      await waitFor(() =>
        expect(rowValue(container, "마지막 적용 요청")).toBe(`2026-11-19 10:47 · 결과 ${word}`),
      );
      expect(dtLabels(container)).toEqual(NORMAL_LABELS);
      expect(rowValue(container, ATTEMPT)).toBeNull();
      expect(rowValue(container, SERVER_PREV)).toBeNull();
      expect(rowValue(container, "요청 결과")).toBe("서버 기록 문구(시험용)");
      // 버튼 누른 시각(10:45)이 아니라 서버 종료 시각(10:47).
      expect(container.textContent).not.toContain("10:45");
    },
  );

  it.each([
    [
      "activated",
      "적용 완료",
      "OCI 활성값을 지금 기준으로 바꾸고 다시 읽어 같음을 확인했습니다 (14/14). 다음 실행부터 이 기준을 씁니다.",
    ],
    ["failed", "적용 실패", "OCI 에 적용하지 못했습니다 (OCI 활성값을 먼저 읽지 못함). 기존 OCI 활성값이 그대로입니다."],
  ] as const)(
    "다시 눌러 응답(%s)을 받으면 '최근 적용 시도' · 서버 기록 줄을 지우고 '마지막 적용 요청'으로 돌아간다",
    async (status, word, message) => {
      fixNow(PRESS_1);
      vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
      vi.mocked(applyThreePushParamToOci)
        .mockRejectedValueOnce(TIMEOUT())
        .mockResolvedValueOnce({
          ...APPLIED,
          status,
          applied_at: "2026-11-19 11:06",
          oci_verified: status === "activated",
          message,
        });
      const { container } = render(<Parent first={DIFFERENT} afterApply={DIFFERENT} />);
      await waitFor(() => expect(rowValue(container, "마지막 적용 요청")).toBe(PREV_RECORD));
      fireEvent.click(applyButton());
      await waitFor(() => expect(rowValue(container, ATTEMPT)).toBe(LOST_1));
      expect(dtLabels(container)).toEqual(LOST_LABELS);
      await screen.findByRole("button", { name: "현재 기준 OCI 적용" });
      vi.setSystemTime(new Date(PRESS_2));
      fireEvent.click(applyButton());
      await waitFor(() =>
        expect(rowValue(container, "마지막 적용 요청")).toBe(`2026-11-19 11:06 · 결과 ${word}`),
      );
      expect(dtLabels(container)).toEqual(NORMAL_LABELS);
      expect(rowValue(container, ATTEMPT)).toBeNull();
      expect(rowValue(container, SERVER_PREV)).toBeNull();
      expect(rowValue(container, "요청 결과")).toBe(message);
      expect(container.textContent).not.toContain("응답을 받지 못함");
      expect(screen.queryByText("요청 실패 (HTTP 0)")).toBeNull();
      expect(screen.queryByText(/자동으로 되돌리거나/)).toBeNull();
      expect(screen.queryByText(/OCI 활성값은 바뀌지 않았습니다/) !== null).toBe(status === "failed");
      expect(fetchThreePushParamState).toHaveBeenCalledTimes(1);
    },
  );

  it("연달아 응답이 없으면 '최근 적용 시도' 시각만 바뀌고 서버 기록 줄은 마지막으로 확인된 서버 기록 그대로", async () => {
    fixNow(PRESS_1);
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci).mockRejectedValue(TIMEOUT());
    const { container } = render(<Parent first={DIFFERENT} afterApply={AFTER_LOST} />);
    await waitFor(() => expect(rowValue(container, "마지막 적용 요청")).toBe(PREV_RECORD));
    fireEvent.click(applyButton());
    await waitFor(() => expect(rowValue(container, ATTEMPT)).toBe(LOST_1));
    await screen.findByRole("button", { name: "현재 기준 OCI 적용" });
    vi.setSystemTime(new Date(PRESS_2));
    fireEvent.click(applyButton());
    await waitFor(() => expect(rowValue(container, ATTEMPT)).toBe(LOST_2));
    expect(rowValue(container, SERVER_PREV)).toBe(PREV_RECORD);
    expect(dtLabels(container)).toEqual(LOST_LABELS);
    // 사이의 응답 없는 시도(10:45)는 서버 기록 줄의 출처가 아니다.
    expect(container.textContent).not.toContain("10:45");
    expect(container.textContent).not.toContain("2026-10-20 13:14 · 결과 확인 불가");
    expect(applyThreePushParamToOci).toHaveBeenCalledTimes(2);
    expect(fetchThreePushParamState).toHaveBeenCalledTimes(1);
  });

  it("연달아 응답 없음 → HTTP 오류 응답이어도 서버 기록 줄의 출처는 같다(C3)", async () => {
    fixNow(PRESS_1);
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci)
      .mockRejectedValueOnce(TIMEOUT())
      .mockRejectedValueOnce(HTTP_502());
    const { container } = render(<Parent first={DIFFERENT} afterApply={AFTER_LOST} />);
    await waitFor(() => expect(rowValue(container, "마지막 적용 요청")).toBe(PREV_RECORD));
    fireEvent.click(applyButton());
    await waitFor(() => expect(rowValue(container, ATTEMPT)).toBe(LOST_1));
    await screen.findByRole("button", { name: "현재 기준 OCI 적용" });
    vi.setSystemTime(new Date(PRESS_2));
    fireEvent.click(applyButton());
    await waitFor(() =>
      expect(rowValue(container, ATTEMPT)).toBe(
        "2026-11-19 11:05 · 결과 확인 불가(서버가 오류로 응답 · HTTP 502)",
      ),
    );
    expect(rowValue(container, SERVER_PREV)).toBe(PREV_RECORD);
    expect(dtLabels(container)).toEqual(LOST_LABELS);
    expect(container.textContent).not.toContain("10:45");
  });

  it("응답을 받은 뒤 다시 응답이 없으면 서버 기록 줄 = 그 뒤 확인된 서버 기록(C3 · 마지막으로 확인된 기록)", async () => {
    fixNow(PRESS_1);
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci)
      .mockResolvedValueOnce({
        ...APPLIED,
        status: "activated",
        applied_at: "2026-11-19 10:46",
        message: "서버 기록 문구(시험용)",
      })
      .mockRejectedValueOnce(TIMEOUT());
    const { container } = render(<Parent first={DIFFERENT} afterApply={DIFFERENT} />);
    await waitFor(() => expect(rowValue(container, "마지막 적용 요청")).toBe(PREV_RECORD));
    fireEvent.click(applyButton());
    await waitFor(() =>
      expect(rowValue(container, "마지막 적용 요청")).toBe("2026-11-19 10:46 · 결과 적용 완료"),
    );
    await screen.findByRole("button", { name: "현재 기준 OCI 적용" });
    vi.setSystemTime(new Date(PRESS_2));
    fireEvent.click(applyButton());
    await waitFor(() => expect(rowValue(container, ATTEMPT)).toBe(LOST_2));
    expect(rowValue(container, SERVER_PREV)).toBe("2026-11-19 10:46 · 결과 적용 완료");
    expect(dtLabels(container)).toEqual(LOST_LABELS);
    expect(container.textContent).not.toContain(PREV_RECORD);
  });

  it("응답 없는 시도 뒤 구성 오류(요청 전 실패)는 줄을 그대로 둔다(구성 오류 경로 그대로)", async () => {
    fixNow(PRESS_1);
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci)
      .mockRejectedValueOnce(TIMEOUT())
      .mockRejectedValueOnce(new ApiConfigError("NEXT_PUBLIC_API_BASE 없음"));
    const { container } = render(<Parent first={DIFFERENT} afterApply={AFTER_LOST} />);
    await waitFor(() => expect(rowValue(container, "마지막 적용 요청")).toBe(PREV_RECORD));
    fireEvent.click(applyButton());
    await waitFor(() => expect(rowValue(container, ATTEMPT)).toBe(LOST_1));
    await screen.findByRole("button", { name: "현재 기준 OCI 적용" });
    vi.setSystemTime(new Date(PRESS_2));
    fireEvent.click(applyButton());
    await screen.findByText("구성 오류: NEXT_PUBLIC_API_BASE 없음");
    expect(rowValue(container, ATTEMPT)).toBe(LOST_1);
    expect(rowValue(container, SERVER_PREV)).toBe(PREV_RECORD);
    expect(dtLabels(container)).toEqual(LOST_LABELS);
    expect(rowValue(container, "요청 결과")).toBe(UNCONFIRMED_TEXT);
  });
});
