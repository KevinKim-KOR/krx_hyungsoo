"use client";

// POC3-02C-OPS-01 — 장중 급등락 설정 승인 카드 (2026-09-16).
//
// 설계자 §4-3 — **직접 종목을 고르는 편집 화면이 아니다.** PC 가 자동 산출한
// 버전의 변경 요약을 보고 승인하거나 기각한다.
//
// 승인과 적용은 한 번의 동작이다(§10-3(3)). 전달이 실패해도 승인은 남으므로
// 재시도할 때 다시 승인할 필요가 없다.
//
// 표시 계약 (설계자 2026-09-16):
//   - 화면 표시명은 내부 이름이 아니라 「장중 급등락 설정」
//   - enabled=false · 정책 미설정을 **오류처럼 표시하지 않는다**
//     → "구조 준비 완료 · 장중 알림 정책 설정 전"
//   - ETF 직접 편집 기능 추가 금지
//   - "승인 대기" 문구를 쓰지 않는다 — 이 화면에는 그 표현을 금지하는 기존
//     계약이 있다(ApprovalTelegramView.test.tsx "빈 자리표시자를 만들지 않는다").
//     대신 "확인할 변경" 으로 쓴다.
//
// 기존 ThreePushParamCard 는 건드리지 않는다 — 별개 운영 경로다.
//
// 2026-09-27 사용자 직접 지시(가독성 · 배치만): 세로로 늘어진 dt/dd 를
//   - 제목 오른쪽 배지 = **지금** 알림 상태(현재 운영값 · 후보 값 아님 — 검증자 P1)
//   - 정렬된 행: 사업군 · 자료 기준일 · (후보 있을 때) 적용 후 상태 · OCI 반영 · 확인할 변경
//   - 판정 기준 값은 늘 펼쳐 둔다
//   - 설정 버전 · 확인값 · 산출 규칙만 「자세히 보기」 안으로
//   로 다시 배치했다. 후보 영역(동작 h3 · 미확정/재시도 문단 · 변경 목록 · 경고 ·
//   버튼 · 알림)의 문구와 조건은 그대로다. 위 표시 계약도 모두 그대로다.

import { Fragment, useCallback, useEffect, useState } from "react";
import {
  approveAndApplyIntradayConfig,
  fetchIntradayConfigState,
  rejectIntradayConfig,
  type IntradayConfigState,
} from "@/lib/api/intradayConfig";

function changeLabel(change: string): string {
  if (change === "added") return "추가";
  if (change === "removed") return "제외";
  return "교체";
}

// OCI 반영 상태. 아직 보낸 적이 없는 것은 실패가 아니다.
function deployLabel(status: string | null): string {
  if (status === "deployed") return "적용 완료";
  if (!status) return "아직 적용하지 않음";
  // 설계자 확정 — 모르는 것을 완료·실패로 단정하지 않는다.
  if (status === "deploy_unconfirmed") return "OCI 적용 여부 확인 필요";
  return "적용 실패";
}

// enabled=false 는 미완성이 아니라 이번 단계의 정상 상태다.
function policyLabel(enabled: boolean, status: string | null): string {
  if (enabled) return "장중 알림 발송 중";
  if (status === "NOT_CONFIGURED") return "구조 준비 완료 · 장중 알림 정책 설정 전";
  return "구조 준비 완료";
}

// `.oci-state` 배지 톤 (globals.css). 발송 중 = ok. 꺼져 있는 것은 이번 단계의
// 정상 상태라 경고색이 아니라 회색(unknown)이다 — 오류처럼 보이지 않게.
function policyTone(enabled: boolean): string {
  return enabled ? "ok" : "unknown";
}

// 아직 보낸 적 없음 = 회색. 미확정·실패 = warn(완료로도 실패로도 칠하지 않는 건
// 문구가 한다 — 「OCI 적용 여부 확인 필요」).
function deployTone(status: string | null): string {
  if (status === "deployed") return "ok";
  if (!status) return "unknown";
  return "warn";
}

// 전달이 실패한 승인본은 **재승인 없이** 재시도한다(§10-3(3)).
const RETRY = "approved_not_deployed";

function shortHash(h: string | null): string {
  return h ? `${h.slice(0, 12)}…` : "—";
}

// OPS-03 §2 — 정책 키를 사용자 말로 옮긴다. 내부 키 이름을 그대로 보이지
// 않는다. 값은 **읽기 전용**이다 — 고치는 입력란을 만들지 않는다.
const POLICY_LABEL: Record<string, string> = {
  drop_threshold_pct: "보유 급락 기준",
  surge_threshold_pct: "보유 급등 기준",
  sector_entry_min_pct: "진입 검토 하한",
  sector_chase_pct: "추격 주의 기준",
  sector_avoid_drop_pct: "진입 회피 기준",
  sector_rank_top_pct: "순위 조건",
  sector_min_coverage_pct: "최소 조회 성공률",
  cooldown_minutes: "재발송 대기",
  dedup_window_minutes: "중복 억제 창",
  max_sends_per_run: "회차당 최대",
  max_sends_per_day: "하루 최대",
  max_items_per_section: "구역별 최대",
};

const PCT_KEYS = new Set([
  "drop_threshold_pct",
  "surge_threshold_pct",
  "sector_entry_min_pct",
  "sector_chase_pct",
  "sector_avoid_drop_pct",
  "sector_rank_top_pct",
  "sector_min_coverage_pct",
]);

const MIN_KEYS = new Set(["cooldown_minutes", "dedup_window_minutes"]);

// 이 둘은 **독립 조절 대상이 아니다**(설계자 OPS-03 필수 보완).
// `dedup_window_minutes` 는 `cooldown_minutes` 의 호환 별칭이고,
// `max_sends_per_run` 은 회차당 본문 1개라는 구조에서 나온 고정값이다.
// 다른 값과 같은 목록에 두면 조절할 수 있는 것처럼 보인다.
const DERIVED_KEYS = new Set(["dedup_window_minutes", "max_sends_per_run"]);

function policyValueText(key: string, value: unknown): string {
  // 값이 없으면 **빠졌다는 사실을 보인다.** 0 으로 위장하지 않는다.
  if (value === null || value === undefined) return "없음";
  if (PCT_KEYS.has(key)) return `${value}%`;
  if (MIN_KEYS.has(key)) return `${value}분`;
  return `${value}건`;
}

export default function IntradayConfigCard() {
  const [state, setState] = useState<IntradayConfigState | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setState(await fetchIntradayConfigState());
    } catch {
      setState(null);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const onApprove = useCallback(async () => {
    if (!state?.candidate_version_id) return;
    setBusy(true);
    try {
      const r = await approveAndApplyIntradayConfig(state.candidate_version_id);
      setNotice(r.message);
    } catch {
      // 실패해도 카드의 기존 상태를 유지한다 — 직전 적용 상태를 볼 수 있어야 한다.
      setNotice("요청이 실패했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setBusy(false);
      void reload();
    }
  }, [state, reload]);

  const onReject = useCallback(async () => {
    if (!state?.candidate_version_id) return;
    setBusy(true);
    try {
      const r = await rejectIntradayConfig(
        state.candidate_version_id,
        "사용자 기각",
      );
      setNotice(r.message);
    } catch {
      setNotice("요청이 실패했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setBusy(false);
      void reload();
    }
  }, [state, reload]);

  if (!state) {
    return (
      <section className="tc-card ops-card" aria-label="장중 급등락 설정">
        <h2 className="tc-h2" aria-level={3}>
          장중 급등락 설정
        </h2>
        <p className="tc-muted tc-small">불러오는 중...</p>
      </section>
    );
  }

  // 내용이 깨진 설정을 "0개 사업군" 으로 그리지 않는다 — 정상적으로 비어 있는
  // 것과 구분되지 않는 거짓 표시다.
  if (state.payload_error) {
    return (
      <section className="tc-card ops-card" aria-label="장중 급등락 설정">
        <h2 className="tc-h2" aria-level={3}>
          장중 급등락 설정
        </h2>
        <p className="tc-small">
          저장된 설정을 읽지 못했습니다. 값을 표시하지 않습니다.
        </p>
        <p className="tc-muted tc-small">{state.payload_error}</p>
      </section>
    );
  }

  const hasCandidate = Boolean(state.candidate_version_id);
  // **미확정이 재시도보다 우선한다.** 둘 다 참이 될 수 있는데(승인은 됐고
  // active 는 아니므로 action_state 는 approved_not_deployed 다), 같이 그리면
  // "완료도 실패도 아니다" 와 "전달만 실패했다" 가 한 화면에 동시에 뜬다
  // — 설계 §12-4 의 완료·실패 추정 금지 위반이다(검증자 지적).
  const isUnconfirmed = state.deploy_status === "deploy_unconfirmed";
  const isRetry = state.action_state === RETRY && !isUnconfirmed;
  const shown = hasCandidate
    ? {
        sectors: state.candidate_sector_count,
        asof: state.candidate_data_asof,
        hash: state.candidate_source_hash,
        version: state.candidate_version_id,
      }
    : {
        sectors: state.active_sector_count,
        asof: state.active_data_asof,
        hash: state.active_source_hash,
        version: state.active_version_id,
      };

  // 「확인할 변경」 행 — 후보가 없으면 없음. 후보가 있으면 바뀐 사업군 수,
  // 첫 설정이거나 바뀐 사업군이 없어도 확인할 버전 자체는 있으므로 "있음".
  const changeSummary = !hasCandidate
    ? "없음"
    : state.active_version_id !== null && state.changes.length > 0
      ? `${state.changes.length}건`
      : "있음";

  return (
    <section className="tc-card ops-card" aria-label="장중 급등락 설정">
      <div className="ops-card-head">
        {/* 합친 화면에서 이 카드는 「② OCI 에 적용」(h2) 안에 있다 — 스크린리더에는
            3단계로 알린다. `<h3>` 요소로 바꾸지 않는다: 이 카드의 `h3` 는 **지금 할
            동작** 하나만이라는 계약이 있다(IntradayConfigCard.test.tsx). */}
        <h2 className="tc-h2" aria-level={3}>
          장중 급등락 설정
        </h2>
        {/* **현재 운영 상태**다. 후보 값을 여기 쓰면 승인 전인데도 "발송 중"
            으로 보인다(검증자 P1). 적용 후 상태는 아래 별도 행이다. */}
        <span
          className={`oci-state ${policyTone(state.policy_enabled)}`}
          title="지금 알림 상태 (현재 운영 중인 설정 기준)"
        >
          {policyLabel(state.policy_enabled, state.policy_status)}
        </span>
      </div>

      <p className="tc-muted tc-small">
        장중에 지켜볼 사업군과 대표 ETF 는 자동으로 정해집니다. 바뀐 내용을
        확인하고 승인하면 운영에 반영됩니다.
      </p>

      <dl className="ops-kv">
        <dt>{hasCandidate ? "적용 예정 사업군" : "지켜보는 사업군"}</dt>
        <dd>{shown.sectors}개 (사업군마다 대표 ETF 1종목)</dd>

        <dt>자료 기준일</dt>
        <dd>{shown.asof ?? "—"}</dd>

        {/* 후보가 있을 때는 **지금**과 **적용 후**를 나란히 글로 보인다 — 제목 옆
            배지만으로는 어느 쪽인지 구분되지 않는다(터치 화면은 툴팁도 없다). */}
        {hasCandidate ? (
          <>
            <dt>지금 알림 상태</dt>
            <dd>{policyLabel(state.policy_enabled, state.policy_status)}</dd>
          </>
        ) : null}

        {hasCandidate && state.candidate_policy_enabled !== null ? (
          <>
            <dt>적용 후 상태</dt>
            <dd>
              {state.candidate_policy_enabled
                ? "장중 알림 발송 시작"
                : "장중 알림 없음"}
            </dd>
          </>
        ) : null}

        <dt>OCI 반영</dt>
        <dd>
          <span className={`oci-state ${deployTone(state.deploy_status)}`}>
            {deployLabel(state.deploy_status)}
          </span>
        </dd>

        {/* 재시도 · 미확정은 **승인이 이미 기록된** 상태다 — '확인할 변경' 을
            보이면 다시 확인 · 승인하라는 뜻으로 읽힌다. 아래 동작 제목이 대신한다. */}
        {isRetry || isUnconfirmed ? null : (
          <>
            <dt>확인할 변경</dt>
            <dd>{changeSummary}</dd>
          </>
        )}
      </dl>

      {state.policy_values.length > 0 ? (
        <>
          {/* `h3` 를 쓰지 않는다 — 이 카드의 `h3` 는 **지금 할 동작** 하나만
              나오게 막는 계약이 있다(IntradayConfigCard.test.tsx "재시도 문단과
              동시에 렌더되지 않는다"). 이 블록은 동작이 아니라 정보다.
              2026-09-27: 접지 않고 늘 펼쳐 둔다(사용자 지시). */}
          <p className="tc-small ops-sub">
            <b>적용될 판정 기준</b> — PC 가 산출한 값입니다. 여기서 고치지 않고
            버전 전체를 승인합니다.
          </p>
          <dl className="ops-kv">
            {state.policy_values
              .filter((p) => !DERIVED_KEYS.has(p.key))
              .map((p) => (
                <Fragment key={p.key}>
                  <dt>{POLICY_LABEL[p.key] ?? p.key}</dt>
                  <dd>{policyValueText(p.key, p.value)}</dd>
                </Fragment>
              ))}
          </dl>

          <p className="tc-muted tc-small">
            중복 억제 창은 재발송 대기와 같은 값이고, 회차당 최대는 1건으로
            고정입니다. 따로 조절하지 않습니다.
          </p>
        </>
      ) : null}

      {/* 대조용 식별값만 접는다 — 판단에 쓰는 값(위)은 접지 않는다. */}
      <details className="ops-details">
        <summary>자세히 보기 (설정 버전 · 확인값 · 산출 규칙)</summary>
        <dl className="ops-kv">
          <dt>설정 버전</dt>
          <dd>{shown.version ?? "—"}</dd>

          <dt>확인값</dt>
          <dd>{shortHash(shown.hash)}</dd>

          <dt>산출 규칙</dt>
          <dd>{state.policy_rule_version ?? "—"}</dd>
        </dl>
      </details>

      {/* 경고는 **적용 결과**로 판단한다. `policy_enabled`(현재 상태)로 가리면
          정작 켜지는 순간에 경고가 숨는다(검증자 P1). */}
      {hasCandidate && state.candidate_policy_enabled ? (
        <p className="tc-small">
          <b>이 설정을 적용하면 장중 알림이 실제로 발송됩니다.</b> 기존 고정 4건에
          더해 조건이 맞는 날 최대 4건이 추가됩니다(하루 최대 8건). 조건이 없으면
          추가 발송은 없습니다.
        </p>
      ) : null}

      {hasCandidate ? (
        <>
          <h3 className="tc-h3">
            {isUnconfirmed
              ? "OCI 적용 여부 확인 필요"
              : isRetry
                ? "적용하지 못한 설정"
                : "확인할 변경"}
          </h3>

          {isUnconfirmed ? (
            <p className="tc-small">
              통신이 끊겨 <b>OCI에 적용됐는지 확인하지 못했습니다.</b> 완료도
              실패도 아닙니다. OCI 상태를 확인한 뒤 재시도해 주세요. 자동으로
              다시 보내지 않습니다.
            </p>
          ) : null}

          {isRetry ? (
            <p className="tc-small">
              승인은 이미 기록됐고 OCI 전달만 실패했습니다. 다시 승인할 필요
              없이 재시도하면 됩니다.
              {state.deploy_error ? ` (사유: ${state.deploy_error})` : ""}
            </p>
          ) : null}

          {state.active_version_id === null ? (
            <p className="tc-small">첫 설정입니다. 직전 승인본이 없습니다.</p>
          ) : state.changes.length > 0 ? (
            <ul className="tc-list">
              {state.changes.map((c) => (
                <li key={`${c.sector_key}-${c.change}`}>
                  <b>{c.sector_key}</b> {changeLabel(c.change)}
                  {c.before ? ` · 이전 ${c.before}` : ""}
                  {c.after ? ` · 이후 ${c.after}` : ""}
                </li>
              ))}
            </ul>
          ) : (
            <p className="tc-muted tc-small">
              직전 승인본과 달라진 사업군이 없습니다.
            </p>
          )}

          <div className="tc-actions">
            <button type="button" onClick={onApprove} disabled={busy}>
              {isUnconfirmed || isRetry ? "OCI 적용 재시도" : "승인하고 OCI 적용"}
            </button>
            <button type="button" onClick={onReject} disabled={busy}>
              기각
            </button>
          </div>
        </>
      ) : (
        <p className="tc-muted tc-small">확인할 변경이 없습니다.</p>
      )}

      {notice ? <p className="tc-small">{notice}</p> : null}
    </section>
  );
}
