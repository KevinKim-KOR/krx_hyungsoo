"use client";

// POC5-05 개정 2 §2 · §6 · PLAN §2-8 — History 창(창 하나 · 종목 · 계좌(position)별 내용).
// 열 때 GET /holdings/trade-history?position_id= 1회만 부른다(시세 · 시장 흐름 · ML 조회 0 — 시장 흐름은
// 기간의 [시장 흐름 보기]를 누를 때만 부른다). 보유 중 = 현재 기간(미실현은 부모가 넘긴
// /holdings/enriched 값) + 지난 기간 · 과거 보유 = 지난 기간 + [재매수].
// 매매 줄 [정정] = 부모가 매매 창(정정 모드)을 연다 · [취소] = 화면 안 확인 → 취소 기록 저장 →
// 다시 조회 + 부모가 보유를 다시 읽는다. 오류는 백엔드 문구 그대로 보인다.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchTradeHistory,
  putTradeCommand,
  type HoldingCycleView,
  type PositionHistory,
  type TradeEventView,
} from "@/lib/api";
import Dialog from "./Dialog";
import HistoryCycle, { type PriceInfo } from "./HistoryCycle";
import type { RowActions } from "./HistoryEventRows";
import { apiErrorText, newSaveId } from "./format";
import { recordBrief, savedAt } from "./historyText";

interface Props {
  positionId: string;
  priceInfo?: PriceInfo | null; // 보유 중일 때 「보유 현황」과 같은 /holdings/enriched 값
  onClose: () => void;
  onRebuy: (position: PositionHistory) => void;
  onCorrect: (position: PositionHistory, cycle: HoldingCycleView, event: TradeEventView) => void;
  onChanged: () => void; // 취소 저장 뒤 부모가 보유 · 적용 상태를 다시 읽는다
  onReview?: (cycleId: string) => void; // POC5-06 — 부모가 이 창 자리에 재진입 검토 창을 연다
}

const SUBTITLE = "체결단가 기준 · 수수료 · 세금 · 배당 미반영 · 이동평균 평단";

export default function HistoryDialog({
  positionId,
  priceInfo,
  onClose,
  onRebuy,
  onCorrect,
  onChanged,
  onReview,
}: Props) {
  const [position, setPosition] = useState<PositionHistory | null>(null);
  const [revision, setRevision] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // 취소 확인: 대상 기록 + 저장 ID(같은 확인 안의 재시도에는 같은 ID 를 다시 쓴다).
  const [confirm, setConfirm] = useState<{ recordId: string; saveId: string } | null>(null);
  const [voiding, setVoiding] = useState(false);
  const [voidError, setVoidError] = useState<string | null>(null);
  const alive = useRef(true);
  const reqNo = useRef(0);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const load = useCallback(async () => {
    const no = ++reqNo.current;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchTradeHistory(positionId);
      if (!alive.current || no !== reqNo.current) return;
      const pos = res.positions.find((p) => p.position_id === positionId) ?? null;
      setRevision(res.revision);
      setPosition(pos);
      if (!pos) setError("이 보유의 기록을 찾을 수 없습니다 — 창을 닫고 새로고침하세요.");
    } catch (e) {
      if (alive.current && no === reqNo.current) setError(apiErrorText(e));
    } finally {
      if (alive.current && no === reqNo.current) setLoading(false);
    }
  }, [positionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const confirmVoid = async () => {
    if (!confirm || revision === null || voiding) return;
    setVoiding(true);
    setVoidError(null);
    try {
      await putTradeCommand({
        record_id: confirm.saveId,
        base_revision: revision,
        action: "void",
        supersedes_id: confirm.recordId,
      });
      if (!alive.current) return;
      setConfirm(null);
      onChanged();
      await load();
    } catch (e) {
      if (alive.current) setVoidError(apiErrorText(e));
    } finally {
      if (alive.current) setVoiding(false);
    }
  };

  const baseActions: Omit<RowActions, "onCorrect"> = {
    confirmId: confirm?.recordId ?? null,
    voiding,
    voidError,
    onAskVoid: (ev) => {
      setConfirm({ recordId: ev.record_id, saveId: newSaveId() });
      setVoidError(null);
    },
    onConfirmVoid: () => void confirmVoid(),
    onCancelVoid: () => {
      setConfirm(null);
      setVoidError(null);
    },
  };

  const title = position
    ? `History — ${position.name || position.ticker} · ${position.account_group}` +
      (position.is_open ? "" : " (과거 보유)")
    : "History";
  // 최근 기간이 위(보유 중 기간은 늘 마지막 기간이므로 맨 위).
  const cycles = position ? [...position.cycles].reverse() : [];
  const closedCount = cycles.filter((c) => c.status === "CLOSED").length;
  // 줄 단위 취소 기록(기간이 모두 취소돼 빠져도 남는다) · 구 응답이면 기간별 목록.
  const voided = position?.voided ?? cycles.flatMap((c) => c.voided);

  return (
    <Dialog title={title} subtitle={SUBTITLE} onClose={onClose} wide>
      {loading && !position ? <p className="muted hmx-small">History 를 불러오는 중…</p> : null}
      {error ? (
        <div className="hmx-error" role="alert">
          {error}
        </div>
      ) : null}
      {position ? (
        <>
          {!position.is_open ? (
            <div className="hmx-info" style={{ marginTop: 0 }}>
              현재 보유 없음 · 지난 보유 기간 {closedCount}건
              <button
                type="button"
                className="hmx-btn-sm"
                style={{ marginLeft: 8 }}
                onClick={() => onRebuy(position)}
              >
                재매수
              </button>
            </div>
          ) : null}
          {cycles.map((cy) => (
            <HistoryCycle
              key={`${cy.cycle_id}:${revision ?? 0}`}
              positionId={position.position_id}
              cycle={cy}
              priceInfo={cy.status === "OPEN" ? (priceInfo ?? null) : null}
              actions={{ ...baseActions, onCorrect: (ev) => onCorrect(position, cy, ev) }}
              onReview={onReview ? () => onReview(cy.cycle_id) : undefined}
            />
          ))}
          {position.is_open && closedCount === 0 ? (
            <p className="muted hmx-small" style={{ margin: "12px 0 0" }}>
              지난 보유 기간 없음.
            </p>
          ) : null}
          {voided.length > 0 ? (
            <details style={{ marginTop: 12 }}>
              <summary className="hmx-small" style={{ cursor: "pointer" }}>
                취소한 기록 {voided.length}건
              </summary>
              <ul className="hmx-small muted" style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                {voided.map((v) => (
                  <li key={v.record_id}>
                    {recordBrief(v)} · {savedAt(v.voided_at)} 취소
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </>
      ) : null}
    </Dialog>
  );
}
