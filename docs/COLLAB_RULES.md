# COLLAB_RULES.md

작성일: 2026-04-21
대상: 모든 AI + 사용자
참조 시점: PR 작성 시 / 신규 문서 작성 시 / AI 역할 혼동 시

## AI 역할 분담
- 설계: 웹 GPT
- 레드팀: 웹 Gemini
- 조언자: 웹 Claude
- 개발: VSCode Claude
- 검증: VSCode Codex

각 AI의 상세 룰은 docs/agents/ 하위 별도 파일 참조.

## 개발 워크플로우
- 1 PR = 1 기능
- PR 설명에 KILL_SWITCHES 중 해당 없음 체크
- ASSUMPTIONS의 Open Question과 연결된 기능이면 명시
- VSCode Claude 개발 → Codex 검증 → 통과 시 커밋

## 문서 관리
- 신규 문서 생성 시 기존 문서 1개 검토 (중복 방지)
- docs/ 루트 파일 수 10개 초과 시 재평가
- 모든 문서는 1페이지 원칙 (불가피한 경우만 예외)