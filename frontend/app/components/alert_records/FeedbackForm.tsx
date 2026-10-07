"use client";

// POC5-03 — 선택 평가 입력(append-only). 평가는 선택이다 — 입력하지 않아도 기록 ·
// 결과 조회 · 이후 ML 사용은 그대로다(설계 개정 2 §4 · §12). 저장이 실패하면 성공한
// 것처럼 상태를 바꾸지 않는다(설계 §7).

import { useState } from "react";
import {
  postLedgerFeedback,
  type FeedbackAction,
  type Helpfulness,
} from "@/lib/api";
import { ACTION_OPTIONS, HELPFULNESS_OPTIONS } from "./format";

const MEMO_MAX = 500;

interface Props {
  eventId: string;
  onSaved: () => void;
}

export default function FeedbackForm({ eventId, onSaved }: Props) {
  const [helpfulness, setHelpfulness] = useState<Helpfulness | null>(null);
  const [action, setAction] = useState<FeedbackAction | "">("");
  const [memo, setMemo] = useState("");
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);

  const save = async () => {
    if (!helpfulness) return;
    setSaving(true);
    setResult(null);
    try {
      await postLedgerFeedback(eventId, {
        helpfulness,
        action: action || null,
        memo: memo.trim() ? memo : null,
      });
      setResult({ ok: true, text: "저장했습니다" });
      setHelpfulness(null);
      setAction("");
      setMemo("");
      onSaved();
    } catch (e) {
      setResult({ ok: false, text: `저장하지 못했습니다 — ${(e as Error).message}` });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="ar-feedback">
      <div className="ar-fb-row" role="group" aria-label="내 평가">
        {HELPFULNESS_OPTIONS.map((o) => (
          <button
            key={o.value}
            type="button"
            className="ar-fb-btn"
            aria-pressed={helpfulness === o.value}
            onClick={() => setHelpfulness(o.value)}
          >
            {o.label}
          </button>
        ))}
        <select
          aria-label="선택 행동"
          value={action}
          onChange={(e) => setAction(e.target.value as FeedbackAction | "")}
        >
          <option value="">선택 행동(선택)</option>
          {ACTION_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <input
          type="text"
          aria-label="메모"
          placeholder="메모(선택 · 500자까지)"
          maxLength={MEMO_MAX}
          value={memo}
          onChange={(e) => setMemo(e.target.value)}
        />
        <button
          type="button"
          className="ar-btn-sm"
          disabled={!helpfulness || saving}
          onClick={save}
        >
          {saving ? "저장 중..." : "저장"}
        </button>
      </div>
      {result ? (
        <div className={result.ok ? "ar-note" : "message error"}>{result.text}</div>
      ) : null}
      <p className="helper">
        저장하면 새 평가가 쌓이고 이전 평가도 남습니다. 평가하지 않아도 이 기록은 그대로
        ML 에 쓰입니다.
      </p>
    </div>
  );
}
