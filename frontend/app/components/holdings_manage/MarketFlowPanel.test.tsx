// POC5-05 개정 2 — 시장 흐름 패널 test(설계 §8 · §11-1 Q-B · PLAN §2-7).
// 자료 = 실제 백엔드 build_market_flow 출력(historyFixtures). API 는 vi.mock("@/lib/api").
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const fetchMarketFlow = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchMarketFlow: (...a: unknown[]) => fetchMarketFlow(...a),
  };
});

import { ApiRequestError, type MarketFlowResponse } from "@/lib/api";
import MarketFlowPanel, { MarketFlowView } from "./MarketFlowPanel";
import { FLOW_ETF, FLOW_STOCK } from "./historyFixtures";
import { REFERENCE_FLOW_NAME_TEXT, REFERENCE_NOTE_TEXT, referenceFlowName, referenceNoteText } from "./historyText";
import { FLOW_REF_OPEN, FLOW_REF_SOLD } from "./referenceFixtures";

// POC6-33 I-2 — 서버 시험(tests/test_poc5_07_reference_date.py)과 같은 공용 고정 자료로 기준일 글 사전을 대조한다
// (POC6-33 poc6_33_filtered_notes.json 과 같은 방식 · 저장소 파일만 읽음 · 보유 자료 없음).
// holdings_manage → components → app → frontend → 저장소 루트
const REPO_ROOT = path.dirname(
  path.dirname(path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))))),
);
type Label = { server: string; display: string };
const LABELS = JSON.parse(
  readFileSync(path.join(REPO_ROOT, "tests", "fixtures", "poc6_33_market_flow_labels.json"), "utf8"),
) as { reference_flow_name: Label; reference_note: Label };

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
      screen.getByText("재진입 판단을 돕는 근거 · ML 연구 추정은 이 기간의 [재진입 검토]에서 봅니다."),
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

describe("비교 시작일 낱말(POC6-33 I-2 · 설계자 RESULT 판정 §2-2) — 서버 원문 ↔ 화면 글 공용 고정 자료", () => {
  it("사전 열쇠 = 고정 자료의 서버 글 · 바꾼 글 = 고정 자료의 화면 글(한 쌍씩 · 그 밖 열쇠 없음)", () => {
    expect([...REFERENCE_FLOW_NAME_TEXT.entries()]).toEqual([
      [LABELS.reference_flow_name.server, LABELS.reference_flow_name.display],
    ]);
    expect([...REFERENCE_NOTE_TEXT.entries()]).toEqual([[LABELS.reference_note.server, LABELS.reference_note.display]]);
    for (const l of [LABELS.reference_flow_name, LABELS.reference_note]) {
      expect(l.server).toContain("가격 비교 기준일");
      expect(l.display).toContain("비교 시작일");
      expect(l.display).not.toContain("기준일");
    }
    // 화면 시험 자료(실제 백엔드 출력 복사)도 같은 서버 글이다 — 복사본만 낡으면 여기서 깨진다.
    for (const f of [FLOW_REF_OPEN, FLOW_REF_SOLD]) {
      expect(f.reference_flow?.name).toBe(LABELS.reference_flow_name.server);
      expect(f.reference_note).toBe(LABELS.reference_note.server);
    }
  });

  it("History 패널 = 서버 원문 대신 화면 글을 보이고 원문 낱말은 보이지 않는다", async () => {
    fetchMarketFlow.mockResolvedValue(FLOW_REF_OPEN);
    render(<MarketFlowPanel positionId="p" cycleId="cyc-ref" />);
    expect((await screen.findByText(LABELS.reference_flow_name.display)).tagName).toBe("STRONG");
    expect(screen.getByText(LABELS.reference_note.display).tagName).toBe("LI");
    expect(screen.queryByText(LABELS.reference_flow_name.server)).toBeNull();
    expect(screen.queryByText(LABELS.reference_note.server)).toBeNull();
    expect(line(LABELS.reference_flow_name.display)).toHaveTextContent("설정한 비교 시작일 2026-01-01) 종가");
  });

  it("재진입 검토 창이 쓰는 같은 그리기(MarketFlowView)도 화면 글로 읽는다", () => {
    render(<MarketFlowView data={FLOW_REF_OPEN} />);
    expect(screen.getByText(LABELS.reference_flow_name.display)).toBeInTheDocument();
    expect(screen.getByText(LABELS.reference_note.display)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/가격 비교 기준일|설정한 기준일/);
  });

  it("사전 밖 글은 원문 그대로(바꾸거나 숨기지 않음 · 'constructor' 같은 글도 글 그대로)", () => {
    expect(referenceFlowName("다른 흐름 이름")).toBe("다른 흐름 이름");
    expect(referenceNoteText("constructor")).toBe("constructor");
    expect(referenceFlowName("toString")).toBe("toString");
    const other = {
      ...FLOW_REF_OPEN,
      reference_flow: { ...FLOW_REF_OPEN.reference_flow!, name: "새 서버 흐름 이름" },
      reference_note: "새 서버 안내 글.",
    } as MarketFlowResponse;
    render(<MarketFlowView data={other} />);
    expect(screen.getByText("새 서버 흐름 이름")).toBeInTheDocument();
    expect(screen.getByText("새 서버 안내 글.")).toBeInTheDocument();
  });

  it("끝난 기간 줄 = '비교 시작일 …' · 휴장으로 옮긴 시작일은 '설정한 비교 시작일 … → 다음 거래일'", () => {
    // 시작일만 휴장 이동으로 바꾼 파생 자료(날짜 · 수치는 FLOW_REF_SOLD 그대로 · 화면 글 갈래 확인용).
    const hp = FLOW_REF_SOLD.holding_period!;
    const moved = {
      ...FLOW_REF_SOLD,
      holding_period: {
        ...hp,
        start_basis: { ...hp.start_basis!, trade_date: "2026-01-01", moved_to_next_trading_day: true },
      },
    } as MarketFlowResponse;
    render(<MarketFlowView data={moved} />);
    expect(line("→ 마지막 매도일")).toHaveTextContent(
      /^비교 시작일 2026-01-02\(설정한 비교 시작일 2026-01-01 → 다음 거래일\) → 마지막 매도일 2026-03-02 종가 변화 \+10%/,
    );
    expect(document.body.textContent).not.toMatch(/가격 비교 기준일|설정한 기준일|보유 기간/);
  });
});
