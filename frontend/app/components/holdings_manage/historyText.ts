// POC5-05 개정 2 — History 창 · 과거 보유 · 시장 흐름 표시 문구(순수 함수 · 화면 표시용 반올림만).
// 백엔드 숫자는 Decimal 십진 문자열이다. 값이 없음(null)은 '—' 로 보이고 0 으로 바꾸지 않는다
// (공용 toFiniteNumber 는 null 을 0 으로 읽으므로 여기서 먼저 거른다).

import type { HoldingCycleView, TradeEventView, TradeRecordView } from "@/lib/api";
import { KIND_LABEL, fmtNum, fmtSignedMoney, fmtSignedPct, toFiniteNumber } from "./format";

type Payload = Record<string, unknown>;

function missing(v: unknown): boolean {
  return v === null || v === undefined || v === "";
}

// 숫자 표시(없으면 '—'). 수량은 digits=6 · 금액 · 단가는 2.
export function dash(v: unknown, digits = 2): string {
  return missing(v) ? "—" : fmtNum(v, digits);
}

// 부호 붙은 금액(원 없이 · 표 칸용).
export function signedNum(v: unknown): string {
  if (missing(v)) return "—";
  const n = toFiniteNumber(v);
  if (n === null) return "—";
  return `${n > 0 ? "+" : ""}${fmtNum(n)}`;
}

// 부호 붙은 금액(원 포함 · 요약 칸용).
export function signedWon(v: unknown): string {
  return missing(v) ? "—" : (fmtSignedMoney(v) ?? "—");
}

export function pct(v: unknown): string {
  return missing(v) ? "—" : (fmtSignedPct(v) ?? "—");
}

export function isZero(v: unknown): boolean {
  return !missing(v) && toFiniteNumber(v) === 0;
}

function text(v: unknown): string | null {
  return typeof v === "string" && v ? v : null;
}

// 저장 시각 "2026-10-08T21:05:12+09:00" → "2026-10-08 21:05"(KST 로 저장된 값 그대로).
export function savedAt(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(iso);
  return m ? `${m[1]} ${m[2]}` : iso;
}

// 매매 기록의 날짜(+시각). 시각을 모르면 날짜만(00:00 으로 채우지 않는다).
export function tradeWhen(payload: Payload): string {
  const day = text(payload.trade_date) ?? "—";
  const time = text(payload.trade_time);
  return time ? `${day} ${time}` : day;
}

export function eventWhen(ev: TradeEventView): string {
  if (ev.kind === "BUY" || ev.kind === "SELL") return tradeWhen(ev.payload);
  if (ev.kind === "BASELINE" || ev.kind === "REGISTER") return "미상";
  return ev.date ?? "—";
}

// 구분 칸: 최초 매수 = 실제 매수로 시작한 기간의 계산 순서상 첫 매수 · 전량매도 = 잔량 0 이 된 매도 ·
// 수량 0 입력 정정 = '입력 정정(종료)'(매도가 아님).
export function eventLabel(ev: TradeEventView, firstBuyId: string | null): string {
  if (ev.kind === "BUY") return ev.record_id === firstBuyId ? "최초 매수" : "추가매수";
  if (ev.kind === "SELL") return isZero(ev.q_after) ? "전량매도" : "분할매도";
  if (ev.kind === "ADJUSTMENT" && "quantity" in ev.payload && isZero(ev.payload.quantity)) {
    return "입력 정정(종료)";
  }
  return KIND_LABEL[ev.kind] ?? "기록";
}

export function firstBuyId(cycle: HoldingCycleView): string | null {
  if (cycle.opened_by !== "BUY") return null;
  return cycle.events.find((e) => e.kind === "BUY")?.record_id ?? null;
}

// 입력 정정 줄: 정정 전 → 정정 후(입력 당시 값) · 종목명만이면 종목명 정정.
export function adjustmentText(payload: Payload): string {
  const before = (payload.before && typeof payload.before === "object" ? payload.before : {}) as Payload;
  const parts: string[] = [];
  if ("quantity" in payload) {
    const prev = `정정 전 수량 · 평단 ${dash(before.quantity, 6)} · ${dash(before.avg_buy_price)}`;
    const next = isZero(payload.quantity)
      ? "정정 후 0 (입력 정정으로 종료)"
      : `정정 후 ${dash(payload.quantity, 6)} · ${dash(payload.avg_buy_price)}`;
    parts.push(`${prev} → ${next}`);
  }
  if ("name" in payload) {
    parts.push(`종목명 정정: ${text(before.name) ?? "—"} → ${text(payload.name) ?? "—"}`);
  }
  return parts.join(" · ") || "입력 정정";
}

// 정정 전 입력 · 취소한 기록 한 줄 요약.
export function recordBrief(r: TradeRecordView): string {
  const p = r.payload;
  const kind = r.kind === "BUY" ? "매수" : r.kind === "SELL" ? "매도" : (KIND_LABEL[r.kind] ?? "기록");
  return `${tradeWhen(p)} ${kind} · 수량 ${dash(p.quantity, 6)} · 체결단가 ${dash(p.price)}`;
}

// 보유 기간 문구: 시작(매수일 미상) ~ 종료.
export function periodText(cycle: HoldingCycleView): string {
  const start = cycle.start_date ?? "매수일 미상";
  return cycle.status === "OPEN" ? `${start} ~` : `${start} ~ ${cycle.end_date ?? "—"}`;
}
