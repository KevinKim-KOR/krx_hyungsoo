"use client";

// POC6-32 V2 ② ETF 흐름(판정 Q2 (c) · Q3 (a) · PLAN V2 §3-1 W5 · W7 · W9 · §9 I-11) — 같은 기초지수 계열만 한 묶음(묶음 이름 =
// 대표의 공식 지수명 · 단독 = ETF명) · 행 순서 = 대표(묶음에서 가장 높은 순위)의 원래 순위 · 첫 화면 3행 + 나머지 펼치기.
// - 계열로 묶였고 공식 기초지수명이 다른 상품이 섞이면(서버 index_names_differ) 묶음 안 줄마다 그 상품의 공식 기초지수를
//   보인다('같은 공식 기초지수'는 이름이 모두 같을 때만 · PLAN I-6 · I-29 · 검토 BE-5).
// - [고르기] = 그 ETF 를 고른다(단독 행 · 묶음은 아래 줄의 ETF 마다 · ③ 검토 · 복사 · 넘기기가 함께 바뀜 · W7).
// - 고른 표시 = [고르기]와 같은 40px 칸 · 파란 바탕 '✓ 고른 후보' · 그 줄 바탕 · 왼쪽 파란 줄(W9).
// - 기간 다름 = 값 + '기간 다름(실제 시작 → 끝)'(W5 · '확인 불가'로 쓰지 않음) · 자료 부족 = 그 줄 아래 '자료 부족: …'
//   (가격 · 상품 사유 · 서버 글 그대로 · 충분하면 표시 없음 · I-11).
// 묶음 · 설명 · 자료 부족 글은 서버가 만든다.

import { Fragment } from "react";
import type { WeeklyFlow, WeeklyMember } from "@/lib/api/weeklyReview";
import { lackText, memberPeriodText, oneMonthText, ranksText, threeMonthText } from "@/lib/weeklyReview";

type PickProps = { selected: string | null; onPick: (ticker: string) => void; busy: boolean };

function Pick({ m, selected, onPick, busy }: PickProps & { m: WeeklyMember }) {
  if (m.ticker === selected) return <span className="wk-picked-mark">✓ 고른 후보</span>;
  return (
    <button
      type="button"
      className="btn-md tc-fold-btn"
      disabled={busy}
      onClick={() => onPick(m.ticker)}
      aria-label={`${m.name} 고르기`}
    >
      고르기
    </button>
  );
}

function Lack({ lack }: { lack: string[] | undefined }) {
  const t = lackText(lack);
  return t ? (
    <div>
      <span className="wk-lack">{t}</span>
    </div>
  ) : null;
}

function Rows({ flows, ...pick }: PickProps & { flows: WeeklyFlow[] }) {
  return (
    <div className="wr-table-wrap">
      <table className="wr-table">
        <thead>
          <tr>
            <th>흐름</th>
            <th>순위</th>
            <th className="wr-num">1개월</th>
            <th className="wr-num">3개월</th>
            <th>함께 읽을 내용</th>
            <th aria-label="고르기" />
          </tr>
        </thead>
        <tbody>
          {flows.map((f) => {
            if (f.kind === "single") {
              const m = f.members[0];
              const on = m.ticker === pick.selected;
              return (
                <tr key={f.key} className={on ? "wr-picked wk-picked-row" : undefined} data-flow={f.rep} data-ticker={m.ticker}>
                  <td>
                    <div className="wr-flow-title">{f.title}</div>
                    <div className="tc-muted tc-small">
                      {m.ticker} · 단독{m.held ? " · 보유" : ""}
                    </div>
                    <Lack lack={m.lack} />
                  </td>
                  <td className="wr-nowrap">{m.rank}</td>
                  <td className="wr-num">{oneMonthText(f)}</td>
                  <td className="wr-num">{threeMonthText(f)}</td>
                  <td className="tc-small">{f.note}</td>
                  <td>
                    <Pick m={m} {...pick} />
                  </td>
                </tr>
              );
            }
            return (
              <Fragment key={f.key}>
                <tr className="wk-grp-row" data-flow={f.rep}>
                  <td>
                    <div className="wr-flow-title">{f.title}</div>
                    <div className="tc-muted tc-small">{f.members.length}개 상품 · 아래 줄에서 하나를 고름</div>
                  </td>
                  <td className="wr-nowrap">{ranksText(f)}</td>
                  <td className="wr-num">{oneMonthText(f)}</td>
                  <td className="wr-num">{threeMonthText(f)}</td>
                  <td className="tc-small">{f.note}</td>
                  <td />
                </tr>
                {f.members.map((m) => {
                  const on = m.ticker === pick.selected;
                  return (
                    <tr
                      key={m.ticker}
                      className={`wk-mem-row${on ? " wr-picked wk-picked-row" : ""}`}
                      data-member={m.ticker}
                      data-ticker={m.ticker}
                    >
                      <td>
                        <span aria-hidden="true">└ </span>
                        {m.name} <span className="tc-muted tc-small">{m.ticker}</span>
                        {m.held ? <span className="tc-muted tc-small"> · 보유</span> : null}
                        <Lack lack={m.lack} />
                      </td>
                      <td className="wr-nowrap">{m.rank}</td>
                      <td className="wr-num">{memberPeriodText(m, "one_month")}</td>
                      <td className="wr-num">{memberPeriodText(m, "three_month")}</td>
                      <td className="tc-small" data-testid={f.index_names_differ ? "wk-mem-index" : undefined}>
                        {f.index_names_differ ? `공식 기초지수 ${m.index_name ?? "확인 불가"}` : null}
                      </td>
                      <td>
                        <Pick m={m} {...pick} />
                      </td>
                    </tr>
                  );
                })}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function WeeklyFlowTable({
  flows,
  firstRows,
  selected,
  onPick,
  busy,
}: {
  flows: WeeklyFlow[];
  firstRows: number;
  selected: string | null;
  onPick: (ticker: string) => void;
  busy: boolean;
}) {
  const first = flows.slice(0, firstRows);
  const rest = flows.slice(firstRows);
  const pick = { selected, onPick, busy };
  return (
    <div className="wr-sec" data-testid="wr-flows">
      <div>
        <span className="wr-sec-title">② ETF 흐름</span>{" "}
        <span className="tc-muted tc-small">
          순위 = 「후보리스트」 선정 순서 · 같은 기초지수 계열(공식 기초지수명이 같거나 계열 사전으로 확인된 것)만 한
          묶음(대표 = 묶음에서 가장 높은 순위) · 묶음 안 ETF 마다 [고르기]
        </span>
      </div>
      <Rows flows={first} {...pick} />
      {rest.length ? (
        <details className="wr-rest">
          <summary>
            나머지 흐름 펼치기 · {rest.length}행 · {ranksText(rest[0]).split(" · ")[0]}위부터 원래 순위
          </summary>
          <Rows flows={rest} {...pick} />
        </details>
      ) : null}
      <div className="tc-muted tc-small">
        지수가 다른 후보끼리의 구성 겹침은 「후보리스트」 [이 목록을 ETF 구성종목에서 보기]에서 봅니다.
      </div>
    </div>
  );
}
