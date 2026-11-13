"use client";

// POC6-29 「보유와 후보 비교」 — 기본 비교 · 종목별 근거.
// 보완 R3(PLAN §9-3 · 목업 R3) 의 좌우 카드 · 차이 줄 · 접기 3개를
// 보완 2차 S3(PLAN §10-6 · 목업 S3 · S 판정 Q-S6 · RESULT 재판정 V2 §4)에서 다음 두 곳으로 다시 묶었다.
// - 기본 비교(표 하나): 머리 = 보유 · 후보 이름 · 배지 · 가격 기준(장중 저장은 잠정).
//   한 항목 = 두 종목 값(실제 기간) 한 줄 + 바로 아래 차이 또는 비교하지 않는 이유 한 줄.
//   항목 = 1개월 · 3개월(같은 기간 KODEX 200 대비) · 최근 5구간 · 최근 20구간 · 고점 대비(20저장일 창 · 고점일).
// - 종목별 근거(후보 · 보유 탭 하나): 시장가 · 기준가(NAV) · 괴리율 · 6 · 12개월 · 20구간 KODEX 200 차이 ·
//   하락 판정 · 구성종목 겹침 · 판단 근거 미리보기(화면이 넘긴 카드 그대로) · [AI 세션에서 검토].
// 값 · 날짜 · 사유 문장은 행 상세(DetailNumbers)와 같은 함수 — 자료 없음 · 기간 다름을 0 으로 채우지 않는다.
// 차이 줄은 lib/compareDiff(두 쪽 시작 · 끝일과 확인된 가격 상태가 같을 때만) · 새 계산 · 점수 · 등급 없음.
// 거래량 · 가격 흔들림은 상세 응답에 없어 넣지 않는다(Q-R4 (a)) — 판단 근거 미리보기에서 본다.

import type { ReactNode } from "react";
import type { EndPrice } from "@/lib/api/etfCompare";
import type { DetailPeriod, DetailSameKodex, EtfDetailItem } from "@/lib/api/etfDetail";
import { DIFF_LABEL, diffLine, diffSideOf, type DiffPeriodKey } from "@/lib/compareDiff";
import { md, mdhm, pct } from "@/lib/etfCompare";
import { dd, drawdownText, excessText, navText, periodText, reasonOf } from "./DetailNumbers";
import { directionColor } from "./helpers";

export type CompareRole = "holding" | "candidate";

const ROLE_WORD: Record<CompareRole, string> = { holding: "보유", candidate: "후보" };
const ROLES: CompareRole[] = ["holding", "candidate"];
const ROWS: DiffPeriodKey[] = ["m1", "m3", "w5", "w20", "drawdown"];

// 기본 비교 머리의 한 종목(이름 · 배지 · 상세를 못 읽었을 때의 안내).
export interface CompareHeadInfo {
  name: string | null;
  badge: string | null;
  note: string | null;
}

// 가격 기준 한 줄 — 장중 저장값은 잠정 · 마감 뒤 저장 · 그 밖은 가격 시점 확인 필요(종가라고 단정하지 않음).
export function priceBasisOf(e: EndPrice | null | undefined): { text: string; provisional: boolean } {
  if (!e || !e.date) return { text: "가격 시점 확인 필요", provisional: false };
  if (e.state === "intraday") return { text: `가격 ${e.fetched_at_kst ? mdhm(e.fetched_at_kst) : md(e.date)} 장중 저장`, provisional: true };
  if (e.state === "after_close")
    return { text: `가격 ${md(e.date)} 마감 뒤 저장${e.fetched_at_kst ? `(${mdhm(e.fetched_at_kst)} 저장)` : ""}`, provisional: false };
  return { text: `가격 ${md(e.date)} · 가격 시점 확인 필요`, provisional: false };
}

function won(v: number): string {
  return `${Math.round(v).toLocaleString("ko-KR")}원`;
}

// 기간 수익률 한 칸(행 상세와 같은 문장 · 계산된 값만 색).
function PeriodVal({ p }: { p: DetailPeriod | null | undefined }) {
  if (!p) return <span className="tc-muted">—</span>;
  return <span style={{ color: p.status === "ok" ? directionColor(p.value) : "var(--muted)" }}>{periodText(p)}</span>;
}

function SameKodexLine({ p, s }: { p: DetailPeriod; s: DetailSameKodex }) {
  if (s.status !== "ok")
    return (
      <div className="hcc-when">
        KODEX 200 대비 {s.status === "period_differs" ? "기간 다름" : `값 없음 · ${reasonOf(s.reason)}`}
      </div>
    );
  const when = s.start === p.start && s.end === p.end ? "같은 기간" : `${dd(s.start, s.end)} → ${dd(s.end)}`;
  return (
    <div className="hcc-sub">
      KODEX 200 대비 <b style={{ color: directionColor(s.value) }}>{pct(s.value, "%p")}</b> (KODEX 200 {pct(s.kodex200_return_pct)} · {when})
    </div>
  );
}

// 최근 고점 대비 한 칸 — 계산됨: 20저장일 창 · 값 · 고점일 / 그 밖(기간 다름 · 값 없음): 행 상세와 같은 문장.
function DrawdownVal({ it }: { it: EtfDetailItem }) {
  const d = it.drawdown;
  if (d.status !== "ok") return <div className="hcc-when">{drawdownText(it)}</div>;
  return (
    <>
      <div className="hcc-when">
        20저장일 {dd(d.start, d.end)} → {dd(d.end)}
      </div>
      <div className="hcc-num" style={{ color: directionColor(d.value) }}>
        {pct(d.value)}
      </div>
      <div className="hcc-when">
        고점 {dd(d.peak_date, d.end)}
        {d.peak_close != null ? `(${won(d.peak_close)})` : ""}
      </div>
    </>
  );
}

// 한 종목 · 한 항목 값 칸 — 계산됨: 실제 기간 · 큰 숫자 / 그 밖: '기간 다름 · 실제 …' · '값 없음 · 사유'(0 아님).
function ValueCell({ role, k, item }: { role: CompareRole; k: DiffPeriodKey; item: EtfDetailItem | null }) {
  const id = `hcc-${role}-${k}`;
  if (!item)
    return (
      <td data-testid={id}>
        <span className="tc-muted">—</span>
      </td>
    );
  if (k === "drawdown")
    return (
      <td data-testid={id}>
        <DrawdownVal it={item} />
      </td>
    );
  const p = item[k];
  const s = k === "m1" ? item.same_kodex.one_month : k === "m3" ? item.same_kodex.three_month : null;
  return (
    <td data-testid={id}>
      {p.status === "ok" ? (
        <>
          <div className="hcc-when">
            {dd(p.start, p.end)} → {dd(p.end)}
          </div>
          <div className="hcc-num" style={{ color: directionColor(p.value) }}>
            {pct(p.value)}
          </div>
        </>
      ) : (
        <div className="hcc-when">{periodText(p)}</div>
      )}
      {s ? <SameKodexLine p={p} s={s} /> : null}
    </td>
  );
}

function HeadCell({ role, head, item }: { role: CompareRole; head: CompareHeadInfo; item: EtfDetailItem | null }) {
  const pb = priceBasisOf(item?.end_price);
  const who = ROLE_WORD[role];
  return (
    <th scope="col" data-testid={`hcc-head-${role}`}>
      <div className="hcc-who">
        <span>
          <span className={`tc-sum-badge ${role === "holding" ? "tc-sum-info" : "tc-sum-ok"}`} data-testid={`hcc-badge-${role}`}>
            {head.badge ?? who}
          </span>
        </span>
        <span className="hcc-name" data-testid={`hcc-name-${role}`}>
          {head.name ?? "—"}
        </span>
        <span className="hcc-when" data-testid={`hcc-price-${role}`}>
          {item ? pb.text : (head.note ?? "—")}
          {item && pb.provisional ? (
            <>
              {" "}
              <span className="tc-sum-badge tc-sum-warn">잠정</span>
            </>
          ) : null}
        </span>
        {item && head.note ? <span className="hcc-when">{head.note}</span> : null}
      </div>
    </th>
  );
}

// 기본 비교 — 표 하나(머리 = 두 종목 · 한 항목 = 값 줄 + 차이 줄). 상세를 아직 못 읽었으면 차이 줄 대신 그 사실 한 줄.
export function CompareBasic({
  hold,
  cand,
  holdHead,
  candHead,
  pending,
}: {
  hold: EtfDetailItem | null;
  cand: EtfDetailItem | null;
  holdHead: CompareHeadInfo;
  candHead: CompareHeadInfo;
  pending: string | null;
}) {
  const items: Record<CompareRole, EtfDetailItem | null> = { holding: hold, candidate: cand };
  const heads: Record<CompareRole, CompareHeadInfo> = { holding: holdHead, candidate: candHead };
  return (
    <section className="tc-card hcc-basic" aria-labelledby="hcc-basic-h" data-testid="hcc-basic">
      <h2 id="hcc-basic-h" className="hcc-h2">
        기본 비교 · 같은 기간 성과 · 최근 움직임 · 고점 대비
      </h2>
      <div className="ec-table-wrap">
        <table className="ec-table hcc-table">
          <colgroup>
            <col className="hcc-col-k" />
            <col />
            <col />
          </colgroup>
          <thead>
            <tr>
              <th scope="col">항목</th>
              {ROLES.map((r) => (
                <HeadCell key={r} role={r} head={heads[r]} item={items[r]} />
              ))}
            </tr>
          </thead>
          {ROWS.map((k) => {
            const l = pending ? null : diffLine(k, diffSideOf(hold, k), diffSideOf(cand, k), reasonOf);
            return (
              <tbody key={k} data-testid={`hcc-row-${k}`}>
                <tr className="hcc-val-row">
                  <th scope="row">{DIFF_LABEL[k]}</th>
                  {ROLES.map((r) => (
                    <ValueCell key={r} role={r} k={k} item={items[r]} />
                  ))}
                </tr>
                <tr className="hcc-diff-row">
                  {l ? (
                    <td colSpan={3} data-testid={`hcc-diff-${k}`} data-kind={l.kind}>
                      {l.text}
                    </td>
                  ) : (
                    <td colSpan={3} data-kind="pending">
                      —
                    </td>
                  )}
                </tr>
              </tbody>
            );
          })}
        </table>
      </div>
      {pending ? (
        <div className="tc-muted tc-small" data-testid="hcc-diff-pending">
          {pending}
        </div>
      ) : null}
      <div className="ec-small">
        차이는 두 쪽의 실제 시작일 · 끝일과 가격 상태(장중 · 마감 뒤)가 같을 때만 적습니다. 고점 대비는 두 종목의 20저장일 창(시작
        · 끝일)이 같을 때만 하락폭을 비교합니다. 둘 다 장중 저장값이면 잠정 비교입니다.
      </div>
    </section>
  );
}

// 종목별 근거 — 후보 · 보유 탭 하나(판단 근거 대상과 같은 선택). 아래에 화면이 넘긴 판단 근거 미리보기를 그대로 둔다.
export function CompareEvidence({
  focus,
  onFocus,
  hold,
  cand,
  holdHead,
  candHead,
  holdingDecline,
  holdingExposure,
  candidateExposure,
  children,
}: {
  focus: CompareRole;
  onFocus: (r: CompareRole) => void;
  hold: EtfDetailItem | null;
  cand: EtfDetailItem | null;
  holdHead: CompareHeadInfo;
  candHead: CompareHeadInfo;
  holdingDecline: string;
  holdingExposure: string;
  candidateExposure: string;
  children: ReactNode;
}) {
  const isHolding = focus === "holding";
  const it = isHolding ? hold : cand;
  const head = isHolding ? holdHead : candHead;
  return (
    <section className="tc-card hcc-evidence" aria-labelledby="hcc-ev-h" data-testid="hcc-evidence">
      <div className="hcc-ev-head">
        <h2 id="hcc-ev-h" className="hcc-h2">
          종목별 근거
        </h2>
        <span className="holdings-sort-seg" role="group" aria-label="판단 근거 대상">
          {(["candidate", "holding"] as const).map((k) => (
            <button key={k} type="button" className={focus === k ? "on" : undefined} aria-pressed={focus === k} onClick={() => onFocus(k)}>
              {k === "candidate" ? "후보 판단 근거" : "보유 판단 근거"}
            </button>
          ))}
        </span>
      </div>
      <div className="ec-small" data-testid="hcc-ev-who">
        {ROLE_WORD[focus]} · {head.name ?? "—"}
        {!it && head.note ? ` — ${head.note}` : ""}
      </div>
      <dl className="ec-lines">
        <dt>시장가 · 기준가(NAV) · 괴리율</dt>
        <dd data-testid="hcc-e-nav">{it ? navText(it) : "—"}</dd>
        <dt>6개월</dt>
        <dd data-testid="hcc-e-m6">
          <PeriodVal p={it?.m6} />
        </dd>
        <dt>12개월</dt>
        <dd data-testid="hcc-e-m12">
          <PeriodVal p={it?.m12} />
        </dd>
        <dt>20구간 KODEX 200 차이</dt>
        <dd
          data-testid="hcc-e-excess"
          style={{ color: it && it.excess20.status === "ok" ? directionColor(it.excess20.value_pctp) : undefined }}
        >
          {it ? excessText(it) : "—"}
        </dd>
        <dt>하락 판정(20저장일)</dt>
        <dd data-testid="hcc-e-decline">{isHolding ? holdingDecline : "보유 종목만 판정합니다"}</dd>
        <dt>구성종목 겹침</dt>
        <dd data-testid="hcc-e-cons">{isHolding ? holdingExposure : candidateExposure}</dd>
      </dl>
      <div className="ec-small">거래량 · 가격 흔들림은 아래 판단 근거 미리보기에서 봅니다.</div>
      <div className="hcc-preview" data-testid="hcc-preview">
        {children}
      </div>
    </section>
  );
}
