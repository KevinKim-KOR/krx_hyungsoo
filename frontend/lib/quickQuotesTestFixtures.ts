// 시험 전용 — 빠른 시세 저장값(GET /market/quick-quotes · POC6-29 보완). 값 모양 = 2026-11-12 15:36 네이버 공개 시세
// 실측(코스피 · 코스닥 · KODEX 200 · 보유 자료 없음). 시험마다 필요한 칸만 바꿔 쓴다.
import type { QuickQuoteItem, QuickQuotesResponse } from "./api/quickQuotes";

export const QUICK_FETCHED = "2026-11-12T15:36:07+09:00";

export function quickItems(over: Partial<Record<"KOSPI" | "KOSDAQ" | "069500", Partial<QuickQuoteItem>>> = {}): QuickQuoteItem[] {
  const ok = (value: number, change: number, pct: number, time: string) => ({
    value,
    change,
    change_pct: pct,
    source_time: time,
    trade_date: "2026-11-12",
    market_status: "CLOSE",
    fetched_at: QUICK_FETCHED,
  });
  const at = { at: QUICK_FETCHED, status: "updated" as const, reason: null };
  return [
    { code: "KOSPI", name: "코스피", kind: "index", quote: ok(5342.73, -32.63, -0.61, "2026-11-12T15:36:00+09:00"), last_attempt: at, ...over.KOSPI },
    { code: "KOSDAQ", name: "코스닥", kind: "index", quote: ok(696.53, -8.57, -1.22, "2026-11-12T15:36:00+09:00"), last_attempt: at, ...over.KOSDAQ },
    { code: "069500", name: "KODEX 200", kind: "stock", quote: ok(84240, -300, -0.35, "2026-11-12T15:35:18+09:00"), last_attempt: at, ...over["069500"] },
  ];
}

export function quickOk(over: Parameters<typeof quickItems>[0] = {}): QuickQuotesResponse {
  return { status: "ok", message: null, items: quickItems(over) };
}

// 한 번도 받은 적 없음(파일 없음) — 세 칸 모두 '시세 미확인'.
export function quickEmpty(): QuickQuotesResponse {
  return {
    status: "empty",
    message: null,
    items: quickItems({
      KOSPI: { quote: null, last_attempt: null },
      KOSDAQ: { quote: null, last_attempt: null },
      "069500": { quote: null, last_attempt: null },
    }),
  };
}
