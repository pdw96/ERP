"""불합격에도 도착일이 남는다 — 로트가 서지 않는 판정의 사실

표를 세우지 않는다. `inspections` 에 칸 하나와 유일키 하나와 CHECK 하나를,
`lots` 에 외래키 하나를 붙인다.

**로트에만 적으면 불합격에서만 사라진다.** 도착일은 사람이 보내는 값인데 그것이
앉는 자리가 `lots.received_date` 하나였고, **원칙 ① 이 「불합격은 로트가 되지
않는다」**이므로 불합격 판정에서는 그 값이 통째로 버려졌다 — 201 로 성공 응답이
나가면서다. 하필 불합격이 **클레임과 반품의 근거**가 되는 판정이고, 그 근거의 첫
줄이 「언제 받은 물건인가」다.

**`judged_at` 이 대신이 되지 못한다.** 이 조각은 뒤늦게 적은 입고를 일부러 받는다
(미래만 막는다). 1일에 온 자재를 21일에 판정하면 둘은 스무 날 갈리고, **그 차이가
곧 검사가 늦은 날수**다.

**옛 줄을 지어내지 않는다.** 칸을 `NOT NULL` 로 세우려면 이미 선 줄에 값을 넣어야
하는데, 합격한 줄은 로트에서 **같은 사실을 옮겨 올 수 있고** 불합격한 줄은 그
값이 애초에 어디에도 없다. 그래서 —

- 합격·특채: 자기를 만든 로트에서 옮긴다. **지어내는 것이 아니라 옮기는 것**이다
- 불합격: 비워 둔다. 「값을 정한 사람이 없으면 `NULL` 로 두고 그 사실을 적는다」

그래서 이 칸은 **널 허용**이고 CHECK 도 `NULL` 을 통과시킨다. 「모른다」를
「위반이다」로 세면 **제약이 이미 선 사실을 막는다** — 기초재고에서 한 번 겪었고
(`08d406fa7f3b`) 맞는 쪽은 테스트였다.

**같은 사실이 두 표에 살게 되므로 쌍으로 묶는다.** `lots.received_date` 는 이월
로트(검사를 모른다)와 FIFO 정렬 키 때문에 남아야 하므로 지울 수 없다. 대신
`(inspection_id, received_date)` 로 검사를 가리키게 해 **갈릴 수 없게** 한다 —
`inspection_result` 를 쌍으로 가리키게 한 것과 같은 자리다(원칙 ⑥).

**자동 생성을 그대로 쓰지 않았다.** `65d31f8b7918` 과 `08d406fa7f3b` 에서 그랬듯
기존 표에 붙는 CHECK 를 Alembic 이 감지하지 않는다. 손으로 적었고
`tests/test_migrations.py` 가 두 스키마를 견준다.

**올릴 때 아무것도 멈추지 않는다.** 널 허용 칸이라 옛 줄이 그대로 서고, 채움은
합격한 줄에만 닿는다.

**내릴 때는 멈춘다.** 칸을 지우면 **불합격의 도착일이 사라지고 복구할 방법이
없다** — 합격한 줄은 로트에 같은 값이 남지만 불합격에는 사본이 없다.
「되돌린 뒤 그 사실을 다시 만들 수 있는가」가 W-6 이 구조 리비전에 묻는 것이고,
여기서는 **불합격에 대해서만 「아니오」**다. 그래서 가드가 세는 것은 칸이 찬 줄
전부가 아니라 **로트가 받쳐 주지 않는 줄**이다.

> **이 가드가 못 보는 부류**(W-6 ③): 로트가 있어 「다시 만들 수 있다」고 센 줄
> 가운데, 되돌린 뒤 **그 로트마저 지워지는** 경우. `08d406fa7f3b` 를 함께 내리면
> 그렇게 되지만 그쪽 가드가 먼저 물므로 이 순서에서는 닿지 않는다.

Revision ID: a7c14b3e9052
Revises: 08d406fa7f3b
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c14b3e9052"
down_revision: str | None = "08d406fa7f3b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("inspections", sa.Column("received_date", sa.Date(), nullable=True))
    # ── 데이터 단계 — 합격한 줄은 로트에서 옮겨 온다 ─────────────────────────
    # **지어내는 것이 아니라 옮기는 것이다.** 같은 입고의 같은 사실이 로트에
    # 이미 적혀 있고, 아래 외래키가 그 뒤로 둘을 갈리지 못하게 한다. 불합격한
    # 줄은 짝이 될 로트가 없으므로 비어서 선다 — 그것이 이 리비전이 고치는
    # 결함의 모양 그대로이며, 지나간 것은 되돌릴 수 없다.
    op.execute(
        """
        UPDATE inspections AS i
        SET received_date = l.received_date
        FROM lots AS l
        WHERE l.inspection_id = i.id AND l.received_date IS NOT NULL
        """
    )
    op.create_check_constraint(
        "ck_inspection_judged_after_arrival",
        "inspections",
        "received_date IS NULL OR judged_at::date >= received_date",
    )
    op.create_unique_constraint(
        "uq_inspection_id_received_date", "inspections", ["id", "received_date"]
    )
    op.create_foreign_key(
        "fk_lot_inspection_received_date",
        "lots",
        "inspections",
        ["inspection_id", "received_date"],
        ["id", "received_date"],
    )


def downgrade() -> None:
    # **사라지는 것을 먼저 이름으로 말하고 멈춘다.** 칸을 지우면 도착일이
    # 사라지는데, 합격한 줄은 로트에 같은 값이 남고 **불합격한 줄은 남지
    # 않는다.** 그래서 세는 것은 「찬 줄」이 아니라 **로트가 받쳐 주지 않는 줄**
    # 이다 — 다시 만들 수 있는 것까지 세면 막을 것이 없는데 멈추게 된다
    # (`08d406fa7f3b` 에서 실제로 그랬다).
    op.execute(
        """
        DO $$
        DECLARE orphaned text;
        BEGIN
          SELECT string_agg(i.id::text, ', ' ORDER BY i.id) INTO orphaned
          FROM inspections AS i
          WHERE i.received_date IS NOT NULL
            AND NOT EXISTS (
              SELECT 1 FROM lots AS l
              WHERE l.inspection_id = i.id AND l.received_date = i.received_date
            );
          IF orphaned IS NOT NULL THEN
            RAISE EXCEPTION
              '되돌리면 이 검사들의 도착일이 사라진다: %. 로트가 없는 판정이라 옮겨 적을 자리가 없다',
              orphaned;
          END IF;
        END $$;
        """
    )

    op.drop_constraint("fk_lot_inspection_received_date", "lots", type_="foreignkey")
    op.drop_constraint("uq_inspection_id_received_date", "inspections", type_="unique")
    op.drop_constraint("ck_inspection_judged_after_arrival", "inspections", type_="check")
    op.drop_column("inspections", "received_date")
