"""계약의 호환 판정 — 3단계 읽는 조각 B2 (ADR 0018).

ADR 0012 의 사진 대조는 계약이 바뀌는 것을 보이게 할 뿐이고, 계약을 바꾸는 PR 은 사진을 다시
지으므로 그것만으로는 견줄 옛 계약이 없다. 여기서는 **이 변경이 들어갈 자리의 계약**을 git 에서
꺼내 지금 스펙과 견주고(`app/api/compat.py`), 판이 계약이 움직인 만큼 움직였는지 본다.
"""

import copy
import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.api import compat, spec
from app.api.app import API_VERSION, app

_REPO = Path(__file__).resolve().parents[2]
DECLARATIONS = _REPO / "docs" / "openapi-declarations.json"

# **기준을 고르는 것은 CI 다** — `ci.yml` 의 「계약의 기준」 스텝이 PR 에서는 들어갈 브랜치의
# 지금 끝을, `main` 푸시에서는 그 푸시 앞의 끝(`github.event.before`)을 받아 이 변수에 싣는다.
# 로컬에서 변수가 없으면 `origin/main`, 그것도 없으면(원격 이름이 다른 체크아웃) 로컬
# `main` 을 쓴다 — 오래 받지 않았으면 낡은 기준과 견준다. git 저장소가 아닌 소스 묶음에서는
# 기준이 없으므로 실패한다(PR #84 Codex 리뷰).
_BASELINE = "ERP_CONTRACT_BASELINE"
_LOCAL_BASELINES = ("origin/main", "main")


def _baseline() -> dict[str, Any]:
    """**들어갈 자리의 계약** — 읽을 수 없으면 건너뛰지 않고 실패한다(ADR 0018)."""
    given = os.environ.get(_BASELINE)
    snapshot = spec.SNAPSHOT.relative_to(_REPO).as_posix()
    tried: list[str] = []
    for revision in (given,) if given else _LOCAL_BASELINES:
        shown = subprocess.run(
            ["git", "show", f"{revision}:{snapshot}"],
            cwd=_REPO,
            capture_output=True,
            text=True,
            check=False,
        )
        if shown.returncode == 0:
            loaded: dict[str, Any] = json.loads(shown.stdout)
            return loaded
        tried.append(f"{revision}: {shown.stderr.strip()}")
    pytest.fail(
        f"기준 계약({snapshot})을 읽을 수 없다 — `{_BASELINE}` 에 이 변경이 들어갈 자리의 git"
        f" 리비전을 주거나 그 리비전을 받아 둔다:\n" + "\n".join(tried)
    )


def _declarations() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(DECLARATIONS.read_text(encoding="utf-8"))
    return loaded


def test_the_version_moves_as_far_as_the_contract_moved() -> None:
    """**판은 계약이 움직인 만큼 움직인다** — 들어갈 자리의 계약과 견준다(ADR 0018).

    기준의 앞자리가 0 이면 창이 열려 있던 계약이라 무엇이든 받는다. 1 이상이면 —

    - **깨는 변경**이 하나라도 있으면 앞자리가 기준보다 커야 한다
    - 깨는 변경 없이 **넓히는 변경**이 있으면 판이 (앞자리, 뒷자리) 순서로 기준보다 커야 한다
    - 아무 변화도 없으면 판이 그대로여야 한다 — 움직인 판은 거짓 신호다
    - 판은 뒤로 가지 않는다

    **넓히는 변경**(옛 스펙으로 짠 부르는 쪽이 그대로 돈다):

    - 경로 · 메서드가 선다
    - 요청에 필수 아닌 인자 · 칸 · 본문이 선다, 요청의 필수가 풀린다
    - 요청의 닫힌 열거에 값이 선다, 요청의 경계(최대 · 최소 · 길이)가 느슨해지거나
      사라진다, 요청이 받는 갈래(`anyOf` · `oneOf`)가 는다
    - 응답에 칸 · 헤더가 선다, 응답의 칸이 필수가 된다
    - 응답의 경계가 조여진다, 응답이 내는 갈래가 준다
    - 응답의 열린 이름(`x-known-values`)에 값이 선다 — **기존 경로면 저자의 선언이
      든다**(아래)

    **깨는 변경**(그 밖의 모든 것 — 넓히는 것을 놓쳐 앞자리를 올리는 쪽이 깨는 것을
    놓치는 쪽보다 싸다):

    - 경로 · 메서드 · 인자 · 칸 · 헤더 · 요청 본문이 사라진다
    - 요청에 필수 인자 · 칸 · 본문이 선다, 요청의 칸이 필수가 된다
    - 요청의 열거에서 값이 빠진다, 요청의 경계가 조여지거나 새로 선다, 요청이 받는
      갈래가 준다
    - 응답의 필수가 풀린다, 응답의 경계가 느슨해진다, 응답이 내는 갈래가 는다
    - 응답의 닫힌 열거에 값이 선다, 열린 이름이든 닫힌 열거든 **이름이 빠지거나
      바뀐다**
    - 상태 코드가 서거나 사라진다, 응답 본문의 미디어 타입이 서거나 사라진다
    - 그 밖의 키워드(`type` · `format` · `pattern` · `default` ·
      `additionalProperties` …)가 바뀐다, 스펙 형식의 판(`openapi`)이 바뀐다
    - 위에서 가르지 않는 칸이 바뀐다 — `operationId`, 그 경로에 실제로 걸리는 `security`
      (경로에 없으면 스펙 머리의 것), 인자의 `style`, 이름으로 불리는 컴포넌트
      (`securitySchemes` 등) 같은 것이다. 이 칸들은 글만 걷고 통째로 견준다

    글(`description` · `title` · `summary` · 예시)이 바뀌는 것은 어느 쪽도 아니다.
    `$ref` 는 풀어서 견주므로 컴포넌트의 이름만 바뀌는 것도 어느 쪽도 아니다 — `$ref`
    옆에 둔 제약은 풀린 스키마에 합쳐 견준다. 경로 머리의 인자는 그 경로의 메서드마다
    걸린 것으로 견준다.

    **기존 경로의 응답에 이름이 늘면 저자가 가른다** — 판을 올려도, 이름을 바꾸느라
    앞자리를 올려도 그렇다. `docs/openapi-declarations.json` 의 새 판 키 아래에 그 경로와
    이름을 적고 `"change"` 를 고른다. 가르는 선은 옛 요청 스키마다(ADR 0018). 받던
    요청에 나가면 `"breaking"`, 옛 요청 스키마 밖이던 입력에만 나가면 `"widening"` 이고
    그 입력을 `"because"` 에 pydantic 의 `loc` 모양으로 든다 — 새 칸이면
    `{"loc": [...]}`, 닫힌 열거의 새 값이면 `{"loc": [...], "value": ...}`. 판정이 그
    근거가 옛 사진에 없고 새 스펙에 있는지 견준다. 다른 판 키의 선언은 지나간 판의
    기록이라 읽지 않는다.

    **이 검사가 못 보는 부류**(W-6 ③): 이름이 늘지 않는 좁힘(있는 이름의 조건을 조이는
    것 — 리뷰의 몫이다), 선언 밖으로 나가는 응답(ADR 0012 의 결과 그대로다), 그리고
    저자가 받던 요청에 나가는 이름을 넓히는 변경으로 선언하면서 **옛 스키마 밖의 입력을
    하나 덧붙여 근거로 드는 것** — 근거가 참인지는 보지만 그 이름이 근거의 입력에만
    나가는지는 코드를 돌려야 안다.
    """
    problems = compat.judge(_baseline(), app.openapi(), _declarations())
    assert problems == [], "\n".join(problems)


def test_the_declarations_name_where_they_are_read() -> None:
    """선언 파일이 있고 판 키가 (앞자리).(뒷자리) 모양이다 — 틀린 키의 선언은 읽히지 않는다."""
    declared = _declarations()
    for key in declared:
        if key.startswith("$"):
            continue
        assert compat.version({"info": {"version": key}}) is not None, key


def test_the_version_is_one_or_later() -> None:
    """**창은 닫혔다**(ADR 0018) — 앞자리가 0 이면 판정이 무엇이든 받는다."""
    moved = compat.version({"info": {"version": API_VERSION}})
    assert moved is not None and moved[0] >= 1


# ── 판정이 무엇을 가르는가 — 지금 스펙을 옛 계약으로 두고 하나씩 어긋낸다 ──────────────


def _closed() -> dict[str, Any]:
    closed = copy.deepcopy(app.openapi())
    closed["info"]["version"] = "1.0"
    return closed


def _judged(
    change: Callable[[dict[str, Any]], object],
    version: str,
    declarations: dict[str, Any] | None = None,
) -> list[str]:
    old = _closed()
    new = copy.deepcopy(old)
    change(new)
    new["info"]["version"] = version
    return compat.judge(old, new, declarations or {})


def _schema(spec_: dict[str, Any], name: str) -> dict[str, Any]:
    found: dict[str, Any] = spec_["components"]["schemas"][name]
    return found


def _lots(spec_: dict[str, Any]) -> dict[str, Any]:
    found: dict[str, Any] = spec_["paths"]["/lots"]["get"]
    return found


def _limit(spec_: dict[str, Any]) -> dict[str, Any]:
    found: dict[str, Any] = next(p for p in _lots(spec_)["parameters"] if p["name"] == "limit")
    return found


def _optional_field(spec_: dict[str, Any]) -> None:
    _schema(spec_, "RetestIn")["properties"]["note"] = {"type": "string"}


def _required_field(spec_: dict[str, Any]) -> None:
    _optional_field(spec_)
    _schema(spec_, "RetestIn")["required"].append("note")


def _gone_field(spec_: dict[str, Any]) -> None:
    del _schema(spec_, "LotOut")["properties"]["balance"]
    _schema(spec_, "LotOut")["required"].remove("balance")


def _new_answer_field(spec_: dict[str, Any]) -> None:
    _schema(spec_, "LotOut")["properties"]["note"] = {"type": "string"}


def _looser_limit(spec_: dict[str, Any]) -> None:
    _limit(spec_)["schema"]["maximum"] = 500


def _tighter_limit(spec_: dict[str, Any]) -> None:
    _limit(spec_)["schema"]["maximum"] = 100


def _new_status(spec_: dict[str, Any]) -> None:
    _lots(spec_)["responses"]["409"] = copy.deepcopy(_lots(spec_)["responses"]["422"])


def _new_path(spec_: dict[str, Any]) -> None:
    spec_["paths"]["/suppliers"] = {"get": copy.deepcopy(_lots(spec_))}


def _gone_path(spec_: dict[str, Any]) -> None:
    del spec_["paths"]["/lots"]


def _new_type(spec_: dict[str, Any]) -> None:
    _schema(spec_, "LotOut")["properties"]["balance"]["type"] = "string"


def _prose(spec_: dict[str, Any]) -> None:
    spec_["info"]["description"] = "다른 글"
    _schema(spec_, "LotOut")["description"] = "다른 글"


def _new_name(spec_: dict[str, Any]) -> None:
    detail = _schema(spec_, "LotListRefusalDetail")["properties"]["type"]
    detail["x-known-values"].append("limit_is_for_another_list")


def _renamed(spec_: dict[str, Any]) -> None:
    detail = _schema(spec_, "LotListRefusalDetail")["properties"]["type"]
    detail["x-known-values"][0] = "cursor_cannot_be_read"


def _security(spec_: dict[str, Any]) -> None:
    spec_["components"]["securitySchemes"] = {"bearer": {"type": "http", "scheme": "bearer"}}
    spec_["security"] = [{"bearer": []}]


def _security_on_one_path(spec_: dict[str, Any]) -> None:
    _lots(spec_)["security"] = [{"bearer": []}]


def _renamed_operation(spec_: dict[str, Any]) -> None:
    _lots(spec_)["operationId"] = "list_every_lot"


def _bound_beside_a_ref(spec_: dict[str, Any]) -> None:
    answer = _lots(spec_)["responses"]["200"]["content"]["application/json"]["schema"]
    answer["maxProperties"] = 5


def _required_on_the_path(spec_: dict[str, Any]) -> None:
    spec_["paths"]["/lots"]["parameters"] = [
        {"in": "query", "name": "site", "required": True, "schema": {"type": "string"}}
    ]


def _new_name_for_a_new_query(spec_: dict[str, Any]) -> None:
    _new_name(spec_)
    _lots(spec_)["parameters"].append(
        {"in": "query", "name": "sort", "required": False, "schema": {"type": "string"}}
    )


@pytest.mark.parametrize(
    ("change", "stays", "moves"),
    [
        pytest.param(_prose, "1.0", None, id="prose-is-not-the-contract"),
        pytest.param(_optional_field, "1.0", "1.1", id="an-optional-request-field-widens"),
        pytest.param(_required_field, "1.1", "2.0", id="a-required-request-field-breaks"),
        pytest.param(_gone_field, "1.1", "2.0", id="a-field-the-answer-dropped-breaks"),
        pytest.param(_new_answer_field, "1.0", "1.1", id="a-new-answer-field-widens"),
        pytest.param(_looser_limit, "1.0", "1.1", id="a-looser-request-bound-widens"),
        pytest.param(_tighter_limit, "1.1", "2.0", id="a-tighter-request-bound-breaks"),
        pytest.param(_new_status, "1.1", "2.0", id="a-new-status-breaks"),
        pytest.param(_new_path, "1.0", "1.1", id="a-new-path-widens"),
        pytest.param(_gone_path, "1.1", "2.0", id="a-gone-path-breaks"),
        pytest.param(_new_type, "1.1", "2.0", id="a-new-type-breaks"),
        pytest.param(_security, "1.1", "2.0", id="security-for-every-path-breaks"),
        pytest.param(_security_on_one_path, "1.1", "2.0", id="security-on-a-path-breaks"),
        pytest.param(_renamed_operation, "1.1", "2.0", id="a-renamed-operation-breaks"),
        pytest.param(_bound_beside_a_ref, "1.0", "1.1", id="a-bound-beside-a-ref-is-seen"),
        pytest.param(_required_on_the_path, "1.1", "2.0", id="a-required-path-input-breaks"),
    ],
)
def test_the_judgment_asks_for_as_far_as_the_contract_moved(
    change: Callable[[dict[str, Any]], object], stays: str, moves: str | None
) -> None:
    """`stays` 로는 빨갛고 `moves` 로는 초록이다 — `moves` 가 없으면 `stays` 가 초록이다."""
    if moves is None:
        assert _judged(change, stays) == []
        assert _judged(change, "1.1") != [], "계약이 그대로인데 판이 움직였다"
        return
    assert _judged(change, stays) != []
    assert _judged(change, moves) == []


def test_a_window_that_was_open_takes_anything() -> None:
    """옛 판의 앞자리가 0 이면 창이 열려 있던 계약이다(ADR 0012 · 0018)."""
    old = _closed()
    old["info"]["version"] = "0.1"
    new = copy.deepcopy(old)
    _gone_path(new)
    new["info"]["version"] = "0.1"
    assert compat.judge(old, new, {}) == []


def test_the_version_does_not_go_back() -> None:
    assert _judged(_new_path, "0.9") != []


def test_a_version_of_another_shape_is_refused() -> None:
    assert _judged(_new_path, "1.1.0") != []


def test_a_new_name_on_an_old_path_needs_the_authors_word() -> None:
    """**선언이 없으면 빨갛다** — 판을 올려도 받던 요청에 나가는지는 스펙이 말하지 않는다."""
    assert _judged(_new_name, "1.1") != []
    assert _judged(_new_name, "2.0") != []


def _broken(operation: str, name: str) -> dict[str, Any]:
    return {"operation": operation, "name": name, "change": "breaking"}


def test_a_renamed_name_breaks() -> None:
    """**이름을 바꾸는 것은 깨는 변경이다** — 새 이름의 선언이 있어도 앞자리가 올라야 한다."""
    declared = {"2.0": [_broken("GET /lots", "cursor_cannot_be_read")]}
    assert _judged(_renamed, "2.0", declared) == []
    declared = {"1.1": declared["2.0"]}
    assert _judged(_renamed, "1.1", declared) != []


def test_a_name_declared_breaking_moves_the_first_place() -> None:
    declared = {"2.0": [_broken("GET /lots", "limit_is_for_another_list")]}
    assert _judged(_new_name, "2.0", declared) == []
    declared["1.1"] = declared.pop("2.0")
    assert _judged(_new_name, "1.1", declared) != []


def test_a_name_declared_widening_must_point_at_an_input_the_old_schema_did_not_take() -> None:
    """**근거가 옛 사진에 없고 새 스펙에 있어야 한다** — 옛 칸을 근거로 들면 빨갛다."""

    def declared(*because: dict[str, Any]) -> dict[str, Any]:
        return {
            "1.1": [
                {
                    "operation": "GET /lots",
                    "name": "limit_is_for_another_list",
                    "change": "widening",
                    "because": list(because),
                }
            ]
        }

    sort, limit = {"loc": ["query", "sort"]}, {"loc": ["query", "limit"]}
    assert _judged(_new_name_for_a_new_query, "1.1", declared(sort)) == []
    assert _judged(_new_name_for_a_new_query, "1.1", declared(limit)) != []
    assert _judged(_new_name, "1.1", declared(sort)) != []
    assert _judged(_new_name_for_a_new_query, "1.1", declared()) != []


def test_a_declaration_of_another_version_is_not_read() -> None:
    """지나간 판의 선언은 기록이다 — 새 이름을 덮지 않는다."""
    declared = {"1.1": [_broken("GET /lots", "limit_is_for_another_list")]}
    assert _judged(_new_name, "2.0", declared) != []


def test_a_new_enum_value_in_the_request_is_a_reason_for_a_new_name() -> None:
    """닫힌 열거의 새 값을 근거로 들 수 있다 — 옛 열거에 있던 값이면 받던 요청이다."""

    def a_mode(spec_: dict[str, Any], values: list[str]) -> None:
        _lots(spec_)["parameters"].append(
            {"in": "query", "name": "mode", "schema": {"type": "string", "enum": values}}
        )

    old = _closed()
    a_mode(old, ["plain"])
    new = copy.deepcopy(old)
    a_mode(new, ["plain", "strict"])
    _lots(new)["parameters"].pop(-2)
    _new_name(new)
    new["info"]["version"] = "1.1"

    def declared(value: str) -> dict[str, Any]:
        return {
            "1.1": [
                {
                    "operation": "GET /lots",
                    "name": "limit_is_for_another_list",
                    "change": "widening",
                    "because": [{"loc": ["query", "mode"], "value": value}],
                }
            ]
        }

    assert compat.judge(old, new, declared("strict")) == []
    assert compat.judge(old, new, declared("plain")) != []


@pytest.mark.parametrize(("bound", "moves"), [(30, "1.1"), (80, "2.0")])
def test_an_answer_bound_moves_the_other_way(bound: int, moves: str) -> None:
    """**응답의 경계는 요청과 거꾸로 센다** — 조여지면 오던 것 안에서만 오고(넓히는 변경),
    느슨해지면 부르는 쪽이 받아 본 적 없는 값이 온다(깨는 변경)."""
    old = _closed()
    _schema(old, "LotOut")["properties"]["lot_number"]["maxLength"] = 50
    new = copy.deepcopy(old)
    _schema(new, "LotOut")["properties"]["lot_number"]["maxLength"] = bound
    new["info"]["version"] = "1.1" if moves == "2.0" else "1.0"
    assert compat.judge(old, new, {}) != []
    new["info"]["version"] = moves
    assert compat.judge(old, new, {}) == []
