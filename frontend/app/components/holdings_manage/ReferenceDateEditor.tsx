"use client";

// POC5-07 설계 §2 · §9-2-2 — History 기간 머리의 가격 비교 기준일 줄(기준잔고 · 잔고 등록 기간만).
// '실제 매수일: 미상'과 '가격 비교 기준일: 날짜/없음'을 함께 보이고 [수정/해제] → 같은 줄 안에서
// 날짜 칸 · [저장] · [해제] · [취소](창 위에 창을 열지 않는다). 저장 = PUT action "reference_date"
// (대상 1개 · base_revision · request_id — 같은 내용 재시도에는 같은 ID). 기준일은 종가 비교의 출발점이며
// 매수일 · 매수 거래가 아니다. 저장 뒤 부모가 History · 보유를 다시 읽는다.

import { useId, useRef, useState } from "react";
import { DEFAULT_REFERENCE_DATE, putReferenceDate } from "@/lib/api";
import { apiErrorText, newSaveId, todayKst } from "./format";

interface Props {
  positionId: string;
  cycleId: string;
  value: string | null;
  revision: number;
  onSaved: () => void;
}

export default function ReferenceDateEditor({ positionId, cycleId, value, revision, onSaved }: Props) {
  const uid = useId();
  const [editing, setEditing] = useState(false);
  const [day, setDay] = useState(value ?? DEFAULT_REFERENCE_DATE);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const attempt = useRef<{ key: string; id: string } | null>(null);
  const today = todayKst();

  const save = async (next: string | null) => {
    if (saving) return;
    const key = next ?? "(해제)";
    if (attempt.current?.key !== key) attempt.current = { key, id: newSaveId() };
    setSaving(true);
    setError(null);
    try {
      await putReferenceDate({
        action: "reference_date",
        request_id: attempt.current.id,
        base_revision: revision,
        reference_date: next,
        targets: [{ position_id: positionId, cycle_id: cycleId }],
      });
      attempt.current = null;
      setEditing(false);
      onSaved();
    } catch (e) {
      setError(apiErrorText(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="hmx-ref-row hmx-small">
      <span>실제 매수일: 미상</span>
      <span>
        가격 비교 기준일: <b>{value ?? "없음"}</b>
      </span>
      {!editing ? (
        <button
          type="button"
          className="hmx-btn-sm hmx-ghost"
          onClick={() => {
            setDay(value ?? DEFAULT_REFERENCE_DATE);
            setError(null);
            setEditing(true);
          }}
        >
          수정/해제
        </button>
      ) : (
        <span className="hmx-row-actions">
          <label htmlFor={`${uid}-ref`} className="muted">
            가격 비교 기준일
          </label>
          <input
            id={`${uid}-ref`}
            type="date"
            value={day}
            max={today}
            onChange={(e) => setDay(e.target.value)}
          />
          <button
            type="button"
            className="hmx-btn-sm"
            disabled={saving || !day || day > today}
            onClick={() => void save(day)}
          >
            {saving ? "저장 중…" : "저장"}
          </button>
          {value ? (
            <button type="button" className="hmx-btn-sm hmx-ghost" disabled={saving} onClick={() => void save(null)}>
              해제
            </button>
          ) : null}
          <button type="button" className="hmx-btn-sm hmx-ghost" disabled={saving} onClick={() => setEditing(false)}>
            취소
          </button>
        </span>
      )}
      {error ? (
        <div className="hmx-error" role="alert">
          {error}
        </div>
      ) : null}
    </div>
  );
}
