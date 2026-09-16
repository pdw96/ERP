# 조기경보 ERP

필름·시트를 코팅하고 적층하는 공정의 ERP. 물건이 지나가는 다섯 구간 —
입고 → 원재료창고 → 생산창고 → 제품창고 → 출하 — 을 장부에 적는다.

- **설계도**: [조기경보 ERP 설계도 42판](https://claude.ai/artifact/GMJpbFywKh8wj6N4vEukT6)
- **이번 범위**: [`PRD.md`](PRD.md) — 1단계 · 표를 세우는 단 한 번
- **표의 모양**: [`docs/schema.md`](docs/schema.md)
- **작업 규칙**: [`CLAUDE.md`](CLAUDE.md) · [`CHECKLIST.md`](CHECKLIST.md)

## 지금 어디인가

**1단계가 끝났다** — 기준정보 표 열셋과 로트 표 하나, 마이그레이션, 시드.
테스트 145개가 PostgreSQL 16 위에서 돈다.

`app/seed_data/` 의 숫자는 **전부 시연용 임의값**이다. 실제 규격은 고객 도면이
있어야 나온다 — 각 파일 머리에 그 사실을 적어 두었다.

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

마이그레이션과 기준정보를 넣으려면:

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
  app/core/codes.py      공통코드 그룹 스물넷 — 프로그램이 아는 이름
  app/db/base.py         SQLAlchemy 뿌리 · 엔진 · 트랜잭션 하나
  app/db/constraints.py  모델과 마이그레이션이 함께 부르는 제약 식
  app/db/common_codes.py 공통코드 본체 두 표
  app/db/code_attributes.py  확장 표 셋과 「코드 × 단계」
  app/db/master.py       품목 · 2단 BOM · 거래처 · 공급사별 품목
  app/db/production.py   근무형태 · 비가동 구간
  app/db/quality.py      공정별 검사 기준
  app/db/inventory.py    로트 한 표
  app/seed.py            세 조건 · 트랜잭션 하나
  app/seed_data/*.sql    기준정보 — 사람이 읽고 고치는 표
  migrations/            Alembic — 리비전 하나
  tests/                 실제 PostgreSQL 에 붙는다 (145개)
compose.yaml             postgres + 일회성 migrate 잡
```
