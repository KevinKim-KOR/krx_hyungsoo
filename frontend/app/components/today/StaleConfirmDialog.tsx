"use client";

// POC6-27 — [요약 다시 읽기] · [AI용 시장 정보 복사] 확인 창(설계 §2 · PLAN 쟁점 4 · 판정 Q3 · §4).
//
// 늦은 자료 · 기준 확인이 필요한 자료 · 다시 읽기에 실패한 자료를 한 줄씩 보이고 고르게 한다.
// [이 자료로 계속] = 창에 보인 바로 그 결과를 반영 · 복사(다시 조회하지 않음 · 호출부) /
// [취소] = 받아 둔 결과를 버리고 이전 화면 · 공유 캐시 · 성공 시각을 그대로(호출부).
// 창이 열려 있는 동안 두 버튼은 다시 실행되지 않는다(호출부가 막음).
import { useEffect, useRef } from "react";
import { freshnessLine, type FreshRow } from "@/lib/todayFreshness";

export interface FailedSource {
  label: string;
  // 남겨 둘 이전 값을 받은 시각(없으면 이전 값 없음) · 실패 사유
  keptAt: string | null;
  reason: string;
}

export const STALE_CONFIRM_TEXT = "최신 상태를 확인해야 할 자료가 있습니다. 현재 저장된 자료로 계속할까요?";

export default function StaleConfirmDialog({
  purpose,
  rows,
  failed,
  onContinue,
  onCancel,
}: {
  purpose: "reload" | "copy";
  rows: FreshRow[];
  failed: FailedSource[];
  onContinue: () => void;
  onCancel: () => void;
}) {
  const firstRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    firstRef.current?.focus();
  }, []);
  return (
    <div className="tc-dialog-backdrop">
      <div
        className="tc-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={purpose === "reload" ? "요약 다시 읽기 확인" : "AI용 시장 정보 복사 확인"}
        data-testid="tc-stale-dialog"
        onKeyDown={(e) => {
          if (e.key === "Escape") onCancel();
        }}
      >
        <p className="tc-dialog-title">{STALE_CONFIRM_TEXT}</p>
        <ul className="tc-fresh-list">
          {rows.map((r) => (
            <li key={r.key} className="tc-fresh-row" data-fresh={r.key}>
              <span className="tc-fresh-label">{r.label}</span>
              <span className="tc-fresh-line">{freshnessLine(r)}</span>
            </li>
          ))}
          {failed.map((f) => (
            <li key={`f-${f.label}`} className="tc-fresh-row" data-failed={f.label}>
              <span className="tc-fresh-label">{f.label}</span>
              <span className="tc-fresh-line">
                불러오지 못함 · {f.keptAt ? `이전 값(${f.keptAt}에 읽음) 유지` : "이전 값 없음"} · {f.reason}
              </span>
            </li>
          ))}
        </ul>
        <p className="tc-muted tc-small">
          {purpose === "reload"
            ? "계속하면 방금 읽은 값으로 요약을 바꾸고 각 줄에 기준일과 상태를 남깁니다. 취소하면 지금 화면을 그대로 둡니다."
            : "계속하면 복사하는 글의 [자료 상태] 줄에 기준일과 상태를 남깁니다."}
        </p>
        <div className="tc-btn-row">
          <button ref={firstRef} type="button" className="btn-md" onClick={onContinue}>
            이 자료로 계속
          </button>
          <button type="button" className="btn-md tc-fold-btn" onClick={onCancel}>
            취소
          </button>
        </div>
      </div>
    </div>
  );
}
