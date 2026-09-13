"""Low-Frequency Telegram Push Operation v1 — focused test 패키지.

원본 `tests/test_low_frequency_push_operation.py` 가 1548줄로 KS-10 테스트
임계(>1500)를 넘어 책임별로 분해했다. 아래는 **원본 머리말에 적혀 있던 사용자
확정 계약 원문**이다. 파일이 나뉘어도 이 계약이 사라지지 않게 여기 보존한다.

사용자 확정 계약:
- partial(가격 일부 실패 / reeval partial / candidate missing) → 미발송 · registry 미기록
- 혼합 Spike 신호 → body 는 신규 fp 만으로 재조립 (기발송 fp 제외)
- ticker loader 예외 → failed
- reeval 예외 → failed (u_notes 폴백 금지)
- Published Evidence 필수 필드 (trigger_type / direction / threshold / evidence_as_of) 강제
- selection_count 종목당 1
"""
