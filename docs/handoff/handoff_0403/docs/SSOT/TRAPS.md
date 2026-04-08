# TRAPS (Do not repeat)

1. **Zombie Uvicorn**: OCI에 수동으로 띄운 `uvicorn`이 8000 포트를 점유하면 `systemctl restart`가 실패함.
   → 해결: `deploy/oci/restart_backend.sh` 사용 (fuser -k 8000 포함).
2. **Windows Encoding Hell**: CP949로 저장된 파일을 UTF-8로 읽으면 500 에러 발생.
   → 해결: 파일 쓰기 시 `encoding="utf-8"` 명시 필수.
3. **Stale Ticket**: `Ticket.md`는 정적 파일이므로, `Export`가 갱신되어도 구형 토큰을 가질 수 있음.
   → 해결: Operator UI에서 `Regenerate Ticket` 수행 또는 `Draft` 단계에서 최신 `Export` 참조.
4. **Localhost Loopback**: OCI에서 `OCI_BACKEND_URL`을 잘못 설정하면 자기 자신을 호출하다 타임아웃 발생.
   → 해결: `localhost` vs `168...` 구분 명확히 설정.
5. **JSON Parse Error**: `Evidence Viewer`가 Markdown/Log 파일을 JSON으로 파싱하려다 500 에러.
   → 해결: `contract_evidence_ref_v1.md`의 Viewer Rule (Fail-Soft) 준수.
