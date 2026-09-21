"""관문 1 — 수입검사 한 건을 받는다.

**합격이 로트를 만든다.** 원칙 ① 이 「재고 로트는 합격 후에 생긴다」이므로
로트를 만드는 것은 입고가 아니라 판정이고, 그 판정을 내는 자리가 여기다.

### 계산이 먼저이고 사람이 나중이다 (원칙 ③)

검사원이 넣는 것은 **측정값뿐**이다. 품목을 고르면 자재군이 정해지고, 자재군이
— 단계와 함께 — 항목 목록을 정하고, 항목을 고르면 규격이 딸려 온다. 판정은 그
규격과 측정값에서 **계산되고**, 사람은 계산이 보지 못한 것(세는 항목의 결함)과
계산을 뒤집는 결정(특채)만 적는다.

### 한 트랜잭션이다

검사 · 측정값 · 로트 · 원장 줄이 **한 번에 들어가거나 아무것도 들어가지
않는다.** 「로트는 생겼는데 원장에 줄이 없는」 상태를 없애는 것이 목적이며,
시드에서 「반쯤 채워짐」을 없앤 것과 같은 이유다.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import String, select, text
from sqlalchemy.orm import Session

from app.core import codes, locks
from app.db.code_attributes import NonconformityAttribute, NonconformityStageRule
from app.db.inspection import Inspection, InspectionMeasurement
from app.db.inventory import Lot, StockLedgerEntry
from app.db.master import Item, Partner
from app.db.quality import ProcessInspectionStandard


class RefusedInspection(Exception):
    """받을 수 없는 검사 — 무엇이 왜 막혔는지 이름으로 말한다.

    **제약이 터지기 전에 막는다.** 데이터베이스가 같은 것을 한 번 더 막는 자리도
    있고, 거기서 나오는 말은 제약 이름이라 검사원에게 아무것도 알려 주지 않는다.

    **다만 어떤 갈래는 여기서만 막힌다.** 「그 무리에 기준이 한 줄이라도 있는가」
    같은 조건은 **줄 하나의 제약이 아니라 개수의 규칙**이라 CHECK 로 서지 않고,
    「계산이 이미 이탈을 잡았는가」는 DB 에 대응물이 없다. 미래 입고일은 합격일
    때만 CHECK 에 닿는다 — **불합격은 로트를 만들지 않아 그 자리를 지나간다.**
    그러므로 이 가드들을 「DB 가 어차피 막는다」로 읽고 지우면 **아무것도 재지
    않은 합격**이 다시 선다(NC-68 이 연 자리다).

    **사람에게 하는 말과 기계에게 하는 말을 함께 든다.** 메시지는 한국어 산문이라
    오타를 고칠 수 있어야 하는데, 부르는 쪽이 그 문자열을 보고 갈라지면 **오타를
    고치는 커밋이 밖에서는 파괴적 변경**이 된다. 그래서 갈라지는 자리에는 `code`
    를 둔다 — 「기준을 심으면 같은 요청이 성공하는 건」과 「영영 실패하는 건」이
    그것으로 갈린다.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# ── 거절의 이름 — **밖으로 나가는 약속이다** ────────────────────────────────
#
# 응답의 `detail[].type` 으로 그대로 나간다. 목록이 여기 한 벌이고, 값을 고치는
# 것은 계약을 고치는 것이다. 메시지는 고쳐도 되지만 **이 이름은 고치면 깨진다.**
UNKNOWN_ITEM = "unknown_item"
ITEM_IS_NOT_RAW_MATERIAL = "item_is_not_raw_material"
UNKNOWN_SUPPLIER = "unknown_supplier"
PARTNER_IS_NOT_SUPPLIER = "partner_is_not_supplier"
RECEIVED_DATE_IS_IN_THE_FUTURE = "received_date_is_in_the_future"
NO_STANDARD_FOR_MATERIAL_GROUP = "no_standard_for_material_group"
NOTHING_TO_MEASURE_FOR_MATERIAL_GROUP = "nothing_to_measure_for_material_group"
ITEM_MEASURED_TWICE = "item_measured_twice"
ITEM_IS_NOT_IN_THE_STANDARD = "item_is_not_in_the_standard"
MEASUREMENT_IS_MISSING = "measurement_is_missing"
NO_REASON_FOR_THE_DEVIATION = "no_reason_for_the_deviation"
REASON_IS_NOT_USABLE_AT_THIS_GATE = "reason_is_not_usable_at_this_gate"
REASON_COMES_WITH_A_COMPUTED_DEVIATION = "reason_comes_with_a_computed_deviation"
SPECIAL_ACCEPTANCE_ON_A_PASS = "special_acceptance_on_a_pass"
SPECIAL_ACCEPTANCE_IS_NOT_OPEN = "special_acceptance_is_not_open"
SUPPLIER_IS_NOT_ACTIVE = "supplier_is_not_active"
REASON_IS_NOT_A_COUNTED_ONE = "reason_is_not_a_counted_one"
REASON_IS_DERIVED_BY_THE_SYSTEM = "reason_is_derived_by_the_system"
ITEM_IS_NOT_MEASURED = "item_is_not_measured"
LOT_NUMBER_WOULD_NOT_FIT = "lot_number_would_not_fit"
MATERIAL_IS_ALREADY_EXPIRED = "material_is_already_expired"


@dataclass(frozen=True)
class Measurement:
    """검사원이 적은 실측값 하나."""

    item_code: str
    value: float


@dataclass(frozen=True)
class IncomingInspection:
    """받은 검사 한 건 — 무엇을 · 누구에게 · 얼마를 · 누가."""

    item_code: str
    supplier_code: str
    supplier_lot_number: str
    quantity: float
    judged_by: str
    received_date: date
    measurements: tuple[Measurement, ...]
    # 세는 항목에서 사람이 잡은 결함. 계산은 이것을 보지 못한다.
    nonconformity_code: str | None = None
    # 불합격인데 쓰기로 한 결정. **사람만 낼 수 있다.**
    special_acceptance: bool = False


@dataclass(frozen=True)
class Judged:
    """판정이 끝난 뒤 남은 것."""

    inspection_id: int
    result: str
    nonconformity_code: str | None
    lot_id: int | None
    lot_number: str | None
    ledger_entry_id: int | None


def _item(session: Session, code: str) -> Item:
    item = session.scalars(select(Item).where(Item.code == code)).one_or_none()
    if item is None:
        raise RefusedInspection(UNKNOWN_ITEM, f"그런 품목이 없다: {code}")
    if item.item_type != codes.RAW_MATERIAL:
        raise RefusedInspection(
            ITEM_IS_NOT_RAW_MATERIAL,
            f"관문 1 이 보는 것은 원자재뿐이다 — {code} 는 {item.item_type} 이다",
        )
    return item


def _supplier(session: Session, code: str) -> Partner:
    partner = session.scalars(select(Partner).where(Partner.code == code)).one_or_none()
    if partner is None:
        raise RefusedInspection(UNKNOWN_SUPPLIER, f"그런 거래처가 없다: {code}")
    if partner.partner_type != codes.SUPPLIER:
        raise RefusedInspection(
            PARTNER_IS_NOT_SUPPLIER, f"공급사가 아니다: {code} 는 {partner.partner_type} 이다"
        )
    if not partner.is_active:
        # **그 칸은 지우지 않고 거래를 끝내기 위해 있다.** 지난 줄이 가리키는
        # 거래처를 지울 수 없으므로 꺼 두는 것인데, 꺼진 거래처로 **새 사실**을
        # 만들면 그 칸이 아무것도 뜻하지 않게 된다.
        raise RefusedInspection(SUPPLIER_IS_NOT_ACTIVE, f"거래가 끝난 공급사다: {code}")
    return partner


def _standards(session: Session, material_group: str) -> dict[str, ProcessInspectionStandard]:
    """그 무리에 걸린 수입 기준 — 검사 항목이 주소다."""
    rows = session.scalars(
        select(ProcessInspectionStandard).where(
            ProcessInspectionStandard.process_code.in_(codes.MATERIAL_GROUPED_PROCESSES),
            ProcessInspectionStandard.material_group == material_group,
        )
    ).all()
    return {row.item_code: row for row in rows}


def _measures(standard: ProcessInspectionStandard) -> bool:
    """재는 항목인가 — 규격이 한쪽이라도 있으면 잰다."""
    return standard.upper_spec_limit is not None or standard.lower_spec_limit is not None


def _within_spec(value: float, standard: ProcessInspectionStandard) -> bool:
    if standard.upper_spec_limit is not None and value > standard.upper_spec_limit:
        return False
    return not (standard.lower_spec_limit is not None and value < standard.lower_spec_limit)


def _reason_for(session: Session, item_code: str) -> str:
    """그 항목의 이탈을 적을 **불합격 사유** — 지어내지 않고 기준정보에서 끌어온다.

    사유 코드는 이미 검사 항목을 가리키고 있다(`nonconformity_attributes`). 그
    방향을 뒤집으면 「입도가 벗어났다」에서 `IQ-PSD` 가 나온다 — 항목마다 사유를
    다시 적어 두면 목록이 두 벌이 되고, 두 벌은 갈린다.
    """
    reason = session.scalars(
        select(NonconformityStageRule.reason_code)
        .join(
            NonconformityAttribute,
            (NonconformityAttribute.group_code == NonconformityStageRule.reason_group)
            & (NonconformityAttribute.code == NonconformityStageRule.reason_code),
        )
        .where(
            NonconformityStageRule.stage_code == codes.STAGE_INCOMING,
            NonconformityAttribute.inspection_item_code == item_code,
            NonconformityAttribute.measure_kind == codes.MEASURED_KIND,
        )
        .order_by(NonconformityStageRule.reason_code)
    ).first()
    if reason is None:
        raise RefusedInspection(
            NO_REASON_FOR_THE_DEVIATION,
            f"{item_code} 이 규격을 벗어났는데 그것을 적을 불합격 사유가 없다",
        )
    return reason


def _must_be_a_reason_a_person_inspects(session: Session, reason_code: str) -> None:
    """사람이 적을 수 있는 사유는 **사람이 보는 항목의 것뿐이다** (원칙 ③).

    두 겹이다 —

    **① 재는 항목의 사유는 측정값에서만 나온다.** 그것을 요청에서 받으면 규격 안에
    든 값을 적어 놓고 같은 항목으로 불합격을 만들 수 있고, 특채가 열린 사유라면
    **규격 안인데 특채**라는 줄까지 선다.

    **② 세는 사유 가운데도 시스템이 다는 것이 있다.** `IQ-EXP`(잔여 유효기간
    부족)가 그것이며, 기준정보가 그 사실을 **검사 항목을 가리키지 않는 것**으로
    적어 둔다 — 사람이 들여다볼 항목이 없고 입고일과 설정기간의 비교 결과일
    뿐이기 때문이다. 첫 겹만 보면 이것이 통과해서, **멀쩡한 자재에 사람이
    「유효기간 부족」을 찍는 줄**이 선다(Codex 리뷰 NC-115).

    **코드를 이름으로 세지 않는다.** 「`IQ-EXP` 는 안 된다」로 적으면 같은 성질의
    사유가 느는 날 이 자리가 낡는다 — 가르는 것은 코드값이 아니라 **그 사유가
    가리키는 검사 항목이 있는가**이고, 그것은 기준정보가 이미 들고 있다.
    """
    attribute = session.get(NonconformityAttribute, (codes.NC_REASON, reason_code))
    if attribute is None or attribute.measure_kind != codes.COUNTED_KIND:
        raise RefusedInspection(
            REASON_IS_NOT_A_COUNTED_ONE,
            f"{reason_code} 는 재는 항목의 사유라 사람이 적을 수 없다 —"
            " 재는 항목의 판정은 측정값에서만 나온다",
        )
    if attribute.inspection_item_code is None:
        raise RefusedInspection(
            REASON_IS_DERIVED_BY_THE_SYSTEM,
            f"{reason_code} 는 사람이 보는 검사 항목이 없다 —"
            " 시스템이 계산해 다는 사유라 요청에서 받지 않는다",
        )


def _allows_special_acceptance(session: Session, reason_code: str) -> bool:
    rule = session.get(
        NonconformityStageRule,
        (codes.NC_REASON, reason_code, codes.INSP_STAGE, codes.STAGE_INCOMING),
    )
    if rule is None:
        raise RefusedInspection(
            REASON_IS_NOT_USABLE_AT_THIS_GATE,
            f"관문 1 에서 쓸 수 있는 사유가 아니다: {reason_code}",
        )
    return rule.special_acceptance_allowed


# **칸의 길이를 여기서 다시 적지 않는다.** 모델이 든 것을 그대로 읽는다 — 두
# 벌이면 칸을 넓히는 날 이 검사가 조용히 낡는다.
_lot_number_column = Lot.__table__.c.lot_number.type
assert isinstance(_lot_number_column, String), "로트 번호는 길이가 있는 문자열 칸이다"
_LOT_NUMBER_LENGTH: int = _lot_number_column.length or 0


def _next_lot_number(session: Session, item: Item, received_date: date) -> str:
    """사내 로트 번호 — `RM-01-260921-01`.

    **우리가 짓는다.** 공급사가 붙여 온 번호는 검사 쪽(`supplier_lot_number`)에
    그대로 남는다 — 남이 지은 번호를 우리 유일키에 쓰면 두 공급사가 같은 번호를
    쓸 때 둘째 입고가 거부된다.

    **잠금을 먼저 건다.** 같은 품목·같은 날에 둘이 동시에 들어오면 둘 다 그날의
    마지막 번호를 읽어 **같은 번호를 짓는다.** 유일키가 그 사고를 막기는 하지만
    막는 방식이 「둘째가 터진다」라, 검사원에게는 이유 없는 실패로 보인다.
    품목마다 따로 줄을 세우므로 다른 품목은 기다리지 않는다.

    **번호의 정렬에 기대지 않는다.** 일련이 두 자리를 넘으면 자릿수가 늘어 문자
    정렬이 어긋나지만, FIFO 는 번호가 아니라 로트의 날짜 칸이 든다.
    """
    session.execute(
        text("SELECT pg_advisory_xact_lock(:key, :item)"),
        {"key": locks.LOT_NUMBER, "item": item.id},
    )
    prefix = f"{item.code}-{received_date:%y%m%d}-"
    used = session.scalars(
        select(Lot.lot_number).where(Lot.item_id == item.id, Lot.lot_number.like(f"{prefix}%"))
    ).all()
    serials = [int(number[len(prefix) :]) for number in used if number[len(prefix) :].isdigit()]
    number = f"{prefix}{max(serials, default=0) + 1:02d}"
    if len(number) > _LOT_NUMBER_LENGTH:
        # **지은 번호를 재지 접두만 재지 않는다.** 처음에는 `len(prefix) + 2` 를
        # 봤는데, 일련이 99 를 넘으면 자릿수가 **세 자리로 는다** — 접두가 딱
        # 맞던 품목의 백째 입고에서 번호가 한 자 길어지고, 데이터베이스가 자르려다
        # 터져 실마리 없는 500 이 된다(Codex 리뷰 NC-116).
        #
        # 두 원인(긴 품목 코드 · 늘어난 일련)이 같은 결과를 내므로 **결과를**
        # 잰다. 자릿수를 두 자리로 묶어 막는 쪽은 쓰지 않는다 — 같은 품목이 하루에
        # 백 번 들어오는 것은 일어날 수 있는 일이고, 제약이 사실을 막으면 안 된다.
        raise RefusedInspection(
            LOT_NUMBER_WOULD_NOT_FIT,
            f"지은 로트 번호가 칸({_LOT_NUMBER_LENGTH}자)을 넘는다: {number}",
        )
    return number


def receive(session: Session, request: IncomingInspection) -> Judged:
    """검사 한 건을 받아 판정하고, 합격이면 로트와 원장 줄을 만든다.

    **부르는 쪽이 트랜잭션을 연다.** 이 함수는 `flush` 까지만 하고 커밋하지
    않는다 — 커밋 경계를 여기 두면 엔드포인트가 다른 일을 함께 묶을 수 없다.
    """
    item = _item(session, request.item_code)
    supplier = _supplier(session, request.supplier_code)
    assert item.material_group is not None  # 원자재는 자재군을 갖는다 (CHECK)

    if request.received_date > date.today():
        # **아직 오지 않은 물건은 검사하지 못한다.** 막지 않으면 합격일(오늘)이
        # 입고일보다 앞서 `ck_lot_passed_after_arrival` 이 물고, 검사원은 제약
        # 이름이 담긴 **500** 을 본다 — 잘 만들어진 요청 하나가 실마리 없는
        # 실패로 나가는 자리였다. **같은 값이 불합격이면 201 로 지나갔다**:
        # 불합격은 로트를 만들지 않아 그 CHECK 에 닿지 않기 때문이다.
        raise RefusedInspection(
            RECEIVED_DATE_IS_IN_THE_FUTURE,
            f"아직 오지 않은 날짜다: {request.received_date} —"
            " 받지 않은 물건은 검사할 수 없다",
        )

    standards = _standards(session, item.material_group)
    if not standards:
        # **감사 W-3 이 연 자리다.** 운영자가 새 자재군을 만들고 기준을 한 줄도
        # 넣지 않으면 「아무것도 재지 않고 합격」이 되고, 그 로트는 아무 근거 없이
        # 재고가 된다. 검사가 아니라 그냥 통과이므로 받지 않는다.
        raise RefusedInspection(
            NO_STANDARD_FOR_MATERIAL_GROUP,
            f"{item.material_group} 에 걸린 수입 기준이 한 줄도 없다 —"
            " 기준을 먼저 세우지 않으면 무엇을 보고 판정하는지 표가 말하지 못한다",
        )

    if not any(_measures(standard) for standard in standards.values()):
        # **같은 자리의 한 겹 아래다.** 위의 가드는 「기준이 0줄」만 보므로, 세는
        # 항목(`이물` · `포장`)만 걸린 무리는 통과하고 **측정값이 한 줄도 없는
        # 합격**이 서서 로트와 입고 줄을 만든다. 결정은 위와 같다 — 재지 않은
        # 합격은 검사가 아니라 통과다.
        raise RefusedInspection(
            NOTHING_TO_MEASURE_FOR_MATERIAL_GROUP,
            f"{item.material_group} 에 걸린 수입 기준에 재는 항목이 한 줄도 없다 —"
            " 세는 항목만으로는 무엇을 보고 판정했는지 측정값 줄이 말하지 못한다",
        )

    measured = {
        measurement.item_code: measurement.value for measurement in request.measurements
    }
    counted = Counter(measurement.item_code for measurement in request.measurements)
    twice = sorted(code for code, times in counted.items() if times > 1)
    if twice:
        # **뭉개는 쪽이 아니라 되돌려보내는 쪽이다.** `dict` 는 뒤엣것으로 덮고
        # 그 순간 **판정이 요청 순서에 달린다** — 같은 값 집합을 순서만 바꿔
        # 보내면 합격과 불합격이 뒤집힌다. 측정값 표의 기본키가 이것을 막도록
        # 되어 있지만 **거기까지 가지 않는다**: `dict` 가 먼저 하나로 만든다.
        raise RefusedInspection(
            ITEM_MEASURED_TWICE,
            f"같은 항목을 두 번 쟀다: {', '.join(twice)} —"
            " 어느 값이 그 항목의 값인지 우리가 고르면 사람이 잰 값 하나가 버려진다",
        )
    unknown = sorted(set(measured) - set(standards))
    if unknown:
        raise RefusedInspection(
            ITEM_IS_NOT_IN_THE_STANDARD,
            f"{item.material_group} 의 수입 기준에 없는 항목을 쟀다: {', '.join(unknown)}",
        )
    counted_items = sorted(code for code in measured if not _measures(standards[code]))
    if counted_items:
        # **세는 항목에는 잰 값이 없다.** 그 무리의 기준에 있으므로 위의 검사는
        # 지나가고, 규격 두 칸이 다 빈 측정 줄이 만들어져
        # `ck_inspection_measurement_has_a_spec` 가 문다 — **잘 만들어진 요청
        # 하나가 제약 이름이 담긴 500 으로 나가던** 자리다.
        raise RefusedInspection(
            ITEM_IS_NOT_MEASURED,
            f"세는 항목에는 잰 값을 적을 수 없다: {', '.join(counted_items)} —"
            " 그 항목의 결함은 사유로 적는다",
        )
    missing = sorted(
        code
        for code, standard in standards.items()
        if _measures(standard) and code not in measured
    )
    if missing:
        raise RefusedInspection(
            MEASUREMENT_IS_MISSING, f"재야 하는 항목의 측정값이 없다: {', '.join(missing)}"
        )

    # ── 계산이 판정을 낸다 ──────────────────────────────────────────────────
    # 여럿이 벗어나면 **항목 코드 순서로 첫 하나**를 사유로 적는다. 검사 기록의
    # 사유 칸은 하나이고, 나머지 이탈은 측정값 줄에 박힌 규격에 그대로 남는다.
    out_of_spec = sorted(
        code for code, value in measured.items() if not _within_spec(value, standards[code])
    )

    reason: str | None = None
    if out_of_spec:
        # **조용히 삼키지 않는다.** 사유 칸은 하나인 것이 설계이므로 둘을 함께
        # 적을 수는 없다. 그렇다고 사람이 적어 보낸 것을 **읽지도 않고 버리면**
        # 「입도가 벗어났는데 이물도 섞여 있었다」가 표 어디에도 남지 않고,
        # 없는 코드를 보내도 아무 말이 없다 — 원칙 ⑥ 이 막으려는 자리다.
        if request.nonconformity_code is not None:
            raise RefusedInspection(
                REASON_COMES_WITH_A_COMPUTED_DEVIATION,
                f"계산이 이미 이탈을 잡았다({', '.join(out_of_spec)}) —"
                f" 사유 칸은 하나라 {request.nonconformity_code} 를 함께 적을 수 없다."
                " 측정값만 보내면 계산이 사유를 고른다",
            )
        reason = _reason_for(session, out_of_spec[0])
    elif request.nonconformity_code is not None:
        # **계산이 보지 못하는 것은 사람이 적는다** — 세는 항목의 결함이다.
        _allows_special_acceptance(session, request.nonconformity_code)
        _must_be_a_reason_a_person_inspects(session, request.nonconformity_code)
        reason = request.nonconformity_code

    if reason is None:
        if request.special_acceptance:
            raise RefusedInspection(
                SPECIAL_ACCEPTANCE_ON_A_PASS, "합격인 검사에 특채를 낼 수 없다"
            )
        result = codes.JUDGMENT_PASSED
    elif request.special_acceptance:
        if not _allows_special_acceptance(session, reason):
            raise RefusedInspection(
                SPECIAL_ACCEPTANCE_IS_NOT_OPEN, f"특채가 열려 있지 않은 사유다: {reason}"
            )
        result = codes.JUDGMENT_SPECIAL
    else:
        result = codes.JUDGMENT_FAILED

    judged_at = datetime.now()
    inspection = Inspection(
        item_id=item.id,
        item_type=item.item_type,
        material_group=item.material_group,
        supplier_id=supplier.id,
        supplier_type=supplier.partner_type,
        supplier_lot_number=request.supplier_lot_number,
        quantity=request.quantity,
        # **불합격에도 남는다.** 로트는 합격과 특채에만 서므로 도착일을 로트에만
        # 적으면 **불합격에서만 사라진다** — 클레임과 반품의 근거가 되는 바로 그
        # 판정이다(NC-109). 합격한 줄에서는 로트가 외래키로 이 칸을 가리킨다.
        received_date=request.received_date,
        judged_at=judged_at,
        judged_by=request.judged_by,
        result=result,
        nonconformity_code=reason,
        special_acceptance_allowed=True if result == codes.JUDGMENT_SPECIAL else None,
    )
    session.add(inspection)
    session.flush()

    # ── 판정 시점의 규격을 박아 둔다 ────────────────────────────────────────
    for code, value in sorted(measured.items()):
        standard = standards[code]
        session.add(
            InspectionMeasurement(
                inspection_id=inspection.id,
                item_code=code,
                process_code=standard.process_code,
                material_group=item.material_group,
                measured_value=value,
                applied_upper_spec=standard.upper_spec_limit,
                applied_lower_spec=standard.lower_spec_limit,
            )
        )

    # ── 불합격은 재고가 되지 않는다 ────────────────────────────────────────
    if result == codes.JUDGMENT_FAILED:
        session.flush()
        return Judged(inspection.id, result, reason, None, None, None)

    expiry_date = (
        request.received_date + timedelta(days=item.shelf_life_days)
        if item.shelf_life_days is not None
        else None
    )
    if expiry_date is not None and expiry_date < judged_at.date():
        # **이미 지난 자재가 합격으로 서지 않는다.** 로트의 CHECK 가 같은 것을
        # 막지만 거기서 나오는 말은 제약 이름이라 500 이 된다.
        #
        # **여기서 보는 것은 「이미 지났는가」뿐이다.** 시드의 `IQ-EXP`(잔여
        # 유효기간 부족)는 「며칠은 남아 있어야 하는가」를 묻는데 **그 값이 어디에도
        # 없다** — 지어내지 않고 열어 둔다(`docs/schema.md` 미결).
        raise RefusedInspection(
            MATERIAL_IS_ALREADY_EXPIRED,
            f"입고일({request.received_date})에 설정기간을 더하면 이미 지난 날이다:"
            f" {expiry_date}",
        )

    lot = Lot(
        item_id=item.id,
        item_type=item.item_type,
        lot_number=_next_lot_number(session, item, request.received_date),
        lot_origin=codes.LOT_FROM_SUPPLIER,
        warehouse=codes.WAREHOUSE_RAW,
        stock_type=codes.STOCK_GOOD,
        quantity=request.quantity,
        received_date=request.received_date,
        passed_date=judged_at.date(),
        # **파생해 저장하는 예외 하나.** 라벨에 찍혀 나가므로 설정기간을 나중에
        # 고쳐도 그 로트의 유효기간은 바뀌지 않는다. 설정기간이 없는 자재
        # (시트 · 필름)는 비어서 선다 — 없는 값을 지어내지 않는다.
        #
        # **세는 것은 입고일부터다.** 시드가 `IQ-EXP` 를 「입고일 + 설정기간에서
        # 시스템이 계산해 단다」로 정해 두었다. 판정일부터 세면 **검사가 늦어진
        # 만큼 유효기간이 늘어난다** — 뒤늦게 적은 입고 한 건이 이미 지난 자재를
        # 멀쩡한 재고로 만든다.
        expiry_date=expiry_date,
        inspection_id=inspection.id,
        inspection_result=result,
    )
    session.add(lot)
    session.flush()

    entry = StockLedgerEntry(
        lot_id=lot.id,
        txn_type=codes.TXN_PURCHASE_RECEIPT,
        quantity=request.quantity,
        occurred_at=judged_at,
        inspection_id=inspection.id,
    )
    session.add(entry)
    session.flush()

    return Judged(inspection.id, result, reason, lot.id, lot.lot_number, entry.id)
