"""공통코드 — 본체 두 표.

**속성을 여기 밀어 넣지 않는다.** 이 설계의 코드는 대부분 값 하나를 더 갖는데
(불합격 코드는 처분 기본값을, 수불유형은 부호를, 미납 종결 코드는 재발주
기본값을) 그것을 전부 한 표에 넣으면 대부분이 빈 칸이 되고 실무에서 흔한
`attr1 … attr9` 로 끝난다 — 「attr3이 무슨 뜻인지 아무도 모른다」가 그 결말이다.

그래서 두 층으로 가른다. 본체에는 **모든 분류가 함께 쓰는 것**만 두고(코드 ·
명칭 · 정렬 · 사용 여부 · 설명), 코드마다 딸린 속성은 그 코드를 참조하는 작은
표에 둔다.
"""

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.constraints import is_present


class CodeGroup(Base):
    """공통코드 그룹. 프로그램이 이름으로 부르므로 화면에서 늘거나 줄지 않는다.

    행을 추가하는 길이 화면에 없다 — 시드와 마이그레이션만 만든다. 목록은
    `app.core.codes.CODE_GROUPS` 이고, 둘이 어긋나지 않는지는 테스트가 지킨다.
    """

    __tablename__ = "code_groups"

    group_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    # 값이 늘 수 있는가. False 면 값마다 프로그램이 분기한다.
    value_fixed: Mapped[bool] = mapped_column(Boolean)
    description: Mapped[str] = mapped_column(String(300))

    codes: Mapped[list["CommonCode"]] = relationship(back_populates="group")


class CommonCode(Base):
    """공통코드 본체 한 줄.

    **삭제 칸이 없다.** 지우면 그 코드로 적힌 과거 기록이 뜻을 잃으므로, 지우는
    대신 `is_active` 를 끈다 — 새 기록에서는 못 고르고 옛 기록에서는 읽힌다.
    원칙 ⑦(일어난 일은 지우지 않는다)의 코드판이다.

    **코드값은 이름이 아니라 주소다.** 명칭과 설명은 뜻이 그대로인 한 고칠 수
    있지만 코드값은 고치지 않는다 — 고치면 과거 기록이 가리키는 것이 통째로
    바뀐다. 뜻이 바뀌면 고치는 것이 아니라 새 코드여야 한다.
    """

    __tablename__ = "common_codes"
    __table_args__ = (
        # 코드값이 공백이거나 공백만으로 이루어질 수 없다. 주소가 비면 그 줄을
        # 가리키는 모든 기록이 갈 곳을 잃는다.
        CheckConstraint(is_present("code"), name="ck_common_code_code_is_present"),
        CheckConstraint(is_present("name"), name="ck_common_code_name_is_present"),
    )

    group_code: Mapped[str] = mapped_column(
        ForeignKey("code_groups.group_code"), primary_key=True
    )
    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # 드롭다운에 뜨는 차례.
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # 삭제 대신 이것을 끈다. 본체에만 있고 확장 표에는 없다.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    group: Mapped[CodeGroup] = relationship(back_populates="codes")
