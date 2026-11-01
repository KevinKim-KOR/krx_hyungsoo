// POC6-15 — 「ML 연구」 카드 공용 표시 부품(PLAN §8 · 판정 §3 · §4).
//
// - CardConclusion: 제목 바로 아래 '현재 결론 한 줄'(배지 + 짧은 문장). 기존 응답 값만 받아 그린다.
//   새 판정 · 계산은 없다(호출하는 카드가 이미 받은 값으로 문장을 만든다).
// - DevDetails: 표 이름 · 파일 경로 · 작업 번호 · 원문 같은 개발 정보를 접어 두는 칸.
//   경고 · 날짜 · 판정 같은 핵심 근거는 여기로만 숨기지 않는다(카드 본문에도 둔다).

import type { ReactNode } from "react";

export type ConclusionTone = "ok" | "warn" | "muted" | "bad";

const TONE_CLASS: Record<ConclusionTone, string> = {
  ok: "ml-readiness-available",
  warn: "ml-readiness-partial",
  muted: "ml-readiness-missing",
  bad: "ml-readiness-bad",
};

export function toneBadgeClass(tone: ConclusionTone): string {
  return `ml-readiness-badge ${TONE_CLASS[tone]}`;
}

export function CardConclusion({
  tone,
  label,
  children,
}: {
  tone: ConclusionTone;
  label: string;
  children?: ReactNode;
}) {
  return (
    <div className="ml-conclusion" data-role="conclusion">
      <span className={toneBadgeClass(tone)}>{label}</span>
      {children ? <span className="ml-conclusion-text">{children}</span> : null}
    </div>
  );
}

// 시간대가 붙은 ISO 시각만 받는다(날짜만 · 시간대 없는 값 · 깨진 값 = null → 호출하는 쪽이 원문을 그대로 보인다).
const ISO_WITH_ZONE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})$/;

// ISO 시각 → 한국 시각 'YYYY-MM-DD HH:MM:SS'(seconds=false 면 'YYYY-MM-DD HH:MM').
export function kstText(iso: string | null | undefined, seconds = true): string | null {
  if (typeof iso !== "string" || !ISO_WITH_ZONE.test(iso)) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const p = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Seoul",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(d)
      .map((x) => [x.type, x.value])
  );
  const hm = `${p.hour}:${p.minute}`;
  return `${p.year}-${p.month}-${p.day} ${seconds ? `${hm}:${p.second}` : hm}`;
}

// 건수 — 쉼표만 넣고 줄이지 않는다(1382327 → 1,382,327). 숫자가 아니면 "-".
export function fmtCount(n: number | null | undefined): string {
  if (typeof n !== "number" || !Number.isFinite(n)) return "-";
  if (!Number.isInteger(n)) return String(n); // 건수가 아닌 값은 자릿수를 건드리지 않는다
  return n.toLocaleString("en-US");
}

export function DevDetails({ children }: { children: ReactNode }) {
  return (
    <details className="ml-dev-details">
      <summary>자세한 정보(개발 정보)</summary>
      <div className="ml-dev-body">{children}</div>
    </details>
  );
}
