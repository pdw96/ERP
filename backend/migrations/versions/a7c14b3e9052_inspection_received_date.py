"""불합격에도 도착일이 남는다 — 로트가 서지 않는 판정의 사실

표를 세우지 않는다. `inspections` 에 칸과 유일키와 CHECK 를, `lots` 에 외래키와
CHECK 를 붙인다(세지 않는다. 세면 갈린다 — 실제로 `lots` 의 CHECK 가 빠져 있었다).

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

**올릴 때 멈출 수 있다 — 아래의 자리마다, 이름을 말하고.** 처음에는 「아무것도
멈추지 않는다」고 적었는데 그것은 **칸을 더하는 것만** 본 말이었다. 칸은 널
허용이라 옛 줄이 그대로 서고 채움도 합격한 줄에만 닿지만, **채움 뒤에 조이는 것이
따라오고** 옛 스키마가 허용하던 줄이 거기 걸린다 —

- **판정이 도착보다 앞선 검사.** 앞 스키마는 `lots.received_date` 와
  `inspections.judged_at` 을 잇는 제약을 갖고 있지 않았으므로 그런 짝이 설 수 있고,
  데이터 단계가 그 값을 옮겨 오면 아래 CHECK 가 걸린다. 거기서 나오는 말은 제약
  이름이라 **어느 검사인지** 모른다 — 그래서 조이기 전에 이름으로 묻는다

**나머지 한 자리에는 가드를 두지 않았다.** 「검사를 가리키는데 도착일이 없는
로트」는 앞 스키마의 제약 사슬이 이미 막고 있어 **옛 줄로는 설 수 없다**(그 사슬은
아래 코드가 이름으로 적는다). **지어낸 가드는 영원히 물지 않고**, 물지 않는 가드는
그 자리가 지켜지고 있다는 잘못된 안심을 준다. 그 CHECK 가 보는 것은 옛 줄이 아니라
**앞으로**다.

**조이기 전에 묻는다** — 제약이 먼저 걸리면 배포하는 사람이 무엇을 고쳐야 하는지
모른 채로 멈춘다. `b41d7c8e5a92` 가 CodeRabbit 리뷰 NC-126 으로 같은 자리를
고쳤는데 **자기 리비전 안에서만 고쳤고**, 형제인 이쪽이 남아 있었다(감사 ⑩ NC-129).

**올릴 때 잠근다.** `inspections` 의 유일키가 인덱스를 만들고, CHECK 가
`inspections` 와 `lots` 의 기존 행 전체를 검사하며, `lots` 의 외래키는 **양쪽을
잡으므로** 이 리비전의 외래키가 가리키는 표는 전부 함께 잠기고 그동안 쓰기가
멈춘다(목록을 세지 않는다. 세면 갈린다). `migrations/env.py` 가 전체를 트랜잭션
하나로 감싸므로 커밋까지 유지된다. **칸을 더하는 것만 무해하다** — 기본값이 없어
표를 다시 쓰지 않는다(PG11+).

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
    # **조이기 전에 묻는다.** 앞 스키마는 로트의 도착일과 검사의 판정시각을 잇는
    # 제약을 갖고 있지 않았으므로 「21일에 받아 20일에 판정」인 짝이 설 수 있었고,
    # 방금 그 값을 옮겨 왔다. CHECK 가 먼저 서면 나오는 말은 제약 이름뿐이다.
    op.execute(
        """
        DO $$
        DECLARE backdated text;
        BEGIN
          SELECT string_agg(i.id::text, ', ' ORDER BY i.id) INTO backdated
          FROM inspections AS i
          WHERE i.received_date IS NOT NULL AND i.judged_at::date < i.received_date;
          IF backdated IS NOT NULL THEN
            RAISE EXCEPTION
              '판정이 도착보다 앞선 검사가 있다: %. 어느 날짜가 오기인지는 사람이 가른다',
              backdated;
          END IF;
        END $$;
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
    # **위 외래키가 못 보는 자리를 여기서 막는다.** 복합 외래키는 한 칸이라도
    # `NULL` 이면 통째로 건너뛰므로, 도착일이 비는 자사 로트가 수입검사를
    # 가리키면서 대조만 빠져나갈 수 있다. 오늘 그 줄을 만드는 쓰기 경로가 없다는
    # 것은 제약의 보증이 아니라 우연이다.
    #
    # **여기에는 조이기 전의 가드를 두지 않는다 — 옛 줄이 걸릴 수 없기 때문이다.**
    # 앞 스키마에서 `inspection_id` 가 찬 로트는 `fk_lot_inspection_item` 때문에
    # 검사와 품목이 같아야 하고, 그 검사는 `ck_inspection_item_is_raw_material` 로
    # 원자재이며, 그러면 로트도 원자재라 `ck_lot_origin_matches_type` 이 공급사로
    # 묶고, `ck_lot_supplied_has_received_date` 가 도착일을 채우게 한다. 사슬이
    # 끊기는 자리가 없다 — **탐침으로 네 갈래를 실제로 막아 보았다.**
    #
    # 그러므로 이 CHECK 가 보는 것은 옛 줄이 아니라 **앞으로**다. 관문 2 가
    # `ck_inspection_item_is_raw_material` 을 넓히는 날 사슬의 둘째 고리가
    # 끊어지고, 그때는 이 자리에도 가드가 필요해진다 — 넓히는 마이그레이션이
    # 그것을 함께 들고 와야 한다.
    op.create_check_constraint(
        "ck_lot_from_an_inspection_has_an_arrival_date",
        "lots",
        "inspection_id IS NULL OR received_date IS NOT NULL",
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

    op.drop_constraint("ck_lot_from_an_inspection_has_an_arrival_date", "lots", type_="check")
    op.drop_constraint("fk_lot_inspection_received_date", "lots", type_="foreignkey")
    op.drop_constraint("uq_inspection_id_received_date", "inspections", type_="unique")
    op.drop_constraint("ck_inspection_judged_after_arrival", "inspections", type_="check")
    op.drop_column("inspections", "received_date")
