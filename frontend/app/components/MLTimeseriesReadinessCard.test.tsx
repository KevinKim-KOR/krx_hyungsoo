// POC6-15 — 「이전 학습용 값 — 쌓인 상태」 카드 시험(가짜 응답 · 서버 없음).
//
// - 순서: 결론 한 줄 → 설명 → 항목 표(버튼 없음).
// - 상태별(불러오는 중 · 불러오기 실패 4종 · 모르는 실패 · 모두 있음 · 모두 없음 · 일부 · 모르는 상태 값 ·
//   항목 0개 · 응답 상태 이상) 결론이 서로 다름.
// - 건수 · 날짜 값은 그대로(쉼표만) · 표 이름 · 칼럼 이름 · 명령 · 응답 원문은 접힌 개발 정보 안.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import type { MlReadinessAxis, MlReadinessResponse } from "@/lib/api";

const fetchMlReadinessLatest = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchMlReadinessLatest: (...a: unknown[]) => fetchMlReadinessLatest(...a),
  };
});

import MLTimeseriesReadinessCard from "./MLTimeseriesReadinessCard";
import { ApiConfigError, ApiRequestError } from "@/lib/api";

// app/api_ml_readiness.py `_build_axes` 의 고정 문장(2026-11-01 실서버 응답과 같은 틀).
function axesFor(etf: number, mkt: number): MlReadinessAxis[] {
  const base = etf > 0 && mkt > 0 ? "available" : etf > 0 || mkt > 0 ? "partial" : "empty";
  const m = mkt > 0 ? "available" : "empty";
  return [
    {
      label: "ETF 가격 시계열",
      status: base,
      note: etf > 0 ? `etf_ml_feature_daily ${etf}건 — return 5/10/20d + close/volume 적재` : "etf_ml_feature_daily 미적재",
    },
    {
      label: "NAV / 괴리율 feature",
      status: base,
      note:
        etf > 0
          ? "etf_ml_feature_daily.nav / nav_market_price / discount_rate_pct + nav_status 컬럼 — latest available ≤ asof 정책"
          : "미적재",
    },
    {
      label: "거래량 / 유동성 feature",
      status: base,
      note: etf > 0 ? "etf_ml_feature_daily.volume + volume_ratio_20d (20일 평균 대비)" : "미적재",
    },
    {
      label: "시장지수 feature",
      status: m,
      note: mkt > 0 ? `market_risk_feature_daily ${mkt}건 — KODEX200 / KOSPI return 1/5/20d` : "market_risk_feature_daily 미적재",
    },
    {
      label: "ETF universe 시장 폭 feature",
      status: m,
      note: mkt > 0 ? "etf_universe_up/down/flat_count + ratio + median_return_1d/5d" : "미적재",
    },
    {
      label: "변동성 feature",
      status: base,
      note:
        etf > 0 && mkt > 0
          ? "etf_ml_feature_daily.volatility_20d (일간 수익률 표준편차) + market_risk_feature_daily.volatility_20d_market_proxy / volatility_expansion_20d"
          : "일부만 적재",
    },
    {
      label: "조정장 전조 feature",
      status: m,
      note:
        mkt > 0
          ? "distance_from_20d_high + down_day_volume_ratio + large_negative_day_proxy + short_term_weakness_proxy + breadth_deterioration_proxy (proxy raw 값. label/threshold 미확정)"
          : "market_risk_feature_daily 미적재",
    },
  ];
}

function resp(etf: number, mkt: number, over: Partial<MlReadinessResponse> = {}): MlReadinessResponse {
  return {
    status: "ok",
    etf_feature_row_count: etf,
    etf_distinct_asof_count: etf > 0 ? 3018 : 0,
    etf_latest_asof: etf > 0 ? "2026-08-27" : null,
    market_risk_row_count: mkt,
    market_risk_latest_asof: mkt > 0 ? "2026-08-27" : null,
    axes: axesFor(etf, mkt),
    ...over,
  };
}

const REAL = resp(1382327, 3018); // 2026-11-01 실서버 응답 값

function conclusionOf(container: HTMLElement): HTMLElement {
  const el = container.querySelector<HTMLElement>('[data-role="conclusion"]');
  if (!el) throw new Error("결론 줄 없음");
  return el;
}

beforeEach(() => {
  fetchMlReadinessLatest.mockReset();
});

describe("MLTimeseriesReadinessCard", () => {
  it("순서 — 결론 → 설명 → 항목 표 · 버튼 없음 · 조회 1회", async () => {
    fetchMlReadinessLatest.mockResolvedValue(REAL);
    const { container } = render(<MLTimeseriesReadinessCard />);
    const table = await screen.findByRole("table");
    const concl = conclusionOf(container);
    const desc = screen.getByText(/이전 실험\(위험 구간 나누기 · 하락 예측 아님\)을 위해 만든 값입니다/);
    const h2 = screen.getByRole("heading", { level: 2, name: "이전 학습용 값 — 쌓인 상태" });
    expect(h2.compareDocumentPosition(concl) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(concl.compareDocumentPosition(desc) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(desc.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const dev = container.querySelector("details.ml-dev-details")!;
    expect(table.compareDocumentPosition(dev) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(fetchMlReadinessLatest).toHaveBeenCalledTimes(1);
    // 사실과 다른 'CLI 로만' 문구 정정 → 다시 만들기 카드 안내
    expect(desc.textContent).toContain("다시 만들기는 아래 「이전 자료와 실험 다시 만들기」에서 합니다.");
    expect(screen.getByText(/이 자료에 없는 것: 공포 · 탐욕 지수, 코스피 변동성 지수/)).toBeInTheDocument();
  });

  it("건수 · 날짜는 응답 값 그대로(쉼표만) — 결론 줄", async () => {
    fetchMlReadinessLatest.mockResolvedValue(REAL);
    const { container } = render(<MLTimeseriesReadinessCard />);
    await screen.findByRole("table");
    const concl = conclusionOf(container);
    expect(within(concl).getByText("7개 항목 모두 있음")).toBeInTheDocument();
    expect(concl.textContent).toContain(
      "마지막 자료일 2026-08-27 · ETF 값 1,382,327건 · 3,018거래일 · 시장 값 3,018건"
    );
  });

  it("ETF 값과 시장 값의 마지막 자료일이 다르면 둘 다 보임", async () => {
    fetchMlReadinessLatest.mockResolvedValue(resp(1382327, 3017, { market_risk_latest_asof: "2026-08-26" }));
    const { container } = render(<MLTimeseriesReadinessCard />);
    await screen.findByRole("table");
    expect(conclusionOf(container).textContent).toContain(
      "마지막 자료일 ETF 값 2026-08-27 · 시장 값 2026-08-26 · ETF 값 1,382,327건 · 3,018거래일 · 시장 값 3,017건"
    );
  });

  it.each<[string, () => Promise<MlReadinessResponse>, string, string]>([
    ["모두 있음", () => Promise.resolve(REAL), "7개 항목 모두 있음", "마지막 자료일 2026-08-27"],
    ["모두 없음", () => Promise.resolve(resp(0, 0)), "7개 항목 모두 없음", "마지막 자료일 - · ETF 값 0건"],
    ["ETF 값만 있음", () => Promise.resolve(resp(1382327, 0)), "7개 항목 중 일부 4 · 없음 3", "시장 값 -"],
    ["시장 값만 있음", () => Promise.resolve(resp(0, 3018)), "7개 항목 중 있음 3 · 일부 4", "ETF 값 -"],
    [
      "모두 일부",
      () => Promise.resolve({ ...REAL, axes: REAL.axes.map((a) => ({ ...a, status: "partial" })) }),
      "7개 항목 모두 일부만 있음",
      "ETF 값 1,382,327건",
    ],
    [
      "모르는 상태 값",
      () => Promise.resolve({ ...REAL, axes: REAL.axes.map((a, i) => (i === 0 ? { ...a, status: "stale" } : a)) }),
      "7개 항목 중 있음 6 · 상태 확인 필요 1",
      "ETF 값 1,382,327건",
    ],
    ["항목 0개", () => Promise.resolve({ ...REAL, axes: [] }), "항목 정보 없음", "ETF 값 1,382,327건"],
    [
      "응답 상태 값 이상",
      () => Promise.resolve({ ...REAL, status: "degraded" as unknown as "ok" }),
      "7개 항목 모두 있음",
      "응답 상태 값 ‘degraded’ — 원인 확인 필요",
    ],
    [
      "불러오기 실패 — HTTP 오류",
      () => Promise.reject(new ApiRequestError("요청 실패: GET /ml/readiness/latest (HTTP 500)", 500, null)),
      "불러오지 못함",
      "서버가 오류로 응답했습니다(HTTP 500)",
    ],
    [
      "불러오기 실패 — 시간 초과",
      () => Promise.reject(new ApiRequestError("요청 시간 초과: GET /ml/readiness/latest (10000ms)", 0, null)),
      "불러오지 못함",
      "서버 응답 시간이 지났습니다",
    ],
    [
      "불러오기 실패 — 연결 안 됨",
      () =>
        Promise.reject(
          new ApiRequestError("네트워크 호출 실패: GET /ml/readiness/latest — Failed to fetch", 0, null)
        ),
      "불러오지 못함",
      "서버에 연결하지 못했습니다",
    ],
    [
      "불러오기 실패 — 설정 오류",
      () => Promise.reject(new ApiConfigError("NEXT_PUBLIC_API_BASE 가 설정되어 있지 않습니다.")),
      "불러오지 못함",
      "화면 설정 오류 — 서버 주소 설정이 없습니다",
    ],
    [
      "불러오기 실패 — 모르는 요청 실패",
      () => Promise.reject(new ApiRequestError("weird thing", 0, null)),
      "불러오지 못함",
      "요청 실패 — 원인 확인 필요 · 원문: 요청 실패(HTTP 0): weird thing",
    ],
    [
      "불러오기 실패 — 모르는 오류",
      () => Promise.reject(new Error("boom")),
      "불러오지 못함",
      "알 수 없는 오류 — 원인 확인 필요 · 원문: 알 수 없는 오류: boom",
    ],
  ])("상태 %s → 결론 배지 · 문장", async (_name, impl, label, text) => {
    fetchMlReadinessLatest.mockImplementation(impl);
    const { container } = render(<MLTimeseriesReadinessCard />);
    const concl = await within(container).findByText(label);
    expect(concl.closest('[data-role="conclusion"]')).not.toBeNull();
    expect(conclusionOf(container).textContent).toContain(text);
  });

  it("불러오는 중 — 결론 '불러오는 중' · 표 없음", () => {
    fetchMlReadinessLatest.mockReturnValue(new Promise(() => {}));
    const { container } = render(<MLTimeseriesReadinessCard />);
    expect(within(conclusionOf(container)).getByText("불러오는 중")).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("표 — 아는 항목은 쉬운 이름 · 상태 있음/일부/없음 · 모르는 항목 · 상태 · 설명은 원문 그대로", async () => {
    const axes = [
      ...axesFor(1382327, 0).slice(0, 4), // 일부 · 일부 · 일부 · 없음
      { label: "새 항목 feature", status: "available", note: "new_col 적재" },
      { label: "변동성 feature", status: "stale", note: "알 수 없는 설명" },
    ];
    fetchMlReadinessLatest.mockResolvedValue(resp(1382327, 0, { axes }));
    render(<MLTimeseriesReadinessCard />);
    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row").slice(1);
    const cells = rows.map((r) => within(r).getAllByRole("cell").map((c) => c.textContent));
    expect(cells).toEqual([
      ["ETF 가격 흐름", "일부", "5 · 10 · 20일 수익률, 종가, 거래량"],
      ["NAV · 괴리율", "일부", "NAV, NAV 기준 시장가, 괴리율(그날 또는 그 전 최신 NAV만 씀)"],
      ["거래량 · 유동성", "일부", "거래량, 20일 평균 대비 거래량"],
      ["시장지수", "없음", "시장 값이 쌓여 있지 않음"],
      ["새 항목 feature", "있음", "new_col 적재"],
      ["변동성", "stale", "알 수 없는 설명"],
    ]);
  });

  it("기본 속성 이름('toString' · 'constructor')도 모르는 값 — 원문 그대로 · 상태 확인 필요로 셈", async () => {
    const axes = [
      { label: "constructor", status: "toString", note: "hasOwnProperty" },
      { label: "변동성 feature", status: "available", note: "constructor" },
    ];
    fetchMlReadinessLatest.mockResolvedValue(resp(1382327, 3018, { axes }));
    const { container } = render(<MLTimeseriesReadinessCard />);
    const table = await screen.findByRole("table");
    const cells = within(table)
      .getAllByRole("row")
      .slice(1)
      .map((r) => within(r).getAllByRole("cell").map((c) => c.textContent));
    expect(cells).toEqual([
      ["constructor", "toString", "hasOwnProperty"],
      ["변동성", "있음", "constructor"],
    ]);
    expect(within(conclusionOf(container)).getByText("2개 항목 중 있음 1 · 상태 확인 필요 1")).toBeInTheDocument();
  });

  it("배지 색 — 섞인 상태 = 주황 · 모르는 상태 값 = 전과 같은 회색 · 있음 = 초록", async () => {
    fetchMlReadinessLatest.mockResolvedValue({
      ...REAL,
      axes: REAL.axes.map((a, i) => (i === 0 ? { ...a, status: "stale" } : a)),
    });
    const { container } = render(<MLTimeseriesReadinessCard />);
    const table = await screen.findByRole("table");
    expect(within(conclusionOf(container)).getByText("7개 항목 중 있음 6 · 상태 확인 필요 1")).toHaveClass(
      "ml-readiness-partial"
    );
    expect(within(table).getByText("stale")).toHaveClass("ml-readiness-missing");
    expect(within(table).getAllByText("있음")[0]).toHaveClass("ml-readiness-available");
  });

  it("응답 상태 값 이상 + 모두 있음 → 배지 주황(초록으로 두지 않음)", async () => {
    fetchMlReadinessLatest.mockResolvedValue({ ...REAL, status: "degraded" as unknown as "ok" });
    const { container } = render(<MLTimeseriesReadinessCard />);
    await screen.findByRole("table");
    expect(within(conclusionOf(container)).getByText("7개 항목 모두 있음")).toHaveClass("ml-readiness-partial");
  });

  it("표 이름 · 칼럼 이름 · 명령 · 응답 원문은 접힌 개발 정보 안", async () => {
    fetchMlReadinessLatest.mockResolvedValue(REAL);
    const { container } = render(<MLTimeseriesReadinessCard />);
    await screen.findByRole("table");
    const dev = container.querySelector<HTMLElement>("details.ml-dev-details")!;
    expect(dev).not.toHaveAttribute("open");
    expect(within(dev).getByText("자세한 정보(개발 정보)").tagName).toBe("SUMMARY");
    for (const id of [
      /etf_ml_feature_daily · market_risk_feature_daily \(SQLite\)/,
      /scripts\/generate_ml_features\.py/,
      /etf_feature_row_count=1382327/,
      /ETF 가격 시계열 \| available \| etf_ml_feature_daily 1382327건 — return 5\/10\/20d \+ close\/volume 적재/,
      /CNN Fear & Greed \/ VKOSPI/,
    ]) {
      const hits = screen.getAllByText(id);
      expect(hits.length).toBeGreaterThan(0);
      for (const h of hits) expect(dev.contains(h)).toBe(true);
    }
  });

  it("불러오기 실패의 원문은 개발 정보에도 남음", async () => {
    fetchMlReadinessLatest.mockRejectedValue(
      new ApiRequestError("요청 실패: GET /ml/readiness/latest (HTTP 503)", 503, null)
    );
    const { container } = render(<MLTimeseriesReadinessCard />);
    await screen.findByText("불러오지 못함");
    const dev = container.querySelector<HTMLElement>("details.ml-dev-details")!;
    expect(within(dev).getByText("오류 원문: 요청 실패(HTTP 503): 요청 실패: GET /ml/readiness/latest (HTTP 503)")).toBeInTheDocument();
    expect(conclusionOf(container).textContent).not.toContain("/ml/readiness/latest");
  });
});
