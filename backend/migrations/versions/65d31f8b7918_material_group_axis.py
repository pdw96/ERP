"""자재군 축 — 수입 기준이 품목을 가리게 한다

「수입」 기준 여덟이 원자재 열다섯 전부에 똑같이 걸리던 자리를 닫는다. 분말에
점도를, 라이너에 입도를 재라고 내밀지 않게 된다.

**자동 생성을 그대로 쓰지 않았다.** Alembic 이 내놓은 것에는 CHECK 넷이 전부
없었고(CHECK 는 비교 대상이 아니다), 기준 표의 **기본키 교체**도 없었다 —
`id` 를 더하기만 하고 옛 기본키를 그대로 두었다. 손으로 다시 적었고
`tests/test_migrations.py` 가 두 스키마를 견준다.

**데이터 단계가 있다.** 스키마만 바꾸면 이미 심긴 데이터베이스는 자재군이
`NULL` 인 「수입」 줄을 들고 있어 새 CHECK 에 걸린다. 그래서 기준정보를 여기서
옮긴다 — `CLAUDE.md` 가 「기준정보 값을 고쳐야 하면 시드가 아니라
마이그레이션으로 낸다」고 적은 그 자리다.

**지우지 않고 옮긴다.** 이 마이그레이션이 존재하는 근거가 「사람이 고친 값을
재시드가 덮어쓰는 쪽이 더 큰 사고다」인데, 지우고 다시 심으면 그 재시드와 같은
일을 하게 된다. 그래서 옛 여덟 줄을 `UPDATE` 로 첫 무리에 옮기고, 두 무리
이상에 걸치는 항목만 **그 줄을 베껴** 나머지 무리에 세운다. 실측 σ 나 고객이
준 규격이 들어 있었다면 그대로 따라간다.

**되돌릴 때는 다르다.** 옛 기본키가 항목마다 한 줄만 받으므로 줄이는 것 자체는
피할 수 없고, 남는 줄은 옮겨 쓴 옛 줄이며 **그 밖의 줄에 있던 값은 사라진다.**
그래서 무엇이 사라지는지 **먼저 이름을 말하고 멈춘다** — 이 리비전이 세우지 않은
줄 · 남길 줄이 아닌 자리의 σ · 남길 줄과 다른 규격과 값 · 심지 않은 자재군 코드 ·
뜻이 달라진 그룹 · 사람이 고친 품목의 자재군 배정 여섯이다.

**데이터 단계는 이미 심긴 데이터베이스에서만 돈다.** 조건은 시드의 조건 ③ 을
뒤집은 것이다 — 시드는 품목 표가 **비어 있을 때** 돌고 이것은 **비어 있지 않을
때** 돈다. 둘은 같은 데이터베이스에서 함께 돌 수 없으므로 값이 두 번 들어가지
않는다.

**이 리비전은 표를 다시 쓰고, 도는 동안 네 표의 쓰기가 멈춘다.** 통과하는 것과
멈추지 않는 것은 다르다 — 논리적으로는 깨끗이 통과하면서도 배타적 잠금으로 그동안의
모든 쓰기를 세운다. 오늘은 운영 데이터도 배포처도 없어 무해하지만, 그 전제가 깨지는
날 이 자리는 다운타임이고 **적혀 있지 않으면 배포하는 사람이 모르고 지나간다.**

- `ADD COLUMN id SERIAL PRIMARY KEY` — 기본값이 휘발성이라 PostgreSQL 이
  `process_inspection_standards` 를 **통째로 다시 쓴다**(실측: `relfilenode` 가 바뀐다).
  그동안 `AccessExclusiveLock`
- 외래키 둘과 CHECK 넷 — **기존 행 전체를 검증한다.** 외래키는 가리키는 표와
  가리켜지는 표 **양쪽**을 잡으므로 `common_codes` 의 쓰기도 함께 멈춘다
- `create_unique_constraint` — 잠금을 잡고 인덱스를 만든다. `CONCURRENTLY` 를 쓸 수
  없는 형태다
- `downgrade()` 도 같다 — `ADD PRIMARY KEY (process_code, item_code)` 가 인덱스를
  만들고 NOT NULL 을 검증한다

**얼마나 멈추는가는 구문 하나의 길이가 아니다.** `migrations/env.py` 가 마이그레이션
전체를 트랜잭션 하나로 감싸므로, 첫 `ALTER` 가 잡은 잠금이 데이터 단계(UPDATE ·
INSERT 다섯 줄과 `DO` 블록 둘)를 지나 **커밋까지** 유지된다. 「반쯤 올라간 스키마」를 없애는
값과 맞바꾼 것이며, 그 맞바꿈은 표를 세우는 단계에서는 옳다.

심각도는 행 수와 동시 쓰기에 달렸고 **그 둘은 저장소에 없다.** 운영 데이터가 있는
곳에서 이것을 돌린다면 쓰기를 세우고 돌리거나, 그 전에 나누는 형태를 검토한다 —
CHECK 와 외래키는 `NOT VALID` + 뒤이은 `VALIDATE CONSTRAINT`, 유일키는
`CREATE INDEX CONCURRENTLY` 뒤 제약으로 승격, `id` 는 `bigint` 로 붙이고 기본값과
시퀀스를 나중에 다는 단계적 백필.

Revision ID: 65d31f8b7918
Revises: 3c602ffaebc3
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "65d31f8b7918"
down_revision: str | None = "3c602ffaebc3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# 이미 심긴 데이터베이스에서만 도는 데이터 단계의 조건. 시드의 조건 ③ 을 뒤집은 것.
_ALREADY_SEEDED = "WHERE EXISTS (SELECT 1 FROM items)"

# 원자재 열다섯이 어느 무리인가. 재고단위가 경계를 말한다 — KG 아홉 · L 둘 · M2 넷.
# **시드 SQL 과 같은 것을 말한다.** 둘이 갈리지 않는지는
# `test_both_roads_reach_the_same_material_groups` 가 두 길을 실제로 돌려 견준다.
_ITEM_GROUPS = """('RM-01','액상수지'),('RM-02','분체'),('RM-03','분체'),('RM-04','시트필름'),
       ('RM-05','액상수지'),('RM-06','분체'),('RM-07','시트필름'),('RM-08','액상수지'),
       ('RM-09','분체'),('RM-10','액상수지'),('RM-11','시트필름'),('RM-12','분체'),
       ('RM-13','액상수지'),('RM-14','액상수지'),('RM-15','시트필름')"""

# 검사항목이 **처음** 서는 무리. 옛 줄을 이 무리로 옮기므로 그 줄의 값이 따라간다.
_FIRST_GROUP = """('입도','분체'),('수분','분체'),('점도','액상수지'),('색차','액상수지'),
       ('두께','시트필름'),('이물','분체'),('포장','분체'),('성적서','분체')"""

# 두 무리 이상에 걸치는 항목의 **나머지** 무리. 첫 무리의 줄을 베껴 세운다.
# 계수 셋(이물 · 포장 · 성적서)은 재는 것이 아니라 세는 것이라 무리를 가리지 않는다.
_EXTRA_GROUPS = """('수분','액상수지'),('색차','시트필름'),
       ('이물','액상수지'),('이물','시트필름'),
       ('포장','액상수지'),('포장','시트필름'),
       ('성적서','액상수지'),('성적서','시트필름')"""

# 이 표에서 **값을 담는 칸 전부.** 정체성(공정 · 검사항목 · 자재군)과 그 그룹 칸을
# 뺀 나머지다. 베끼는 `INSERT` 와 되돌리기 가드가 **같은 목록을 부른다** — 두 벌이면
# 갈리고, 갈리는 쪽은 언제나 가드다(베끼는 쪽은 틀리면 바로 터진다).
_VALUE_COLUMNS = (
    "upper_spec_limit",
    "lower_spec_limit",
    "center_line",
    "warning_ratio",
    "sigma",
    "sigma_source",
    "time_variant",
    "unit",
)
_STANDARD_VALUE_COLUMNS = ", ".join(_VALUE_COLUMNS)

# 되돌리기 가드가 **줄 대 줄로 견주는** 칸. σ 와 σ출처는 뺀다 — 앞선 가드가 σ 를
# 이미 보고, σ 가 비어 있으면 양방향 CHECK 가 σ출처를 「미정」 하나로 못박으므로
# 두 줄이 그 칸에서 갈릴 수 없다.
_COMPARED_VALUE_COLUMNS = tuple(c for c in _VALUE_COLUMNS if not c.startswith("sigma"))
_DOOMED_VALUES = ", ".join("s." + c for c in _COMPARED_VALUE_COLUMNS)
_KEPT_VALUES = ", ".join("k." + c for c in _COMPARED_VALUE_COLUMNS)

# 옮기지 못한 줄이 있으면 **무엇이 남았는지 말하고 멈춘다.** 그냥 두면 바로 뒤의
# 양방향 CHECK 가 대신 터지는데, 그 오류는 「제약 위반」일 뿐이라 원인이 위의 두
# 목록에 있다는 것을 말해 주지 않는다. 트랜잭션 하나이므로 멈추면 아무것도 남지 않는다.
_STOP_IF_ANYTHING_WAS_LEFT_BEHIND = """
DO $$
DECLARE leftover text;
BEGIN
  SELECT string_agg(DISTINCT code, ', ') INTO leftover
    FROM items WHERE item_type = '원자재' AND material_group IS NULL;
  IF leftover IS NOT NULL THEN
    RAISE EXCEPTION '자재군을 정하지 못한 원자재가 있다: % — 이 리비전의 _ITEM_GROUPS 에 더해야 한다', leftover;
  END IF;

  SELECT string_agg(DISTINCT item_code, ', ') INTO leftover
    FROM process_inspection_standards WHERE process_code = '수입' AND material_group IS NULL;
  IF leftover IS NOT NULL THEN
    RAISE EXCEPTION '자재군을 정하지 못한 수입 검사항목이 있다: % — 이 리비전의 _FIRST_GROUP 에 더해야 한다', leftover;
  END IF;
END $$;
"""

# 이 리비전이 심는 자재군 코드 셋. **넣는 쪽과 되돌릴 때 지키는 쪽이 같은 것을
# 부른다** — 두 벌이면 갈리고, 갈리면 「심은 것만 지운다」가 거짓이 된다.
_MATERIAL_GROUP_CODES = (
    "('MATERIAL_GROUP','분체','분체',1,'입도와 수분을 본다'),"
    " ('MATERIAL_GROUP','액상수지','액상 · 수지',2,'점도와 색차를 본다'),"
    " ('MATERIAL_GROUP','시트필름','시트 · 필름',3,'두께와 색차를 본다')"
)

# **되돌리기가 조용히 지우지 못하게 막는다.**
#
# 옛 기본키 `(공정, 검사항목)` 이 돌아오므로 항목마다 한 줄로 줄이는 것 **자체는
# 피할 수 없다.** 피할 수 있는 것은 **조용한 것**이다 — upgrade 가 멈출 때 이유를
# 말하는데 downgrade 는 아무 말도 하지 않았다.
#
# **다섯을 본다.** 이 리비전이 세우지 않은 수입 기준(남이 더한 것) · 남길 한 줄이
# 아닌 자리의 σ(사람이 넣은 값 — 「임의」와 「실측」 둘 다다. 「미정」만 빈 값이다) ·
# 이 리비전이 심지 않은 자재군 코드 · 뜻이 달라진 그룹 · **사람이 고친 품목의 자재군
# 배정.** 다섯 다 「일어난 일은 지우지 않는다」에 걸린다.
#
# **세는 방식이 세 번 틀렸다.** 감사 ③ 은 「지우는 자리를 전부 다시 봤다 — 셋뿐이다」로
# 닫았는데 그 셋은 `DELETE` 만 센 것이었다. **칸을 떨어뜨리는 것도 지우는 것이다** —
# `drop_column("items","material_group")` 이 사람이 고친 배정을 말없이 가져갔다.
# 여기서 세어야 하는 것은 구문이 아니라 **되돌릴 때 사라지는 사실**이다.
_STOP_IF_DOWNGRADE_WOULD_LOSE_SOMETHING = f"""
DO $$
DECLARE doomed text;
BEGIN
  SELECT string_agg(DISTINCT item_code || '/' || material_group, ', ') INTO doomed
    FROM process_inspection_standards
   WHERE process_code = '수입'
     AND (item_code, material_group) NOT IN (
           SELECT f.item, f.grp FROM (VALUES {_FIRST_GROUP}) AS f(item, grp)
           UNION ALL
           SELECT e.item, e.grp FROM (VALUES {_EXTRA_GROUPS}) AS e(item, grp)
         );
  IF doomed IS NOT NULL THEN
    RAISE EXCEPTION '되돌리면 이 리비전이 세우지 않은 수입 기준이 사라진다: % — 남이 더한 줄이다. 지울지 옮길지는 사람이 정한다', doomed;
  END IF;

  -- **「실측」만 보지 않는다.** σ 출처는 미정 · 임의 · 실측 셋이고, 「임의」도 사람이
  -- 넣은 값이다. 좁히면 그것이 다시 조용히 사라지므로 넓게 잡고 말을 맞춘다.
  SELECT string_agg(DISTINCT item_code || '/' || material_group, ', ') INTO doomed
    FROM process_inspection_standards s
   WHERE s.process_code = '수입' AND s.sigma IS NOT NULL
     AND s.id <> (SELECT min(t.id) FROM process_inspection_standards t
                   WHERE t.process_code = '수입' AND t.item_code = s.item_code);
  IF doomed IS NOT NULL THEN
    RAISE EXCEPTION '되돌리면 σ 가 사라진다: % — 옛 기본키가 항목마다 한 줄만 받으므로 줄이는 것은 피할 수 없다. 남길 줄로 옮긴 뒤 다시 되돌린다', doomed;
  END IF;

  -- **σ 만 보지 않는다.** 같은 줄에 규격 · 경고비 · 경시변화 · 단위가 함께 있고,
  -- 그중 규격은 「고객이 정한다」(설계 원칙 5). 이 표는 (공정 × 검사항목 × 자재군)
  -- 유일키라 **무리마다 다른 규격을 허용하도록 설계됐고** 그것을 금지하는 제약도
  -- 없다 — 사람이 무리별로 적어 둔 값이 여기서 말없이 사라졌다.
  --
  -- **같은 모양의 다섯 번째다.** 앞의 넷은 「지우는 자리」를 좁게 셌고(`DELETE` 만
  -- 세어 `drop_column` 을 빠뜨렸다), 이번 것은 자리는 맞게 셌는데 **그 자리에서
  -- 사라지는 사실을 좁게 셌다** — 한 칸(σ)에만 물었다. 세어야 하는 것은 구문도
  -- 칸 하나도 아니고 **그 줄에서 사람의 것인 값 전부**다.
  SELECT string_agg(DISTINCT s.item_code || '/' || s.material_group, ', ') INTO doomed
    FROM process_inspection_standards s
    JOIN process_inspection_standards k
      ON k.id = (SELECT min(t.id) FROM process_inspection_standards t
                  WHERE t.process_code = '수입' AND t.item_code = s.item_code)
   WHERE s.process_code = '수입' AND s.id <> k.id
     AND ({_DOOMED_VALUES})
         IS DISTINCT FROM
         ({_KEPT_VALUES});
  IF doomed IS NOT NULL THEN
    RAISE EXCEPTION '되돌리면 남길 줄과 다른 규격 · 경고비 · 경시변화 · 단위가 사라진다: % — 사람이 무리별로 적어 둔 값이다. 남길 줄로 옮긴 뒤 다시 되돌린다', doomed;
  END IF;

  -- **이 리비전이 심은 것만 지운다는 말을 지킨다.**
  --
  -- upgrade 가 「이미 있으면 넘어간다」로 바뀌면서 운영자가 먼저 만든 줄이 살아서
  -- 건너오게 됐다. 그런데 downgrade 는 이름으로 셋을 지우므로 **심지 않은 것까지**
  -- 지운다 — 고침 하나가 한 표 옆에 같은 자리를 새로 연 것이다.
  SELECT string_agg(DISTINCT c.code, ', ') INTO doomed
    FROM common_codes c
    JOIN (VALUES {_MATERIAL_GROUP_CODES}) AS v(group_code, code, name, sort_order, description)
      ON c.group_code = v.group_code AND c.code = v.code
   WHERE (c.name, c.sort_order, c.description, c.is_active)
         IS DISTINCT FROM (v.name, v.sort_order, v.description, TRUE);
  IF doomed IS NOT NULL THEN
    RAISE EXCEPTION '되돌리면 이 리비전이 심지 않은 자재군 코드가 사라진다: % — 사람이 먼저 만들었거나 고친 줄이다. 지울지는 사람이 정한다', doomed;
  END IF;

  IF EXISTS (
    SELECT 1 FROM code_groups
     WHERE group_code = 'MATERIAL_GROUP'
       AND (name, value_fixed, description)
           IS DISTINCT FROM ('자재군', FALSE, '수입 검사 기준이 걸리는 축이다.')
  ) THEN
    RAISE EXCEPTION 'MATERIAL_GROUP 그룹이 이 리비전이 심은 것과 다르다 — 되돌리면 사람이 적은 것이 사라진다. 지울지는 사람이 정한다';
  END IF;

  -- **칸을 떨어뜨리는 것도 지우는 것이다.**
  --
  -- `drop_column("items","material_group")` 은 `DELETE` 가 아니라 보이지 않았는데,
  -- 사람이 고친 배정은 거기서 사라진다. 다시 올리면 `_ITEM_GROUPS` 의 값이 돌아와
  -- **지어낸 값이 사람의 판단을 덮는다.** 하필 `RM-12` 는 「코드로 판정할 수 없다,
  -- 사람이 본다」로 대장에 적어 둔 품목이다 — 사람이 보고 고칠 것을 전제한 칸인데
  -- 그 고침이 남지 않았다.
  --
  -- 이 리비전이 심지 않은 배정을 전부 본다: 값을 고친 것과, 이 리비전이 모르는
  -- 원자재를 사람이 더한 것 둘 다다.
  SELECT string_agg(DISTINCT i.code || '/' || i.material_group, ', ') INTO doomed
    FROM items i
    LEFT JOIN (VALUES {_ITEM_GROUPS}) AS g(code, grp) ON i.code = g.code
   WHERE i.material_group IS NOT NULL AND i.material_group IS DISTINCT FROM g.grp;
  IF doomed IS NOT NULL THEN
    RAISE EXCEPTION '되돌리면 사람이 고친 자재군 배정이 사라진다: % — 이 리비전이 심은 값이 아니다. 다시 올리면 _ITEM_GROUPS 의 값이 덮는다. 지울지는 사람이 정한다', doomed;
  END IF;
END $$;
"""


# 그룹이 이미 있어도 **뜻이 같으면** 넘어간다. 다른 것은 `value_fixed` 하나뿐인데,
# 그것이 참이면 「프로그램이 값을 보고 분기한다」는 뜻이라 자재군과 정반대다 —
# 넘어가면 화면에서 무리를 못 늘리게 된다. 그때는 이름을 말하고 멈춘다.
_STOP_IF_THE_GROUP_MEANS_SOMETHING_ELSE = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM code_groups WHERE group_code = 'MATERIAL_GROUP' AND value_fixed) THEN
    RAISE EXCEPTION 'MATERIAL_GROUP 그룹이 이미 있는데 value_fixed 가 참이다 — 자재군은 값이 늘 수 있는 그룹이어야 한다. 먼저 사람이 정한다';
  END IF;
END $$;
"""


def upgrade() -> None:
    # ── 품목이 자기 무리를 안다 ─────────────────────────────────────────────
    op.add_column("items", sa.Column("material_group", sa.String(length=30), nullable=True))
    op.add_column(
        "items",
        sa.Column(
            "material_group_group",
            sa.String(length=20),
            server_default="MATERIAL_GROUP",
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_item_material_group",
        "items",
        "common_codes",
        ["material_group_group", "material_group"],
        ["group_code", "code"],
    )
    op.create_check_constraint(
        "ck_item_material_group_group", "items", "material_group_group = 'MATERIAL_GROUP'"
    )

    # ── 기준 표가 자재군을 받는다 ───────────────────────────────────────────
    op.add_column(
        "process_inspection_standards",
        sa.Column("material_group", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "process_inspection_standards",
        sa.Column(
            "material_group_group",
            sa.String(length=20),
            server_default="MATERIAL_GROUP",
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_inspection_standard_material_group",
        "process_inspection_standards",
        "common_codes",
        ["material_group_group", "material_group"],
        ["group_code", "code"],
    )
    op.create_check_constraint(
        "ck_inspection_standard_material_group_group",
        "process_inspection_standards",
        "material_group_group = 'MATERIAL_GROUP'",
    )

    # ── 기본키를 대리키로 바꾼다 ────────────────────────────────────────────
    # 정체성은 (공정 × 검사항목 × 자재군)이지만 기본키는 `NULL` 을 받지 않고,
    # 공정검사 줄의 자재군은 비어 있다. 자리만 맡는 `id` 를 두고 정체성은 아래의
    # 유일키가 말한다. `SERIAL` 이라 이미 있는 줄에도 번호가 채워진다.
    op.execute(
        "ALTER TABLE process_inspection_standards DROP CONSTRAINT process_inspection_standards_pkey"
    )
    op.execute("ALTER TABLE process_inspection_standards ADD COLUMN id SERIAL PRIMARY KEY")

    # ── 데이터 — 이미 심긴 데이터베이스에서만 돈다 ─────────────────────────
    # **이미 있으면 넘어간다.** 자재군은 「값이 늘 수 있는 그룹」이라 운영자가 먼저
    # 만들어 두었을 수 있다. 그대로 `INSERT` 하면 「제약 위반」만 보이고 원인이
    # 이 리비전에 있다는 것을 말해 주지 않는다 — upgrade 가 멈출 때 이유를 말하기로
    # 한 것과 같은 자리다.
    op.execute(_STOP_IF_THE_GROUP_MEANS_SOMETHING_ELSE)
    op.execute(
        "INSERT INTO code_groups (group_code, name, value_fixed, description)"
        " SELECT 'MATERIAL_GROUP', '자재군', FALSE, '수입 검사 기준이 걸리는 축이다.'"
        f" {_ALREADY_SEEDED}"
        "   AND NOT EXISTS (SELECT 1 FROM code_groups WHERE group_code = 'MATERIAL_GROUP')"
    )
    op.execute(
        "INSERT INTO common_codes (group_code, code, name, sort_order, description)"
        " SELECT v.group_code, v.code, v.name, v.sort_order, v.description FROM (VALUES"
        f" {_MATERIAL_GROUP_CODES}"
        " ) AS v(group_code, code, name, sort_order, description)"
        f" {_ALREADY_SEEDED}"
        "   AND NOT EXISTS (SELECT 1 FROM common_codes c"
        "                    WHERE c.group_code = v.group_code AND c.code = v.code)"
    )
    op.execute(
        "UPDATE items SET material_group = m.grp"
        f" FROM (VALUES {_ITEM_GROUPS}) AS m(code, grp)"
        " WHERE items.code = m.code"
    )
    # 옛 줄을 **옮긴다.** 지우지 않으므로 그 줄에 들어 있던 값이 따라간다.
    op.execute(
        "UPDATE process_inspection_standards s SET material_group = m.grp"
        f" FROM (VALUES {_FIRST_GROUP}) AS m(item, grp)"
        " WHERE s.process_code = '수입' AND s.item_code = m.item"
    )
    # 두 무리 이상에 걸치는 항목만 **그 줄을 베껴** 나머지 무리에 세운다.
    #
    # **규격은 따라가고 σ 는 따라가지 않는다.** 규격 상·하한과 중심선은 고객이
    # 정하는 것이라 같은 항목이면 무리가 달라도 그대로 쓸 수 있다. σ 는 **잰
    # 값**이고 새 무리에서는 잰 적이 없다 — 베껴 오면 재지 않은 것을 쟀다고
    # 적는 것이 된다. 그래서 「미정」으로 세운다(σ 와 출처를 묶는 양방향 CHECK
    # 가 그 짝을 지킨다).
    op.execute(
        "INSERT INTO process_inspection_standards"
        " (process_group, process_code, item_group, item_code, material_group,"
        f"  material_group_group, {_STANDARD_VALUE_COLUMNS})"
        " SELECT s.process_group, s.process_code, s.item_group, s.item_code, m.grp,"
        "        s.material_group_group, s.upper_spec_limit, s.lower_spec_limit, s.center_line,"
        "        s.warning_ratio, NULL, '미정', s.time_variant, s.unit"
        "   FROM process_inspection_standards s"
        f"   JOIN (VALUES {_EXTRA_GROUPS}) AS m(item, grp) ON s.item_code = m.item"
        "  WHERE s.process_code = '수입' AND s.material_group IS NOT NULL"
    )
    op.execute(_STOP_IF_ANYTHING_WAS_LEFT_BEHIND)

    # ── 데이터가 자리를 잡은 뒤에 규칙을 건다 ───────────────────────────────
    # 순서가 뒤집히면 옛 줄이 새 CHECK 에 걸려 마이그레이션이 멈춘다.
    op.create_check_constraint(
        "ck_item_material_group_matches_type",
        "items",
        "(item_type = '원자재') = (material_group IS NOT NULL)",
    )
    op.create_unique_constraint(
        "uq_inspection_standard",
        "process_inspection_standards",
        ["process_code", "item_code", "material_group"],
        postgresql_nulls_not_distinct=True,
    )
    op.create_check_constraint(
        "ck_inspection_standard_material_group_matches_process",
        "process_inspection_standards",
        "(process_code IN ('수입')) = (material_group IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_inspection_standard_material_group_matches_process",
        "process_inspection_standards",
        type_="check",
    )
    op.drop_constraint("uq_inspection_standard", "process_inspection_standards", type_="unique")
    op.drop_constraint("ck_item_material_group_matches_type", "items", type_="check")

    op.execute(_STOP_IF_DOWNGRADE_WOULD_LOSE_SOMETHING)

    # **항목마다 가장 먼저 선 줄 하나만 남기고 나머지를 지운다.**
    #
    # 조건은 `id` 가 최솟값이 아닌 **전부**다 — 「베낀 줄만」이 아니라 이 리비전이
    # 베끼지 않은 줄도 함께 지운다. 남는 한 줄이 옮겨 쓴 옛 줄이라 사람이 고친 값이
    # 거기 있다는 것은 맞지만, 그 밖의 줄에 있던 값은 사라진다. 한때 이 파일의
    # 머리말이 「베낀 줄만 지운다」고 말했고 여기만 고쳤다가 감사 ⑤ 에 걸렸다 —
    # **명제는 한 자리에서 고쳐지지 않는다.**
    #
    # 줄이는 것 자체는 피할 수 없다(옛 기본키가 항목마다 한 줄만 받는다). 그래서
    # 위에서 **무엇이 사라지는지 먼저 말하고 멈춘다.**
    op.execute(
        "DELETE FROM process_inspection_standards s"
        " WHERE s.process_code = '수입'"
        "   AND s.id <> (SELECT min(t.id) FROM process_inspection_standards t"
        "                 WHERE t.process_code = '수입' AND t.item_code = s.item_code)"
    )
    op.execute(
        "UPDATE process_inspection_standards SET material_group = NULL WHERE process_code = '수입'"
    )

    op.execute(
        "ALTER TABLE process_inspection_standards DROP CONSTRAINT process_inspection_standards_pkey"
    )
    op.drop_column("process_inspection_standards", "id")
    op.execute(
        "ALTER TABLE process_inspection_standards ADD PRIMARY KEY (process_code, item_code)"
    )

    op.drop_constraint(
        "ck_inspection_standard_material_group_group",
        "process_inspection_standards",
        type_="check",
    )
    op.drop_constraint(
        "fk_inspection_standard_material_group",
        "process_inspection_standards",
        type_="foreignkey",
    )
    op.drop_column("process_inspection_standards", "material_group_group")
    op.drop_column("process_inspection_standards", "material_group")

    op.drop_constraint("ck_item_material_group_group", "items", type_="check")
    op.drop_constraint("fk_item_material_group", "items", type_="foreignkey")
    op.drop_column("items", "material_group_group")
    op.drop_column("items", "material_group")

    # **코드는 맨 마지막에, 심은 셋만 지운다.**
    #
    # 가리키는 칸을 먼저 걷어내야 지울 수 있다 — 순서를 바꾸면 외래키가 막는다.
    # 그리고 자재군은 「값이 늘 수 있는 그룹」이므로 올린 뒤에 넷째 무리가 늘었을
    # 수 있다. 그룹째 지우면 사람이 넣은 사실이 함께 사라지므로, 이 리비전이 심은
    # 셋만 지우고 그룹은 **남은 값이 없을 때만** 지운다.
    #
    # 「심은 셋」인지는 위의 멈춤 검사가 지킨다 — 이름이 같아도 값이 다르면 남이
    # 만든 줄이므로 거기서 멈춘다. 그 검사가 없으면 이 `DELETE` 는 이름만 보고
    # 남의 것을 지운다.
    #
    # **목록을 여기 다시 적지 않는다.** 이름 셋을 손으로 적어 두었더니 넣는 쪽과
    # 지우는 쪽이 두 벌이 됐다 — `_MATERIAL_GROUP_CODES` 에 넷째를 더해도 이 줄은
    # 모르고, 여기에 남의 코드를 하나 더해도 넣는 쪽은 모른다. 한쪽만 고치면
    # 「심은 것만 지운다」가 조용히 거짓이 되는 그 길이다.
    op.execute(
        f"DELETE FROM common_codes c WHERE c.group_code = 'MATERIAL_GROUP'"
        f" AND EXISTS (SELECT 1 FROM (VALUES {_MATERIAL_GROUP_CODES})"
        f"              AS v(group_code, code, name, sort_order, description)"
        f"             WHERE v.group_code = c.group_code AND v.code = c.code)"
    )
    op.execute(
        "DELETE FROM code_groups WHERE group_code = 'MATERIAL_GROUP'"
        " AND NOT EXISTS (SELECT 1 FROM common_codes WHERE group_code = 'MATERIAL_GROUP')"
    )
