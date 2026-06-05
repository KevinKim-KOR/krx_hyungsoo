"use client";

// AI Sessions 화면 — 탭 컨테이너 (POC2 — 2026-05-21).
//
// 책임:
// - [새 기록 저장] / [기록 조회] 탭 분리 렌더링.
// - sessionStorage 의 draft 를 마운트 시점에 1회 읽어 CreateTab 에 전달.
// - draft 가 있으면 default 탭 = create (Market Discovery 에서 넘어온 흐름).
// - draft 가 없으면 default 탭 = list (메뉴 직접 진입).
// - CreateTab 저장 성공 시 reloadTrigger 증가 → ListTab 이 fetch 재호출.

import { useEffect, useMemo, useState } from "react";
import AISessionsCreateTab from "./AISessionsCreateTab";
import AISessionsListTab from "./AISessionsListTab";
import {
  loadAISessionsDraft,
  type AISessionsDraft,
} from "@/lib/aiSessionsDraft";

type TabKey = "create" | "list";

export default function AISessionsView() {
  // 마운트 시점에 단 1회 draft 읽기 — 그 이후는 명시적 reload (저장 후 clear) 만.
  const [draft, setDraft] = useState<AISessionsDraft | null>(null);
  const [draftLoaded, setDraftLoaded] = useState<boolean>(false);
  const [active, setActive] = useState<TabKey>("list");
  const [reloadTrigger, setReloadTrigger] = useState<number>(0);

  useEffect(() => {
    const d = loadAISessionsDraft();
    setDraft(d);
    setDraftLoaded(true);
    if (d) {
      setActive("create");
    }
  }, []);

  const handleSaved = useMemo(
    () => () => {
      // draft 는 CreateTab 안에서 storage 까지 clear 됨.
      setDraft(null);
      setReloadTrigger((n) => n + 1);
    },
    [],
  );

  if (!draftLoaded) {
    return (
      <section aria-labelledby="ai-sessions-h">
        <h1 id="ai-sessions-h">AI Sessions</h1>
        <div className="card">
          <div className="message info">불러오는 중...</div>
        </div>
      </section>
    );
  }

  return (
    <section aria-labelledby="ai-sessions-h">
      <h1 id="ai-sessions-h">AI Sessions</h1>
      <p className="subtitle">
        외부 AI(GPT / Gemini / Claude) 답변과 사용자 판단을 기록합니다. 저장은
        Market Discovery 에서 넘어온 후보 스냅샷 기반으로만 가능합니다.
      </p>
      <div className="role-banner">
        <strong>[보조 화면]</strong> Market Discovery에서 생성한 AI 투자세션 문구를 외부 AI에
        붙여넣고 받은 답변 및 사용자 판단을 기록하는 화면입니다. 판단 초안 생성(Holdings 화면)
        전후 참고 자료로 활용합니다.
      </div>

      <div className="decision-tab-row">
        <button
          type="button"
          className={
            active === "create"
              ? "decision-tab-btn decision-tab-active"
              : "decision-tab-btn"
          }
          onClick={() => setActive("create")}
        >
          새 기록 저장
        </button>
        <button
          type="button"
          className={
            active === "list"
              ? "decision-tab-btn decision-tab-active"
              : "decision-tab-btn"
          }
          onClick={() => setActive("list")}
        >
          기록 조회
        </button>
      </div>

      {active === "create" ? (
        <AISessionsCreateTab draft={draft} onSaved={handleSaved} />
      ) : (
        <AISessionsListTab reloadTrigger={reloadTrigger} />
      )}
    </section>
  );
}
