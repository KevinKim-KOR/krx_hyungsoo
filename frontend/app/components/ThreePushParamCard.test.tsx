// 「현재 운영 기준」 카드 — 행 표시 계약 (2026-09-27 배치 정리 · 검토 반영).
//
// '마지막 적용' 은 `YYYY-MM-DD HH:MM`(없으면 '—') 그대로다 — POC2 지시문 §5.2 의
// 표시 계약이라 한국식 짧은 날짜(9/22(화) 등)로 바꾸지 않는다. 행 이름 · 배지 문구 ·
// 버튼 문구 · 버튼 하나를 고정한다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

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
  message: "OCI 반영이 완료되었습니다.",
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
  it("세 행: 적용 기준 · 마지막 적용(원형 그대로) · OCI 반영", async () => {
    const { container } = await renderWith();
    expect(rowValue(container, "적용 기준")).toBe("기본 운영 기준");
    expect(rowValue(container, "마지막 적용")).toBe("2026-09-22 00:16");
    expect(rowValue(container, "OCI 반영")).toBe("OCI 반영이 완료되었습니다.");
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
    ["applied", "적용 완료"],
    ["failed", "적용 실패"],
    ["verification_required", "확인 필요"],
    ["not_applied", "미적용"],
  ] as const)("배지 문구: %s → %s", async (status, label) => {
    const { container } = await renderWith({ status });
    const badge = container.querySelector(".ops-card-head .oci-state");
    expect(badge?.textContent).toBe(label);
  });

  it("버튼은 하나 · 문구 그대로 · 눌러야만 적용 요청", async () => {
    await renderWith();
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(1);
    expect(buttons[0].textContent).toBe("현재 기준 OCI 적용");
    expect(applyThreePushParamToOci).not.toHaveBeenCalled();
  });
});
