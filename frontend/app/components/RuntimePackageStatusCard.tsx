"use client";

// POC2 3-PUSH Runtime Package PC 검증 (2026-06-13) — runtime_package 상태 카드.
//
// 책임 (지시문 §11):
// - draft_payload.runtime_package 가 있으면 status / source probe 요약만 표시.
// - 빈 runtime slot 을 "unavailable" placeholder 로 반복 노출하지 않는다 (§14).
// - raw JSON 덤프는 details 내부에서만 노출 (개발자용 접힘).
// - schema_version / package_id / generation_status / runtime probe 상태 요약.
//
// frontend 는 message_text 를 조립하지 않는다 — 본 카드도 message_text 를
// 생성/변형하지 않고, runtime_package 의 status 만 read-only 표시한다.

import type { Run } from "@/lib/api";

interface RuntimePackageGenerationStatus {
  status?: string;
  missing_sections?: unknown;
  warnings?: unknown;
  errors?: unknown;
}

interface RuntimeSnapshotItemStatus {
  status?: string;
  captured_at?: string;
  items?: unknown[];
  indices?: unknown[];
}

interface RuntimeSnapshot {
  captured_at?: string;
  kr_realtime_price_snapshot?: RuntimeSnapshotItemStatus;
  overnight_us_market_snapshot?: RuntimeSnapshotItemStatus;
  cache_status?: string;
}

interface RuntimePackage {
  schema_version?: string;
  package_id?: string;
  push_kind?: string;
  source_mode?: string;
  generation_status?: RuntimePackageGenerationStatus;
  runtime_snapshot?: RuntimeSnapshot;
}

function asRecord(v: unknown): Record<string, unknown> | null {
  if (v && typeof v === "object" && !Array.isArray(v)) {
    return v as Record<string, unknown>;
  }
  return null;
}

function extractRuntimePackage(run: Run): RuntimePackage | null {
  const payload = asRecord(run.draft_payload);
  if (!payload) return null;
  const pkg = asRecord(payload.runtime_package);
  if (!pkg) return null;
  return pkg as RuntimePackage;
}

function statusBadgeClass(status: string | undefined): string {
  switch (status) {
    case "ok":
      return "status-COMPLETED";
    case "partial":
      return "status-DELIVERING";
    case "failed":
    case "unavailable":
      return "status-FAILED";
    default:
      return "status-PENDING_APPROVAL";
  }
}

function summarizeKrSnapshot(snap: RuntimeSnapshotItemStatus | undefined): string {
  if (!snap || !snap.status) return "데이터 없음";
  const items = Array.isArray(snap.items) ? snap.items : [];
  const ok = items.filter(
    (it) =>
      it !== null &&
      typeof it === "object" &&
      (it as Record<string, unknown>).data_status === "ok",
  ).length;
  if (snap.status === "ok") return `정상 (${ok}/${items.length}건)`;
  if (snap.status === "partial") return `부분 성공 (${ok}/${items.length}건)`;
  if (snap.status === "failed") return "조회 실패 (소스 응답 없음)";
  if (snap.status === "unavailable") return "조회 미수행";
  return snap.status;
}

function summarizeUsSnapshot(snap: RuntimeSnapshotItemStatus | undefined): string {
  if (!snap || !snap.status) return "데이터 없음";
  const indices = Array.isArray(snap.indices) ? snap.indices : [];
  const ok = indices.filter(
    (it) =>
      it !== null &&
      typeof it === "object" &&
      (it as Record<string, unknown>).status === "ok",
  ).length;
  if (snap.status === "ok") return `정상 (${ok}/${indices.length}종)`;
  if (snap.status === "partial") return `부분 성공 (${ok}/${indices.length}종)`;
  if (snap.status === "failed") return "조회 실패 (소스 응답 없음)";
  if (snap.status === "unavailable") return "조회 미수행";
  return snap.status;
}

export default function RuntimePackageStatusCard({ run }: { run: Run }) {
  const pkg = extractRuntimePackage(run);
  if (!pkg) {
    return null;
  }
  const gs = pkg.generation_status ?? {};
  const rs = pkg.runtime_snapshot ?? {};
  const kr = rs.kr_realtime_price_snapshot;
  const us = rs.overnight_us_market_snapshot;

  // 빈 placeholder 금지 (§14) — kr 또는 us 가 unavailable 이면 해당 행 자체 생략.
  const showKr = kr && kr.status && kr.status !== "unavailable";
  const showUs = us && us.status && us.status !== "unavailable";

  const warnings = Array.isArray(gs.warnings) ? (gs.warnings as string[]) : [];
  const errors = Array.isArray(gs.errors) ? (gs.errors as string[]) : [];
  const missing = Array.isArray(gs.missing_sections)
    ? (gs.missing_sections as string[])
    : [];

  return (
    <div className="card" style={{ marginTop: 12 }}>
      <h3 style={{ marginTop: 0 }}>Runtime Package 상태</h3>
      <div className="status-row" style={{ flexWrap: "wrap", gap: 8 }}>
        <span className={`status-badge ${statusBadgeClass(gs.status)}`}>
          {gs.status ?? "-"}
        </span>
        <span className="kv">
          <span className="k">schema</span>
          <span className="v">
            <code>{pkg.schema_version ?? "-"}</code>
          </span>
        </span>
        <span className="kv">
          <span className="k">push_kind</span>
          <span className="v">{pkg.push_kind ?? "-"}</span>
        </span>
        <span className="kv">
          <span className="k">source_mode</span>
          <span className="v">{pkg.source_mode ?? "-"}</span>
        </span>
        {rs.cache_status ? (
          <span className="kv">
            <span className="k">cache</span>
            <span className="v">{rs.cache_status}</span>
          </span>
        ) : null}
      </div>
      <div style={{ marginTop: 8 }}>
        {showKr ? (
          <div className="helper">
            국내 시세 probe: <strong>{summarizeKrSnapshot(kr)}</strong>
          </div>
        ) : null}
        {showUs ? (
          <div className="helper">
            미국 지수 probe: <strong>{summarizeUsSnapshot(us)}</strong>
          </div>
        ) : null}
      </div>
      {warnings.length > 0 ? (
        <div className="message info" style={{ marginTop: 8 }}>
          <strong>warnings:</strong> {warnings.join(", ")}
        </div>
      ) : null}
      {errors.length > 0 ? (
        <div className="message error" style={{ marginTop: 8 }}>
          <strong>errors:</strong> {errors.join(", ")}
        </div>
      ) : null}
      {missing.length > 0 ? (
        <div className="message error" style={{ marginTop: 8 }}>
          <strong>missing:</strong> {missing.join(", ")}
        </div>
      ) : null}
      <details style={{ marginTop: 8 }}>
        <summary
          style={{ cursor: "pointer", color: "var(--muted)", fontSize: "0.85rem" }}
        >
          개발자 보기 (raw runtime_package JSON)
        </summary>
        <pre
          style={{
            marginTop: 8,
            background: "var(--code-bg, #1115)",
            padding: 8,
            borderRadius: 4,
            maxHeight: 320,
            overflow: "auto",
            fontSize: "0.75rem",
          }}
        >
          {JSON.stringify(pkg, null, 2)}
        </pre>
      </details>
    </div>
  );
}
