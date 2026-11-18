// POC6-32 V2(PLAN §2 S4 · S6 · §4-4 · §9 I-1 ~ I-5) — 보낸 화면 기록 · 한 번 넘김(순수 함수 · 모듈 메모리).
// 화면 key 는 아무 문자열(lib 는 화면 모듈을 모름) — 상세 여부는 부르는 쪽이 넘긴다.
import { describe, it, expect } from "vitest";
import {
  navBack,
  navGo,
  navHighlight,
  navSelect,
  navSender,
  navStack,
  navStart,
  presetExposureSingle,
  presetOpenRecord,
  takeExposureSingle,
  takeOpenRecord,
  type NavState,
} from "./detailNav";

type K = "weekly" | "list" | "exposure" | "compare" | "sessions";
const DETAIL = new Set<K>(["exposure", "compare"]);
const go = (s: NavState<K>, key: K) => navGo(s, s.active.id, key, DETAIL.has(key));
const keys = (s: NavState<K>) => navStack(s).map((e) => e.key);

describe("보낸 화면 기록", () => {
  it("상세로 가면 지금 화면을 기록 끝에 넣는다 · 강조 = 처음 보낸 화면 · 돌아갈 곳 = 기록 끝", () => {
    let s = navStart<K>("weekly");
    expect(navHighlight(s)).toBe("weekly");
    expect(navSender(s)).toBeNull();
    s = go(s, "exposure");
    s = go(s, "compare");
    expect(keys(s)).toEqual(["weekly", "exposure", "compare"]);
    expect(navHighlight(s)).toBe("weekly");
    expect(navSender(s)?.key).toBe("exposure");
  });

  it("[← 보낸 화면으로]는 한 단계씩 · 숨겨 둔 그 화면(같은 번호)으로 · 기록이 없으면 그대로", () => {
    let s = navStart<K>("weekly");
    const weeklyId = s.active.id;
    s = go(s, "exposure");
    const exposureId = s.active.id;
    s = go(s, "compare");
    s = navBack(s);
    expect(s.active).toEqual({ key: "exposure", id: exposureId });
    expect(keys(s)).toEqual(["weekly", "exposure"]);
    s = navBack(s);
    expect(s.active).toEqual({ key: "weekly", id: weeklyId });
    expect(s.trail).toEqual([]);
    expect(navBack(s)).toBe(s);
  });

  it("메뉴 클릭 = 기록을 버리고 새 번호로 처음부터(강조 중인 메뉴를 눌러도) · 기록이 없을 때 지금 화면 메뉴는 그대로", () => {
    let s = navStart<K>("weekly");
    const firstId = s.active.id;
    expect(navSelect(s, "weekly")).toBe(s);
    s = go(s, "compare");
    s = navSelect(s, "weekly");
    expect(s.trail).toEqual([]);
    expect(s.active.key).toBe("weekly");
    expect(s.active.id).not.toBe(firstId);
    s = go(s, "exposure");
    s = navSelect(s, "list");
    expect(keys(s)).toEqual(["list"]);
  });

  it("화면 안에서 상세가 아닌 화면으로 가면 기록을 버린다 · 같은 화면으로의 이동 · 숨겨 둔 화면의 이동은 무시", () => {
    let s = navStart<K>("weekly");
    const weeklyId = s.active.id;
    s = go(s, "compare");
    // 숨겨 둔 「주간」이 부른 이동은 무시
    expect(navGo(s, weeklyId, "exposure", true)).toBe(s);
    // 같은 화면으로의 이동은 그대로
    expect(go(s, "compare")).toBe(s);
    s = go(s, "sessions");
    expect(keys(s)).toEqual(["sessions"]);
    expect(navHighlight(s)).toBe("sessions");
    // 기록을 버린 뒤 같은 key 로 가면 새 번호(처음부터)
    s = go(s, "weekly");
    expect(s.active.key).toBe("weekly");
    expect(s.active.id).not.toBe(weeklyId);
  });
});

describe("한 번 넘김", () => {
  it("「ETF 구성종목」 한 ETF — 한 번 읽으면 비움 · 넘긴 뒤 원본을 바꿔도 그대로", () => {
    expect(takeExposureSingle()).toBeNull();
    const p = { ticker: "T00001", name: "가상 ETF 하나", from: "「주간 ETF 점검」", condition: { basis: "one_month" } };
    presetExposureSingle(p);
    p.name = "바뀐 이름";
    expect(takeExposureSingle()).toEqual({
      ticker: "T00001",
      name: "가상 ETF 하나",
      from: "「주간 ETF 점검」",
      condition: { basis: "one_month" },
    });
    expect(takeExposureSingle()).toBeNull();
  });

  it("「AI 투자 세션」 기록 열기 — 한 번 읽으면 비움 · 마지막 값", () => {
    expect(takeOpenRecord()).toBeNull();
    presetOpenRecord("rec-a");
    presetOpenRecord("rec-b");
    expect(takeOpenRecord()).toBe("rec-b");
    expect(takeOpenRecord()).toBeNull();
  });
});
