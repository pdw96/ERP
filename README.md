# 조기경보 ERP

필름·시트를 코팅하고 적층하는 공정의 ERP. 물건이 지나가는 다섯 구간 —
입고 → 원재료창고 → 생산창고 → 제품창고 → 출하 — 을 장부에 적는다.

- **설계도**: [조기경보 ERP 설계도 42판](https://claude.ai/artifact/GMJpbFywKh8wj6N4vEukT6)
- **이번 범위**: [`PRD.md`](PRD.md) — 1단계 · 표를 세우는 단 한 번
- **표의 모양**: [`docs/schema.md`](docs/schema.md)
- **작업 규칙**: [`CLAUDE.md`](CLAUDE.md) · [`CHECKLIST.md`](CHECKLIST.md)

## 지금 어디인가

**가설공사가 섰고 본 공사는 아직이다.** 도구(린트 · 타입체크 · 테스트 러너 ·
마이그레이션 · DB)가 돌고, 표는 하나도 없다.

1단계에는 **공개 API 도 화면도 없다.** 뜨는 것은 데이터베이스뿐이고 backend 는
마이그레이션과 시드를 돌리고 끝나는 일회성 잡이다. 웹 서버는 2단계에 들어온다.

## 돌리는 법

```sh
# 데이터베이스
docker compose up -d postgres

# 테스트용 DB 를 한 번 만든다
docker compose exec -T postgres psql -U erp -d erp -c 'CREATE DATABASE erp_test OWNER erp'

# 개발 환경
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

# 검사 넷 — CI 가 도는 것과 같다
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy app migrations
ERP_TEST_DATABASE_URL="postgresql+psycopg://erp:erp@127.0.0.1:5432/erp_test" .venv/bin/pytest
```

마이그레이션과 시드까지 컨테이너에서 돌리려면:

```sh
docker compose run --rm migrate
```

## 환경변수

| 이름 | 기본값 | 무엇 |
|---|---|---|
| `ERP_DATABASE_URL` | 로컬 compose 의 postgres | 앱이 붙는 DB |
| `ERP_TEST_DATABASE_URL` | `…/erp_test` | 테스트가 붙는 DB |
| `ERP_SEED_ENABLED` | `false` | 시드 스위치. **운영에서 자동 시드는 사고다** |

## 구조

```
backend/
  app/core/config.py     환경에서 읽는 설정
  app/db/base.py         SQLAlchemy 뿌리 · 엔진 · 트랜잭션 하나
  migrations/            Alembic — 리비전은 아직 0개
  tests/                 실제 PostgreSQL 에 붙는다
compose.yaml             postgres + 일회성 migrate 잡
```
