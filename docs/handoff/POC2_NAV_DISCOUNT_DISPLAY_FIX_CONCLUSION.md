# POC2 — NAV / Discount Display FIX CONCLUSION

작성: 2026-06-08
성격: Step 완료 보고. canonical 상태 (`docs/STATE_LATEST.md`) 의 detail 링크.

---

## 0. 한 줄 요약

직전 STEP(Naver ETF Universe NAV / 괴리율 연동) 이 저장은 완료했지만 사용자가
주요 화면에서 NAV 값을 한눈에 확인하기 어려운 표시 누락을 정정. 신규 read-only
API `GET /market/nav-discount/latest` + Data Status 전체 ETF 조회 화면 +
Market Discovery NAV 컬럼 + ETF Exposure / Holdings Evidence 표시 보강.
**표시 매트릭스 (4 화면 × 6 필드) 모두 visible**. 신규 source 0 / 매수·매도
판단 0 / 기존 응답 계약 무변경.

---

## 1. AC 달성 현황

```text
AC-1  Market Discovery NAV 표시 (NAV/시장가/괴리율/asof/source/status)  = DONE (CandidateTable 6 컬럼 직접 노출)
AC-2  ETF Exposure NAV 표시 (placeholder 아닌 실제 값)                 = DONE (NavDiscountPlaceholderCard 컬럼 보강)
AC-3  Holdings Evidence NAV 표시 (asof 포함)                          = DONE (NavDiscountLine asof+status 추가)
AC-4  전체 ETF NAV 조회 + 검색 + status 필터 + 괴리율 정렬             = DONE (Data Status 재설계)
AC-5  저장값 조회 — 조회 시점에 외부 source 호출 X                     = DONE (API 단위 테스트 + 코드 검증)
AC-6  unavailable 처리 — 화면 실패 X                                   = DONE (NAV ok/unavailable/partial 모두 표시)
AC-7  기존 data_quality.nav_discount 계약 무변경                       = DONE
AC-8  기존 흐름 유지 (MD/ETF Exposure/Holdings/Draft/Approval)         = DONE (pytest 395 PASS)
AC-9  범위 위반 0건 (매수/매도/threshold/Telegram/OCI/ML/신규 source) = DONE
AC-10 문서 갱신 (STATE / NEXT_ACTIONS / FEATURE_INVENTORY / FIX Conclusion) = DONE
```

---

## 2. 변경 파일

**Backend 신규 (2)**:
- `app/api_nav_discount.py` — `GET /market/nav-discount/latest` 라우터 + Pydantic 응답.
- `tests/test_api_nav_discount.py` — 4 테스트 (empty / stored items + names / 최신
  per-ticker / 외부 source 미호출 보장).

**Backend 수정 (2)**:
- `app/etf_nav_store.py` — `fetch_all_latest_nav()` 추가 (ticker 별 최신 asof 1건씩).
- `app/api.py` — `nav_discount_router` include 1줄.

**Frontend 신규 (1)**:
- `frontend/lib/api/navDiscount.ts` — `fetchNavDiscountLatest()` + 타입 4종.

**Frontend 수정 (5)**:
- `frontend/lib/api/index.ts` — barrel re-export 1줄.
- `frontend/app/components/DataStatusView.tsx` — 전면 재설계. placeholder → 전체
  ETF NAV 표 + 검색/필터/정렬.
- `frontend/app/components/CandidateTable.tsx` — NAV / 시장가 / 괴리율 / asof /
  source / status 6 컬럼 직접 노출 (2026-06-08 라운드 2 FIX: tooltip → 직접 컬럼).
- `frontend/app/components/NavDiscountPlaceholderCard.tsx` — flag/source 통합
  컬럼 → asof / source / status 분리.
- `frontend/app/components/HoldingsMarketEvidenceCard.tsx` — `NavDiscountLine`
  에 asof / status 추가.

**Docs 수정 (3)**:
- `docs/STATE_LATEST.md` — 최종 업데이트 / Current 상태 / Latest step / Recent
  history / Current evidence flow (Data Status 신규 항목).
- `docs/handoff/POC2_B_NEXT_ACTIONS.md` — §0 NAV Display FIX 결과 추가.
- `docs/handoff/POC2_FEATURE_INVENTORY.md` — §2.13c NAV 데이터 품질 row 갱신.

**Docs 신규 (1)**:
- 본 파일 (`POC2_NAV_DISCOUNT_DISPLAY_FIX_CONCLUSION.md`).

---

## 3. 표시 매트릭스 실측

| Evidence | Market Discovery | ETF Exposure | Holdings Evidence | Data Status (전체 ETF) |
| --- | :--: | :--: | :--: | :--: |
| NAV | ✅ 컬럼 | ✅ 컬럼 | ✅ 라인 | ✅ 컬럼 |
| 시장가격 | ✅ 컬럼 | ✅ 컬럼 | ✅ 라인 | ✅ 컬럼 |
| 괴리율 | ✅ 컬럼 (색상) | ✅ 컬럼 | ✅ 라인 | ✅ 컬럼 (색상 + flag) |
| asof | ✅ 컬럼 | ✅ 컬럼 | ✅ 라인 | ✅ 컬럼 |
| source | ✅ 컬럼 | ✅ 컬럼 | ✅ 라인 | ✅ 컬럼 |
| status | ✅ 컬럼 | ✅ 컬럼 | ✅ 라인 | ✅ status 배지 |

지시문 §5 표시 매트릭스 — 필수 칸 24개 / 누락 0개.

---

## 4. API 동작 실측

```
GET /market/nav-discount/latest →
status=200
summary={'total_count': 1136, 'ok_count': 1136, 'unavailable_count': 0, 'failed_count': 0}
asof=2026-06-08
source=naver_etf_item_list
items[0]={'ticker': '0000D0', 'name': 'TIGER 엔비디아미국채커버드콜밸런스(합성)',
          'nav': 10562.0, 'market_price': 10580.0,
          'discount_rate_pct': 0.17042..., 'flag': null,
          'asof': '2026-06-08', 'source': 'naver_etf_item_list',
          'status': 'ok', 'message': null}
```

- 외부 호출 0건 (테스트로 보장: `_boom` monkeypatch).
- refresh 0건.
- `etf_nav_daily` read-only.

---

## 5. 운영 동작

```
사용자: 좌측 메뉴 Data Status 클릭
  ↓ GET /market/nav-discount/latest (외부 호출 0, fetch_all_latest_nav 1회 SQL)
  ↓ NavDiscountResponse — items 1136건 + summary + asof + source
화면:
  - 조회 옵션 카드: 검색 입력 / status 필터 / 정렬키 / 정렬방향 / 다시 불러오기
  - 상위 200건 표시 (성능 — 검색/필터로 좁히면 정확히 확인)
  - 괴리율 절대값 정렬이 기본 (5% 이상은 danger 색 / 3-5%는 warn 색)

사용자: Market Discovery 진입
  - CandidateTable 6 컬럼 직접 노출: NAV / 시장가 / 괴리율 / asof / source / status
  - 괴리율 색상 (음수 빨강 / 양수 초록), flag 는 괴리율 옆 인라인 (예: discount_check_needed)
  - tooltip 없음 — 모든 필수 메타 (asof / source / status) 가 별도 컬럼으로 표시

사용자: ETF Exposure 진입 (draft 있을 때)
  - NavDiscountPlaceholderCard: 후보 candidates 의 NAV ok/unavailable count + 상위 5건 표
  - 표 컬럼: ETF / NAV / 시장가 / 괴리율(+flag) / asof / source / status

사용자: Holdings 진입
  - HoldingsMarketEvidenceCard 종목 row → NavDiscountLine
  - "NAV 130,551 · 시장가 131,030 · 괴리율 0.37% · asof 2026-06-08 · source: naver_etf_item_list · status: ok"
```

---

## 6. 이번 STEP 에서 의도적으로 하지 않은 것 (지시문 §7)

- Naver source 재진단 / 다른 source 추가 / per-ticker 대량 호출.
- 조회 API 에서 Naver 직접 호출 / refresh 수행.
- 매수 / 매도 / 교체 추천 / 괴리율 기준 투자 정책 / 괴리율 threshold 변경.
- Telegram 문구 변경 / OCI push 연결 / ML / 백테스트 연결.
- 새 Workbench 화면 / Dashboard 대개편 / UI 리디자인.

---

## 7. 검증 결과

- **backend pytest** — PASS (395 passed in 117s, +4 신규 / 회귀 0).
- **black --check** — PASS.
- **flake8** — PASS (0건).
- **frontend ESLint** — PASS.
- **frontend Next.js build** — PASS (4 static pages, TypeScript types check PASS).
- **외부 source 미호출 보장** — 테스트 `test_get_nav_discount_latest_does_not_call_external_source`
  에서 `_boom` monkeypatch 로 확인.
- **API live 실측** — 1136 ETF / 0초대 응답 / `naver_etf_item_list` source 일관.

---

## 8. 다음 분기 후보 (사용자 결정 영역)

표시 매트릭스가 완료되었으므로 다음 분기는 §POC2_B_NEXT_ACTIONS 와 동일:

1. NAV / 괴리율 시계열 누적 활용 (위험 감지 축 2 의 1차 후보).
2. 위험 감지 지표 시계열 적재 1차 (VKOSPI / Fear&Greed / 수급 / 시장 폭).
3. 구성종목 가격 시계열 source 진단.
4. MDD / Sharpe 계산 도입.

본 문서는 다음 STEP 을 임의 확정하지 않는다.
