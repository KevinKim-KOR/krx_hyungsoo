# POC3-02C-OPS-02 종료 · 다음 챕터 진입 — 2026-09-21

- **작성**: 개발자(VSCode Claude) · **독자**: 다음 세션 개발자
- **상태**: 검증자 `VERIFIED` · 커밋·푸시 완료 · **활성화는 불가**
- **2026-09-22 정정**: OCI 는 **자동 배포가 아니다** — 수동 `git pull` 이다
  (실측: user crontab 에 git 항목 0건 · 관련 systemd timer 0건). 초판의
  "자동 배포" 는 사용자가 곧바로 pull 한 것을 잘못 읽은 것이다.
- **2026-09-22 후속**: `OPS-03` 으로 활성화 경로가 생겼고, 사용자가
  2026-09-21 23:48 KST 승인해 **장중 알림이 운영 중**이다.

```text
기능          구현·검증·배포 완료
정책          enabled=false · policy_status=NOT_CONFIGURED
켤 수 있나    아니오 — 켜는 경로가 소스에 없다 (DEF-INTRADAY-POLICY-ACTIVATION-PATH)
다음 차례     설계자 (임계값 12개 + 투입 경로 결정)
```

배포 확인은 SHA 를 문서에 적지 않고 명령으로 한다 — 커밋할 때마다 낡는다.

```bash
git log --oneline -1
ssh oci-krx "cd /home/ubuntu/krx_hyungsoo && git log --oneline -1"
```

두 값이 다르면 **OCI 가 옛 코드로 돈다.** 푸시했다고 배포된 것이 아니다.

---

## 1. 이 챕터에서 만든 것

기존 `holdings_risk_alert` 7틱(09:30·10:30·11:30·12:30·13:30·14:30·15:20)에
**사업군 대표 ETF 판정**과 **보유 급등**을 얹어 「장중 급등락」 통합 본문을
만든다. 신규 push_kind 0 · 신규 cron 0 — 기존 종류에 올라탄다.

| 구역 | 내용 |
|---|---|
| 보유종목 | 보유 급락 + 보유 급등 (합쳐서 최대 3) |
| 진입 회피 | 사업군 급락 + 추격 주의 (합쳐서 최대 3) |
| 신규 진입 검토 | 사업군 진입 후보 (최대 3) |

한 메시지 최대 9종목. 잘린 것은 `dropped` 이력에만 남고 **발송으로 치지 않는다**.

15:40 보유 브리핑 말미에 그날 회차 집계가 한 줄 붙는다.

### 신규 모듈 5개

```text
408  app/runtime_evidence/sector_signal.py          사업군 판정(§4-2 표) · 커버리지 Gate · provider 장애 구분
325  app/runtime_evidence/sector_signal_state.py    억제·cooldown · 관측 3상태 저장
468  app/runtime_evidence/intraday_alert_flow.py    회차 조립 · 대체 조회 · 구역/일일 상한
281  app/runtime_evidence/intraday_alert_render.py  본문 · 15:40 요약 한 줄
178  app/runtime_evidence/intraday_checkup_tally.py 회차 집계 (발송 상태와 별개 파일)
```

커밋 1건에 26개 파일(신규 13 · 수정 13). 테스트 41+34+23+37+53 = 188건 신규.

---

## 2. 반드시 알아야 할 계약 3개

이 셋을 모르면 다음 수정에서 같은 함정에 빠진다. **검증 9라운드가 전부 이 셋의
조합에서 났다.**

### 2-1. 관측 상태 ≠ 발송 진척 (설계서 §15-2)

한 파일(`sector_signal_state_latest.json`) 안에서 **필드와 저장 시점이 다르다.**

| 구분 | 필드 | 언제 쓰나 |
|---|---|---|
| 관측 상태 | `state` · `continuous` · `sector_key` · `day_return_pct` | 운영 Gate 통과 **매 회차** |
| 발송 진척 | `last_sent_at` · `sent_today` | **전체 전송 성공 시에만** 전진 |

- `fingerprint` 는 **저장 필드가 아니다.** `ticker#state` 파생값이고,
  `holdings_risk_alert` 의 registry 중복키는 실행 시각 `HH:MM` 이다.
- 파일이나 `sent_today` 키의 **존재는 발송 성공의 증거가 아니다.**
  `sent_today` 는 0 으로 존재할 수 있다(카운터 초기값).
- 계약은 "저장 여부" 가 아니라 **"전진 여부"** 로 말한다.

### 2-2. 관측은 3상태다 — 모르는 것을 회복으로 적지 않는다

```text
SIGNAL_PRESENT   조건 충족          → continuous=true
SIGNAL_ABSENT    정상 평가 후 미충족 → continuous=false
UNEVALUABLE      평가 불가          → 기존 값 전부 유지
```

평가 불가는 provider 장애 · 커버리지 미달 · 사업군 예외(`held`) · 시세 없음이다.
이걸 회복으로 적으면 지속 신호가 cooldown 뒤 **재발송**된다.

보존은 **`sector_key` 단위**다. 직전 회차가 대체 ETF 로 저장됐다면 이번 회차의
대표 ticker 와 달라서, ticker 로만 잡으면 빠진다.

범위를 분리한다 — 사업군이 통째로 무너져도 **정상 평가된 보유 급등은 갱신**한다.

### 2-3. 라이브 파일은 운영 Gate 통과 회차만 쓴다

```text
mode = send  AND  정책 enabled  AND  PUSH_AUTOSEND_HOLDINGS_RISK_ALERT_ENABLED  AND  duplicate 아님
```

조립은 **쓰지 않고 의도만 담는다**(`RiskAssembly.intraday_records`).
러너 `_finish()` 한 곳에서 `apply_intraday_records()` 가 실제로 쓴다.
모든 종료 지점이 `_finish` 를 지나므로 분기마다 호출을 넣지 않아도 된다.

pending 은 `record[PENDING_KEY]` 로 실어 보내고 **직렬화 전에 꺼내 지운다** —
경로·set 이 섞여 있어 history JSONL 로 나가면 안 된다.

> `dry-run` 만 돌려도 라이브 파일이 바뀌면 안 된다. duplicate 회차를 세면
> 15:40 의 "장중 점검 N회" 가 같은 틱을 두 번 센다.

---

## 3. 지금 실제로 바뀐 동작 2건 (`enabled=false` 인데도)

배포됐으니 다음 거래일부터 보인다. **정책과 무관하다.**

1. **보유 급락·급등 판정 분모가 바뀌었다.** 조정계열 역산이 아니라 Naver
   무조정 D-1 등락률(`fluctuationsRatio`)을 그대로 쓴다. 등락률을 못 구하면
   그 종목은 선정에서 빠지고 `데이터 확인 대상` 으로 간다.
   배포 전 24거래일 재생에서 **급락 판정 변경 0건**.

2. **15:40 보유 브리핑 말미에 `장중 점검 확인 불가` 가 붙는다.**
   부착 조건이 `슬롯 == CLOSE and 본문 있음` 뿐이라 정책으로 막히지 않는다.
   집계 파일이 없으므로 이 문구가 나간다. → §5 결함 2.

---

## 4. 재사용할 것 · 건드리지 말 것

**재사용**

- `usable_day_return(quote, today_kst)` — 판정에 쓸 수 있는 무조정 D-1 등락률.
  `0.0` 은 유효한 보합이다. 여기서 걸러지면 하락·보합이 통째로 사라진다.
- `compute_sector_changes()` — 억제 판정. `last_sent_at` 이 없으면 나머지와
  무관하게 **발송**이다(보낸 적 없으면 억제할 근거가 없다).
- `build_section_plan()` — 구역 **단위** 상한. 하위 유형마다 따로 적용하면
  한 메시지 최대가 9 가 아니라 15 가 된다.

**건드리지 말 것**

- 러너 `scripts/run_three_push_runtime_oci.py` — **646줄, KS-10 동결선 648.**
  줄이 늘어야 하면 기존 줄 교체로 해결하고, 넘으면 **중단·보고**.
- `FORBIDDEN_PHRASES` — 면책 문구가 `"매도 지시"` 에 부분일치로 걸린 적이
  있다. 가드를 약화시키지 말고 문구를 바꾼다(설계자 §15-1 확정).
- `holdings_risk_state` — 보유 **급락** 억제는 여전히 이쪽이다. 장중 상태
  파일과 별개다.

---

## 5. 열린 결함 2건 — **둘 다 설계자 차례**

### 결함 1 · `DEF-INTRADAY-POLICY-ACTIVATION-PATH` (활성화 차단)

정책을 켤 경로가 소스에 없다. 실측:

```text
generator.py 가 build_payload() 에 policy= 를 넘기지 않는다
  → 항상 {"enabled": False, "policy_status": "NOT_CONFIGURED"}
policy= 를 넘기는 호출처       저장소 전체 0건
API                            GET /state · POST /approve-and-apply · POST /reject
                               쓰기 2개는 사업군 목록만 승인·거부한다
화면 카드의 `알림 상태`        표시 전용 — 승인해도 enabled 는 false
```

`enabled=true` 로 만들려면 아래 12개를 모두 채우고 범위 검사를 통과해야 한다
(`schema.py :: validate`). 괄호는 `INITIAL_POLICY_VALUES` 기본값이다.

```text
sector_min_coverage_pct  (80.0)   [0, 100]      sector_rank_top_pct    (20.0)  [0, 100]
sector_entry_min_pct      (1.5)   [-100, 100]   sector_chase_pct        (4.0)  [-100, 100]
sector_avoid_drop_pct    (-1.5)   [-100, 100]   surge_threshold_pct     (5.0)  [0, 100]
drop_threshold_pct       (-5.0)   [-100, 0]     cooldown_minutes        (120)  [0, 1440]
dedup_window_minutes      (120)   [0, 1440]     max_sends_per_run         (1)  [1, 10]
max_sends_per_day           (4)   [1, 50]       max_items_per_section     (3)  [1, 20]
```

**설계자가 정할 것**: 값과 **투입 경로**(화면 입력 / 시드 스크립트 / PARAM).
개발자가 임의로 정하지 않았다 — 임계값이 곧 발송량이다.

### 결함 2 · `DEF-INTRADAY-SUMMARY-WHEN-DISABLED`

§3-2 의 그 줄이다. "기능이 꺼짐" 과 "켜져 있는데 집계를 못 읽음" 을 같은
문구로 말한다. 비활성이면 줄을 아예 빼는 것이 맞는지 설계자 확인 필요.

---

## 6. 사용자 확인 대기 2건

1. **메시지 형식** — 결과서 §7 목업. 설계 §10-6 이 지정한 확인 대상인데 아직
   못 받았다.
2. **발송량** — 조건형 최대 4건이 기존 고정 4건에 **더해진다.** 하루 최대 8건.

---

## 7. 이번 Step 에서 배운 것 (반복하지 말 것)

검증자 반려가 9라운드 났다. **사유가 매번 "방금 고친 것의 옆칸"** 이었다.

1. **층(layer)만 열거하면 놓친다.** 결함은 다른 차원에 있었다 — **상태**(버전이
   여럿일 때), **순서**(N행 위에서 이미 무슨 일이 일어났나), **조합**(분기 A ×
   분기 B). 파일·모듈은 잘 훑었는데 그게 아니었다.
2. **상태 계약을 고치면 상태 × 전이 표를 먼저 그린다.** 셀이 비면 그게
   미검증이다. 억제 계약을 7셀 표로 전수 고정했더니, 판정 순서를 되돌렸을 때
   **2셀만 실패**했다 — 나머지 5셀은 옛 코드에서도 통과했다. 셀 단위 테스트만
   썼으면 못 잡았다.
3. **한 함수에 인자를 추가하면 호출부를 전부 센다.** `merge_sector_entries()` 에
   `unevaluable` 을 열어 두고 호출부 한 곳을 빠뜨려 P1 이 났다.
4. **"X 하지 않는다" 주장은 실행 순서를 위에서부터 읽어** 첫 X 지점을 찾는다.
   함수 이름이 아니라 줄 순서를 본다.
5. **테스트는 diff 가 아니라 계약 문장에서 쓴다.** 고친 뒤 "이제 된다" 를 쓰면
   그 테스트는 내가 이미 아는 버그만 잡는다.
6. **무력화 실증을 반드시 한다.** 고친 줄을 되돌려 실제로 실패하는지 본다.
   이번에 22종을 실증했고, 그 과정에서 **내 테스트 기대가 틀린 것을 2번** 잡았다.
7. **"계약 공백" 과 "동작 결함" 을 혼동하지 말 것.** 계약에 정의가 없어도
   동작은 이미 틀려 있을 수 있다. 정의가 없다는 이유로 판정을 미루지 않는다.
8. **문서에 자기참조 값을 적지 않는다.** "현재 HEAD = `<SHA>`" · 커밋 수 ·
   그 문서 자신의 줄 수는 커밋하는 순간 낡는다. 경로와 확인 명령을 적는다.

---

## 8. 다음 사람이 바로 할 일

```text
1. 설계자 회신 대기 — 결함 2건(§5). 임계값 12개 + 투입 경로가 정해져야 움직인다.
2. 정해지면 정책 생성 경로 구현 + 관통 테스트.
3. 활성화 후: PROGRAM_TRUTH 프로세스 C 와 STATE_LATEST 를 "발송 중" 으로 갱신.
   지금은 enabled=false 라 "지금 실제 동작" 이 아직 안 바뀌었다고 적어 뒀다.
4. 사용자 확인 2건(§6)을 활성화 전에 받는다.
```

착수 전 `docs/PROGRAM_TRUTH.md` 프로세스 C 와 §13-7 을 읽는다 — 배포 후 실제
동작과 활성화 경로 부재가 거기 있다.

---

## 9. 문서

| 문서 | 경로 |
|---|---|
| 설계서 (상태 저장 계약 **정본 = §15-2**) | `docs/ai_design/POC3/POC3-02C-OPS-02_INTRADAY_SURGE_DROP_ALERT_DESIGN_V1.md` |
| 개발 PLAN | `docs/ai_plan/POC3/POC3-02C-OPS-02_INTRADAY_SURGE_DROP_ALERT_PLAN_V1.md` |
| 결과서 (목업 §7 · D2/D3 §23 · 교차 결함 §24) | `docs/ai_result/POC3/POC3-02C-OPS-02_INTRADAY_SURGE_DROP_ALERT_RESULT.md` |
| 직전 챕터 종료 | `docs/handoff/POC3-02C-OPS-01_CLOSEOUT_2026-09-18.md` |
| 지금 실제 동작 | `docs/PROGRAM_TRUTH.md` 프로세스 C · §13-7 · 부록 A |
| 상태 앵커 | `docs/STATE_LATEST.md` |

---

## 10. 검증 실적 (2026-09-21 실측)

```text
전체 회귀      1,904 passed / 0 failed
신규 계약       188 passed  (사업군 41 · 본문 34 · 통합 23 · 가격기준 37 · 관통 53)
관통 53건       전부 실제 run() 경로
무력화 실증     22종 — 전부 "되돌리면 실패" 확인
black           361 files unchanged
flake8          0건
러너            646줄 (KS-10 동결선 648 이하)
KS-10           전수 484 · TRIGGER 0 · NEAR 7
라이브 DB       회귀 전후 sha256 동일
Telegram / OCI 쓰기 / 발송   0 / 0 / 0
```

재현:

```bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m pytest tests/test_intraday_alert_flow_through.py -q
.venv/bin/black --check app/ tests/ scripts/ && .venv/bin/flake8 app/ tests/ scripts/
wc -l scripts/run_three_push_runtime_oci.py
```
