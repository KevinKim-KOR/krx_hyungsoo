// POC6-15 — 「이전 자료 점검」 카드 시험(가짜 응답 · 서버 없음).
//
// - 순서: 제목 → 결론 한 줄 → 설명 → 표 → 접힌 개발 정보.
// - 상태마다 다른 쉬운 한국어 결론(불러오는 중 · 불러오기 실패 4종 · 결과 없음 · 파일 손상 · 응답에 결과 없음 ·
//   정상 · 주의 · 오류 · 모르는 상태 = 원문).
// - 숫자 · 날짜 · 비율 자릿수 그대로(건수만 쉼표) · 경고는 본문에 쉬운 말 · 원문 · 경로 · 명령은 개발 정보 안.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import type { MlFeatureSanityResponse, MlSanitySnapshot } from "@/lib/api";

const fetchMlFeatureSanityLatest = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchMlFeatureSanityLatest: (...a: unknown[]) => fetchMlFeatureSanityLatest(...a),
  };
});

import MLFeatureSanityCard from "./MLFeatureSanityCard";
import { ApiConfigError, ApiRequestError } from "@/lib/api";

// 2026-11-01 실서버 GET /ml/feature-sanity/latest 응답에서 옮긴 값(견본 2행만).
const W_ROWS = "ticker별 row 누락: 1056개 ticker 의 row 수가 trading_days×0.95 미만";
const W_DROP = "asof별 ticker count 급감: 817건 (median=357 의 0.7 미만)";
const W_NULL1 = "null ratio > 0.5: down_day_volume_ratio = 0.984095";
const W_NULL2 = "null ratio > 0.5: large_negative_day_proxy = 0.984095";
const PATH = "state/ml/ml_feature_sanity_latest.json";

function snap(over: Partial<MlSanitySnapshot> = {}): MlSanitySnapshot {
  return {
    generated_at: "2026-08-30T14:38:39Z",
    feature_asof_range: { start: "2014-05-12", end: "2026-08-27", trading_days: 3018 },
    etf_feature_row_count: 1382327,
    market_risk_row_count: 3018,
    checked_ticker_count: 10,
    sampled_tickers: ["069500", "252670"],
    sanity_status: "warn",
    coverage_checks: {
      status: "warn",
      latest_asof_matches_readiness: true,
      tickers_with_missing_rows: 1056,
      warnings: [W_ROWS, W_DROP],
      errors: [],
    },
    calculation_checks: {
      status: "ok",
      checked_ticker_count: 10,
      checked_fields: [
        "return_5d",
        "return_10d",
        "return_20d",
        "excess_return_5d_vs_kodex200",
        "excess_return_10d_vs_kodex200",
        "excess_return_20d_vs_kodex200",
        "volatility_20d",
        "drawdown_20d",
        "volume_ratio_20d",
      ],
      warnings: [],
      errors: [],
    },
    nav_join_checks: {
      status: "ok",
      future_nav_join_count: 0,
      unavailable_ratio: 0.958675,
      same_asof_count: 6902,
      past_latest_count: 50223,
      warnings: [],
      errors: [],
    },
    risk_proxy_checks: {
      status: "warn",
      all_null_asof_count: 0,
      warnings: [W_NULL1, W_NULL2],
      errors: [],
    },
    sample_rows: [
      {
        ticker: "069500",
        name: "KODEX 200",
        asof: "2026-08-27",
        return_5d: 0.8734633515112389,
        return_20d: 22.04081632653061,
        excess_return_20d_vs_kodex200: 0.0,
        volatility_20d: 6.583040843995929,
        drawdown_20d: -0.8404506632745723,
        nav_discount_rate_pct: -0.273224043715847,
        nav_status: "ok",
      },
      {
        ticker: "252670",
        name: "KODEX 200선물인버스2X",
        asof: "2026-08-27",
        return_5d: -1.3157894736842146,
        return_20d: -45.652173913043484,
        excess_return_20d_vs_kodex200: -67.6929902395741,
        volatility_20d: 12.407335522574018,
        drawdown_20d: -47.55244755244755,
        nav_discount_rate_pct: 0.0,
        nav_status: "unavailable",
      },
    ],
    warnings: [W_ROWS, W_DROP, W_NULL1, W_NULL2],
    errors: [],
    ...over,
  };
}

function ok(s: MlSanitySnapshot = snap()): MlFeatureSanityResponse {
  return { status: "ok", snapshot_path: PATH, snapshot: s, message: null };
}

function conclusion(): HTMLElement {
  const el = document.querySelector<HTMLElement>('[data-role="conclusion"]');
  expect(el).not.toBeNull();
  return el!;
}

function devDetails(container: HTMLElement): HTMLDetailsElement {
  const d = container.querySelector<HTMLDetailsElement>("details.ml-dev-details");
  expect(d).not.toBeNull();
  return d!;
}

function outsideDevText(container: HTMLElement): string {
  const clone = container.cloneNode(true) as HTMLElement;
  clone.querySelector("details.ml-dev-details")?.remove();
  return clone.textContent ?? "";
}

beforeEach(() => {
  fetchMlFeatureSanityLatest.mockReset();
});

describe("MLFeatureSanityCard", () => {
  it("순서 — 제목 → 결론 → 설명 → 점검 표 · 견본 표 → 개발 정보 · 조회는 마운트 때 1회", async () => {
    fetchMlFeatureSanityLatest.mockResolvedValue(ok());
    const { container } = render(<MLFeatureSanityCard />);
    await screen.findByText("견본 ETF(마지막 자료일)");
    expect(fetchMlFeatureSanityLatest).toHaveBeenCalledTimes(1);
    const h2 = screen.getByRole("heading", { level: 2, name: "이전 자료 점검" });
    const concl = conclusion();
    const desc = container.querySelector('[data-role="description"]')!;
    const tables = screen.getAllByRole("table");
    const dev = devDetails(container);
    expect(tables).toHaveLength(2);
    const chain: Element[] = [h2, concl, desc, tables[0], tables[1], dev];
    for (let i = 0; i < chain.length - 1; i++) {
      expect(chain[i].compareDocumentPosition(chain[i + 1]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
    expect(desc).toHaveTextContent("「이전 자료와 실험 다시 만들기」에서 합니다");
    expect(desc.textContent).not.toContain("CLI");
  });

  type Case = {
    name: string;
    setup: () => void;
    label: string;
    text: string;
    body?: string;
  };
  const cases: Case[] = [
    {
      name: "불러오는 중",
      setup: () => fetchMlFeatureSanityLatest.mockReturnValue(new Promise(() => {})),
      label: "불러오는 중",
      text: "점검 결과를 불러오는 중입니다.",
    },
    {
      name: "불러오기 실패 — 서버 오류(HTTP 500)",
      setup: () =>
        fetchMlFeatureSanityLatest.mockRejectedValue(
          new ApiRequestError("요청 실패: GET /ml/feature-sanity/latest (HTTP 500)", 500, null)
        ),
      label: "불러오지 못함",
      text: "서버가 오류로 답해 점검 결과를 불러오지 못했습니다(HTTP 500).",
    },
    {
      name: "불러오기 실패 — 연결 실패(HTTP 0)",
      setup: () =>
        fetchMlFeatureSanityLatest.mockRejectedValue(
          new ApiRequestError("네트워크 호출 실패: GET /ml/feature-sanity/latest — x", 0, null)
        ),
      label: "불러오지 못함",
      text: "서버에 연결하지 못해 점검 결과를 불러오지 못했습니다.",
    },
    {
      name: "불러오기 실패 — 시간 초과(HTTP 0)",
      setup: () =>
        fetchMlFeatureSanityLatest.mockRejectedValue(
          new ApiRequestError("요청 시간 초과: GET /ml/feature-sanity/latest (10000ms)", 0, null)
        ),
      label: "불러오지 못함",
      text: "서버 응답 시간이 지나 점검 결과를 불러오지 못했습니다.",
    },
    {
      name: "불러오기 실패 — 화면 설정",
      setup: () => fetchMlFeatureSanityLatest.mockRejectedValue(new ApiConfigError("no base")),
      label: "불러오지 못함",
      text: "화면 설정 오류로 점검 결과를 불러오지 못했습니다.",
    },
    {
      name: "불러오기 실패 — 모르는 요청 실패(HTTP 0 · 원문 함께)",
      setup: () =>
        fetchMlFeatureSanityLatest.mockRejectedValue(new ApiRequestError("weird transport", 0, null)),
      label: "불러오지 못함",
      text: "요청이 실패해 점검 결과를 불러오지 못했습니다 · 원인 확인 필요. 원문: 요청 실패(HTTP 0): weird transport",
    },
    {
      name: "불러오기 실패 — 알 수 없는 오류(원문 함께)",
      setup: () => fetchMlFeatureSanityLatest.mockRejectedValue(new Error("boom")),
      label: "불러오지 못함",
      text: "알 수 없는 오류로 점검 결과를 불러오지 못했습니다 · 원인 확인 필요. 원문: 알 수 없는 오류: boom",
    },
    {
      name: "결과 파일 없음(empty)",
      setup: () =>
        fetchMlFeatureSanityLatest.mockResolvedValue({
          status: "empty",
          snapshot_path: PATH,
          snapshot: null,
          message:
            "sanity snapshot 미생성. CLI 'python scripts/check_ml_feature_sanity.py' 를 1회 실행하면 본 화면에 검산 결과가 표시됩니다.",
        }),
      label: "점검 결과 없음",
      text: "아직 점검 결과가 없습니다.",
      body: "「이전 자료와 실험 다시 만들기」를 실행하면 점검 결과가 생깁니다.",
    },
    {
      name: "결과 파일 손상(error)",
      setup: () =>
        fetchMlFeatureSanityLatest.mockResolvedValue({
          status: "error",
          snapshot_path: PATH,
          snapshot: null,
          message: "snapshot 파일이 손상되어 읽을 수 없습니다 (json_decode_failed): Expecting value",
        }),
      label: "파일 손상",
      text: "점검 결과 파일이 손상되어 읽을 수 없습니다.",
      body: "점검 결과 파일은 있지만 내용을 읽을 수 없습니다.",
    },
    {
      name: "응답 상태 ok 인데 결과 없음",
      setup: () =>
        fetchMlFeatureSanityLatest.mockResolvedValue({
          status: "ok",
          snapshot_path: PATH,
          snapshot: null,
          message: null,
        }),
      label: "확인 필요",
      text: "응답에 점검 결과가 없습니다(응답 상태 ok).",
    },
    {
      name: "정상(ok)",
      setup: () => fetchMlFeatureSanityLatest.mockResolvedValue(ok(snap({ sanity_status: "ok", warnings: [] }))),
      label: "정상",
      text: "경고 0건 · 오류 0건 · 마지막 자료일 2026-08-27",
    },
    {
      name: "주의(warn)",
      setup: () => fetchMlFeatureSanityLatest.mockResolvedValue(ok()),
      label: "주의",
      text: "경고 4건 · 오류 0건 · 마지막 자료일 2026-08-27",
    },
    {
      name: "오류(error)",
      setup: () =>
        fetchMlFeatureSanityLatest.mockResolvedValue(
          ok(snap({ sanity_status: "error", errors: ["all-null risk proxy asof=2026-08-27"] }))
        ),
      label: "오류",
      text: "경고 4건 · 오류 1건 · 마지막 자료일 2026-08-27",
    },
    {
      name: "모르는 점검 상태 = 원문",
      setup: () => fetchMlFeatureSanityLatest.mockResolvedValue(ok(snap({ sanity_status: "stale" }))),
      label: "stale",
      text: "알 수 없는 점검 상태 · 경고 4건",
    },
  ];

  it.each(cases)("상태별 결론 — $name", async ({ setup, label, text, body }) => {
    setup();
    render(<MLFeatureSanityCard />);
    if (label !== "불러오는 중") {
      // 불러오기가 끝나면 결론 배지가 '불러오는 중'에서 바뀐다.
      await waitFor(() => expect(conclusion()).not.toHaveTextContent("불러오는 중"));
    }
    const concl = conclusion();
    expect(within(concl).getByText(label)).toBeInTheDocument();
    expect(concl).toHaveTextContent(text);
    if (body) expect(screen.getByText(body, { exact: false })).toBeInTheDocument();
  });

  it("상태마다 결론 배지 · 문장이 서로 다름(불러오기 실패 6종은 같은 배지 · 결론 문장이 다름)", () => {
    const keys = new Set(cases.map((c) => `${c.label}|${c.text}`));
    expect(keys.size).toBe(cases.length);
    const failTexts = cases.filter((c) => c.label === "불러오지 못함").map((c) => c.text);
    expect(new Set(failTexts).size).toBe(6);
    const labels = new Set(cases.filter((c) => c.label !== "불러오지 못함").map((c) => c.label));
    expect(labels.size).toBe(cases.filter((c) => c.label !== "불러오지 못함").length);
    expect(labels.has("실패")).toBe(false); // 주의(warn)를 '실패'로 바꾸지 않음
  });

  it("숫자 · 날짜 · 비율 그대로 — 건수만 쉼표 · NAV 없는 비율 자릿수 유지 · 견본 값 서식 그대로", async () => {
    fetchMlFeatureSanityLatest.mockResolvedValue(ok());
    const { container } = render(<MLFeatureSanityCard />);
    await screen.findByText("견본 ETF(마지막 자료일)");
    const concl = conclusion();
    expect(concl).toHaveTextContent(
      "경고 4건 · 오류 0건 · 마지막 자료일 2026-08-27 · 3,018거래일 · ETF 1,382,327줄 · 시장 3,018줄 · 견본 10종목 검산"
    );
    const [checks, sample] = screen.getAllByRole("table");
    const rows = within(checks).getAllByRole("row");
    expect(rows[1]).toHaveTextContent(
      "자료 기간 · 빠진 줄주의2014-05-12 → 2026-08-27 · ETF 값과 시장 값의 마지막 날짜가 같음 · 경고 2건(아래)"
    );
    expect(rows[2]).toHaveTextContent("계산 검산정상다시 계산해 비교하는 값 9개 · 경고 0 · 오류 0");
    expect(rows[3]).toHaveTextContent(
      "NAV 연결정상미래 날짜 NAV를 쓴 줄 0 · NAV가 없는 줄의 비율 95.8675% · 같은 날 NAV로 연결 6,902줄 · 그 전 최신 NAV로 연결 50,223줄"
    );
    expect(rows[4]).toHaveTextContent("위험 신호 값주의모든 값이 빈 날 0일 · 빈 비율이 기준을 넘은 값 2개 · 경고 2건(아래)");
    const r1 = within(sample).getAllByRole("row")[1];
    expect(r1).toHaveTextContent("069500KODEX 200+0.87%+22.04%0.00%6.5830-0.84%-0.27%");
    const r2 = within(sample).getAllByRole("row")[2];
    expect(r2).toHaveTextContent("252670KODEX 200선물인버스2X-1.32%-45.65%-67.69%12.4073-47.55%0.00% (NAV 없음)");
    expect(screen.getByText("점검한 시각 2026-08-30 23:38:39")).toBeInTheDocument();
    expect(devDetails(container)).toHaveTextContent("unavailable_ratio=0.958675");
  });

  it("계산 검산 불가(KODEX 200 자료 없음) — 표가 '다시 계산했다'고 쓰지 않고 오류는 쉬운 말로 본문에", async () => {
    const s = snap();
    const kodexErr = "KODEX200 시계열을 읽을 수 없음 — calculation check 불가";
    fetchMlFeatureSanityLatest.mockResolvedValue(
      ok({
        ...s,
        sanity_status: "error",
        checked_ticker_count: 0,
        calculation_checks: { ...s.calculation_checks, status: "error", checked_ticker_count: 0, errors: [kodexErr] },
        errors: [kodexErr],
      })
    );
    render(<MLFeatureSanityCard />);
    const [checks] = await screen.findAllByRole("table");
    const row = within(checks).getAllByRole("row")[2];
    expect(row).toHaveTextContent("계산 검산오류다시 계산해 비교하는 값 9개 · 경고 0 · 오류 1");
    expect(row.textContent).not.toContain("개 값을 다시 계산");
    expect(conclusion()).toHaveTextContent("견본 0종목 검산");
    expect(screen.getByText("KODEX 200 가격 자료를 읽을 수 없어 계산 검산을 못 함")).toBeInTheDocument();
  });

  it("불러오기 실패 — 결론이 설명보다 앞 · 원문은 개발 정보 안(아는 실패는 본문에 원문 없음)", async () => {
    fetchMlFeatureSanityLatest.mockRejectedValue(
      new ApiRequestError("요청 실패: GET /ml/feature-sanity/latest (HTTP 503)", 503, null)
    );
    const { container } = render(<MLFeatureSanityCard />);
    await waitFor(() => expect(conclusion()).toHaveTextContent("HTTP 503"));
    const desc = container.querySelector('[data-role="description"]')!;
    expect(conclusion().compareDocumentPosition(desc) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const dev = devDetails(container);
    expect(desc.compareDocumentPosition(dev) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(dev.textContent).toContain("오류 원문: 요청 실패(HTTP 503): 요청 실패: GET /ml/feature-sanity/latest (HTTP 503)");
    expect(outsideDevText(container)).not.toContain("GET /ml/feature-sanity/latest");
  });

  it.each([
    [0.5, "50%"],
    [0, "0%"],
    [1, "100%"],
    [0.000001, "0.0001%"],
    [1e-7, "1e-7"], // 지수 표기는 원래 값 그대로
  ])("NAV 없는 비율 %s → %s(자릿수를 버리지 않음)", async (ratio, shown) => {
    const s = snap();
    fetchMlFeatureSanityLatest.mockResolvedValue(
      ok({ ...s, nav_join_checks: { ...s.nav_join_checks, unavailable_ratio: ratio } })
    );
    render(<MLFeatureSanityCard />);
    const [checks] = await screen.findAllByRole("table");
    expect(within(checks).getAllByRole("row")[3]).toHaveTextContent(`NAV가 없는 줄의 비율 ${shown} ·`);
  });

  it("경고 · 오류 — 본문에 쉬운 말(아는 틀) · 모르는 문장은 원문(오류는 원인 확인 필요) · 원문은 개발 정보 안", async () => {
    const unknownWarn = "something new happened";
    const unknownErr = "unexpected failure X";
    const knownErr = "all-null risk proxy asof=2026-08-27";
    fetchMlFeatureSanityLatest.mockResolvedValue(
      ok(snap({ sanity_status: "error", warnings: [W_ROWS, W_DROP, W_NULL1, W_NULL2, unknownWarn], errors: [knownErr, unknownErr] }))
    );
    const { container } = render(<MLFeatureSanityCard />);
    await screen.findByText("경고 5건");
    expect(screen.getByText("오류 2건")).toBeInTheDocument();
    expect(screen.getByText("줄 수가 모자란 종목 1,056개(거래일 수의 95% 미만)")).toBeInTheDocument();
    expect(screen.getByText("그날 종목 수가 크게 줄어든 날 817일(가운데 값 357종목의 70% 미만)")).toBeInTheDocument();
    expect(screen.getByText("빈 값 비율이 0.5를 넘음: 하락일 거래량 비율 = 0.984095")).toBeInTheDocument();
    expect(screen.getByText("빈 값 비율이 0.5를 넘음: 큰 하락일 신호 = 0.984095")).toBeInTheDocument();
    expect(screen.getByText(unknownWarn)).toBeInTheDocument();
    expect(screen.getByText("위험 신호 값이 모두 빈 날: 2026-08-27")).toBeInTheDocument();
    expect(screen.getByText(`${unknownErr} · 원인 확인 필요`)).toBeInTheDocument();

    const dev = devDetails(container);
    const outside = outsideDevText(container);
    for (const raw of [W_ROWS, W_DROP, W_NULL1, W_NULL2, knownErr]) {
      expect(dev.textContent).toContain(raw);
      expect(outside).not.toContain(raw);
    }
  });

  it("개발 식별자(파일 경로 · 원래 시각 · 점검 이름 · 명령 · 필드 이름)는 개발 정보 안에만", async () => {
    fetchMlFeatureSanityLatest.mockResolvedValue(ok());
    const { container } = render(<MLFeatureSanityCard />);
    await screen.findByText("견본 ETF(마지막 자료일)");
    const dev = devDetails(container);
    expect(dev.tagName).toBe("DETAILS");
    expect(dev.open).toBe(false);
    const outside = outsideDevText(container);
    for (const id of [
      PATH,
      "2026-08-30T14:38:39Z",
      "coverage · calculation · nav join · risk proxy",
      "scripts/check_ml_feature_sanity.py",
      "down_day_volume_ratio",
      "volatility_20d",
      "252670=unavailable",
    ]) {
      expect(dev.textContent).toContain(id);
      expect(outside).not.toContain(id);
    }
  });

  it("결과 없음 · 파일 손상 — 메시지 원문 · 경로는 개발 정보 안 · 모르는 손상 메시지는 원문 + 원인 확인 필요", async () => {
    const missing =
      "sanity snapshot 미생성. CLI 'python scripts/check_ml_feature_sanity.py' 를 1회 실행하면 본 화면에 검산 결과가 표시됩니다.";
    fetchMlFeatureSanityLatest.mockResolvedValue({ status: "empty", snapshot_path: PATH, snapshot: null, message: missing });
    const a = render(<MLFeatureSanityCard />);
    await screen.findByText("점검 결과 없음");
    expect(devDetails(a.container).textContent).toContain(missing);
    expect(outsideDevText(a.container)).not.toContain(PATH);
    expect(outsideDevText(a.container)).not.toContain("CLI");
    a.unmount();

    fetchMlFeatureSanityLatest.mockResolvedValue({
      status: "error",
      snapshot_path: PATH,
      snapshot: null,
      message: "disk read failed",
    });
    const b = render(<MLFeatureSanityCard />);
    await screen.findByText("파일 손상");
    expect(screen.getByText("disk read failed · 원인 확인 필요")).toBeInTheDocument();
    expect(devDetails(b.container).textContent).toContain("disk read failed");
  });
});
