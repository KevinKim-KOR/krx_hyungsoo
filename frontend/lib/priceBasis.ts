// POC5-09 — 가격 기준일(price_basis.reference_date) 문구(「확인 근거」 전용 · 판정 §9-4).
// 날짜는 backend(app/pc_price_basis.py)가 실제 계산 이력에서 준 값만 쓴다. 날짜를 코드에 두지 않는다.
import type { PriceBasis, PriceBasisMismatch } from "@/lib/api";

const UNKNOWN = "확인 불가";

// 종목 마지막 저장일(항목 end_date)별로 묶는다: '보유 A · 보유 B(마지막 저장일 2026-08-12)'.
// POC6-33 RESULT 판정 §2-6 — 종목 자신의 마지막 저장일은 '마지막 저장일', reference_date 는 '가격 기준일'.
export function describeMismatched(list: PriceBasisMismatch[]): string {
  const groups = new Map<string, string[]>();
  for (const m of list) {
    const key = m.end_date ?? UNKNOWN;
    const names = groups.get(key) ?? [];
    names.push(m.name ?? m.ticker);
    groups.set(key, names);
  }
  return Array.from(groups)
    .map(([d, names]) => `${names.join(" · ")}(마지막 저장일 ${d})`)
    .join(" · ");
}

// 「확인 근거」 목록 위 한 줄. POC6-33(판정 Q31 · Q47 · PLAN E1) — 가격 기준일(reference_date) 날짜는 목록 위 요약
// 칸 '가격 기준일' 한 곳에만 이름을 붙여 보이고, 이 줄은 KODEX 200 비교 기간 · 뺀 종목만 적는다. 5 · 20 은 '저장일'.
export function priceBasisLine(basis: PriceBasis): string {
  let s = "가격 흐름(최근 5 · 20저장일 · KODEX 200 대비) 기준";
  s +=
    basis.reference_date && basis.kodex200_start_date_20d
      ? ` · KODEX 200 20저장일 비교 기간 ${basis.kodex200_start_date_20d} ~ ${basis.reference_date}`
      : ` · KODEX 200 20저장일 비교 기간 ${UNKNOWN}`;
  s += ".";
  if (basis.date_mismatch.length > 0) {
    s += ` 마지막 저장일이 가격 기준일과 다른 ${basis.date_mismatch.length}종목은 현재 비교에서 뺐습니다: ${describeMismatched(basis.date_mismatch)}.`;
  }
  return s;
}

export function dateMismatchText(endDate: string | null, referenceDate: string | null): string {
  return `이 종목 마지막 저장일: ${endDate ?? UNKNOWN} / 가격 기준일: ${referenceDate ?? UNKNOWN} — 두 날짜가 달라 현재 비교에 사용하지 않습니다.`;
}

export function windowMismatchText(
  days: 5 | 20,
  start: string | null,
  end: string | null,
  benchStart: string | null,
  referenceDate: string | null,
): string {
  return (
    `KODEX 200 대비 ${days}저장일: 종목 비교 기간 ${start ?? UNKNOWN} ~ ${end ?? UNKNOWN} / ` +
    `KODEX 200 비교 기간 ${benchStart ?? UNKNOWN} ~ ${referenceDate ?? UNKNOWN} — 기간이 달라 비교값을 비워 두었습니다.`
  );
}

export const WINDOW_MISMATCH_OTHER_TEXT =
  "KODEX 200 비교 기간이 종목과 달라 일부 비교값을 비워 두었습니다.";

// 상세 '가격 흐름 기준' 줄(5 · 20 = 저장일 · 판정 Q47).
export function priceFlowLine(
  end: string,
  start5: string | null,
  start20: string | null,
): string {
  // 이 종목 자신의 마지막 날짜 — '가격 기준일'(price_basis.reference_date)과 구별해 '마지막 저장일'(RESULT 판정 §2-6).
  return `마지막 저장일 ${end} · 5저장일 ${start5 ?? UNKNOWN} ~ ${end} · 20저장일 ${start20 ?? UNKNOWN} ~ ${end}`;
}
