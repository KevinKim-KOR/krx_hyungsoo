// POC3-02C-OPS-01 — 장중 급등락 설정 카드 표시 계약.
//
// 기존 ApprovalTelegramView.test.tsx 는 API 가 실패해 카드가 "불러오는 중" 으로
// 렌더되는 상태에서만 통과했다. 그러면 **데이터가 실제로 들어온 화면의 계약이
// 검사되지 않는다.** 여기서는 state 를 실제로 채워 렌더한다.
//
// POC6-34 (PLAN V1 O8 ~ O12 · Q5 · Q6 · Q10): 배지 · 후보 문구 = PC 에 기록된 설정 상태 ·
// 조회 실패 분기 · 날짜 이름 · 판정 기준 표(늘 펼침 · 세 묶음 · 4열) · 켜짐 변화 차이.
// 값은 모두 합성 고정값이다(보유 종목 · 금액 없음).

import { afterEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";

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

import {
  approveAndApplyIntradayConfig,
  fetchIntradayConfigState,
} from "@/lib/api/intradayConfig";

// 설계 고정값(`CONFIRMED_POLICY`)과 같은 12개 — 응답 순서(REQUIRED_POLICY_KEYS) 그대로.
const CONFIRMED_VALUES: IntradayConfigState["policy_values"] = [
  { key: "surge_threshold_pct", value: 5.0 },
  { key: "drop_threshold_pct", value: -5.0 },
  { key: "cooldown_minutes", value: 120 },
  { key: "dedup_window_minutes", value: 120 },
  { key: "max_sends_per_run", value: 1 },
  { key: "max_sends_per_day", value: 4 },
  { key: "sector_entry_min_pct", value: 1.5 },
  { key: "sector_chase_pct", value: 4.0 },
  { key: "sector_avoid_drop_pct", value: -1.5 },
  { key: "sector_rank_top_pct", value: 20.0 },
  { key: "max_items_per_section", value: 3 },
  { key: "sector_min_coverage_pct", value: 80.0 },
];

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
  policy_values: CONFIRMED_VALUES,
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
  it("깨진 설정을 '0개' 로 그리지 않고 읽지 못했다고 말한다 · 배지는 확인 불가", async () => {
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
    // POC6-34 Q5 — 설정 손상은 설정 상태를 확인할 수 없는 경우다.
    expect(headBadge(container).textContent).toBe(
      "PC 기록 기준 · 장중 알림 설정 확인 불가",
    );
    expect(headBadge(container).className).toContain("unknown");
    expect(container.querySelector("table")).toBeNull();
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
    // 정책 키 이름도 화면에 나오지 않는다.
    for (const p of CONFIRMED_VALUES) expect(text).not.toContain(p.key);
  });

  it("'승인 대기' 문구를 쓰지 않는다 (승인·적용 화면 기존 계약)", async () => {
    const { container } = await renderWith();
    expect(container.textContent ?? "").not.toContain("승인 대기");
  });

  it("enabled=false·정책 미설정을 오류로 표현하지 않는다", async () => {
    const { container } = await renderWith();
    const text = container.textContent ?? "";
    expect(text).toContain("PC 기록 기준 · 장중 알림 정책 미설정");
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
    expect(text).toContain("2026-09-11"); // 대표 ETF 선정에 사용한 종가일
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
// 후보 값을 `policy_enabled` 로 내려서, 승인 전인데도 켜진 것처럼 보이고 정작
// 활성화 경고는 `!policy_enabled` 조건에 가려 숨었다.
describe("IntradayConfigCard — 활성화 후보 승인 대기", () => {
  const ENABLING: IntradayConfigState = {
    ...BASE,
    policy_enabled: false, // 지금은 꺼져 있다
    policy_status: "NOT_CONFIGURED",
    candidate_policy_enabled: true, // 승인하면 켜진다
    candidate_policy_status: "CONFIGURED",
  };

  async function renderEnabling() {
    vi.mocked(fetchIntradayConfigState).mockResolvedValue(ENABLING);
    const r = render(<IntradayConfigCard />);
    await screen.findByRole("heading", { name: "확인할 변경" });
    return r;
  }

  it("승인 전에는 '켜짐' 으로 표시하지 않는다 · '발송 중 / 발송 시작' 문구가 없다", async () => {
    const { container } = await renderEnabling();
    const text = container.textContent ?? "";
    expect(headBadge(container).textContent).toBe("PC 기록 기준 · 장중 알림 정책 미설정");
    expect(text).not.toContain("PC 기록 기준 · 장중 알림 설정 켜짐");
    expect(text).not.toContain("발송 중");
    expect(text).not.toContain("발송 시작");
  });

  it("승인 후 켜진다는 것을 따로 보여준다", async () => {
    const { container } = await renderEnabling();
    expect(rowValue(container, "승인 후 장중 알림 설정")).toBe(
      "켜짐 (지금 꺼짐 → 켜짐)",
    );
  });

  it("활성화 경고를 숨기지 않는다", async () => {
    const { container } = await renderEnabling();
    const text = container.textContent ?? "";
    // 설계자 RESULT 판정 C7(2026-11-19 · 형수님 결정 — 경고는 표 아래라 '위 표의').
    expect(text).toContain(
      "이 설정을 승인하면 장중 알림 설정이 켜집니다. 발송 조건을 충족한 장중 알림에는 위 표의 하루 최대 한도가 적용됩니다.",
    );
    expect(text).not.toContain("실제로 발송됩니다");
  });

  it("후보가 비활성이면 활성화 경고를 띄우지 않는다", async () => {
    vi.mocked(fetchIntradayConfigState).mockResolvedValue(BASE);
    const { container } = render(<IntradayConfigCard />);
    await screen.findByRole("heading", { name: "확인할 변경" });
    expect(container.textContent ?? "").not.toContain("이 설정을 승인하면");
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

// 판정 기준 표의 한 행 — [항목, 설정값, 무엇을 보는지, 이 값의 뜻].
function criteriaRow(container: HTMLElement, label: string): string[] | null {
  const tr = Array.from(container.querySelectorAll("table.ops-criteria tbody tr")).find(
    (r) => r.querySelector("td")?.textContent === label,
  );
  return tr ? Array.from(tr.querySelectorAll("td")).map((td) => td.textContent ?? "") : null;
}

// 판정 기준 표 바로 아래 각주 문단의 글.
function footnoteText(container: HTMLElement): string | null {
  return container.querySelector("table.ops-criteria")?.nextElementSibling?.textContent ?? null;
}

const FOOTNOTE_TAIL =
  "위 등락률 기준은 알림 후보를 고르는 조건이며, 실제 발송에는 보유 종목 제외 · 조회 성공률 · 재발송 대기 · 구역별 최대 · 하루 최대가 함께 적용됩니다(보유 급락은 같은 날 더 나쁜 구간으로 내려갈 때만 다시 알림).";
// 회차당 최대가 확인될 때(기존 각주 그대로) · 값이 없을 때(설계자 RESULT 판정 C9 · 형수님 결정 U3).
const KNOWN_FOOTNOTE = `중복 억제 창은 재발송 대기와 같은 값만 저장되는 다른 이름이라 따로 동작하지 않고, 회차당 최대 1건은 한 점검 회차가 알림 메시지를 하나만 만드는 구조에서 나온 고정값입니다. ${FOOTNOTE_TAIL}`;
const C9_MISSING_FOOTNOTE = `중복 억제 창은 재발송 대기와 같은 값만 저장되는 다른 이름이라 따로 동작하지 않습니다. 회차당 최대 건수는 이 설정에서 확인할 수 없습니다. ${FOOTNOTE_TAIL}`;

// POC6-34 r1 R1-F1 — 보유 급등 · 급락 행의 '이 값의 뜻'은 저장값이 아니라 프로그램에 고정된 경계로
// 만든다(저장값이 고정 경계와 같거나 없으면 이 문장 그대로 · 다르면 '다릅니다' 한 문장이 붙음).
const SURGE_FIXED_MEANING =
  "실행 코드는 이 설정값을 읽지 않고, 프로그램에 고정된 +5% 이상(+5 ~ +7% · +7 ~ +10% · +10% 이상)으로 판정합니다. 오늘 +5.2%인 보유 종목은 급등 후보가 됩니다(정확히 +5.0% 포함 · +4.9% 해당 없음).";
const DROP_FIXED_MEANING =
  "실행 코드는 이 설정값을 읽지 않고, 프로그램에 고정된 -5% 이하(-5 ~ -7% · -7 ~ -10% · -10% 이하)로 판정합니다. 오늘 -5.2%인 보유 종목은 급락 후보가 됩니다(정확히 -5.0% 포함 · -4.9% 해당 없음).";

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
    expect(badge.textContent).toBe("PC 기록 기준 · 장중 알림 정책 미설정");
    expect(badge.className).toContain("unknown");
    expect(badge.className).not.toContain("ok");
    // 켜진다는 사실은 배지가 아니라 「승인 후 장중 알림 설정」 행이 말한다.
    expect(rowValue(container, "승인 후 장중 알림 설정")).toBe("켜짐 (지금 꺼짐 → 켜짐)");
  });

  it("지금 켜져 있으면 배지가 'PC 기록 기준 · 장중 알림 설정 켜짐' (ok)", async () => {
    const { container } = await renderNoCandidate({
      policy_enabled: true,
      policy_status: "CONFIGURED",
    });
    const badge = headBadge(container);
    expect(badge.textContent).toBe("PC 기록 기준 · 장중 알림 설정 켜짐");
    expect(badge.className).toContain("ok");
  });

  it("후보가 있으면 '적용 예정 사업군' · 없으면 '지켜보는 사업군'", async () => {
    const withCand = await renderWith();
    expect(rowValue(withCand.container, "적용 예정 사업군")).toBe(
      "27개 (사업군마다 대표 ETF 1종목)",
    );
    expect(rowValue(withCand.container, "지켜보는 사업군")).toBeNull();
    expect(rowValue(withCand.container, "대표 ETF 선정에 사용한 종가일")).toBe("2026-09-11");
    cleanup();

    const noCand = await renderNoCandidate();
    expect(rowValue(noCand.container, "지켜보는 사업군")).toBe(
      "26개 (사업군마다 대표 ETF 1종목)",
    );
    expect(rowValue(noCand.container, "적용 예정 사업군")).toBeNull();
    expect(rowValue(noCand.container, "대표 ETF 선정에 사용한 종가일")).toBe("2026-09-10");
    // 후보가 없으면 「승인 후 장중 알림 설정」 행이 없다.
    expect(rowValue(noCand.container, "승인 후 장중 알림 설정")).toBeNull();
  });

  it("설정 버전 · 확인값 · 산출 규칙만 「자세히 보기」 안에 있고 기본은 접혀 있다", async () => {
    const { container } = await renderWith();
    const details = container.querySelector("details") as HTMLDetailsElement;
    expect(details).not.toBeNull();
    expect(container.querySelectorAll("details")).toHaveLength(1);
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
    for (const label of [
      "적용 예정 사업군",
      "대표 ETF 선정에 사용한 종가일",
      "OCI 반영",
      "확인할 변경",
    ]) {
      const dt = Array.from(container.querySelectorAll("dt")).find(
        (d) => d.textContent === label,
      );
      expect(dt).toBeTruthy();
      expect(dt?.closest("details")).toBeNull();
    }
    // 판정 기준 표도 접힌 영역에 없다.
    expect(details.querySelector("table")).toBeNull();
  });

  it("판정 기준 값은 펼치지 않아도 보인다 · 파생 키 숨김 · 값 없음은 '확인 불가'", async () => {
    const { container } = await renderWith({
      policy_values: [
        { key: "drop_threshold_pct", value: -5.0 },
        { key: "cooldown_minutes", value: 120 },
        { key: "dedup_window_minutes", value: 120 },
        { key: "max_sends_per_run", value: 1 },
        { key: "max_sends_per_day", value: null },
      ],
    });
    const drop = screen.getByText("보유 급락 기준", { selector: "td" });
    expect(drop.closest("details")).toBeNull();
    expect(drop).toBeVisible();
    expect(criteriaRow(container, "보유 급락 기준")?.[1]).toBe("-5%");
    expect(criteriaRow(container, "재발송 대기")?.[1]).toBe("120분");
    expect(criteriaRow(container, "하루 최대")?.slice(1)).toEqual([
      "확인 불가",
      "같은 날(한국 시각) 장중 급등락 알림 메시지를 끝까지 보낸 횟수를 셉니다. 종목 수가 아니라 메시지 수이며, 정해진 시각에 나가는 정기 알림은 세지 않습니다.",
      "확인 불가",
    ]);
    // 응답에 아예 없는 키도 행은 있고 값은 '확인 불가'다(늘 펼침).
    expect(criteriaRow(container, "보유 급등 기준")?.[1]).toBe("확인 불가");
    const text = container.textContent ?? "";
    expect(screen.queryByText("중복 억제 창", { selector: "td" })).toBeNull();
    expect(screen.queryByText("회차당 최대", { selector: "td" })).toBeNull();
    expect(text).toContain("중복 억제 창은 재발송 대기와 같은 값만 저장되는 다른 이름이라");
    expect(text).toContain("회차당 최대 1건은 한 점검 회차가");
  });

  it("「확인할 변경」 행: 후보 없음 → 없음 · 바뀐 사업군 n → n건 · 첫 설정 → 있음 · 차이 0 → 비교할 수 없는 차이", async () => {
    const two = await renderWith();
    expect(rowValue(two.container, "확인할 변경")).toBe("2건");
    cleanup();

    const empty = await renderWith({ changes: [] });
    expect(rowValue(empty.container, "확인할 변경")).toBe(
      "있음 (이 화면에서 비교할 수 없는 차이)",
    );
    expect(empty.container.textContent ?? "").toContain(
      "직전 승인본과 달라진 사업군 · 장중 알림 설정이 없습니다. 판정 기준값 · 대체 ETF 의 차이는 이 화면에서 비교할 수 없습니다.",
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
  it("후보가 있으면 '지금 알림 상태' 와 '승인 후 장중 알림 설정' 을 글로 나란히 보인다", async () => {
    const { container } = await renderWith({
      policy_enabled: false,
      policy_status: "NOT_CONFIGURED",
      candidate_policy_enabled: true,
      candidate_policy_status: "CONFIGURED",
    });
    expect(rowValue(container, "지금 알림 상태")).toBe(
      "PC 기록 기준 · 장중 알림 정책 미설정",
    );
    expect(rowValue(container, "승인 후 장중 알림 설정")).toBe("켜짐 (지금 꺼짐 → 켜짐)");
  });

  it("후보가 없으면 '지금 알림 상태' 행을 따로 두지 않는다(배지로 충분)", async () => {
    const { container } = await renderNoCandidate({ policy_enabled: true });
    expect(rowValue(container, "지금 알림 상태")).toBeNull();
    expect(headBadge(container).textContent).toBe("PC 기록 기준 · 장중 알림 설정 켜짐");
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

// ── POC6-34 — 설정 상태 문구 · 조회 실패 · 판정 기준 표 · 후보 차이 ─────────────────
const BADGE_TITLE =
  "장중 알림 설정 (PC 에 기록된 활성 설정 · 실제 발송은 Telegram 에서 확인)";

describe("IntradayConfigCard — POC6-34 배지 = PC 에 기록된 설정 상태 (Q5 · I-13)", () => {
  // 활성 버전이 있는 응답(BASE)이다. 상태 null 두 줄은 설계자 RESULT 판정 C8(2026-11-19)로 '정책 상태 확인 불가'가
  // 붙고 회색이다(전에는 '켜짐'(ok) · '꺼짐').
  it.each([
    [true, "CONFIGURED", "PC 기록 기준 · 장중 알림 설정 켜짐", "ok"],
    [true, null, "PC 기록 기준 · 장중 알림 설정 켜짐 · 정책 상태 확인 불가", "unknown"],
    [false, "CONFIGURED", "PC 기록 기준 · 장중 알림 설정 꺼짐", "unknown"],
    [false, null, "PC 기록 기준 · 장중 알림 설정 꺼짐 · 정책 상태 확인 불가", "unknown"],
    [false, "NOT_CONFIGURED", "PC 기록 기준 · 장중 알림 정책 미설정", "unknown"],
  ])("enabled=%s · status=%s → '%s' (%s)", async (enabled, status, label, tone) => {
    const { container } = await renderNoCandidate({
      policy_enabled: enabled,
      policy_status: status,
    });
    const badge = headBadge(container);
    expect(badge.textContent).toBe(label);
    expect(badge.className).toBe(`oci-state ${tone}`);
    expect(badge.getAttribute("title")).toBe(BADGE_TITLE);
    expect(container.textContent ?? "").not.toContain("발송 중");
  });

  it("응답 전에는 '불러오는 중...' · 배지 없음", async () => {
    vi.mocked(fetchIntradayConfigState).mockReturnValue(new Promise(() => {}));
    const { container } = render(<IntradayConfigCard />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(container.textContent ?? "").toContain("불러오는 중...");
    expect(headBadge(container)).toBeNull();
  });

  it("조회 실패는 '불러오는 중' 과 구분한다 — 값 없이 확인 불가", async () => {
    vi.mocked(fetchIntradayConfigState).mockRejectedValue(new Error("HTTP 500"));
    const { container } = render(<IntradayConfigCard />);
    expect(
      await screen.findByText("장중 급등락 설정을 불러오지 못했습니다."),
    ).toBeTruthy();
    const text = container.textContent ?? "";
    expect(text).not.toContain("불러오는 중");
    expect(headBadge(container).textContent).toBe("PC 기록 기준 · 장중 알림 설정 확인 불가");
    expect(headBadge(container).className).toBe("oci-state unknown");
    expect(headBadge(container).getAttribute("title")).toBe(BADGE_TITLE);
    // 값을 지어내지 않는다 — 표 · 행 · 버튼 없음.
    expect(container.querySelector("table")).toBeNull();
    expect(container.querySelectorAll("dt")).toHaveLength(0);
    expect(container.querySelectorAll("button")).toHaveLength(0);
    expect(screen.getByRole("region", { name: "장중 급등락 설정" })).toBeTruthy();
  });

  it("승인 뒤 다시 읽기가 실패해도 직전 동작 안내는 보인다", async () => {
    vi.mocked(fetchIntradayConfigState)
      .mockResolvedValueOnce(BASE)
      .mockRejectedValue(new Error("HTTP 500"));
    vi.mocked(approveAndApplyIntradayConfig).mockResolvedValue({
      ok: true,
      config_version_id: BASE.candidate_version_id as string,
      deploy_status: "deployed",
      message: "승인 후 OCI 적용 완료",
    });
    render(<IntradayConfigCard />);
    await screen.findByRole("heading", { name: "확인할 변경" });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "승인하고 OCI 적용" }));
    });
    expect(
      await screen.findByText("장중 급등락 설정을 불러오지 못했습니다."),
    ).toBeTruthy();
    expect(screen.getByText("승인 후 OCI 적용 완료")).toBeTruthy();
    expect(approveAndApplyIntradayConfig).toHaveBeenCalledTimes(1);
  });
});

describe("IntradayConfigCard — POC6-34 후보 쪽 문구 = 설정 상태 (I-14)", () => {
  it.each([
    [true, true, "켜짐 (지금과 같음)", false],
    [false, true, "켜짐 (지금 꺼짐 → 켜짐)", true],
    [true, false, "꺼짐 (지금 켜짐 → 꺼짐)", false],
    [false, false, "꺼짐 (지금과 같음)", false],
  ])("지금 %s · 후보 %s → '%s' · 경고 %s", async (nowOn, candOn, label, warn) => {
    const { container } = await renderWith({
      policy_enabled: nowOn,
      policy_status: "CONFIGURED",
      candidate_policy_enabled: candOn,
      candidate_policy_status: "CONFIGURED",
    });
    expect(rowValue(container, "승인 후 장중 알림 설정")).toBe(label);
    expect(rowValue(container, "적용 후 상태")).toBeNull();
    expect(rowValue(container, "지금 알림 상태")).toBe(headBadge(container).textContent);
    const text = container.textContent ?? "";
    expect(text.includes("이 설정을 승인하면 장중 알림 설정이 켜집니다.")).toBe(warn);
    expect(text).not.toContain("발송 시작");
  });

  // POC6-34 검증자 r1 R1-F3 — 후보 정책에서 켜짐 여부를 읽지 못하면 행을 숨기지 않고
  // '확인 불가'로 쓴다('꺼짐'으로 읽지 않는다). 제목 옆 배지는 그대로 **지금** 상태다.
  it.each([
    [false, "NOT_CONFIGURED", "PC 기록 기준 · 장중 알림 정책 미설정"],
    [true, "CONFIGURED", "PC 기록 기준 · 장중 알림 설정 켜짐"],
  ])(
    "후보의 켜짐 여부가 없으면(null) '승인 후 장중 알림 설정' = '확인 불가' · 지금 %s",
    async (nowOn, nowStatus, badge) => {
      const { container } = await renderWith({
        policy_enabled: nowOn,
        policy_status: nowStatus,
        candidate_policy_enabled: null,
        candidate_policy_status: null,
      });
      expect(rowValue(container, "승인 후 장중 알림 설정")).toBe("확인 불가");
      expect(headBadge(container).textContent).toBe(badge);
      expect(rowValue(container, "지금 알림 상태")).toBe(badge);
      const text = container.textContent ?? "";
      expect(text).not.toContain("이 설정을 승인하면");
      // 켜짐 변화는 비교하지 못했다 — 변경 목록 · 건수에 넣지 않는다.
      expect(text).not.toContain("장중 알림 설정: ");
      expect(rowValue(container, "확인할 변경")).toBe("2건");
    },
  );

  it("후보의 켜짐 여부가 없고 바뀐 사업군도 없으면 '장중 알림 설정이 없습니다'라고 쓰지 않는다", async () => {
    const { container } = await renderWith({
      changes: [],
      candidate_policy_enabled: null,
      candidate_policy_status: null,
    });
    const text = container.textContent ?? "";
    expect(text).not.toContain("장중 알림 설정이 없습니다");
    expect(text).toContain(
      "직전 승인본과 달라진 사업군이 없습니다. 승인할 설정의 장중 알림 켜짐 여부는 확인할 수 없습니다. 판정 기준값 · 대체 ETF 의 차이는 이 화면에서 비교할 수 없습니다.",
    );
    expect(rowValue(container, "확인할 변경")).toBe("있음 (이 화면에서 비교할 수 없는 차이)");
  });

  it("날짜 이름은 '대표 ETF 선정에 사용한 종가일' · 값이 없으면 '—'", async () => {
    const { container } = await renderNoCandidate({ active_data_asof: null });
    expect(rowValue(container, "대표 ETF 선정에 사용한 종가일")).toBe("—");
    expect(rowValue(container, "자료 기준일")).toBeNull();
    expect(container.textContent ?? "").not.toContain("자료 기준일");
  });
});

describe("IntradayConfigCard — POC6-34 판정 기준 표 (Q6 · 늘 펼침 · O10 · O11)", () => {
  it("후보가 없으면 제목 'PC에 기록된 적용 기준' · 한 줄 설명 · 세 묶음 · 4열", async () => {
    const { container } = await renderNoCandidate({
      policy_enabled: true,
      policy_status: "CONFIGURED",
      active_sector_count: 27,
    });
    const text = container.textContent ?? "";
    expect(text).toContain("PC에 기록된 적용 기준");
    expect(text).not.toContain("승인 시 적용될 기준");
    expect(text).not.toContain("적용될 판정 기준");
    // 설계자 RESULT 판정 C5(2026-11-19).
    expect(text).toContain(
      "사업군 판정과 발송 조건은 설정 버전에서 확인합니다. 보유 급등·급락 판정에는 프로그램의 고정 경계를 적용합니다. PC 가 계산하는 것은 사업군 · 대표 ETF 목록(시가총액 순)입니다. 여기서 하나씩 고치지 않고 버전 전체를 승인합니다.",
    );
    const table = screen.getByRole("table", { name: "PC에 기록된 적용 기준" });
    expect(table.closest("details")).toBeNull();
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((h) => h.textContent),
    ).toEqual(["항목", "설정값", "무엇을 보는지", "이 값의 뜻"]);
    expect(
      Array.from(table.querySelectorAll("tr.ops-criteria-group th")).map((h) => h.textContent),
    ).toEqual(["보유 종목 급등락", "사업군 대표 ETF 검토", "발송 한도와 자료 조건"]);
    // 각 묶음의 행 순서.
    const bodies = Array.from(table.querySelectorAll("tbody")).map((b) =>
      Array.from(b.querySelectorAll("td.oci-table-item")).map((td) => td.textContent),
    );
    expect(bodies).toEqual([
      ["보유 급등 기준", "보유 급락 기준"],
      ["진입 검토 하한", "추격 주의 기준", "진입 회피 기준", "순위 조건"],
      ["재발송 대기", "하루 최대", "구역별 최대", "최소 조회 성공률"],
    ]);
    // 지금 값(활성 27개) 문장 — 순위 · 조회 성공률은 실제 범위와 함께 읽힌다.
    expect(criteriaRow(container, "순위 조건")?.[3]).toBe(
      "27개 사업군이 모두 읽히면 27×20%=5.4에서 소수점을 버려 오른 쪽 5개, 내린 쪽 5개가 순위 조건을 충족합니다. 22개만 읽히면 4개씩입니다. 21개 이하로 읽히면 조회 성공률 80%에 못 미쳐 순위를 매기지 않습니다.",
    );
    expect(criteriaRow(container, "최소 조회 성공률")?.[3]).toBe(
      "27개 사업군 중 22개 이상(81.5%)을 읽으면 사업군 판정을 하고, 21개(77.8%) 이하이면 그 회차의 「신규 진입 검토」와 「진입 회피」 구역을 모두 뺍니다. 보유 종목 급등락 알림은 그대로 판정합니다.",
    );
    expect(criteriaRow(container, "보유 급락 기준")).toEqual([
      "보유 급락 기준",
      "-5%",
      "보유 종목의 오늘 등락률을 봅니다. 직전 거래일 종가 대비 값을 소수 첫째 자리로 반올림해서 씁니다.",
      DROP_FIXED_MEANING,
    ]);
    expect(criteriaRow(container, "보유 급등 기준")?.[3]).toBe(SURGE_FIXED_MEANING);
    // 모든 값 옆에 판정 대상과 해석이 있다(값 있는 10행 모두 '확인 불가' 아님).
    const rows = Array.from(table.querySelectorAll("tbody tr:not(.ops-criteria-group)"));
    expect(rows).toHaveLength(10);
    for (const tr of rows) {
      const cells = Array.from(tr.querySelectorAll("td")).map((td) => td.textContent ?? "");
      expect(cells).toHaveLength(4);
      expect(cells.slice(1).every((c) => c.length > 0 && c !== "확인 불가")).toBe(true);
    }
    // 이 표에는 입력란이 없다(읽기 전용).
    expect(table.querySelectorAll("input, select, textarea, button")).toHaveLength(0);
  });

  it("좁은 화면용 작은 머리(무엇을 보는지 · 이 값의 뜻)가 두 문장 칸에 붙어 있다", async () => {
    const { container } = await renderWith();
    const rows = Array.from(
      container.querySelectorAll("table.ops-criteria tbody tr:not(.ops-criteria-group)"),
    );
    expect(rows.length).toBe(10);
    for (const tr of rows) {
      const tds = Array.from(tr.querySelectorAll("td"));
      expect(tds.map((td) => td.getAttribute("data-label"))).toEqual([
        null,
        null,
        "무엇을 보는지",
        "이 값의 뜻",
      ]);
      expect(tds[1].className).toBe("ops-criteria-value");
    }
  });

  it("후보 값이 활성과 다르면 제목 · 값 · 문장이 모두 후보(같은 응답)를 가리킨다", async () => {
    const candidateValues = CONFIRMED_VALUES.map((p) =>
      p.key === "sector_rank_top_pct"
        ? { key: p.key, value: 25 }
        : p.key === "sector_min_coverage_pct"
          ? { key: p.key, value: 90 }
          : p.key === "max_items_per_section"
            ? { key: p.key, value: 4 }
            : p,
    );
    const { container } = await renderWith({
      active_sector_count: 27,
      candidate_sector_count: 20,
      policy_values: candidateValues,
    });
    const text = container.textContent ?? "";
    expect(text).toContain("승인 시 적용될 기준");
    expect(text).not.toContain("PC에 기록된 적용 기준");
    expect(screen.getByRole("table", { name: "승인 시 적용될 기준" })).toBeTruthy();
    expect(criteriaRow(container, "순위 조건")?.slice(1)).toEqual([
      "25%",
      "오늘 등락률을 읽은 사업군 대표 ETF(대표를 못 읽으면 대체 ETF)를 등락률로 줄 세운 순위를 봅니다. 많이 오른 쪽 위 25%는 신규 진입 검토에, 많이 내린 쪽 아래 25%는 장중 급락 회피에 씁니다.",
      "20개 사업군이 모두 읽히면 20×25%=5에서 소수점을 버려 오른 쪽 5개, 내린 쪽 5개가 순위 조건을 충족합니다. 18개만 읽히면 4개씩입니다. 17개 이하로 읽히면 조회 성공률 90%에 못 미쳐 순위를 매기지 않습니다.",
    ]);
    expect(criteriaRow(container, "최소 조회 성공률")?.slice(1, 2)).toEqual(["90%"]);
    expect(criteriaRow(container, "최소 조회 성공률")?.[3]).toBe(
      "20개 사업군 중 18개 이상(90.0%)을 읽으면 사업군 판정을 하고, 17개(85.0%) 이하이면 그 회차의 「신규 진입 검토」와 「진입 회피」 구역을 모두 뺍니다. 보유 종목 급등락 알림은 그대로 판정합니다.",
    );
    expect(criteriaRow(container, "구역별 최대")?.[1]).toBe("4건");
    expect(criteriaRow(container, "구역별 최대")?.[3]).toContain(
      "종목이 6개여도 이번 메시지에는 4개만 실리고, 한 메시지에는 최대 12종목이 실립니다.",
    );
    expect(criteriaRow(container, "진입 검토 하한")?.[3]).toContain("상승 순위 상위 25% 안에");
    // 활성 사업군 수(27)로 만든 문장이 섞이지 않는다.
    expect(text).not.toContain("27개 사업군");
  });

  it("값이 하나도 없어도(빈 목록) 표는 펼쳐져 있고 모든 값은 '확인 불가'", async () => {
    const { container } = await renderNoCandidate({ policy_values: [] });
    const table = screen.getByRole("table", { name: "PC에 기록된 적용 기준" });
    expect(table.closest("details")).toBeNull();
    const values = Array.from(table.querySelectorAll("td.ops-criteria-value")).map(
      (td) => td.textContent,
    );
    expect(values).toHaveLength(10);
    expect(values.every((v) => v === "확인 불가")).toBe(true);
    expect(footnoteText(container)).toBe(C9_MISSING_FOOTNOTE);
  });

  // POC6-34 검증자 r1 R1-F3 — 후보의 정책 블록이 빠졌을 때 백엔드가 내리는 모양
  // (12개 키 값 모두 null · 후보 켜짐 · 상태 null). 활성 값으로 메우지 않는다.
  it("후보 정책이 빠지면 제목은 '승인 시 적용될 기준' 그대로 · 모든 값 '확인 불가' · 승인 후 설정도 '확인 불가'", async () => {
    const { container } = await renderWith({
      policy_enabled: true,
      policy_status: "CONFIGURED",
      candidate_policy_enabled: null,
      candidate_policy_status: null,
      policy_values: CONFIRMED_VALUES.map((p) => ({ key: p.key, value: null })),
    });
    const text = container.textContent ?? "";
    expect(text).not.toContain("PC에 기록된 적용 기준");
    const table = screen.getByRole("table", { name: "승인 시 적용될 기준" });
    expect(table.closest("details")).toBeNull();
    // 설정값 칸 10개 모두 '확인 불가'.
    const values = Array.from(table.querySelectorAll("td.ops-criteria-value")).map(
      (td) => td.textContent,
    );
    expect(values).toHaveLength(10);
    expect(values.every((v) => v === "확인 불가")).toBe(true);
    // '이 값의 뜻' — R1-F1 × R1-F3 합친 계약. 보유 급등 · 급락 두 행은 설정값이 아니라 프로그램 고정
    // 경계 문장 그대로(값이 없으니 '다릅니다' 문장 없음)이고, 나머지 8행은 '확인 불가'다.
    expect(criteriaRow(container, "보유 급등 기준")?.[3]).toBe(SURGE_FIXED_MEANING);
    expect(criteriaRow(container, "보유 급락 기준")?.[3]).toBe(DROP_FIXED_MEANING);
    const meanings = Array.from(table.querySelectorAll("tbody tr:not(.ops-criteria-group)"))
      .map((tr) => Array.from(tr.querySelectorAll("td")).map((td) => td.textContent ?? ""))
      .filter((cells) => cells[0] !== "보유 급등 기준" && cells[0] !== "보유 급락 기준")
      .map((cells) => cells[3]);
    expect(meanings).toHaveLength(8);
    expect(meanings.every((m) => m === "확인 불가")).toBe(true);
    expect(footnoteText(container)).toBe(C9_MISSING_FOOTNOTE);
    expect(rowValue(container, "승인 후 장중 알림 설정")).toBe("확인 불가");
    // 배지는 지금(활성) 상태 그대로다.
    expect(headBadge(container).textContent).toBe("PC 기록 기준 · 장중 알림 설정 켜짐");
  });

  it("활성도 후보도 없으면 제목 'PC에 기록된 적용 기준' · 모든 값 '확인 불가'", async () => {
    const { container } = await renderNoCandidate({
      active_version_id: null,
      active_source_hash: null,
      active_data_asof: null,
      active_sector_count: 0,
      deploy_status: null,
      policy_values: CONFIRMED_VALUES.map((p) => ({ key: p.key, value: null })),
    });
    expect(screen.getByRole("table", { name: "PC에 기록된 적용 기준" })).toBeTruthy();
    for (const label of ["순위 조건", "최소 조회 성공률", "하루 최대"]) {
      expect(criteriaRow(container, label)?.[1]).toBe("확인 불가");
      expect(criteriaRow(container, label)?.[3]).toBe("확인 불가");
    }
    // 보유 급등 · 급락은 설정값 칸만 '확인 불가'이고, '이 값의 뜻'은 프로그램 고정 경계 문장이다
    // (실행 코드가 설정값을 읽지 않음 · POC6-34 r1 R1-F1).
    expect(criteriaRow(container, "보유 급등 기준")?.[1]).toBe("확인 불가");
    expect(criteriaRow(container, "보유 급등 기준")?.[3]).toBe(SURGE_FIXED_MEANING);
    expect(criteriaRow(container, "보유 급락 기준")?.[1]).toBe("확인 불가");
    expect(criteriaRow(container, "보유 급락 기준")?.[3]).toBe(DROP_FIXED_MEANING);
  });
});

describe("IntradayConfigCard — POC6-34 후보 차이 = 대표 + 켜짐 변화 (Q10 · I-24)", () => {
  it("꺼짐 → 켜짐이면 변경 목록에 한 줄 · 건수에 더한다", async () => {
    const { container } = await renderWith({
      policy_enabled: false,
      candidate_policy_enabled: true,
    });
    expect(rowValue(container, "확인할 변경")).toBe("3건");
    const items = Array.from(container.querySelectorAll("ul.tc-list li")).map(
      (li) => li.textContent,
    );
    expect(items).toEqual([
      "반도체 교체 · 이전 091160 · 이후 396500",
      "조선 추가 · 이후 466920",
      "장중 알림 설정: 꺼짐 → 켜짐",
    ]);
  });

  it("켜짐 → 꺼짐도 한 줄 · 사업군 차이가 없어도 '1건'", async () => {
    const { container } = await renderWith({
      changes: [],
      policy_enabled: true,
      policy_status: "CONFIGURED",
      candidate_policy_enabled: false,
    });
    expect(rowValue(container, "확인할 변경")).toBe("1건");
    expect(
      Array.from(container.querySelectorAll("ul.tc-list li")).map((li) => li.textContent),
    ).toEqual(["장중 알림 설정: 켜짐 → 꺼짐"]);
    expect(container.textContent ?? "").not.toContain("비교할 수 없는 차이");
  });

  it("켜짐이 같으면 그 줄은 없다", async () => {
    const { container } = await renderWith({
      policy_enabled: true,
      policy_status: "CONFIGURED",
      candidate_policy_enabled: true,
    });
    expect(rowValue(container, "확인할 변경")).toBe("2건");
    expect(container.textContent ?? "").not.toContain("장중 알림 설정: ");
  });

  it("첫 설정이면 차이 목록 대신 '첫 설정입니다' (켜짐 줄도 없음)", async () => {
    const { container } = await renderWith({
      active_version_id: null,
      policy_enabled: false,
      candidate_policy_enabled: true,
    });
    expect(rowValue(container, "확인할 변경")).toBe("있음");
    expect(container.querySelector("ul.tc-list")).toBeNull();
    expect(container.textContent ?? "").toContain("첫 설정입니다. 직전 승인본이 없습니다.");
  });
});

// ── POC6-34 검증자 r2 R2-F4 — 지금(활성) 켜짐 여부를 모를 때 ─────────────────────────
//
// 활성 정책의 `enabled` 가 없거나 bool 이 아니면 응답은 null 이다(옛 서버는 값 없음 · 문자열이 그대로
// 올 수도 있다고 보고 화면도 bool 만 믿는다). 배지 · '지금 알림 상태' = 확인 불가, 후보와의 비교는
// '같음' · '꺼짐 → 켜짐'을 말하지 않고, 경고는 꺼짐도 켜짐도 가정하지 않는다. 값은 합성 고정값이다.
const UNKNOWN_BADGE = "PC 기록 기준 · 장중 알림 설정 확인 불가";
const ENABLE_WARN = "이 설정을 승인하면 장중 알림 설정이 켜집니다.";
// 설계자 RESULT 판정 C7(2026-11-19 · 형수님 결정 U1 · U2) — 고정 건수 문장 대신 '위 표의 하루 최대 한도'.
const UNKNOWN_ENABLE_WARN =
  "이 설정을 승인하면 장중 알림 설정이 켜진 상태가 됩니다. 지금 설정을 확인할 수 없어 새로 켜지는 것인지는 알 수 없습니다. 발송 조건을 충족한 장중 알림에는 위 표의 하루 최대 한도가 적용됩니다.";
// 지금 · 후보를 비교했다고 읽히는 글 — 지금 켜짐 여부를 모르면 하나도 없어야 한다.
const COMPARED_TEXTS = [
  "지금과 같음",
  "지금 꺼짐 → 켜짐",
  "지금 켜짐 → 꺼짐",
  "장중 알림 설정: ",
  "장중 알림 설정이 없습니다",
];

function unknownParagraph(side: string): string {
  return `직전 승인본과 달라진 사업군이 없습니다. ${side}의 장중 알림 켜짐 여부는 확인할 수 없습니다. 판정 기준값 · 대체 ETF 의 차이는 이 화면에서 비교할 수 없습니다.`;
}

// 응답 형식 밖의 값(값 없음 · 문자열)도 그대로 넣어 본다.
function raw(value: unknown): boolean | null {
  return value as boolean | null;
}

describe("IntradayConfigCard — POC6-34 r2 지금 켜짐 여부 모름 (R2-F4 · Q5 · I-13)", () => {
  it.each([
    ["null", null, null],
    ["null", null, "NOT_CONFIGURED"],
    ["null", null, "CONFIGURED"],
    ["값 없음", undefined, "NOT_CONFIGURED"],
    ['문자열 "false"', "false", "NOT_CONFIGURED"],
    ['문자열 "true"', "true", "CONFIGURED"],
  ])(
    "후보 없음 · 지금 켜짐 여부 %s · 상태 %s → 배지 '확인 불가'(회색) · 켜짐 · 꺼짐 · 미설정 없음",
    async (_name, enabled, status) => {
      const { container } = await renderNoCandidate({
        policy_enabled: raw(enabled),
        policy_status: status,
      });
      const badge = headBadge(container);
      expect(badge.textContent).toBe(UNKNOWN_BADGE);
      expect(badge.className).toBe("oci-state unknown");
      expect(badge.getAttribute("title")).toBe(BADGE_TITLE);
      const text = container.textContent ?? "";
      expect(text).not.toContain("장중 알림 설정 켜짐");
      expect(text).not.toContain("장중 알림 설정 꺼짐");
      expect(text).not.toContain("정책 미설정");
    },
  );

  it.each([
    [true, null, "켜짐 (지금 상태 확인 불가)", true],
    [true, "NOT_CONFIGURED", "켜짐 (지금 상태 확인 불가)", true],
    [false, null, "꺼짐 (지금 상태 확인 불가)", false],
    [null, null, "확인 불가", false],
  ])(
    "지금 null · 후보 %s (지금 상태 %s) → '승인 후 장중 알림 설정' = '%s' · 비교 문구 없음 · 모름 경고 %s",
    async (candOn, nowStatus, label, unknownWarn) => {
      const { container } = await renderWith({
        policy_enabled: null,
        policy_status: nowStatus,
        candidate_policy_enabled: candOn,
        candidate_policy_status: candOn === null ? null : candOn ? "CONFIGURED" : "NOT_CONFIGURED",
      });
      expect(headBadge(container).textContent).toBe(UNKNOWN_BADGE);
      expect(headBadge(container).className).toBe("oci-state unknown");
      expect(rowValue(container, "지금 알림 상태")).toBe(UNKNOWN_BADGE);
      expect(rowValue(container, "승인 후 장중 알림 설정")).toBe(label);
      const text = container.textContent ?? "";
      for (const t of COMPARED_TEXTS) expect(text).not.toContain(t);
      // 켜짐 변화는 세지 않는다 — 바뀐 사업군 두 줄만.
      expect(rowValue(container, "확인할 변경")).toBe("2건");
      expect(
        Array.from(container.querySelectorAll("ul.tc-list li")).map((li) => li.textContent),
      ).toEqual(["반도체 교체 · 이전 091160 · 이후 396500", "조선 추가 · 이후 466920"]);
      // '켜집니다'(지금 꺼짐 가정) 경고는 없고, 후보가 켜짐이면 모름 경고가 있다(경고 없음 = 지금 켜짐 가정).
      expect(text).not.toContain(ENABLE_WARN);
      expect(text.includes(UNKNOWN_ENABLE_WARN)).toBe(unknownWarn);
    },
  );

  it.each([
    [true, "지금 설정"],
    [false, "지금 설정"],
    [null, "지금 설정과 승인할 설정"],
  ])(
    "지금 null · 후보 %s · 바뀐 사업군 없음 → '%s의 … 확인할 수 없습니다' · '장중 알림 설정이 없습니다' 없음",
    async (candOn, side) => {
      const { container } = await renderWith({
        changes: [],
        policy_enabled: null,
        policy_status: null,
        candidate_policy_enabled: candOn,
      });
      const text = container.textContent ?? "";
      expect(text).toContain(unknownParagraph(side));
      for (const t of COMPARED_TEXTS) expect(text).not.toContain(t);
      expect(container.querySelector("ul.tc-list")).toBeNull();
      expect(rowValue(container, "확인할 변경")).toBe("있음 (이 화면에서 비교할 수 없는 차이)");
    },
  );

  it("지금은 알고 후보만 모르면 문단은 '승인할 설정의 …'(r1 문구 그대로)", async () => {
    const { container } = await renderWith({
      changes: [],
      policy_enabled: true,
      policy_status: "CONFIGURED",
      candidate_policy_enabled: null,
    });
    expect(container.textContent ?? "").toContain(unknownParagraph("승인할 설정"));
  });

  it.each([
    ['문자열 "false"', "false"],
    ['문자열 "true"', "true"],
    ["값 없음", undefined],
    ["숫자 0", 0],
  ])(
    "지금 켜짐 여부가 %s · 후보 켜짐 → '지금과 같음' · '꺼짐 → 켜짐' · '켜집니다' 없음(검증자 재현)",
    async (_name, enabled) => {
      const { container } = await renderWith({
        policy_enabled: raw(enabled),
        policy_status: "NOT_CONFIGURED",
        candidate_policy_enabled: true,
        candidate_policy_status: "CONFIGURED",
      });
      expect(headBadge(container).textContent).toBe(UNKNOWN_BADGE);
      expect(rowValue(container, "승인 후 장중 알림 설정")).toBe("켜짐 (지금 상태 확인 불가)");
      const text = container.textContent ?? "";
      for (const t of COMPARED_TEXTS) expect(text).not.toContain(t);
      expect(text).not.toContain(ENABLE_WARN);
      expect(text).toContain(UNKNOWN_ENABLE_WARN);
      expect(rowValue(container, "확인할 변경")).toBe("2건");
    },
  );

  it.each([
    ["값 없음", undefined],
    ['문자열 "true"', "true"],
  ])(
    "후보 켜짐 여부가 %s 이면 '확인 불가' · 켜짐 변화 줄 없음(지금 꺼짐)",
    async (_name, candOn) => {
      const { container } = await renderWith({
        policy_enabled: false,
        policy_status: "NOT_CONFIGURED",
        candidate_policy_enabled: raw(candOn),
      });
      expect(rowValue(container, "승인 후 장중 알림 설정")).toBe("확인 불가");
      const text = container.textContent ?? "";
      expect(text).not.toContain("장중 알림 설정: ");
      expect(text).not.toContain("이 설정을 승인하면");
      expect(headBadge(container).textContent).toBe("PC 기록 기준 · 장중 알림 정책 미설정");
    },
  );

  it("첫 설정 · 지금 null · 후보 켜짐 → '첫 설정입니다' · 모름 경고 · 켜짐 줄 없음", async () => {
    const { container } = await renderWith({
      active_version_id: null,
      policy_enabled: null,
      policy_status: null,
      candidate_policy_enabled: true,
      candidate_policy_status: "CONFIGURED",
    });
    expect(rowValue(container, "확인할 변경")).toBe("있음");
    expect(container.querySelector("ul.tc-list")).toBeNull();
    const text = container.textContent ?? "";
    expect(text).toContain("첫 설정입니다. 직전 승인본이 없습니다.");
    expect(text).toContain(UNKNOWN_ENABLE_WARN);
    expect(text).not.toContain(ENABLE_WARN);
    expect(rowValue(container, "승인 후 장중 알림 설정")).toBe("켜짐 (지금 상태 확인 불가)");
  });
});

// ── 설계자 RESULT 판정(2026-11-19) — C7 켜짐 경고 · C8 정책 상태 확인 불가 · C9 각주 · 조회 성공률 ─────────
//
// 값은 모두 합성 고정값이다. 형수님 결정(2026-11-19): C7 은 경고가 판정 기준 표 **아래**에 그려지므로 '위 표의' ·
// 두 경고 모두 같은 발송 안내 · C9 는 값이 없으면 중복 억제 창 문장을 끊고 회차당 최대를 따로 쓴다.
const LABEL_ON = "PC 기록 기준 · 장중 알림 설정 켜짐";
const LABEL_OFF = "PC 기록 기준 · 장중 알림 설정 꺼짐";
const LABEL_NOT_CONFIGURED = "PC 기록 기준 · 장중 알림 정책 미설정";
const LABEL_ON_STATUS_UNKNOWN = "PC 기록 기준 · 장중 알림 설정 켜짐 · 정책 상태 확인 불가";
const LABEL_OFF_STATUS_UNKNOWN = "PC 기록 기준 · 장중 알림 설정 꺼짐 · 정책 상태 확인 불가";
const C7_OFF_WARN =
  "이 설정을 승인하면 장중 알림 설정이 켜집니다. 발송 조건을 충족한 장중 알림에는 위 표의 하루 최대 한도가 적용됩니다.";
const COVERAGE_WHAT =
  "이 표에 표시한 설정의 사업군 가운데 오늘 시세(등락률)를 읽은 사업군의 비율을 봅니다. 대표 ETF 대신 대체 ETF로 읽은 경우도 성공으로 셉니다.";

// [활성 버전 있음, 켜짐 여부, 정책 상태, 배지 · '지금 알림 상태' 글, 배지 톤] — 활성 있음/없음 × 켜짐 true/false/null ×
// 상태 CONFIGURED/NOT_CONFIGURED/null/'WEIRD' 24조합. 활성 없음(첫 설정 · C6)과 켜짐 null(r2)은 전과 같다.
const C8_MATRIX: [boolean, boolean | null, string | null, string, string][] = [
  [true, true, "CONFIGURED", LABEL_ON, "ok"],
  [true, true, "NOT_CONFIGURED", LABEL_ON, "ok"],
  [true, true, null, LABEL_ON_STATUS_UNKNOWN, "unknown"],
  [true, true, "WEIRD", LABEL_ON_STATUS_UNKNOWN, "unknown"],
  [true, false, "CONFIGURED", LABEL_OFF, "unknown"],
  [true, false, "NOT_CONFIGURED", LABEL_NOT_CONFIGURED, "unknown"],
  [true, false, null, LABEL_OFF_STATUS_UNKNOWN, "unknown"],
  [true, false, "WEIRD", LABEL_OFF_STATUS_UNKNOWN, "unknown"],
  [true, null, "CONFIGURED", UNKNOWN_BADGE, "unknown"],
  [true, null, "NOT_CONFIGURED", UNKNOWN_BADGE, "unknown"],
  [true, null, null, UNKNOWN_BADGE, "unknown"],
  [true, null, "WEIRD", UNKNOWN_BADGE, "unknown"],
  [false, true, "CONFIGURED", LABEL_ON, "ok"],
  [false, true, "NOT_CONFIGURED", LABEL_ON, "ok"],
  [false, true, null, LABEL_ON, "ok"],
  [false, true, "WEIRD", LABEL_ON, "ok"],
  [false, false, "CONFIGURED", LABEL_OFF, "unknown"],
  [false, false, "NOT_CONFIGURED", LABEL_NOT_CONFIGURED, "unknown"],
  [false, false, null, LABEL_OFF, "unknown"],
  [false, false, "WEIRD", LABEL_OFF, "unknown"],
  [false, null, "CONFIGURED", UNKNOWN_BADGE, "unknown"],
  [false, null, "NOT_CONFIGURED", UNKNOWN_BADGE, "unknown"],
  [false, null, null, UNKNOWN_BADGE, "unknown"],
  [false, null, "WEIRD", UNKNOWN_BADGE, "unknown"],
];

function activePatch(hasActive: boolean): Partial<IntradayConfigState> {
  return hasActive ? {} : { active_version_id: null, active_source_hash: null, active_data_asof: null };
}

describe("IntradayConfigCard — 설계자 RESULT 판정 C8 정책 상태 확인 불가", () => {
  it.each(C8_MATRIX)(
    "후보 있음 · 활성 %s · 켜짐 %s · 상태 %s → 배지 · '지금 알림 상태' = '%s' (%s)",
    async (hasActive, enabled, status, label, tone) => {
      const { container } = await renderWith({
        ...activePatch(hasActive),
        policy_enabled: enabled,
        policy_status: status,
      });
      const badge = headBadge(container);
      expect(badge.textContent).toBe(label);
      expect(badge.className).toBe(`oci-state ${tone}`);
      expect(badge.getAttribute("title")).toBe(BADGE_TITLE);
      expect(rowValue(container, "지금 알림 상태")).toBe(label);
    },
  );

  it.each(C8_MATRIX)(
    "후보 없음 · 활성 %s · 켜짐 %s · 상태 %s → 배지 = '%s' (%s)",
    async (hasActive, enabled, status, label, tone) => {
      const { container } = await renderNoCandidate({
        ...activePatch(hasActive),
        policy_enabled: enabled,
        policy_status: status,
      });
      const badge = headBadge(container);
      expect(badge.textContent).toBe(label);
      expect(badge.className).toBe(`oci-state ${tone}`);
    },
  );

  it("정책 상태가 문자열이 아니어도(옛 서버 · 숫자) 활성 버전이 있으면 '정책 상태 확인 불가'(회색)", async () => {
    const { container } = await renderNoCandidate({
      policy_enabled: true,
      policy_status: 1 as unknown as string,
    });
    expect(headBadge(container).textContent).toBe(LABEL_ON_STATUS_UNKNOWN);
    expect(headBadge(container).className).toBe("oci-state unknown");
  });
});

describe("IntradayConfigCard — 설계자 RESULT 판정 C7 켜짐 경고의 발송 안내", () => {
  // 후보의 하루 최대(6)가 활성 값과 달라도 경고는 숫자를 직접 쓰지 않고 위 표(후보값)를 가리킨다.
  const CANDIDATE_DAILY_6 = CONFIRMED_VALUES.map((p) =>
    p.key === "max_sends_per_day" ? { key: p.key, value: 6 } : p,
  );

  it.each([
    ["지금 꺼짐 확인", false, "NOT_CONFIGURED", "이 설정을 승인하면 장중 알림 설정이 켜집니다.", C7_OFF_WARN],
    [
      "지금 확인 불가",
      null,
      null,
      "이 설정을 승인하면 장중 알림 설정이 켜진 상태가 됩니다.",
      UNKNOWN_ENABLE_WARN,
    ],
  ])(
    "%s · 후보 켜짐 → 경고 글자 그대로 · 고정 건수 없음 · 판정 기준 표 아래",
    async (_name, nowOn, nowStatus, head, want) => {
      const { container } = await renderWith({
        policy_enabled: nowOn,
        policy_status: nowStatus,
        candidate_policy_enabled: true,
        candidate_policy_status: "CONFIGURED",
        policy_values: CANDIDATE_DAILY_6,
      });
      const warns = Array.from(container.querySelectorAll("p")).filter((p) =>
        (p.textContent ?? "").startsWith("이 설정을 승인하면"),
      );
      expect(warns).toHaveLength(1);
      const warn = warns[0];
      expect(warn.textContent).toBe(want);
      expect(warn.querySelector("b")?.textContent).toBe(head);
      for (const bad of ["4건", "8건", "기존 고정", "추가 발송", "아래의"]) {
        expect(warn.textContent).not.toContain(bad);
      }
      // '위 표의' — 판정 기준 표는 늘 그려지고 경고보다 앞(위)에 있다. 하루 최대는 그 표의 후보값이다.
      const table = screen.getByRole("table", { name: "승인 시 적용될 기준" });
      expect(table.compareDocumentPosition(warn) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(criteriaRow(container, "하루 최대")?.[1]).toBe("6건");
    },
  );
});

describe("IntradayConfigCard — 설계자 RESULT 판정 C9 각주 · 조회 성공률 대상 문구", () => {
  const RUN_NULL = CONFIRMED_VALUES.map((p) =>
    p.key === "max_sends_per_run" ? { key: p.key, value: null } : p,
  );
  const RUN_ABSENT = CONFIRMED_VALUES.filter((p) => p.key !== "max_sends_per_run");

  it.each([
    ["null", RUN_NULL],
    ["칸 없음", RUN_ABSENT],
  ])("활성 값(후보 없음)의 회차당 최대가 %s → 각주 문장 분리", async (_name, values) => {
    const { container } = await renderNoCandidate({ policy_values: values });
    expect(screen.getByRole("table", { name: "PC에 기록된 적용 기준" })).toBeTruthy();
    expect(footnoteText(container)).toBe(C9_MISSING_FOOTNOTE);
    expect(container.textContent ?? "").not.toContain("확인 불가는");
  });

  it.each([
    ["null", RUN_NULL],
    ["칸 없음", RUN_ABSENT],
  ])("후보 값의 회차당 최대가 %s → 각주 문장 분리", async (_name, values) => {
    const { container } = await renderWith({ policy_values: values });
    expect(screen.getByRole("table", { name: "승인 시 적용될 기준" })).toBeTruthy();
    expect(footnoteText(container)).toBe(C9_MISSING_FOOTNOTE);
    expect(container.textContent ?? "").not.toContain("확인 불가는");
  });

  it("회차당 최대가 확인되면 각주는 기존 문장 그대로(후보 있음 · 없음)", async () => {
    const withCand = await renderWith();
    expect(footnoteText(withCand.container)).toBe(KNOWN_FOOTNOTE);
    cleanup();
    const noCand = await renderNoCandidate();
    expect(footnoteText(noCand.container)).toBe(KNOWN_FOOTNOTE);
  });

  it("조회 성공률 '무엇을 보는지' = '이 표에 표시한 설정의 사업군 가운데 …'(후보 있음 · 없음)", async () => {
    const withCand = await renderWith();
    expect(criteriaRow(withCand.container, "최소 조회 성공률")?.[2]).toBe(COVERAGE_WHAT);
    expect(withCand.container.textContent ?? "").not.toContain("활성 설정의 사업군 가운데");
    cleanup();
    const noCand = await renderNoCandidate();
    expect(criteriaRow(noCand.container, "최소 조회 성공률")?.[2]).toBe(COVERAGE_WHAT);
    expect(noCand.container.textContent ?? "").not.toContain("활성 설정의 사업군 가운데");
  });
});
