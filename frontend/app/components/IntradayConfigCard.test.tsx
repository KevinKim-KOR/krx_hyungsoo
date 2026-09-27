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
  candidate_policy_enabled: false,
  candidate_policy_status: "NOT_CONFIGURED",
  policy_values: [
    { key: "drop_threshold_pct", value: -5.0 },
    { key: "surge_threshold_pct", value: 5.0 },
    { key: "cooldown_minutes", value: 120 },
    { key: "max_sends_per_day", value: 4 },
  ],
  policy_rule_version: "sector_rep.v1",
  deploy_status: null,
  deploy_error: null,
  action_state: "pending_approval",
  payload_error: null,
};

async function renderWith(state: Partial<IntradayConfigState> = {}) {
  vi.mocked(fetchIntradayConfigState).mockResolvedValue({ ...BASE, ...state });
  const r = render(<IntradayConfigCard />);
  // 2026-09-27: 「확인할 변경」이 행 이름(dt)에도 나와서 동작 제목(h3)으로 특정한다.
  await waitFor(() =>
    expect(screen.getByRole("heading", { name: "확인할 변경" })).toBeTruthy(),
  );
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
    expect(text).toContain("27개"); // 지켜보는 / 적용 예정 사업군
    // 2026-09-27: 사업군 수 · 대표 ETF 수 두 행을 한 행으로 합쳤다(사용자 지시).
    expect(text).toContain("27개 (사업군마다 대표 ETF 1종목)"); // 적용 예정 대표 ETF
    expect(text).toContain("2026-09-11"); // 자료 기준일
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

// ── 승인 대기 중인 **활성화 후보** (검증자 P1) ─────────────────────────────
//
// active 는 비활성인데 후보가 `enabled=true` 인 실제 상태다. 예전에는 API 가
// 후보 값을 `policy_enabled` 로 내려서, 승인 전인데도 「장중 알림 발송 중」 으로
// 보이고 정작 활성화 경고는 `!policy_enabled` 조건에 가려 숨었다.
describe("IntradayConfigCard — 활성화 후보 승인 대기", () => {
  const ENABLING: IntradayConfigState = {
    ...BASE,
    policy_enabled: false, // 지금은 꺼져 있다
    policy_status: "NOT_CONFIGURED",
    candidate_policy_enabled: true, // 적용하면 켜진다
    candidate_policy_status: "CONFIGURED",
  };

  async function renderEnabling() {
    vi.mocked(fetchIntradayConfigState).mockResolvedValue(ENABLING);
    const r = render(<IntradayConfigCard />);
    await screen.findByText("장중 급등락 설정");
    return r;
  }

  it("승인 전에는 '발송 중' 으로 표시하지 않는다", async () => {
    const { container } = await renderEnabling();
    const text = container.textContent ?? "";
    expect(text).toContain("구조 준비 완료 · 장중 알림 정책 설정 전");
    expect(text).not.toContain("장중 알림 발송 중");
  });

  it("적용 후 켜진다는 것을 따로 보여준다", async () => {
    const { container } = await renderEnabling();
    expect(container.textContent ?? "").toContain("장중 알림 발송 시작");
  });

  it("활성화 경고를 숨기지 않는다", async () => {
    const { container } = await renderEnabling();
    const text = container.textContent ?? "";
    expect(text).toContain("이 설정을 적용하면 장중 알림이 실제로 발송됩니다");
    expect(text).toContain("하루 최대 8건");
  });

  it("후보가 비활성이면 활성화 경고를 띄우지 않는다", async () => {
    vi.mocked(fetchIntradayConfigState).mockResolvedValue(BASE);
    const { container } = render(<IntradayConfigCard />);
    await screen.findByText("장중 급등락 설정");
    expect(container.textContent ?? "").not.toContain(
      "이 설정을 적용하면 장중 알림이 실제로 발송됩니다",
    );
  });
});

// ── 2026-09-27 사용자 직접 지시 — 배치 정리(배지 · 정렬 행 · 자세히 보기) ─────────
//
// 배치만 바꿨다. 위의 표시 계약(현재/후보 분리 · 승인 대기 금지 · 미확정 · h3 하나 ·
// 값 없음 표시 · 파생 키 숨김)은 그대로 위 test 들이 지킨다.
function rowValue(container: HTMLElement, label: string): string | null {
  const dt = Array.from(container.querySelectorAll("dt")).find(
    (d) => d.textContent === label,
  );
  return dt ? (dt.nextElementSibling?.textContent ?? null) : null;
}

function headBadge(container: HTMLElement): HTMLElement {
  return container.querySelector(".ops-card-head .oci-state") as HTMLElement;
}

const NO_CANDIDATE: Partial<IntradayConfigState> = {
  candidate_version_id: null,
  candidate_source_hash: null,
  candidate_data_asof: null,
  candidate_sector_count: 0,
  candidate_policy_enabled: null,
  candidate_policy_status: null,
  changes: [],
  action_state: null,
  deploy_status: "deployed",
};

async function renderNoCandidate(extra: Partial<IntradayConfigState> = {}) {
  vi.mocked(fetchIntradayConfigState).mockResolvedValue({
    ...BASE,
    ...NO_CANDIDATE,
    ...extra,
  });
  const r = render(<IntradayConfigCard />);
  await screen.findByText("확인할 변경이 없습니다.");
  return r;
}

describe("IntradayConfigCard — 배치 정리 (2026-09-27)", () => {
  it("제목 옆 배지는 **지금** 상태다 — 후보가 알림을 켜도 배지는 켜지지 않는다", async () => {
    vi.mocked(fetchIntradayConfigState).mockResolvedValue({
      ...BASE,
      policy_enabled: false,
      policy_status: "NOT_CONFIGURED",
      candidate_policy_enabled: true,
      candidate_policy_status: "CONFIGURED",
    });
    const { container } = render(<IntradayConfigCard />);
    await screen.findByRole("heading", { name: "확인할 변경" });
    const badge = headBadge(container);
    expect(badge.textContent).toBe("구조 준비 완료 · 장중 알림 정책 설정 전");
    expect(badge.className).toContain("unknown");
    expect(badge.className).not.toContain("ok");
    // 켜진다는 사실은 배지가 아니라 「적용 후 상태」 행이 말한다.
    expect(rowValue(container, "적용 후 상태")).toBe("장중 알림 발송 시작");
  });

  it("지금 켜져 있으면 배지가 '장중 알림 발송 중' (ok)", async () => {
    const { container } = await renderNoCandidate({
      policy_enabled: true,
      policy_status: "CONFIGURED",
    });
    const badge = headBadge(container);
    expect(badge.textContent).toBe("장중 알림 발송 중");
    expect(badge.className).toContain("ok");
  });

  it("후보가 있으면 '적용 예정 사업군' · 없으면 '지켜보는 사업군'", async () => {
    const withCand = await renderWith();
    expect(rowValue(withCand.container, "적용 예정 사업군")).toBe(
      "27개 (사업군마다 대표 ETF 1종목)",
    );
    expect(rowValue(withCand.container, "지켜보는 사업군")).toBeNull();
    expect(rowValue(withCand.container, "자료 기준일")).toBe("2026-09-11");
    cleanup();

    const noCand = await renderNoCandidate();
    expect(rowValue(noCand.container, "지켜보는 사업군")).toBe(
      "26개 (사업군마다 대표 ETF 1종목)",
    );
    expect(rowValue(noCand.container, "적용 예정 사업군")).toBeNull();
    expect(rowValue(noCand.container, "자료 기준일")).toBe("2026-09-10");
    // 후보가 없으면 「적용 후 상태」 행이 없다.
    expect(rowValue(noCand.container, "적용 후 상태")).toBeNull();
  });

  it("설정 버전 · 확인값 · 산출 규칙만 「자세히 보기」 안에 있고 기본은 접혀 있다", async () => {
    const { container } = await renderWith();
    const details = container.querySelector("details") as HTMLDetailsElement;
    expect(details).not.toBeNull();
    expect(details.open).toBe(false);
    expect(details.querySelector("summary")?.textContent).toBe(
      "자세히 보기 (설정 버전 · 확인값 · 산출 규칙)",
    );
    const inside = Array.from(details.querySelectorAll("dt")).map((d) => d.textContent);
    expect(inside).toEqual(["설정 버전", "확인값", "산출 규칙"]);
    expect(rowValue(details, "설정 버전")).toBe("intraday-20260916T124928-439563");
    expect(rowValue(details, "확인값")).toBe(`${"b".repeat(12)}…`);
    expect(rowValue(details, "산출 규칙")).toBe("sector_rep.v1");
    // 판단에 쓰는 행은 접힌 영역 밖이다.
    for (const label of ["적용 예정 사업군", "자료 기준일", "OCI 반영", "확인할 변경"]) {
      const dt = Array.from(container.querySelectorAll("dt")).find(
        (d) => d.textContent === label,
      );
      expect(dt?.closest("details")).toBeNull();
    }
  });

  it("판정 기준 값은 펼치지 않아도 보인다 · 파생 키 숨김 · 값 없음은 '없음'", async () => {
    const { container } = await renderWith({
      policy_values: [
        { key: "drop_threshold_pct", value: -5.0 },
        { key: "cooldown_minutes", value: 120 },
        { key: "dedup_window_minutes", value: 120 },
        { key: "max_sends_per_run", value: 1 },
        { key: "max_sends_per_day", value: null },
      ],
    });
    const drop = screen.getByText("보유 급락 기준", { selector: "dt" });
    expect(drop.closest("details")).toBeNull();
    expect(drop).toBeVisible();
    expect(rowValue(container, "보유 급락 기준")).toBe("-5%");
    expect(rowValue(container, "재발송 대기")).toBe("120분");
    expect(rowValue(container, "하루 최대")).toBe("없음");
    const text = container.textContent ?? "";
    expect(screen.queryByText("중복 억제 창", { selector: "dt" })).toBeNull();
    expect(screen.queryByText("회차당 최대", { selector: "dt" })).toBeNull();
    expect(text).toContain("중복 억제 창은 재발송 대기와 같은 값이고");
  });

  it("「확인할 변경」 행: 후보 없음 → 없음 · 바뀐 사업군 n → n건 · 첫 설정/변경 0 → 있음", async () => {
    const two = await renderWith();
    expect(rowValue(two.container, "확인할 변경")).toBe("2건");
    cleanup();

    const empty = await renderWith({ changes: [] });
    expect(rowValue(empty.container, "확인할 변경")).toBe("있음");
    expect(empty.container.textContent ?? "").toContain(
      "직전 승인본과 달라진 사업군이 없습니다.",
    );
    cleanup();

    const first = await renderWith({ active_version_id: null });
    expect(rowValue(first.container, "확인할 변경")).toBe("있음");
    expect(first.container.textContent ?? "").toContain("첫 설정입니다.");
    cleanup();

    const none = await renderNoCandidate();
    expect(rowValue(none.container, "확인할 변경")).toBe("없음");
    // 후보가 없으면 동작 제목 · 버튼이 없다.
    expect(none.container.querySelectorAll("h3").length).toBe(0);
    expect(none.container.querySelectorAll("button").length).toBe(0);
  });

  it("「OCI 반영」 은 배지로 보이고 문구는 그대로다", async () => {
    const { container } = await renderWith({ deploy_status: null });
    expect(rowValue(container, "OCI 반영")).toBe("아직 적용하지 않음");
    cleanup();
    const done = await renderNoCandidate({ deploy_status: "deployed" });
    expect(rowValue(done.container, "OCI 반영")).toBe("적용 완료");
  });
});

describe("IntradayConfigCard — 합친 화면 보완 (2026-09-27 검토 반영)", () => {
  it("후보가 있으면 '지금 알림 상태' 와 '적용 후 상태' 를 글로 나란히 보인다", async () => {
    const { container } = await renderWith({
      policy_enabled: false,
      policy_status: "NOT_CONFIGURED",
      candidate_policy_enabled: true,
      candidate_policy_status: "CONFIGURED",
    });
    expect(rowValue(container, "지금 알림 상태")).toBe(
      "구조 준비 완료 · 장중 알림 정책 설정 전",
    );
    expect(rowValue(container, "적용 후 상태")).toBe("장중 알림 발송 시작");
  });

  it("후보가 없으면 '지금 알림 상태' 행을 따로 두지 않는다(배지로 충분)", async () => {
    const { container } = await renderNoCandidate({ policy_enabled: true });
    expect(rowValue(container, "지금 알림 상태")).toBeNull();
    expect(headBadge(container).textContent).toBe("장중 알림 발송 중");
  });

  it("재시도 · 미확정(승인 기록됨)에는 '확인할 변경' 행이 없다", async () => {
    vi.mocked(fetchIntradayConfigState).mockResolvedValue({
      ...BASE,
      action_state: "approved_not_deployed",
      deploy_status: "scp_failed",
      deploy_error: "boom",
    });
    const retry = render(<IntradayConfigCard />);
    await screen.findByRole("heading", { name: "적용하지 못한 설정" });
    expect(rowValue(retry.container, "확인할 변경")).toBeNull();
    cleanup();

    vi.mocked(fetchIntradayConfigState).mockResolvedValue({
      ...BASE,
      action_state: "approved_not_deployed",
      deploy_status: "deploy_unconfirmed",
    });
    const unconf = render(<IntradayConfigCard />);
    await screen.findByRole("heading", { name: "OCI 적용 여부 확인 필요" });
    expect(rowValue(unconf.container, "확인할 변경")).toBeNull();
    // 동작 제목(h3)은 여전히 하나다.
    expect(unconf.container.querySelectorAll("h3")).toHaveLength(1);
  });

  it("카드 제목은 화면 ② 섹션 아래 3단계 제목이다(h3 요소는 늘리지 않음)", async () => {
    const { container } = await renderWith();
    expect(
      screen.getByRole("heading", { level: 3, name: "장중 급등락 설정" }),
    ).toBeTruthy();
    expect(Array.from(container.querySelectorAll("h3")).map((h) => h.textContent)).toEqual([
      "확인할 변경",
    ]);
  });
});
