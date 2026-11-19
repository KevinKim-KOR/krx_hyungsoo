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
//   - enabled=false · 정책 미설정을 **오류처럼 표시하지 않는다**(회색 배지)
//   - ETF 직접 편집 기능 추가 금지
//   - "승인 대기" 문구를 쓰지 않는다 — 이 화면에는 그 표현을 금지하는 기존
//     계약이 있다(ApprovalTelegramView.test.tsx "빈 자리표시자를 만들지 않는다").
//     대신 "확인할 변경" 으로 쓴다.
//
// 기존 ThreePushParamCard 는 건드리지 않는다 — 별개 운영 경로다.
//
// 2026-09-27 사용자 직접 지시(가독성 · 배치만): 세로로 늘어진 dt/dd 를
//   - 제목 오른쪽 배지 = **지금** 알림 상태(현재 운영값 · 후보 값 아님 — 검증자 P1)
//   - 정렬된 행: 사업군 · 종가일 · (후보 있을 때) 승인 후 설정 · OCI 반영 · 확인할 변경
//   - 판정 기준 값은 늘 펼쳐 둔다
//   - 설정 버전 · 확인값 · 산출 규칙만 「자세히 보기」 안으로
//   로 다시 배치했다.
//
// POC6-34 (PLAN V1 O8 ~ O12 · Q5 · Q6 · Q10 · I-13 ~ I-26):
//   - 배지 = PC DB 에 기록된 활성 설정 플래그다. 실제 발송도, OCI 현재값을 읽은 결과도 아니다
//     → 'PC 기록 기준 · 장중 알림 설정 켜짐 / 꺼짐 / 정책 미설정 / 확인 불가'.
//   - 조회 실패는 '불러오는 중...' 과 구분한다(값 없이 확인 불가 분기 · 직전 동작 안내는 남김).
//   - 후보 쪽 문구도 설정 상태로 쓴다('발송 시작' 아님) · 경고는 꺼짐 → 켜짐일 때만.
//   - 날짜 = 대표 ETF 선정에 사용한 무조정 종가의 거래일(`sector_representative_universe.data_asof`).
//   - 판정 기준 표는 `approval/IntradayCriteriaTable` 이 그린다(늘 펼침 · 세 묶음 · 4열).
//   - 확인할 변경 = 사업군 대표 추가 · 제외 · 교체 + 장중 알림 설정 켜짐 변화(Q10).
//   - 검증자 r2 R2-F4: 지금(활성) 켜짐 여부도 후보와 같이 '모름'(null)을 따로 다룬다. 배지 · '지금 알림
//     상태' = 확인 불가 · 후보와의 비교는 '같음' · '꺼짐 → 켜짐'을 말하지 않는다 · 경고는 꺼짐 · 켜짐을
//     가정하지 않는 문단으로 바꾼다.
//   - 설계자 RESULT 판정(2026-11-19): C7 켜짐 경고 두 문단의 발송 안내 = '위 표의 하루 최대 한도'(고정 건수
//     문장 없앰) · C8 활성 버전의 정책 상태를 읽지 못하면 배지 · '지금 알림 상태' = 확인한 켜짐 · 꺼짐 +
//     '정책 상태 확인 불가'(회색).

import { useCallback, useEffect, useState } from "react";
import {
  approveAndApplyIntradayConfig,
  fetchIntradayConfigState,
  rejectIntradayConfig,
  type IntradayConfigState,
} from "@/lib/api/intradayConfig";
import IntradayCriteriaTable from "./approval/IntradayCriteriaTable";

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

// 조회 실패 · 설정 손상 · 켜짐 여부를 읽지 못함 — 설정 상태를 확인할 수 없다(Q5 · R2-F4).
const POLICY_UNKNOWN_LABEL = "PC 기록 기준 · 장중 알림 설정 확인 불가";

// 켜짐 여부는 true · false 일 때만 안다. null · 값 없음(옛 응답) · 문자열 "false" 같은 bool 이
// 아닌 값은 모두 null(확인 불가)이다 — 꺼짐으로도 켜짐으로도 읽지 않는다(POC6-34 검증자 r2 R2-F4).
function knownOnOff(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

// 확인 가능한 정책 상태값(백엔드 `schema.POLICY_CONFIGURED` · `POLICY_NOT_CONFIGURED`).
const KNOWN_POLICY_STATUS: ReadonlySet<string> = new Set(["CONFIGURED", "NOT_CONFIGURED"]);

// 설계자 RESULT 판정 C8(2026-11-19) — 활성 버전이 있는데 정책 상태 값이 빠졌거나 확인 가능한 값으로
// 읽히지 않는 경우. 활성 버전이 없는 첫 설정(C6)은 해당하지 않는다.
function policyStatusUnknown(hasActive: boolean, status: unknown): boolean {
  return hasActive && !(typeof status === "string" && KNOWN_POLICY_STATUS.has(status));
}

function onOff(on: boolean): string {
  return on ? "켜짐" : "꺼짐";
}

// 배지 · '지금 알림 상태' 행 문안(I-13). PC DB 활성 버전 사본의 `enabled` 플래그다.
// enabled=false 는 미완성이 아니라 정상 상태일 수 있다 — 오류처럼 칠하지 않는다.
// 켜짐 여부를 모르면 상태값이 미설정이어도 '확인 불가'다(R2-F4 · C8 마지막 문장).
// 켜짐 여부는 알고 활성 버전의 정책 상태만 읽지 못하면 확인한 켜짐 · 꺼짐 뒤에 '정책 상태 확인 불가'를
// 붙인다(C8) — 꺼짐이 '정책 미설정'과 섞이지 않게 한다.
function policyLabel(enabled: boolean | null, status: string | null, hasActive: boolean): string {
  if (enabled === null) return POLICY_UNKNOWN_LABEL;
  if (policyStatusUnknown(hasActive, status)) {
    return `PC 기록 기준 · 장중 알림 설정 ${onOff(enabled)} · 정책 상태 확인 불가`;
  }
  if (enabled) return "PC 기록 기준 · 장중 알림 설정 켜짐";
  if (status === "NOT_CONFIGURED") return "PC 기록 기준 · 장중 알림 정책 미설정";
  return "PC 기록 기준 · 장중 알림 설정 꺼짐";
}

const BADGE_TITLE =
  "장중 알림 설정 (PC 에 기록된 활성 설정 · 실제 발송은 Telegram 에서 확인)";

// `.oci-state` 배지 톤 (globals.css). 켜짐 = ok. 나머지(모름 포함)는 회색(unknown) — 오류처럼 보이지 않게.
// 정책 상태를 확인하지 못한 켜짐(C8)도 회색이다 — 확인되지 않은 부분이 있는 상태를 정상(초록)으로 칠하지 않는다.
function policyTone(enabled: boolean | null, status: string | null, hasActive: boolean): string {
  return enabled === true && !policyStatusUnknown(hasActive, status) ? "ok" : "unknown";
}

// 켜짐 경고 두 문단의 발송 안내(설계자 RESULT 판정 C7 · 2026-11-19 형수님 결정 — 경고는 판정 기준 표 **아래**에
// 그려지므로 '아래의'가 아니라 '위 표의'). 후보에 따라 달라질 수 있는 한도는 표의 후보값에서 읽는다.
const DAILY_LIMIT_NOTE = "발송 조건을 충족한 장중 알림에는 위 표의 하루 최대 한도가 적용됩니다.";
const ENABLE_WARN_HEAD = "이 설정을 승인하면 장중 알림 설정이 켜집니다.";
const UNKNOWN_ENABLE_WARN_HEAD = "이 설정을 승인하면 장중 알림 설정이 켜진 상태가 됩니다.";
const UNKNOWN_ENABLE_WARN_BODY = `지금 설정을 확인할 수 없어 새로 켜지는 것인지는 알 수 없습니다. ${DAILY_LIMIT_NOTE}`;

// '승인 후 장중 알림 설정' 행(I-14) — 승인하면 어떤 설정이 되는지와 지금과의 차이.
// 후보 정책에서 켜짐 여부를 읽지 못하면(null) '확인 불가'다 — '꺼짐'으로 읽지 않는다
// (POC6-34 검증자 r1 R1-F3). 지금 켜짐 여부를 모르면 승인 후 값만 쓰고 비교하지 않는다 —
// '지금과 같음' · '지금 꺼짐 → 켜짐'이라고 쓰지 않는다(r2 R2-F4).
function afterApprovalLabel(candidateOn: boolean | null, nowOn: boolean | null): string {
  if (candidateOn === null) return "확인 불가";
  const after = onOff(candidateOn);
  if (nowOn === null) return `${after} (지금 상태 확인 불가)`;
  if (candidateOn === nowOn) return `${after} (지금과 같음)`;
  return `${after} (지금 ${onOff(nowOn)} → ${after})`;
}

// 달라진 사업군이 없고 켜짐 여부를 비교하지 못했을 때의 문단 — 비교하지 못한 쪽을 그대로 말한다.
// '장중 알림 설정이 없습니다'(켜짐 차이 없음 = 같음)라고 쓰지 않는다(R1-F3 · R2-F4).
function unknownEnabledParagraph(nowOn: boolean | null, candidateOn: boolean | null): string {
  const side =
    nowOn === null && candidateOn === null
      ? "지금 설정과 승인할 설정"
      : nowOn === null
        ? "지금 설정"
        : "승인할 설정";
  return `직전 승인본과 달라진 사업군이 없습니다. ${side}의 장중 알림 켜짐 여부는 확인할 수 없습니다. 판정 기준값 · 대체 ETF 의 차이는 이 화면에서 비교할 수 없습니다.`;
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

// 합친 화면에서 이 카드는 「② OCI 에 적용」(h2) 안에 있다 — 스크린리더에는 3단계로
// 알린다. `<h3>` 요소로 바꾸지 않는다: 이 카드의 `h3` 는 **지금 할 동작** 하나만이라는
// 계약이 있다(IntradayConfigCard.test.tsx).
function CardHead({ label, tone }: { label: string; tone: string }) {
  return (
    <div className="ops-card-head">
      <h2 className="tc-h2" aria-level={3}>
        장중 급등락 설정
      </h2>
      {/* **현재 운영 상태**다. 후보 값을 여기 쓰면 승인 전인데도 "켜짐" 으로 보인다
          (검증자 P1). 승인 후 설정은 아래 별도 행이다. */}
      <span className={`oci-state ${tone}`} title={BADGE_TITLE}>
        {label}
      </span>
    </div>
  );
}

export default function IntradayConfigCard() {
  const [state, setState] = useState<IntradayConfigState | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setState(await fetchIntradayConfigState());
      setLoadFailed(false);
    } catch {
      // 값을 지어내지 않는다 — 실패를 '불러오는 중' 으로도 숨기지 않는다(I-13).
      setState(null);
      setLoadFailed(true);
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

  if (!state && loadFailed) {
    // 첫 조회든 승인 · 기각 뒤 다시 읽기든 실패면 값 없이 이 분기다. 직전 동작 안내는 남긴다.
    return (
      <section className="tc-card ops-card" aria-label="장중 급등락 설정">
        <CardHead label={POLICY_UNKNOWN_LABEL} tone="unknown" />
        <p className="tc-small">장중 급등락 설정을 불러오지 못했습니다.</p>
        {notice ? <p className="tc-small">{notice}</p> : null}
      </section>
    );
  }

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
        <CardHead label={POLICY_UNKNOWN_LABEL} tone="unknown" />
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
  // 지금 · 승인 후 켜짐 여부. 모르면 null — 아래 모든 문구가 이 두 값만 읽는다(R2-F4).
  const nowOn = knownOnOff(state.policy_enabled);
  const candidateOn = knownOnOff(state.candidate_policy_enabled);
  // 활성 버전이 있는지 — 첫 설정(활성 없음 · C6)의 판정은 아래 「확인할 변경」과 같은 조건(`=== null`)이다.
  const hasActive = state.active_version_id !== null;
  const nowLabel = policyLabel(nowOn, state.policy_status, hasActive);

  // Q10 — 응답으로 만들 수 있는 차이는 둘뿐이다: 사업군 대표 추가 · 제외 · 교체와 켜짐 변화.
  // 판정 기준값 · 대체 ETF 의 차이는 응답에 없어 이 화면에서 비교할 수 없다(I-24).
  // 켜짐 변화는 두 쪽을 모두 알 때만 센다 — 한쪽이라도 모르면 변화가 있다고도 없다고도 하지 않는다.
  const enabledChange =
    hasCandidate && candidateOn !== null && nowOn !== null && candidateOn !== nowOn
      ? `${onOff(nowOn)} → ${onOff(candidateOn)}`
      : null;
  const changeCount = state.changes.length + (enabledChange ? 1 : 0);

  // 「확인할 변경」 행 — 후보가 없으면 없음. 첫 설정이면 확인할 버전 자체가 있으므로
  // "있음". 그 밖에는 위 두 차이의 합이고, 합이 0 이면 이 화면에서 비교할 수 없는 차이다.
  const changeSummary = !hasCandidate
    ? "없음"
    : state.active_version_id === null
      ? "있음"
      : changeCount > 0
        ? `${changeCount}건`
        : "있음 (이 화면에서 비교할 수 없는 차이)";

  return (
    <section className="tc-card ops-card" aria-label="장중 급등락 설정">
      <CardHead label={nowLabel} tone={policyTone(nowOn, state.policy_status, hasActive)} />

      <p className="tc-muted tc-small">
        장중에 지켜볼 사업군과 대표 ETF 는 자동으로 정해집니다. 바뀐 내용을
        확인하고 승인하면 운영에 반영됩니다.
      </p>

      <dl className="ops-kv">
        <dt>{hasCandidate ? "적용 예정 사업군" : "지켜보는 사업군"}</dt>
        <dd>{shown.sectors}개 (사업군마다 대표 ETF 1종목)</dd>

        {/* 판정 기준의 날짜도, 설정 생성 · 승인 · 적용 날짜도 아니다(I-15). */}
        <dt>대표 ETF 선정에 사용한 종가일</dt>
        <dd>{shown.asof ?? "—"}</dd>

        {/* 후보가 있을 때는 **지금**과 **승인 후**를 나란히 글로 보인다 — 제목 옆
            배지만으로는 어느 쪽인지 구분되지 않는다(터치 화면은 툴팁도 없다). */}
        {hasCandidate ? (
          <>
            <dt>지금 알림 상태</dt>
            <dd>{nowLabel}</dd>
          </>
        ) : null}

        {/* 후보가 있으면 늘 보인다. 켜짐 여부가 없으면 행을 숨기지 않고 '확인 불가'로 쓴다. */}
        {hasCandidate ? (
          <>
            <dt>승인 후 장중 알림 설정</dt>
            <dd>{afterApprovalLabel(candidateOn, nowOn)}</dd>
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

      {/* 늘 펼친다(2026-09-27 사용자 지시 · 2026-11-19 형수님 결정 Q6). 후보가 있으면 후보 값,
          없으면 PC 에 기록된 활성 값이다(응답 `policy_values`). */}
      <IntradayCriteriaTable
        hasCandidate={hasCandidate}
        policyValues={state.policy_values}
        sectorCount={shown.sectors}
      />

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

      {/* 경고는 **승인 결과**로 판단한다. 지금 꺼져 있고 승인하면 켜질 때만 보인다(I-14).
          이미 켜져 있으면 승인해도 새로 켜지는 것이 아니다. 두 경고 모두 위 판정 기준 표(늘 그림) 아래에
          있어 발송 안내는 '위 표의 하루 최대'를 가리킨다(C7) — 건수를 이 문단에 따로 적지 않는다. */}
      {hasCandidate && candidateOn === true && nowOn === false ? (
        <p className="tc-small">
          <b>{ENABLE_WARN_HEAD}</b> {DAILY_LIMIT_NOTE}
        </p>
      ) : null}

      {/* 지금 켜짐 여부를 모르면(R2-F4) '켜집니다'(지금 꺼짐 가정)도, 경고 없음(지금 켜짐 가정)도
          아니다 — 승인 뒤 켜진 상태가 된다는 것과 위 표의 하루 최대가 적용된다는 것만 말한다. */}
      {hasCandidate && candidateOn === true && nowOn === null ? (
        <p className="tc-small">
          <b>{UNKNOWN_ENABLE_WARN_HEAD}</b> {UNKNOWN_ENABLE_WARN_BODY}
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
          ) : changeCount > 0 ? (
            <ul className="tc-list">
              {state.changes.map((c) => (
                <li key={`${c.sector_key}-${c.change}`}>
                  <b>{c.sector_key}</b> {changeLabel(c.change)}
                  {c.before ? ` · 이전 ${c.before}` : ""}
                  {c.after ? ` · 이후 ${c.after}` : ""}
                </li>
              ))}
              {enabledChange ? (
                <li key="policy-enabled">
                  <b>장중 알림 설정</b>: {enabledChange}
                </li>
              ) : null}
            </ul>
          ) : candidateOn === null || nowOn === null ? (
            // 켜짐 여부를 비교하지 못했으면(어느 쪽이든) '장중 알림 설정이 없습니다'라고 쓰지 않는다.
            <p className="tc-muted tc-small">
              {unknownEnabledParagraph(nowOn, candidateOn)}
            </p>
          ) : (
            <p className="tc-muted tc-small">
              직전 승인본과 달라진 사업군 · 장중 알림 설정이 없습니다. 판정
              기준값 · 대체 ETF 의 차이는 이 화면에서 비교할 수 없습니다.
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
