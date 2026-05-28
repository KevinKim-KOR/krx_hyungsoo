"use client";

// AI Sessions / 새 기록 저장 탭 (POC2 — 2026-05-21).
//
// Market Discovery 의 "AI Sessions로 넘기기" 가 sessionStorage 에 적재한 draft
// (asof / filters / candidate_snapshot / question_text) 를 자동 채움한 뒤,
// 사용자가 GPT / Gemini / Claude 답변 + 메모 + 1차 판정 + 다음 확인 항목을
// 입력해서 POST /decision/sessions 로 저장한다.
//
// draft 가 없으면 저장을 막고 안내 문구 표시 (지시문 §5.4 / AC-7).
//
// AI API 직접 호출 / 자동 토론은 본 STEP 의 작업이 아니다.

import { useCallback, useMemo, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  DECISION_VERDICT_LABEL,
  DEFAULT_DECISION_VERDICT,
  createDecisionSession,
  type DecisionUserVerdict,
} from "@/lib/api";
import {
  clearAISessionsDraft,
  type AISessionsDraft,
} from "@/lib/aiSessionsDraft";

interface Props {
  draft: AISessionsDraft | null;
  onSaved: () => void;
}

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패(HTTP ${e.httpStatus}): ${e.message}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

function splitNextChecks(raw: string): string[] {
  return raw
    .split("\n")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

const VERDICT_OPTIONS: DecisionUserVerdict[] = [
  "useful",
  "needs_constituents",
  "needs_market_compare",
  "hold",
];

function FiltersSummary({ draft }: { draft: AISessionsDraft }) {
  const f = draft.filters;
  const items: string[] = [];
  if (f.exclude_inverse) items.push("인버스 제외");
  if (f.exclude_leveraged) items.push("레버리지 제외");
  if (f.exclude_synthetic) items.push("합성 제외");
  if (f.exclude_futures) items.push("선물형 제외");
  return (
    <div className="helper">
      {items.length > 0 ? items.join(" · ") : "필터 없음"}
    </div>
  );
}

function CandidatesSummary({ draft }: { draft: AISessionsDraft }) {
  const cs = draft.candidate_snapshot;
  if (cs.length === 0) {
    return <div className="helper">후보 없음</div>;
  }
  const head = cs.slice(0, 3).map((c) => c.name ?? c.ticker ?? "-");
  const tail = cs.length > 3 ? ` 외 ${cs.length - 3}건` : "";
  return (
    <div className="helper">
      총 {cs.length}건 — {head.join(", ")}
      {tail}
    </div>
  );
}

export default function AISessionsCreateTab({ draft, onSaved }: Props) {
  const initialQuestion = useMemo(
    () => (draft ? draft.question_text : ""),
    [draft],
  );

  const [questionText, setQuestionText] = useState<string>(initialQuestion);
  const [gptAnswer, setGptAnswer] = useState<string>("");
  const [geminiAnswer, setGeminiAnswer] = useState<string>("");
  const [claudeAnswer, setClaudeAnswer] = useState<string>("");
  const [userMemo, setUserMemo] = useState<string>("");
  const [userVerdict, setUserVerdict] = useState<DecisionUserVerdict>(
    DEFAULT_DECISION_VERDICT,
  );
  const [nextChecksRaw, setNextChecksRaw] = useState<string>("");
  const [saving, setSaving] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const hasAtLeastOneAnswer =
    gptAnswer.trim().length > 0 ||
    geminiAnswer.trim().length > 0 ||
    claudeAnswer.trim().length > 0;

  const canSave =
    draft !== null &&
    draft.candidate_snapshot.length > 0 &&
    questionText.trim().length > 0 &&
    hasAtLeastOneAnswer &&
    !saving;

  const handleSave = useCallback(async () => {
    if (!draft) {
      setErrorMessage(
        "Market Discovery 에서 후보를 조회한 뒤 'AI Sessions로 넘기기'를 먼저 실행하세요.",
      );
      return;
    }
    if (!hasAtLeastOneAnswer) {
      setErrorMessage(
        "GPT / Gemini / Claude 답변 중 최소 1개 이상을 입력해야 저장됩니다.",
      );
      return;
    }
    setSaving(true);
    setStatusMessage(null);
    setErrorMessage(null);
    try {
      const res = await createDecisionSession({
        asof: draft.asof,
        source_screen: "market_discovery",
        filters: draft.filters,
        candidate_snapshot: draft.candidate_snapshot,
        question_text: questionText,
        gpt_answer_text: gptAnswer,
        gemini_answer_text: geminiAnswer,
        claude_answer_text: claudeAnswer,
        user_memo: userMemo,
        user_verdict: userVerdict,
        next_checks: splitNextChecks(nextChecksRaw),
        linked_market_refresh_id: draft.linked_market_refresh_id,
        // 2026-05-22 — Market Discovery 에서 넘어온 시장 문맥 그대로 영속화.
        market_context_snapshot: draft.market_context_snapshot ?? null,
        // 2026-05-27 — ETF Exposure 에서 넘어온 구성종목/중복률 snapshot.
        // Market Discovery 직접 흐름에서는 null.
        constituent_snapshot: draft.constituent_snapshot ?? null,
        overlap_snapshot: draft.overlap_snapshot ?? null,
      });
      setStatusMessage(
        `저장 완료 (id: ${res.id}). [기록 조회] 탭에서 확인할 수 있습니다.`,
      );
      // draft + 입력 모두 클리어 — 다음 기록과 섞이지 않도록.
      clearAISessionsDraft();
      setQuestionText("");
      setGptAnswer("");
      setGeminiAnswer("");
      setClaudeAnswer("");
      setUserMemo("");
      setUserVerdict(DEFAULT_DECISION_VERDICT);
      setNextChecksRaw("");
      onSaved();
    } catch (e) {
      setErrorMessage(describeError(e));
    } finally {
      setSaving(false);
    }
  }, [
    draft,
    hasAtLeastOneAnswer,
    questionText,
    gptAnswer,
    geminiAnswer,
    claudeAnswer,
    userMemo,
    userVerdict,
    nextChecksRaw,
    onSaved,
  ]);

  if (!draft) {
    return (
      <div className="card decision-card">
        <h2>새 기록 저장</h2>
        <div className="message info">
          Market Discovery 에서 후보를 조회한 뒤 &ldquo;AI Sessions로
          넘기기&rdquo;를 실행하세요. 저장에는 후보 스냅샷이 필수입니다.
        </div>
      </div>
    );
  }

  return (
    <div className="card decision-card">
      <h2>새 기록 저장</h2>
      <p className="helper" style={{ marginBottom: 8 }}>
        Market Discovery 에서 넘어온 후보를 기반으로 외부 AI(GPT / Gemini /
        Claude) 답변과 사용자 메모 / 1차 판정을 저장합니다. AI 를 직접 호출하지
        않습니다.
      </p>

      <h3>기준일 (asof)</h3>
      <div className="decision-pre" style={{ padding: "8px 12px" }}>
        {draft.asof}
      </div>

      <h3>필터 조건</h3>
      <FiltersSummary draft={draft} />

      <h3>후보 스냅샷</h3>
      <CandidatesSummary draft={draft} />

      <label htmlFor="ais-question">AI 에게 보낸 질문 (자동 채움 / 편집 가능)</label>
      <textarea
        id="ais-question"
        className="decision-textarea"
        value={questionText}
        onChange={(e) => setQuestionText(e.target.value)}
        rows={8}
      />

      <label htmlFor="ais-gpt">GPT 답변</label>
      <textarea
        id="ais-gpt"
        className="decision-textarea"
        value={gptAnswer}
        onChange={(e) => setGptAnswer(e.target.value)}
        rows={6}
        placeholder="ChatGPT 답변을 그대로 붙여넣으세요."
      />

      <label htmlFor="ais-gemini">Gemini 답변</label>
      <textarea
        id="ais-gemini"
        className="decision-textarea"
        value={geminiAnswer}
        onChange={(e) => setGeminiAnswer(e.target.value)}
        rows={6}
        placeholder="Gemini 답변을 그대로 붙여넣으세요."
      />

      <label htmlFor="ais-claude">Claude 답변</label>
      <textarea
        id="ais-claude"
        className="decision-textarea"
        value={claudeAnswer}
        onChange={(e) => setClaudeAnswer(e.target.value)}
        rows={6}
        placeholder="Claude 답변을 그대로 붙여넣으세요."
      />

      <label htmlFor="ais-memo">사용자 메모</label>
      <textarea
        id="ais-memo"
        className="decision-textarea"
        value={userMemo}
        onChange={(e) => setUserMemo(e.target.value)}
        rows={4}
        placeholder="해석 / 의문점 / 다음 액션 등을 자유롭게."
      />

      <label htmlFor="ais-verdict">사용자 1차 판정</label>
      <select
        id="ais-verdict"
        className="decision-select"
        value={userVerdict}
        onChange={(e) => setUserVerdict(e.target.value as DecisionUserVerdict)}
      >
        {VERDICT_OPTIONS.map((v) => (
          <option key={v} value={v}>
            {DECISION_VERDICT_LABEL[v]}
          </option>
        ))}
      </select>

      <label htmlFor="ais-next-checks">
        다음 확인 항목 (한 줄당 1항목)
      </label>
      <textarea
        id="ais-next-checks"
        className="decision-textarea"
        value={nextChecksRaw}
        onChange={(e) => setNextChecksRaw(e.target.value)}
        rows={4}
        placeholder={"예:\nKODEX200 대비 초과수익 확인\n구성 종목 중복률 확인"}
      />

      <div className="btn-row" style={{ marginTop: 12 }}>
        <button type="button" onClick={handleSave} disabled={!canSave}>
          {saving ? "저장 중..." : "기록 저장"}
        </button>
      </div>

      {!hasAtLeastOneAnswer ? (
        <div className="helper" style={{ marginTop: 6 }}>
          GPT / Gemini / Claude 답변 중 최소 1개 이상 입력하면 저장할 수 있습니다.
        </div>
      ) : null}

      {statusMessage ? (
        <div className="message info" style={{ marginTop: 8 }}>
          {statusMessage}
        </div>
      ) : null}
      {errorMessage ? (
        <div className="message error" style={{ marginTop: 8 }}>
          {errorMessage}
        </div>
      ) : null}
    </div>
  );
}
