// POC6-32 V2(PLAN §4-1) — 사건 문장 · '아침과 당일이 같은 근거면 한 번' 규칙은 서버(app/market_evidence_text.py)로 옮겼다.
// 서버 시험(tests/test_poc6_32_market_evidence.py)과 같은 고정 자료(저장소 tests/fixtures/poc6_32_evidence_cases.json)를
// 화면 함수(eventSentence · commonClosedRow)에도 넣어 같은 결과가 나오는지 본다(두 구현이 어긋나면 한쪽 시험이 깨짐).
// 외부 호출 0 — 저장소 파일만 읽는다(합성 값 · 계좌 · 보유 자료 없음).
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { FlowEvent } from "./api/marketFlow";
import type { MorningBasisResponse } from "./api/morningBasis";
import type { QueryState } from "./api/queryCache";
import { eventSentence } from "./todayMarketLines";
import { commonClosedRow } from "./morningText";

// lib → frontend → 저장소 루트(dependencyDirection.test 와 같은 방식 · Vite 가 바꾸는 new URL(…, import.meta.url) 형태를 쓰지 않음)
const REPO_ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));
const FIXTURE = path.join(REPO_ROOT, "tests", "fixtures", "poc6_32_evidence_cases.json");

interface Cases {
  events: { note: string; input: FlowEvent; expected_sentence: string }[];
  common_rows: { note: string; input: QueryState<MorningBasisResponse>; expected: ReturnType<typeof commonClosedRow> }[];
}

const cases = JSON.parse(readFileSync(FIXTURE, "utf8")) as Cases;

describe("POC6-32 V2 공통 시장 근거 — 서버와 같은 고정 자료로 화면 함수 대조", () => {
  it("고정 자료에 사건 문장 · 같은 행 사례가 모두 있다(빈 자료로 통과하지 않게)", () => {
    expect(cases.events.length).toBeGreaterThan(0);
    expect(cases.common_rows.length).toBeGreaterThan(0);
    // 같은 행 사례에는 '같음'(행)과 '다름'(null)이 모두 있어야 규칙을 양쪽으로 본다
    expect(cases.common_rows.some((c) => c.expected !== null)).toBe(true);
    expect(cases.common_rows.some((c) => c.expected === null)).toBe(true);
  });

  it.each(cases.events.map((c) => [c.note, c] as const))("사건 문장 — %s", (_note, c) => {
    expect(eventSentence(c.input)).toBe(c.expected_sentence);
  });

  it.each(cases.common_rows.map((c) => [c.note, c] as const))("아침 · 당일 같은 근거 한 번 — %s", (_note, c) => {
    expect(commonClosedRow(c.input)).toEqual(c.expected);
  });
});
