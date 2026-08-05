// 승인·적용 화면 — 역할 축소(POC3-07 §5.4·§7·§10.1) 계약 test.
//
// 검증:
// - 화면 제목 = "승인·적용".
// - 유일한 실제 작업 = OCI 운영 기준 적용(ThreePushParamCard).
// - 정보 PUSH 카드·미리보기·샘플·개발 호환 점검·현재 run 표시는 여기 없다(진단·상태로 이동).
// - 투자 판단 초안·승인 대기·빈 자리표시자를 만들지 않는다.
// - 내부 route key 'approval' 이 화면 텍스트로 노출되지 않는다.
import { describe, it, expect, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";

const fetchThreePushParamState = vi.fn().mockResolvedValue(null);
const applyThreePushParamToOci = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchThreePushParamState: (...a: unknown[]) => fetchThreePushParamState(...a),
    applyThreePushParamToOci: (...a: unknown[]) => applyThreePushParamToOci(...a),
  };
});

vi.mock("@/lib/api/threePushParam", () => ({
  fetchThreePushParamState: (...a: unknown[]) => fetchThreePushParamState(...a),
  applyThreePushParamToOci: (...a: unknown[]) => applyThreePushParamToOci(...a),
}));

import ApprovalTelegramView from "./ApprovalTelegramView";

async function renderView() {
  const utils = render(<ApprovalTelegramView />);
  await act(async () => {
    await Promise.resolve();
  });
  return utils;
}

describe("승인·적용 — 역할 축소", () => {
  it("화면 제목이 '승인·적용' 이다", async () => {
    await renderView();
    expect(screen.getByRole("heading", { name: "승인·적용" })).toBeTruthy();
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
