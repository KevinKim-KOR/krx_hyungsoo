"use client";

// 개발/테스트용 — 운영 입력 아님.
// 고정된 샘플 input_data 1세트로 generateDraft 를 호출한다 (사용자 결정 #5:
// "필요하면 고정된 샘플 초안을 생성하는 버튼만 둡니다"). JSON 직접 입력 폼은 폐기.

import { useCallback, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  generateDraft,
  type Run,
} from "@/lib/api";

const FIXED_SAMPLE_INPUT = {
  title: "샘플 초안 (개발/테스트용)",
  note: "운영 입력 아님 — 샘플 버튼으로 생성된 초안입니다.",
  recommendations: [
    { ticker: "069500", score: 0.5, action: "HOLD" },
  ],
};

interface Props {
  onDraftCreated: (run: Run) => void;
}

export default function SampleDraftQuickButton({ onDraftCreated }: Props) {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const onClick = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const run = await generateDraft(FIXED_SAMPLE_INPUT);
      onDraftCreated(run);
    } catch (e) {
      if (e instanceof ApiConfigError) {
        setError(`구성 오류: ${e.message}`);
      } else if (e instanceof ApiRequestError) {
        setError(`요청 실패(HTTP ${e.httpStatus}): ${JSON.stringify(e.body)}`);
      } else {
        setError(`알 수 없는 오류: ${(e as Error).message}`);
      }
    } finally {
      setLoading(false);
    }
  }, [onDraftCreated]);

  return (
    <div>
      <p className="helper" style={{ marginTop: 0 }}>
        고정된 샘플 입력으로 초안 1건을 즉시 생성합니다. 운영 흐름과 무관하며
        승인 루프 검증용입니다.
      </p>
      {error ? <div className="message error">{error}</div> : null}
      <button onClick={onClick} disabled={loading} type="button">
        {loading ? "처리 중..." : "샘플 초안 만들기 (개발용)"}
      </button>
    </div>
  );
}
