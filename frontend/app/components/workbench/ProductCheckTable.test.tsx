// POC6-32 V2(PLAN §3-2 D2 · D3 · §9 I-6 · I-19 · I-21) — 「보유와 후보 비교」 상품 확인 표 · 지수 상태(순수 함수 · 칸 글).
// 화면 전체 흐름(고르기 → 표 → 차이 줄 조건)은 HoldingCandidateCompareView.test.tsx 의 조합 표에서 본다.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import type { EtfOfficialResponse, OfficialCsv, OfficialItem, OfficialPair } from "@/lib/api/etfOfficial";
import type { QueryState } from "@/lib/api/queryCache";
import ProductCheckTable, { feeText, indexGateOf, productCells, structureText } from "./ProductCheckTable";

const CSV: OfficialCsv = { name: "krx_etf_basic_20260927.csv", asof: "2026-09-27", ok: true, error: null };
const BAD_CSV: OfficialCsv = { name: null, asof: null, ok: false, error: "공식 기준정보 파일을 읽지 못함(유효한 파일 없음)" };

function it0(over: Partial<OfficialItem> = {}): OfficialItem {
  return {
    ticker: "X00001",
    found: true,
    kind: "etf",
    name: "시험 ETF",
    index_name: "시험 지수 A",
    index_provider: "시험 산출기관",
    market: "해외",
    asset: "주식",
    multiple: "일반",
    replication: "실물(패시브)",
    fee_pct: "0.450000",
    tax: "배당소득세(보유기간과세)",
    listed: "2024/01/02",
    missing_reason: null,
    ...over,
  };
}
const NOT_FOUND = {
  found: false,
  index_name: null,
  index_provider: null,
  market: null,
  asset: null,
  multiple: null,
  replication: null,
  fee_pct: null,
  tax: null,
  listed: null,
} as const;

const ok = (data: EtfOfficialResponse, stale = false): QueryState<EtfOfficialResponse> => ({ phase: "success", data, stale });
const pair = (over: Partial<OfficialPair> = {}): OfficialPair => ({
  state: "same",
  label: "같은 공식 기초지수",
  reason: "두 상품 모두 공식 기초지수 '시험 지수 A'",
  structure_diffs: [],
  ...over,
});

describe("feeText — 총보수 CSV 글자(값은 바꾸지 않고 소수 끝의 0 만 지움)", () => {
  it.each([
    ["0.450000", "0.45%"],
    ["0.150000", "0.15%"],
    ["1.000000", "1%"],
    ["0.000000", "0%"],
    ["0.0099", "0.0099%"],
    ["10", "10%"],
    [" 0.5 ", "0.5%"],
    ["해당 없음", "해당 없음"],
  ])("%s → %s", (v, out) => expect(feeText(v)).toBe(out));
  it("비었으면 null(0 으로 채우지 않음)", () => {
    expect(feeText(null)).toBeNull();
    expect(feeText("")).toBeNull();
    expect(feeText("   ")).toBeNull();
  });
});

describe("productCells — 칸 글", () => {
  it("공식 기준정보에 있음 = CSV 값 그대로 · 투자 대상 · 상품 구조는 ' · '로 · 파일 날짜", () => {
    expect(productCells(it0(), CSV)).toEqual({
      index: "시험 지수 A",
      provider: "시험 산출기관",
      target: "해외 · 주식",
      structure: "일반 · 실물(패시브) · 총보수 0.45%",
      tax: "배당소득세(보유기간과세)",
      file: "KRX 2026-09-27 파일",
    });
  });

  it("값이 일부 비면 있는 값만 · 다 비면 —", () => {
    const c = productCells(it0({ market: null, fee_pct: null, replication: "", index_provider: null, tax: null }), CSV);
    expect(c.target).toBe("주식");
    expect(c.structure).toBe("일반");
    expect(c.provider).toBe("—");
    expect(c.tax).toBe("—");
    expect(productCells(it0({ market: null, asset: null }), CSV).target).toBe("—");
  });

  it("개별 주식(I-19) = '개별 주식 · 기초지수 해당 없음' · 나머지 — · 파일 해당 없음", () => {
    const c = productCells(it0({ ...NOT_FOUND, kind: "stock", name: null, missing_reason: "개별 주식 · 기초지수 해당 없음" }), CSV);
    expect(c).toEqual({ index: "개별 주식 · 기초지수 해당 없음", provider: "—", target: "—", structure: "—", tax: "—", file: "해당 없음" });
  });

  it("공식 기준정보에 없음(I-21) = '공식 기준정보에 없음 — 확인 불가' · 그 파일에 없음", () => {
    const c = productCells(it0({ ...NOT_FOUND, missing_reason: "공식 기준정보에 없음" }), CSV);
    expect(c.index).toBe("공식 기준정보에 없음 — 확인 불가");
    expect(c.file).toBe("KRX 2026-09-27 파일에 없음");
  });

  it("공식 기준정보 파일을 못 읽음 = 서버 사유 + 확인 불가 · 파일을 읽지 못함", () => {
    const c = productCells(it0({ ...NOT_FOUND, missing_reason: "공식 기준정보 파일을 읽지 못함" }), BAD_CSV);
    expect(c.index).toBe("공식 기준정보 파일을 읽지 못함 — 확인 불가");
    expect(c.file).toBe("파일을 읽지 못함");
  });

  it("ETF 목록을 못 읽어 종류를 모름(unknown) · 사유 칸 없음 = 공식 기준정보에 없음 — 확인 불가", () => {
    const c = productCells(it0({ ...NOT_FOUND, kind: "unknown", missing_reason: null }), CSV);
    expect(c.index).toBe("공식 기준정보에 없음 — 확인 불가");
  });

  it("응답에 그 종목이 없음 = '공식 기준정보 응답에 없음 — 확인 불가'", () => {
    expect(productCells(undefined, CSV).index).toBe("공식 기준정보 응답에 없음 — 확인 불가");
  });

  it("파일 날짜가 비었으면 날짜를 지어내지 않는다", () => {
    expect(productCells(it0(), { ...CSV, asof: null }).file).toBe("KRX 파일(날짜 확인 불가)");
  });
});

describe("structureText — 구조 다름(확인된 값 · 보유 ↔ 후보)", () => {
  it("다른 칸만 · 총보수는 % · 빈 값은 —", () => {
    expect(
      structureText([
        { field: "추적배수", a: "일반", b: "2X 레버리지" },
        { field: "총보수", a: "0.150000", b: "0.450000" },
        { field: "과세유형", a: null, b: "비과세" },
      ]),
    ).toBe("구조 다름: 추적배수 일반 ↔ 2X 레버리지 · 총보수 0.15% ↔ 0.45% · 과세유형 — ↔ 비과세(보유 ↔ 후보)");
    expect(structureText([])).toBeNull();
  });
});

describe("indexGateOf — 차이 줄 조건(서버 판정 그대로 · 다시 판정하지 않음)", () => {
  const resp = (p?: OfficialPair): EtfOfficialResponse => ({ csv: CSV, items: {}, ...(p ? { pair: p } : {}) });

  it("읽기 전 · 읽는 중 = 차이를 아직 적지 않음", () => {
    expect(indexGateOf({ phase: "idle" })).toEqual({ phase: "pending", text: "공식 기준정보를 읽는 중이라 차이는 아직 적지 않습니다" });
    expect(indexGateOf({ phase: "loading" }).phase).toBe("pending");
  });

  it("못 읽음 · 응답에 상태 없음 · 알 수 없는 상태 글 = 기준 미확인(영어 상태 글 없음)", () => {
    expect(indexGateOf({ phase: "error" })).toMatchObject({ phase: "ready", state: "unconfirmed", label: "기준 미확인", reason: "공식 기준정보를 읽지 못함" });
    expect(indexGateOf(ok(resp()))).toMatchObject({ state: "unconfirmed", reason: "공식 기준정보 응답에 두 상품의 지수 상태가 없음" });
    const odd = indexGateOf(ok(resp(pair({ state: "odd" as unknown as OfficialPair["state"], label: "odd" }))));
    expect(odd).toMatchObject({ state: "unconfirmed", label: "기준 미확인" });
  });

  it.each([
    ["same", "같은 공식 기초지수"],
    ["same_family", "다른 지수 · 같은 계열"],
    ["different", "다른 지수"],
    ["unconfirmed", "기준 미확인"],
  ] as const)("서버 상태 %s = 이름 '%s'(화면 이름표 · 서버 사유 그대로)", (st, label) => {
    const g = indexGateOf(ok(resp(pair({ state: st, label: "서버 이름", reason: "서버 사유" }))));
    expect(g).toMatchObject({ phase: "ready", state: st, label, reason: "서버 사유" });
  });

  it("구조 다름 글은 같은 공식 기초지수일 때만(지수가 다르면 차이 요약이 없으므로 붙이지 않음)", () => {
    const diffs = [{ field: "추적배수", a: "일반", b: "2X 레버리지" }];
    expect(indexGateOf(ok(resp(pair({ structure_diffs: diffs }))))).toMatchObject({
      state: "same",
      structure: "구조 다름: 추적배수 일반 ↔ 2X 레버리지(보유 ↔ 후보)",
    });
    expect(indexGateOf(ok(resp(pair({ state: "different", structure_diffs: diffs }))))).toMatchObject({ state: "different", structure: null });
  });

  // r1 F2 — 빈 값은 차이가 아니다: 서버가 따로 준 '확인 안 된 구조 항목'은 '구조 다름' 문장 밖에 적는다.
  it.each([
    ["두 쪽 모두 확인 · 다름", [{ field: "총보수", a: "0.150000", b: "0.450000" }], [], "구조 다름: 총보수 0.15% ↔ 0.45%(보유 ↔ 후보)"],
    ["한쪽(보유)만 빔", [], [{ field: "총보수", side: "a" }], "확인 안 된 구조 항목: 총보수(보유 쪽)"],
    ["한쪽(후보)만 빔", [], [{ field: "과세유형", side: "b" }], "확인 안 된 구조 항목: 과세유형(후보 쪽)"],
    ["두 쪽 모두 빔", [], [{ field: "추적배수", side: "both" }], "확인 안 된 구조 항목: 추적배수(두 쪽 모두)"],
    [
      "다름 + 빔",
      [{ field: "추적배수", a: "일반", b: "2X 레버리지" }],
      [{ field: "총보수", side: "a" }],
      "구조 다름: 추적배수 일반 ↔ 2X 레버리지(보유 ↔ 후보) / 확인 안 된 구조 항목: 총보수(보유 쪽)",
    ],
  ] as const)("%s", (_name, diffs, unconfirmed, text) => {
    const g = indexGateOf(ok(resp(pair({ structure_diffs: [...diffs], structure_unconfirmed: [...unconfirmed] }))));
    // 같은 공식 기초지수는 그대로(차이 줄을 적음) · 빈 칸은 '구조 다름' 문장 안에 들어가지 않음
    expect(g).toMatchObject({ phase: "ready", state: "same", structure: text });
    if (diffs.length === 0) expect(g.phase === "ready" && g.structure).not.toContain("구조 다름");
    expect(structureText([...diffs], [...unconfirmed])).toBe(text);
  });

  it("빈 칸 목록이 없는 응답(옛 서버) = 빈 목록 · 둘 다 없으면 구조 글 없음", () => {
    expect(indexGateOf(ok(resp(pair())))).toMatchObject({ state: "same", structure: null });
    expect(structureText([], [])).toBeNull();
  });
});

describe("ProductCheckTable — 칸 · 지수 상태 한 줄", () => {
  const hold = { ticker: "H00001", name: "시험 보유" };
  const cand = { ticker: "C00001", name: "시험 후보" };

  it("다른 지수 = 빨간 칩 · 서버 사유 + '각 ETF 값만' · 다시 읽기 실패면 이전 값 안내", () => {
    const data: EtfOfficialResponse = {
      csv: CSV,
      items: { H00001: it0({ ticker: "H00001", index_name: "시험 지수 A" }), C00001: it0({ ticker: "C00001", index_name: "시험 지수 B" }) },
      pair: pair({ state: "different", label: "다른 지수", reason: "공식 기초지수가 다름('시험 지수 A' ↔ '시험 지수 B')" }),
    };
    const q = ok(data, true);
    render(<ProductCheckTable q={q} gate={indexGateOf(q)} hold={hold} cand={cand} />);
    expect(screen.getByTestId("hcc-p-index-holding")).toHaveTextContent("시험 지수 A");
    expect(screen.getByTestId("hcc-p-index-candidate")).toHaveTextContent("시험 지수 B");
    expect(screen.getByTestId("hcc-index-chip")).toHaveTextContent("다른 지수");
    expect(screen.getByTestId("hcc-index-chip")).toHaveClass("tc-sum-bad");
    expect(screen.getByTestId("hcc-index-reason")).toHaveTextContent(
      "공식 기초지수가 다름('시험 지수 A' ↔ '시험 지수 B') — 수익률 차이 요약을 쓰지 않고 각 ETF 값만 보입니다",
    );
    expect(screen.getByTestId("hcc-product-stale")).toBeInTheDocument();
  });

  it("읽는 중 = 표 · 상태 줄 없이 '확인 중' · 못 읽음 = 안내 + 기준 미확인 줄", () => {
    const { unmount } = render(<ProductCheckTable q={{ phase: "loading" }} gate={indexGateOf({ phase: "loading" })} hold={hold} cand={cand} />);
    expect(screen.getByTestId("hcc-product")).toHaveTextContent("공식 기준정보 확인 중...");
    expect(screen.queryByTestId("hcc-product-table")).toBeNull();
    expect(screen.queryByTestId("hcc-index-state")).toBeNull();
    unmount();
    render(<ProductCheckTable q={{ phase: "error" }} gate={indexGateOf({ phase: "error" })} hold={hold} cand={cand} />);
    expect(screen.getByTestId("hcc-product-error")).toBeInTheDocument();
    expect(screen.getByTestId("hcc-index-chip")).toHaveTextContent("기준 미확인");
    expect(screen.getByTestId("hcc-index-chip")).toHaveClass("tc-sum-muted");
  });
});
