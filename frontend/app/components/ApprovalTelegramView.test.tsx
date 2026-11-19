// 「OCI 운영·적용」 화면 — 역할 축소(POC3-07 §5.4·§7·§10.1) 계약 test.
//
// 2026-09-27 사용자 직접 지시: 「승인·적용」과 「OCI 운영 상태」를 한 화면으로
// 합쳐 제목이 「OCI 운영·적용」이 됐다(① 지금 OCI 상태 → ② OCI 에 적용).
// POC6-34 O1 · O4: ① 이름은 '① 마지막 OCI 점검 (읽기만)' · 머리 안내도 그 이름으로.
//
// 검증:
// - 화면 제목 = "OCI 운영·적용" (예전 "승인·적용").
// - ① 읽기(OCI 상태) · ② 쓰기(적용 카드 두 장)가 이 순서로 있다.
// - 유일한 실제 작업 = OCI 운영 기준 적용(ThreePushParamCard).
// - 정보 PUSH 카드·미리보기·샘플·개발 호환 점검·현재 run 표시는 여기 없다(진단·상태로 이동).
// - 투자 판단 초안·승인 대기·빈 자리표시자를 만들지 않는다.
// - 내부 route key 'approval' 이 화면 텍스트로 노출되지 않는다.
import { describe, it, expect, vi } from "vitest";
import { render, screen, act, within, fireEvent, waitFor } from "@testing-library/react";

const fetchThreePushParamState = vi.fn().mockResolvedValue(null);
const applyThreePushParamToOci = vi.fn();
// ① 패널 · 장중 급등락 카드의 조회도 대역으로 — 실제 요청을 보내지 않는다.
const fetchOciStartupStatus = vi.fn().mockResolvedValue({
  checked_at: "2026-09-27T08:18:31+00:00",
  reachable: true,
  overall: "OPERATING",
  summary_line: "OCI 자동 운영 스케줄 활성 (필수 3종 등록 · 기동 시 확인)",
  crontab_active: true,
  jobs: [
    { job: "crontab", status: "SUCCESS", detail: "필수 스케줄(시장·보유·급등락) 모두 등록됨" },
  ],
  note: "",
});
const fetchIntradayConfigState = vi.fn().mockRejectedValue(new Error("test: 조회 안 함"));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchThreePushParamState: (...a: unknown[]) => fetchThreePushParamState(...a),
    applyThreePushParamToOci: (...a: unknown[]) => applyThreePushParamToOci(...a),
    fetchOciStartupStatus: (...a: unknown[]) => fetchOciStartupStatus(...a),
  };
});

vi.mock("@/lib/api/threePushParam", () => ({
  fetchThreePushParamState: (...a: unknown[]) => fetchThreePushParamState(...a),
  applyThreePushParamToOci: (...a: unknown[]) => applyThreePushParamToOci(...a),
}));

vi.mock("@/lib/api/intradayConfig", () => ({
  fetchIntradayConfigState: (...a: unknown[]) => fetchIntradayConfigState(...a),
  approveAndApplyIntradayConfig: vi.fn(),
  rejectIntradayConfig: vi.fn(),
}));

import ApprovalTelegramView from "./ApprovalTelegramView";

async function renderView() {
  const utils = render(<ApprovalTelegramView />);
  await act(async () => {
    await Promise.resolve();
  });
  return utils;
}

describe("OCI 운영·적용 — 역할 축소", () => {
  it("화면 제목이 'OCI 운영·적용' 이다", async () => {
    await renderView();
    expect(screen.getByRole("heading", { level: 1, name: "OCI 운영·적용" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "승인·적용" })).toBeNull();
    expect(screen.queryByText("Approval / Telegram")).toBeNull();
  });

  it("OCI 운영 기준 적용이 유일한 실제 작업으로 존재한다", async () => {
    await renderView();
    // ThreePushParamCard 의 제목.
    expect(screen.getByText("현재 운영 기준")).toBeTruthy();
  });

  it("투자 판단 초안·승인 대기·빈 자리표시자를 만들지 않는다", async () => {
    const { container } = await renderView();
    const text = container.textContent ?? "";
    expect(text).not.toContain("승인 대기");
    expect(text).not.toContain("판단 초안");
    expect(text).not.toContain("아직 생성된 초안이 없습니다");
  });

  it("미리보기·샘플·개발 호환 점검은 이 화면에 없다 (진단·상태로 이동)", async () => {
    const { container } = await renderView();
    const text = container.textContent ?? "";
    expect(text).not.toContain("미리보기·수동 전달 점검");
    expect(text).not.toContain("개발·호환 점검 — 일반 운영 기능 아님");
    expect(text).not.toContain("현재 미리보기·수동 처리 상태");
    // 정보 PUSH 를 카드로 만들지 않는다 (역할 안내 문장은 있어도 카드 아님).
    expect(container.querySelector('[aria-labelledby="info-push-h"]')).toBeNull();
  });

  it("내부 route key 'approval' 이 화면 텍스트로 노출되지 않는다", async () => {
    const { container } = await renderView();
    expect(container.textContent ?? "").not.toContain("approval");
  });
});

describe("OCI 운영·적용 — ① 읽기 · ② 적용 합친 화면 (2026-09-27)", () => {
  it("섹션이 ① 마지막 OCI 점검 → ② OCI 에 적용 순서로 있다", async () => {
    const { container } = await renderView();
    const h2 = Array.from(container.querySelectorAll("h2")).map((h) => h.textContent ?? "");
    expect(h2).not.toContain("① 지금 OCI 상태 (읽기만)");
    const now = h2.indexOf("① 마지막 OCI 점검 (읽기만)");
    const apply = h2.indexOf("② OCI 에 적용 (버튼으로 반영)");
    expect(now).toBeGreaterThanOrEqual(0);
    expect(apply).toBeGreaterThan(now);
    // ① 섹션 제목 위에 다른 h2 가 없다(① 이 화면의 첫 섹션).
    expect(now).toBe(0);
  });

  it("① 에 OCI 상태 요약 + 표가 있고 버튼이 없다 (읽기만)", async () => {
    await renderView();
    const now = screen
      .getByRole("heading", { level: 2, name: "① 마지막 OCI 점검 (읽기만)" })
      .closest("section") as HTMLElement;
    expect(await within(now).findByText("예약표에서 필수 3종 표기 확인")).toBeTruthy();
    // 08:18 UTC = 17:18 KST (2026-09-27 일요일) · 재시작 포함 안내.
    expect(
      within(now).getByText("확인 시각 9/27(일) 17:18 · PC 백엔드가 시작될 때 한 번 읽음(재시작 포함)"),
    ).toBeTruthy();
    expect(within(now).getByText(/실제 수신은 Telegram 에서 확인/)).toBeTruthy();
    expect(within(now).getByRole("table")).toBeTruthy();
    expect(within(now).queryAllByRole("button")).toHaveLength(0);
    // 패널 자기 h1 이 없다 — 화면 h1 은 「OCI 운영·적용」 하나.
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("② 에 현재 운영 기준 → 장중 급등락 설정 순서로 카드가 있다", async () => {
    await renderView();
    const apply = screen
      .getByRole("heading", { level: 2, name: "② OCI 에 적용 (버튼으로 반영)" })
      .closest("section") as HTMLElement;
    const param = within(apply).getByRole("heading", { name: "현재 운영 기준" });
    const intraday = within(apply).getByRole("region", { name: "장중 급등락 설정" });
    expect(
      param.compareDocumentPosition(intraday) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    // POC5-27 — 운영 기준 카드 버튼은 다시 '적용'(실제 활성화 · ② 제목 · 화면 안내는 그대로).
    expect(within(apply).getByRole("button", { name: "현재 기준 OCI 적용" })).toBeTruthy();
  });

  it("② 운영 기준 적용이 끝나면 ① 을 다시 읽는다(POC3-02D-OPS-04 항목 6 · POC5-27)", async () => {
    applyThreePushParamToOci.mockResolvedValue({
      status: "activated",
      display_label: "기본 운영 기준",
      applied_at: "2026-10-20 10:12",
      oci_verified: true,
      message: "OCI 활성값을 지금 기준으로 바꾸고 다시 읽어 같음을 확인했습니다 (14/14). 다음 실행부터 이 기준을 씁니다.",
      content_sha256: null,
    });
    await renderView();
    const before = fetchOciStartupStatus.mock.calls.length;
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "현재 기준 OCI 적용" }));
    });
    await waitFor(() =>
      expect(fetchOciStartupStatus.mock.calls.length).toBe(before + 1),
    );
  });

  it("안내: 정보 PUSH 는 승인 대상 아님 · 발송 여부는 Telegram · 진단·상태 안내 없음", async () => {
    const { container } = await renderView();
    const header = container.querySelector("header.oci-alert-header") as HTMLElement;
    const text = header.textContent ?? "";
    expect(text).toContain("정보 PUSH(시장 흐름·보유 종목·급등락)는 OCI 가 자동 발송하며");
    expect(text).toContain("승인 대상이");
    expect(text).toContain("PUSH 발송 여부는 Telegram 에서 확인합니다");
    expect(text).not.toContain("진단·상태에서 확인");
  });

  it("머리 안내: ① 은 마지막 OCI 점검 결과 · ② 에서 적용할 변경 유무와 마지막 적용 요청 (POC6-34 O4)", async () => {
    const { container } = await renderView();
    const header = container.querySelector("header.oci-alert-header") as HTMLElement;
    const first = header.querySelectorAll("p.subtitle")[0].textContent ?? "";
    expect(first.replace(/\s+/g, " ")).toBe(
      "① 에서 마지막 OCI 점검 결과를 확인하고, ② 에서 PC 에서 확정한 운영 기준(PARAM · 장중 급등락 설정)을 사용자가 [적용] 버튼으로 OCI 에 반영합니다. 적용할 변경 유무와 마지막 적용 요청은 ② 의 카드에서 확인합니다.",
    );
    expect(header.textContent).not.toContain("지금 OCI 상태를 확인");
    expect(header.textContent).not.toContain("적용 상태·마지막 적용 시각");
  });
});

// POC6-34 I-8 — ② 「현재 운영 기준」 카드는 GET /oci/startup-status 를 따로 부르지 않고 ① 이 받은
// 같은 응답을 쓴다. 그래서 ① '운영 기준 활성' 행과 ② 머리 배지 · 'OCI 활성값 마지막 확인' 줄이
// 늘 같은 응답을 가리킨다(적용 뒤 ① 다시 읽기도 그대로 따라감). 값은 시험용 고정 자료다.
describe("OCI 운영·적용 — ① 과 ② 가 같은 응답 (POC6-34 I-8)", () => {
  const CRON = { job: "crontab", status: "SUCCESS", detail: "필수 스케줄(시장·보유·급등락) 모두 등록됨" };
  function ociResponse(paramStatus: "SUCCESS" | "STALE", readAt: string, source: "startup" | "apply") {
    return {
      checked_at: "2026-09-27T08:18:31+00:00",
      reachable: true,
      overall: "OPERATING",
      summary_line: "OCI 자동 운영 스케줄 활성 (필수 3종 등록 · 기동 시 확인)",
      crontab_active: true,
      jobs: [
        CRON,
        {
          job: "param_active",
          status: paramStatus,
          detail: paramStatus === "SUCCESS" ? "일치 (3/3) · 시험 자료" : "다름 (1/3) · 시험 자료",
        },
      ],
      note: "",
      param_read_at: readAt,
      param_source: source,
    };
  }
  const nowSection = () =>
    screen
      .getByRole("heading", { level: 2, name: "① 마지막 OCI 점검 (읽기만)" })
      .closest("section") as HTMLElement;
  const paramCard = () =>
    screen.getByRole("heading", { level: 3, name: "현재 운영 기준" }).closest("section") as HTMLElement;
  const paramRowState = () =>
    within(nowSection()).getByText("운영 기준 활성").closest("tr")?.querySelector(".oci-state")
      ?.textContent;
  const readLine = () =>
    within(paramCard()).getByText("OCI 활성값 마지막 확인").nextElementSibling?.textContent;

  it("① 과 ② 가 같은 응답을 쓴다 · GET /oci/startup-status 는 1번", async () => {
    fetchOciStartupStatus.mockResolvedValueOnce(
      ociResponse("SUCCESS", "2026-09-27T08:18:31+00:00", "startup"),
    );
    const before = fetchOciStartupStatus.mock.calls.length;
    await renderView();
    expect(await within(paramCard()).findByText("확인값 기준으로 적용할 변경 없음")).toBeTruthy();
    expect(paramRowState()).toBe("일치");
    expect(readLine()).toBe("9/27(일) 17:18 · 마지막 OCI 점검 때 읽음");
    // 몇 번 더 흘려 보내도 추가 조회가 없다(② 가 따로 부르지 않음).
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(fetchOciStartupStatus.mock.calls.length - before).toBe(1);
  });

  it("적용이 끝나면 ① 을 다시 읽고 ② 도 그 응답을 따른다(다름 → 일치 · 적용 요청 때 읽음) · 조회 2번", async () => {
    fetchOciStartupStatus
      .mockResolvedValueOnce(ociResponse("STALE", "2026-09-27T08:18:31+00:00", "startup"))
      .mockResolvedValueOnce(ociResponse("SUCCESS", "2026-09-27T08:20:05+00:00", "apply"));
    applyThreePushParamToOci.mockResolvedValue({
      status: "activated",
      display_label: "기본 운영 기준",
      applied_at: "2026-09-27 17:20",
      oci_verified: true,
      message: "OCI 활성값을 지금 기준으로 바꾸고 다시 읽어 같음을 확인했습니다 (3/3). 다음 실행부터 이 기준을 씁니다.",
      content_sha256: null,
    });
    const before = fetchOciStartupStatus.mock.calls.length;
    await renderView();
    expect(await within(paramCard()).findByText("적용할 변경 있음")).toBeTruthy();
    expect(paramRowState()).toBe("다름");
    await act(async () => {
      fireEvent.click(within(paramCard()).getByRole("button", { name: "현재 기준 OCI 적용" }));
    });
    expect(await within(paramCard()).findByText("확인값 기준으로 적용할 변경 없음")).toBeTruthy();
    expect(paramRowState()).toBe("일치");
    expect(readLine()).toBe("9/27(일) 17:20 · 적용 요청 때 읽음");
    expect(fetchOciStartupStatus.mock.calls.length - before).toBe(2);
  });

  it("① 조회가 실패하면 ② 도 '적용할 변경 확인 불가' · 확인 줄 '확인 불가' · 조회 1번", async () => {
    fetchOciStartupStatus.mockRejectedValueOnce(new Error("시험: 조회 실패"));
    const before = fetchOciStartupStatus.mock.calls.length;
    await renderView();
    expect(await within(nowSection()).findByText("알 수 없는 오류: 시험: 조회 실패")).toBeTruthy();
    expect(await within(paramCard()).findByText("적용할 변경 확인 불가")).toBeTruthy();
    expect(readLine()).toBe("확인 불가");
    expect(fetchOciStartupStatus.mock.calls.length - before).toBe(1);
  });

  it("적용 뒤 ① 다시 읽기가 실패하면 ② 도 앞선 '변경 없음'을 남기지 않는다", async () => {
    fetchOciStartupStatus
      .mockResolvedValueOnce(ociResponse("SUCCESS", "2026-09-27T08:18:31+00:00", "startup"))
      .mockRejectedValueOnce(new Error("시험: 다시 읽기 실패"));
    applyThreePushParamToOci.mockResolvedValue({
      status: "active_same",
      display_label: "기본 운영 기준",
      applied_at: "2026-09-27 17:20",
      oci_verified: true,
      message: "OCI 활성값이 이미 지금 기준과 같습니다 (3/3). 바꾸지 않았습니다.",
      content_sha256: null,
    });
    await renderView();
    expect(await within(paramCard()).findByText("확인값 기준으로 적용할 변경 없음")).toBeTruthy();
    const card = paramCard();
    // 일치일 때 버튼은 [자세히 보기 (필요할 때 다시 적용)] 안에 있다(기본 닫힘 · 펼쳐서 누름).
    const details = card.querySelector("details.ops-details") as HTMLDetailsElement;
    expect(details.open).toBe(false);
    details.open = true;
    await act(async () => {
      fireEvent.click(within(card).getByRole("button", { name: "현재 기준 OCI 적용" }));
    });
    expect(await within(paramCard()).findByText("적용할 변경 확인 불가")).toBeTruthy();
    expect(within(paramCard()).queryByText("확인값 기준으로 적용할 변경 없음")).toBeNull();
    expect(readLine()).toBe("확인 불가");
  });

  it("① 응답 전에는 ② 도 '적용할 변경 확인 중…'", async () => {
    fetchOciStartupStatus.mockReturnValueOnce(new Promise(() => undefined));
    await renderView();
    expect(within(nowSection()).getByText("확인 중…")).toBeTruthy();
    expect(within(paramCard()).getByText("적용할 변경 확인 중…")).toBeTruthy();
    expect(readLine()).toBe("확인 중…");
  });
});
