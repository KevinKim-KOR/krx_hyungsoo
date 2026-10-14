// POC5-12 — 정비 큐 VIX 항목(설계 §2 · PLAN §1 · 판정 Q1). 같은 자리 · 같은 이동 버튼 · 문구 3종.
import { describe, it, expect } from "vitest";
import { collectMaintenance } from "./maintenanceQueue";
import type { MarketTopNResponse } from "@/lib/api";
import type { QueryState } from "@/lib/api/queryCache";

const IDLE = { phase: "idle" } as const;

function market(vix: Record<string, unknown>): QueryState<MarketTopNResponse> {
  return {
    phase: "success",
    stale: false,
    data: {
      status: "ok",
      asof: "2026-10-14",
      candidates: [],
      market_context: {
        status: "ok",
        kospi: { status: "ok", as_of_date: "2026-10-13", display_state: "ok" },
      },
      market_risk_reference: {
        kodex200: { availability: "available", as_of_date: "2026-10-14", recent_20d_series: [] },
        vix: { availability: "available", recent_20d_series: [], ...vix },
      },
    } as unknown as MarketTopNResponse,
  };
}

function vixItems(vix: Record<string, unknown>) {
  return collectMaintenance(IDLE, IDLE, IDLE, market(vix)).filter((it) =>
    /VIX|시장 불안 지표/.test(it.text),
  );
}

describe("정비 큐 VIX 항목 (POC5-12)", () => {
  it("첨부 사례: KODEX200 10-14 · VIX 10-13 · fresh → 항목 없음(옛 규칙이면 경고였음)", () => {
    expect(
      vixItems({
        as_of_date: "2026-10-13",
        freshness: { state: "fresh", compare_date: "2026-10-13", weekdays_behind: 0 },
      }),
    ).toEqual([]);
  });

  it("평일 1일 차이는 항목 없음", () => {
    expect(
      vixItems({
        as_of_date: "2026-10-12",
        freshness: { state: "one_weekday_behind", compare_date: "2026-10-13", weekdays_behind: 1 },
      }),
    ).toEqual([]);
  });

  it("update_check: 문구 · heavy · 같은 이동 버튼", () => {
    const got = vixItems({
      as_of_date: "2026-10-09",
      freshness: { state: "update_check", compare_date: "2026-10-13", weekdays_behind: 2 },
    });
    expect(got).toHaveLength(1);
    expect(got[0]).toMatchObject({
      text: "VIX 자료 업데이트 확인 필요(기준일 2026-10-09)",
      kind: "heavy",
      target: "market_discovery",
      actionLabel: "시장 자료 업데이트로",
    });
    expect(got[0].reason).not.toMatch(/시장 기준일|보다 이전/);
  });

  it("date_check · 판정 필드 없음 → 'VIX 기준일 확인 필요'", () => {
    expect(
      vixItems({
        as_of_date: "2026-10-14",
        freshness: { state: "date_check", compare_date: "2026-10-13", weekdays_behind: null },
      }).map((it) => it.text),
    ).toEqual(["VIX 기준일 확인 필요(기준일 2026-10-14)"]);
    expect(vixItems({ as_of_date: "2026-10-01" }).map((it) => it.text)).toEqual([
      "VIX 기준일 확인 필요(기준일 2026-10-01)",
    ]);
  });

  it("VIX 자료 없음 항목은 그대로", () => {
    const got = collectMaintenance(
      IDLE,
      IDLE,
      IDLE,
      market({ availability: "unavailable", as_of_date: null }),
    ).filter((it) => /시장 불안 지표|VIX/.test(it.text));
    expect(got.map((it) => it.text)).toEqual(["시장 불안 지표 자료가 없습니다"]);
  });
});
