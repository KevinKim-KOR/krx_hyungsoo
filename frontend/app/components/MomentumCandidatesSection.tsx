"use client";

// POC2 Step 5D Cleanup — RunPanel.tsx 에서 분리된 모멘텀 후보 상세 섹션.
// 분리 전후 렌더링 결과 / 문구 / 배치 / 동작 모두 동일.
//
// 정책 (Step5B 합의):
// - 본 섹션은 EvidenceDetails 안에서만 사용된다 (기본 접힘).
// - 승인 초안 기본 영역 / message_text / Telegram 에는 표시되지 않는다 (Top N 정책 금지).
// - placeholder 산식 명시 문구가 헤더에 포함된다.

type MomentumBundle = {
  items: Array<Record<string, unknown>>;
  mode: string;
  engine: string;
};

// Step 5B: draft_payload.momentum_result.candidates 추출 (mode 라벨 포함).
export function pickMomentumCandidates(
  payload: Record<string, unknown>,
): MomentumBundle | null {
  const mr = payload.momentum_result;
  if (!mr || typeof mr !== "object") return null;
  const m = mr as Record<string, unknown>;
  const cands = m.candidates;
  if (!Array.isArray(cands) || cands.length === 0) return null;
  return {
    items: cands as Array<Record<string, unknown>>,
    mode: typeof m.mode === "string" ? m.mode : "holdings",
    engine: typeof m.engine_id === "string" ? m.engine_id : "",
  };
}

interface Props {
  bundle: MomentumBundle | null;
}

export default function MomentumCandidatesSection({ bundle }: Props) {
  if (bundle === null) return null;
  const { items, mode } = bundle;
  return (
    <div className="momentum-candidates" style={{ marginTop: 12 }}>
      <div className="reason-section-title">
        모멘텀 점검 후보 상세 (mode: {mode}, placeholder 산식 — 최종 투자 판단 산식이 아님)
      </div>
      <ul className="reason-list">
        {items.map((c) => {
          const ticker = typeof c.ticker === "string" ? c.ticker : "";
          const name = typeof c.name === "string" ? c.name : ticker;
          const ag = typeof c.account_group === "string" ? c.account_group : "";
          const rank = typeof c.rank === "number" ? c.rank : null;
          const sr = (c.score_result as Record<string, unknown>) ?? {};
          const isScored = Boolean(sr.is_scored);
          const score = typeof sr.score_value === "number" ? sr.score_value : null;
          const unit = typeof sr.score_unit === "string" ? sr.score_unit : "";
          const reason =
            typeof c.reason_text === "string"
              ? c.reason_text
              : typeof c.exclusion_reason === "string"
                ? c.exclusion_reason
                : "";
          const headParts: string[] = [];
          if (rank !== null) headParts.push(`#${rank}`);
          if (ag) headParts.push(`[${ag}]`);
          headParts.push(name);
          if (ticker && ticker !== name) headParts.push(`(${ticker})`);
          const head = headParts.join(" ");
          const valueText = isScored && score !== null ? `${score}${unit}` : "—";
          return (
            <li key={String(c.candidate_id ?? `${ticker}-${ag}`)}>
              <span className="reason-name">{head}</span>
              <span className="reason-text">
                {valueText}
                {reason ? ` · ${reason}` : ""}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
