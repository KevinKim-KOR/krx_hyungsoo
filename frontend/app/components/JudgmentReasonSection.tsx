"use client";

// POC2 Step 5D Cleanup + Step 6 + Step 7A + Step 7B — [판단 사유] 섹션.
//
// Step 7B (2026-05-12) 정책:
// - 기존 "보유 비중 영향" + "모멘텀 점검" 두 별도 bullet 을 공식 PUSH 1 명칭
//   "보유 종목 상태 브리핑" 1줄로 통합.
// - bullet 순서: 보유 종목 상태 브리핑 → 신규 ETF 관찰 후보.
// - 사용자 노출 placeholder 표현 제거 (백엔드와 동일 정정 로직).
// - 매수/매도 의견 아님 중립 안내 항상 포함.
//
// 이전 정책 (보존):
// - bullet 이 0개면 섹션 자체 미생성 (헤더 중복 / 빈 헤더 노출 금지).
// - 종목별 signal / 후보 순위 / Top N 표시 금지.

import type { Run } from "@/lib/api";

type SimpleBullet = { label: string; text: string };

const HOLDINGS_STATUS_BRIEFING_LABEL = "보유 종목 상태 브리핑";
const HOLDINGS_STATUS_BRIEFING_NEUTRAL_NOTE = "이 내용은 매수/매도 의견이 아닙니다.";
const PLACEHOLDER_USER_FACING_PATTERN = "placeholder 기준으로";
const PLACEHOLDER_USER_FACING_REPLACEMENT = "현재 보유 종목 점검 기준으로";

function firstSentence(text: string): string {
  const stripped = text.trim();
  const idx = stripped.indexOf(". ");
  if (idx >= 0) return stripped.substring(0, idx + 1);
  return stripped;
}

// Step 7B — 보유 비중 영향 (factor_signals scope=portfolio) +
// holdings momentum (momentum_result.summary) 를 1줄 bullet 으로 통합.
// 백엔드 _holdings_status_briefing_bullet 과 동일 의미.
export function pickHoldingsStatusBriefing(
  payload: Record<string, unknown>,
): SimpleBullet | null {
  const parts: string[] = [];

  // 1) portfolio scope signal — reason_text 또는 fallback_text 의 첫 문장.
  const fs = payload.factor_signals;
  if (Array.isArray(fs)) {
    for (const sig of fs) {
      if (
        !sig ||
        typeof sig !== "object" ||
        (sig as Record<string, unknown>).scope !== "portfolio"
      ) {
        continue;
      }
      const s = sig as Record<string, unknown>;
      const text = s.is_available ? s.reason_text : s.fallback_text;
      if (typeof text === "string" && text.length > 0) {
        const first = firstSentence(text);
        if (first.length > 0) parts.push(first);
      }
      break;
    }
  }

  // 2) holdings momentum top_candidate.reason_text 첫 문장 (placeholder 정정).
  const mr = payload.momentum_result;
  if (mr && typeof mr === "object") {
    const summary = (mr as Record<string, unknown>).summary;
    if (summary && typeof summary === "object") {
      const s = summary as Record<string, unknown>;
      let text: unknown = null;
      const top = s.top_candidate;
      if (top && typeof top === "object") {
        const t = (top as Record<string, unknown>).reason_text;
        if (typeof t === "string" && t.length > 0) text = t;
      }
      if (text === null) {
        const sr = s.summary_reason_text;
        if (typeof sr === "string" && sr.length > 0) text = sr;
      }
      if (typeof text === "string") {
        let first = firstSentence(text);
        if (first.length > 0) {
          first = first.replace(
            PLACEHOLDER_USER_FACING_PATTERN,
            PLACEHOLDER_USER_FACING_REPLACEMENT,
          );
          parts.push(first);
        }
      }
    }
  }

  if (parts.length === 0) return null;

  const body = parts.join(" ") + " " + HOLDINGS_STATUS_BRIEFING_NEUTRAL_NOTE;
  return { label: HOLDINGS_STATUS_BRIEFING_LABEL, text: body };
}

// Step 6 + Fix 라운드 + Step 7A 명칭 정렬: factor_signals 의 scope="universe" signal 에서 1줄.
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
  const briefingBullet = pickHoldingsStatusBriefing(payload);
  const externalBullet = pickExternalUniverseBullet(payload);

  if (briefingBullet === null && externalBullet === null) return null;

  return (
    <div className="reason-section">
      <div className="reason-section-title">판단 사유</div>
      <ul className="reason-list">
        {briefingBullet ? (
          <li>
            <span className="reason-name">{briefingBullet.label}</span>
            <span className="reason-text">{briefingBullet.text}</span>
          </li>
        ) : null}
        {externalBullet ? (
          <li>
            <span className="reason-name">{externalBullet.label}</span>
            <span className="reason-text">{externalBullet.text}</span>
          </li>
        ) : null}
      </ul>
    </div>
  );
}
