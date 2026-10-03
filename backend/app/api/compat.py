"""**계약의 호환 판정** — 들어갈 자리의 계약과 지금 계약을 견주어 판이 움직인 만큼
움직였는지 본다(ADR 0018).

ADR 0012 의 사진(`docs/openapi.json`)은 계약이 바뀌는 것을 **보이게** 할 뿐 막지
않는다 — 계약을 바꾸는 PR 은 사진을 다시 지으므로, 사진과 실제 스펙만 견주면 견줄
옛 계약이 없다. 그래서 판정은 그 옆에 따로 선다: 옛 계약은 **이 변경이 들어갈 자리의
사진**이고(`tests/test_contract_judgment.py` 가 고른다), 새 계약은 지금 코드의 스펙이다.

**무엇을 깨는 변경 · 넓히는 변경으로 세는지의 목록은 `tests/test_contract_judgment.py`
의 판정 테스트 독스트링 한 자리에 있다** — 여기 베끼지 않는다(ADR 0018, 「목록을 두
벌 두지 않는다」). 이 모듈은 그 목록을 코드로 짓는다.

**사진이 못 보는 좁힘은 저자가 가른다.** 기존 경로에 응답의 이름(`x-known-values`)이
늘면 판정은 저자의 선언(`docs/openapi-declarations.json`)을 요구한다 — 받던 요청에 새
이름이 나가는지는 스펙이 말해 주지 않는다. 넓히는 변경이라는 선언은 근거(옛 요청
스키마 밖이던 입력)를 들고, 판정이 그 근거를 옛 사진과 새 스펙에 견주어 본다.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

Kind = Literal["breaking", "widening"]
Side = Literal["request", "response"]

# **글은 계약이 아니다.** 설명 · 제목 · 예시가 바뀌어도 부르는 쪽이 보내는 것과 받는 것은 같다.
_PROSE = frozenset({"description", "title", "summary", "example", "examples", "deprecated"})

# 경계는 **느슨해지는 쪽**이 정해져 있다 — 위 끝은 커지거나 사라지면,
# 아래 끝은 작아지거나 사라지면 느슨해진다
_UPPER = frozenset({"maximum", "exclusiveMaximum", "maxLength", "maxItems", "maxProperties"})
_LOWER = frozenset({"minimum", "exclusiveMinimum", "minLength", "minItems", "minProperties"})

_BRANCHES = ("anyOf", "oneOf")
_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
_VERSION = re.compile(r"\A(\d+)\.(\d+)\Z")
_MISSING: Any = object()


@dataclass(frozen=True)
class Change:
    kind: Kind
    where: str
    what: str


@dataclass(frozen=True)
class NewName:
    """**기존 경로의 응답에 새로 나가는 이름** — 받던 요청에 나가는지는 저자가 가른다."""

    operation: str
    name: str
    where: str


@dataclass
class Diff:
    changes: list[Change] = field(default_factory=list)
    names: list[NewName] = field(default_factory=list)


def version(spec: Mapping[str, Any]) -> tuple[int, int] | None:
    """`info.version` 을 (앞자리, 뒷자리)로 읽는다 — 자리가 둘이 아니면 `None`."""
    matched = _VERSION.match(str(spec.get("info", {}).get("version", "")))
    return (int(matched[1]), int(matched[2])) if matched else None


def compare(old: Mapping[str, Any], new: Mapping[str, Any]) -> Diff:
    """두 스펙 사이의 변화를 깨는 것 · 넓히는 것 · 새 이름으로 가른다."""
    diff = Diff()
    if old.get("openapi") != new.get("openapi"):
        diff.changes.append(Change("breaking", "openapi", "스펙 형식의 판이 바뀌었다"))
    old_paths, new_paths = old.get("paths", {}), new.get("paths", {})
    for path in sorted(set(old_paths) | set(new_paths)):
        for method in _METHODS:
            before = old_paths.get(path, {}).get(method)
            after = new_paths.get(path, {}).get(method)
            key = f"{method.upper()} {path}"
            if before is None and after is not None:
                diff.changes.append(Change("widening", key, "경로가 섰다"))
            elif before is not None and after is None:
                diff.changes.append(Change("breaking", key, "경로가 사라졌다"))
            elif before is not None and after is not None:
                _Operation(diff, key).compare(operation(old, key), operation(new, key))
    return diff


def operation(spec: Mapping[str, Any], key: str) -> dict[str, Any] | None:
    """`"GET /lots"` 의 요청과 응답을 `$ref` 를 풀고 글을 걷어 낸 모양으로 돌려준다."""
    method, _, path = key.partition(" ")
    raw = spec.get("paths", {}).get(path, {}).get(method.lower())
    if raw is None:
        return None
    plain = _Plain(spec)
    body = raw.get("requestBody")
    return {
        "parameters": {
            (p["in"], p["name"]): {
                "required": bool(p.get("required", False)),
                "schema": plain.schema(p.get("schema", {})),
            }
            for p in map(plain.node, raw.get("parameters", []))
        },
        "body": None
        if body is None
        else {
            "required": bool(plain.node(body).get("required", False)),
            "content": plain.content(plain.node(body).get("content", {})),
        },
        "responses": {
            status: {
                "headers": {
                    name: plain.schema(plain.node(header).get("schema", {}))
                    for name, header in plain.node(answer).get("headers", {}).items()
                },
                "content": plain.content(plain.node(answer).get("content", {})),
            }
            for status, answer in raw.get("responses", {}).items()
        },
    }


class _Plain:
    """`$ref` 를 풀고 글을 걷는다 — 같은 계약이면 같은 값이 되게."""

    def __init__(self, spec: Mapping[str, Any]) -> None:
        self._spec = spec

    def node(self, value: Any, seen: tuple[str, ...] = ()) -> Any:
        while isinstance(value, dict) and "$ref" in value and value["$ref"] not in seen:
            seen = (*seen, value["$ref"])
            value = self._look_up(value["$ref"])
        return value

    def content(self, content: Mapping[str, Any]) -> dict[str, Any]:
        return {
            media: self.schema(self.node(body).get("schema", {}))
            for media, body in content.items()
        }

    def schema(self, value: Any, seen: tuple[str, ...] = ()) -> Any:
        if isinstance(value, dict) and "$ref" in value:
            if value["$ref"] in seen:  # 제 자신을 가리키는 스키마 — 이름으로 남긴다
                return {"$ref": value["$ref"]}
            return self.schema(self._look_up(value["$ref"]), (*seen, value["$ref"]))
        if not isinstance(value, dict):
            return value
        plain: dict[str, Any] = {}
        for key, inner in value.items():
            if key in _PROSE:
                continue
            if key == "properties":
                plain[key] = {name: self.schema(s, seen) for name, s in inner.items()}
            elif key in (*_BRANCHES, "allOf", "prefixItems"):
                plain[key] = [self.schema(s, seen) for s in inner]
            elif key in ("items", "not", "additionalProperties") and isinstance(inner, dict):
                plain[key] = self.schema(inner, seen)
            else:
                plain[key] = inner
        return plain

    def _look_up(self, ref: str) -> Any:
        if not ref.startswith("#/"):
            raise ValueError(f"이 스펙 밖을 가리키는 `$ref` 는 읽지 않는다: {ref}")
        found: Any = self._spec
        for part in ref[2:].split("/"):
            found = found[part.replace("~1", "/").replace("~0", "~")]
        return found


class _Operation:
    """경로 하나의 옛 모양과 새 모양을 견준다."""

    def __init__(self, diff: Diff, key: str) -> None:
        self._diff = diff
        self._key = key

    def compare(self, old: Any, new: Any) -> None:
        old_params, new_params = old["parameters"], new["parameters"]
        for where in sorted(set(old_params) | set(new_params)):
            label = f"{where[0]} 인자 `{where[1]}`"
            before, after = old_params.get(where), new_params.get(where)
            if before is None:
                self._note("breaking" if after["required"] else "widening", label, "섰다")
            elif after is None:
                self._note("breaking", label, "사라졌다")
            else:
                self._required(before["required"], after["required"], label)
                self._schema(before["schema"], after["schema"], "request", label)
        self._body(old["body"], new["body"])
        old_answers, new_answers = old["responses"], new["responses"]
        for status in sorted(set(old_answers) | set(new_answers)):
            label = f"응답 {status}"
            before, after = old_answers.get(status), new_answers.get(status)
            if before is None or after is None:
                self._note("breaking", label, "섰다" if before is None else "사라졌다")
                continue
            # 헤더가 느는 것은 모르면 지나치면 되지만, 본문의 미디어 타입이 느는 것은
            # 읽는 법을 모르는 본문이 온다는 뜻이다
            headers, content = f"{label} 헤더", f"{label} 본문"
            self._map(before["headers"], after["headers"], "response", headers, "widening")
            self._map(before["content"], after["content"], "response", content, "breaking")

    def _body(self, old: Any, new: Any) -> None:
        if old is None and new is None:
            return
        if old is None or new is None:
            if new is None:
                self._note("breaking", "요청 본문", "사라졌다")
            else:
                self._note("breaking" if new["required"] else "widening", "요청 본문", "섰다")
            return
        self._required(old["required"], new["required"], "요청 본문")
        self._map(old["content"], new["content"], "request", "요청 본문", "widening")

    def _required(self, old: bool, new: bool, where: str) -> None:
        if old != new:
            self._note("breaking" if new else "widening", where, "필수가 바뀌었다")

    def _map(
        self, old: Mapping[str, Any], new: Mapping[str, Any], side: Side, where: str, came: Kind
    ) -> None:
        """헤더나 미디어 타입처럼 이름으로 묶인 스키마들 — 하나가 서면 `came` 으로 센다."""
        for name in sorted(set(old) | set(new)):
            label = f"{where} `{name}`"
            if name not in old:
                self._note(came, label, "섰다")
            elif name not in new:
                self._note("breaking", label, "사라졌다")
            else:
                self._schema(old[name], new[name], side, label)

    def _schema(self, old: Any, new: Any, side: Side, where: str) -> None:
        if old == new:
            return
        if not isinstance(old, dict) or not isinstance(new, dict):
            self._note("breaking", where, "스키마가 바뀌었다")
            return
        for key in sorted(set(old) | set(new)):
            before, after = old.get(key, _MISSING), new.get(key, _MISSING)
            if before == after:
                continue
            label = f"{where}.{key}"
            if key == "properties":
                self._properties(before, after, side, where)
            elif key == "required":
                self._required_names(before, after, side, where)
            elif key in _BRANCHES:
                self._branches(before, after, side, label)
            elif key == "items" and before is not _MISSING and after is not _MISSING:
                self._schema(before, after, side, f"{where}[]")
            elif key == "enum" and before is not _MISSING and after is not _MISSING:
                self._values(before, after, side, label, opened=False)
            elif key == "x-known-values" and before is not _MISSING and after is not _MISSING:
                self._values(before, after, side, label, opened=True)
            elif key in _UPPER or key in _LOWER:
                self._bound(key, before, after, side, label)
            else:
                self._note("breaking", label, f"{_show(before)} → {_show(after)}")

    def _properties(self, old: Any, new: Any, side: Side, where: str) -> None:
        old, new = old if old is not _MISSING else {}, new if new is not _MISSING else {}
        for name in sorted(set(old) | set(new)):
            label = f"{where}.{name}"
            if name not in old:
                # 요청에서 필수로 선 칸은 `required` 의 변화가 따로 깨는 변경으로 센다
                self._note("widening", label, "칸이 섰다")
            elif name not in new:
                self._note("breaking", label, "칸이 사라졌다")
            else:
                self._schema(old[name], new[name], side, label)

    def _required_names(self, old: Any, new: Any, side: Side, where: str) -> None:
        old = set(old if old is not _MISSING else [])
        new = set(new if new is not _MISSING else [])
        for name in sorted(new - old):
            # 요청에서는 보내야 할 것이 늘고, 응답에서는 늘 오는 것이 는다
            self._note(
                "breaking" if side == "request" else "widening",
                f"{where}.{name}",
                "필수가 됐다",
            )
        for name in sorted(old - new):
            self._note(
                "widening" if side == "request" else "breaking",
                f"{where}.{name}",
                "필수가 풀렸다",
            )

    def _branches(self, old: Any, new: Any, side: Side, where: str) -> None:
        old = list(old if old is not _MISSING else [])
        new = list(new if new is not _MISSING else [])
        gone = [branch for branch in old if branch not in new]
        came = [branch for branch in new if branch not in old]
        if len(gone) == len(came) == 1:  # 갈래 하나가 고쳐졌다 — 그 안으로 들어간다
            self._schema(gone[0], came[0], side, where)
            return
        for _ in came:
            self._note("widening" if side == "request" else "breaking", where, "갈래가 섰다")
        for _ in gone:
            self._note(
                "breaking" if side == "request" else "widening", where, "갈래가 사라졌다"
            )

    def _values(self, old: Any, new: Any, side: Side, where: str, *, opened: bool) -> None:
        for value in [v for v in new if v not in old]:
            if opened and side == "response":
                # **열린 문자열이라 스펙으로는 넓히는 변경이다** — 받던 요청에
                # 나가는지는 저자가 가른다
                self._diff.names.append(NewName(self._key, str(value), where))
            elif side == "request":
                self._note("widening", where, f"값 `{value}` 이 섰다")
            else:  # 닫힌 열거에 응답의 값이 늘면 옛 스펙으로 검증하는 쪽이 응답을 거부한다
                self._note("breaking", where, f"값 `{value}` 이 섰다")
        for value in [v for v in old if v not in new]:
            # 이름을 빼는 것도 · 바꾸는 것(빼고 더하기)도 그 이름에 분기한 쪽을 깬다
            gone_is_safe = side == "response" and not opened
            self._note(
                "widening" if gone_is_safe else "breaking", where, f"값 `{value}` 이 사라졌다"
            )

    def _bound(self, key: str, old: Any, new: Any, side: Side, where: str) -> None:
        if old is _MISSING or new is _MISSING:
            looser = new is _MISSING
        else:
            looser = new > old if key in _UPPER else new < old
        # 요청은 경계가 느슨해지면 받던 것을 다 받고, 응답은 조여지면 오던 것 안에서만 온다
        widening = looser if side == "request" else not looser
        self._note(
            "widening" if widening else "breaking", where, f"{_show(old)} → {_show(new)}"
        )

    def _note(self, kind: Kind, where: str, what: str) -> None:
        self._diff.changes.append(Change(kind, f"{self._key} {where}", what))


def _show(value: Any) -> str:
    return "(없음)" if value is _MISSING else repr(value)


# ── 판정 ───────────────────────────────────────────────────────────────────


def judge(
    old: Mapping[str, Any],
    new: Mapping[str, Any],
    declarations: Mapping[str, Any],
) -> list[str]:
    """**판이 계약이 움직인 만큼 움직였는가.** 빈 목록이면 초록이다.

    옛 판의 앞자리가 0 이면 창이 열려 있던 계약이다 — 무엇이든 받는다(ADR 0012 · 0018).
    """
    before, after = version(old), version(new)
    if before is None or after is None:
        return [f"판이 (앞자리).(뒷자리) 모양이 아니다 — 옛 {before} · 새 {after}"]
    if before[0] == 0:
        return []
    problems: list[str] = []
    diff = compare(old, new)
    breaking = [c for c in diff.changes if c.kind == "breaking"]
    widening = [c for c in diff.changes if c.kind == "widening"]
    declared = _declared(declarations.get(f"{after[0]}.{after[1]}", []), problems)
    for name in diff.names:
        said = declared.get((name.operation, name.name))
        where = f"{name.operation} 의 `{name.name}`({name.where})"
        if said is None:
            problems.append(
                f"{where} 이 새로 나간다 — 받던 요청에 나가는지(깨는 변경) 옛 요청 스키마 밖의"
                f" 입력에만 나가는지(넓히는 변경) `docs/openapi-declarations.json` 의"
                f' "{after[0]}.{after[1]}" 에 선언한다'
            )
        elif said["change"] == "breaking":
            breaking.append(Change("breaking", where, "선언 — 받던 요청에 나간다"))
        else:
            for item in said["because"]:
                why = _not_new(old, new, name.operation, item)
                if why:
                    problems.append(f"{where} 을 넓히는 변경으로 선언했는데 {why}")
            widening.append(Change("widening", where, "선언 — 옛 요청 스키마 밖에만 나간다"))
    moved = f"{before[0]}.{before[1]} → {after[0]}.{after[1]}"
    if breaking and after[0] <= before[0]:
        problems.append(
            f"깨는 변경이 있는데 앞자리가 오르지 않았다({moved}):\n"
            + "\n".join(f"  - {c.where}: {c.what}" for c in breaking)
        )
    elif not breaking and widening and after <= before:
        problems.append(
            f"넓히는 변경이 있는데 판이 오르지 않았다({moved}):\n"
            + "\n".join(f"  - {c.where}: {c.what}" for c in widening)
        )
    elif not breaking and not widening and after != before:
        problems.append(f"계약이 그대로인데 판이 움직였다({moved})")
    elif after < before:
        problems.append(f"판이 뒤로 갔다({moved})")
    return problems


def _declared(entries: Iterable[Any], problems: list[str]) -> dict[tuple[str, str], Any]:
    """선언의 모양을 묻는다 — 모양이 틀린 선언은 선언이 아니다."""
    found: dict[tuple[str, str], Any] = {}
    for entry in entries:
        ok = (
            isinstance(entry, dict)
            and isinstance(entry.get("operation"), str)
            and isinstance(entry.get("name"), str)
            and (
                (entry.get("change") == "breaking" and "because" not in entry)
                or (
                    entry.get("change") == "widening"
                    and isinstance(entry.get("because"), list)
                    and entry["because"]
                    and all(_is_input(item) for item in entry["because"])
                )
            )
        )
        if not ok:
            problems.append(f"선언의 모양이 맞지 않는다: {entry!r}")
            continue
        found[(entry["operation"], entry["name"])] = entry
    return found


def _is_input(item: Any) -> bool:
    return (
        isinstance(item, dict)
        and set(item) <= {"loc", "value"}
        and isinstance(item.get("loc"), list)
        and len(item["loc"]) >= 1
        and all(isinstance(part, str | int) for part in item["loc"])
    )


def _not_new(old: Mapping[str, Any], new: Mapping[str, Any], key: str, item: Any) -> str:
    """근거로 든 입력이 **옛 요청 스키마 밖이고 새 스키마 안인가** — 아니면 그 까닭."""
    loc = item["loc"]
    before = _find(operation(old, key), loc)
    after = _find(operation(new, key), loc)
    if "value" not in item:
        if after is None:
            return f"근거의 칸 {loc} 이 새 요청 스키마에 없다"
        if before is not None:
            return f"근거의 칸 {loc} 이 옛 요청 스키마에도 있었다 — 받던 요청이다"
        return ""
    value = item["value"]
    if after is None or not _accepts(after, value):
        return f"근거의 값 {loc} = {value!r} 을 새 요청 스키마가 받지 않는다"
    if before is not None and _accepts(before, value):
        return f"근거의 값 {loc} = {value!r} 을 옛 요청 스키마도 받았다 — 받던 요청이다"
    return ""


def _find(plain: Any, loc: list[Any]) -> Any:
    """pydantic 의 `loc` 모양으로 요청 스키마를 찾는다.

    `["body", "칸", ...]` 은 본문에서, `["query", "이름", ...]` 은 그 인자에서 내려간다.
    """
    if plain is None:
        return None
    if loc[0] == "body":
        body = plain["body"]
        schema = None if body is None else body["content"].get("application/json")
        rest = loc[1:]
    else:
        if len(loc) < 2:
            return None
        parameter = plain["parameters"].get((loc[0], loc[1]))
        schema = None if parameter is None else parameter["schema"]
        rest = loc[2:]
    for part in rest:
        schema = _step(schema, part)
    return schema


def _step(schema: Any, part: str | int) -> Any:
    if not isinstance(schema, dict):
        return None
    for key in _BRANCHES:
        for branch in schema.get(key, []):
            found = _step(branch, part)
            if found is not None:
                return found
    if isinstance(part, int):
        return schema.get("items")
    return schema.get("properties", {}).get(part)


def _accepts(schema: Any, value: Any) -> bool:
    if not isinstance(schema, dict):
        return False
    if any(key in schema for key in _BRANCHES):
        return any(
            _accepts(branch, value) for key in _BRANCHES for branch in schema.get(key, [])
        )
    if "enum" in schema:
        return value in schema["enum"]
    if "const" in schema:
        return bool(value == schema["const"])
    if isinstance(value, bool):  # `bool` 은 `int` 의 하위형이다 — 수로 읽히지 않게 먼저 가른다
        return schema.get("type") in (None, "boolean")
    kinds = {"string": str, "integer": int, "number": int | float, "boolean": bool}
    wanted = schema.get("type")
    if wanted == "null":
        return value is None
    return wanted not in kinds or isinstance(value, kinds[wanted])
