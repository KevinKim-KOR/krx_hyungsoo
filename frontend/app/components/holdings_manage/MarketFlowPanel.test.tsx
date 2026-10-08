// POC5-05 개정 2 — 시장 흐름 패널 test(설계 §8 · §11-1 Q-B · PLAN §2-7).
// 자료 = 실제 백엔드 build_market_flow 출력(historyFixtures). API 는 vi.mock("@/lib/api").
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const fetchMarketFlow = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchMarketFlow: (...a: unknown[]) => fetchMarketFlow(...a),
  };
});

import { ApiRequestError } from "@/lib/api";
import MarketFlowPanel from "./MarketFlowPanel";
import { FLOW_ETF, FLOW_STOCK } from "./historyFixtures";

beforeEach(() => {
  fetchMarketFlow.mockReset();
});

// 줄(li) 전체 글자로 찾는다(값 · 태그가 하위 요소로 나뉘어 있다).
function line(fragment: string): HTMLElement {
  const hits = screen.getAllByRole("listitem").filter((li) => li.textContent?.includes(fragment));
  if (hits.length !== 1) throw new Error(`줄 ${hits.length}개: ${fragment}`);
  return hits[0];
}

describe("ETF 기간", () => {
  it("마운트 때 1회 조회 · 불러오는 중 → 매매별 줄 · 마지막 저장일 날짜를 늘 보인다", async () => {
    fetchMarketFlow.mockResolvedValue(FLOW_ETF);
    render(<MarketFlowPanel positionId="pos-1" cycleId="cyc-1" />);
    expect(screen.getByText("시장 흐름을 불러오는 중…")).toBeInTheDocument();
    await screen.findByText(/저장 종가 비교값/);
    expect(fetchMarketFlow).toHaveBeenCalledTimes(1);
    expect(fetchMarketFlow).toHaveBeenCalledWith("pos-1", "cyc-1");
    const events = FLOW_ETF.events;
    expect(events).toHaveLength(4);
    for (const ev of events) {
      expect(line(`${ev.window_label}: ${ev.basis.basis_date}`)).toHaveTextContent("마지막 저장일 2026-10-02 종가");
    }
  });

  it("OK + 출처 다름: 변화율 · '출처 다름(시작 → 끝)' · 기준일(판정 근거 · 실제 거래일)", async () => {
    fetchMarketFlow.mockResolvedValue(FLOW_ETF);
    render(<MarketFlowPanel positionId="pos-1" cycleId="cyc-1" />);
    await screen.findByText(/저장 종가 비교값/);
    const li = line("매수 기준일 → 마지막 저장일: 2026-03-03(");
    expect(li).toHaveTextContent(
      "매수 기준일 → 마지막 저장일: 2026-03-03(비거래일(연도 파일) → 다음 거래일(연도 파일) · 거래일 2026-03-02) 종가 → 마지막 저장일 2026-10-02 종가: +18.32%",
    );
    expect(li).toHaveTextContent("출처 다름(NAVER_FDR → FinanceDataReader)");
    expect(li).toHaveTextContent("같은 날짜 KOSPI +10%");
    expect(li).toHaveTextContent("출처 다름(NAVER_FDR → KRX_OPEN_API/idx_kospi_dd_trd)");
    expect(li.querySelectorAll(".hmx-tag")).toHaveLength(2);
  });

  it("OK + 같은 출처: 변화율 · (출처 X) · 매도 줄은 '매도 뒤' 강조", async () => {
    fetchMarketFlow.mockResolvedValue(FLOW_ETF);
    render(<MarketFlowPanel positionId="pos-1" cycleId="cyc-1" />);
    await screen.findByText(/저장 종가 비교값/);
    const li = line("2026-05-20(거래일 그대로");
    expect(li).toHaveTextContent(
      "매도 뒤 · 매도 기준일 → 마지막 저장일: 2026-05-20(거래일 그대로(연도 파일)) 종가 → 마지막 저장일 2026-10-02 종가: +11.2% (출처 FinanceDataReader)",
    );
    expect(li).toHaveTextContent("같은 날짜 KOSPI +5.67% (출처 KRX_OPEN_API/idx_kospi_dd_trd)");
    expect(li.querySelector("strong")).toHaveTextContent("매도 뒤");
    expect(li.querySelector(".hmx-tag")).toBeNull();
  });

  it("NOT_COMPARABLE = 사유 문구(값 없음) · NO_DATA = 사유 문구", async () => {
    fetchMarketFlow.mockResolvedValue(FLOW_ETF);
    render(<MarketFlowPanel positionId="pos-1" cycleId="cyc-1" />);
    await screen.findByText(/저장 종가 비교값/);
    const nc = line("2026-04-15(");
    expect(nc).toHaveTextContent("비교 불가(가격 기준 확인 안 됨) (KRX_UNADJ → FinanceDataReader)");
    expect(nc).toHaveTextContent("같은 날짜 KOSPI +8.2%");
    const nd = line("2026-05-06(");
    expect(nd).toHaveTextContent("매도 뒤");
    expect(nd).toHaveTextContent(
      "종가: 자료 없음(기준일 종가 없음 · 인접일 대체 안 함) · 같은 날짜 KOSPI 자료 없음(기준일 종가 없음 · 인접일 대체 안 함)",
    );
    expect(nd).not.toHaveTextContent("%");
  });

  it("보유 기간(OK): 최초 매수일 → 마지막 매도일 종가 변화 · 같은 기간 KOSPI · 안내 · ML 버튼 없음", async () => {
    fetchMarketFlow.mockResolvedValue(FLOW_ETF);
    render(<MarketFlowPanel positionId="pos-1" cycleId="cyc-1" />);
    await screen.findByText(/저장 종가 비교값/);
    const li = line("보유 기간:");
    expect(li).toHaveTextContent(
      "보유 기간: 최초 매수일 2026-03-03(거래일 2026-03-02 → 다음 거래일) → 마지막 매도일 2026-05-20 종가 변화 +6.4%",
    );
    expect(li).toHaveTextContent("같은 기간 KOSPI +4.1%");
    for (const note of FLOW_ETF.notes) expect(screen.getByText(note)).toBeInTheDocument();
    expect(screen.getByText("계열: ETF 저장 종가 · KOSPI 저장 종가 · 출처는 각 날짜 행에 저장된 출처입니다.")).toBeInTheDocument();
    expect(
      screen.getByText("재진입 판단을 돕는 ‘재진입 검토’(ML)는 후속 단계에서 따로 설계합니다."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("개별주 · 오류", () => {
  it("개별주: 자료 없음(미수집) · 마지막 저장일 없음 · 매수일 미상 = 보유 기간 계산 안 함", async () => {
    fetchMarketFlow.mockResolvedValue(FLOW_STOCK);
    render(<MarketFlowPanel positionId="pos-2" cycleId="cyc-2" />);
    await screen.findByText(/저장 종가 비교값/);
    const li = line("매도 기준일 → 마지막 저장일");
    expect(li).toHaveTextContent(
      "매도 뒤 · 매도 기준일 → 마지막 저장일: 2026-09-30(거래일 그대로(연도 파일)) 종가 → 마지막 저장일 없음: 자료 없음(PC 개별주 일별 종가 미수집)",
    );
    expect(li).toHaveTextContent("같은 날짜 KOSPI 자료 없음(종목 비교 구간 없음)");
    expect(line("보유 기간:")).toHaveTextContent("보유 기간: 매수일 미상 — 매수 전후 변화 계산 안 함");
  });

  it("조회 실패 = 백엔드 문구('시세 DB 조회 실패') · 개인 History 와 무관하게 패널 안에만", async () => {
    fetchMarketFlow.mockRejectedValue(
      new ApiRequestError("HTTP 500", 500, { detail: "시세 DB 조회 실패: market_db_read_failed:DatabaseError" }),
    );
    render(<MarketFlowPanel positionId="pos-1" cycleId="cyc-1" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "시세 DB 조회 실패: market_db_read_failed:DatabaseError",
    );
    expect(screen.queryByText("시장 흐름을 불러오는 중…")).toBeNull();
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });
});
