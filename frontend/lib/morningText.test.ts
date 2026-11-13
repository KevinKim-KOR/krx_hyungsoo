// POC6-29 보완 2차 — 아침 요약 준비 상태 · 끝 줄 · 아침 판정 · 5거래일 문장 · 시세 머리 · ③ 결과 줄(조합 표).
import { describe, it, expect } from "vitest";
import type { MorningBasisResponse, MorningItem } from "./api/morningBasis";
import type { RefreshAllPrevdayStep } from "./api/refreshAll";
import type { QueryState } from "./api/queryCache";
import {
  commonClosedRow,
  endLine,
  flowsMorning,
  morningStatus,
  morningVerdict,
  prevdayLine,
  quoteHeader,
  readiness,
  scoreRuleText,
  scoreText,
  shortFlowText,
  todayBasis,
} from "./morningText";
import { MORNING_CTX, morningMissing, morningOk, shortOk } from "./morningTestFixtures";
import { quickItems } from "./quickQuotesTestFixtures";

function withItems(edit: (i: MorningItem) => MorningItem): MorningBasisResponse {
  const ok = morningOk();
  const items = ok.items.map(edit);
  const missing = items.filter((i) => i.required && !i.met).map((i) => i.key);
  return { ...ok, items, missing, ready: missing.length === 0 };
}

describe("readiness — 필수 3 준비 상태 한 줄(서버 판단 그대로)", () => {
  it.each<[string, MorningBasisResponse | null, boolean | null, string]>([
    ["불러오는 중", null, null, "아침 요약 기준 불러오는 중"],
    ["읽기 실패", { ...morningOk(), status: "invalid", message: "아침 요약 기준을 읽지 못했습니다" }, null, "아침 요약 기준을 읽지 못했습니다"],
    ["준비됨", morningOk(), true, "필수 자료 준비됨 · 코스피 공식 종가 · KODEX 200 판정 근거 · 투자자 수급"],
    ["같은 날짜 둘 = 한 묶음 · 받침 있음 '은'", morningMissing(), false, "전일 자료 미완료 · 코스피 공식 종가 · 수급은 11/9까지"],
    [
      "날짜가 다르면 묶음 둘 · 받침 없음 '는'",
      withItems((i) => (i.key === "kospi" ? { ...i, met: false, stored_date: "2026-11-10" } : i.key === "flows" ? { ...i, met: false, stored_date: "2026-11-09" } : i)),
      false,
      "전일 자료 미완료 · 수급은 11/9까지 · 코스피 공식 종가는 11/10까지",
    ],
    [
      "자료 없음 · KODEX 200 미확인",
      withItems((i) => (i.key === "flows" ? { ...i, met: false, stored_date: null } : i.key === "kodex200" ? { ...i, met: false } : i)),
      false,
      "전일 자료 미완료 · 수급 자료 없음 · KODEX 200 근거 미확인",
    ],
    ["해외 늦음은 준비 상태를 막지 않음", withItems((i) => (i.key === "vix" ? { ...i, met: false, state: "update_check" } : i)), true, "필수 자료 준비됨 · 코스피 공식 종가 · KODEX 200 판정 근거 · 투자자 수급"],
  ])("%s", (_t, mb, ok, head) => {
    const r = readiness(mb);
    expect(r.ok).toBe(ok);
    expect(r.head).toBe(head);
  });

  it("사유 = 서버 문장 그대로(KODEX 200 은 이름을 이미 담고 있어 앞에 붙이지 않음)", () => {
    const mb = withItems((i) =>
      i.key === "kodex200" ? { ...i, met: false, reason: "KODEX 200 근거 미확인 — [최신 자료 갱신]" } : i.key === "flows" ? { ...i, met: false, stored_date: "2026-11-10", reason: NOT } : i,
    );
    expect(readiness(mb).reasons).toEqual(["KODEX 200 근거 미확인 — [최신 자료 갱신]", `수급: ${NOT}`]);
  });
});
const NOT = "아직 받지 않음 — [최신 자료 갱신]";

describe("endLine — 갱신 끝 줄(아침 요약과 같은 판단)", () => {
  it("준비됨 · 남은 예외 · 확인 불가", () => {
    expect(endLine(morningOk())).toEqual({ text: "아침 요약 기준 11/11 · 필수 자료 모두 준비됨", warn: false });
    expect(endLine(morningMissing())).toEqual({
      text:
        "아침 요약 기준 11/11 · 남은 예외: 코스피 공식 종가 · 수급은 11/9까지 — 코스피 공식 종가: 설정 확인 필요(KRX 키 없음) · 15:59 확인 / 수급: 가져오기 실패(가져오기 실행 실패) · 15:59 확인",
      warn: true,
    });
    expect(endLine(null).warn).toBe(true);
    expect(endLine({ ...morningOk(), expected_date: null }).text).toContain("아침 요약 기준 확인 불가");
  });
});

// 설계자 정리(2026-11-13 · 마감 뒤) — 시장 판단 먼저 + KODEX 200 핵심 근거(20거래일 · 20 · 60일선) · 60거래일은 쓰지 않음
describe("morningVerdict — 판단 · 핵심 근거 · 미확인", () => {
  const withK = (k: Record<string, unknown>) =>
    ({ ...morningOk(), morning_regime: { status: "ok" as const, basis_date: "2026-11-11", reason: null, context: { ...MORNING_CTX, kodex200: { ...(MORNING_CTX.kodex200 as object), ...k } } as unknown as typeof MORNING_CTX } });
  it.each<[string, MorningBasisResponse, string, string | null]>([
    ["둘 다 아래 · 하락", morningOk(), "국내 시장은 하락장 24거래일째입니다.", "KODEX 200은 최근 20거래일간 10.70% 하락했고, 20일선과 60일선 아래에 있습니다."],
    ["상승 · 둘 다 위", withK({ return_20d_pct: 3.2, ma20_position: "above", ma60_position: "above" }), "국내 시장은 하락장 24거래일째입니다.", "KODEX 200은 최근 20거래일간 3.20% 상승했고, 20일선과 60일선 위에 있습니다."],
    ["엇갈림", withK({ ma20_position: "above", ma60_position: "below" }), "국내 시장은 하락장 24거래일째입니다.", "KODEX 200은 최근 20거래일간 10.70% 하락했고, 20일선 위, 60일선 아래에 있습니다."],
    ["변동 없음 · 위치 모름", withK({ return_20d_pct: 0, ma20_position: null }), "국내 시장은 하락장 24거래일째입니다.", "KODEX 200은 최근 20거래일간 변동이 없었습니다."],
    ["수익률 모름", withK({ return_20d_pct: null }), "국내 시장은 하락장 24거래일째입니다.", "KODEX 200은 20일선과 60일선 아래에 있습니다."],
  ])("%s", (_t, mb, head, detail) => {
    const v = morningVerdict(mb, () => "하락장");
    expect(v.head).toBe(head);
    expect(v.detail).toBe(detail);
    expect(v.detail ?? "").not.toContain("60거래일");
  });
  it("미확인 = '아침 판정 미확인 — 서버 사유'", () => {
    expect(morningVerdict({ ...morningOk(), morning_regime: { status: "unconfirmed", basis_date: "2026-11-11", reason: "KODEX 200 11/11 마감 가격 미확인", context: null } }, () => "x").head).toBe(
      "아침 판정 미확인 — KODEX 200 11/11 마감 가격 미확인",
    );
    expect(morningVerdict(null, () => "x").head).toBe("아침 판정 미확인 — 기준일 근거를 확인하지 못했습니다");
  });
});

describe("morningStatus — 끝 한 줄(빠진 자료만 짧게 · 원인은 [자료 상태 보기])", () => {
  it.each<[string, MorningBasisResponse | null, QueryState<MorningBasisResponse>["phase"], string, string, number]>([
    ["준비됨 = 짧게 한 줄", morningOk(), "success", "필수 자료 준비됨(코스피 공식 종가 · KODEX 200 · 수급)", "ok", 0],
    ["같은 날짜 둘", morningMissing(), "success", "코스피 공식 종가 · 수급은 11/9까지 있습니다.", "warn", 2],
    [
      "KODEX 200 미확인 · 자료 없음",
      withItems((i) => (i.key === "flows" ? { ...i, met: false, stored_date: null } : i.key === "kodex200" ? { ...i, met: false, reason: "KODEX 200 근거 미확인 — [최신 자료 갱신]" } : i)),
      "success",
      "수급 자료가 없습니다. KODEX 200 판정 근거는 확인되지 않았습니다.",
      "warn",
      1,
    ],
    ["불러오는 중", null, "loading", "아침 요약 기준 불러오는 중", "muted", 0],
    ["첫 조회 실패", null, "error", "아침 요약 기준을 불러오지 못했습니다(PC 서버 확인)", "warn", 0],
  ])("%s", (_t, mb, phase, text, tone, reasons) => {
    const st = morningStatus(mb, phase);
    expect(st.text).toBe(text);
    expect(st.tone).toBe(tone);
    expect(st.reasons).toHaveLength(reasons);
  });
});

describe("5거래일 문장", () => {
  it("합 · 비교 문장 · 자료 부족", () => {
    const sf = shortOk();
    expect(shortFlowText(sf.investors[0])).toBe("최근 5거래일 1.1조원 순매도 · 순매수 → 순매도 전환");
    expect(shortFlowText(sf.investors[2])).toBe("5거래일 자료 부족");
    expect(shortFlowText(null)).toBe("확인 불가");
    expect(flowsMorning(sf)?.text).toBe("외국인은 최근 5거래일(11/5 ~ 11/11) 1.1조원 순매도입니다(순매수 → 순매도 전환).");
    const noRecent = { ...sf, investors: [{ ...sf.investors[0], recent5: null, note: "5거래일 자료 부족" }] };
    expect(flowsMorning(noRecent)?.text).toBe("외국인 최근 5거래일 — 5거래일 자료 부족.");
    expect(flowsMorning({ ...sf, status: "empty" })).toBeNull();
  });
});

describe("quoteHeader — 공통 시점은 한 번 · 다른 칸만 따로", () => {
  it("같음 · 실패 칸 · 기록 없음", () => {
    const same = quoteHeader(quickItems());
    expect(same.head).toBe("11/12 마감 · 네이버 시세 · 마지막 조회 11/12 15:36");
    expect(same.differs.size).toBe(0);
    const failed = quoteHeader(
      quickItems({ KOSDAQ: { last_attempt: { at: "2026-11-12T16:00:00+09:00", status: "failed", reason: "timeout" } } }),
    );
    expect([...failed.differs]).toEqual(["KOSDAQ"]);
    expect(failed.head).toBe("11/12 마감 · 네이버 시세 · 마지막 조회 11/12 15:36");
    const none = quoteHeader(quickItems({ KOSPI: { quote: null }, KOSDAQ: { quote: null }, "069500": { quote: null } }));
    expect(none.head).toBeNull();
    expect(none.differs.size).toBe(3);
  });
});

describe("prevdayLine — ③ 결과 줄(항목 상태 조합)", () => {
  const base: RefreshAllPrevdayStep = { status: "done", id: "p", expected_date: "2026-11-11", reason: null, items: {} };
  it.each<[string, RefreshAllPrevdayStep | null, string | null, boolean]>([
    ["없음 · 대기", null, null, false],
    ["대기(pending)", { status: "pending" }, null, false],
    ["진행 중", { status: "running" }, "③ 전일 자료 보충 중...(코스피 공식 종가 · 수급 · 해외 지표 중 모자란 것만)", false],
    ["건너뜀", { status: "skipped", reason: "시장 전체 갱신을 시작했습니다 — 같은 수집에서 받습니다" }, "③ 전일 자료 보충 안 함 — 시장 전체 갱신을 시작했습니다 — 같은 수집에서 받습니다", false],
    ["예외", { status: "failed", reason: "전일 자료를 보충하는 중 오류가 났습니다." }, "③ 전일 자료 보충 실패 — 전일 자료를 보충하는 중 오류가 났습니다.", true],
    ["모두 이미 있음", { ...base, items: { kospi: { label: "", status: "already", before: "2026-11-11", after: "2026-11-11", reason: null } } }, "③ 전일 자료(11/11 기준) — 코스피 공식 종가 11/11 이미 있음", false],
    [
      "그대로(원천 미공개) · 실패 = 경고",
      {
        ...base,
        items: {
          kospi: { label: "", status: "unchanged", before: "2026-11-10", after: "2026-11-10", reason: "KRX 에 아직 기준일 자료가 없음" },
          flows: { label: "", status: "failed", before: "2026-11-09", after: "2026-11-09", reason: "OCI 연결 실패", via: "pull" },
          wti: { label: "", status: "skipped", before: "2026-11-11", after: "2026-11-11", reason: "x" },
        },
      },
      "③ 전일 자료(11/11 기준) — 코스피 공식 종가 11/10 그대로(KRX 에 아직 기준일 자료가 없음) · 수급 받지 못함(OCI 연결 실패) · 11/9까지",
      true,
    ],
    [
      "날짜는 나아졌지만 일부 확인 필요",
      { ...base, items: { usdkrw: { label: "", status: "fetched", before: "2026-11-09", after: "2026-11-11", reason: "WTI" } } },
      "③ 전일 자료(11/11 기준) — 원/달러 11/9 → 11/11 받음(일부 확인 필요: WTI)",
      false,
    ],
    ["결과 기록 저장 실패는 끝에", { ...base, reason: "결과 기록을 저장하지 못했습니다" }, "③ 전일 자료(11/11 기준) — 보충할 항목 없음 · 결과 기록을 저장하지 못했습니다", true],
  ])("%s", (_t, step, text, warn) => {
    const r = prevdayLine(step);
    if (text === null) {
      expect(r).toBeNull();
      return;
    }
    expect(r?.text).toBe(text);
    expect(r?.warn).toBe(warn);
  });
});

// 당일 판정 출처(형수님 결정 2026-11-13 · 검증자 F8 · F10) — 같은 한 번 읽기 응답이 '지금 성공'일 때만 · 그 밖은 시장 판정 응답의 판정 · 날짜만.
describe("todayBasis — 아침 기준 응답 상태 × today_regime", () => {
  const market = { ...morningOk().morning_regime!.context!, asof: "2026-11-12", regime_label: "상승장", regime_code: "bull" as const };
  const row = { date: "2026-11-12", close: 85045, state: "intraday" as const, fetched_at_kst: "2026-11-12T09:53:21+09:00" };
  const tr = { status: "ok" as const, basis_date: "2026-11-12", reason: null, context: { ...market, regime_label: "하락장", regime_code: "bear" as const }, basis_row: row };
  const ok = (over: Partial<MorningBasisResponse> = {}): MorningBasisResponse => ({ ...morningOk(), today_regime: tr, ...over });
  it.each<[string, QueryState<MorningBasisResponse>, "today" | "market" | "missing"]>([
    ["지금 성공 · 같은 읽기 있음", { phase: "success", data: ok(), stale: false }, "today"],
    ["다시 읽기 실패로 남은 이전 응답(F10)", { phase: "success", data: ok(), stale: true }, "market"],
    ["첫 조회 실패", { phase: "error" }, "market"],
    ["불러오는 중", { phase: "loading" }, "market"],
    ["칸 없음(옛 서버)", { phase: "success", data: morningOk(), stale: false }, "market"],
    ["읽기 실패 응답(today_regime null)", { phase: "success", data: { ...ok(), status: "invalid", today_regime: null }, stale: false }, "market"],
    ["같은 읽기가 미확인", { phase: "success", data: ok({ today_regime: { ...tr, status: "unconfirmed", reason: "KODEX 200 판정 근거 부족(저장 이력)", context: null } }), stale: false }, "missing"],
  ])("%s", (_t, q, want) => {
    const b = todayBasis(q, market);
    if (want === "today") {
      expect(b.ctx?.regime_label).toBe("하락장");
      expect(b.row).toEqual(row);
    } else if (want === "market") {
      expect(b.ctx?.regime_label).toBe("상승장");
      expect(b.row).toBeNull();
      expect(b.date).toBe("2026-11-12");
      expect(b.missing).toBeNull();
    } else {
      expect(b.ctx).toBeNull();
      expect(b.missing).toBe("당일 판정 미확인 — KODEX 200 판정 근거 부족(저장 이력)");
    }
  });
});

// 설계자 RESULT 재판정 V3 D1 · D2(2026-11-13)
describe("D1 — scoreText · scoreRuleText(서버가 준 경계값 그대로)", () => {
  it.each<[number | null | undefined, string]>([
    [-4, "-4점"],
    [0, "0점"],
    [2, "+2점"],
    [null, "확인 불가"],
    [undefined, "확인 불가"],
  ])("%s → %s", (score, want) => {
    expect(scoreText(score === undefined ? null : ({ ...MORNING_CTX, regime_score: score } as typeof MORNING_CTX))).toBe(want);
  });

  it("경계값은 응답 값으로 만든다(화면에 숫자를 따로 두지 않음) · 응답이 없으면 읽지 못했다고", () => {
    const t = scoreRuleText({ return_20d_pct: 3, return_60d_pct: 6, bull_min: 3, bear_max: -3 });
    expect(t).toContain("20거래일 수익률 +3% 이상 +1 · -3% 이하 -1 · 그 사이 0");
    expect(t).toContain("60거래일 수익률 +6% 이상 +1 · -6% 이하 -1 · 그 사이 0");
    expect(t).toContain("+3점 이상 상승장 · -3점 이하 하락장 · 그 사이 보합장");
    expect(scoreRuleText(null)).toContain("점수 산식을 불러오지 못했습니다(아침 요약 기준 읽기 실패).");
    expect(scoreRuleText(null, true)).toContain("점수 산식을 불러오는 중입니다.");
    // 산식이 없어도 이동평균 한계 문장은 남긴다
    expect(scoreRuleText(null, true)).toContain("미래의 추세 전환을 예측하는 값은 아닙니다");
  });
});

describe("D2 — commonClosedRow(같은 유효 응답의 같은 KODEX 200 마감 뒤 저장 행일 때만)", () => {
  const SAME = { date: "2026-11-11", close: 84540, state: "after_close" as const, fetched_at_kst: "2026-11-11T16:00:00+09:00" };
  const tr = (row: typeof SAME | (Omit<typeof SAME, "state"> & { state: "intraday" | "after_close" | "unknown" })) => ({
    status: "ok" as const,
    basis_date: row.date,
    reason: null,
    context: MORNING_CTX,
    basis_row: row,
  });
  const q = (data: MorningBasisResponse, stale = false): QueryState<MorningBasisResponse> => ({ phase: "success", data, stale });
  it.each<[string, QueryState<MorningBasisResponse>, boolean]>([
    ["같은 행(날짜 · 마감 뒤 · 종가)", q({ ...morningOk(), today_regime: tr(SAME) }), true],
    ["다시 읽기 실패로 남은 이전 응답(유효 응답 아님)", q({ ...morningOk(), today_regime: tr(SAME) }, true), false],
    ["당일 행이 다른 날", q({ ...morningOk(), today_regime: tr({ ...SAME, date: "2026-11-12" }) }), false],
    ["당일 행이 장중 저장", q({ ...morningOk(), today_regime: tr({ ...SAME, state: "intraday" }) }), false],
    ["당일 행 저장 시점 확인 불가", q({ ...morningOk(), today_regime: tr({ ...SAME, state: "unknown" }) }), false],
    [
      "기준일 행 종가가 다름",
      q({
        ...morningOk(),
        today_regime: tr(SAME),
        items: morningOk().items.map((i) => (i.key === "kodex200" ? { ...i, basis_row: { date: "2026-11-11", close: 85000, state: "after_close" as const } } : i)),
      }),
      false,
    ],
    ["아침 판정 미확인", q({ ...morningOk(), today_regime: tr(SAME), morning_regime: { status: "unconfirmed", basis_date: "2026-11-11", reason: "x", context: null } }), false],
    ["당일 판정 미확인", q({ ...morningOk(), today_regime: { ...tr(SAME), status: "unconfirmed", context: null } }), false],
    ["당일 판정 칸 없음", q(morningOk()), false],
    ["읽기 실패 응답", q({ ...morningOk(), status: "invalid", today_regime: tr(SAME) }), false],
    ["첫 조회 실패", { phase: "error" }, false],
  ])("%s", (_t, query, same) => {
    expect(commonClosedRow(query) !== null).toBe(same);
  });
});

// 두 응답 모두 쓸 수 없을 때의 사유 — 한 곳(todayBasis)에서 정해 상자 · 표 · 복사가 같은 문장
describe("todayBasis — 시장 판정 응답 상태(같은 읽기를 못 쓸 때)", () => {
  it.each<[string, QueryState<MorningBasisResponse>["phase"], string | null]>([
    ["시장 판정 응답 실패", "error", "당일 판정을 불러오지 못했습니다"],
    ["시장 판정 응답은 왔으나 판정 칸 없음", "success", "당일 판정 확인 불가(시장 판정 자료 없음)"],
    ["시장 판정 불러오는 중", "loading", null],
  ])("%s", (_t, phase, missing) => {
    const b = todayBasis({ phase: "error" }, null, phase);
    expect(b.ctx).toBeNull();
    expect(b.missing).toBe(missing);
  });
});
