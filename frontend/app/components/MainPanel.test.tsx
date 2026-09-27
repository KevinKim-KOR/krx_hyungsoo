// POC3-02D-OPS-02 3-1 — 라우팅 관통 test.
//
// 「오늘의 투자 점검」 OCI 한 줄의 링크를 누르면 **실제 MainPanel 전환**으로
// OCI 상세가 있는 화면이 떠야 한다. 2026-08-16 메뉴 분리 뒤에도 이 링크만
// 「개발·실험용」(`diagnostics` · OCI 상세 없음)으로 가던 결함의 재발 방지다.
// 단위 test(onNavigate 인자)만으로는 MainPanel switch 연결을 못 본다.
//
// 2026-09-27 사용자 직접 지시: 「승인·적용」과 「OCI 운영 상태」(`oci_status`)가
// 한 화면 「OCI 운영·적용」(`approval`)으로 합쳐졌다. 도착 화면은 그 화면의
// ① 지금 OCI 상태 (읽기만) 섹션이다.
//
// @/lib/api 는 부분 mock — 오늘 화면 · OCI 화면이 부르는 조회만 대역으로 바꾼다.
// 시장 · 보유 자료는 일부러 실패시킨다(이 test 는 자료가 아니라 이동을 본다).
// ② 의 적용 카드 두 장(현재 운영 기준 · 장중 급등락 설정)의 조회도 대역으로 바꿔
// 실제 요청이 나가지 않게 한다. 적용 · 승인 호출은 누르지 않는다.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";

const fetchOciStartupStatus = vi.fn();
const fetchThreePushParamState = vi.fn();
const applyThreePushParamToOci = vi.fn();
const fetchIntradayConfigState = vi.fn();
const approveAndApplyIntradayConfig = vi.fn();
const rejectIntradayConfig = vi.fn();
const noData = () => Promise.reject(new Error("test: 자료 없음"));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchMarketTopnLatest: () => noData(),
    fetchEnrichedHoldings: () => noData(),
    fetchHoldingsMarketEvidence: () => noData(),
    fetchNavDiscountLatest: () => noData(),
    fetchBenchmarkSeries: () => noData(),
    fetchOciStartupStatus: (...a: unknown[]) => fetchOciStartupStatus(...a),
  };
});

vi.mock("@/lib/api/threePushParam", () => ({
  fetchThreePushParamState: (...a: unknown[]) => fetchThreePushParamState(...a),
  applyThreePushParamToOci: (...a: unknown[]) => applyThreePushParamToOci(...a),
}));

vi.mock("@/lib/api/intradayConfig", () => ({
  fetchIntradayConfigState: (...a: unknown[]) => fetchIntradayConfigState(...a),
  approveAndApplyIntradayConfig: (...a: unknown[]) =>
    approveAndApplyIntradayConfig(...a),
  rejectIntradayConfig: (...a: unknown[]) => rejectIntradayConfig(...a),
}));

import MainPanel from "./MainPanel";

beforeEach(() => {
  __resetQueryCache();
  vi.clearAllMocks();
  fetchOciStartupStatus.mockResolvedValue({
    checked_at: "2026-09-27T08:18:31+00:00",
    reachable: true,
    overall: "OPERATING",
    summary_line: "OCI 자동 운영 스케줄 활성 (필수 3종 등록 · 기동 시 확인)",
    crontab_active: true,
    jobs: [
      {
        job: "crontab",
        status: "SUCCESS",
        detail: "필수 스케줄(시장·보유·급등락) 모두 등록됨",
      },
    ],
    note: "",
  });
  fetchThreePushParamState.mockResolvedValue({
    status: "applied",
    display_label: "기본 운영 기준",
    applied_at: "2026-09-25 15:40",
    oci_verified: true,
    message: "OCI 반영 확인됨",
  });
  fetchIntradayConfigState.mockResolvedValue({
    active_version_id: "intraday-20260910T000000-000001",
    active_source_hash: "a".repeat(64),
    active_data_asof: "2026-09-10",
    active_sector_count: 26,
    candidate_version_id: null,
    candidate_source_hash: null,
    candidate_data_asof: null,
    candidate_sector_count: 0,
    changes: [],
    policy_enabled: false,
    policy_status: "NOT_CONFIGURED",
    candidate_policy_enabled: null,
    candidate_policy_status: null,
    policy_values: [],
    policy_rule_version: "sector_rep.v1",
    deploy_status: "deployed",
    deploy_error: null,
    action_state: null,
    payload_error: null,
  });
});

describe("MainPanel 라우팅 관통 (POC3-02D-OPS-02 3-1)", () => {
  it("오늘의 투자 점검 OCI 링크 → 「OCI 운영·적용」 화면이 뜬다", async () => {
    render(<MainPanel />);
    expect(
      await screen.findByRole("heading", { level: 1, name: "오늘의 투자 점검" }),
    ).toBeInTheDocument();

    fireEvent.click(
      await screen.findByRole("button", { name: "OCI 운영·적용에서 상세 보기 →" }),
    );

    // 도착 화면 = 「OCI 운영·적용」. 「개발·실험용」이 아니다.
    expect(
      await screen.findByRole("heading", { level: 1, name: "OCI 운영·적용" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 1, name: "개발·실험용" })).toBeNull();
    expect(
      screen.queryByRole("heading", { level: 1, name: "오늘의 투자 점검" }),
    ).toBeNull();
    // OCI 상세(①)가 실제로 그려진다(도착 화면이 빈 화면이 아님).
    expect(
      screen.getByRole("heading", { level: 2, name: "① 지금 OCI 상태 (읽기만)" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("정상 운영 중")).toBeInTheDocument();
    expect(
      screen.getByText("시장 브리핑 · 보유 브리핑 · 장중 급등락"),
    ).toBeInTheDocument();

    // ② 적용 카드 두 장도 같은 화면에 있다(대역 조회로 채워짐).
    const apply = screen
      .getByRole("heading", { level: 2, name: "② OCI 에 적용 (버튼으로 반영)" })
      .closest("section") as HTMLElement;
    expect(await within(apply).findByText("기본 운영 기준")).toBeInTheDocument();
    expect(
      within(apply).getByRole("heading", { name: "현재 운영 기준" }),
    ).toBeInTheDocument();
    expect(
      await within(apply).findByRole("region", { name: "장중 급등락 설정" }),
    ).toBeInTheDocument();
    expect(fetchThreePushParamState).toHaveBeenCalled();
    expect(fetchIntradayConfigState).toHaveBeenCalled();
    // 적용 · 승인 · 기각은 누르지 않았다 — 쓰기 호출 0.
    expect(applyThreePushParamToOci).not.toHaveBeenCalled();
    expect(approveAndApplyIntradayConfig).not.toHaveBeenCalled();
    expect(rejectIntradayConfig).not.toHaveBeenCalled();

    // 사이드바의 현재 화면도 「OCI 운영·적용」 하나다.
    const sidebar = screen.getByRole("complementary", { name: "좌측 메뉴" });
    const current = within(sidebar)
      .getAllByRole("button")
      .filter((b) => b.getAttribute("aria-current") === "page");
    expect(current).toHaveLength(1);
    expect(current[0].textContent).toContain("OCI 운영·적용");
  });
});
