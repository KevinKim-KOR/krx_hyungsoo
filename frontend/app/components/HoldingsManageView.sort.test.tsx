// POC3-08 종목 관리(입력) 화면 정렬 로직 테스트.
// 핵심: rows·metas 를 index 짝 보존하며 함께 정렬. 빈 행은 뒤로. 편집값 보존.
import { describe, it, expect } from "vitest";
import { sortRowsWithMetas } from "./HoldingsManageView";

// RowDraft / RowMeta 는 내부 타입 — 테스트는 동일 shape 객체로 구성.
function row(
  ticker: string,
  name: string,
  account_group: string,
  quantity = "1",
  avg_buy_price = "100"
) {
  return { ticker, name, quantity, avg_buy_price, account_group };
}
function meta(codeStatus: "ok" | "warn" | "err" | "none" = "none") {
  return { codeStatus, autoName: null };
}

describe("sortRowsWithMetas — 계좌순(기본)", () => {
  it("계좌 그룹을 증권사 순서로 묶는다", () => {
    const rows = [
      row("A", "가", "연금"),
      row("B", "나", "일반"),
      row("C", "다", "오픈뱅킹"),
      row("D", "라", "ISA"),
      row("E", "마", "기타"),
    ];
    const metas = rows.map(() => meta());
    const out = sortRowsWithMetas(rows, metas, "account");
    expect(out.rows.map((r) => r.account_group)).toEqual([
      "일반",
      "ISA",
      "연금",
      "오픈뱅킹",
      "기타",
    ]);
  });

  it("같은 계좌 안은 종목명 가나다순", () => {
    const rows = [
      row("T1", "다종목", "일반"),
      row("T2", "가종목", "일반"),
      row("T3", "나종목", "일반"),
    ];
    const out = sortRowsWithMetas(rows, rows.map(() => meta()), "account");
    expect(out.rows.map((r) => r.name)).toEqual([
      "가종목",
      "나종목",
      "다종목",
    ]);
  });

  it("빈 종목코드 행은 항상 맨 뒤(새 입력 행이 위로 안 튐)", () => {
    const rows = [
      row("", "", "일반"), // 새로 추가한 빈 행
      row("069500", "KODEX 200", "일반"),
    ];
    const out = sortRowsWithMetas(rows, rows.map(() => meta()), "account");
    expect(out.rows[0].ticker).toBe("069500");
    expect(out.rows[1].ticker).toBe("");
  });

  it("빈 account_group 은 '일반' 취급", () => {
    const rows = [row("A", "가", "ISA"), row("X", "엑스", "")];
    const out = sortRowsWithMetas(rows, rows.map(() => meta()), "account");
    expect(out.rows[0].ticker).toBe("X"); // '일반' 이 ISA 보다 앞
  });
});

describe("sortRowsWithMetas — metas 짝 보존", () => {
  it("rows 재배열 시 metas 도 같은 순서로 따라간다", () => {
    const rows = [
      row("069500", "KODEX 200", "일반"),
      row("005930", "삼성전자", "일반"),
    ];
    // 069500 에 warn, 005930 에 err 라고 표시해두고, 종목명순 정렬 후 짝 확인.
    const metas = [meta("warn"), meta("err")];
    const out = sortRowsWithMetas(rows, metas, "name");
    // 종목명순: KODEX 200 < 삼성전자 (ko locale). 순서 유지되므로 meta 도 그대로.
    const idxKodex = out.rows.findIndex((r) => r.ticker === "069500");
    const idxSamsung = out.rows.findIndex((r) => r.ticker === "005930");
    expect(out.metas[idxKodex].codeStatus).toBe("warn");
    expect(out.metas[idxSamsung].codeStatus).toBe("err");
  });
});

describe("sortRowsWithMetas — 종목명순 / 종목코드순", () => {
  it("종목명순은 계좌 무시 전체 가나다", () => {
    const rows = [
      row("T1", "다", "일반"),
      row("T2", "가", "연금"),
      row("T3", "나", "ISA"),
    ];
    const out = sortRowsWithMetas(rows, rows.map(() => meta()), "name");
    expect(out.rows.map((r) => r.name)).toEqual(["가", "나", "다"]);
  });

  it("종목코드순은 ticker 오름차순", () => {
    const rows = [
      row("069500", "케이", "일반"),
      row("000660", "에스", "ISA"),
      row("005930", "삼", "연금"),
    ];
    const out = sortRowsWithMetas(rows, rows.map(() => meta()), "ticker");
    expect(out.rows.map((r) => r.ticker)).toEqual([
      "000660",
      "005930",
      "069500",
    ]);
  });
});

describe("sortRowsWithMetas — 원본 불변", () => {
  it("입력 rows 배열을 변형하지 않는다", () => {
    const rows = [row("B", "나", "일반"), row("A", "가", "일반")];
    const before = rows.map((r) => r.ticker);
    sortRowsWithMetas(rows, rows.map(() => meta()), "name");
    expect(rows.map((r) => r.ticker)).toEqual(before);
  });
});
