"use client";

// POC6-32 ④ AI 의견 대조 · ⑤ 최근 검토 기록(판정 Q6 · Q8 (a) · §2 ④ · ⑤).
// 최근 검토 기록 = 이 화면에서 넘겨 저장한 기록 중 저장 시각이 가장 최근인 1건(다른 화면 기록은 섞지 않음).
// ⑤ 한 줄 = 저장 시각 · 원자료 기준일 · 고른 후보(저장한 코드 · 이름) · 사용자 판단 · AI 답 수(목업 ⑤ · 검토 F4).
// 대조는 서버가 규칙으로 한다 — 같은 ETF 의 상태와 인용 근거 번호 집합만(글 뜻 비교 · 자동 AI 호출 없음 · AI 의견).
// POC6-32 V2(PLAN §4-3 · §4-4 · I-12 · I-14) — WeeklyAnswers = 답마다 최신 확인 · AI 가 적은 확인 항목 줄 · ETF 별 상태 ·
// 인용 근거 · 이유 · 다음 확인 · 대조 표. 「주간 ETF 점검」 ④ 와 「AI 투자 세션」 '당시 검토'(기록 하나의 해석)가 같이 쓴다.
// ⑤ 사용자 판단 = '미기록' 또는 '<이름>(직접 고름)' · [기록 열기]는 기록이 있을 때만 보이고 그 기록 id 를 넘긴 뒤
// (lib/detailNav · 한 번 넘김) 「AI 투자 세션」으로 간다 → 그 기록 상세를 바로 엶.

import {
  WEEKLY_REVIEW_SOURCE,
  type WeeklyAi,
  type WeeklyCell,
  type WeeklyCompareResult,
  type WeeklyLastRecord,
  type WeeklyLatestState,
} from "@/lib/api/weeklyReview";
import { kstDateTimeLabel, verdictText } from "@/lib/aiSessionsDraft";
import { presetOpenRecord } from "@/lib/detailNav";
import { md } from "@/lib/weeklyReview";

const AIS: [WeeklyAi, string][] = [
  ["gpt", "GPT"],
  ["gemini", "Gemini"],
  ["claude", "Claude"],
];
const LATEST_PILL: Record<WeeklyLatestState, string> = {
  같음: "wr-pill",
  "새 값 있음": "wr-pill wr-pill-wait",
  "확인 불가": "wr-pill",
  "형식 없음": "wr-pill wr-pill-wait",
};

function Cell({ c }: { c: WeeklyCell }) {
  if (c.status === "no_answer") return <span className="tc-muted">답 없음</span>;
  if (c.status === "needs_check")
    return (
      <span className="wr-check-need">
        요약 확인 필요<div className="tc-muted tc-small">{c.reason}</div>
      </span>
    );
  return (
    <>
      <div>
        {c.state}
        {c.cited && c.cited.length ? ` · 근거 ${c.cited.join(", ")}` : ""}
      </div>
      <div className="tc-small">
        이유: {c.why ?? "미기재"} · 다음 확인: {c.next_check ?? "미기재"}
      </div>
    </>
  );
}

// 답마다 최신 확인(같음 · 새 값 있음 · 확인 불가 · 형식 없음) + AI 가 적은 확인 항목 줄(확인 시각이 비면 '확인 시각 미기재').
function Latest({ cmp }: { cmp: WeeklyCompareResult }) {
  const answers = cmp.answers;
  if (!answers) return null;
  const answered = AIS.filter(([k]) => answers[k]?.status === "ok");
  return (
    <div className="wk-ai-latest" data-testid="wr-ai-latest">
      <div>
        최신 확인:{" "}
        {answered.length
          ? answered.map(([k, label], i) => {
              const a = answers[k];
              if (a.status !== "ok") return null;
              return (
                <span key={k}>
                  {i ? " · " : ""}
                  {label} <span className={LATEST_PILL[a.latest.state] ?? "wr-pill"}>{a.latest.state}</span>
                  {a.latest.reason ? <span className="tc-muted tc-small">({a.latest.reason})</span> : null}
                </span>
              );
            })
          : "AI 답 없음"}
        {cmp.opinion_text && answered.length ? <span className="tc-muted tc-small"> · {cmp.opinion_text}</span> : null}
      </div>
      {answered.flatMap(([k, label]) => {
        const a = answers[k];
        if (a.status !== "ok") return [];
        return a.items.map((it, i) => (
          <div key={`${k}-${i}`} className="tc-small" data-testid="wr-ai-item">
            {label} — 항목 {it.item} · 값 {it.value ?? "-"} · 기준일 {it.basis_date ?? "-"} · 출처 {it.source ?? "-"} · 확인 시각{" "}
            {it.checked_at ?? <span className="wr-pill wr-pill-wait">{it.checked_at_text}</span>} · 달라지는 해석{" "}
            {it.changes ?? "-"}
          </div>
        ));
      })}
      <div className="tc-muted tc-small">확인 시각 = AI 가 답에 적은 시각(기록 저장 시각과 따로)</div>
    </div>
  );
}

// 답 해석 한 벌(서버 `weekly_review_answers.compare` 모양) — 최신 확인 · 확인 항목 → 대조 표(형식을 못 읽으면 안내).
// 대조 표 열 = 답이 있는 AI(답이 하나도 없으면 셋 모두) · 칸 = 상태 · 인용 근거 · 이유 · 다음 확인.
export function WeeklyAnswers({ cmp }: { cmp: WeeklyCompareResult }) {
  const answered = cmp.answers ? AIS.filter(([k]) => cmp.answers?.[k]?.status === "ok") : [];
  const cols = answered.length ? answered : AIS;
  return (
    <>
      <Latest cmp={cmp} />
      {cmp.status !== "ok" ? (
        <div className="wr-warn">{cmp.message ?? "요약 확인 필요"}</div>
      ) : (
        <div className="wr-table-wrap">
          <table className="wr-table">
            <thead>
              <tr>
                <th>ETF</th>
                {cols.map(([k, label]) => (
                  <th key={k}>{label}</th>
                ))}
                <th>대조</th>
              </tr>
            </thead>
            <tbody>
              {cmp.rows.map((r) => (
                <tr key={r.ticker} data-ticker={r.ticker}>
                  <td>
                    {r.ticker}
                    {r.name ? <div className="tc-small">{r.name}</div> : null}
                  </td>
                  {cols.map(([k]) => (
                    <td key={k}>
                      <Cell c={r.cells[k]} />
                    </td>
                  ))}
                  <td>
                    <div className={r.state_same === false ? "wr-diff" : r.state_same ? "wr-same" : "tc-muted"}>
                      {r.state_text}
                    </div>
                    {r.cited_text ? (
                      <div className={`tc-small ${r.cited_same ? "wr-same" : "wr-diff"}`}>{r.cited_text}</div>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function Missing() {
  return <span className="wr-pill wr-pill-wait">미기록</span>;
}

// 저장한 고른 후보 — 칸이 없는 기록은 '기록 없음'(고르지 않음과 구별 · 지금 값으로 채우지 않음).
function pickedText(last: WeeklyLastRecord): string {
  const sel = last.selected;
  if (sel?.status === "ok") return `고른 후보 ${sel.ticker}${sel.name ? ` ${sel.name}` : ""}`;
  return sel?.status === "none" ? "고른 후보 없음" : "고른 후보 기록 없음";
}

function answerCountText(last: WeeklyLastRecord): string {
  const n = last.answer_count ?? last.compare?.answer_count;
  return typeof n === "number" ? `AI 답 ${n}개` : "AI 답 수 확인 불가";
}

// onOpen = 「AI 투자 세션」으로 이동(부르는 쪽). 이동 전에 기록 id 를 넘긴다 — id 가 없으면(기록 없음 · 읽기 실패) 버튼 없음.
export function WeeklyLast({ last, onOpen }: { last: WeeklyLastRecord; onOpen: () => void }) {
  const id = last.status === "ok" && last.id ? last.id : null;
  return (
    <div className="wr-sec" data-testid="wr-last">
      <div>
        <span className="wr-sec-title">⑤ 최근 검토 기록</span>{" "}
        <span className="tc-muted tc-small">
          이 화면에서 넘겨 저장한 기록 중 가장 최근 1건 · 다른 화면 기록은 「AI 투자 세션」에서
        </span>
      </div>
      {last.status === "ok" ? (
        <>
          <div data-testid="wr-last-line">
            저장 {kstDateTimeLabel(last.saved_at ?? "")} · 원자료 기준일 {md(last.asof)} · {pickedText(last)} · 사용자 판단{" "}
            <b>{verdictText(WEEKLY_REVIEW_SOURCE, last.verdict)}</b> · {answerCountText(last)}
          </div>
          <div>이유(메모) {last.memo ? <span>{last.memo}</span> : <Missing />}</div>
          <div>
            다음 확인 {last.next_checks && last.next_checks.length ? <span>{last.next_checks.join(" · ")}</span> : <Missing />}
          </div>
          <div className="tc-muted tc-small">
            새 주간 기록은 판단 &apos;미기록&apos;에서 시작하고 그대로 저장할 수 있습니다 · 직접 고른 &apos;보류&apos;는 메모 ·
            다음 확인이 비어도 유효 · 실제 편입 여부는 이 자료로 알 수 없습니다
          </div>
        </>
      ) : (
        <div>
          <span className={last.status === "error" ? "wr-warn" : "wr-pill wr-pill-wait"}>{last.message}</span>
        </div>
      )}
      {id ? (
        <div>
          <button
            type="button"
            className="btn-md tc-fold-btn"
            onClick={() => {
              presetOpenRecord(id);
              onOpen();
            }}
          >
            기록 열기 → AI 투자 세션
          </button>{" "}
          <span className="tc-muted tc-small">그 기록 상세를 바로 엽니다</span>
        </div>
      ) : null}
    </div>
  );
}
