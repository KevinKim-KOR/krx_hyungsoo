# 서버 인프라 정보

## 접속 정보

| 항목 | 값 |
|------|-----|
| IP | ***.***.***.** |
| OS 사용자 | ubuntu |
| SSH 키 경로 | {SSH 키 파일 경로} |
| 도메인 | etf.dojason.com |

```bash
ssh -i {SSH 키 파일 경로} ubuntu@***.***.***.**
```

---

## Docker 컨테이너 구성

| 컨테이너명 | 이미지 | 역할 |
|------------|--------|------|
| momentum-etf-app-1 | momentum-etf-app | Node 웹 앱 (포트 80) |
| momentum-etf-fastapi_app-1 | momentum-etf-fastapi_app | 내부 FastAPI 백엔드 (포트 8000, 외부 미공개) |
| nginx-proxy | nginxproxy/nginx-proxy | 리버스 프록시 (80, 443) |
| nginx-proxy-acme | nginxproxy/acme-companion | SSL 인증서 자동 갱신 |

---

## nginx-proxy 구성

### vhost.d 경로

nginx-proxy는 도메인별 커스텀 nginx 설정을 `/etc/nginx/vhost.d/` 에서 읽는다.
호스트 경로(bind mount)는 다음과 같다:

```
/home/ubuntu/apps/nginx-proxy/vhost.d/
```

### 파일 종류

| 파일명 | 적용 위치 | 용도 |
|--------|-----------|------|
| `{domain}` | server 블록 내부 (location 블록 밖) | 새 location 블록 추가 등 서버 레벨 설정 |
| `{domain}_location` | `location /` 블록 내부 | 기본 proxy location 내 추가 설정 |
| `{domain}_location_override` | `location /` 블록 전체 대체 | proxy location 완전 교체 |

### 설정 변경 절차

1. `/home/ubuntu/apps/nginx-proxy/vhost.d/{파일}` 생성 또는 수정
2. nginx-proxy 재시작으로 템플릿 재렌더링 (단순 reload로는 적용 안 됨)

```bash
docker restart nginx-proxy
```

### 예시: robots.txt 응답 추가

파일: `/home/ubuntu/apps/nginx-proxy/vhost.d/etf.dojason.com`

```nginx
location = /robots.txt {
    return 200 'User-agent: *\nAllow: /\n';
    add_header Content-Type text/plain;
}
```

---

## 앱 배포 구조

- Node 웹 앱이 컨테이너 내부 포트 80으로 실행
- FastAPI 내부 API가 컨테이너 내부 포트 8000으로 실행
- Node 앱이 내부 네트워크에서 FastAPI를 호출
- nginx-proxy가 `etf.dojason.com` 요청을 momentum-etf-app-1 컨테이너로 프록시
- SSL은 acme-companion이 Let's Encrypt 인증서로 자동 처리
