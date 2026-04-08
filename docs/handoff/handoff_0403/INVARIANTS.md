# INVARIANTS

1. **UI-First**: 운영 루프는 PC Cockpit + OCI Operator UI로 완결되어야 한다. (CLI Fallback Only)
2. **Fail-Closed**: LIVE 모드에서의 모든 불일치(Token/ID/Hash)는 **차단**이 원칙이다.
3. **No Plain Token**: 로그에 토큰 평문 노출 금지 (Masking 필수).
4. **No External Side-Effects**: `no_external_send`, `no_broker_call` 등 플래그 준수.
5. **SSOT Supremacy**: 대화 내용이 문서와 충돌하면, **문서(Docs)**가 우선이다.
6. **Immutable Input**: `Export`는 생성 후 불변이며, `Ticket`은 이를 단순 시각화한 것이다.
