// POC6-15 — 「상대 상승 참고점수(이전 실험)」 카드 시험(가짜 응답 · 서버 없음 · 2026-11-01).
//
// - 순서: 결론 한 줄 → [참고점수 계산] → 상태 줄 → 응답 문장 → 접힌 개발 정보.
// - 결론(미채택 · 연구용)은 어느 상태에서도 그대로이고, 상태 줄은 상태마다 다른 쉬운 한국어.
// - 숫자 · 날짜 값은 그대로(건수만 쉼표) · 버튼 핸들러 · 막힘 조건(계산 중) 그대로.
// - 모델 이름 · 판정 원문 · 응답 원래 값은 개발 정보 칸 안에.
import { useState } from "react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor, within, act } from "@testing-library/react";
import type { RelativeUpsideRunResult } from "@/lib/api/mlRelativeUpside";

const runRelativeUpsideScore = vi.fn();
vi.mock("@/lib/api/mlRelativeUpside", () => ({
  runRelativeUpsideScore: (...a: unknown[]) => runRelativeUpsideScore(...a),
}));

import RelativeUpsideRunCard from "./RelativeUpsideRunCard";
import { ApiRequestError } from "@/lib/api";

// 백엔드(app/api_ml_relative_upside.py)가 돌려주는 6필드 · 고정 문장 그대로.
const OK: RelativeUpsideRunResult = {
  status: "ok",
  asof_date: "2026-10-30",
  generated_at: "2026-11-01T01:05:12.345678+00:00",
  scored_candidate_count: 1163,
  gpu_execution_used: true,
  message: "상대상승 참고점수 계산이 완료되었습니다.",
};
const OK_NO_GPU: RelativeUpsideRunResult = {
  ...OK,
  gpu_execution_used: false,
  message: "계산은 완료됐지만 GPU 실행은 확인되지 않았습니다.",
};
const FAILED: RelativeUpsideRunResult = {
  status: "failed",
  asof_date: null,
  generated_at: null,
  scored_candidate_count: null,
  gpu_execution_used: null,
  message: "새 점수를 계산하지 못했습니다. 기존 점수는 유지됩니다.",
};
const UNAVAILABLE: RelativeUpsideRunResult = {
  status: "unavailable",
  asof_date: "2026-10-30",
  generated_at: "2026-11-01T01:05:12.345678+00:00",
  scored_candidate_count: 0,
  gpu_execution_used: true,
  message: "계산은 시도했지만 점수를 생성하지 못했습니다. 기존 점수는 유지됩니다.",
};
const UNKNOWN = { ...OK, status: "partial" } as unknown as RelativeUpsideRunResult;
const REQUEST_ERROR_TEXT = "새 점수를 계산하지 못했습니다. 기존 점수는 유지됩니다.";

/** MLView 와 같은 방식으로 결과 · 오류를 들고 있는 부모(결과 성공 시 오류 지움). */
function Harness({
  initial = null,
  initialError = null,
}: {
  initial?: RelativeUpsideRunResult | null;
  initialError?: string | null;
}) {
  const [result, setResult] = useState<RelativeUpsideRunResult | null>(initial);
  const [err, setErr] = useState<string | null>(initialError);
  return (
    <RelativeUpsideRunCard
      result={result}
      errorMessage={err}
      onResult={(r) => {
        setResult(r);
        setErr(null);
      }}
      onError={setErr}
    />
  );
}

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

function card(container: HTMLElement): HTMLElement {
  const el = container.querySelector("section");
  if (!el) throw new Error("카드를 찾지 못했다");
  return el as HTMLElement;
}
const conclusionOf = (c: HTMLElement) =>
  c.querySelector('[data-role="conclusion"]') as HTMLElement;
const devOf = (c: HTMLElement) => c.querySelector("details.ml-dev-details") as HTMLElement;
const statusLineOf = () => screen.getByTestId("ru-status-line");
const follows = (a: Node, b: Node) =>
  Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

beforeEach(() => {
  runRelativeUpsideScore.mockReset();
});

describe("RelativeUpsideRunCard — POC6-15 배치 · 쉬운 한국어", () => {
  it("순서 = 제목 → 결론 → 버튼 → 상태 줄 → 응답 문장 → 개발 정보", () => {
    const { container } = render(<Harness initial={OK} />);
    const c = card(container);
    const h2 = screen.getByRole("heading", { level: 2, name: "상대 상승 참고점수(이전 실험)" });
    const concl = conclusionOf(c);
    const btn = screen.getByRole("button", { name: "참고점수 계산" });
    const line = statusLineOf();
    const msg = screen.getByText(OK.message);
    const dev = devOf(c);
    expect(follows(h2, concl)).toBe(true);
    expect(follows(concl, btn)).toBe(true);
    expect(follows(btn, line)).toBe(true);
    expect(follows(line, msg)).toBe(true);
    expect(follows(msg, dev)).toBe(true);
    // 결론 = 당시 판정(미채택) · 연구용 — 기본 화면(접힘 밖)에 보인다.
    expect(within(concl).getByText("미채택")).toBeInTheDocument();
    expect(within(concl).getByText("2026-08-29 판정 · 연구용 기준선 · 투자 판단에 쓰지 않음")).toBeInTheDocument();
    expect(concl.closest("details")).toBeNull();
  });

  // 상태별(응답 없음 · 완료 · 실패 · 결과를 사용할 수 없음 · 모르는 값 · 빈 값 · 요청 오류) 상태 줄 + 요청 오류 칸.
  const CASES: {
    name: string;
    initial: RelativeUpsideRunResult | null;
    error?: string;
    badge: string;
    note: string | null;
  }[] = [
    { name: "응답 없음(아직 계산 안 함)", initial: null, badge: "아직 계산 안 함", note: null },
    { name: "완료", initial: OK, badge: "완료", note: null },
    { name: "실패", initial: FAILED, badge: "실패", note: "원인 확인 필요" },
    { name: "결과를 사용할 수 없음", initial: UNAVAILABLE, badge: "결과를 사용할 수 없음", note: null },
    {
      name: "모르는 상태 값 = 원래 값",
      initial: UNKNOWN,
      badge: "partial",
      note: "알 수 없는 상태 · 확인 필요",
    },
    {
      name: "빈 상태 값",
      initial: { ...OK, status: "" } as unknown as RelativeUpsideRunResult,
      badge: "빈 값",
      note: "알 수 없는 상태 · 확인 필요",
    },
    {
      // 응답은 받았는데 상태 값이 없다 — '아직 계산 안 함'(응답 없음)과 합치지 않는다.
      name: "응답에 상태 값 없음(null)",
      initial: { ...OK, status: null } as unknown as RelativeUpsideRunResult,
      badge: "응답에 없음",
      note: "알 수 없는 상태 · 확인 필요",
    },
    {
      name: "글자가 아닌 상태 값 = 원래 값",
      initial: { ...OK, status: 3 } as unknown as RelativeUpsideRunResult,
      badge: "3",
      note: "알 수 없는 상태 · 확인 필요",
    },
    {
      name: "요청 오류(이전 결과 없음)",
      initial: null,
      error: REQUEST_ERROR_TEXT,
      badge: "아직 계산 안 함",
      note: null,
    },
    {
      name: "요청 오류(이전 완료 결과 유지)",
      initial: OK,
      error: REQUEST_ERROR_TEXT,
      badge: "완료",
      note: null,
    },
  ];

  it.each(CASES)("상태 $name — 결론은 그대로 · 상태 글자 구분", ({ initial, error, badge, note }) => {
    const { container } = render(<Harness initial={initial} initialError={error ?? null} />);
    const c = card(container);
    expect(within(conclusionOf(c)).getByText("미채택")).toBeInTheDocument();
    expect(screen.getByTestId("ru-status")).toHaveTextContent(new RegExp(`^${badge}$`));
    const line = statusLineOf();
    if (note) expect(within(line).getByText(note)).toBeInTheDocument();
    else {
      expect(within(line).queryByText("원인 확인 필요")).toBeNull();
      expect(within(line).queryByText("알 수 없는 상태 · 확인 필요")).toBeNull();
    }
    const reqErr = screen.queryByTestId("ru-request-error");
    if (error) {
      expect(reqErr).toHaveTextContent(`계산 요청 오류 · 원인 확인 필요 — ${error}`);
    } else {
      expect(reqErr).toBeNull();
    }
  });

  it("상태마다 화면 글자(상태 줄 + 요청 오류)가 서로 다르다 · 계산 중 포함", async () => {
    const seen: string[] = [];
    for (const k of CASES) {
      const { unmount } = render(<Harness initial={k.initial} initialError={k.error ?? null} />);
      seen.push(
        `${statusLineOf().textContent}|${screen.queryByTestId("ru-request-error")?.textContent ?? ""}`,
      );
      unmount();
    }
    const d = deferred<RelativeUpsideRunResult>();
    runRelativeUpsideScore.mockReturnValue(d.promise);
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "참고점수 계산" }));
    expect(await screen.findByTestId("ru-status")).toHaveTextContent(/^계산 중$/);
    seen.push(`${statusLineOf().textContent}|`);
    expect(new Set(seen).size).toBe(seen.length);
    await act(async () => d.resolve(OK));
  });

  it("숫자 · 날짜 값 그대로(건수만 쉼표) · 시간대 없는 시각은 받은 글자 그대로", () => {
    const { unmount } = render(
      <Harness initial={{ ...OK, scored_candidate_count: 1382327 }} />,
    );
    const line = statusLineOf();
    expect(within(line).getByText("2026-10-30")).toBeInTheDocument();
    expect(within(line).getByText("2026-11-01 10:05")).toBeInTheDocument(); // 01:05 UTC → 한국 시각
    expect(within(line).getByText("1,382,327개 후보")).toBeInTheDocument();
    expect(within(line).getByText("확인됨")).toBeInTheDocument();
    unmount();

    const r2 = render(
      <Harness
        initial={{ ...OK_NO_GPU, generated_at: "2026-11-01 10:05:12", scored_candidate_count: 0 }}
      />,
    );
    expect(within(statusLineOf()).getByText("2026-11-01 10:05:12")).toBeInTheDocument();
    expect(within(statusLineOf()).getByText("0개 후보")).toBeInTheDocument(); // 0 은 '—' 아님
    expect(within(statusLineOf()).getByText("확인되지 않음")).toBeInTheDocument();
    expect(screen.getByText(OK_NO_GPU.message)).toBeInTheDocument();
    r2.unmount();

    render(<Harness initial={FAILED} />);
    // 기준일 · 마지막 계산 · 점수 반영 · GPU 계산 = 값 없음 표시 4칸.
    expect(within(statusLineOf()).getAllByText("—")).toHaveLength(4);
    expect(screen.getByText(FAILED.message)).toBeInTheDocument();
  });

  it("버튼 = 같은 API 한 번 · 계산 중에는 막힘(색 포함) · 끝나면 결과 표시", async () => {
    const d = deferred<RelativeUpsideRunResult>();
    runRelativeUpsideScore.mockReturnValue(d.promise);
    render(<Harness />);
    const btn = screen.getByRole("button", { name: "참고점수 계산" });
    expect(btn).toBeEnabled();
    expect(btn).toHaveStyle({ backgroundColor: "#0284c7", cursor: "pointer" });

    fireEvent.click(btn);
    const busy = await screen.findByRole("button", { name: "계산 진행 중..." });
    expect(busy).toBeDisabled();
    expect(busy).toHaveStyle({ backgroundColor: "#9ca3af", cursor: "not-allowed" });
    fireEvent.click(busy);
    expect(runRelativeUpsideScore).toHaveBeenCalledTimes(1);
    expect(runRelativeUpsideScore).toHaveBeenCalledWith();

    await act(async () => d.resolve(OK));
    expect(screen.getByRole("button", { name: "참고점수 계산" })).toBeEnabled();
    expect(screen.getByTestId("ru-status")).toHaveTextContent(/^완료$/);
    expect(within(statusLineOf()).getByText("1,163개 후보")).toBeInTheDocument();
  });

  it("요청 오류 = 같은 사용자 문장 · 이전 결과 유지 · 다음 성공 때 오류 지움", async () => {
    runRelativeUpsideScore.mockRejectedValueOnce(new ApiRequestError("boom", 500, null));
    render(<Harness initial={OK} />);
    fireEvent.click(screen.getByRole("button", { name: "참고점수 계산" }));
    const reqErr = await screen.findByTestId("ru-request-error");
    expect(reqErr).toHaveTextContent(`계산 요청 오류 · 원인 확인 필요 — ${REQUEST_ERROR_TEXT}`);
    expect(screen.getByTestId("ru-status")).toHaveTextContent(/^완료$/); // 이전 결과 유지
    expect(screen.queryByText(/boom/)).toBeNull(); // 원문 오류는 기본 화면에 없음(기존 계약)

    runRelativeUpsideScore.mockResolvedValueOnce(OK_NO_GPU);
    fireEvent.click(screen.getByRole("button", { name: "참고점수 계산" }));
    await waitFor(() => expect(screen.queryByTestId("ru-request-error")).toBeNull());
    expect(runRelativeUpsideScore).toHaveBeenCalledTimes(2);
  });

  it("모델 이름 · 판정 원문 · 응답 원래 값은 개발 정보 칸 안에만", () => {
    const { container } = render(<Harness initial={OK} />);
    const c = card(container);
    const dev = devOf(c);
    expect(dev).not.toBeNull();
    expect(dev).not.toHaveAttribute("open");
    expect(dev).toHaveTextContent("relative_upside_v0");
    expect(dev).toHaveTextContent("REJECT(2026-08-29 POC3-ML-02)");
    expect(dev).toHaveTextContent('status = "ok"');
    expect(dev).toHaveTextContent('generated_at = "2026-11-01T01:05:12.345678+00:00"');
    expect(dev).toHaveTextContent("scored_candidate_count = 1163");
    expect(dev).toHaveTextContent("gpu_execution_used = true");
    // 접힘 칸 밖(기본 화면)에는 옮긴 식별자가 남아 있지 않다.
    const outside = c.cloneNode(true) as HTMLElement;
    outside.querySelector("details.ml-dev-details")?.remove();
    const text = outside.textContent ?? "";
    for (const id of ["relative_upside_v0", "REJECT", "generated_at", "2026-11-01T01:05"]) {
      expect(text).not.toContain(id);
    }
  });
});
