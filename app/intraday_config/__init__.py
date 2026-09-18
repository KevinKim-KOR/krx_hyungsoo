"""POC3-02C-OPS-01 — 장중 알림 설정 번들 (`INTRADAY_ALERT_CONFIG`).

- `schema`   번들 계약 · 두 해시 분리 · checksum 범위
- `selector` 사업군 자동 분류 · 대표/대체 선정
- `store`    DB version/approval/active · **승인 게이트**

이번 Step 은 **생성·승인·전달까지**다. 장중 조회·판정·발송은 `OPS-02` 다.
최초 번들은 `enabled=false` 로 나간다 — 러너 동작은 바뀌지 않는다.
"""
