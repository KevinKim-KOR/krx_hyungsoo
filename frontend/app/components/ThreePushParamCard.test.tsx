// 「현재 운영 기준」 카드 — 행 표시 계약 (2026-09-27 배치 정리 · 검토 반영).
//
// '마지막 적용' 은 `YYYY-MM-DD HH:MM`(없으면 '—') 그대로다 — POC2 지시문 §5.2 의
// 표시 계약이라 한국식 짧은 날짜(9/22(화) 등)로 바꾸지 않는다. 행 이름 · 배지 문구 ·
// 버튼 문구 · 버튼 하나를 고정한다.
//
// 2026-10-06 POC3-02D-OPS-04 항목 6(사용자 목업 확정): 이 버튼은 운영 기준을 OCI 에 **전달**만
// 한다 — 배지 · 'OCI 전달' 행 · 버튼 · 안내 1줄 · 전달 뒤 ① 다시 읽기(onDelivered)를 고정한다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

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

import ThreePushParamCard from "./ThreePushParamCard";
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

const APPLIED: ThreePushParamState = {
  status: "applied",
  display_label: "기본 운영 기준",
  applied_at: "2026-09-22 00:16",
  oci_verified: true,
  message: "OCI 에 전달되었습니다.",
};

async function renderWith(state: Partial<ThreePushParamState> = {}) {
  vi.mocked(fetchThreePushParamState).mockResolvedValue({ ...APPLIED, ...state });
  const r = render(<ThreePushParamCard />);
  await screen.findByText(state.display_label ?? APPLIED.display_label);
  return r;
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ThreePushParamCard — 행 · 배지 (2026-09-27)", () => {
  it("세 행: 적용 기준 · 마지막 적용(원형 그대로) · OCI 전달", async () => {
    const { container } = await renderWith();
    expect(rowValue(container, "적용 기준")).toBe("기본 운영 기준");
    expect(rowValue(container, "마지막 적용")).toBe("2026-09-22 00:16");
    expect(rowValue(container, "OCI 전달")).toBe("OCI 에 전달되었습니다.");
    expect(rowValue(container, "OCI 반영")).toBeNull();
  });

  it("전달 완료면 활성 여부는 ① 표에서 보라는 안내 1줄 · 아니면 없음", async () => {
    await renderWith();
    expect(
      screen.getByText("실제로 쓰이는지는 위 ① 표 ‘운영 기준 활성’ 행에서 확인하세요."),
    ).toBeTruthy();
    cleanup();
    await renderWith({ status: "failed" });
    expect(screen.queryByText(/운영 기준 활성/)).toBeNull();
  });

  it("전달 시도가 끝나면 onDelivered 를 부른다(① 다시 읽기)", async () => {
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci).mockResolvedValue({ ...APPLIED });
    const onDelivered = vi.fn();
    render(<ThreePushParamCard onDelivered={onDelivered} />);
    await screen.findByText(APPLIED.display_label);
    fireEvent.click(screen.getByRole("button", { name: "현재 기준 OCI 전달" }));
    await waitFor(() => expect(onDelivered).toHaveBeenCalledTimes(1));
  });

  it("적용한 적이 없으면 '마지막 적용' 은 '—'", async () => {
    const { container } = await renderWith({
      status: "not_applied",
      applied_at: null,
      message: "아직 OCI 에 적용하지 않았습니다.",
    });
    expect(rowValue(container, "마지막 적용")).toBe("—");
  });

  it.each([
    ["applied", "전달 완료"],
    ["failed", "전달 실패"],
    ["verification_required", "확인 필요"],
    ["not_applied", "미전달"],
  ] as const)("배지 문구: %s → %s", async (status, label) => {
    const { container } = await renderWith({ status });
    const badge = container.querySelector(".ops-card-head .oci-state");
    expect(badge?.textContent).toBe(label);
  });

  it("버튼은 하나 · 문구 '현재 기준 OCI 전달' · 눌러야만 전달 요청", async () => {
    await renderWith();
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(1);
    expect(buttons[0].textContent).toBe("현재 기준 OCI 전달");
    expect(applyThreePushParamToOci).not.toHaveBeenCalled();
  });
});
