// POC6-34 L3 — 「장중 급등락 설정」 카드의 판정 기준 표(PLAN V1 O10 · O11 · I-16 · I-17 · I-23).
//
// **늘 펼친다**(후보 유무와 관계없이 · 2026-11-19 형수님 결정 · 2026-09-27 '판정 기준 값은 늘 펼쳐 둔다'
// 지시 그대로). `<details>` 안에 넣지 않는다.
//   - 제목: 후보 없음 'PC에 기록된 적용 기준' · 후보 있음 '승인 시 적용될 기준'.
//   - 세 묶음 아래 4열(항목 · 설정값 · 무엇을 보는지 · 이 값의 뜻)을 기본 화면에 보인다.
//   - 좁은 화면(720px 이하)은 '항목 설정값' 한 줄 + 바로 아래 두 문장(작은 머리 = `data-label`).
//   - 제목은 `h3` 가 아니다 — 이 카드의 `h3` 는 **지금 할 동작** 하나만이라는 계약이 있다
//     (IntradayConfigCard.test.tsx "재시도 문단과 동시에 렌더되지 않는다").
// 문장은 `intradayCriteria.ts` 가 같은 응답 값으로 만든다. 값은 읽기 전용이다 — 입력란을 만들지 않는다.

import {
  buildCriteria,
  CRITERIA_INTRO,
  criteriaFootnote,
  criteriaTitle,
  type PolicyValue,
} from "./intradayCriteria";

type Props = {
  hasCandidate: boolean;
  policyValues: readonly PolicyValue[];
  // 그 버전의 사업군 수(후보가 있으면 후보 · 없으면 활성).
  sectorCount: number;
};

export default function IntradayCriteriaTable({
  hasCandidate,
  policyValues,
  sectorCount,
}: Props) {
  const title = criteriaTitle(hasCandidate);
  const groups = buildCriteria(policyValues, sectorCount);
  return (
    <>
      <p className="tc-small ops-sub">
        <b>{title}</b>
      </p>
      <p className="tc-muted tc-small">{CRITERIA_INTRO}</p>
      <table className="oci-table ops-criteria" aria-label={title}>
        <thead>
          <tr>
            <th scope="col">항목</th>
            <th scope="col">설정값</th>
            <th scope="col">무엇을 보는지</th>
            <th scope="col">이 값의 뜻</th>
          </tr>
        </thead>
        {groups.map((g) => (
          <tbody key={g.title}>
            <tr className="ops-criteria-group">
              <th scope="rowgroup" colSpan={4}>
                {g.title}
              </th>
            </tr>
            {g.rows.map((r) => (
              <tr key={r.key}>
                <td className="oci-table-item">{r.label}</td>
                <td className="ops-criteria-value">{r.value}</td>
                <td data-label="무엇을 보는지">{r.what}</td>
                <td data-label="이 값의 뜻">{r.meaning}</td>
              </tr>
            ))}
          </tbody>
        ))}
      </table>
      <p className="tc-muted tc-small">{criteriaFootnote(policyValues)}</p>
    </>
  );
}
