"use client";

// POC5-07 설계 §1 · §2 — [가격 비교 기준일 설정] 일괄 창(보유 표 버튼).
// 대상 = 보유 중 · 기준잔고 / 잔고 등록으로 시작 · 기준일 없는 기간(이미 설정된 기간은 덮어쓰지 않는다 —
// 서버는 base_revision 으로 그 사이 변경을 거절). 날짜 한 칸(초기값 2026-01-02 · KST 오늘 이하) ·
// 대상 목록과 건수 · [설정] = PUT action "reference_date" 한 번(모두 저장되거나 아무것도 저장되지 않음).
// 실제 매수일은 미상으로 남고 수량 · 평단 · 손익 · OCI 보유는 바뀌지 않는다. 대상이 없으면 안내만.

import { useId, useMemo, useRef, useState } from "react";
import { DEFAULT_REFERENCE_DATE, putReferenceDate, type PositionHistory } from "@/lib/api";
import Dialog from "./Dialog";
import { apiErrorText, newSaveId, todayKst } from "./format";

interface Props {
  positions: PositionHistory[];
  revision: number;
  onClose: () => void;
  onSaved: () => void;
}

interface Target {
  position_id: string;
  cycle_id: string;
  ticker: string;
  name: string | null;
  account_group: string;
}

export function referenceTargets(positions: PositionHistory[]): Target[] {
  const out: Target[] = [];
  for (const p of positions) {
    if (!p.is_open) continue;
    const cy = p.cycles.find((c) => c.status === "OPEN");
    if (!cy || cy.opened_by === "BUY" || cy.reference_date) continue;
    out.push({
      position_id: p.position_id,
      cycle_id: cy.cycle_id,
      ticker: p.ticker,
      name: p.name,
      account_group: p.account_group,
    });
  }
  return out;
}

export default function ReferenceDateDialog({ positions, revision, onClose, onSaved }: Props) {
  const uid = useId();
  const targets = useMemo(() => referenceTargets(positions), [positions]);
  const [day, setDay] = useState(DEFAULT_REFERENCE_DATE);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const attempt = useRef<{ key: string; id: string } | null>(null);
  const today = todayKst();
  const canSave = targets.length > 0 && !!day && day <= today && !saving;

  const submit = async () => {
    if (!canSave) return;
    if (attempt.current?.key !== day) attempt.current = { key: day, id: newSaveId() };
    setSaving(true);
    setError(null);
    try {
      await putReferenceDate({
        action: "reference_date",
        request_id: attempt.current.id,
        base_revision: revision,
        reference_date: day,
        targets: targets.map((t) => ({ position_id: t.position_id, cycle_id: t.cycle_id })),
      });
      onSaved();
    } catch (e) {
      setError(apiErrorText(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      title="가격 비교 기준일 설정"
      subtitle="실제 매수일은 미상으로 남습니다 · 수량 · 평단 · 손익 · OCI 보유는 바뀌지 않습니다"
      onClose={onClose}
      wide
      footer={
        <>
          <button type="button" className="hmx-ghost" onClick={onClose} disabled={saving}>
            취소
          </button>
          <button type="button" onClick={() => void submit()} disabled={!canSave}>
            {saving ? "설정 중…" : "설정"}
          </button>
        </>
      }
    >
      <p className="helper" style={{ marginTop: 0 }}>
        가격 비교 기준일은 History 의 [시장 흐름 보기]에서 &lsquo;가격 비교 기준일 이후 종가 변화&rsquo;를 보는
        출발점입니다. 그날 보유 · 매수했다는 뜻이 아니며, 이미 기준일이 있는 기간은 바꾸지 않습니다(기간별
        수정 · 해제는 History 에서).
      </p>
      {targets.length === 0 ? (
        <div className="hmx-info" style={{ marginTop: 0 }}>
          설정할 보유가 없습니다 — 기준잔고 · 잔고 등록으로 시작했고 기준일이 없는 현재 보유만 대상입니다.
        </div>
      ) : (
        <>
          <form className="hmx-form" onSubmit={(e) => e.preventDefault()}>
            <div className="hmx-field">
              <label htmlFor={`${uid}-day`}>가격 비교 기준일</label>
              <input id={`${uid}-day`} type="date" value={day} max={today} onChange={(e) => setDay(e.target.value)} />
            </div>
            <div className="hmx-field">
              <span className="hmx-lbl">대상</span>
              <span className="hmx-out hmx-right">{targets.length}건</span>
            </div>
          </form>
          <div className="hmx-tbl-wrap" style={{ marginTop: 12 }}>
            <table className="hmx-tbl">
              <thead>
                <tr>
                  <th>종목</th>
                  <th>계좌</th>
                  <th>실제 매수일</th>
                </tr>
              </thead>
              <tbody>
                {targets.map((t) => (
                  <tr key={t.cycle_id}>
                    <td>
                      {t.name || t.ticker} <span className="muted hmx-small">{t.ticker}</span>
                    </td>
                    <td>{t.account_group}</td>
                    <td className="muted">미상</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {error ? (
        <div className="hmx-error" role="alert">
          {error}
        </div>
      ) : null}
    </Dialog>
  );
}
