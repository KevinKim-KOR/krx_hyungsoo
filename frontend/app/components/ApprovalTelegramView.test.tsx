// OCI 적용·알림 화면 — A구간 (역할 분리·상단 재배치) 계약 test.
//
// 설계 정정(Q1-c) 검증:
// - 화면 명칭 = "OCI 적용·알림" (기존 "Approval / Telegram" 아님).
// - 투자 판단 초안 영역·"승인 대기" 표현·빈 자리표시자를 만들지 않는다.
// - 정보 PUSH 3카드는 "자동 발송 · 메시지별 승인 없음" 안내만.
// - 실측 상태(정상/운영 중/최근 성공)를 정보 PUSH 안내에 표시하지 않는다(Q4).
// - approval route key 는 코드 계약이라 화면 텍스트로 노출되지 않는다.
import { describe, it, expect, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";

// 하위 카드들이 mount 시 호출하는 API 를 모두 통제(네트워크 미의존).
const fetchThreePushParamState = vi.fn().mockResolvedValue(null);
const applyThreePushParamToOci = vi.fn();
const refreshUniverseMomentum = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchThreePushParamState: (...a: unknown[]) => fetchThreePushParamState(...a),
    applyThreePushParamToOci: (...a: unknown[]) => applyThreePushParamToOci(...a),
    refreshUniverseMomentum: (...a: unknown[]) => refreshUniverseMomentum(...a),
  };
});

vi.mock("@/lib/api/threePushParam", () => ({
  fetchThreePushParamState: (...a: unknown[]) => fetchThreePushParamState(...a),
  applyThreePushParamToOci: (...a: unknown[]) => applyThreePushParamToOci(...a),
}));

import ApprovalTelegramView from "./ApprovalTelegramView";
import type { Run } from "@/lib/api";

// RunPanel 표시용 최소 run fixture (PENDING — polling 미발생).
function makeRun(overrides: Partial<Run> = {}): Run {
  return {
    run_id: "r-1",
    asof: "2026-07-24",
    status: "PENDING_APPROVAL",
    draft_payload: { note: "미리보기" },
    message_text: "샘플 미리보기 본문",
    push_kind: "market_briefing",
    ...overrides,
  };
}

// mount 시 ThreePushParamCard 의 비동기 state 업데이트(fetchThreePushParamState resolve)를
// flush 해 act() 경고 없이 렌더를 안정화한다.
async function renderView(
  run: Parameters<typeof ApprovalTelegramView>[0]["run"] = null
) {
  const utils = render(<ApprovalTelegramView run={run} setRun={() => {}} />);
  await act(async () => {
    await Promise.resolve();
  });
  return utils;
}

describe("OCI 적용·알림 A구간", () => {
  it("화면 제목이 'OCI 적용·알림' 이다 (기존 Approval/Telegram 아님)", async () => {
    await renderView();
    expect(screen.getByRole("heading", { name: "OCI 적용·알림" })).toBeTruthy();
    expect(screen.queryByText("Approval / Telegram")).toBeNull();
  });

  it("투자 판단 초안 영역·'승인 대기' 표현·빈 자리표시자를 만들지 않는다", async () => {
    const { container } = await renderView(null);
    const text = container.textContent ?? "";
    // 판단 초안/승인 대기 관련 표현이 화면에 없다.
    expect(text).not.toContain("승인 대기");
    expect(text).not.toContain("판단 초안");
    expect(text).not.toContain("초안을 검토");
    // run 이 없어도 "아직 생성된 초안이 없습니다" 같은 빈 자리표시자를 만들지 않는다.
    expect(text).not.toContain("아직 생성된 초안이 없습니다");
  });

  it("정보 PUSH 운영 기준은 '자동 발송 · 메시지별 승인 없음' 안내다", async () => {
    await renderView();
    expect(screen.getByText("정보 PUSH 운영 기준")).toBeTruthy();
    expect(screen.getByText("시장 흐름")).toBeTruthy();
    expect(screen.getByText("보유 종목")).toBeTruthy();
    expect(screen.getByText("급등락")).toBeTruthy();
    // "메시지별 승인 없음" 이 3카드에 표시된다.
    expect(screen.getAllByText(/메시지별 승인 없음/).length).toBeGreaterThanOrEqual(3);
  });

  it("정보 PUSH 안내에 실측 상태(정상/운영 중/최근 성공)를 표시하지 않는다 (Q4)", async () => {
    const { container } = await renderView();
    const guide = container.querySelector('[aria-labelledby="info-push-h"]');
    const text = guide?.textContent ?? "";
    expect(text).not.toContain("정상");
    expect(text).not.toContain("운영 중");
    expect(text).not.toContain("최근 성공");
    // 대신 "운영 기준" 안내임을 명시한다.
    expect(text).toContain("운영 기준");
  });

  it("OCI 운영 기준 적용이 주 작업으로 존재한다", async () => {
    await renderView();
    // ThreePushParamCard 의 제목.
    expect(screen.getByText("현재 운영 기준")).toBeTruthy();
  });

  it("내부 route key 'approval' 이 화면 텍스트로 노출되지 않는다", async () => {
    const { container } = await renderView();
    expect(container.textContent ?? "").not.toContain("approval");
  });
});

describe("OCI 적용·알림 B구간 — 미리보기·수동 전달 점검", () => {
  it("미리보기·수동 전달 점검 영역이 자동 PUSH 와 구분됨을 안내한다", async () => {
    await renderView();
    expect(screen.getByText("미리보기·수동 전달 점검")).toBeTruthy();
    // 자동 발송(OCI)이 아니라 PC 수동임을 명시.
    const sec = screen
      .getByText("미리보기·수동 전달 점검")
      .closest(".manual-preview-section");
    expect(sec?.textContent ?? "").toContain("수동");
  });

  it("신뢰 가능한 push_kind 의 현재 run 은 '현재 미리보기·수동 처리 상태' 로 종류 라벨과 함께 표시된다", async () => {
    await renderView(makeRun({ push_kind: "market_briefing" }));
    expect(screen.getByText("현재 미리보기·수동 처리 상태")).toBeTruthy();
    // push_kind 라벨(시장 흐름) 이 표시된다 — "승인 대기" 로 표시하지 않는다.
    const head = screen
      .getByText("현재 미리보기·수동 처리 상태")
      .closest(".current-manual-run-head");
    expect(head?.textContent ?? "").toContain("시장 흐름");
  });

  it("push_kind=null 인 run 은 미리보기 영역이 아니라 개발·호환 점검에 '종류 확인 불가' 로 표시된다", async () => {
    await renderView(makeRun({ push_kind: null }));
    // 미리보기·수동 처리 상태에는 나타나지 않는다.
    expect(screen.queryByText("현재 미리보기·수동 처리 상태")).toBeNull();
    // 개발·호환 점검에 "종류 확인 불가" 안내가 있다.
    expect(screen.getByText(/종류 확인 불가/)).toBeTruthy();
  });

  it("자동 발송 이력처럼 보이는 표현이 없다 (발송 완료 이력·자동 발송됨 등)", async () => {
    const { container } = await renderView(makeRun());
    const text = container.textContent ?? "";
    // 자동 발송 이력을 읽는 계약이 없으므로 그런 표현을 만들지 않는다.
    expect(text).not.toContain("자동 발송 이력");
    expect(text).not.toContain("발송 완료 이력");
  });

  it("개발·호환 점검은 details(기본 접힘) 안에 있다", async () => {
    const { container } = await renderView();
    const summary = screen.getByText("개발·호환 점검 — 일반 운영 기능 아님");
    const details = summary.closest("details");
    expect(details).toBeTruthy();
    // 기본 접힘 — open 속성 없음.
    expect(details?.hasAttribute("open")).toBe(false);
    void container;
  });
});
