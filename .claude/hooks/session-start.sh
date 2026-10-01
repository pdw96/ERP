#!/bin/bash
# 클라우드 세션(Claude Code on the web)이 시작될 때 「로컬에서 도는 검사」를 돌릴 수 있게 세운다.
# 무엇을 돌리는지는 `CLAUDE.md` 「로컬에서 도는 검사」가 든다 — 여기는 그 검사가 기대는 바탕만 세운다.
#
# **떠 있어야 하는 것(PostgreSQL · dockerd)을 여기서 띄운다.** 환경의 setup script 는 컨테이너를
# 만들 때 한 번 돌고, 세션 도중 컨테이너가 다시 시작되면 띄워 둔 프로세스가 사라진다(실제로
# PostgreSQL 이 한 번 꺼졌다). 이 훅은 재개 때도 다시 돈다. 모든 걸음은 다시 돌려도 같다.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR/backend"

# 파이썬 — CI 와 같은 잠금에서 해시까지 맞춰 깐다(`backend/requirements.in` 머리)
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q --disable-pip-version-check --require-hashes -r requirements-dev.txt

# 셸 검사 — CI 의 「셸」 스텝이 쓴다
if ! command -v shellcheck >/dev/null; then
  apt-get install -y -q shellcheck >/dev/null
fi

# PostgreSQL 16 — 테스트는 실제 DB 에 붙는다. 없으면 건너뛰지 않고 실패한다(`CLAUDE.md`)
if ! pg_isready -q -h 127.0.0.1 -p 5432; then
  pg_ctlcluster 16 main start
fi
for _ in $(seq 1 30); do
  pg_isready -q -h 127.0.0.1 -p 5432 && break
  sleep 1
done
su postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname = 'erp'\"" | grep -q 1 \
  || su postgres -c "psql -qc \"CREATE ROLE erp LOGIN PASSWORD 'erp' SUPERUSER\""
su postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname = 'erp_test'\"" | grep -q 1 \
  || su postgres -c "psql -qc 'CREATE DATABASE erp_test OWNER erp'"

if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo 'export ERP_TEST_DATABASE_URL="postgresql+psycopg://erp:erp@127.0.0.1:5432/erp_test"' >> "$CLAUDE_ENV_FILE"
fi

# Docker — 이미지 빌드 · 기동 · 되돌림 실측이 쓴다. 바이너리는 있고 데몬만 떠 있지 않다
if command -v dockerd >/dev/null && ! docker info >/dev/null 2>&1; then
  nohup dockerd >/tmp/dockerd.log 2>&1 &
  for _ in $(seq 1 30); do
    docker info >/dev/null 2>&1 && break
    sleep 1
  done
fi
