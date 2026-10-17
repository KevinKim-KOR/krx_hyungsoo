// POC5-21 — 「요즘 잘 오르는 ETF」 후보 수익률의 실제 계산 기간 표시(카드 · 표 · 요약 · 복사문).
// 설계 V1 §3 · §5-3 · PLAN 판정(2026-10-17 · Q1 · Q3 · §2 시험 보충).
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within, act } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";
import type {
  MarketCandidate,
  MarketContext,
  MarketContextKodex200,
  MarketPeriodReturn,
} from "@/lib/api";

const fetchMarketTopnLatest = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchMarketTopnLatest: (...a: unknown[]) => fetchMarketTopnLatest(...a),
  };
});

import CandidateCards from "./CandidateCards";
import CandidateTable from "./CandidateTable";
import MarketDiscoveryView from "./MarketDiscoveryView";
import { buildMarketDiscoveryCopyText } from "@/lib/marketDiscoveryCopyText";

const ASOF = "2026-10-14";

function r(pct: number, start?: string, end?: string): MarketPeriodReturn {
  return {
    return_pct: pct,
    basis_start_date: start ?? null,
    basis_end_date: ASOF,
    ...(start ? { price_start_date: start } : {}),
    ...(end ? { price_end_date: end } : {}),
  };
}

const KODEX: MarketContextKodex200 = {
  status: "ok",
  return_1m_pct: -15.06,
  return_3m_pct: -13.23,
  return_1m_start_date: "2026-09-10",
  return_3m_start_date: "2026-07-14",
  return_end_date: ASOF,
};

function ctx(k: MarketContextKodex200 = KODEX): MarketContext {
  return {
    status: "ok",
    regime_label: "하락장",
    regime_code: "bear",
    regime_reasons: [],
    kodex200: k,
    kospi: { status: "unavailable" },
    warnings: [],
  } as unknown as MarketContext;
}

// 정상 후보(실측 2026-10-14 날짜와 같은 모양).
function normal(ticker: string, name: string, rank: number): MarketCandidate {
  return {
    rank,
    ticker,
    name,
    returns: {
      daily: r(5.4, "2026-10-13", ASOF),
      one_month: r(22.27, "2026-09-14", ASOF),
      three_month: r(33.79, "2026-07-16", ASOF),
      six_month: r(-18.26, "2026-04-17", ASOF),
      twelve_month: r(55.12, "2025-10-14", ASOF),
      three_year: r(65.01, "2025-01-07", ASOF),
    },
    excess_return: { vs_kodex200_1m_pctp: 37.33, vs_kodex200_3m_pctp: 47.02 },
  } as MarketCandidate;
}

// 늦게 상장(3개월 이상 시작 2026-07-28 · 실측 0223A0 모양).
function late(rank: number): MarketCandidate {
  const c = normal("0223A0", "RISE 코스닥커버드콜액티브", rank);
  c.returns = {
    ...c.returns,
    three_month: r(31.24, "2026-07-28", ASOF),
    six_month: r(31.24, "2026-07-28", ASOF),
    twelve_month: r(31.24, "2026-07-28", ASOF),
    three_year: r(31.24, "2026-07-28", ASOF),
  };
  return c;
}

// 끝 행이 하루 앞(격리 자료).
function stale(rank: number): MarketCandidate {
  return {
    rank,
    ticker: "418670",
    name: "TIGER 글로벌AI사이버보안",
    returns: {
      daily: r(0.08, "2026-10-12", "2026-10-13"),
      one_month: r(17.89, "2026-09-14", "2026-10-13"),
      three_month: r(7.43, "2026-07-16", "2026-10-13"),
      six_month: r(1, "2026-04-17", "2026-10-13"),
      twelve_month: r(2, "2025-10-14", "2026-10-13"),
      three_year: r(3, "2025-01-07", "2026-10-13"),
    },
    excess_return: { vs_kodex200_1m_pctp: 32.95, vs_kodex200_3m_pctp: 20.66 },
  } as MarketCandidate;
}

function noDates(rank: number): MarketCandidate {
  return {
    rank,
    ticker: "0209D0",
    name: "KODEX 전고체배터리ESS TOP2플러스",
    returns: { daily: r(5.09), one_month: r(20.3), three_month: r(30.97) },
    excess_return: { vs_kodex200_1m_pctp: 35.36, vs_kodex200_3m_pctp: 44.2 },
  } as MarketCandidate;
}

function lines(): string[] {
  const box = screen.getByTestId("return-period-line");
  // 줄 = 이름 | 내용(? 버튼 글자 제외).
  return Array.from(box.querySelectorAll(".rp-line")).map(
    (l) => `${l.querySelector(".rp-k")?.textContent} | ${l.querySelector(".rp-v")?.textContent}`,
  );
}

function openHelp(label: string): string {
  fireEvent.click(screen.getByRole("button", { name: `${label} 도움말` }));
  const text = screen.getByRole("dialog", { name: `${label} 도움말` }).textContent ?? "";
  fireEvent.click(screen.getByRole("button", { name: `${label} 도움말` }));
  return text;
}

describe("정상 자료 — 위 두 줄만 · 후보마다 날짜 반복 없음", () => {
  it("카드: 기간 한 줄 + KODEX200 비교 한 줄 · 후보 표시 0 · %p", () => {
    render(
      <CandidateCards
        candidates={[normal("0005D0", "SOL 전고체배터리&실리콘음극재", 1), normal("476260", "HANARO", 2)]}
        heldTickers={new Set()}
        marketAsof={ASOF}
        kodex={KODEX}
      />,
    );
    expect(lines()).toEqual([
      "1개월 수익률 계산 기간 | 2026-09-14 → 2026-10-14 종가 · 표시 후보 2개 모두 같음",
      "KODEX200 대비 1M · 3M | 기간 다른 수익률 차이 (%p)",
    ]);
    const list = screen.getByTestId("candidate-card-list");
    expect(list.querySelectorAll(".rp-note")).toHaveLength(0);
    expect(list.textContent).not.toMatch(/수익률 끝일|확인 불가/);
    expect(within(list).getAllByText("+37.33%p")).toHaveLength(2);
  });

  it("? 안에 계산 정의 · 기간별 날짜 · 양쪽 KODEX200 기간", () => {
    render(
      <CandidateCards candidates={[late(1), normal("0005D0", "SOL", 2)]} heldTickers={new Set()} marketAsof={ASOF} kodex={KODEX} />,
    );
    const main = openHelp("수익률 계산 기간");
    expect(main).toContain("· 1개월 2026-09-14 → 2026-10-14 (2개 모두)");
    expect(main).toContain("· 3개월 종목별 다름 — 시작 2026-07-16 ~ 2026-07-28 · 끝 2026-10-14");
    expect(main).toContain("그 기간 전체의 수익률이 아닙니다");
    expect(main).toContain("시장 저장 최신일 2026-10-14 = 저장된 전체 종목 가격 중 가장 늦은 저장일");
    const k = openHelp("KODEX200 대비 기간");
    expect(k).toContain("단위 %p");
    expect(k).toContain("· 1M — 후보 2026-09-14 → 2026-10-14 (2개 모두) · KODEX200 2026-09-10 → 2026-10-14");
    expect(k).toContain("· 3M — 후보 종목별 다름 — 시작 2026-07-16 ~ 2026-07-28 · 끝 2026-10-14 · KODEX200 2026-07-14 → 2026-10-14");
    expect(k).toContain("같은 기간의 초과수익이나 시장 대비 우위를 확인한 값이 아닙니다");
  });
});

describe("날짜 차이 — 시작일 여러 종류 · 끝일 다름 · 확인 불가", () => {
  it("3개월 기준: 모든 3개월 값 아래 실제 시작일 · 끝일 다른 후보는 이름 옆", () => {
    const cs = [normal("0005D0", "SOL", 1), late(2), stale(3)];
    render(<CandidateCards candidates={cs} heldTickers={new Set()} basis="three_month" marketAsof={ASOF} kodex={KODEX} />);
    expect(lines()[0]).toBe(
      "3개월 수익률 계산 기간 | 종목별 계산 기간 다름 · 시작일은 각 값 아래 · 끝일이 시장 저장 최신일과 다른 후보는 이름 옆",
    );
    const cards = screen.getAllByRole("button", { name: /상세 보기/ });
    const threeNote = (card: HTMLElement) =>
      card.querySelectorAll(".wb-hm-cell")[2].querySelector(".rp-note")?.textContent ?? null;
    expect(cards.map(threeNote)).toEqual(["시작 2026-07-16", "시작 2026-07-28", "시작 2026-07-16"]);
    expect(within(cards[2]).getByText("수익률 끝일 2026-10-13")).toBeInTheDocument();
    expect(within(cards[0]).queryByText(/수익률 끝일/)).toBeNull();
  });

  it("일부 확인 불가 — 위 줄에 알리고 그 후보 이름 옆에도", () => {
    render(
      <CandidateCards candidates={[normal("0005D0", "SOL", 1), noDates(2)]} heldTickers={new Set()} marketAsof={ASOF} kodex={KODEX} />,
    );
    expect(lines()[0]).toContain("날짜 확인된 1개 같음 · 1개 계산 기간 확인 불가");
    expect(lines()[1]).toBe("KODEX200 대비 1M · 3M | 기간 다른 수익률 차이 · 1개 기간 확인 불가 (%p)");
    const cards = screen.getAllByRole("button", { name: /상세 보기/ });
    expect(within(cards[1]).getByText("계산 기간 확인 불가")).toBeInTheDocument();
    expect(within(cards[1]).getByText("기간 확인 불가")).toBeInTheDocument(); // KODEX200 대비 값 아래
  });

  it("전부 확인 불가(예전 형식 응답) — 위 줄 한 번만", () => {
    render(<CandidateCards candidates={[noDates(1)]} heldTickers={new Set()} marketAsof={ASOF} kodex={{ status: "ok" }} />);
    expect(lines()).toEqual([
      "1개월 수익률 계산 기간 | 확인 불가 — 응답에 사용 종가 날짜가 없습니다",
      "KODEX200 대비 1M · 3M | 기간 확인 불가 (%p)",
    ]);
    expect(screen.getByTestId("candidate-card-list").querySelectorAll(".rp-note, .wb-hb.mute").length).toBe(1); // '미보유'만
  });

  it("개별주만 더 최신(시장 저장 최신일 10-15) — ETF 후보 모두 '수익률 끝일 10-14'", () => {
    render(
      <CandidateCards
        candidates={[normal("0005D0", "SOL", 1), normal("476260", "HANARO", 2)]}
        heldTickers={new Set()}
        marketAsof="2026-10-15"
        kodex={KODEX}
      />,
    );
    expect(screen.getAllByText("수익률 끝일 2026-10-14")).toHaveLength(2);
    expect(lines()[0]).toContain("2026-09-14 → 2026-10-14 종가 · 표시 후보 2개 모두 같음");
  });
});

describe("표 보기", () => {
  it("같은 두 줄 · 칸 아래 시작일 · 이름 아래 끝일 · %p · 표 아래 '1년' 문구 정정", () => {
    render(
      <CandidateTable
        candidates={[normal("0005D0", "SOL", 1), late(2), stale(3)]}
        basis="three_month"
        order="desc"
        onSort={() => undefined}
        marketAsof={ASOF}
        kodex={KODEX}
      />,
    );
    expect(lines()[0]).toContain("종목별 계산 기간 다름");
    const rows = screen.getAllByRole("row").slice(1);
    const notes = (row: HTMLElement) => Array.from(row.querySelectorAll(".rp-note")).map((n) => n.textContent);
    // 3개월 · 6개월 · 12개월 · 3년(일간 · 1개월은 시작일 한 종류라 표시 없음).
    expect(notes(rows[1]).filter((t) => t === "시작 2026-07-28")).toHaveLength(4);
    expect(notes(rows[2])).toContain("수익률 끝일 2026-10-13");
    expect(notes(rows[0])).not.toContain("수익률 끝일 2026-10-14");
    expect(within(rows[0]).getByText("+37.33%p")).toBeInTheDocument();
    const helper = document.querySelector(".market-topn-card p.helper")?.textContent ?? "";
    expect(helper).toContain("6개월 / 12개월 / 3년은");
    expect(helper).not.toContain("1년");
  });
});

describe("화면에 보인 날짜 = 복사문 날짜", () => {
  it("후보마다 일간 · 1개월 · 3개월의 시작 · 끝이 복사문 괄호와 같다", () => {
    const cs = [normal("0005D0", "SOL", 1), late(2), stale(3), noDates(4)];
    render(<CandidateCards candidates={cs} heldTickers={new Set()} basis="three_month" marketAsof={ASOF} kodex={KODEX} />);
    const help = openHelp("수익률 계산 기간");
    // ? 안 기간별 줄에서 공통 시작일(한 종류일 때만 있다).
    const D = "(\\d{4}-\\d{2}-\\d{2})";
    const commonStart = (label: string): string | null => {
      const same = help.match(new RegExp(`· ${label} ${D} → ${D} \\(`));
      if (same) return same[1];
      const diff = help.match(new RegExp(`· ${label} 종목별 다름 — 시작 ${D} ·`));
      return diff ? diff[1] : null;
    };
    const copy = buildMarketDiscoveryCopyText({
      asof: ASOF,
      filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true },
      candidates: cs,
      marketContext: ctx(),
    }).split("\n");
    const cards = screen.getAllByRole("button", { name: /상세 보기/ });
    let checked = 0;
    cs.forEach((c, i) => {
      const card = cards[i];
      const badge = Array.from(card.querySelectorAll(".wb-hb.mute")).map((b) => b.textContent ?? "");
      const unknown = badge.includes("계산 기간 확인 불가");
      const endBadge = badge.find((b) => b.startsWith("수익률 끝일 "));
      const head = copy.findIndex((l) => l === `${c.rank}. ${c.name} (${c.ticker})`);
      ["일간", "1개월", "3개월"].forEach((label, j) => {
        const line = copy[head + 1 + j];
        expect(line.startsWith(`   - ${label} 수익률:`)).toBe(true);
        if (unknown) {
          expect(line).toContain("(계산 기간 확인 불가)");
          return;
        }
        const note = card.querySelectorAll(".wb-hm-cell")[j].querySelector(".rp-note")?.textContent ?? "";
        const start = note.startsWith("시작 ") ? note.slice(3) : commonStart(label);
        expect(start).not.toBeNull();
        const end = endBadge ? endBadge.slice("수익률 끝일 ".length) : ASOF;
        expect(line).toContain(`사용 종가 ${start} → ${end})`);
        checked += 1;
      });
    });
    expect(checked).toBe(9);
    // KODEX200 비교 두 기간도 ? 안의 날짜와 같다.
    const k = openHelp("KODEX200 대비 기간");
    expect(k).toContain("KODEX200 2026-09-10 → 2026-10-14");
    expect(copy).toContain(
      "   - KODEX200 대비 1개월 수익률 차이: +37.33%p (기간 다름 — 후보 2026-09-14 → 2026-10-14 · KODEX200 2026-09-10 → 2026-10-14)",
    );
  });
});

describe("요약 명칭 — 시장 저장 최신일(저장된 전체 종목 가격)", () => {
  beforeEach(() => {
    __resetQueryCache();
    fetchMarketTopnLatest.mockReset();
  });

  it("개별주만 더 최신이어도 같은 명칭 · 후보 끝일은 각자", async () => {
    fetchMarketTopnLatest.mockResolvedValue({
      status: "ok",
      asof: "2026-10-15",
      filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true },
      candidates: [normal("0005D0", "SOL", 1)],
      daily_topn: [],
      one_month_topn: [],
      three_month_topn: [],
      market_context: ctx(),
    });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await act(async () => {
      for (let i = 0; i < 5; i++) await Promise.resolve();
    });
    const text = document.body.textContent ?? "";
    expect(text).toContain("시장 저장 최신일: 2026-10-15 (저장된 전체 종목 가격 중 가장 늦은 저장일)");
    expect(text).not.toContain("시장 데이터 기준일");
    expect(screen.getByText("수익률 끝일 2026-10-14")).toBeInTheDocument();
  });
});
