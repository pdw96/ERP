"""초기 스키마 — 기준정보 열셋과 로트

표 열넷을 한 번에 굽는다. 조각마다 리비전을 내면 같은 표를 여러 번 다시 만들게
되므로 **재시드가 한 번으로 끝나지 않는다.**

**자동 생성을 그대로 믿지 않는다.** Alembic 은 CHECK 식을 실행 시점 방언으로
문자열로 박으면서 바꾼다 — `LIKE 'FG-%'` 의 퍼센트를 두 번 적어 넣었고, 그것이
데이터베이스까지 들어갔다. 다시 생성할 때마다 또 들어가므로 손으로 되돌린다.
`tests/test_migrations.py` 가 두 스키마를 실제로 만들어 견주므로, 이 파일을
손보든 다시 생성하든 **그 테스트를 돌려 보고 나서** 믿는다.

Revision ID: 3c602ffaebc3
Revises:
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3c602ffaebc3"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "code_groups",
        sa.Column("group_code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("value_fixed", sa.Boolean(), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.PrimaryKeyConstraint("group_code"),
    )
    op.create_table(
        "non_working_periods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.String(length=100), nullable=False),
        sa.CheckConstraint(
            "btrim(reason, E' \\t\\n\\r\\u3000\\u00a0') <> ''",
            name="ck_non_working_period_reason",
        ),
        sa.CheckConstraint("ends_at > starts_at", name="ck_non_working_period_order"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "partners",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("partner_type", sa.String(length=10), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.CheckConstraint(
            "btrim(code, E' \\t\\n\\r\\u3000\\u00a0') <> ''", name="ck_partner_code_is_present"
        ),
        sa.CheckConstraint(
            "btrim(name, E' \\t\\n\\r\\u3000\\u00a0') <> ''", name="ck_partner_name_is_present"
        ),
        sa.CheckConstraint("partner_type IN ('공급사', '고객사')", name="ck_partner_type"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "partner_type", name="uq_partner_id_type"),
    )
    op.create_index(op.f("ix_partners_code"), "partners", ["code"], unique=True)
    op.create_index(
        op.f("ix_partners_partner_type"), "partners", ["partner_type"], unique=False
    )
    op.create_table(
        "common_codes",
        sa.Column("group_code", sa.String(length=20), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.CheckConstraint(
            "btrim(code, E' \\t\\n\\r\\u3000\\u00a0') <> ''",
            name="ck_common_code_code_is_present",
        ),
        sa.CheckConstraint(
            "btrim(name, E' \\t\\n\\r\\u3000\\u00a0') <> ''",
            name="ck_common_code_name_is_present",
        ),
        sa.ForeignKeyConstraint(
            ["group_code"],
            ["code_groups.group_code"],
        ),
        sa.PrimaryKeyConstraint("group_code", "code"),
    )
    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("item_type", sa.String(length=20), nullable=False),
        sa.Column("process", sa.String(length=30), nullable=True),
        sa.Column(
            "process_group", sa.String(length=20), server_default="PROCESS", nullable=False
        ),
        sa.Column("stock_uom", sa.String(length=30), nullable=False),
        sa.Column(
            "stock_uom_group", sa.String(length=20), server_default="UOM", nullable=False
        ),
        sa.Column("phase", sa.String(length=10), server_default="초기", nullable=False),
        sa.Column("shelf_life_days", sa.Integer(), nullable=True),
        sa.Column("safety_stock", sa.Float(), nullable=True),
        sa.Column("setup_hours", sa.Float(), nullable=True),
        sa.Column("hours_per_unit", sa.Float(), nullable=True),
        sa.CheckConstraint(
            "(item_type = '완제품' AND code LIKE 'FG-%') OR (item_type = '반제품' AND code LIKE 'SF-%') OR (item_type = '원자재' AND code LIKE 'RM-%')",
            name="ck_item_code_prefix",
        ),
        sa.CheckConstraint(
            "btrim(code, E' \\t\\n\\r\\u3000\\u00a0') <> ''", name="ck_item_code_is_present"
        ),
        sa.CheckConstraint(
            "btrim(name, E' \\t\\n\\r\\u3000\\u00a0') <> ''", name="ck_item_name_is_present"
        ),
        sa.CheckConstraint(
            "item_type <> '반제품' OR shelf_life_days IS NULL",
            name="ck_item_semi_finished_has_no_shelf_life",
        ),
        sa.CheckConstraint(
            "item_type <> '원자재' OR safety_stock IS NOT NULL",
            name="ck_item_raw_material_has_safety_stock",
        ),
        sa.CheckConstraint("item_type IN ('완제품', '반제품', '원자재')", name="ck_item_type"),
        sa.CheckConstraint("phase IN ('초기', '양산')", name="ck_item_phase"),
        sa.CheckConstraint("process_group = 'PROCESS'", name="ck_item_process_group"),
        sa.CheckConstraint("stock_uom_group = 'UOM'", name="ck_item_stock_uom_group"),
        sa.CheckConstraint(
            "hours_per_unit IS NULL OR (hours_per_unit >= 0 AND hours_per_unit > '-Infinity'::double precision AND hours_per_unit < 'Infinity'::double precision)",
            name="ck_item_hours_per_unit",
        ),
        sa.CheckConstraint(
            "safety_stock IS NULL OR (safety_stock >= 0 AND safety_stock > '-Infinity'::double precision AND safety_stock < 'Infinity'::double precision)",
            name="ck_item_safety_stock",
        ),
        sa.CheckConstraint(
            "setup_hours IS NULL OR (setup_hours >= 0 AND setup_hours > '-Infinity'::double precision AND setup_hours < 'Infinity'::double precision)",
            name="ck_item_setup_hours",
        ),
        sa.CheckConstraint(
            "shelf_life_days IS NULL OR shelf_life_days > 0", name="ck_item_shelf_life"
        ),
        sa.ForeignKeyConstraint(
            ["process_group", "process"],
            ["common_codes.group_code", "common_codes.code"],
            name="fk_item_process",
        ),
        sa.ForeignKeyConstraint(
            ["stock_uom_group", "stock_uom"],
            ["common_codes.group_code", "common_codes.code"],
            name="fk_item_stock_uom",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "item_type", name="uq_item_id_type"),
    )
    op.create_index(op.f("ix_items_code"), "items", ["code"], unique=True)
    op.create_index(op.f("ix_items_item_type"), "items", ["item_type"], unique=False)
    op.create_table(
        "nonconformity_attributes",
        sa.Column(
            "group_code", sa.String(length=20), server_default="NC_REASON", nullable=False
        ),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("measure_kind", sa.String(length=10), nullable=False),
        sa.Column("inspection_item_code", sa.String(length=30), nullable=True),
        sa.Column(
            "inspection_item_group",
            sa.String(length=20),
            server_default="INSP_ITEM",
            nullable=False,
        ),
        sa.CheckConstraint("group_code = 'NC_REASON'", name="ck_nonconformity_attribute_group"),
        sa.CheckConstraint(
            "inspection_item_group = 'INSP_ITEM'", name="ck_nonconformity_attribute_item_group"
        ),
        sa.CheckConstraint(
            "measure_kind <> '계량' OR inspection_item_code IS NOT NULL",
            name="ck_nonconformity_attribute_measured_needs_item",
        ),
        sa.CheckConstraint(
            "measure_kind IN ('계량', '계수')", name="ck_nonconformity_attribute_kind"
        ),
        sa.ForeignKeyConstraint(
            ["group_code", "code"],
            ["common_codes.group_code", "common_codes.code"],
            name="fk_nonconformity_attribute",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_item_group", "inspection_item_code"],
            ["common_codes.group_code", "common_codes.code"],
            name="fk_nonconformity_attribute_item",
        ),
        sa.PrimaryKeyConstraint("group_code", "code"),
    )
    op.create_table(
        "process_inspection_standards",
        sa.Column("process_code", sa.String(length=30), nullable=False),
        sa.Column(
            "process_group", sa.String(length=20), server_default="PROCESS", nullable=False
        ),
        sa.Column("item_code", sa.String(length=30), nullable=False),
        sa.Column(
            "item_group", sa.String(length=20), server_default="INSP_ITEM", nullable=False
        ),
        sa.Column("upper_spec_limit", sa.Float(), nullable=True),
        sa.Column("lower_spec_limit", sa.Float(), nullable=True),
        sa.Column("center_line", sa.Float(), nullable=True),
        sa.Column("warning_ratio", sa.Float(), server_default="0.70", nullable=False),
        sa.Column("sigma", sa.Float(), nullable=True),
        sa.Column("sigma_source", sa.String(length=10), server_default="미정", nullable=False),
        sa.Column("time_variant", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.CheckConstraint(
            "(sigma IS NULL) = (sigma_source = '미정')",
            name="ck_inspection_standard_sigma_matches_source",
        ),
        sa.CheckConstraint(
            "item_group = 'INSP_ITEM'", name="ck_inspection_standard_item_group"
        ),
        sa.CheckConstraint(
            "process_group = 'PROCESS'", name="ck_inspection_standard_process_group"
        ),
        sa.CheckConstraint(
            "sigma_source IN ('미정', '임의', '실측')",
            name="ck_inspection_standard_sigma_source",
        ),
        sa.CheckConstraint(
            "center_line IS NULL OR ((upper_spec_limit IS NULL OR center_line <= upper_spec_limit) AND (lower_spec_limit IS NULL OR center_line >= lower_spec_limit))",
            name="ck_inspection_standard_center_within_spec",
        ),
        sa.CheckConstraint(
            "sigma IS NULL OR (sigma > 0 AND sigma > '-Infinity'::double precision AND sigma < 'Infinity'::double precision)",
            name="ck_inspection_standard_sigma",
        ),
        sa.CheckConstraint(
            "upper_spec_limit IS NULL OR lower_spec_limit IS NULL OR upper_spec_limit > lower_spec_limit",
            name="ck_inspection_standard_spec_order",
        ),
        sa.CheckConstraint(
            "warning_ratio > 0 AND warning_ratio < 1",
            name="ck_inspection_standard_warning_ratio",
        ),
        sa.ForeignKeyConstraint(
            ["item_group", "item_code"],
            ["common_codes.group_code", "common_codes.code"],
            name="fk_inspection_standard_item",
        ),
        sa.ForeignKeyConstraint(
            ["process_group", "process_code"],
            ["common_codes.group_code", "common_codes.code"],
            name="fk_inspection_standard_process",
        ),
        sa.PrimaryKeyConstraint("process_code", "item_code"),
    )
    op.create_table(
        "purchase_close_attributes",
        sa.Column(
            "group_code", sa.String(length=20), server_default="PO_CLOSE", nullable=False
        ),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("responsibility", sa.String(length=10), nullable=False),
        sa.Column("scorecard_axis", sa.String(length=20), nullable=True),
        sa.Column("reorder_default", sa.String(length=10), nullable=False),
        sa.CheckConstraint("group_code = 'PO_CLOSE'", name="ck_purchase_close_attribute_group"),
        sa.CheckConstraint(
            "reorder_default IN ('필요', '불필요', '건별')",
            name="ck_purchase_close_attribute_reorder",
        ),
        sa.CheckConstraint(
            "responsibility IN ('공급사', '자사')",
            name="ck_purchase_close_attribute_responsibility",
        ),
        sa.CheckConstraint(
            "scorecard_axis IS NULL OR responsibility = '공급사'",
            name="ck_purchase_close_attribute_axis_needs_supplier",
        ),
        sa.CheckConstraint(
            "scorecard_axis IS NULL OR scorecard_axis IN ('수량 준수율', '납기 준수율', '공급 가능성')",
            name="ck_purchase_close_attribute_axis",
        ),
        sa.ForeignKeyConstraint(
            ["group_code", "code"],
            ["common_codes.group_code", "common_codes.code"],
            name="fk_purchase_close_attribute",
        ),
        sa.PrimaryKeyConstraint("group_code", "code"),
    )
    op.create_table(
        "shift_patterns",
        sa.Column("group_code", sa.String(length=20), server_default="SHIFT", nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("starts_at", sa.Time(), nullable=False),
        sa.Column("ends_at", sa.Time(), nullable=False),
        sa.Column("on_site", sa.Boolean(), nullable=False),
        sa.CheckConstraint("group_code = 'SHIFT'", name="ck_shift_pattern_group"),
        sa.CheckConstraint("starts_at <> ends_at", name="ck_shift_pattern_has_length"),
        sa.ForeignKeyConstraint(
            ["group_code", "code"],
            ["common_codes.group_code", "common_codes.code"],
            name="fk_shift_pattern",
        ),
        sa.PrimaryKeyConstraint("group_code", "code"),
    )
    op.create_table(
        "txn_type_attributes",
        sa.Column(
            "group_code", sa.String(length=20), server_default="TXN_TYPE", nullable=False
        ),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("total_effect", sa.String(length=10), nullable=False),
        sa.Column("paired_code", sa.String(length=30), nullable=True),
        sa.Column("source_document_type", sa.String(length=30), nullable=False),
        sa.CheckConstraint("group_code = 'TXN_TYPE'", name="ck_txn_type_attribute_group"),
        sa.CheckConstraint(
            "total_effect IN ('증가', '감소', '양방향', '불변', '기준점')",
            name="ck_txn_type_attribute_effect",
        ),
        sa.CheckConstraint("paired_code <> code", name="ck_txn_type_attribute_pair_not_self"),
        sa.ForeignKeyConstraint(
            ["group_code", "code"],
            ["common_codes.group_code", "common_codes.code"],
            name="fk_txn_type_attribute",
        ),
        sa.ForeignKeyConstraint(
            ["group_code", "paired_code"],
            ["txn_type_attributes.group_code", "txn_type_attributes.code"],
            name="fk_txn_type_attribute_pair",
        ),
        sa.PrimaryKeyConstraint("group_code", "code"),
    )
    op.create_table(
        "bom_components",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_item_id", sa.Integer(), nullable=False),
        sa.Column("parent_item_type", sa.String(length=20), nullable=False),
        sa.Column("child_item_id", sa.Integer(), nullable=False),
        sa.Column("child_item_type", sa.String(length=20), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("unit_quantity", sa.Float(), nullable=False),
        sa.CheckConstraint(
            "(level = 1 AND parent_item_type = '완제품' AND child_item_type = '반제품') OR (level = 2 AND parent_item_type = '반제품' AND child_item_type = '원자재')",
            name="ck_bom_component_level_types",
        ),
        sa.CheckConstraint("parent_item_id <> child_item_id", name="ck_bom_component_not_self"),
        sa.CheckConstraint(
            "unit_quantity >= 0 AND unit_quantity > '-Infinity'::double precision AND unit_quantity < 'Infinity'::double precision",
            name="ck_bom_component_quantity",
        ),
        sa.ForeignKeyConstraint(
            ["child_item_id", "child_item_type"],
            ["items.id", "items.item_type"],
            name="fk_bom_component_child",
        ),
        sa.ForeignKeyConstraint(
            ["parent_item_id", "parent_item_type"],
            ["items.id", "items.item_type"],
            name="fk_bom_component_parent",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "parent_item_id", "child_item_id", name="uq_bom_component_parent_child"
        ),
    )
    op.create_table(
        "lots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(length=20), nullable=False),
        sa.Column("lot_number", sa.String(length=50), nullable=False),
        sa.Column("lot_origin", sa.String(length=10), nullable=False),
        sa.Column("warehouse", sa.String(length=20), nullable=False),
        sa.Column("stock_type", sa.String(length=10), server_default="양품", nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("received_date", sa.Date(), nullable=True),
        sa.Column("produced_date", sa.Date(), nullable=True),
        sa.Column("passed_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("reworked", sa.Boolean(), server_default="false", nullable=False),
        sa.CheckConstraint(
            "(lot_origin = '공급사' AND item_type IN ('원자재')) OR (lot_origin = '자사' AND item_type IN ('반제품', '완제품'))",
            name="ck_lot_origin_matches_type",
        ),
        sa.CheckConstraint(
            "(warehouse = '원재료' AND item_type IN ('원자재')) OR (warehouse = '생산' AND item_type IN ('원자재', '반제품', '완제품')) OR (warehouse = '제품' AND item_type IN ('완제품'))",
            name="ck_lot_warehouse_holds_type",
        ),
        sa.CheckConstraint("NOT reworked OR lot_origin = '자사'", name="ck_lot_rework_is_ours"),
        sa.CheckConstraint(
            "btrim(lot_number, E' \\t\\n\\r\\u3000\\u00a0') <> ''",
            name="ck_lot_number_is_present",
        ),
        sa.CheckConstraint(
            "item_type <> '반제품' OR expiry_date IS NULL",
            name="ck_lot_semi_finished_has_no_expiry",
        ),
        sa.CheckConstraint(
            "lot_origin <> '공급사' OR (received_date IS NOT NULL AND produced_date IS NULL)",
            name="ck_lot_supplied_has_received_date",
        ),
        sa.CheckConstraint(
            "lot_origin <> '자사' OR (produced_date IS NOT NULL AND received_date IS NULL)",
            name="ck_lot_produced_has_produced_date",
        ),
        sa.CheckConstraint("lot_origin IN ('공급사', '자사')", name="ck_lot_origin"),
        sa.CheckConstraint(
            "stock_type <> '불량품' OR warehouse = '제품'",
            name="ck_lot_defective_only_in_finished_warehouse",
        ),
        sa.CheckConstraint("stock_type IN ('양품', '불량품')", name="ck_lot_stock_type"),
        sa.CheckConstraint("warehouse IN ('원재료', '생산', '제품')", name="ck_lot_warehouse"),
        sa.CheckConstraint(
            "expiry_date IS NULL OR expiry_date >= COALESCE(passed_date, received_date, produced_date)",
            name="ck_lot_expires_after_it_exists",
        ),
        sa.CheckConstraint(
            "passed_date IS NULL OR passed_date >= COALESCE(received_date, produced_date)",
            name="ck_lot_passed_after_arrival",
        ),
        sa.CheckConstraint(
            "quantity >= 0 AND quantity > '-Infinity'::double precision AND quantity < 'Infinity'::double precision",
            name="ck_lot_quantity",
        ),
        sa.ForeignKeyConstraint(
            ["item_id", "item_type"], ["items.id", "items.item_type"], name="fk_lot_item"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id", "lot_number", name="uq_lot_item_number"),
    )
    op.create_index(op.f("ix_lots_lot_number"), "lots", ["lot_number"], unique=False)
    op.create_index(op.f("ix_lots_warehouse"), "lots", ["warehouse"], unique=False)
    op.create_table(
        "nonconformity_stage_rules",
        sa.Column(
            "reason_group", sa.String(length=20), server_default="NC_REASON", nullable=False
        ),
        sa.Column("reason_code", sa.String(length=30), nullable=False),
        sa.Column(
            "stage_group", sa.String(length=20), server_default="INSP_STAGE", nullable=False
        ),
        sa.Column("stage_code", sa.String(length=30), nullable=False),
        sa.Column("disposition", sa.String(length=20), nullable=False),
        sa.Column(
            "special_acceptance_allowed", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.CheckConstraint(
            "disposition IN ('반품', '환불', '재작업', '폐기', '등급 하향')",
            name="ck_nonconformity_stage_rule_disposition",
        ),
        sa.CheckConstraint(
            "reason_group = 'NC_REASON'", name="ck_nonconformity_stage_rule_reason_group"
        ),
        sa.CheckConstraint(
            "stage_group = 'INSP_STAGE'", name="ck_nonconformity_stage_rule_stage_group"
        ),
        sa.ForeignKeyConstraint(
            ["reason_group", "reason_code"],
            ["nonconformity_attributes.group_code", "nonconformity_attributes.code"],
            name="fk_nonconformity_stage_rule_reason",
        ),
        sa.ForeignKeyConstraint(
            ["stage_group", "stage_code"],
            ["common_codes.group_code", "common_codes.code"],
            name="fk_nonconformity_stage_rule_stage",
        ),
        sa.PrimaryKeyConstraint("reason_group", "reason_code", "stage_group", "stage_code"),
    )
    op.create_table(
        "supplier_items",
        sa.Column("partner_id", sa.Integer(), nullable=False),
        sa.Column(
            "partner_type", sa.String(length=10), server_default="공급사", nullable=False
        ),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(length=20), server_default="원자재", nullable=False),
        sa.Column("lead_time_hours", sa.Float(), nullable=False),
        sa.Column("purchase_uom", sa.String(length=30), nullable=False),
        sa.Column(
            "purchase_uom_group", sa.String(length=20), server_default="UOM", nullable=False
        ),
        sa.Column("conversion_factor", sa.Float(), server_default="1.0", nullable=False),
        sa.CheckConstraint("item_type = '원자재'", name="ck_supplier_item_is_raw_material"),
        sa.CheckConstraint("partner_type = '공급사'", name="ck_supplier_item_is_supplier"),
        sa.CheckConstraint("purchase_uom_group = 'UOM'", name="ck_supplier_item_uom_group"),
        sa.CheckConstraint(
            "conversion_factor > 0 AND conversion_factor > '-Infinity'::double precision AND conversion_factor < 'Infinity'::double precision",
            name="ck_supplier_item_conversion",
        ),
        sa.CheckConstraint(
            "lead_time_hours >= 0 AND lead_time_hours > '-Infinity'::double precision AND lead_time_hours < 'Infinity'::double precision",
            name="ck_supplier_item_lead_time",
        ),
        sa.ForeignKeyConstraint(
            ["item_id", "item_type"],
            ["items.id", "items.item_type"],
            name="fk_supplier_item_item",
        ),
        sa.ForeignKeyConstraint(
            ["partner_id", "partner_type"],
            ["partners.id", "partners.partner_type"],
            name="fk_supplier_item_partner",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_uom_group", "purchase_uom"],
            ["common_codes.group_code", "common_codes.code"],
            name="fk_supplier_item_uom",
        ),
        sa.PrimaryKeyConstraint("partner_id", "item_id"),
    )


def downgrade() -> None:
    op.drop_table("supplier_items")
    op.drop_table("nonconformity_stage_rules")
    op.drop_index(op.f("ix_lots_warehouse"), table_name="lots")
    op.drop_index(op.f("ix_lots_lot_number"), table_name="lots")
    op.drop_table("lots")
    op.drop_table("bom_components")
    op.drop_table("txn_type_attributes")
    op.drop_table("shift_patterns")
    op.drop_table("purchase_close_attributes")
    op.drop_table("process_inspection_standards")
    op.drop_table("nonconformity_attributes")
    op.drop_index(op.f("ix_items_item_type"), table_name="items")
    op.drop_index(op.f("ix_items_code"), table_name="items")
    op.drop_table("items")
    op.drop_table("common_codes")
    op.drop_index(op.f("ix_partners_partner_type"), table_name="partners")
    op.drop_index(op.f("ix_partners_code"), table_name="partners")
    op.drop_table("partners")
    op.drop_table("non_working_periods")
    op.drop_table("code_groups")
