// POC3-02C-OPS-01 — 장중 급등락 설정 카드 표시 계약.
//
// 기존 ApprovalTelegramView.test.tsx 는 API 가 실패해 카드가 "불러오는 중" 으로
// 렌더되는 상태에서만 통과했다. 그러면 **데이터가 실제로 들어온 화면의 계약이
// 검사되지 않는다.** 여기서는 state 를 실제로 채워 렌더한다.

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import IntradayConfigCard from "./IntradayConfigCard";
import type { IntradayConfigState } from "@/lib/api/intradayConfig";

vi.mock("@/lib/api/intradayConfig", async () => {
  const actual = await vi.importActual<
    typeof import("@/lib/api/intradayConfig")
  >("@/lib/api/intradayConfig");
  return {
    ...actual,
    fetchIntradayConfigState: vi.fn(),
    approveAndApplyIntradayConfig: vi.fn(),
    rejectIntradayConfig: vi.fn(),
  };
});

import { fetchIntradayConfigState } from "@/lib/api/intradayConfig";

const BASE: IntradayConfigState = {
  active_version_id: "intraday-20260910T000000-000001",
  active_source_hash: "a".repeat(64),
  active_data_asof: "2026-09-10",
  active_sector_count: 26,
  candidate_version_id: "intraday-20260916T124928-439563",
  candidate_source_hash: "b".repeat(64),
  candidate_data_asof: "2026-09-11",
  candidate_sector_count: 27,
  changes: [
    { sector_key: "반도체", change: "replaced", before: "091160", after: "396500" },
    { sector_key: "조선", change: "added", before: null, after: "466920" },
  ],
  policy_enabled: false,
  policy_status: "NOT_CONFIGURED",
  deploy_status: null,
  deploy_error: null,
  action_state: "pending_approval",
  payload_error: null,
};

async function renderWith(state: Partial<IntradayConfigState> = {}) {
  vi.mocked(fetchIntradayConfigState).mockResolvedValue({ ...BASE, ...state });
  const r = render(<IntradayConfigCard />);
  await waitFor(() => expect(screen.getByText("확인할 변경")).toBeTruthy());
  return r;
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("IntradayConfigCard — 전달 실패 후 재시도 (검증자 P1-2)", () => {
  // 승인 직후 전달이 실패한 버전이 새로고침 후에도 화면에 남아야 한다.
  // 예전에는 API 가 이 버전을 아예 돌려주지 않아 카드가 통째로 비었다.
  async function renderRetry() {
    vi.mocked(fetchIntradayConfigState).mockResolvedValue({
      ...BASE,
      action_state: "approved_not_deployed",
      deploy_status: "scp_failed",
      deploy_error: "boom",
    });
    const r = render(<IntradayConfigCard />);
    await waitFor(() =>
      expect(screen.getByText("적용하지 못한 설정")).toBeTruthy(),
    );
    return r;
  }

  it("재승인이 아니라 재시도라고 말한다", async () => {
    const { container } = await renderRetry();
    const text = container.textContent ?? "";
    expect(text).toContain("다시 승인할 필요");
    expect(text).toContain("boom");
  });

  it("버튼이 '재시도' 로 바뀐다", async () => {
    const { container } = await renderRetry();
    const labels = Array.from(container.querySelectorAll("button")).map(
      (b) => b.textContent ?? "",
    );
    expect(labels).toEqual(["OCI 적용 재시도", "기각"]);
  });

  it("재시도 화면에서도 '승인 대기' 문구를 쓰지 않는다", async () => {
    const { container } = await renderRetry();
    expect(container.textContent ?? "").not.toContain("승인 대기");
  });
});

describe("IntradayConfigCard — OCI 적용 여부 불명 (설계자 확정)", () => {
  // 완료도 실패도 아니다. 사람이 OCI 를 확인해야 한다.
  async function renderUnconfirmed() {
    vi.mocked(fetchIntradayConfigState).mockResolvedValue({
      ...BASE,
      action_state: "approved_not_deployed",
      deploy_status: "deploy_unconfirmed",
      deploy_error: null,
    });
    const r = render(<IntradayConfigCard />);
    // 같은 문구가 「OCI 반영」 값과 제목 두 곳에 나온다 — 제목으로 특정한다.
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "OCI 적용 여부 확인 필요" }),
      ).toBeTruthy(),
    );
    return r;
  }

  it("완료·실패를 단정하는 표현이 하나도 없다", async () => {
    const { container } = await renderUnconfirmed();
    const text = container.textContent ?? "";
    expect(text).toContain("OCI 적용 여부 확인 필요");
    // 정확한 문자열 2개만 막으면 "OCI 전달만 실패했습니다" 같은 단정을
    // 놓친다(검증자 지적). **단정 표현 전체**를 막는다.
    for (const banned of [
      "적용 실패",
      "적용 완료",
      "적용하지 못한",
      "전달만 실패",
      "실패했습니다",
      "다시 승인할 필요",
    ]) {
      expect(text).not.toContain(banned);
    }
  });

  it("재시도 문단과 동시에 렌더되지 않는다", async () => {
    const { container } = await renderUnconfirmed();
    const headings = Array.from(container.querySelectorAll("h3")).map(
      (h) => h.textContent ?? "",
    );
    expect(headings).toEqual(["OCI 적용 여부 확인 필요"]);
  });

  it("그래도 재시도는 할 수 있다", async () => {
    const { container } = await renderUnconfirmed();
    const labels = Array.from(container.querySelectorAll("button")).map(
      (b) => b.textContent ?? "",
    );
    expect(labels).toEqual(["OCI 적용 재시도", "기각"]);
  });

  it("자동 재전송하지 않는다고 알린다", async () => {
    const { container } = await renderUnconfirmed();
    const text = container.textContent ?? "";
    expect(text).toContain("확인하지 못했습니다");
    expect(text).toContain("자동으로");
  });
});

describe("IntradayConfigCard — 손상 설정 (검증자 r3)", () => {
  it("깨진 설정을 '0개' 로 그리지 않고 읽지 못했다고 말한다", async () => {
    vi.mocked(fetchIntradayConfigState).mockResolvedValue({
      ...BASE,
      payload_error: "intraday-x 설정 내용을 읽을 수 없다",
    });
    const { container } = render(<IntradayConfigCard />);
    await waitFor(() =>
      expect(screen.getByText(/저장된 설정을 읽지 못했습니다/)).toBeTruthy(),
    );
    const text = container.textContent ?? "";
    expect(text).toContain("intraday-x");
    expect(text).not.toContain("0개");
    expect(container.querySelectorAll("button").length).toBe(0);
  });
});

describe("IntradayConfigCard", () => {
  it("표시명이 '장중 급등락 설정' 이다 (내부 이름 비노출)", async () => {
    const { container } = await renderWith();
    expect(
      screen.getByRole("heading", { name: "장중 급등락 설정" }),
    ).toBeTruthy();
    const text = container.textContent ?? "";
    expect(text).not.toContain("INTRADAY_ALERT_CONFIG");
    expect(text).not.toContain("intraday_alert_policy");
  });

  it("'승인 대기' 문구를 쓰지 않는다 (승인·적용 화면 기존 계약)", async () => {
    const { container } = await renderWith();
    expect(container.textContent ?? "").not.toContain("승인 대기");
  });

  it("enabled=false·정책 미설정을 오류로 표현하지 않는다", async () => {
    const { container } = await renderWith();
    const text = container.textContent ?? "";
    expect(text).toContain("구조 준비 완료 · 장중 알림 정책 설정 전");
    for (const banned of ["오류", "실패", "에러", "비정상"]) {
      expect(text).not.toContain(banned);
    }
  });

  it("아직 보낸 적 없는 상태를 '적용 실패' 로 표시하지 않는다", async () => {
    const { container } = await renderWith({ deploy_status: null });
    const text = container.textContent ?? "";
    expect(text).toContain("아직 적용하지 않음");
    expect(text).not.toContain("적용 실패");
  });

  it("설계자 요구 항목을 모두 보여준다", async () => {
    const { container } = await renderWith();
    const text = container.textContent ?? "";
    expect(text).toContain("27개"); // 자동 분류 사업군
    expect(text).toContain("27종목"); // 적용 예정 대표 ETF
    expect(text).toContain("2026-09-11"); // 데이터 기준일
    expect(text).toContain("intraday-20260916T124928-439563"); // 설정 버전
    expect(text).toContain("bbbbbbbbbbbb"); // checksum 앞자리
  });

  it("직전 승인본 대비 변경 요약을 보여준다", async () => {
    const { container } = await renderWith();
    const text = container.textContent ?? "";
    expect(text).toContain("반도체");
    expect(text).toContain("교체");
    expect(text).toContain("091160");
    expect(text).toContain("396500");
    expect(text).toContain("조선");
    expect(text).toContain("추가");
  });

  it("ETF 를 직접 고르는 편집 UI 가 없다", async () => {
    const { container } = await renderWith();
    expect(container.querySelectorAll("input").length).toBe(0);
    expect(container.querySelectorAll("select").length).toBe(0);
    // 동작 버튼은 승인·기각 둘뿐이다.
    const labels = Array.from(container.querySelectorAll("button")).map(
      (b) => b.textContent ?? "",
    );
    expect(labels).toEqual(["승인하고 OCI 적용", "기각"]);
  });

  it("승인과 적용이 한 번의 동작이다 (버튼이 둘로 나뉘지 않는다)", async () => {
    const { container } = await renderWith();
    const labels = Array.from(container.querySelectorAll("button")).map(
      (b) => b.textContent ?? "",
    );
    expect(labels.filter((l) => l.includes("승인")).length).toBe(1);
    expect(labels.some((l) => l === "OCI 적용")).toBe(false);
  });
});
