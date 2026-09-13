"use client";

// POC3-OPS-02B-2-KS10-TRIGGER-FILE-SPLIT (2026-09-13)
// `TodayInvestmentCheckView.tsx` 가 907줄로 KS-10 프론트 임계(>900)를 넘어
// 책임별로 분리했다. **JSX·문구·className·핸들러·호출 조건을 고치지 않았다** —
// 바뀐 것은 파일 배치와 import/export 줄뿐이다.

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

// ── §4.3 정비 큐 (자료 업데이트 필요) ────────────────────────────────────────
export default function MaintenanceQueueSection({
  items,
  loading,
  refreshing,
  onLightRefresh,
  onNavigate,
}: {
  items: MaintenanceItem[];
  loading: boolean;
  refreshing: "idle" | "running" | "done" | "failed";
  onLightRefresh: () => void;
  onNavigate: (key: MenuKey) => void;
}) {
  const lightItems = items.filter((it) => it.kind === "light");
  const heavyItems = items.filter((it) => it.kind === "heavy");
  return (
    <section className="tc-card" aria-label="자료 최신화 필요">
      {/* 제목 + 건수. "최신" 배지는 아래 보유 현재가 행 문구 옆으로 이동(사용자 지시). */}
      <div className="tc-maint-title-row">
        <h2 className="tc-h2" style={{ marginBottom: 0 }}>
          자료 최신화 필요{" "}
          {!loading && (
            <span className="tc-count">
              {items.length > 0 ? `${items.length}건` : "0건"}
            </span>
          )}
        </h2>
      </div>

      {loading ? (
        <p className="tc-maint-asof tc-muted">자료 상태 확인 중...</p>
      ) : (
        // 모든 항목을 동일한 행 형태로 (그룹 라벨·상태줄 없음 · 사용자 지시 2026-07-30).
        // 각 행: [최신 배지?] 문구 ⓘ근거 ... [버튼]. light/heavy 형태 동일.
        <ul className="tc-maint-list">
          {/* 보유 현재가(light) 행 — 결측이 있으면 그 항목, 없으면 "최신" 배지 행. */}
          {lightItems.length > 0 ? (
            lightItems.map((it, i) => (
              <li key={`l${i}`} className="tc-maint-item">
                <span className="tc-maint-text">
                  {it.text}
                  <MaintInfo reason={it.reason} />
                  {refreshing === "done"
                    ? " · 완료"
                    : refreshing === "failed"
                      ? " · 실패"
                      : ""}
                </span>
                <button
                  type="button"
                  className="tc-btn tc-btn-link"
                  onClick={onLightRefresh}
                  disabled={refreshing === "running"}
                >
                  {refreshing === "running" ? "불러오는 중..." : "업데이트"}
                </button>
              </li>
            ))
          ) : (
            <li className="tc-maint-item">
              <span className="tc-maint-text">
                <span className="tc-fresh-badge">최신</span> 보유 종목 현재가는 최신
                상태입니다
                <MaintInfo reason="보유 종목의 저장된 현재가(시세)가 모두 있습니다. '업데이트' 로 저장된 시세를 다시 불러올 수 있습니다." />
                {refreshing === "done"
                  ? " · 완료"
                  : refreshing === "failed"
                    ? " · 실패"
                    : ""}
              </span>
              <button
                type="button"
                className="tc-btn tc-btn-link"
                onClick={onLightRefresh}
                disabled={refreshing === "running"}
              >
                {refreshing === "running" ? "불러오는 중..." : "업데이트"}
              </button>
            </li>
          )}
          {/* 상세 화면 갱신 대상(heavy) — 같은 행 형태 + ⓘ근거 + 이동 버튼. */}
          {heavyItems.map((it, i) => (
            <li key={`h${i}`} className="tc-maint-item">
              <span className="tc-maint-text">
                {it.text}
                <MaintInfo reason={it.reason} />
              </span>
              <button
                type="button"
                className="tc-btn tc-btn-link"
                onClick={() => onNavigate(it.target)}
              >
                {it.actionLabel}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
