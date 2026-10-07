"use client";

// POC5-03 설계 개정 2 — 「진단·상태 > 받은 알림 기록」.
//
// OCI 가 보낸 알림과 그때의 판단 근거, 이후 가격 결과를 PC 사본에서 날짜별로 본다.
// 매일 평가하는 화면이 아니다 — 평가는 선택이고, 평가하지 않아도 이후 ML 이 이 기록을
// 그대로 쓴다(설계 §1 · §12). 미평가 수 · 완료율 · 독촉은 만들지 않는다.
//
// - 진입 · 날짜 · 종류 변경은 PC 사본 조회(GET)만 한다. OCI 원장 SSH 는 `원장 새로고침`
//   버튼을 눌렀을 때만이다(설계 §3).
// - 처음 열면 날짜를 보내지 않는다 — 백엔드가 사본에서 받은 알림이 있는 가장 최근 날짜를
//   고른다. 그 뒤 사용자가 고른 날짜는 새로고침 · 종류 변경 뒤에도 유지한다(설계 §5).

import { useEffect, useRef, useState } from "react";
import {
  ApiRequestError,
  fetchLedgerAlerts,
  syncDecisionLedger,
  type LedgerAlertList,
  type LedgerKind,
} from "@/lib/api";
import AlertCard from "./alert_records/AlertCard";
import SignalOutcomeLedger from "./alert_records/SignalOutcomeLedger";
import { KIND_FILTERS, fmtStamp, shiftDate } from "./alert_records/format";

type SyncUi =
  | { phase: "idle" }
  | { phase: "running" }
  | { phase: "done"; text: string };

export default function AlertRecordsView() {
  const [day, setDay] = useState<string | null>(null);
  const [kind, setKind] = useState<LedgerKind>("all");
  const [tick, setTick] = useState(0);
  const [data, setData] = useState<LedgerAlertList | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sync, setSync] = useState<SyncUi>({ phase: "idle" });
  // 기본 날짜를 받아 day 를 채울 때 같은 조회를 다시 하지 않게 한다.
  const loadedKey = useRef<string | null>(null);

  useEffect(() => {
    if (loadedKey.current === `${day}|${kind}|${tick}`) return;
    let alive = true;
    fetchLedgerAlerts(day, kind)
      .then((res) => {
        if (!alive) return;
        loadedKey.current = `${res.date}|${kind}|${tick}`;
        setData(res);
        setLoadError(null);
        if (day === null) setDay(res.date);
      })
      .catch((e: Error) => {
        if (alive) setLoadError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [day, kind, tick]);

  const reload = () => setTick((t) => t + 1);

  const onSync = async () => {
    setSync({ phase: "running" });
    try {
      const r = await syncDecisionLedger();
      setSync({ phase: "done", text: r.ok ? "완료" : "실패" });
    } catch (e) {
      const busy = e instanceof ApiRequestError && e.httpStatus === 409;
      setSync({ phase: "done", text: busy ? "이미 진행 중" : "실패" });
    }
    reload();
  };

  const status = data?.sync;
  const failedLater =
    !!status?.last_failure_at &&
    (!status.last_success_at || status.last_failure_at > status.last_success_at);

  return (
    <section aria-labelledby="alert-records-h">
      <h1 id="alert-records-h">받은 알림 기록</h1>
      <p className="subtitle">
        OCI 가 보낸 알림과 그때의 판단 근거, 이후 가격 결과를 모아 둔 기록입니다. 매일 평가할
        필요는 없고, 나중에 ML 로 사후 검토할 때 쓰입니다.
      </p>

      <div className="card">
        <div className="ar-toolbar">
          <button
            type="button"
            className="ar-ghost"
            disabled={sync.phase === "running"}
            onClick={onSync}
          >
            {sync.phase === "running" ? "불러오는 중..." : "원장 새로고침"}
          </button>
          <span className="ar-note" data-testid="sync-line">
            {!status
              ? ""
              : status.has_copy
                ? `마지막 성공 동기화 ${fmtStamp(status.last_success_at)}`
                : "원장 새로고침이 필요합니다"}
            {sync.phase === "done" ? ` · ${sync.text}` : ""}
          </span>
        </div>
        {status?.has_copy && failedLater ? (
          <div className="ar-note">
            기존 기록을 표시 중입니다 · 실패 {fmtStamp(status.last_failure_at)}
          </div>
        ) : null}
        <div className="ar-toolbar ar-gap-top">
          <button
            type="button"
            className="ar-ghost ar-btn-sm"
            disabled={!day}
            onClick={() => day && setDay(shiftDate(day, -1))}
          >
            ◀ 이전 날
          </button>
          <input
            type="date"
            aria-label="날짜"
            className="ar-date"
            value={day ?? ""}
            onChange={(e) => e.target.value && setDay(e.target.value)}
          />
          <button
            type="button"
            className="ar-ghost ar-btn-sm"
            disabled={!day}
            onClick={() => day && setDay(shiftDate(day, 1))}
          >
            다음 날 ▶
          </button>
          <span className="ar-spacer" />
          <div className="ar-seg" role="group" aria-label="알림 종류">
            {KIND_FILTERS.map((f) => (
              <button
                key={f.kind}
                type="button"
                aria-pressed={kind === f.kind}
                onClick={() => setKind(f.kind)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
        <p className="helper">발송 완료 · 일부 전달 알림만 보입니다.</p>
      </div>

      <div className="card">
        {loadError ? (
          <div className="message error">기록을 불러오지 못했습니다 — {loadError}</div>
        ) : !data ? (
          <div className="message info">불러오는 중...</div>
        ) : data.alerts.length === 0 ? (
          <div className="message info">
            {data.sync.has_copy ? "이 날짜에 받은 알림이 없습니다" : "원장 새로고침이 필요합니다"}
          </div>
        ) : (
          <ul className="ar-alerts">
            {data.alerts.map((a) => (
              <AlertCard key={a.event_id} alert={a} onSaved={reload} refreshKey={tick} />
            ))}
          </ul>
        )}
      </div>

      {data && data.alerts.length > 0 ? (
        <div className="card">
          <SignalOutcomeLedger alerts={data.alerts} refreshKey={tick} />
        </div>
      ) : null}
    </section>
  );
}
