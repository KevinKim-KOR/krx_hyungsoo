"use client";

// POC5-03 — 받은 알림 카드 1장. 카드에는 시각 · 종류 · 전달 상태 · 핵심 item · 내 평가(또는
// '평가 없음')만 보이고, 원문 · 당시 판단 근거 · 선택 평가는 `자세히 보기` 를 눌렀을 때만
// 상세를 불러와 보인다(설계 개정 2 §5).
//
// partial 의 body_text 는 분할 전 전체 생성 본문이다 — 받은 전문으로 부르지 않는다.

import { useEffect, useState } from "react";
import {
  fetchLedgerAlertDetail,
  type LedgerAlertCard,
  type LedgerAlertDetail,
} from "@/lib/api";
import FeedbackForm from "./FeedbackForm";
import {
  PUSH_KIND_LABEL,
  actionLabel,
  dispositionLabel,
  fmtPrice,
  fmtStamp,
  helpfulnessLabel,
  keyItemSummary,
  subjectName,
} from "./format";

interface Props {
  alert: LedgerAlertCard;
  onSaved: () => void;
  // 목록을 다시 읽을 때마다 바뀐다 — 열려 있으면 상세도 다시 읽는다.
  refreshKey: number;
}

export default function AlertCard({ alert, onSaved, refreshKey }: Props) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<LedgerAlertDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 열려 있는 동안 평가 저장(feedback_count) · 원장 새로고침(refreshKey) 이 있으면 다시 읽는다.
  useEffect(() => {
    if (!open) return;
    let alive = true;
    fetchLedgerAlertDetail(alert.event_id)
      .then((d) => {
        if (alive) {
          setDetail(d);
          setError(null);
        }
      })
      .catch((e: Error) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [open, alert.event_id, alert.feedback_count, refreshKey]);

  const latest = alert.latest_feedback;
  return (
    <li className="ar-alert">
      <div className="ar-alert-top">
        <span className="ar-time">{alert.time_kst ?? "—"}</span>
        <span className="ar-kind">{PUSH_KIND_LABEL[alert.push_kind] ?? alert.push_kind}</span>
        {alert.delivery_status === "partial" ? (
          <span className="ar-badge-warn">일부 전달</span>
        ) : (
          <span className="ar-status">발송 완료</span>
        )}
        {alert.off_schedule ? <span className="ar-status">예정 외 실행</span> : null}
        <span className="ar-items">{keyItemSummary(alert.key_items)}</span>
        <span className="ar-spacer" />
        <span className="ar-mine">
          {latest ? `내 평가: ${helpfulnessLabel(latest.helpfulness)}` : "평가 없음"}
        </span>
        <button
          type="button"
          className="ar-ghost ar-btn-sm"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "닫기" : "자세히 보기"}
        </button>
      </div>
      {open ? (
        <div className="ar-detail">
          {error ? <div className="message error">상세를 불러오지 못했습니다 — {error}</div> : null}
          {!detail && !error ? <div className="ar-note">불러오는 중...</div> : null}
          {detail ? <DetailBody detail={detail} /> : null}
          {detail ? (
            <>
              <div className="ar-sec-h">내 평가 (선택)</div>
              {latest ? (
                <div className="ar-note">
                  최근 평가: {helpfulnessLabel(latest.helpfulness)}
                  {actionLabel(latest.action) ? ` · ${actionLabel(latest.action)}` : ""}
                  {latest.memo ? ` · ${latest.memo}` : ""} · {fmtStamp(latest.feedback_at)}
                  {alert.feedback_count > 1 ? ` (이전 평가 ${alert.feedback_count - 1}건 보존)` : ""}
                </div>
              ) : null}
              <FeedbackForm eventId={alert.event_id} onSaved={onSaved} />
            </>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

function DetailBody({ detail }: { detail: LedgerAlertDetail }) {
  return (
    <>
      {detail.body_withheld ? (
        <div className="ar-note">본문에 민감 문자열이 있어 저장하지 않았습니다</div>
      ) : (
        <>
          <div className="ar-sec-h">
            {detail.body_partial_delivery ? "생성된 원문 — 일부만 전달됨" : "원문"}
          </div>
          {detail.body_partial_delivery ? (
            <div className="ar-body-warn">실제 수신된 범위는 확인할 수 없습니다.</div>
          ) : null}
          <pre className="ar-body">{detail.body_text ?? "원문이 없습니다"}</pre>
        </>
      )}
      <div className="ar-sec-h">당시 판단 근거</div>
      <div className="ar-table-wrap">
        <table className="ar-table">
          <thead>
            <tr>
              <th>항목</th>
              <th>당시 상태</th>
              <th>직전 상태</th>
              <th>처리</th>
              <th>t0</th>
            </tr>
          </thead>
          <tbody>
            {detail.items.map((i) => (
              <tr key={i.item_seq}>
                <td>{subjectName(i)}</td>
                <td>{i.state_label ?? "—"}</td>
                <td>{i.prev_state_label ?? "—"}</td>
                <td>{dispositionLabel(i.disposition)}</td>
                <td className="ar-num">{fmtPrice(i.t0_price)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
