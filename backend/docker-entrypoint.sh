#!/usr/bin/env bash
# 기동 절차 — 시드 판단 세 조건이 여기 있다.
#
#   ① 표를 먼저 맞춘다 — 마이그레이션을 끝까지 돌린다. 판단이 아니라 전제다.
#   ② 스위치가 켜져 있어야 한다 — 운영에서 자동 시드는 사고이지 편의가 아니다.
#   ③ 품목 표가 비어 있어야 한다 — 물어야 할 것은 표의 유무가 아니라 내용의 유무다.
#
# 「DB 파일이 없으면」으로 판단하지 않는다. PostgreSQL 에는 그 파일이 없다.
#
# **상주하는 `api` 도 이 스크립트로 뜬다 — 그래서 코드만 되돌릴 수 없다.**
# 되돌린 이미지의 `versions/` 에는 DB 가 들고 있는 리비전이 없으므로 아래
# `alembic upgrade head` 가 `ResolutionError` 로 죽고, 나오는 말은 해시 하나다.
# 그때 DB 를 먼저 내리는 길도 좁다 — `08d406fa7f3b` 의 가드가 로트가 한 건이라도
# 있으면 멈춘다. **되돌릴 수 있는 창이 「로트가 0건일 때」로 좁혀져 있다**
# (감사 ⑬ NC-146). 배포처가 서는 날 이 창을 넓히는 것은 마이그레이션을 이
# 스크립트에서 떼어 `migrate` 잡에만 두는 것이고, 순서는 compose 의
# `service_completed_successfully` 가 이미 보증한다.
set -euo pipefail

echo "[1/2] 마이그레이션"
alembic upgrade head

echo "[2/2] 시드"
if [ "${ERP_SEED_ENABLED:-false}" != "true" ]; then
  echo "  건너뜀 — ERP_SEED_ENABLED 가 꺼져 있다"
else
  # 조건 ③(품목 표가 비어 있는가)은 시드 모듈이 본다 — 표를 아는 쪽이
  # 판단해야 셸이 스키마를 알 필요가 없다. 시드 전체가 트랜잭션 하나라
  # 중간에 터지면 아무것도 남지 않는다.
  python -m app.seed
fi

exec "$@"
