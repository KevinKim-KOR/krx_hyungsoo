"use client";

// POC2 Step 5D Cleanup + Step 6 + Step 7A — [판단 사유] 섹션.
// 정책:
// - factor bullet (보유 비중 영향) + momentum bullet (모멘텀 점검) +
//   universe scope bullet (신규 ETF 관찰 후보) 까지 최대 3줄을 한 헤더 아래에.
// - bullet 이 0개면 섹션 자체 미생성 (헤더 중복 / 빈 헤더 노출 금지).
// - bullet 순서: 보유 비중 영향 → 모멘텀 점검 → 신규 ETF 관찰 후보 (Step7A 명칭 정렬).
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

// Step 6 + Fix 라운드: factor_signals 의 scope="universe" signal 에서 1줄 추출.
// 백엔드 draft.py 가 universe_momentum_latest.json → factor signal 1건으로 변환하여
// factor_signals 리스트에 추가한다 (draft_payload 키 신설 없음 — BACKLOG 가드 준수).
// 본 picker 는 신호의 reason_text (성공/부분 성공) 또는 fallback_text (실패) 를
// bullet 본문으로 사용한다.
export function pickExternalUniverseBullet(
  payload: Record<string, unknown>,
): SimpleBullet | null {
  const fs = payload.factor_signals;
  if (!Array.isArray(fs)) return null;
  let universeSig: Record<string, unknown> | null = null;
  for (const sig of fs) {
    if (
      sig &&
      typeof sig === "object" &&
      (sig as Record<string, unknown>).scope === "universe"
    ) {
      universeSig = sig as Record<string, unknown>;
      break;
    }
  }
  if (universeSig === null) return null;
  const factorName =
    typeof universeSig.factor_name === "string"
      ? universeSig.factor_name
      : "신규 ETF 관찰 후보";
  const text = universeSig.is_available
    ? universeSig.reason_text
    : universeSig.fallback_text;
  if (typeof text !== "string" || text.length === 0) return null;
  return { label: factorName, text };
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
