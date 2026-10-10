// POC5-06 — 재진입 검토 창 test(설계 개정 2 §2 · §5 · §10-4 · §10-5). 자료 = 실제 백엔드 출력
// (reentryFixtures · historyFixtures). API 는 vi.mock("@/lib/api") 로 바꿔 끼운다.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";

const fetchReentryReview = vi.fn();
const runReentryMl = vi.fn();
const fetchTradeHistory = vi.fn();
const fetchEnrichedHoldings = vi.fn();
const fetchMarketFlow = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchReentryReview: (...a: unknown[]) => fetchReentryReview(...a),
    runReentryMl: (...a: unknown[]) => runReentryMl(...a),
    fetchTradeHistory: (...a: unknown[]) => fetchTradeHistory(...a),
    fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
    fetchMarketFlow: (...a: unknown[]) => fetchMarketFlow(...a),
  };
});

import { ApiRequestError, type HoldingItem, type ReentryMlResponse } from "@/lib/api";
import ReentryReviewDialog from "./ReentryReviewDialog";
import HoldingsBookSection from "./HoldingsBookSection";
import { ML_OK, ML_SHORT, REVIEW } from "./reentryFixtures";
import { HISTORY, HISTORY_V1 } from "./historyFixtures";

const PID = REVIEW.selection.position_id;
const CID = REVIEW.selection.cycle_id;

beforeEach(() => {
  for (const f of [fetchReentryReview, runReentryMl, fetchTradeHistory, fetchEnrichedHoldings, fetchMarketFlow]) {
    f.mockReset();
  }
  fetchReentryReview.mockResolvedValue(REVIEW);
});

function renderReview(extra: Partial<Parameters<typeof ReentryReviewDialog>[0]> = {}) {
  const props = {
    positionId: PID,
    cycleId: CID,
    onBack: vi.fn(),
    onClose: vi.fn(),
    onNavigate: vi.fn(),
    onTrade: vi.fn(),
    ...extra,
  };
  render(<ReentryReviewDialog {...props} />);
  return props;
}

describe("재진입 검토 창", () => {
  it("열면 검토 GET 만 부르고 ML 은 부르지 않는다 · 세 부분 · 날짜 기준 표시", async () => {
    renderReview();
    expect(await screen.findByRole("heading", { name: /내 거래/ })).toBeInTheDocument();
    expect(fetchReentryReview).toHaveBeenCalledWith(PID, CID);
    expect(runReentryMl).not.toHaveBeenCalled();
    expect(screen.getByRole("heading", { name: /저장된 근거/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /ML 검토 — 이후 20거래일 최저 종가 변화\(연구 추정\)/ })).toBeInTheDocument();
    const ps = REVIEW.stored_evidence.price_state;
    expect(screen.getByText(`저장 종가 ${ps.t} 기준`)).toBeInTheDocument();
    expect(screen.getByText("이 날짜 기준 검토")).toBeInTheDocument(); // 자료 = 기대 완료일보다 이른 저장일
    // 읽은 기준 = revision + 문서 hash(§10-5 — V1 은 revision 0 이라 hash 로 구분)
    expect(document.body.textContent).toContain(`revision 0 · 문서 hash ${REVIEW.read_basis.doc_sha256.slice(0, 12)}`);
    expect(screen.getByText("5거래일 종가 변화")).toBeInTheDocument();
    expect(screen.getByText("매수일 미상 — 기준잔고 · 잔고 등록으로 시작한 기간(입력 평단 기준)")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/하락 위험|재진입 적기/);
  });

  it("같은 종목 알림과 연관 근거를 나눠 보이고 평가는 알림 전체 평가로 쓴다", async () => {
    renderReview();
    await screen.findByRole("heading", { name: /저장된 근거/ });
    const subjectRows = REVIEW.stored_evidence.ledger.items.filter((i) => i.link_kind === "SUBJECT");
    expect(subjectRows).toHaveLength(1);
    expect(screen.getAllByText("내 평가(알림 전체)", { selector: "th" })).toHaveLength(2); // 같은 종목 · 연관 근거 표
    // 같은 알림(event)의 item 두 개 = 알림 1건(중복 발송처럼 세지 않음 · §10-4)
    expect(screen.getByText(/기초지수 묶음 구성 ETF 로 기록된 알림 1건\(항목 2개\)/)).toBeInTheDocument();
    // 사용자 평가를 먼저(§3) · 계약 버전 보존
    const heads = screen.getAllByRole("columnheader").slice(0, 4).map((h) => h.textContent);
    expect(heads).toEqual(["시각", "알림", "내 평가(알림 전체)", "상태"]);
    expect(screen.getAllByText(new RegExp(`· ${subjectRows[0].contract_version}`)).length).toBeGreaterThan(0);
    expect(screen.getByText(/평가는 알림 전체에 대한 평가입니다/)).toBeInTheDocument();
    // 평가 · 메모는 화면에 보인다(설계 §2 · PLAN — 산출물에는 메모를 남기지 않는 것은 backend test)
    const fb = subjectRows[0].feedback.latest!;
    expect(screen.getByText(new RegExp(`· ${fb.memo}`))).toBeInTheDocument();
  });

  it("같은 종목의 관측만 된 알림은 표에 섞지 않고 건수 + 펼치기로 둔다", async () => {
    const base = REVIEW.stored_evidence.ledger.items[0];
    const observed = { ...base, event_id: "ev9", disposition: "not_selected", view: "OBSERVED" as const, view_text: "관측만(본문에 안 실림)" };
    fetchReentryReview.mockResolvedValue({
      ...REVIEW,
      stored_evidence: {
        ...REVIEW.stored_evidence,
        ledger: { ...REVIEW.stored_evidence.ledger, items: [...REVIEW.stored_evidence.ledger.items, observed, { ...observed, event_id: "ev10" }] },
      },
    });
    renderReview();
    const summary = await screen.findByText("관측만 된 알림(본문에 안 실림) 2건");
    const details = summary.closest("details")!;
    expect(details.open).toBe(false);
    expect(within(details).getAllByText("관측만(본문에 안 실림)")).toHaveLength(2);
    expect(screen.getAllByText("전달됨").length).toBeGreaterThan(0); // 본문에 실린 SUBJECT 행은 그대로 표
  });

  it("ML 검토 실행 → 추정값 · 단순 기준 · 검증 오차 · 구간 표 · 산출물", async () => {
    runReentryMl.mockResolvedValue(ML_OK);
    renderReview();
    fireEvent.click(await screen.findByRole("button", { name: "ML 검토 실행" }));
    await screen.findByText(/추정값\(기준일/);
    expect(runReentryMl).toHaveBeenCalledWith(PID, CID);
    expect(screen.getByText("단순 기준(학습 중앙값)")).toBeInTheDocument();
    expect(screen.getByText(new RegExp(ML_OK.result.overall!.verdict_text))).toBeInTheDocument();
    expect(screen.getByText(/연구 추정 · 투자 유효성 미확정 · 이 값은 매수\/매도 지시가 아닙니다/)).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toBeTruthy();
    expect(screen.getByText(/연구 산출물:/)).toHaveTextContent(ML_OK.artifact.folder);
    // 저장일이 늦으면 추정값 옆에 '이 날짜 기준 검토'(§2)
    expect(ML_OK.stale).toBe(true);
    const estimate = screen.getByText(/추정값\(기준일/).closest(".hmx-rv-metric")!;
    expect(within(estimate as HTMLElement).getByText("이 날짜 기준 검토")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ML 검토 다시 실행" })).toBeInTheDocument();
  });

  it("단순 기준보다 오차가 크면 그 문구를 추정값 옆 안내로 보인다", async () => {
    const worse: ReentryMlResponse = {
      ...ML_OK,
      result: {
        ...ML_OK.result,
        overall: { ...ML_OK.result.overall!, verdict: "WORSE", verdict_text: "단순 기준보다 검증 오차 큼" },
      },
    };
    runReentryMl.mockResolvedValue(worse);
    renderReview();
    fireEvent.click(await screen.findByRole("button", { name: "ML 검토 실행" }));
    const note = await screen.findByText(/단순 기준보다 검증 오차 큼/);
    expect(note.className).toContain("hmx-rv-warn");
  });

  it("자료 부족이면 추정값을 보이지 않고 사유와 구간 표만 보인다", async () => {
    runReentryMl.mockResolvedValue(ML_SHORT);
    renderReview();
    fireEvent.click(await screen.findByRole("button", { name: "ML 검토 실행" }));
    await screen.findByText(new RegExp(ML_SHORT.status_text));
    expect(screen.queryByText(/추정값\(기준일/)).toBeNull();
    expect(screen.getAllByText("자료 부족").length).toBeGreaterThan(0);
  });

  it("ML 실패는 오류로 보이고 직전 결과를 남기지 않는다", async () => {
    runReentryMl.mockResolvedValueOnce(ML_OK);
    runReentryMl.mockRejectedValueOnce(
      new ApiRequestError("HTTP 500", 500, { detail: "연구 산출물 저장 실패: OSError — 결과를 보이지 않습니다." }),
    );
    renderReview();
    fireEvent.click(await screen.findByRole("button", { name: "ML 검토 실행" }));
    await screen.findByText(/추정값\(기준일/);
    fireEvent.click(screen.getByRole("button", { name: "ML 검토 다시 실행" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("결과를 보이지 않습니다");
    expect(screen.queryByText(/추정값\(기준일/)).toBeNull();
  });

  it("보유가 바뀌어 기간이 없으면(404) 다시 열라는 문구", async () => {
    fetchReentryReview.mockRejectedValueOnce(
      new ApiRequestError("HTTP 404", 404, { detail: "보유가 바뀌었거나 없는 보유 기간입니다 — History 를 다시 여세요." }),
    );
    renderReview();
    expect(await screen.findByRole("alert")).toHaveTextContent("History 를 다시 여세요");
  });

  it("ML 대상이 아니면 실행 버튼 없이 안내만", async () => {
    fetchReentryReview.mockResolvedValue({ ...REVIEW, ml: { ...REVIEW.ml, available: false } });
    renderReview();
    expect(await screen.findByText(/ML 대상이 아닙니다/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "ML 검토 실행" })).toBeNull();
  });

  it("← History · 이동 링크 · 매매 창 연결(자동 실행 없음)", async () => {
    const p = renderReview();
    await screen.findByRole("heading", { name: /저장된 근거/ });
    fireEvent.click(screen.getByRole("button", { name: /요즘 잘 오르는 ETF/ }));
    expect(p.onNavigate).toHaveBeenCalledWith("market_discovery");
    fireEvent.click(screen.getByRole("button", { name: /받은 알림 기록/ }));
    expect(p.onNavigate).toHaveBeenCalledWith("alert_records");
    fireEvent.click(screen.getByRole("button", { name: /매매 창/ }));
    expect(p.onTrade).toHaveBeenCalledWith(REVIEW.my_trades.position);
    fireEvent.click(screen.getByRole("button", { name: "← History" }));
    expect(p.onBack).toHaveBeenCalled();
    expect(runReentryMl).not.toHaveBeenCalled();
  });
});

describe("History → 재진입 검토 → History", () => {
  const V1_POS = HISTORY_V1.positions[0]; // 기준잔고 · 매매 없음
  const holdings: HoldingItem[] = [
    {
      ticker: V1_POS.ticker,
      name: V1_POS.name,
      account_group: V1_POS.account_group,
      quantity: 3,
      avg_buy_price: 100,
      position_id: V1_POS.position_id,
      cycle_id: V1_POS.cycles[0].cycle_id,
    },
  ];

  it("매매가 없는 기간에도 버튼이 있고 · 검토 창이 History 자리를 대신하며 · 돌아오면 History", async () => {
    fetchTradeHistory.mockResolvedValue(HISTORY_V1);
    fetchEnrichedHoldings.mockResolvedValue({ items: [] });
    const onNavigate = vi.fn();
    render(
      <HoldingsBookSection
        holdings={holdings}
        revision={0}
        status="OK"
        busy={false}
        reloadKey={0}
        onEdit={vi.fn()}
        onChanged={vi.fn()}
        onNavigate={onNavigate}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "History" }));
    const review = await screen.findByRole("button", { name: "재진입 검토" });
    expect(screen.queryByRole("button", { name: "시장 흐름 보기" })).toBeNull(); // 매매 없음 = 시장 흐름 없음
    fireEvent.click(review);
    await waitFor(() => expect(fetchReentryReview).toHaveBeenCalledWith(V1_POS.position_id, V1_POS.cycles[0].cycle_id));
    expect(screen.getAllByRole("dialog")).toHaveLength(1); // 창 위에 창을 겹치지 않는다
    fireEvent.click(await screen.findByRole("button", { name: /요즘 잘 오르는 ETF/ }));
    expect(onNavigate).toHaveBeenCalledWith("market_discovery");
    fireEvent.click(screen.getByRole("button", { name: "← History" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("button", { name: "재진입 검토" })).toBeInTheDocument();
  });

  it("매매가 있는 기간은 시장 흐름 보기와 재진입 검토가 함께 있다", async () => {
    fetchTradeHistory.mockResolvedValue(HISTORY);
    fetchEnrichedHoldings.mockResolvedValue({ items: [] });
    const pos = HISTORY.positions[0];
    render(
      <HoldingsBookSection
        holdings={[{ ...holdings[0], ticker: pos.ticker, name: pos.name, position_id: pos.position_id }]}
        revision={14}
        status="OK"
        busy={false}
        reloadKey={0}
        onEdit={vi.fn()}
        onChanged={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "History" }));
    await waitFor(() => expect(screen.getAllByRole("button", { name: "재진입 검토" })).toHaveLength(2));
    expect(screen.getAllByRole("button", { name: "시장 흐름 보기" })).toHaveLength(2);
  });
});
