// POC6-33(PLAN §4 D6 · 판정 Q3 · Q38 ~ Q42 · Q53) — 순자산가치(NAV) · 괴리율 자료의 사용자용 한국어 표기 한 곳.
//
// 「데이터 상태」 · 「확인 근거」 NAV 묶음 · ETF 비교하기(workbench/DetailNumbers 괴리 표시)가 같은 낱말을 쓴다.
// 원값(수집 상태 status · 출처 source · 괴리율 표시 flag)은 API 계약 그대로 받고, 화면 글자만 여기서 바꾼다.
// 사전 밖 값은 '상태 확인 필요' · '기타 출처'로 보이고, 원문은 각 화면의 [자세히]에서만 보인다(I-11).
// 이 파일에는 React · JSX 가 없다(lib 는 app/components 를 가져오지 않는다 · lib/dependencyDirection.test.ts).

const DASH = "-";

// 화면의 첫 NAV 표기(Q53 · I-10). 그 화면의 나머지 자리는 'NAV'.
export const NAV_TERM = "순자산가치(NAV)";

// 수집 상태(etf_nav_daily.status) — 저장되는 값은 ok · partial · unavailable 셋(app/etf_nav_service.py).
// partial = 이번 네이버 조회가 실패해 이전에 받아 둔 목록을 새 날짜로 다시 저장한 행.
const NAV_STATUS_LABEL: Record<string, string> = {
  ok: "수집됨",
  partial: "이전 목록 재사용",
  unavailable: "확인 불가",
};
const NAV_STATUS_UNKNOWN = "상태 확인 필요";

export function isKnownNavStatus(status: string | null | undefined): boolean {
  return status != null && Object.prototype.hasOwnProperty.call(NAV_STATUS_LABEL, status);
}

export function navStatusLabel(status: string | null | undefined): string {
  return status != null && isKnownNavStatus(status) ? NAV_STATUS_LABEL[status] : NAV_STATUS_UNKNOWN;
}

// 날짜 칸 이름 — 이전 목록 재사용(partial) 행의 날짜는 기준일이 아니라 다시 저장한 날(Q40 · I-9).
export function navDateLabel(status: string | null | undefined): "기준일" | "재저장일" {
  return status === "partial" ? "재저장일" : "기준일";
}

// 표의 기준일 칸 — 보통 행은 날짜만, 이전 목록 재사용 행은 '재저장일 YYYY-MM-DD'(열 이름 '기준일' 그대로).
export function navDateCell(status: string | null | undefined, date: string | null | undefined): string {
  if (!date) return DASH;
  return status === "partial" ? `${navDateLabel(status)} ${date}` : date;
}

// 출처(etf_nav_daily.source) — 운영 저장값은 naver_etf_item_list 하나(app/naver_etf_universe_fetcher.py SOURCE_LABEL).
const NAV_SOURCE_LABEL: Record<string, string> = {
  naver_etf_item_list: "네이버",
};
const NAV_SOURCE_UNKNOWN = "기타 출처";

export function isKnownNavSource(source: string | null | undefined): boolean {
  return source != null && Object.prototype.hasOwnProperty.call(NAV_SOURCE_LABEL, source);
}

// 값 없음(null · 빈 글자) → '-' · 사전 안 → 한국어 · 사전 밖 → '기타 출처'.
export function navSourceLabel(source: string | null | undefined): string {
  if (!source) return DASH;
  return isKnownNavSource(source) ? NAV_SOURCE_LABEL[source] : NAV_SOURCE_UNKNOWN;
}

// 괴리율 표시(flag) — 백엔드가 읽을 때 |괴리율| 로 정한다(3% 이상 5% 미만 · 5% 이상 · app/etf_nav_fetcher.py).
// 글자는 기존 ETF 비교하기(DetailNumbers) 글자 그대로.
const DISCOUNT_FLAG_LABEL: Record<string, string> = {
  discount_check_needed: "괴리 확인 필요(3% 이상)",
  discount_warning: "괴리 주의(5% 이상)",
};

export function isKnownDiscountFlag(flag: string | null | undefined): boolean {
  return flag != null && Object.prototype.hasOwnProperty.call(DISCOUNT_FLAG_LABEL, flag);
}

// 표시 없음(null) 또는 사전 밖 → null(부르는 쪽이 처리 · DetailNumbers 는 지금처럼 원문을 잇는다).
export function discountFlagLabel(flag: string | null | undefined): string | null {
  return flag != null && isKnownDiscountFlag(flag) ? DISCOUNT_FLAG_LABEL[flag] : null;
}

// 괴리율 표시 글자의 class — 기존 색(두 표시 모두 --warn) 그대로. 규칙 = globals.css '.nav-flag'.
export function discountFlagClass(flag: string | null | undefined): string {
  return isKnownDiscountFlag(flag) ? "nav-flag" : "";
}

// 괴리율 숫자 글자 — 소수 둘째 자리 · 양수만 '+' · 보이는 값이 0.00 이면 부호 없이 '0.00%'(−0.004 도 같음 · '-0.00%' 없음)
// · 값 없음 '-'. 「데이터 상태」 표와 「확인 근거」 NAV 묶음이 같은 함수를 써 같은 저장값이 두 화면에서 같은 글자로 보인다.
export function discountPctText(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "-";
  const r = Number(value.toFixed(2)) || 0;
  if (r === 0) return "0.00%";
  return `${r > 0 ? "+" : ""}${r.toFixed(2)}%`;
}

// 괴리율 숫자 색 — 기존 「데이터 상태」 규칙 그대로: 값 없음 --muted · |값| 5 이상 --danger · 3 이상 --warn · 그 밖 --fg.
export function discountRateColor(value: number | null | undefined): string {
  if (value == null) return "var(--muted)";
  const abs = Math.abs(value);
  if (abs >= 5) return "var(--danger)";
  if (abs >= 3) return "var(--warn)";
  return "var(--fg)";
}
