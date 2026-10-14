---
name: krx-verify
description: krx_hyungsoo 프로젝트의 개발 결과서와 실제 Git 변경을 대조해 구현을 검증한다. 검증 요청, RESULT 검토, rN 재검증에 사용하며 일반 질문·개발 구현에는 사용하지 않는다.
---

# KRX 구현 검증

이 스킬은 검증 절차와 근거를 관리한다. 자동 검사만으로 기능 통과를 판정하지 않는다.

## 적용 규칙

1. 모든 진행 알림·보고는 한국어로 한다.
2. 저장소의 `AGENTS.md`와 `docs/agent/VERIFY_RULES.md`를 읽고, 해당 단계의 설계서·PLAN·결과서·실제 diff를 대조한다. 사용자 지시는 이 스킬보다 우선한다.
3. 원본 요구·개발 보고·실제 변경 중 하나라도 없으면 `BLOCKED`. 대화형 UI 작업에는 VERIFY_RULES §1-A의 대체 입력을 적용한다.
4. 코드는 검증만 한다. 운영 코드·테스트를 직접 수정하지 않는다. **문서의 수치·줄 수·메타 정보만 틀린 경우 실측 후 직접 정정한다. 그것만으로 REJECTED하지 않는다.** 의미·승인 범위가 달라지는 문서는 임의 정정하지 않는다.
5. `znotes/`, 실제 `.env`, 라이브 `state/`·`logs/`·DB, 사용자 소유 `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`는 명시적 권한 없이 읽거나 수정하지 않는다. 사용자 소유 파일을 stage하지 않는다.

## 검증 시작

저장소 루트에서 실행한다. 기본 세션 식별자는 `CODEX_THREAD_ID`이다. 없는 환경에서는 모든 명령에 같은 `--session-id`를 명시한다.

```bash
python3 .agents/skills/krx-verify/scripts/verify_scope.py begin \
  --input docs/ai_design/POC5/해당_설계서.md \
  --input docs/ai_plan/POC5/해당_PLAN.md \
  --input docs/ai_result/POC5/해당_결과서.md
```

`--input`에는 실제 경로를 넣는다. 도구는 HEAD·index blob·작업 파일 SHA-256·줄 수(`wc -l` 기준)·Git 상태를 저장소 밖 임시 경로에 고정한다. 이름만 조회한 제외 파일과 해시를 읽지 못한 파일을 구분해 출력한다. 비추적 산출물·미해결 병합 충돌·읽기 제외된 추적 파일 변경이 있으면 통과 기록을 막는다. `.env.example`은 공개 설정 예제로만 해시를 확인한다.

## 코드·산출물 대조

- A-1~4, B-1~6, 기반 문서·안전성·범위 폭주를 모두 확인한다. 배포 파일의 Git 추적 상태와 실제 실행 경로도 확인한다.
- 보고서 숫자는 현재 측정값과 대조한다. 테스트 수는 실행 결과를 근거로 쓴다. 소스에서 센 시험 함수 수를 통과 건수로 쓰지 않는다.
- 기존 재현은 수정본에서도 확인한다. 같은 원인의 다른 경로는 필요한 범위에서 살핀다. 이미 확인한 관점을 반복하는 다수 검토는 하지 않는다.
- 시험은 저장소 밖 소스 사본과 임시 상태·DB를 사용한다. `tests/_live_guard.py` 등 기존 격리 장치를 유지한다. 운영 데이터·외부 API·발송·서버 재시작을 시험에 연결하지 않는다.
- 개발자의 전체 회귀 근거와 최종 코드가 일치하면 전체 회귀를 자동 반복하지 않는다. 필요한 재현·관련 시험만 실행하고, 재실행하지 않은 검사와 근거 재사용 범위를 명시한다.
- 켜진 개발 서버가 있는 저장소에서 `npm run build`를 실행하지 않는다. 필요한 build는 저장소 밖 사본에서 한다.

```bash
python3 .agents/skills/krx-verify/scripts/verify_scope.py check
```

소스·HEAD·stage 범위가 바뀌면 이전 검증 근거로 통과하지 않는다. 이는 기준 변경이며 그 자체를 코드 결함으로 단정하지 않는다.

## 보고 직전

VERIFY_RULES의 7섹션 보고서를 작성한다. 결함이 없고 A/B 전체가 통과하면 `VERIFIED`를 사용한다. 문서 수치만 고쳤다면 정정 사실을 보고한다. 사용자의 커밋·push·배포 별도 승인 조건은 그대로 유지한다.

```bash
python3 .agents/skills/krx-verify/scripts/verify_scope.py finish --verdict VERIFIED
```

직접 정정한 문서가 있으면 아래 옵션을 추가한다. 코드 파일은 이 옵션으로 승인할 수 없다.

```bash
python3 .agents/skills/krx-verify/scripts/verify_scope.py finish --verdict VERIFIED \
  --accept-doc docs/ai_result/POC5/해당_결과서.md \
  --doc-reason '줄 수를 실제 측정값으로 정정; 코드·판정 의미 변경 없음'
```

종합 판정은 `종합 판정: VERIFIED`처럼 명시한다. `finish`는 기능을 검증하거나 Git에 stage하지 않는다. 검증자가 내린 판정과 최종 소스 상태만 기록한다.

## 저장소 훅

- `.codex/hooks.json`의 SessionStart는 이 스킬을 안내한다. Stop은 **이 세션에서 검증을 시작했고 통과 판정을 보고하는 경우에만** 근거 기록·최종 소스 일치를 확인한다.
- 훅은 시험·운영 파일 접근·Git 쓰기·네트워크 요청을 실행하지 않는다. 일반 질문과 개발 작업에는 검증 종료 차단을 적용하지 않는다.
- 새 훅은 Codex의 신뢰 확인 후 활성화된다. `/hooks`에서 프로젝트 훅 정의를 확인한다. 기존 전역 훅은 유지한다. [공식 훅 안내](https://learn.chatgpt.com/docs/hooks)
- 훅은 정적 범위 검사다. 기능 결함 탐지·문서 의미 검증·운영 데이터 불변 증명의 대체물이 아니다.
