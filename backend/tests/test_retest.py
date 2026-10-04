"""만료된 로트가 재검사로 돌아온다 — 3단계 재검사 조각의 스키마.

**재검사는 로트를 만들지 않고 있는 로트를 가리킨다.** 합격하면 갱신 만료일이 그 줄에 박히고
(ADR 0017) 불합격하면 그 로트의 잔량 전부가 폐기출고 한 줄로 나간다. 재검사는 경시변화 항목만
잰다.

**「만료된 로트만」은 트리거가 지킨다**(ADR 0016). 로트의 지금 만료일은 다른 표의 여러 줄에서
나오므로 CHECK 로 적을 수 없다. 그래서 이 파일의 절반은 데이터베이스가 **들어오는 순간 묻고, 그
뒤로는 읽은 것이 움직이지 않게 하는지**를 잰다. 마지막 절은 두 연결로 동시에 넣는다 — 한 연결
안의 순차 테스트는 잠금이 없어도 통과한다.

쓰기 경로가 서기 전이라 줄은 전부 SQL 로 넣는다 — 트리거 쪽 하나씩이다. 쓰기 경로 쪽 짝은
그 경로가 서는 조각이 더한다.
"""

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core import codes
from app.db.base import Base
from app.db.code_attributes import (
    NonconformityAttribute,
    NonconformityStageRule,
    TxnTypeAttribute,
)
from app.db.inspection import Inspection, InspectionMeasurement
from app.db.inventory import Lot, PurchaseReturn, StockLedgerEntry
from app.db.master import Item, Partner
from app.db.quality import ProcessInspectionStandard
from tests.factories import add_code, make_item, make_partner, prepare_item_codes

RECEIVED = date(2026, 9, 21)
JUDGED = datetime(2026, 9, 21, 9, 0)
EXPIRES = date(2026, 9, 30)
RETESTED = datetime(2026, 10, 2, 10, 0)
RENEWED = date(2027, 10, 2)
GROUP = "분체"
INCOMING = "수입"
# 경시변화 항목과 그렇지 않은 항목 하나씩.
AGES = "수분"
STAYS = "입도"
REASON = "IQ-MOI"
IN_KIND = "대물"


def _standard(item_code: str, time_variant: bool) -> ProcessInspectionStandard:
    return ProcessInspectionStandard(
        process_code=INCOMING,
        process_group=codes.PROCESS,
        item_code=item_code,
        item_group=codes.INSP_ITEM,
        material_group=GROUP,
        material_group_group=codes.MATERIAL_GROUP,
        upper_spec_limit=50.0,
        lower_spec_limit=10.0,
        center_line=30.0,
        warning_ratio=codes.DEFAULT_WARNING_RATIO,
        sigma_source=codes.SIGMA_UNDECIDED,
        time_variant=time_variant,
        unit="%",
    )


def _plant(session: Session) -> None:
    """만료일이 지난 로트 하나(500, 입고 줄까지)와 그것을 잴 기준 둘."""
    prepare_item_codes(session)
    add_code(session, codes.INSP_STAGE, codes.STAGE_INCOMING, "수입검사")
    add_code(session, codes.INSP_STAGE, codes.RETEST_STAGE, "재검사")
    add_code(session, codes.WAREHOUSE, codes.WAREHOUSE_RAW, "원재료창고")
    add_code(session, codes.SETTLE_TYPE, IN_KIND, "대물정산")
    add_code(session, codes.NC_REASON, REASON, "수분")
    add_code(session, codes.INSP_ITEM, AGES)
    add_code(session, codes.INSP_ITEM, STAYS)
    for txn_type in codes.LEDGER_TXN_TYPES:
        add_code(session, codes.TXN_TYPE, txn_type)
    session.flush()

    session.add_all(
        [
            *(
                TxnTypeAttribute(
                    code=txn_type, total_effect=effect, source_document_type="시험"
                )
                for txn_type, effect in codes.LEDGER_EFFECTS.items()
            ),
            NonconformityAttribute(code=REASON, measure_kind=codes.COUNTED_KIND),
            _standard(AGES, time_variant=True),
            _standard(STAYS, time_variant=False),
        ]
    )
    session.flush()
    session.add_all(
        [
            NonconformityStageRule(
                reason_code=REASON,
                stage_code=stage,
                disposition="폐기" if stage == codes.RETEST_STAGE else "반품",
                special_acceptance_allowed=False,
            )
            for stage in codes.INSPECTION_STAGES_BUILT
        ]
    )

    material = make_item(codes.RAW_MATERIAL, code="RM-01", material_group=GROUP)
    supplier = make_partner(codes.SUPPLIER, code="SUP-01")
    session.add_all([material, supplier])
    session.flush()
    _a_lot(session, material, "RM-01-260921-01", EXPIRES)


def _a_lot(
    session: Session, material: Item, number: str, expires: date | None, *, receipt: bool = True
) -> Lot:
    """IQC 합격 한 건과 그것이 만든 로트 — 넘긴 만료일로, 입고 줄은 넘기면 뺀다."""
    supplier = session.query(Partner).one()
    passed = Inspection(
        item_id=material.id,
        item_type=material.item_type,
        material_group=material.material_group,
        supplier_id=supplier.id,
        supplier_type=supplier.partner_type,
        supplier_lot_number=f"SL-{number}",
        quantity=500.0,
        received_date=RECEIVED,
        judged_at=JUDGED,
        judged_by="검사원 1",
        result=codes.JUDGMENT_PASSED,
    )
    session.add(passed)
    session.flush()
    lot = Lot(
        item_id=material.id,
        item_type=material.item_type,
        lot_number=number,
        lot_origin=codes.LOT_FROM_SUPPLIER,
        warehouse=codes.WAREHOUSE_RAW,
        stock_type=codes.STOCK_GOOD,
        quantity=500.0,
        received_date=RECEIVED,
        expiry_date=expires,
        inspection_id=passed.id,
        inspection_result=passed.result,
    )
    session.add(lot)
    session.flush()
    if receipt:
        session.add(
            StockLedgerEntry(
                lot_id=lot.id,
                inspection_id=passed.id,
                txn_type=codes.TXN_PURCHASE_RECEIPT,
                quantity=500.0,
                occurred_at=datetime(2026, 9, 21, 9, 30),
            )
        )
        session.flush()
    return lot


@pytest.fixture
def prepared(session: Session) -> Session:
    _plant(session)
    return session


def _the_lot(session: Session) -> Lot:
    return session.query(Lot).filter_by(lot_number="RM-01-260921-01").one()


def _retest(
    session: Session,
    result: str = codes.JUDGMENT_PASSED,
    *,
    lot: Lot | None = None,
    **overrides: object,
) -> Inspection:
    """재검사 한 건 — 제약을 통과하는 모양. 넘긴 값만 달라진다."""
    target = lot or _the_lot(session)
    material = session.get(Item, target.item_id)
    assert material is not None
    fields: dict[str, object] = {
        "inspection_stage": codes.RETEST_STAGE,
        "item_id": target.item_id,
        "item_type": target.item_type,
        "material_group": material.material_group,
        "target_lot_id": target.id,
        "judged_at": RETESTED,
        "judged_by": "검사원 1",
        "result": result,
        "nonconformity_code": None if result == codes.JUDGMENT_PASSED else REASON,
        "renewed_expiry_date": RENEWED if result == codes.JUDGMENT_PASSED else None,
    }
    fields.update(overrides)
    return Inspection(**fields)


def _add(session: Session, row: object) -> object:
    session.add(row)
    session.flush()
    return row


def _disposal(
    session: Session, retest: Inspection, quantity: float = 500.0, **overrides: object
) -> StockLedgerEntry:
    """그 재검사의 폐기 줄 — 같은 로트 · 같은 시각 · 잔량 전부. 넘긴 값만 달라진다."""
    lot = session.get(Lot, retest.target_lot_id)
    assert lot is not None
    fields: dict[str, object] = {
        "inspection_id": lot.inspection_id,
        "lot_id": retest.target_lot_id,
        "txn_type": codes.TXN_DISPOSAL,
        "quantity": quantity,
        "occurred_at": retest.judged_at,
        "retest_id": retest.id,
        "retest_result": codes.JUDGMENT_FAILED,
    }
    fields.update(overrides)
    return StockLedgerEntry(**fields)


def _fail_and_dispose(session: Session, **overrides: object) -> Inspection:
    """떨어뜨리고 잔량 전부를 버린다 — 쓰기 경로가 한 트랜잭션에서 할 일."""
    retest = _retest(session, codes.JUDGMENT_FAILED, **overrides)
    _add(session, retest)
    _add(session, _disposal(session, retest))
    return retest


def _balance(session: Session, lot_id: int) -> float:
    return float(
        session.execute(
            text(
                "SELECT coalesce(sum(CASE a.total_effect WHEN '증가' THEN e.quantity"
                " ELSE -e.quantity END), 0)"
                " FROM stock_ledger_entries AS e JOIN txn_type_attributes AS a"
                " ON a.group_code = e.txn_type_group AND a.code = e.txn_type"
                " WHERE e.lot_id = :lot"
            ),
            {"lot": lot_id},
        ).scalar_one()
    )


def _immediately(session: Session) -> None:
    """커밋까지 미뤄 두는 검사를 지금 돌린다 — 테스트 세션은 커밋하지 않고 되돌리므로."""
    session.execute(text("SET CONSTRAINTS retest_failure_has_its_disposal_line IMMEDIATE"))


# ── 재검사의 모양 ───────────────────────────────────────────────────────────


def test_a_passed_retest_renews_the_expiry_on_its_own_row(prepared: Session) -> None:
    """**새 만료일은 재검사 기록에 박히고 로트의 옛 만료일은 그대로다**(원칙 ⑦).

    트리거가 `BEFORE INSERT` 라 지금 만료일을 구할 때 들어오는 줄을 빼고 본다 — `AFTER` 면
    방금 넣은 합격의 갱신 만료일이 「가장 최근」으로 잡혀 이 줄부터 거절된다.
    """
    retest = _add(prepared, _retest(prepared))

    assert isinstance(retest, Inspection)
    assert retest.renewed_expiry_date == RENEWED
    prepared.expire_all()
    assert _the_lot(prepared).expiry_date == EXPIRES


def test_a_retest_names_the_lot_it_looks_at(prepared: Session) -> None:
    """**양방향이다** — 재검사가 로트를 비우면 가리키는 외래키가 통째로 건너뛰어진다."""
    with pytest.raises(IntegrityError, match="ck_inspection_target_lot_only_for_retest"):
        _add(prepared, _retest(prepared, target_lot_id=None))


def test_an_incoming_inspection_does_not_name_a_lot(prepared: Session) -> None:
    """IQC 는 로트를 **만든다** — 가리키지 않는다. 섞이면 로트를 만드는 판정과 다시 보는 판정이
    한 줄에 산다."""
    lot = _the_lot(prepared)
    with pytest.raises(IntegrityError, match="ck_inspection_target_lot_only_for_retest"):
        prepared.execute(
            text("UPDATE inspections SET target_lot_id = :lot WHERE id = :id"),
            {"lot": lot.id, "id": lot.inspection_id},
        )


@pytest.mark.parametrize(
    "delivery",
    [
        {"quantity": 500.0},
        {"supplier_lot_number": "SL-1"},
        {"received_date": RECEIVED},
    ],
    ids=["quantity", "supplier-lot", "arrival"],
)
def test_a_retest_carries_no_delivery(prepared: Session, delivery: dict[str, object]) -> None:
    """**재검사는 들어온 물건이 아니다** — 공급사 · 공급사 로트번호 · 입고 수량 · 도착일은 그
    로트를 만든 IQC 가 든다(원칙 ⑥)."""
    with pytest.raises(IntegrityError, match="ck_inspection_delivery_only_for_incoming"):
        _add(prepared, _retest(prepared, **delivery))


@pytest.mark.parametrize("missing", ["quantity", "supplier_lot_number", "supplier_id"])
def test_an_incoming_inspection_still_names_its_delivery(
    prepared: Session, missing: str
) -> None:
    """칸이 빌 수 있게 된 것은 재검사 때문이다 — IQC 는 여전히 무엇을 누구에게 얼마나 받았는지
    빠짐없이 든다."""
    lot = _the_lot(prepared)
    with pytest.raises(IntegrityError, match="ck_inspection_incoming_names_its_delivery"):
        prepared.execute(
            text(f"UPDATE inspections SET {missing} = NULL WHERE id = :id"),
            {"id": lot.inspection_id},
        )


def test_a_passed_retest_carries_its_new_expiry(prepared: Session) -> None:
    """합격한 재검사가 비워 두면 지금 만료일이 옛 만료일로 남아 곧바로 다시 재검사를 받는다."""
    with pytest.raises(IntegrityError, match="ck_inspection_renewal_only_for_a_passed_retest"):
        _add(prepared, _retest(prepared, renewed_expiry_date=None))


def test_a_failed_retest_renews_nothing(prepared: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_inspection_renewal_only_for_a_passed_retest"):
        _add(prepared, _retest(prepared, codes.JUDGMENT_FAILED, renewed_expiry_date=RENEWED))


def test_an_incoming_inspection_renews_nothing(prepared: Session) -> None:
    lot = _the_lot(prepared)
    with pytest.raises(IntegrityError, match="ck_inspection_renewal_only_for_a_passed_retest"):
        prepared.execute(
            text(
                "UPDATE inspections SET renewed_expiry_date = DATE '2027-01-01' WHERE id = :id"
            ),
            {"id": lot.inspection_id},
        )


def test_a_renewal_does_not_leave_the_lot_expired(prepared: Session) -> None:
    """**합격한 그날 만료된 로트로 남지 않는다** — 판정일보다 이른 갱신 만료일은 받지 않는다."""
    with pytest.raises(IntegrityError, match="ck_inspection_renewal_after_judgement"):
        _add(prepared, _retest(prepared, renewed_expiry_date=date(2026, 10, 1)))


def test_a_renewal_may_end_on_the_day_it_was_judged(prepared: Session) -> None:
    """**경계는 만료 판정과 같다** — 만료일 당일까지는 쓸 수 있으므로 판정일과 같은 갱신
    만료일은 「만료된 채」가 아니다. 계산식(판정일 + 설정기간)은 쓰기 경로가 든다(ADR 0017)."""
    _add(prepared, _retest(prepared, renewed_expiry_date=RETESTED.date()))


def test_a_retest_has_no_special_acceptance(prepared: Session) -> None:
    """**재검사에는 특채가 없다** — 사유의 플래그가 켜져 있어도. 관문 2 가 범위 밖이다."""
    prepared.execute(
        text("UPDATE nonconformity_stage_rules SET special_acceptance_allowed = TRUE")
    )
    with pytest.raises(IntegrityError, match="ck_inspection_retest_has_no_special_acceptance"):
        _add(
            prepared,
            _retest(
                prepared,
                codes.JUDGMENT_SPECIAL,
                renewed_expiry_date=None,
                special_acceptance_allowed=True,
            ),
        )


def test_a_retest_looks_at_a_lot_of_its_own_item(prepared: Session) -> None:
    """**같은 품목의 로트여야 한다** — 다르면 남의 기준으로 잰 재검사가 선다."""
    other = make_item(codes.RAW_MATERIAL, code="RM-02", material_group=GROUP)
    prepared.add(other)
    prepared.flush()
    with pytest.raises(IntegrityError, match="fk_inspection_target_lot"):
        _add(prepared, _retest(prepared, item_id=other.id))


def test_a_retest_cannot_make_a_lot(prepared: Session) -> None:
    """**재검사 줄은 로트를 만들 수 없다** — 로트는 검사를 도착일과 쌍으로 가리키는데 재검사는
    도착일을 비운다. 짝이 없다."""
    retest = _add(prepared, _retest(prepared))
    assert isinstance(retest, Inspection)
    material = prepared.get(Item, retest.item_id)
    assert material is not None
    with pytest.raises(IntegrityError, match="fk_lot_inspection_"):
        _add(
            prepared,
            Lot(
                item_id=material.id,
                item_type=material.item_type,
                lot_number="RM-01-261002-01",
                lot_origin=codes.LOT_FROM_SUPPLIER,
                warehouse=codes.WAREHOUSE_RAW,
                quantity=500.0,
                received_date=RECEIVED,
                inspection_id=retest.id,
                inspection_result=retest.result,
            ),
        )


def test_a_failed_retest_is_not_sent_back_to_the_supplier(prepared: Session) -> None:
    """**반품은 IQC 를 가리킨다.** 불합격한 재검사를 들고 로트를 비우면 「재고가 된 적 없는
    불합격분」이 되는데, 재검사에는 입고 수량이 없어 합의 규칙이 물지 못한다."""
    failed = _fail_and_dispose(prepared)
    with pytest.raises(IntegrityError, match="fk_purchase_return_inspection_stage"):
        _add(
            prepared,
            PurchaseReturn(
                inspection_id=failed.id,
                inspection_result=failed.result,
                lot_id=None,
                settle_type=IN_KIND,
                quantity=100.0,
                returned_at=datetime(2026, 10, 3, 9, 0),
                returned_by="자재 담당 1",
            ),
        )


# ── 측정 — 재검사는 경시변화 항목만 ─────────────────────────────────────────


def _measurement(
    inspection: Inspection, item_code: str, **overrides: object
) -> InspectionMeasurement:
    retest = inspection.inspection_stage == codes.RETEST_STAGE
    fields: dict[str, object] = {
        "inspection_id": inspection.id,
        "item_code": item_code,
        "process_code": INCOMING,
        "material_group": GROUP,
        "inspection_stage": inspection.inspection_stage,
        "standard_time_variant": True if retest else None,
        "measured_value": 30.0,
        "applied_upper_spec": 50.0,
        "applied_lower_spec": 10.0,
        "applied_unit": "%",
    }
    fields.update(overrides)
    return InspectionMeasurement(**fields)


def test_a_retest_measures_what_changes_with_time(prepared: Session) -> None:
    retest = _add(prepared, _retest(prepared))
    assert isinstance(retest, Inspection)

    _add(prepared, _measurement(retest, AGES))


def test_a_retest_does_not_measure_what_time_leaves_alone(prepared: Session) -> None:
    """**경시변화가 아닌 기준은 짝이 없다** — 재검사 줄은 기준을 플래그까지 더해 가리킨다."""
    retest = _add(prepared, _retest(prepared))
    assert isinstance(retest, Inspection)

    with pytest.raises(IntegrityError, match="fk_inspection_measurement_time_variant"):
        _add(prepared, _measurement(retest, STAYS))


def test_a_retest_measurement_cannot_drop_the_flag(prepared: Session) -> None:
    """**양방향이다** — 재검사 측정이 플래그를 비우면 위의 외래키가 통째로 건너뛰어진다."""
    retest = _add(prepared, _retest(prepared))
    assert isinstance(retest, Inspection)

    with pytest.raises(
        IntegrityError, match="ck_inspection_measurement_time_variant_only_for_retest"
    ):
        _add(prepared, _measurement(retest, STAYS, standard_time_variant=None))


def test_a_retest_measurement_cannot_point_with_a_false_flag(prepared: Session) -> None:
    """거짓을 받으면 꺼진 기준을 거짓으로 가리켜 외래키가 막지 못한다."""
    retest = _add(prepared, _retest(prepared))
    assert isinstance(retest, Inspection)

    with pytest.raises(
        IntegrityError, match="ck_inspection_measurement_retest_is_time_variant"
    ):
        _add(prepared, _measurement(retest, STAYS, standard_time_variant=False))


def test_an_incoming_measurement_does_not_lock_the_flag(prepared: Session) -> None:
    """IQC 측정은 플래그를 들지 않는다 — 들면 IQC 가 기준의 플래그를 잠근다."""
    incoming = prepared.get(Inspection, _the_lot(prepared).inspection_id)
    assert incoming is not None

    with pytest.raises(
        IntegrityError, match="ck_inspection_measurement_time_variant_only_for_retest"
    ):
        _add(prepared, _measurement(incoming, AGES, standard_time_variant=True))


def test_a_measurement_says_the_stage_of_its_inspection(prepared: Session) -> None:
    """**단계는 검사에서 온다** — 쌍으로 가리켜, IQC 측정을 재검사로 적어 플래그 규칙을 비켜
    가지 못한다."""
    incoming = prepared.get(Inspection, _the_lot(prepared).inspection_id)
    assert incoming is not None

    with pytest.raises(IntegrityError, match="fk_inspection_measurement_stage"):
        _add(
            prepared,
            _measurement(
                incoming,
                AGES,
                inspection_stage=codes.RETEST_STAGE,
                standard_time_variant=True,
            ),
        )


def test_a_standard_a_retest_relied_on_stays_time_variant(prepared: Session) -> None:
    """**거래 데이터가 자기 근거를 잠근다** — 재검사가 잰 기준의 플래그를 끄면 그 재검사가
    「경시변화가 아닌 것을 잰」 기록이 된다. 가리키던 짝이 사라지므로 끄는 것 자체가 막힌다."""
    retest = _add(prepared, _retest(prepared))
    assert isinstance(retest, Inspection)
    _add(prepared, _measurement(retest, AGES))

    with pytest.raises(IntegrityError, match="fk_inspection_measurement_time_variant"):
        prepared.execute(
            text(
                "UPDATE process_inspection_standards SET time_variant = FALSE"
                " WHERE item_code = :code"
            ),
            {"code": AGES},
        )


# ── 폐기 줄 ─────────────────────────────────────────────────────────────────


def test_a_failed_retest_empties_the_lot_in_one_line(prepared: Session) -> None:
    """**불합격하면 잔량 전부가 폐기출고 한 줄로 나간다**(`docs/PRD-3단계.md` 성공 기준 6)."""
    _fail_and_dispose(prepared)

    assert _balance(prepared, _the_lot(prepared).id) == 0.0


def test_a_disposal_takes_the_whole_balance(prepared: Session) -> None:
    """일부만 버리면 떨어진 물건이 재고에 남는다."""
    retest = _add(prepared, _retest(prepared, codes.JUDGMENT_FAILED))
    assert isinstance(retest, Inspection)

    with pytest.raises(IntegrityError, match="잔량 전부"):
        _add(prepared, _disposal(prepared, retest, 300.0))


def test_a_disposal_names_its_retest(prepared: Session) -> None:
    """**양방향이다** — 폐기 줄이 재검사를 비우면 가리키는 외래키가 통째로 건너뛰어진다."""
    lot = _the_lot(prepared)
    with pytest.raises(IntegrityError, match="ck_stock_ledger_entry_disposal_names_its_retest"):
        _add(
            prepared,
            StockLedgerEntry(
                lot_id=lot.id,
                inspection_id=lot.inspection_id,
                txn_type=codes.TXN_DISPOSAL,
                quantity=500.0,
                occurred_at=RETESTED,
            ),
        )


def test_a_passed_retest_disposes_of_nothing(prepared: Session) -> None:
    """**합격한 재검사로 버리지 못한다** — 판정 칸까지 쌍으로 가리켜 짝이 없다."""
    retest = _add(prepared, _retest(prepared))
    assert isinstance(retest, Inspection)

    with pytest.raises(IntegrityError, match="fk_stock_ledger_entry_retest"):
        _add(prepared, _disposal(prepared, retest))


def test_a_disposal_carries_the_failure_it_follows(prepared: Session) -> None:
    """판정 칸은 재검사와 함께 차고, 차면 불합격이다 — 비면 위의 외래키가 건너뛰어진다."""
    retest = _add(prepared, _retest(prepared, codes.JUDGMENT_FAILED))
    assert isinstance(retest, Inspection)

    with pytest.raises(
        IntegrityError, match="ck_stock_ledger_entry_disposal_follows_a_failure"
    ):
        _add(prepared, _disposal(prepared, retest, retest_result=None))


@pytest.mark.parametrize(
    "change",
    [{"occurred_at": datetime(2026, 10, 3, 9, 0)}, {"lot": "other"}],
    ids=["another-time", "another-lot"],
)
def test_a_disposal_says_what_its_retest_says(
    prepared: Session, change: dict[str, object]
) -> None:
    """**같은 로트 · 같은 시각까지 가리킨다** — 재검사만 가리키면 남의 로트를 버리는 줄이
    선다."""
    retest = _add(prepared, _retest(prepared, codes.JUDGMENT_FAILED))
    assert isinstance(retest, Inspection)
    lot = _the_lot(prepared)
    overrides: dict[str, object] = {}
    if change.get("lot") == "other":
        material = prepared.get(Item, lot.item_id)
        assert material is not None
        other = _a_lot(prepared, material, "RM-01-260921-02", EXPIRES)
        overrides = {"inspection_id": other.inspection_id, "lot_id": other.id}
    else:
        overrides.update(change)

    with pytest.raises(IntegrityError, match="fk_stock_ledger_entry_retest"):
        _add(prepared, _disposal(prepared, retest, **overrides))


def test_one_retest_takes_one_disposal_line(prepared: Session) -> None:
    """둘째 줄이 0 이면 잔량 규칙은 막지 못한다 — 한 재검사에 폐기 줄은 하나다."""
    retest = _fail_and_dispose(prepared)

    with pytest.raises(IntegrityError, match="uq_stock_ledger_entry_one_line_per_retest"):
        _add(prepared, _disposal(prepared, retest, 0.0))


def test_a_failed_retest_cannot_stand_without_its_disposal(prepared: Session) -> None:
    """**판정과 폐기는 함께 선다** — 떨어진 재검사가 홀로 서면 떨어진 물건이 잔량에 남는다."""
    _add(prepared, _retest(prepared, codes.JUDGMENT_FAILED))

    with pytest.raises(IntegrityError, match="원장에 폐기 줄이 없다"):
        _immediately(prepared)


def test_a_failed_retest_with_its_disposal_passes_the_commit_check(prepared: Session) -> None:
    _fail_and_dispose(prepared)

    _immediately(prepared)


def test_a_passed_retest_needs_no_ledger_line(prepared: Session) -> None:
    _add(prepared, _retest(prepared))

    _immediately(prepared)


# ── 들어오는 순간 묻는다 — 만료된 로트에만 (ADR 0016) ─────────────────────


@pytest.mark.parametrize(
    "judged_at",
    [datetime(2026, 9, 29, 10, 0), datetime(2026, 9, 30, 23, 0)],
    ids=["before-expiry", "on-the-expiry-day"],
)
def test_a_lot_that_has_not_expired_is_not_retested(
    prepared: Session, judged_at: datetime
) -> None:
    """**만료일 당일까지는 쓸 수 있다** — 그날의 재검사도 거절된다. 경계는 IQC 가 「이미 지난
    자재」를 가른 것과 같다."""
    with pytest.raises(IntegrityError, match="만료되지 않은 로트는 재검사를 받지 않는다"):
        _add(prepared, _retest(prepared, judged_at=judged_at))


def test_the_day_after_expiry_takes_a_retest(prepared: Session) -> None:
    _add(prepared, _retest(prepared, judged_at=datetime(2026, 10, 1, 0, 0)))


def test_a_lot_without_an_expiry_is_not_retested(prepared: Session) -> None:
    """**만료일이 없으면 만료가 아니다** — SQL 의 NULL 견줌은 막지 못하므로 따로 묻는다."""
    material = prepared.get(Item, _the_lot(prepared).item_id)
    assert material is not None
    forever = _a_lot(prepared, material, "RM-01-260921-02", None)

    with pytest.raises(IntegrityError, match="만료일이 없다"):
        _add(prepared, _retest(prepared, lot=forever))


def test_a_lot_with_nothing_left_is_not_retested(prepared: Session) -> None:
    """**없는 물건을 검사한 기록은 서지 않는다** — 잔량이 0 인 로트."""
    material = prepared.get(Item, _the_lot(prepared).item_id)
    assert material is not None
    empty = _a_lot(prepared, material, "RM-01-260921-02", EXPIRES, receipt=False)

    with pytest.raises(IntegrityError, match="남은 것이 없다"):
        _add(prepared, _retest(prepared, lot=empty))


def test_a_renewed_lot_waits_for_its_new_expiry(prepared: Session) -> None:
    """**지금 만료일은 가장 최근에 합격한 재검사의 것이다** — 갱신된 로트는 새 만료일이 지날
    때까지 다시 재검사를 받지 않는다."""
    _add(prepared, _retest(prepared))

    with pytest.raises(IntegrityError, match="만료되지 않은 로트"):
        _add(prepared, _retest(prepared, judged_at=datetime(2027, 3, 1, 9, 0)))


def test_a_renewed_lot_comes_back_once_the_new_expiry_passes(prepared: Session) -> None:
    _add(prepared, _retest(prepared))

    _add(
        prepared,
        _retest(
            prepared,
            judged_at=datetime(2027, 10, 3, 9, 0),
            renewed_expiry_date=date(2028, 10, 3),
        ),
    )


def test_a_lot_that_failed_its_retest_is_not_retested_again(prepared: Session) -> None:
    """**폐기된 로트는 다시 검사하지 않는다.**"""
    _fail_and_dispose(prepared)

    with pytest.raises(IntegrityError, match="이미 재검사에서 떨어졌다"):
        _add(prepared, _retest(prepared, judged_at=datetime(2026, 10, 3, 9, 0)))


def test_a_failure_still_waiting_for_its_disposal_blocks_a_pass(prepared: Session) -> None:
    """**같은 트랜잭션의 「불합격 → 합격」** — 폐기 줄이 아직 서기 전이라 잔량은 그대로 보이고,
    로트 잠금은 같은 트랜잭션 안에서 다시 잡혀 막지 못한다. 앞선 불합격을 묻는 것이 막는다."""
    _add(prepared, _retest(prepared, codes.JUDGMENT_FAILED))

    with pytest.raises(IntegrityError, match="이미 재검사에서 떨어졌다"):
        _add(prepared, _retest(prepared, judged_at=datetime(2026, 10, 3, 9, 0)))


def test_a_retest_does_not_slip_in_before_an_earlier_one(prepared: Session) -> None:
    """**「가장 최근」은 판정 시각의 순서다** — 끼워 넣으면 지금 만료일이 어느 시점의 것인지
    갈린다."""
    _add(
        prepared,
        _retest(
            prepared,
            judged_at=datetime(2027, 10, 3, 9, 0),
            renewed_expiry_date=date(2028, 10, 3),
        ),
    )

    with pytest.raises(IntegrityError, match="앞선 재검사"):
        _add(prepared, _retest(prepared))


# ── 읽은 것은 움직이지 않는다 (ADR 0016) ────────────────────────────────────


@pytest.mark.parametrize(
    "change",
    [
        "judged_at = TIMESTAMP '2026-09-29 09:00'",
        "renewed_expiry_date = DATE '2030-01-01'",
        "judged_by = '검사원 2'",
    ],
    ids=["judged-at", "renewal", "judge"],
)
def test_a_retest_is_never_rewritten(prepared: Session, change: str) -> None:
    """**재검사 줄은 고치지 않는다** — 판정 시각을 고치면 만료되지 않은 로트로 옮겨 가고, 갱신
    만료일을 고치면 지금 만료일이 소급해 바뀐다. 오기를 고칠 길은 그 길이 서는 조각에서 새
    사실로 연다(원칙 ⑦)."""
    _add(prepared, _retest(prepared))

    with pytest.raises(IntegrityError, match=r"재검사 \d+는 고치지 않는다"):
        prepared.execute(
            text(f"UPDATE inspections SET {change} WHERE inspection_stage = '재검사'")
        )


def test_a_retest_is_never_erased(prepared: Session) -> None:
    """합격 재검사를 지우면 지금 만료일이 기준 만료일로 되돌아가 갱신된 로트가 다시 재검사를
    받는다."""
    _add(prepared, _retest(prepared))

    with pytest.raises(IntegrityError, match="지우지 않는다"):
        prepared.execute(text("DELETE FROM inspections WHERE inspection_stage = '재검사'"))


def test_an_inspection_keeps_the_stage_it_came_in_with(prepared: Session) -> None:
    """**단계는 어느 줄에서도 바뀌지 않는다** — IQC 줄을 재검사로 바꾸며 칸을 한꺼번에 갈아
    끼우면, 재검사 줄의 고정도 들어오는 순간 묻는 트리거도 물지 않는다."""
    with pytest.raises(IntegrityError, match="단계는 바뀌지 않는다"):
        prepared.execute(
            text(
                "UPDATE inspections SET inspection_stage = '재검사'"
                " WHERE inspection_stage = 'IQC'"
            )
        )


def test_an_incoming_inspection_can_still_be_corrected(prepared: Session) -> None:
    """**고정은 재검사와 단계에만 문다** — 반품이 가리키지 않는 IQC 줄의 오기는 지금처럼
    고친다."""
    prepared.execute(
        text("UPDATE inspections SET judged_by = '검사원 2' WHERE inspection_stage = 'IQC'")
    )


@pytest.mark.parametrize("new_expiry", ["DATE '2026-09-01'", "DATE '2027-01-01'", "NULL"])
def test_a_lots_expiry_stays_as_labelled(prepared: Session, new_expiry: str) -> None:
    """**로트의 만료일은 고치지 않는다** — 과거로 돌리면 만료되지 않은 로트가 재검사를 받고,
    앞으로 밀면 이미 선 재검사가 소급해 무효가 된다. 라벨에 찍혀 나간 값이다."""
    with pytest.raises(IntegrityError, match="만료일은 고치지 않는다"):
        prepared.execute(text(f"UPDATE lots SET expiry_date = {new_expiry}"))


# ── 동시에 — 두 연결 ────────────────────────────────────────────────────────


@contextmanager
def _committed_schema(engine: Engine, name: str) -> Iterator[Engine]:
    """커밋이 실제로 일어나는 스키마 하나 — 테스트 세션의 롤백 안에서는 잠금을 잴 수 없다."""
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))
        conn.execute(text(f'CREATE SCHEMA "{name}"'))
    scoped = create_engine(
        engine.url, connect_args={"options": f"-csearch_path={name}"}, poolclass=NullPool
    )
    try:
        Base.metadata.create_all(scoped)
        with Session(scoped) as session:
            _plant(session)
            session.commit()
        yield scoped
    finally:
        scoped.dispose()
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))


def _race(scoped: Engine, first_write: Callable[[Session], None]) -> object:
    """**첫째가 잡은 채로 둘째(합격 재검사)를 보내고, 둘째가 기다리기 시작한 뒤에 첫째를
    커밋한다.** 기다리는지를 보지 않고 커밋하면, 둘째가 첫째의 커밋 뒤에 출발했을 때 잠금이
    없어도 통과한다 — `tests/test_purchase_returns.py` 의 같은 이름 함수와 같은 자리다."""
    first = Session(scoped)
    second = Session(scoped)
    outcome: dict[str, object] = {}
    try:
        first_write(first)
        pid = second.execute(text("SELECT pg_backend_pid()")).scalar_one()

        def go() -> None:
            try:
                second.add(_retest(second, judged_at=datetime(2026, 10, 2, 11, 0)))
                second.flush()
                second.commit()
                outcome["second"] = "committed"
            except IntegrityError as error:
                second.rollback()
                outcome["second"] = error

        racer = threading.Thread(target=go)
        racer.start()
        deadline = time.monotonic() + 10
        with scoped.connect() as watcher:
            while racer.is_alive() and time.monotonic() < deadline:
                waiting = watcher.execute(
                    text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"),
                    {"pid": pid},
                ).scalar_one_or_none()
                if waiting == "Lock":
                    break
                time.sleep(0.02)
        first.commit()
        racer.join(10)
        assert not racer.is_alive(), "둘째가 끝나지 않았다"
    finally:
        first.close()
        second.close()
    return outcome["second"]


def test_two_retests_at_once_do_not_both_find_the_lot_expired(engine: Engine) -> None:
    """**앞의 것이 합격이면** 뒤의 것은 갱신된 만료일을 보고 거절된다 — 잠그지 않으면 둘 다
    「만료」를 보고 함께 선다."""
    with _committed_schema(engine, "retest_race_pass") as scoped:

        def pass_it(session: Session) -> None:
            session.add(_retest(session))
            session.flush()

        second = _race(scoped, pass_it)

        assert isinstance(second, IntegrityError), second
        assert "만료되지 않은 로트" in str(second)


def test_a_retest_behind_a_failure_finds_the_lot_disposed(engine: Engine) -> None:
    """**앞의 것이 불합격이면** 뒤의 것은 그 불합격을 보고 거절된다 — 없는 물건에 합격이 서지
    않는다."""
    with _committed_schema(engine, "retest_race_fail") as scoped:

        def fail_it(session: Session) -> None:
            _fail_and_dispose(session)

        second = _race(scoped, fail_it)

        assert isinstance(second, IntegrityError), second
        assert "이미 재검사에서 떨어졌다" in str(second)
