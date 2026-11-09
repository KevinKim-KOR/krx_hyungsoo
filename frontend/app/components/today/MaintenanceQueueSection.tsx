"use client";

// POC3-OPS-02B-2-KS10-TRIGGER-FILE-SPLIT (2026-09-13) 에서 TodayInvestmentCheckView 에서 분리한 정비 큐.
// POC6-27 — 「자료 확인」 줄의 펼침 목록(PLAN 판정 Q2 (a) 보완): 구성종목 · NAV · VIX · 보유 비교 자료 등
// 기존 정비 항목을 기존 문구 · ⓘ 사유 · 이동 버튼 그대로 보인다. 늦은 자료 · 바로 조치할 일(보유 현재가 ·
// 다시 읽기 · 시장 자료 갱신)은 맨 위 「자료 최신화 필요」와 상단 버튼으로 옮겼다. 코스피 항목은 위 카드의
// 코스피 줄과 같아 여기서는 뺀다(같은 항목 두 번 없음).

import type { MenuKey } from "../LeftSidebar";
import type { MaintenanceItem } from "./maintenanceQueue";

function MaintInfo({ reason }: { reason?: string }) {
  if (!reason) return null;
  return (
    <span
      className="tc-info"
      tabIndex={0}
      role="note"
      aria-label={reason}
      title={reason}
    >
      {" "}
      ⓘ
    </span>
  );
}

export function maintenanceListItems(items: MaintenanceItem[]): MaintenanceItem[] {
  return items.filter((it) => it.kind === "heavy" && it.source !== "kospi");
}

export default function MaintenanceQueueSection({
  items,
  loading,
  onNavigate,
}: {
  items: MaintenanceItem[];
  loading: boolean;
  onNavigate: (key: MenuKey) => void;
}) {
  const list = maintenanceListItems(items);
  if (loading) return <p className="tc-muted tc-small">자료 상태 확인 중...</p>;
  if (list.length === 0) return <p className="tc-muted tc-small">이 목록에 올릴 정비 항목이 없습니다.</p>;
  return (
    <ul className="tc-maint-list" aria-label="자료 업데이트 목록">
      {list.map((it, i) => (
        <li key={`h${i}`} className="tc-maint-item">
          <span className="tc-maint-text">
            {it.text}
            <MaintInfo reason={it.reason} />
          </span>
          <button type="button" className="tc-btn tc-btn-link" onClick={() => onNavigate(it.target)}>
            {it.actionLabel}
          </button>
        </li>
      ))}
    </ul>
  );
}
