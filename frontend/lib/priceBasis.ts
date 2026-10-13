// POC5-09 — PC 가격 흐름 기준일 문구(「확인 근거」 · 「오늘의 투자 점검」 공용 · 판정 §9-4).
// 날짜는 backend(app/pc_price_basis.py)가 실제 계산 이력에서 준 값만 쓴다. 날짜를 코드에 두지 않는다.
import type { PriceBasis, PriceBasisMismatch } from "@/lib/api";

const UNKNOWN = "확인 불가";

// 기준일별로 묶는다: '삼성전자 · SK하이닉스 · 삼성SDI(저장 가격 기준일 2026-08-12)'.
export function describeMismatched(list: PriceBasisMismatch[]): string {
  const groups = new Map<string, string[]>();
  for (const m of list) {
    const key = m.end_date ?? UNKNOWN;
    const names = groups.get(key) ?? [];
    names.push(m.name ?? m.ticker);
    groups.set(key, names);
  }
  return Array.from(groups)
    .map(([d, names]) => `${names.join(" · ")}(저장 가격 기준일 ${d})`)
    .join(" · ");
}

// 「확인 근거」 목록 위 한 줄.
export function priceBasisLine(basis: PriceBasis): string {
  const ref = basis.reference_date ?? UNKNOWN;
  let s = `가격 흐름(5일 · 20일 · KODEX200 대비) 기준: PC 저장 가격 기준일 ${ref}`;
  if (basis.reference_date && basis.kodex200_start_date_20d) {
    s += ` · KODEX200 20일 비교 기간 ${basis.kodex200_start_date_20d} ~ ${basis.reference_date}`;
  }
  s += ".";
  if (basis.date_mismatch.length > 0) {
    s += ` 기준일이 다른 ${basis.date_mismatch.length}종목은 현재 비교에서 뺐습니다: ${describeMismatched(basis.date_mismatch)}.`;
  }
  return s;
}

export function dateMismatchText(endDate: string | null, referenceDate: string | null): string {
  return `저장 가격 기준일: ${endDate ?? UNKNOWN} / PC 비교 기준일: ${referenceDate ?? UNKNOWN} — 기준일이 달라 현재 비교에 사용하지 않습니다.`;
}

export function windowMismatchText(
  days: 5 | 20,
  start: string | null,
  end: string | null,
  benchStart: string | null,
  referenceDate: string | null,
): string {
  return (
    `KODEX200 대비 ${days}일: 종목 비교 기간 ${start ?? UNKNOWN} ~ ${end ?? UNKNOWN} / ` +
    `KODEX200 비교 기간 ${benchStart ?? UNKNOWN} ~ ${referenceDate ?? UNKNOWN} — 기간이 달라 비교값을 비워 두었습니다.`
  );
}

export const WINDOW_MISMATCH_OTHER_TEXT =
  "KODEX200 비교 기간이 종목과 달라 일부 비교값을 비워 두었습니다.";

// 상세 '가격 흐름 기준' 줄.
export function priceFlowLine(
  end: string,
  start5: string | null,
  start20: string | null,
): string {
  return `기준일 ${end} · 5일 ${start5 ?? UNKNOWN} ~ ${end} · 20일 ${start20 ?? UNKNOWN} ~ ${end}`;
}
