"use client";

// AI Sessions 화면 — 탭 컨테이너 (POC2 — 2026-05-21).
//
// 책임:
// - [새 기록 저장] / [기록 조회] 탭 분리 렌더링.
// - sessionStorage 의 draft 를 마운트 시점에 1회 읽어 CreateTab 에 전달.
// - draft 가 있으면 default 탭 = create (Market Discovery 에서 넘어온 흐름).
// - draft 가 없으면 default 탭 = list (메뉴 직접 진입).
// - CreateTab 저장 성공 시 reloadTrigger 증가 → ListTab 이 fetch 재호출.
// - POC6-32 V2(PLAN §4-4) — 「주간 ETF 점검」 ⑤ [기록 열기]가 넘긴 기록 id(lib/detailNav · 한 번 읽으면 비움)가 있으면
//   [기록 조회] 탭에서 그 기록 상세를 바로 연다(남은 초안보다 우선 · 초안은 지우지 않고 [새 기록 저장] 탭에 그대로).

import { useEffect, useMemo, useState } from "react";
import AISessionsCreateTab from "./AISessionsCreateTab";
import AISessionsListTab from "./AISessionsListTab";
import {
  loadAISessionsDraft,
  type AISessionsDraft,
} from "@/lib/aiSessionsDraft";
import { takeOpenRecord } from "@/lib/detailNav";

type TabKey = "create" | "list";

export default function AISessionsView() {
  // 넘겨받은 기록 id — useState 초기값에서 한 번만 읽는다(effect 에서 읽으면 Strict Mode 두 번째 실행이 빈 값을 읽음 ·
  // compareSelection 선례). openId 는 바꾸지 않는다(초안 탭보다 먼저인지 정함) · listOpenId 는 [기록 조회]가 처음 그려질 때
  // 그 기록을 여는 데만 쓰고, 탭을 누르면 비운다(탭을 오가도 같은 기록을 다시 열지 않음).
  const [openId] = useState<string | null>(() => takeOpenRecord());
  const [listOpenId, setListOpenId] = useState<string | null>(openId);
  // 마운트 시점에 단 1회 draft 읽기 — 그 이후는 명시적 reload (저장 후 clear) 만.
  const [draft, setDraft] = useState<AISessionsDraft | null>(null);
  const [draftLoaded, setDraftLoaded] = useState<boolean>(false);
  const [active, setActive] = useState<TabKey>("list");
  const [reloadTrigger, setReloadTrigger] = useState<number>(0);

  useEffect(() => {
    const d = loadAISessionsDraft();
    setDraft(d);
    setDraftLoaded(true);
    if (d && !openId) {
      setActive("create");
    }
  }, [openId]);

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
        「후보리스트」 · 「주간 ETF 점검」 · 판단 근거 미리보기에서 넘어온 스냅샷 기반으로만 가능합니다.
      </p>
      <div className="role-banner">
        <strong>[보조 화면]</strong> 「후보리스트」 · 판단 근거 미리보기에서 만든 AI 투자세션 문구를 외부 AI에
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
          onClick={() => {
            setListOpenId(null);
            setActive("create");
          }}
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
          onClick={() => {
            setListOpenId(null);
            setActive("list");
          }}
        >
          기록 조회
        </button>
      </div>

      {active === "create" ? (
        <AISessionsCreateTab draft={draft} onSaved={handleSaved} />
      ) : (
        <AISessionsListTab reloadTrigger={reloadTrigger} openId={listOpenId} />
      )}
    </section>
  );
}
