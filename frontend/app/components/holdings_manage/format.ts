// POC5-05 개정 2 — 「종목 관리」 매매 · History 공용 표시 helper.
// 백엔드 숫자는 Decimal 십진 문자열이다. 화면 반올림은 표시용으로만 쓰고 다음 계산에 쓰지 않는다.
// 저장 전 미리보기(previewTrade)는 화면 안내용 근사값이며, 저장 결과는 늘 서버 계산을 따른다.

import { ApiRequestError } from "@/lib/api";
import { fmtSignedMoney, fmtSignedPct, pnlClass, toFiniteNumber } from "@/lib/holdings_view";

export { fmtSignedMoney, fmtSignedPct, pnlClass, toFiniteNumber };

// null · undefined · 빈 문자열은 숫자 0 이 아니라 '없음'(Number(null) = 0 함정 방지).
function numOrNull(v: unknown): number | null {
  return v === null || v === undefined || v === "" ? null : toFiniteNumber(v);
}

export function fmtNum(v: unknown, digits = 2): string {
  const n = numOrNull(v);
  if (n === null) return "—";
  return n.toLocaleString("ko-KR", { maximumFractionDigits: digits });
}

export function fmtWon(v: unknown, digits = 2): string {
  const n = numOrNull(v);
  return n === null ? "—" : `${fmtNum(n, digits)}원`;
}

// 입력칸 문자열(쉼표 허용) → 숫자. 빈칸 · 숫자 아님은 null.
export function parseInput(text: string): number | null {
  const t = text.replace(/,/g, "").trim();
  if (!t) return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

// 서버로 보낼 십진 문자열(쉼표만 제거 · 반올림하지 않는다 · 자릿수 검증은 서버가 한다).
export function toDecimalText(text: string): string {
  return text.replace(/,/g, "").trim();
}

// 저장된 숫자를 지수 표기 없이 같은 값의 십진 문자열로(1e-7 → "0.0000001" · 1e+21 → "1000…0").
// 입력칸 콤마 처리는 숫자 · 소수점만 남겨 'e' 를 지우므로(1e-7 → "17"), 칸에 채우기 전에 풀어 쓴다.
export function plainNumberText(n: number): string {
  const s = String(n);
  const m = /^(-?)(\d+)(?:\.(\d+))?e([+-]\d+)$/.exec(s);
  if (!m) return s;
  const [, sign, intPart, frac = "", expText] = m;
  const digits = intPart + frac;
  const point = intPart.length + Number(expText);
  if (point <= 0) return `${sign}0.${"0".repeat(-point)}${digits}`;
  if (point >= digits.length) return `${sign}${digits}${"0".repeat(point - digits.length)}`;
  return `${sign}${digits.slice(0, point)}.${digits.slice(point)}`;
}

export type TradeKind = "buy" | "sell" | "sell_all";

export interface TradePreview {
  quantity: number;
  avg: number | null;
  realized: number | null;
  rate: number | null;
  oversell: boolean;
}

// 이동평균 미리보기(설계 §3): 매수 C += b×p · 매도분 원가 = C×s/Q · 남은 평단 유지.
export function previewTrade(
  q: number,
  c: number,
  kind: TradeKind,
  price: number | null,
  qty: number | null,
): TradePreview | null {
  if (price === null || qty === null || price <= 0 || qty <= 0) return null;
  if (kind === "buy") {
    const nq = q + qty;
    return { quantity: nq, avg: (c + qty * price) / nq, realized: null, rate: null, oversell: false };
  }
  if (qty > q + 1e-9) return { quantity: q, avg: q > 0 ? c / q : null, realized: null, rate: null, oversell: true };
  const cost = Math.abs(qty - q) < 1e-9 ? c : (c * qty) / q;
  const realized = qty * price - cost;
  const left = q - qty;
  return {
    quantity: left < 1e-9 ? 0 : left,
    avg: left < 1e-9 ? null : c / q,
    realized,
    rate: cost > 0 ? (realized / cost) * 100 : null,
    oversell: false,
  };
}

// 저장 동작마다 새 UUID(같은 내용의 재시도에는 같은 값을 다시 쓴다).
export function newSaveId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  const hex = Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16));
  hex[12] = "4";
  hex[16] = ((parseInt(hex[16], 16) & 0x3) | 0x8).toString(16);
  const s = hex.join("");
  return `${s.slice(0, 8)}-${s.slice(8, 12)}-${s.slice(12, 16)}-${s.slice(16, 20)}-${s.slice(20)}`;
}

// API 오류 → 사람이 읽는 문구(백엔드 detail 은 문자열 · 객체면 [object Object] 대신 요약).
export function apiErrorText(e: unknown): string {
  if (e instanceof ApiRequestError) {
    const body = e.body as { detail?: unknown } | null;
    const detail = body && typeof body === "object" ? body.detail : null;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return "입력값을 확인하세요.";
    if (e.httpStatus === 0) return e.message;
    return `요청 실패 (HTTP ${e.httpStatus})`;
  }
  return e instanceof Error ? e.message : String(e);
}

export function todayKst(): string {
  const now = new Date(Date.now() + 9 * 3600 * 1000);
  return now.toISOString().slice(0, 10);
}

export const KIND_LABEL: Record<string, string> = {
  BASELINE: "기준잔고",
  REGISTER: "잔고 등록",
  BUY: "매수",
  SELL: "매도",
  ADJUSTMENT: "입력 정정",
  VOID: "취소",
};
