"use client";

// POC5-08 — 「사후평가 결과」 카드(설계 §8 · 사용자 확인 목업 2026-10-11).
//
// 완성된 최신 산출물의 요약만 보인다 — 실행은 화면 머리의 [사후평가 실행]. 기준 날짜(신호 기간 끝 ·
// 가격 관측 기준일 · 사본 읽은 시각 · 사본 동기화) → 건수 → 가격 결과 → ML 과거 검증 → 안내 순서.
// 결과 수치는 원시값의 화면 표현이라 성공 · 실패 색이나 배지를 붙이지 않는다.

import type { RetroBlock, RetroResult } from "@/lib/api";
import { fmtStamp } from "./format";

const HORIZONS = [1, 5, 20] as const;
const MISSING: { code: string; label: string }[] = [
  { code: "T0_MISSING", label: "기준 가격 없음" },
  { code: "PRICE_MISSING", label: "가격 자료 없음" },
  { code: "UNTRACKED_AFTER_EXIT", label: "매도 뒤 추적 중단" },
  { code: "UNSUPPORTED_PRICE_SOURCE", label: "지원 계열 없음" },
];
// ML 대상이 아닌 +5 칸의 사유(백엔드 features.REASON_TEXT 의 짧은 표기).
const NOT_ELIGIBLE: { code: string; label: string }[] = [
  { code: "NOT_MATURED", label: "+5 미성숙" },
  { code: "NO_LABEL", label: "+5 결과 없음" },
  { code: "OUT_OF_SCOPE", label: "이번 ML 범위 밖" },
  { code: "UNSUPPORTED_CONTRACT", label: "지원 안 되는 계약 버전" },
  { code: "UNSUPPORTED_PRICE_BASIS", label: "지원 안 되는 가격 기준" },
];

// 대상에서 뺀 항목의 사유(백엔드 population._exclusions 코드).
const EXCLUSION: { code: string; label: string }[] = [
  { code: "after_end", label: "신호 기간 끝 뒤" },
  { code: "run_not_finalized", label: "끝나지 않은 실행" },
  { code: "cohort_not_primary_live", label: "운영 표본 아님(LEGACY 등)" },
  { code: "off_schedule", label: "예정 외 실행" },
  { code: "evaluable_0", label: "평가 불가 항목" },
  { code: "subject_not_outcome_target", label: "가격 결과 대상 아님" },
  { code: "market_not_sp500", label: "S&P500 외 시장" },
  { code: "disposition_outside_observed", label: "관측 밖 처리" },
];

const n = (v: number | undefined) => (v ?? 0).toLocaleString("ko-KR");
export const fmtPp = (v: number) => `${v.toFixed(2)}%p`;
const fmtDiff = (v: number) => `${v > 0 ? "+" : v < 0 ? "-" : ""}${Math.abs(v).toFixed(2)}%p`;

function blockState(b: RetroBlock): string {
  return b.status === "VALID" ? "유효" : `자료 부족 · ${b.reason ?? ""}`;
}

interface Props {
  data: RetroResult | null;
  error: string | null;
  // 방금 누른 [사후평가 실행] 이 산출물을 만들지 못했을 때의 문구(사본 없음 · 확인 필요 · 실패).
  runProblem: string | null;
}

export default function RetroSummary({ data, error, runProblem }: Props) {
  return (
    <div className="card" data-testid="retro-summary">
      <div className="ar-retro-head">
        <h2>사후평가 결과</h2>
        {data?.status === "OK" && data.input_changed === false ? (
          <span className="ar-retro-ok">{data.input_check ?? ""}</span>
        ) : null}
      </div>
      {runProblem ? <div className="message error">사후평가 실행 — {runProblem}</div> : null}
      {error ? (
        <div className="message error">사후평가 결과를 불러오지 못했습니다 — {error}</div>
      ) : !data ? (
        <div className="ar-note">불러오는 중...</div>
      ) : data.status === "OK" ? (
        <Body data={data} />
      ) : data.status === "NO_RESULT" ? (
        <div className="ar-note">
          아직 사후평가 결과가 없습니다 — [사후평가 실행]을 누르면 PC 원장 사본으로 만듭니다.
        </div>
      ) : (
        <div className="message error">{data.status_text}</div>
      )}
    </div>
  );
}

function Body({ data }: { data: RetroResult }) {
  const s = data.summary;
  const ml = data.ml;
  const fb = data.feedback_summary;
  const partial = s?.delivery.partial_items ?? 0;
  const excluded = EXCLUSION.filter((r) => (data.exclusions?.[r.code] ?? 0) > 0)
    .map((r) => `${r.label} ${n(data.exclusions?.[r.code])}`)
    .join(" · ");
  const notEligible = NOT_ELIGIBLE.filter((r) => (ml?.not_eligible[r.code] ?? 0) > 0)
    .map((r) => `${r.label} ${n(ml?.not_eligible[r.code])}`)
    .join(" · ");
  return (
    <>
      {data.input_changed ? (
        <div className="ar-retro-warn">
          입력이 변경됨 · 재실행 필요 — 이 결과를 만든 뒤 원장 사본 또는 평가가 바뀌었습니다.
        </div>
      ) : data.input_changed === null ? (
        <div className="ar-retro-warn">
          {data.input_check ?? "입력 변경을 확인할 수 없습니다"} — 아래는 기존 결과입니다.
        </div>
      ) : null}
      <dl className="ar-retro-meta">
        <div>
          <dt>신호 기간 끝(종료일)</dt>
          <dd>{data.end_date ?? "—"}</dd>
        </div>
        <div>
          <dt>가격 관측 기준일</dt>
          <dd>{data.price_asof_date ?? "—"}</dd>
        </div>
        <div>
          <dt>사본 읽은 시각</dt>
          <dd>{fmtStamp(data.snapshot_acquired_at ?? null)}</dd>
        </div>
        <div>
          <dt>생성 시각</dt>
          <dd>{fmtStamp(data.created_at ?? null)}</dd>
        </div>
        <div>
          <dt>사본 동기화</dt>
          <dd>{fmtStamp(data.copy_sync?.last_success_at ?? null)}</dd>
        </div>
      </dl>
      <p className="ar-retro-counts" data-testid="retro-counts">
        <span>대상</span> 알림 {n(s?.denominators.events)} · 항목 {n(s?.denominators.items)} ·
        가격 관측 {n(s?.denominators.price_observations)} · 신호일{" "}
        {n(s?.denominators.signal_dates)}일 &nbsp; <span>전달 · 평가</span> 전달된 항목{" "}
        {n(s?.delivery.delivered_items)}
        {partial > 0 ? ` · 일부 전달 ${n(partial)}` : ""} · 평가 있는 알림{" "}
        {n(fb?.events_with_feedback)} / 없음 {n(fb?.events_without_feedback)}
      </p>
      {excluded ? (
        <p className="ar-retro-counts" data-testid="retro-excluded">
          <span>대상에서 뺀 항목</span> {excluded}
        </p>
      ) : null}
      <div className="ar-table-wrap">
        <table className="ar-table ar-fit">
          <thead>
            <tr>
              <th>가격 결과</th>
              <th className="ar-num">성숙</th>
              <th className="ar-num">미도래</th>
              <th className="ar-num">도래 후 미기록</th>
              <th className="ar-num">결측 · 미추적 · 미지원</th>
            </tr>
          </thead>
          <tbody>
            {HORIZONS.map((h) => {
              const c = s?.status_by_horizon[String(h)] ?? {};
              const miss = MISSING.filter((m) => (c[m.code] ?? 0) > 0);
              return (
                <tr key={h}>
                  <td>+{h} 거래일</td>
                  <td className="ar-num">{n(c.MATURED)}</td>
                  <td className="ar-num">{n(c.PENDING_NOT_DUE)}</td>
                  <td className="ar-num">{n(c.PENDING_DUE)}</td>
                  <td
                    className="ar-num"
                    title={miss.map((m) => `${m.label} ${c[m.code]}`).join(" · ") || undefined}
                  >
                    {n(miss.reduce((acc, m) => acc + (c[m.code] ?? 0), 0))}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {ml ? (
        <p className="ar-retro-ml" data-testid="retro-ml">
          {ml.overall ? (
            <>
              <b>ML 과거 검증(+5): {ml.overall.verdict_text}</b> — 전체 모델 MAE{" "}
              {fmtPp(ml.overall.model_mae_pp)} · 단순 기준 {fmtPp(ml.overall.baseline_mae_pp)}{" "}
              (차이 {fmtDiff(ml.overall.difference_pp)} · 날짜 균형 · {ml.overall.test_dates}{" "}
              시험일)
            </>
          ) : (
            <>
              <b>ML 과거 검증(+5): 자료 부족</b> — {ml.reason ?? ""} · 대상{" "}
              {n(ml.eligible_rows)}행{notEligible ? `(${notEligible})` : ""}
            </>
          )}
        </p>
      ) : null}
      {ml && ml.blocks.length > 0 ? (
        <div className="ar-table-wrap">
          <table className="ar-table ar-fit">
            <thead>
              <tr>
                <th>구간</th>
                <th>신호일</th>
                <th className="ar-num">학습 신호일</th>
                <th className="ar-num">시험 행</th>
                <th className="ar-num">모델 MAE</th>
                <th className="ar-num">단순 기준 MAE</th>
                <th>상태</th>
              </tr>
            </thead>
            <tbody>
              {ml.blocks.map((b) => (
                <tr key={b.index}>
                  <td>{b.index}</td>
                  <td>
                    {b.start.slice(5)} ~ {b.end.slice(5)}
                  </td>
                  <td className="ar-num">{b.train_dates ?? "—"}</td>
                  <td className="ar-num">{n(b.test_rows)}</td>
                  <td className="ar-num">
                    {b.model_mae_pp !== undefined ? fmtPp(b.model_mae_pp) : "—"}
                  </td>
                  <td className="ar-num">
                    {b.baseline_mae_pp !== undefined ? fmtPp(b.baseline_mae_pp) : "—"}
                  </td>
                  <td className={b.status === "VALID" ? undefined : "ar-dim"}>{blockState(b)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <ul className="ar-retro-notes">
        <li>
          가격 결과는 저장된 무조정 종가 비교입니다 — 배당 · 세금 · 수수료를 포함한 개인 손익이
          아닙니다.
        </li>
        <li>
          과거 검증 추정은 보존된 기록으로 다시 계산한 연구 값이며 당시 알림이 낸 예측 · 추천이
          아닙니다. 사용자 평가는 쓰지 않습니다.
        </li>
        {ml && !ml.overall ? (
          <li>
            세 구간 전체 비교는 구간마다 학습 신호일 20일 이상과 시험 행이 갖춰지면 나옵니다.
          </li>
        ) : null}
      </ul>
    </>
  );
}
