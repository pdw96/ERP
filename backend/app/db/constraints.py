"""제약에 쓰는 식과 참조 — **모델과 마이그레이션이 같은 것을 부른다.**

Alembic 자동 생성은 CHECK 제약을 실행 시점 방언으로 **문자열로** 구워 박는다.
모델이 쓰는 식을 마이그레이션이 그대로 부르지 않으면 둘이 갈리고, 갈린 쪽은
조용히 규칙을 잃는다. 그래서 식을 여기 한 곳에 두고 양쪽이 이것을 부른다.
"""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint

# `btrim` 의 기본은 **스페이스만** 깎는다. 탭도 전각 공백도 남으므로
# `btrim(x) <> ''` 는 「눈에는 비어 보이는데 비어 있지 않은」 값을 통과시킨다.
# 한국어 입력에서 전각 공백(U+3000)은 실제로 섞여 들어오고, 화면에서는 빈 칸과
# 구별되지 않는다. 그래서 깎을 문자를 명시한다.
#
# 스페이스 · 탭 · 개행 · 복귀 · 전각 공백 · 줄바꿈 없는 공백.
BLANK_CHARACTERS = " \\t\\n\\r\\u3000\\u00a0"


def is_present(column: str) -> str:
    """그 칸이 **공백만으로 이루어지지 않았는가.**

    `NOT NULL` 은 「값이 있는가」만 본다. 「그 값이 뜻이 있는가」는 이것이 본다.
    """
    return f"btrim({column}, E'{BLANK_CHARACTERS}') <> ''"


def blank_characters() -> str:
    """SQL 이 깎는 그 글자들을 **파이썬 글자로.**

    경계(pydantic)도 같은 것을 막아야 한다 — 막지 않으면 공백 한 칸이 경계를
    지나 CHECK 에 걸리고, 검사원은 422 대신 **제약 이름이 담긴 500** 을 본다.

    그런데 목록을 경계 쪽에 다시 적으면 **두 벌이 되고 두 벌은 갈린다.** 위의
    상수는 `E'…'` 안에 박히는 이스케이프 형태라 파이썬에서 쓰려면 한 번 풀어야
    하고, **푸는 자리를 여기 하나만 둔다.**
    """
    return BLANK_CHARACTERS.encode("ascii").decode("unicode_escape")


def code_reference(
    *,
    group_column: str,
    code_column: str,
    group_code: str,
    name: str,
) -> tuple[ForeignKeyConstraint, CheckConstraint]:
    """그 칸이 **특정 그룹의 공통코드만** 가리키게 한다.

    공통코드로 모으면 타입이 사라진다 — `common_codes.code` 를 가리키는 칸은
    어느 그룹의 코드든 받는다. 「이 칸에는 불합격사유 그룹만」을 문서가 아니라
    **제약으로** 강제하려면 복합 외래키와 그룹 고정 CHECK 가 함께 서야 한다.

    그룹 칸은 데이터가 아니라 **구조**다. 값이 언제나 같으므로 모델은 기본값을
    두고 CHECK 가 그것을 못박는다.
    """
    return (
        ForeignKeyConstraint(
            [group_column, code_column],
            ["common_codes.group_code", "common_codes.code"],
            name=f"fk_{name}",
        ),
        CheckConstraint(f"{group_column} = '{group_code}'", name=f"ck_{name}_group"),
    )


def is_finite(column: str) -> str:
    """그 칸이 **셀 수 있는 수인가.**

    PostgreSQL 의 `double precision` 은 `NaN` 과 `Infinity` 를 값으로 받고,
    정렬에서 **`NaN` 을 모든 수보다 크게** 둔다. 그래서 `quantity >= 0` 은
    `NaN` 을 그대로 통과시킨다 — 터지지 않고 들어온다.

    들어오고 나면 되돌릴 수 없다. 그 로트 하나가 이후의 모든 합계를 `NaN` 으로
    만들고, `NaN` 과의 비교는 전부 거짓이라 **재고가 조용히 사라진다.** 무한대도
    같은 이유로 막는다 — 더하면 남는 것은 무한대뿐이다.

    하한 비교(`>= 0`)와 **함께** 건다. 이것만으로는 음수를 막지 못하고, 하한만
    으로는 `NaN` 을 막지 못한다.
    """
    return (
        f"{column} > '-Infinity'::double precision"
        f" AND {column} < 'Infinity'::double precision"
    )
