"""숫자만 박고 그 뜻은 두고 왔다 — 판정 시점의 단위

표를 세우지 않는다. `inspection_measurements` 에 칸 하나를, `process_inspection_standards`
에 유일키 하나를, 그 둘 사이에 외래키 하나를 붙인다.

**규격을 박아 두는 이유의 절반이 빠져 있었다.** 측정 줄은 상·하한을 박아 「기준이
나중에 바뀌어도 그때 그 판정은 그대로」를 지키는데, **그 숫자가 `µm` 인지 `mm` 인지는
기준 표에만** 있었다. 거기서 단위를 고치면 측정값도 박아 둔 한계도 하나도 바뀌지
않는데 **읽히는 뜻이 천 배 달라진다** — 50µm 가 50mm 가 된다. 숫자가 그대로라
아무도 알아채지 못하고, 그 기록이 고객에게 가거나 클레임 근거가 된다.

`PRD.md` 성공기준 ④ 가 「기준이 나중에 바뀌어도 그때 그 판정은 그대로 남아야
한다」이고, 이 리비전은 그 적용을 끝까지 미는 자리다.

**박는 것만으로는 모자라 쌍으로 묶는다.** 칸만 더하면 이 줄의 단위와 기준의 단위가
갈릴 수 있고, 갈린 쪽이 옳은지 말해 줄 것이 없다. 넷을 함께 가리키면 둘은 갈릴 수
없고, **가리키는 줄이 있는 동안 기준의 단위를 바꾸는 것 자체가 막힌다** — 바꾸면
가리키던 짝이 사라지기 때문이다. 「이미 특채를 낸 사유의 플래그를 끌 수 없다」와
같은 자리이며, 거래 데이터가 자기 근거를 잠근다.

**더하는 유일키는 행을 좁히지 않는다.** `(공정 × 항목 × 자재군)` 이 이미 유일하므로
넷째 칸을 더해도 같은 줄이다 — `uq_inspection_id_result` 와 같은 이유로, 목적은
**가리킬 상대를 만드는 것**이다.

**옛 줄에 채우는 값은 「그때의 단위」가 아니다.** 기준에서 옮겨 오지만, 이 리비전이
서기 전에 누가 단위를 고쳤다면 **그때 값은 이미 사라졌고 되찾을 방법이 없다.**
채우는 것은 **「지금 읽히고 있는 값」을 고정하는 것**이지 복원이 아니다 — 이 리비전
뒤로는 갈리지 않는다는 것이 이 단계가 주는 전부다.

**올릴 때 멈추지 않는다.** 널 허용 칸이고, 채움은 기준이 있는 줄에만 닿는다.

**내릴 때도 멈추지 않는다.** 되돌리면 이 칸이 사라지지만 **그 사실을 다시 만들 수
있다** — 위의 외래키가 사는 동안 기준의 단위가 이 값이었음을 보증하므로, 다시 올릴
때 같은 자리에서 같은 값이 나온다(W-6 이 구조 리비전에 묻는 것이고, 그 가능성의
근거가 바로 그 외래키다). 다만 **그 보증 밖의 줄**은 이름으로 말하고 멈춘다.

> **이 가드가 못 보는 부류**(W-6 ③): 되돌린 **뒤에** 기준의 단위를 고치는 것.
> 그때는 막을 외래키가 이미 없고, 다시 올리면 새 단위가 박힌다 — 되돌리기가
> 여는 창이며 닫는 것은 이 리비전이 아니라 **되돌리지 않는 것**이다.

Revision ID: b41d7c8e5a92
Revises: a7c14b3e9052
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b41d7c8e5a92"
down_revision: str | None = "a7c14b3e9052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "inspection_measurements",
        sa.Column("applied_unit", sa.String(length=20), nullable=True),
    )
    # ── 데이터 단계 — 기준이 지금 들고 있는 단위를 옮긴다 ──────────────────
    # **복원이 아니라 고정이다.** 이 리비전이 서기 전에 단위가 고쳐졌다면 그때
    # 값은 이미 사라졌다. 여기서 하는 일은 「지금 읽히는 값」을 그 줄에 박아
    # **이 뒤로는 갈리지 않게** 하는 것뿐이다.
    op.execute(
        """
        UPDATE inspection_measurements AS m
        SET applied_unit = s.unit
        FROM process_inspection_standards AS s
        WHERE s.process_code = m.process_code
          AND s.item_code = m.item_code
          AND s.material_group = m.material_group
        """
    )
    op.create_unique_constraint(
        "uq_inspection_standard_unit",
        "process_inspection_standards",
        ["process_code", "item_code", "material_group", "unit"],
        postgresql_nulls_not_distinct=True,
    )
    op.create_foreign_key(
        "fk_inspection_measurement_unit",
        "inspection_measurements",
        "process_inspection_standards",
        ["process_code", "item_code", "material_group", "applied_unit"],
        ["process_code", "item_code", "material_group", "unit"],
    )


def downgrade() -> None:
    # **되돌려도 되는 근거를 먼저 확인한다.** 이 칸의 값은 위의 외래키가 사는
    # 동안 기준의 단위와 같음이 보증되므로, 지우더라도 기준에서 다시 만들 수
    # 있다. 그 보증 밖으로 나간 줄 — 외래키가 건너뛴 자리 — 만 되찾을 수 없다.
    op.execute(
        """
        DO $$
        DECLARE adrift text;
        BEGIN
          SELECT string_agg(m.inspection_id::text || '/' || m.item_code, ', '
                            ORDER BY m.inspection_id, m.item_code) INTO adrift
          FROM inspection_measurements AS m
          LEFT JOIN process_inspection_standards AS s
            ON s.process_code = m.process_code
           AND s.item_code = m.item_code
           AND s.material_group = m.material_group
          WHERE m.applied_unit IS NOT NULL
            AND m.applied_unit IS DISTINCT FROM s.unit;
          IF adrift IS NOT NULL THEN
            RAISE EXCEPTION
              '되돌리면 이 측정 줄의 단위를 되찾을 수 없다: %. 기준이 든 단위와 이미 달라 기준에서 다시 만들 수 없다',
              adrift;
          END IF;
        END $$;
        """
    )

    op.drop_constraint(
        "fk_inspection_measurement_unit", "inspection_measurements", type_="foreignkey"
    )
    op.drop_constraint(
        "uq_inspection_standard_unit", "process_inspection_standards", type_="unique"
    )
    op.drop_column("inspection_measurements", "applied_unit")
