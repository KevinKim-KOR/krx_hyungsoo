"use client";

// POC2 Step 5D Cleanup + Step 6 — [판단 사유] 섹션.
// 정책:
// - factor bullet (보유 비중 영향) + momentum bullet (모멘텀 점검) +
//   external universe bullet (외부 후보 점검) 까지 최대 3줄을 한 헤더 아래에.
// - bullet 이 0개면 섹션 자체 미생성 (헤더 중복 / 빈 헤더 노출 금지).
// - bullet 순서: 보유 비중 영향 → 모멘텀 점검 → 외부 후보 점검 (Step6 §13 / AC-27).
// - 종목별 signal / 후보 순위 / Top N 표시 금지.

import type { Run } from "@/lib/api";

type FactorSignal = {
  factor_name: string;
  is_available: boolean;
  reason_text: string | null;
  fallback_text: string | null;
};

type SimpleBullet = { label: string; text: string };

// Step 3: draft_payload.factor_signals 에서 portfolio scope 1개 추출.
export function pickPortfolioFactorSignal(
  payload: Record<string, unknown>,
): FactorSignal | null {
  const fs = payload.factor_signals;
  if (!Array.isArray(fs)) return null;
  for (const sig of fs) {
    if (
      sig &&
      typeof sig === "object" &&
      (sig as Record<string, unknown>).scope === "portfolio"
    ) {
      const s = sig as Record<string, unknown>;
      return {
        factor_name:
          typeof s.factor_name === "string" ? s.factor_name : "보유 비중 영향",
        is_available: Boolean(s.is_available),
        reason_text: typeof s.reason_text === "string" ? s.reason_text : null,
        fallback_text:
          typeof s.fallback_text === "string" ? s.fallback_text : null,
      };
    }
  }
  return null;
}

// Step 5B: draft_payload.momentum_result.summary 에서 1줄 추출.
export function pickMomentumBullet(
  payload: Record<string, unknown>,
): SimpleBullet | null {
  const mr = payload.momentum_result;
  if (!mr || typeof mr !== "object") return null;
  const summary = (mr as Record<string, unknown>).summary;
  if (!summary || typeof summary !== "object") return null;
  const s = summary as Record<string, unknown>;
  const top = s.top_candidate;
  let text: unknown;
  if (top && typeof top === "object") {
    text = (top as Record<string, unknown>).reason_text;
  }
  if (typeof text !== "string" || text.length === 0) {
    text = s.summary_reason_text;
  }
  if (typeof text !== "string" || text.length === 0) return null;
  return { label: "모멘텀 점검", text };
}

// Step 6: draft_payload.external_universe_check 에서 1줄 조립.
// 기준일 우선순위: top_candidate.price_history_basis.latest_date → universe.asof
// → "기준일 확인 불가". refresh_status 별 형식은 백엔드 build_message_text 와 동일.
export function pickExternalUniverseBullet(
  payload: Record<string, unknown>,
): SimpleBullet | null {
  const universe = payload.external_universe_check;
  if (!universe || typeof universe !== "object") return null;
  const u = universe as Record<string, unknown>;
  const status = u.refresh_status;
  if (status !== "ok" && status !== "partial" && status !== "failed") {
    return null;
  }
  const top = u.top_candidate;
  const asof = typeof u.asof === "string" ? u.asof : null;

  let basisDate = "기준일 확인 불가";
  if (top && typeof top === "object") {
    const phb = (top as Record<string, unknown>).price_history_basis;
    if (phb && typeof phb === "object") {
      const ld = (phb as Record<string, unknown>).latest_date;
      if (typeof ld === "string" && ld.length > 0) basisDate = ld;
    }
  }
  if (basisDate === "기준일 확인 불가" && asof) basisDate = asof;

  if (status === "failed") {
    return {
      label: "외부 후보 점검",
      text: `pykrx 가격 데이터 부족으로 1개월 점검값을 계산하지 못했습니다(기준일 ${basisDate}).`,
    };
  }

  if (!top || typeof top !== "object") return null;
  const t = top as Record<string, unknown>;
  const score = t.score_result;
  if (!score || typeof score !== "object") return null;
  const sv = (score as Record<string, unknown>).score_value;
  const name = typeof t.name === "string" ? t.name : (t.ticker as string) || "(이름 미상)";
  const scored = u.scored_count;
  const total = u.total_count;
  if (
    typeof sv !== "number" ||
    typeof scored !== "number" ||
    typeof total !== "number" ||
    total <= 0
  ) {
    return null;
  }
  return {
    label: "외부 후보 점검",
    text:
      `pykrx 1개월 수익률 기준 ${name}이 가장 높습니다` +
      `(${sv}%, 기준일 ${basisDate}, 계산 가능 ${scored}/${total}개). ` +
      "이 값은 매수 추천이 아닙니다.",
  };
}

interface Props {
  run: Run;
}

export default function JudgmentReasonSection({ run }: Props) {
  const payload = (run.draft_payload ?? {}) as Record<string, unknown>;
  const signal = pickPortfolioFactorSignal(payload);
  const momentumBullet = pickMomentumBullet(payload);
  const externalBullet = pickExternalUniverseBullet(payload);

  const factorText = signal
    ? signal.is_available
      ? signal.reason_text
      : signal.fallback_text
    : null;
  const hasFactor =
    signal !== null && typeof factorText === "string" && factorText.length > 0;
  const hasMomentum = momentumBullet !== null;
  const hasExternal = externalBullet !== null;
  if (!hasFactor && !hasMomentum && !hasExternal) return null;

  return (
    <div className="reason-section">
      <div className="reason-section-title">판단 사유</div>
      <ul className="reason-list">
        {hasFactor && signal ? (
          <li>
            <span className="reason-name">{signal.factor_name}</span>
            <span className="reason-text">{factorText as string}</span>
          </li>
        ) : null}
        {hasMomentum && momentumBullet ? (
          <li>
            <span className="reason-name">{momentumBullet.label}</span>
            <span className="reason-text">{momentumBullet.text}</span>
          </li>
        ) : null}
        {hasExternal && externalBullet ? (
          <li>
            <span className="reason-name">{externalBullet.label}</span>
            <span className="reason-text">{externalBullet.text}</span>
          </li>
        ) : null}
      </ul>
    </div>
  );
}
