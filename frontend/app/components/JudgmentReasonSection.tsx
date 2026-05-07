"use client";

// POC2 Step 5D Cleanup — RunPanel.tsx 에서 분리된 [판단 사유] 섹션.
// 분리 전후 렌더링 결과 / 문구 / 배치 / 동작 / message_text 모두 동일.
//
// 정책 (Step3 + Step5B 합의):
// - factor bullet (보유 비중 영향) + momentum bullet (모멘텀 점검) 두 줄을 한 헤더 아래에 합침.
// - 둘 다 없으면 섹션 자체 미생성 (헤더 중복 / 빈 헤더 노출 금지).
// - 종목별 signal / 후보 순위는 본 섹션에 표시하지 않는다 (Top N 정책 금지).

import type { Run } from "@/lib/api";

type FactorSignal = {
  factor_name: string;
  is_available: boolean;
  reason_text: string | null;
  fallback_text: string | null;
};

type MomentumBullet = { label: string; text: string };

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
): MomentumBullet | null {
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

interface Props {
  run: Run;
}

export default function JudgmentReasonSection({ run }: Props) {
  const payload = (run.draft_payload ?? {}) as Record<string, unknown>;
  const signal = pickPortfolioFactorSignal(payload);
  const momentumBullet = pickMomentumBullet(payload);

  // 두 bullet 중 하나라도 있어야 섹션을 그린다 (헤더 중복 방지 — 백엔드와 동일 정책).
  const factorText = signal
    ? signal.is_available
      ? signal.reason_text
      : signal.fallback_text
    : null;
  const hasFactor =
    signal !== null && typeof factorText === "string" && factorText.length > 0;
  const hasMomentum = momentumBullet !== null;
  if (!hasFactor && !hasMomentum) return null;

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
      </ul>
    </div>
  );
}
