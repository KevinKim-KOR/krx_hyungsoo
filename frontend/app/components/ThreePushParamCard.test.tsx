// 「현재 운영 기준」 카드 — 행 표시 계약 (2026-09-27 배치 정리 · 검토 반영).
//
// '마지막 적용' 은 `YYYY-MM-DD HH:MM`(없으면 '—') 그대로다 — POC2 지시문 §5.2 의
// 표시 계약이라 한국식 짧은 날짜(9/22(화) 등)로 바꾸지 않는다. 행 이름 · 배지 문구 ·
// 버튼 문구 · 버튼 하나를 고정한다.
//
// 2026-10-06 POC3-02D-OPS-04 항목 6: 버튼이 OCI 에 **전달**만 하던 때의 문구를 고정했었다.
// 2026-10-20 POC5-27(PLAN 판정 · 사용자 목업 확인): 버튼 = [현재 기준 OCI 적용](실제 활성화 +
// 다시 읽어 확인). 배지 · 'OCI 적용' 행 · 버튼 · 안내 · 결과 4종 · 예전 전달 기록 표시 ·
// 적용 뒤 ① 다시 읽기(onDelivered)를 고정한다.
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
import { ApiConfigError, ApiRequestError } from "@/lib/api";
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
  status: "active_same",
  display_label: "기본 운영 기준",
  applied_at: "2026-10-20 10:12",
  oci_verified: true,
  message: "OCI 활성값이 이미 지금 기준과 같습니다 (14/14). 새로 바꾼 것은 없습니다.",
};
const NOTE =
  "OCI 러너가 이후 실행에서 읽는 기준을 적용합니다. 이미 시작한 실행은 그때 읽은 기준으로 끝납니다. 지금 OCI 활성값과의 차이는 위 ① 표 ‘운영 기준 활성’ 행에 있습니다.";

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
  it("세 행: 적용 기준 · 마지막 적용(원형 그대로) · OCI 적용", async () => {
    const { container } = await renderWith();
    expect(rowValue(container, "적용 기준")).toBe("기본 운영 기준");
    expect(rowValue(container, "마지막 적용")).toBe("2026-10-20 10:12");
    expect(rowValue(container, "OCI 적용")).toBe(APPLIED.message);
    expect(rowValue(container, "OCI 전달")).toBeNull();
  });

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

  it("적용 시도가 끝나면 onDelivered 를 부른다(① 다시 읽기)", async () => {
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci).mockResolvedValue({ ...APPLIED });
    const onDelivered = vi.fn();
    render(<ThreePushParamCard onDelivered={onDelivered} />);
    await screen.findByText(APPLIED.display_label);
    fireEvent.click(screen.getByRole("button", { name: "현재 기준 OCI 적용" }));
    await waitFor(() => expect(onDelivered).toHaveBeenCalledTimes(1));
  });

  it("응답이 빨리 와도 끝난 뒤 '진행 중' 문구가 다시 나타나지 않는다(남은 타이머 정리)", async () => {
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci).mockResolvedValue({
      ...APPLIED,
      status: "busy",
      message: "이미 적용이 진행 중입니다. 끝난 뒤 이 화면을 다시 열어 결과를 확인하세요.",
    });
    render(<ThreePushParamCard />);
    await screen.findByText(APPLIED.display_label);
    fireEvent.click(screen.getByRole("button", { name: "현재 기준 OCI 적용" }));
    await screen.findByRole("button", { name: "현재 기준 OCI 적용" });
    await new Promise((r) => setTimeout(r, 1300)); // 400ms · 1200ms 타이머가 지난 뒤
    expect(screen.queryByText(/진행 중:/)).toBeNull();
  });

  // 검증자 F1 — 적용 요청의 응답을 받지 못하면 이번 결과는 '확인 불가'. 지난 성공 기록(GET)으로
  // 다시 읽어 덮지 않고, 이번 오류 안내도 남는다(설계 §4 · 응답 단절 = 결과 미확인).
  it.each([
    ["activated", "적용 완료", new ApiRequestError("요청 시간 초과", 0, null), "요청 실패 (HTTP 0)"],
    ["active_same", "일치 · 변경 없음", new ApiRequestError("네트워크 호출 실패", 0, null), "요청 실패 (HTTP 0)"],
    ["activated", "적용 완료", new ApiRequestError("요청 실패", 502, null), "요청 실패 (HTTP 502)"],
    ["active_same", "일치 · 변경 없음", new Error("body"), "알 수 없는 오류가 발생했습니다."],
  ] as const)(
    "응답 단절: 이전 %s('%s') 뒤에도 이번 결과는 '확인 불가' · 오류 안내 유지",
    async (prevStatus, prevBadge, err, errText) => {
      vi.mocked(fetchThreePushParamState).mockResolvedValue({
        ...APPLIED,
        status: prevStatus,
      });
      vi.mocked(applyThreePushParamToOci).mockRejectedValue(err);
      const onDelivered = vi.fn();
      render(<ThreePushParamCard onDelivered={onDelivered} />);
      expect(await screen.findByText(prevBadge)).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "현재 기준 OCI 적용" }));
      expect(await screen.findByText("확인 불가")).toBeInTheDocument();
      expect(screen.queryByText(prevBadge)).toBeNull();
      expect(
        screen.getByText(
          "적용 결과를 확인하지 못했습니다. OCI 활성값이 바뀌었는지 알 수 없습니다.",
        ),
      ).toBeInTheDocument();
      expect(screen.getByText(errText)).toBeInTheDocument();
      expect(screen.getByText(/자동으로 되돌리거나 다시 적용하지 않습니다/)).toBeInTheDocument();
      // 지난 기록을 다시 읽어 덮지 않는다(처음 1회만) · ① 은 다시 읽게 한다.
      expect(fetchThreePushParamState).toHaveBeenCalledTimes(1);
      await waitFor(() => expect(onDelivered).toHaveBeenCalledTimes(1));
    },
  );

  // r3(검증자 F1-NULL) — 이전 상태의 모든 종류(첫 상태 조회 실패로 '없음' 포함) × 응답을 못 받은
  // 오류 종류. 어느 조합이든 이번 결과는 '확인 불가' + 안내 + 이번 오류 줄이다(설계 §4).
  const PRIORS = [
    ["없음(첫 조회 실패)", null, null],
    ["not_applied", "not_applied", "미적용"],
    ["delivered_only", "delivered_only", "이전 전달 기록"],
    ["active_same", "active_same", "일치 · 변경 없음"],
    ["activated", "activated", "적용 완료"],
    ["failed", "failed", "적용 실패"],
    ["unconfirmed", "unconfirmed", "확인 불가"],
    ["busy", "busy", "적용 중"],
    ["verification_required", "verification_required", "확인 필요"],
  ] as const;
  const LOST = [
    ["HTTP 0", () => new ApiRequestError("요청 시간 초과", 0, null), "요청 실패 (HTTP 0)"],
    ["본문 오류", () => new Error("body"), "알 수 없는 오류가 발생했습니다."],
  ] as const;
  const TABLE = PRIORS.flatMap((p) => LOST.map((l) => [...p, ...l] as const));

  it.each(TABLE)(
    "응답 단절 조합: 이전 %s × %s → '확인 불가'",
    async (_name, prevStatus, prevBadge, _lost, makeErr, errText) => {
      if (prevStatus === null) {
        vi.mocked(fetchThreePushParamState).mockRejectedValue(
          new ApiRequestError("네트워크 호출 실패", 0, null),
        );
      } else {
        vi.mocked(fetchThreePushParamState).mockResolvedValue({
          ...APPLIED,
          status: prevStatus,
        });
      }
      vi.mocked(applyThreePushParamToOci).mockRejectedValue(makeErr());
      const { container } = render(<ThreePushParamCard />);
      if (prevBadge === null) {
        await screen.findByText("요청 실패 (HTTP 0)");
        expect(screen.queryByText("확인 불가")).toBeNull();
      } else {
        await screen.findByText(prevBadge);
      }
      fireEvent.click(screen.getByRole("button", { name: "현재 기준 OCI 적용" }));
      await waitFor(() => expect(applyThreePushParamToOci).toHaveBeenCalledTimes(1));
      await screen.findByRole("button", { name: "현재 기준 OCI 적용" });
      expect(screen.getByText("확인 불가")).toBeInTheDocument();
      if (prevBadge !== null && prevBadge !== "확인 불가") {
        expect(screen.queryByText(prevBadge)).toBeNull();
      }
      expect(
        screen.getByText(
          "적용 결과를 확인하지 못했습니다. OCI 활성값이 바뀌었는지 알 수 없습니다.",
        ),
      ).toBeInTheDocument();
      expect(screen.getByText(/자동으로 되돌리거나 다시 적용하지 않습니다/)).toBeInTheDocument();
      expect(screen.getByText(errText)).toBeInTheDocument();
      if (prevStatus === null) {
        // 적용 기준 · 마지막 적용은 모른다 — 카드의 기존 빈 값 표기 '—'.
        expect(rowValue(container, "적용 기준")).toBe("—");
        expect(rowValue(container, "마지막 적용")).toBe("—");
      } else {
        expect(rowValue(container, "적용 기준")).toBe(APPLIED.display_label);
        expect(rowValue(container, "마지막 적용")).toBe(APPLIED.applied_at);
      }
      expect(fetchThreePushParamState).toHaveBeenCalledTimes(1); // 지난 기록으로 다시 읽지 않는다
    },
  );

  it.each([
    ["없음(첫 조회 실패)", null],
    ["active_same", "일치 · 변경 없음"],
  ] as const)(
    "구성 오류 조합: 이전 %s → 상태 그대로 · '확인 불가' 없음",
    async (_name, prevBadge) => {
      if (prevBadge === null) {
        vi.mocked(fetchThreePushParamState).mockRejectedValue(
          new ApiConfigError("NEXT_PUBLIC_API_BASE 없음"),
        );
      } else {
        vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
      }
      vi.mocked(applyThreePushParamToOci).mockRejectedValue(
        new ApiConfigError("NEXT_PUBLIC_API_BASE 없음"),
      );
      render(<ThreePushParamCard />);
      await screen.findByText(prevBadge ?? "구성 오류: NEXT_PUBLIC_API_BASE 없음");
      fireEvent.click(screen.getByRole("button", { name: "현재 기준 OCI 적용" }));
      await waitFor(() => expect(applyThreePushParamToOci).toHaveBeenCalledTimes(1));
      await screen.findByRole("button", { name: "현재 기준 OCI 적용" });
      expect(screen.getByText("구성 오류: NEXT_PUBLIC_API_BASE 없음")).toBeInTheDocument();
      expect(screen.queryByText("확인 불가")).toBeNull();
      if (prevBadge !== null) expect(screen.getByText(prevBadge)).toBeInTheDocument();
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
    render(<ThreePushParamCard />);
    await screen.findByText("요청 실패 (HTTP 0)");
    fireEvent.click(screen.getByRole("button", { name: "현재 기준 OCI 적용" }));
    expect(await screen.findByText("적용 완료")).toBeInTheDocument();
    expect(screen.queryByText("요청 실패 (HTTP 0)")).toBeNull();
    expect(screen.queryByText("확인 불가")).toBeNull();
  });

  it("구성 오류(요청을 보내기 전)면 카드 상태를 그대로 두고 오류만 보인다", async () => {
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci).mockRejectedValue(
      new ApiConfigError("NEXT_PUBLIC_API_BASE 없음"),
    );
    render(<ThreePushParamCard />);
    await screen.findByText("일치 · 변경 없음");
    fireEvent.click(screen.getByRole("button", { name: "현재 기준 OCI 적용" }));
    expect(await screen.findByText("구성 오류: NEXT_PUBLIC_API_BASE 없음")).toBeInTheDocument();
    expect(screen.getByText("일치 · 변경 없음")).toBeInTheDocument();
    expect(screen.queryByText("확인 불가")).toBeNull();
  });

  it("적용 중에는 버튼이 막히고 문구가 바뀐다(두 번 누름 방지)", async () => {
    vi.mocked(fetchThreePushParamState).mockResolvedValue(APPLIED);
    vi.mocked(applyThreePushParamToOci).mockReturnValue(new Promise(() => undefined));
    render(<ThreePushParamCard />);
    await screen.findByText(APPLIED.display_label);
    fireEvent.click(screen.getByRole("button", { name: "현재 기준 OCI 적용" }));
    const busy = await screen.findByRole("button", { name: "적용 진행 중..." });
    expect(busy).toHaveProperty("disabled", true);
    // 첫 단계는 OCI 실제 활성값 읽기(같으면 바꾸지 않는다) — 예전 '운영 기준 생성 중' 이 아니다.
    expect(screen.getByText("진행 중: OCI 활성값 읽는 중")).toBeInTheDocument();
    fireEvent.click(busy);
    expect(applyThreePushParamToOci).toHaveBeenCalledTimes(1);
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
    ["active_same", "일치 · 변경 없음", "ok"],
    ["activated", "적용 완료", "ok"],
    ["failed", "적용 실패", "warn"],
    ["unconfirmed", "확인 불가", "unknown"],
    ["busy", "적용 중", "info"],
    ["verification_required", "확인 필요", "warn"],
    ["delivered_only", "이전 전달 기록", "unknown"],
    ["not_applied", "미적용", "unknown"],
  ] as const)("배지: %s → %s (%s)", async (status, label, tone) => {
    const { container } = await renderWith({ status });
    const badge = container.querySelector(".ops-card-head .oci-state");
    expect(badge?.textContent).toBe(label);
    expect(badge?.className).toBe(`oci-state ${tone}`);
  });

  it("예전 전달 기록은 '미적용'으로 단정하지 않는다(판정 §5)", async () => {
    const msg =
      "이전 전달 기록(2026-10-04 11:09) · 활성화 확인 없음. 지금 OCI 활성값과의 일치 여부는 위 ① '운영 기준 활성' 행에서 확인하세요.";
    const { container } = await renderWith({
      status: "delivered_only",
      applied_at: "2026-10-04 11:09",
      oci_verified: false,
      message: msg,
    });
    expect(rowValue(container, "OCI 적용")).toBe(msg);
    expect(container.textContent).not.toContain("미적용");
  });

  it("버튼은 하나 · 문구 '현재 기준 OCI 적용' · 눌러야만 적용 요청", async () => {
    await renderWith();
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(1);
    expect(buttons[0].textContent).toBe("현재 기준 OCI 적용");
    expect(applyThreePushParamToOci).not.toHaveBeenCalled();
  });
});
