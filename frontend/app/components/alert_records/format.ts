// POC5-03 「받은 알림 기록」 표기 도우미 — 화면 문구 · 날짜 계산만(조회 · 상태 없음).
//
// 결과 칸 문구는 설계 개정 2 §5 원문을 그대로 쓴다. 수익률은 원시값의 화면 표현일
// 뿐이라 성공 · 실패 색이나 배지를 붙이지 않는다.

import type {
  FeedbackAction,
  Helpfulness,
  LedgerKeyItem,
  LedgerKind,
  LedgerOutcomeRow,
} from "@/lib/api";

// 화면 이름은 기존 「OCI 운영·적용」 표기(OciStatusView PUSH_KIND_LABEL)와 같다.
export const PUSH_KIND_LABEL: Record<string, string> = {
  market_briefing: "시장 브리핑",
  holdings_briefing: "보유 브리핑",
  holdings_risk_alert: "장중 급등락",
};

export const PUSH_KIND_SHORT: Record<string, string> = {
  market_briefing: "시장",
  holdings_briefing: "보유",
  holdings_risk_alert: "장중",
};

export const KIND_FILTERS: { kind: LedgerKind; label: string }[] = [
  { kind: "all", label: "전체" },
  { kind: "market", label: "시장" },
  { kind: "holdings", label: "보유" },
  { kind: "intraday", label: "장중" },
];

export const HELPFULNESS_OPTIONS: { value: Helpfulness; label: string }[] = [
  { value: "HELPFUL", label: "도움됨" },
  { value: "NEUTRAL", label: "보통" },
  { value: "UNHELPFUL_CONFUSING", label: "불필요·혼란" },
];

export const ACTION_OPTIONS: { value: FeedbackAction; label: string }[] = [
  { value: "WATCH_ONLY", label: "관찰만" },
  { value: "BUY_OR_ADD", label: "매수·추가" },
  { value: "SELL_OR_REDUCE", label: "매도·축소" },
  { value: "OTHER", label: "기타" },
];

export function helpfulnessLabel(v: string): string {
  return HELPFULNESS_OPTIONS.find((o) => o.value === v)?.label ?? v;
}

export function actionLabel(v: string | null): string | null {
  if (!v) return null;
  return ACTION_OPTIONS.find((o) => o.value === v)?.label ?? v;
}

// 원장 disposition(POC5-01B ledger_items) → 화면 문구(설계자 RESULT 판정 2026-10-07 확정 표현).
export const DISPOSITION_LABEL: Record<string, string> = {
  sent: "알림 본문에 포함",
  suppressed: "반복 알림 생략",
  cut_by_section_cap: "구역별 항목 수 제한으로 제외",
  cut_by_daily_cap: "하루 알림 횟수 제한으로 제외",
  not_selected: "이번 알림에 포함 안 됨",
  data_unavailable: "자료 문제로 판단 보류",
};

export function dispositionLabel(v: string): string {
  return DISPOSITION_LABEL[v] ?? v;
}

export function subjectName(item: {
  subject_kind: string;
  subject_id: string;
  name: string | null;
}): string {
  if (item.name) return item.name;
  if (item.subject_kind === "market" && item.subject_id === "SP500") return "S&P500";
  return item.subject_id;
}

// 카드 한 줄 — "삼성전자 외 1종목" · "S&P500 외 2개 항목".
export function keyItemSummary(items: LedgerKeyItem[]): string {
  if (items.length === 0) return "";
  const first = subjectName(items[0]);
  const rest = items.length - 1;
  if (rest === 0) return first;
  const unit = items.every((i) => i.subject_kind === "ticker") ? "종목" : "개 항목";
  return `${first} 외 ${rest}${unit}`;
}

// "2026-10-08T09:37:12+09:00" → "10-08 09:37"
export function fmtStamp(iso: string | null): string {
  if (!iso || iso.length < 16) return "—";
  return `${iso.slice(5, 10)} ${iso.slice(11, 16)}`;
}

// 달력 기준 ±n일(설계 개정 2 §5 · 주말도 하루로 센다).
export function shiftDate(day: string, delta: number): string {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + delta);
  return d.toISOString().slice(0, 10);
}

export function fmtPrice(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString("ko-KR", { maximumFractionDigits: 2 });
}

export function fmtReturn(raw: number | null): string {
  if (raw === null || raw === undefined) return "—";
  const pct = raw * 100;
  return `${pct >= 0 ? "+" : "-"}${Math.abs(pct).toFixed(2)}%`;
}

export const HORIZONS = [1, 5, 20] as const;
export const NOT_TARGET = "결과 대상 아님";
export const PENDING = "집계 중";

const STATUS_LABEL: Record<string, string> = {
  PRICE_MISSING: "가격 자료 없음",
  UNTRACKED_AFTER_EXIT: "매도 뒤 추적 중단",
  UNSUPPORTED_PRICE_SOURCE: "지원 계열 없음",
  T0_MISSING: "기준 가격 없음",
};

// 결과 행 한 칸. 행이 없으면 아직 성숙 전(집계 중).
export function outcomeCell(
  row: Pick<LedgerOutcomeRow, "status" | "return_raw"> | undefined,
): string {
  if (!row) return PENDING;
  if (row.status === "MATURED") return fmtReturn(row.return_raw);
  return STATUS_LABEL[row.status] ?? row.status;
}
