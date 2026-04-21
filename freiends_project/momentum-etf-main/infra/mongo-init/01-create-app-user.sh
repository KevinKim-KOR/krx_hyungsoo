#!/bin/bash
# mongodb 컨테이너 최초 기동 시 1회 실행.
# MONGO_INITDB_ROOT_USERNAME/PASSWORD 로 admin 계정이 이미 생성된 상태이며,
# 이 스크립트는 mongosh 인증 없이 admin 권한으로 실행됩니다.
#
# 목적: 앱 전용 유저(readWrite/dbAdmin) 생성 → .env 의
#       MONGO_DB_USER/MONGO_DB_PASSWORD 와 일치시킴.

set -euo pipefail

APP_USER="${MONGO_APP_USER:-}"
APP_PASSWORD="${MONGO_APP_PASSWORD:-}"
APP_DB="${MONGO_APP_DB:-momentum_etf_db}"

if [[ -z "${APP_USER}" || -z "${APP_PASSWORD}" ]]; then
  echo "[mongo-init] MONGO_APP_USER / MONGO_APP_PASSWORD 가 설정되지 않아 앱 유저 생성을 건너뜁니다."
  exit 0
fi

echo "[mongo-init] 앱 유저 생성: user=${APP_USER} db=${APP_DB}"

mongosh --quiet <<EOF
use admin;
const existing = db.getUser("${APP_USER}");
if (existing) {
  print("[mongo-init] 이미 존재합니다: ${APP_USER}");
} else {
  db.createUser({
    user: "${APP_USER}",
    pwd: "${APP_PASSWORD}",
    roles: [
      { role: "readWrite", db: "${APP_DB}" },
      { role: "dbAdmin",   db: "${APP_DB}" }
    ]
  });
  print("[mongo-init] 생성 완료: ${APP_USER}");
}
EOF

echo "[mongo-init] done"
