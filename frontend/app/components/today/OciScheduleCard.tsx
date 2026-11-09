"use client";

// POC6-27 — 상단 「OCI 운영 스케줄 확인」(설계 §5 · 사용자 결정 ② · PLAN 쟁점 3 · 판정 §2 · Q6 · §4).
//
// - 예약: 백엔드가 기동 때 1회 읽은 스냅샷(GET /oci/startup-status · OCI 다시 조회 없음)의 schedule 3줄.
//   확인 실패(unknown)는 누락으로 세지 않는다. 옛 응답(schedule 없음)이면 기존 요약 문장 + '확인 불가'.
// - 발송: PC 원장 사본의 종류별 마지막 실행(GET /decision-ledger/latest-by-kind · SSH 0).
//   '오늘 기록'은 사본 마지막 동기화가 오늘(KST)이고 그 종류의 실행 발생일도 오늘일 때만(판정 Q6).
//   조회 실패와 사본 없음은 다른 상태. 모르면 늘 「받은 알림 기록」 이동(사본 새로고침은 그 화면에서 사용자가).
// - 기본 접힘(화면 안 상태만 · 다시 들어오면 접힘). 접힌 줄: '예약 n/3 확인' · 발송 한마디.
// - 사용자 결정 ⑤(2026-11-09): 옆 「자료 최신화 필요」와 함께 펼치고 접는다 — 부모가 open · onToggle 을 주면 그 상태를 쓴다.
import { useEffect, useState } from "react";
import { fetchOciStartupStatus, type OciStartupStatus } from "@/lib/api";
import { fetchLedgerLatestByKind, type LedgerLatestByKind } from "@/lib/api/decisionLedger";
import { kstDate } from "@/lib/todayFreshness";
import { isRealDate, md, parseIsoInstant } from "@/lib/todayMarketLines";
import type { MenuKey } from "../LeftSidebar";

type Load<T> = { phase: "loading" } | { phase: "ok"; data: T } | { phase: "error" };

const STATE_WORD: Record<string, string> = {
  registered: "예약 확인",
  missing: "예약 누락",
  unknown: "확인 불가",
};

const DELIVERY_WORD: Record<string, string> = {
  sent: "보냄",
  partial: "일부 보냄",
  skipped: "건너뜀",
  failed: "실패",
};

// ISO 시각 → 'M/D HH:MM'(한국 시각) · 읽을 수 없으면 원문.
export function mdHm(iso: string | null | undefined): string {
  if (!iso) return "확인 불가";
  const d = parseIsoInstant(iso); // 느슨한 해석 금지(2026-02-30 을 3/2 로 보이지 않음 · F2)
  if (!d) return iso;
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Seoul",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(d);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${Number(get("month"))}/${Number(get("day"))} ${get("hour")}:${get("minute")}`;
}

export function scheduleSummary(s: OciStartupStatus | null): string {
  const rows = s?.schedule;
  if (!rows || rows.length === 0) return "예약 확인 불가";
  const ok = rows.filter((r) => r.state === "registered").length;
  const missing = rows.filter((r) => r.state === "missing").length;
  const unknown = rows.filter((r) => r.state === "unknown").length;
  return [
    `예약 ${ok}/${rows.length} 확인`,
    missing ? `누락 ${missing}` : null,
    unknown ? `확인 불가 ${unknown}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

// 종류별 '오늘 기록' — 동기화 날짜와 실행 날짜가 모두 오늘(KST)일 때만.
export function todayRecords(d: LedgerLatestByKind): LedgerLatestByKind["kinds"] {
  const syncDay = kstDate(d.sync.last_success_at);
  if (!d.sync.has_copy || !isRealDate(d.today_kst) || syncDay !== d.today_kst) return [];
  return d.kinds.filter((k) => k.run_date_kst === d.today_kst);
}

export function sendSummary(l: Load<LedgerLatestByKind>): string {
  if (l.phase === "loading") return "발송 기록 확인 중";
  if (l.phase === "error") return "발송 기록 불러오지 못함";
  if (!l.data.sync.has_copy) return "발송 사본 없음";
  const t = todayRecords(l.data);
  return t.length === 0 ? "발송 확인 불가" : `오늘 기록 ${t.length}/${l.data.kinds.length}`;
}

export default function OciScheduleCard({
  onNavigate,
  open: openProp,
  onToggle,
}: {
  onNavigate: (key: MenuKey) => void;
  open?: boolean;
  onToggle?: () => void;
}) {
  const [openSelf, setOpenSelf] = useState(false);
  const open = openProp ?? openSelf;
  const [oci, setOci] = useState<Load<OciStartupStatus>>({ phase: "loading" });
  const [ledger, setLedger] = useState<Load<LedgerLatestByKind>>({ phase: "loading" });

  useEffect(() => {
    let alive = true;
    fetchOciStartupStatus()
      .then((data) => alive && setOci({ phase: "ok", data }))
      .catch(() => alive && setOci({ phase: "error" }));
    fetchLedgerLatestByKind()
      .then((data) => alive && setLedger({ phase: "ok", data }))
      .catch(() => alive && setLedger({ phase: "error" }));
    return () => {
      alive = false;
    };
  }, []);

  const s = oci.phase === "ok" ? oci.data : null;
  const schedSummary =
    oci.phase === "loading" ? "예약 확인 중" : oci.phase === "error" ? "예약 상태 불러오지 못함" : scheduleSummary(s);
  const today = ledger.phase === "ok" ? todayRecords(ledger.data) : [];

  return (
    <section className="tc-card tc-fold-card" aria-label="OCI 운영 스케줄 확인" data-testid="tc-oci-card">
      <div className="tc-fold-card-head">
        <h2 className="tc-h2 tc-fold-card-title">OCI 운영 스케줄 확인</h2>
        <span className="tc-chip" data-testid="tc-oci-summary">
          {schedSummary}
        </span>
        <span className="tc-muted tc-small" data-testid="tc-send-summary">
          {sendSummary(ledger)}
        </span>
        <button
          type="button"
          className="btn-md tc-fold-btn tc-fold-card-btn"
          aria-expanded={open}
          aria-label={open ? "OCI 운영 스케줄 확인 접기" : "OCI 운영 스케줄 확인 펼치기"}
          onClick={() => (onToggle ? onToggle() : setOpenSelf((v) => !v))}
        >
          {open ? "접기" : "펼치기"}
        </button>
      </div>
      {open ? (
        <div className="tc-fold-card-body" data-testid="tc-oci-body">
          <div className="tc-muted tc-small">
            기동 확인 {s?.checked_at ? mdHm(s.checked_at) : "확인 불가"} · PC 백엔드가 켜질 때 1회 읽은 값입니다
          </div>
          {s?.schedule && s.schedule.length > 0 ? (
            <ul className="tc-fresh-list">
              {s.schedule.map((r) => (
                <li key={r.kind} className="tc-fresh-row" data-kind={r.kind}>
                  <span className="tc-fresh-label">{r.label}</span>
                  <span className={r.state === "registered" ? "tc-ok" : "tc-warn"}>{STATE_WORD[r.state] ?? r.state}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="tc-muted tc-small">
              {s ? `${s.summary_line} · 알림별 예약 상태는 확인 불가(서버 응답에 예약 목록 없음)` : schedSummary}
            </p>
          )}
          <div className="tc-divider tc-oci-send" data-testid="tc-oci-send">
            <div>
              최근 PUSH 발송{" "}
              <span className="tc-muted">
                {ledger.phase === "ok" && ledger.data.sync.has_copy && today.length === 0
                  ? `확인 불가 · 사본 ${mdHm(ledger.data.sync.last_success_at)}`
                  : sendSummary(ledger)}
              </span>
            </div>
            {ledger.phase === "ok" && ledger.data.sync.has_copy ? (
              <ul className="tc-list-plain tc-small">
                {ledger.data.kinds.map((k) => (
                  <li key={k.kind} data-kind={k.kind}>
                    {k.label} ·{" "}
                    {k.time_kst
                      ? `${md(k.run_date_kst)} ${mdHm(k.time_kst).split(" ")[1] ?? ""} ${
                          k.delivery_status ? (DELIVERY_WORD[k.delivery_status] ?? k.delivery_status) : "결과 기록 없음"
                        }`
                      : "실행 기록 없음"}
                  </li>
                ))}
                <li className="tc-muted">사본 동기화 {mdHm(ledger.data.sync.last_success_at)}</li>
              </ul>
            ) : null}
          </div>
          <div className="tc-btn-row">
            <button type="button" className="tc-btn tc-btn-link" onClick={() => onNavigate("alert_records")}>
              받은 알림 기록 →
            </button>
            <button type="button" className="tc-btn tc-btn-link" onClick={() => onNavigate("approval")}>
              OCI 운영·적용 →
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
