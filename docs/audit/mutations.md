# 돌연변이 기록

**「물게 하는 돌연변이를 실제로 돌려 빨갛게 한 기록이 있을 것」**이 `CLAUDE.md` 의
조건이고, 그 기록이 사는 자리가 정해져 있지 않았다 — 남아 있던 것은 **산문의
주장**뿐이었다(NC-89). `.gitignore` 가 돌연변이를 돌리는 워크트리를 버전관리에서
빼므로 근거가 저장소에 들어올 길이 설계상 닫혀 있었다.

## 이 파일의 규칙

- **돌린 것만 적는다.** 「돌렸을 것이다」는 적지 않는다 — 그것이 NC-89 가 낸 말이다
- **다음 사람이 손으로 재현할 수 있게 적는다**: 무엇을 · 어떻게 어긋냈고 · **어느
  검사가** 빨개졌는가. 검사 이름이 없으면 재현이 아니라 주장이다
- **통과한 돌연변이도 적는다.** 값은 오히려 그쪽에 있다 — 검사가 아무것도 지키지
  않는다는 뜻이기 때문이다
- **묶음마다 잰 커밋을 적는다.** 「그때 빨개졌다」는 그 뒤에 코드가 바뀌면 지금도
  참인지 알 수 없고, **언제의 「그때」인지가 없으면 무엇이 바뀌었는지조차 물을 수
  없다.** 적는 것은 **바탕이 아니라 잰 트리의 커밋**이다 — 「`X` 뒤」는 바탕만
  가리켜 같은 바탕의 두 묶음을 가르지 못한다(실제로 `2fc40f3` 뒤가 둘이고, 옛
  묶음의 그 형태는 소급해 고치지 않는다 — 잰 트리를 지어내는 것이 되기 때문이다).
  `backend/tests/test_prose.py` 가 이 규칙을 문다 (감사 ⑪ NC-132).
  **쓰는 시점에 그 해시를 모르면 회차를 닫을 때 채운다** — 예외를 적지 않았더니
  규칙을 세운 그 회차의 묶음이 「`X` 의 다음 커밋」으로 섰다(감사 ⑫ NC-143)
- 이 파일은 **⑧ 부터의 기록이다.** 그 앞 회차의 돌연변이는 PR 본문이 요약만 들고
  있고, 없는 기록을 소급해 지어내지 않는다

## ⑧ 의 고침 (`03b6c1f`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 65 | `992bb442d985` · `361ec789023c` · `e84fbec436c0` 의 `downgrade()` 에서 `DO $$ … RAISE EXCEPTION` 블록을 지웠다(각각 따로) | `test_downgrade_says_whose_judgements_would_vanish` · `…whose_measurements_would_vanish` · `…which_lots_would_lose_their_ledger` |
| 64 | `backend/.dockerignore` 를 지웠다 | `test_the_build_context_does_not_carry_the_secret_file` |
| 64 | `compose.yaml` 의 `"127.0.0.1:8000:8000"` 을 `"8000:8000"` 으로 | `test_every_published_port_is_bound_to_loopback` |
| 68 | `incoming.py` 의 `if not any(_measures(...)):` 를 `if False:` 로 | `test_a_material_group_with_nothing_to_measure_is_refused` |
| 72 | `incoming.py` 의 `if twice:` 를 `if False:` 로 | `test_measuring_the_same_item_twice_is_refused` |
| 71 | `incoming.py` 의 `if request.nonconformity_code is not None:` 를 `if False:` 로 | `test_a_reason_sent_with_an_out_of_spec_value_is_refused` |
| 74 | `schemas.py` 의 `_present` 에서 `if not value.strip(_BLANK):` 를 `if False:` 로 | `test_the_boundary_refuses_what_only_looks_empty` — **갈래 열둘 전부** |

## ⑧(`audit-contract`) 의 고침 (`72392cf`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 77 | `incoming.py` 의 `if request.received_date > date.today():` 를 `if False:` 로 | `test_a_delivery_that_has_not_arrived_is_refused` |
| 82 | `schemas.py` 의 `ConfigDict(extra="forbid")` 를 `extra="ignore"` 로 | `test_a_field_we_do_not_know_is_refused` |
| 78 | `app.py` 의 `@app.exception_handler(Exception)` 를 `ZeroDivisionError` 로 좁혔다 | `test_a_break_answers_with_json_and_says_nothing_about_the_inside` |
| 75 | `app.py` 의 거절 본문을 `[{"loc": …, "type": refused.code}]` 에서 `[str(refused)]` 로 | `test_both_kinds_of_422_have_the_same_shape` |
| 81 | `schemas.py` 의 `result` 에서 `json_schema_extra={"enum": …}` 를 뺐다 | `test_the_spec_says_which_version_and_which_judgements` |
| **79** | `app.py` 의 `version=API_VERSION` 을 뺐다 | **통과했다.** FastAPI 의 기본 판이 하필 고른 값(`0.1.0`)과 같아 「적었다」와 「안 적었다」가 밖에서 구별되지 않았다 — 판을 `0.1` 로 바꾸고 **기본값과 다른지**까지 보게 고친 뒤 같은 돌연변이가 빨개졌다 |

## ⑨ 의 고침 (`fc940e8`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 87 | `app.py` 의 `session_scope` 에서 `session.commit()` 을 지웠다 | `test_a_pass_is_actually_committed` — **그 전에는 294 개가 전부 초록이었다** |
| 88 | `_sessions()` 를 게으른 형태에서 **모듈 최상단**으로 되돌렸다 | `test_the_app_does_not_reach_for_the_default_database` · `test_a_pass_is_actually_committed` |
| 91 | `ck_lot_passed_after_arrival` 의 `>=` 를 `>` 로 | `test_a_lot_that_arrives_and_passes_on_the_same_day_stands` |
| 90 | `inspections` 에 `UNIQUE (supplier_id, item_id, supplier_lot_number)` 를 **더했다**(NC-67 의 결정을 뒤집는 변경) | `test_the_same_request_twice_makes_two_lots` · `test_a_split_delivery_of_the_same_supplier_lot_is_accepted`. **「둘째는 그날의 다음 일련을 받는다」는 통과했다** — 감사자가 예측한 그대로다 |
| 92 · 86 | `production.py` 의 문장을 「1단계에서는 표만 선다」로 되돌렸다 | `test_a_stage_that_closed_is_not_written_as_if_it_were_now` |
| 86 | 저장소 최상위에 `frontend/` 를 만들었다 | `test_there_is_still_no_screen` |

## 감사 ⑩ 의 고침 (`a98f40d`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 129 | `a7c14b3e9052` 의 `upgrade()` 에서 **조이기 전의 가드**(`판정이 도착보다 앞선 검사가 있다`)를 통째로 지웠다 | `test_upgrading_says_which_judgement_came_before_its_arrival` — 가드가 없으면 `ck_inspection_judged_after_arrival` 이 **제약 이름만** 들고 걸린다 |

**가드를 하나 세우려다 말았고, 그것을 탐침이 정했다.** 감사 ⑩ 이 낸 NC-129 는 두 갈래였는데 둘째(「검사를 가리키는데 도착일이 없는 로트」)는 **옛 줄로 설 수 없었다.** 앞 스키마에서 네 갈래를 실제로 심어 보았고 전부 막혔다 —

| 심어 본 줄 | 막은 것 |
|---|---|
| 공급사 로트의 도착일 비우기 | `ck_lot_supplied_has_received_date` |
| 그 로트를 자사로 바꾸기 | `ck_lot_origin_matches_type` |
| 자사 반제품 로트 세우기 | `ck_lot_warehouse` — 창고 코드가 없어서였고, 심고 다시 했다 |
| 자사 반제품 로트가 수입검사를 가리키기 | **`fk_lot_inspection_item`** — NC-118 이 세운 쌍 외래키가 사슬의 마지막 고리다 |

**닿지 않는 가드는 세우지 않는다.** 물지 않는 가드는 그 자리가 지켜지고 있다는 잘못된 안심을 주고, 그것을 무는 검사는 **통과하면서 아무것도 지키지 않는다.** 사슬을 리비전에 이름으로 적어 두었으므로, 관문 2 가 `ck_inspection_item_is_raw_material` 을 넓혀 둘째 고리를 끊는 날 그 자리가 드러난다.

## 감사 ⑪ 의 고침 (`5f9922c`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 132 | `## 감사 ⑩ 의 고침` 제목에서 커밋을 뗐다 | `test_a_mutation_bundle_says_which_commit_it_was_measured_on` |
| 132 | **이 파일을 통째로 지웠다** | 같은 검사 — 앵커가 물었다. 그 전까지 이 파일은 **지워도 초록**이었다(⑪ OB-3) |
| 132 | 파일은 두고 **고침 묶음만 전부 없앴다** | 같은 검사 — 둘째 앵커가 물었다(훑을 것이 있었는가) |

**전수 단언에 앵커를 함께 걸었다**(⑪ OB-1). 「어긋난 것이 없다」 꼴은 훑은 집합이
비면 그대로 통과하므로, **훑을 것이 있었다**는 것까지 같은 검사가 센다. 이 저장소에
이미 세 자리에 있던 관용구이고 네 자리에 없었다.

## 감사 ⑫ 의 고침 (`f520d26`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 135 | `app.py` 의 `@app.exception_handler(StarletteHTTPException)` 를 `ZeroDivisionError` 로 좁혔다 | `test_a_path_error_answers_in_the_same_shape` — 404·405 의 `detail` 이 다시 문자열이 됐다 |
| 134 | 라우트의 `responses={422: {"model": Refused}}` 를 뺐다 | `test_the_spec_lists_every_refusal_name` |
| 134 | `RefusalDetail.type` 을 `Refusal` 에서 `str` 로 되돌렸다 | 같은 검사 — 스펙에서 `Refusal` 컴포넌트가 통째로 사라진다 |

**둘째와 셋째가 같은 검사를 다른 이유로 물게 한다.** 하나는 **스펙이 그 모양을
가리키지 않는 것**이고 하나는 **가리키는데 이름 목록이 비는 것**이다 — 한 검사가
두 겹을 다 세는지 확인했다.

## 감사 ⑬ 의 고침 (`0d9a96d`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 145 | 미들웨어에서 `response.headers[_REQUEST_ID_HEADER] = request_id` 를 지웠다 | `test_every_answer_carries_an_id_that_names_the_request` · `test_an_id_the_caller_brought_is_not_replaced` |
| 145 | 받은 값의 모양 검사를 빼고 **그대로 되돌려 싣게** 했다 | `test_an_id_we_cannot_use_is_replaced_not_echoed` |
| 145 | 500 처리기의 `_log.exception` 을 `_log.debug` 로 낮췄다 | `test_a_break_leaves_a_log_line_that_names_the_request` |
| 145 | 500 처리기에서 헤더를 **다시 다는 줄**을 지웠다 | 같은 검사 |
| 147 | `docker-entrypoint.sh` 의 `set -euo pipefail` 을 지우고 `shellcheck` 를 돌렸다 | **없다 — 통과했다.** 그것이 NC-147 의 근거다 |

**통과한 줄이 이 묶음에서 가장 값지다.** 그 어긋냄이 없었으면 「`shellcheck` 가
`set -euo pipefail` 을 지킨다」가 근거로 남아 있었다 — 도구가 요구하지 않는
줄이다. **이 줄은 ⑬ 이 실제로 돌렸는데 여기 적히지 않아**(감사 ⑮ NC-156) 결과가
`ci.yml` 주석과 대장에만 남았고, `mutations.md` 만 읽는 사람에게 셸 검사는
**어긋내 본 적이 없는 검사**로 보였다. 규칙 ③ 이 요구하는 바로 그 줄이다.

**첫 어긋냄에서 500 검사만 통과했고 그것이 옳다.** `ServerErrorMiddleware` 가
사용자 미들웨어 **바깥**에 서므로 그 응답은 미들웨어를 지나오지 않고, 처리기가
따로 축을 단다 — 네 번째 어긋냄이 그 자리를 따로 문다. **두 자리를 한 검사가
겹쳐 세지 않는다.**

**그리고 이 검사가 실제로 결함을 하나 잡았다.** 처음 세웠을 때 500 에는 헤더가
붙지 않았다 — 하필 **축이 가장 필요한 응답**이다. 검사를 먼저 쓰지 않았으면
「달았다」로 끝났을 자리다.

## 감사 ⑮ 의 고침 (`b2bb637`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 153 | `## 감사 ⑬ 의 고침 (\`0d9a96d\`)` 을 `## 감사 ⑬ 가 돌린 어긋냄` 으로(해시도 함께 뗐다) | **고치기 전에는 없다 — 통과했다.** 고친 뒤 `test_a_mutation_bundle_says_which_commit_it_was_measured_on` |
| 155 | `backend/.dockerignore` 에 `migrations/` 를 한 줄 더했다 | **고치기 전에는 없다 — 364 개가 전부 통과했다.** 고친 뒤 `test_the_build_context_still_carries_what_the_image_needs_to_boot` |
| 155 | `chmod -x backend/docker-entrypoint.sh` | **고치기 전에는 없다 — `pytest` 도 `shellcheck` 도 통과했다.** 고친 뒤 `test_the_entrypoint_is_executable` |
| 154 | 저장소 루트에 `.sh` 파일을 하나 심고 `git ls-files '*.sh'` 와 `:(top)*.sh` 를 견줬다 | 검사가 아니라 **명령의 범위**를 쟀다 — 기본 경로명세가 그 파일을 놓쳤다 |

**셋 다 「고치기 전에는 통과, 고친 뒤에는 빨강」이다** — 어긋냄이 결함을 먼저
보이고 고침이 그것을 물게 한 순서다. 이 회차의 어긋냄은 감사자가 「돌려 봐야
확정된다」고 지목한 것을 그대로 돌린 것이고, 셋 다 감사자의 예측대로였다.

## 감사 ⑯ 의 고침 (`1e0a336`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 160 | `responses` 에서 404 선언을 뺐다 | `test_the_spec_declares_every_answer_that_actually_goes_out` · `test_the_spec_says_which_header_names_the_request` |
| 160 | 405 의 `Allow` 헤더 선언을 뺐다 | `test_the_spec_says_which_header_names_the_request` |
| 160 | `Transport` 열거에 이름(`ghost`)을 하나 더했다 | **없다 — 통과했다.** 양변이 같은 원천에서 나온다 |
| 160 | `http_error` 를 `path_error` 로 고쳤다 | **없다 — 통과했다.** 같은 이유. 다만 `/openapi.json` 이 함께 바뀌어 diff 에는 보인다 |
| 161 | 덮개에서 본문 금지 상태 코드 갈래를 지웠다 | `test_a_status_that_may_not_carry_a_body_does_not_get_one` |

**통과한 둘이 이 묶음의 값이다.** 스펙 쪽 열거는 pydantic 이 코드의 열거에서
만들므로 이름을 더하거나 고치면 **두 변이 함께 움직인다** — 이 검사가 무는 것은
**배선의 끊김**이지 이름의 변동이 아니다. NC-160 이 요구한 것(이름이 기계가 읽는
계약에 있을 것)은 충족되지만, 「이름이 바뀌면 검사가 문다」를 원하면 필요한 것은
**찍어 둔 스펙과의 대조**이고 그것은 아직 없다(감사 ⑯ OB-1). 두 검사의 독스트링이
이 사각을 적는다.

**어긋냄이 아니라 찍어서 잡은 것이 하나 더 있다** — 헤더를 201 에 선언하지 않은
자리다. 실제 응답에는 붙는데 선언에는 없어, **고침이 NC-160 의 모양을 한 겹
남겼다.** 검사를 고치고 선언을 채웠다.

## 감사 ⑰ 의 고침 (`bb0c2e5`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 162 | 미들웨어에서 4xx 이상을 찍는 줄을 지웠다 | `test_a_refusal_leaves_a_line_that_names_the_request` |
| 162 | 그 줄의 레벨을 `warning` 에서 `info` 로 낮췄다 | 같은 검사 — 루트에 레벨이 없어 한 줄도 나오지 않는다 |
| 164 | `hide_parameters=True` 를 뗐다 | **처음에는 없었다 — 통과했다.** 처리기가 DB 오류의 말을 아예 옮기지 않아 API 쪽 검사가 막아 주었다. 엔진 층을 직접 무는 검사를 세운 뒤 `test_a_database_error_does_not_render_the_values_it_was_given` |
| 164 | DB 오류 갈래를 지우고 `exc_info=exc` 하나로 되돌렸다 | `test_a_break_does_not_carry_the_values_the_caller_sent` — `DETAIL: Failing row contains` 가 실린다 |

**셋째가 이 묶음의 값이다.** 고침이 두 겹인데 **검사는 한 겹만 물고 있었다** —
둘째 겹(처리기)이 첫째 겹(엔진)을 가려 주는 바람에, 첫째를 떼도 초록이었다.
「두 겹으로 막았다」가 「두 겹이 지켜진다」는 뜻이 아니다. 엔진 층을 직접 무는
검사를 따로 세웠다.

**넷째는 고침 중에 실제로 일어났다.** `hide_parameters` 만 걸고 검사를 돌렸더니
**빨갰다**: 끈 것은 SQLAlchemy 층이고 PostgreSQL 자신이 `DETAIL` 로 줄의 값을
되비춘다. **검사를 먼저 쓰지 않았으면 「껐다」로 닫혔을 자리**이고, 그 말은 이
저장소가 NC-145 에서 이미 한 번 적었다.

**그리고 새 검사가 다른 검사를 빨갛게 했다.** 엔진을 만들고 버리지 않아 풀의
연결이 나중에 수거되면서 `ResourceWarning` 을 냈고, pytest 는 그것을 **그때 돌던
남의 검사**의 실패로 올렸다 — 단독으로는 초록이고 전체에서만 빨간 자리다.
`engine.dispose()` 로 닫았다.

**돌연변이가 아니라 실측으로 확정한 것이 셋 더 있다**(회차 절에 있다) — 거절이
로그에 0 건인 것, 로트 0건에서 되돌리기가 멈추는 것, 예외 문자열에 요청 본문의
값이 실리는 것. 셋 다 앱을 띄우거나 실제로 되돌려 찍었다.

## Codex 리뷰의 고침 (`d6b350c`)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 148 | HTTP 예외 처리기에서 `headers=exc.headers` 를 뺐다 | `test_a_method_error_still_says_which_method_works` — 405 의 `Allow` 가 사라진다 |
| 149 | `_log.error(..., exc_info=exc)` 를 `_log.exception(...)` 으로 되돌렸다 | `test_a_break_leaves_the_cause_not_just_the_axis` — 로그에 `NoneType: None` 이 찍힌다 |

**둘째는 앞 커밋이 세운 검사가 놓친 자리다.** `…names_the_request` 는 로그에 **축이
있는지**만 물었고 **까닭이 실렸는지**는 묻지 않았다 — 그래서 `NoneType: None` 이
찍히는 동안에도 초록이었다. 단언을 넓히지 않고 **검사를 따로 세웠다**: 하나는 축을,
하나는 까닭을 문다.

## 아직 도구가 없다

여기 적힌 것은 **손으로 돌린 것**이다. 돌연변이 러너를 개발 의존성으로 들이는
쪽(NC-89 의 제안 ②)은 아직 하지 않았다 — 먼저 **기록의 자리**를 정하는 것이 싸고,
그 자리가 없으면 러너를 들여도 결과가 다시 저장소 밖에 남는다.

## Codex 리뷰의 고침 (`ebeef8a` 뒤)

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 104 | `app.py` 에서 커밋을 **의존성 뒤로 되돌렸다**(`yield` 다음) | `test_a_commit_that_fails_does_not_answer_201` — 커밋이 터졌는데 **201 이 나갔다.** 그것이 이 부적합의 모양 그대로다 |
| 103 | `incoming.py` 의 `_must_be_a_counted_reason(...)` 호출을 지웠다 | `test_a_measured_reason_cannot_be_sent_by_a_person` |
| 107 | `if counted_items:` 를 `if False:` 로 | `test_a_value_for_a_counted_item_is_refused` |
| 106 | `if not partner.is_active:` 를 `if False:` 로 | `test_an_inactive_supplier_cannot_deliver` |
| 105 | 로트 번호 길이 가드를 `if False:` 로 | `test_an_item_code_too_long_for_the_lot_number_is_refused` |
| 102 | 유효기간을 `request.received_date` 대신 **`judged_at.date()`** 에서 세게 되돌렸다 | `test_the_expiry_counts_from_the_day_it_arrived` · `test_material_that_already_expired_on_arrival_is_refused` |

## CodeRabbit 리뷰의 고침 (`e3b3eeb` 뒤)

넷 중 **하나만** 기계가 셀 수 있는 모양이었다. 나머지 셋(110 · 111 · 113)은 산문의
뜻이 갈린 자리라 게이트가 서지 않는다 — 그 셋이 못 세는 부류라는 것이
`test_prose.py` 머리말의 「이 게이트가 못 보는 부류」다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 112 | 대장의 NC-35 줄 끝에 **칸 하나를 도로 붙였다**(머리가 6 칸인데 7 칸) | `test_a_table_row_does_not_carry_a_cell_the_header_did_not_declare` — 줄 번호까지 가리켰다(`docs/audit/README.md:111`) |

## NC-109 의 고침 — `inspections.received_date` (`9c09a96` 뒤)

**하나가 통과했고 그것이 이 표의 값이다.** 데이터 단계를 「로트에서 옮긴다」에서
「판정일에서 센다」로 어긋냈는데 전부 초록이었다 — 픽스처의 로트 도착일과 판정일이
**같은 날**이라 두 구현이 같은 값을 냈다. 테스트가 그 자리를 지나가면서 아무것도
지키지 않던 자리이고, 도착일을 판정일에서 떼어 두고서야 물었다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 109 | `incoming.py` 에서 `received_date=request.received_date` 를 지웠다(검사 쪽) | `test_a_failed_judgement_still_remembers_when_the_material_arrived` 외 여럿 — 쌍 외래키가 합격 경로도 함께 무너뜨린다 |
| 109 | `fk_lot_inspection_received_date` 를 통째로 뺐다 | `test_a_pass_cannot_let_the_two_arrival_dates_drift` · `test_the_migration_builds_the_same_tables_as_the_models` |
| 109 | `ck_inspection_judged_after_arrival` 의 비교를 60 일 늦췄다 | `test_an_inspection_cannot_be_judged_before_the_material_arrived` · 대조 테스트 |
| 109 | 데이터 단계를 `l.received_date` 대신 `i.judged_at::date` 로 | **처음에는 통과했다.** 픽스처의 두 날짜를 떼어 둔 뒤 `test_the_data_step_moves_the_arrival_date_from_the_lot` 이 물었다 |
| 109 | 되돌림 가드의 `NOT EXISTS` 를 `FALSE AND NOT EXISTS` 로(아무것도 세지 않게) | `test_downgrade_says_whose_arrival_date_has_no_lot_to_fall_back_on` |
| 114 | `ck_lot_from_an_inspection_has_an_arrival_date` 를 항상 참으로(`OR TRUE`) | `test_an_own_lot_cannot_borrow_an_incoming_inspection` · 대조 테스트. **CHECK 를 걸기 전에 그 검사가 실제로 통과하는 것**(DID NOT RAISE)을 먼저 확인했다 — 구멍이 있다는 주장과 구멍이 있다는 사실은 다르다 |

## Codex 리뷰의 고침 — `931a400` 뒤

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 115 | `if attribute.inspection_item_code is None:` 을 `if False:` 로 | `test_a_reason_the_system_derives_cannot_be_sent_by_a_person` |
| 116 | 길이 가드를 접두를 재던 옛 식(`len(prefix) + 2`)으로 되돌렸다 | `test_a_serial_that_grew_a_digit_is_refused_by_name` — 긴 코드 갈래는 **그대로 통과한다**(같은 결과의 두 원인이라 한 갈래로는 갈리지 않는다) |
| 117 | `08d406fa7f3b` 의 데이터 단계를 `SELECT 1` 로 | `test_upgrading_a_database_that_already_has_a_ledger_line_does_not_stop` |

## CodeRabbit 리뷰의 고침 — `2fc40f3` 뒤

**검사가 아무것도 재지 않는 것을 한 번 더 겪었다.** 어긋난 짝을 만들려고 둘째
품목의 검사를 심었는데 **그 품목이 픽스처에 없어** 삽입이 빈 동작이 됐고, 원장
줄은 원래 검사를 그대로 가리켜 가드가 물 자리가 없었다. 가드가 옳은데 검사가
빨갛지 않아 **가드부터 의심하게 되는** 모양이다 — 품목을 함께 심고서야 물었다.

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 118 | 품목 대조 가드의 조건을 `WHERE FALSE` 로(아무것도 세지 않게) | `test_upgrading_stops_when_a_ledger_line_points_at_another_items_inspection` |

## Codex 리뷰의 고침 — `2fc40f3` 뒤

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 118(구조) | `fk_lot_inspection_item` 을 통째로 뺐다 | `test_a_lot_cannot_point_at_another_items_inspection` · 대조 테스트 |
| 119 | 역방향 가드의 `HAVING count(DISTINCT lot_id) > 1` 을 `HAVING FALSE` 로 | `test_upgrading_stops_when_two_lots_share_one_inspection` |
| 120 | `startswith(..., autoescape=True)` 를 `like(prefix + '%')` 로 되돌렸다 | `test_a_wildcard_in_the_item_code_does_not_reach_the_like` |
| 121 | `if attribute.inspection_item_code not in standards:` 를 `if False:` 로 | `test_a_reason_this_material_is_not_inspected_for_is_refused` |

## NC-122 의 고침 — `186207e` 뒤

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 122 | `applied_unit=standard.unit` 를 `None` 으로 | `test_the_measurement_pins_the_unit_the_number_meant` · 잠금 검사 |
| 122 | `fk_inspection_measurement_unit` 을 통째로 뺐다 | `test_a_standard_cannot_change_its_unit_while_a_measurement_cites_it` · 대조 테스트 |
| 122 | 리비전의 데이터 단계를 `SELECT 1` 로 | `test_the_data_step_moves_the_unit_from_the_standard` 외 하나 |
| 122 | 되돌림 가드의 값 대조를 `AND FALSE` 로(외래키에 기대게) | `test_downgrade_says_which_measurements_would_lose_their_unit` |

## NC-123 의 고침 — `fcb7570` 뒤

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 123 | `ck_inspection_standard_measured_has_a_unit` 의 식을 `TRUE` 로 | `test_a_standard_that_measures_must_say_in_what_unit` · 대조 테스트 |
| 123 | 시드의 `입도` 에서 단위를 지웠다 | **CHECK 가 심는 단계에서 거부해** 시드를 쓰는 검사가 전부 빨갛다 — 시드 쪽 검사는 그 위의 덧대기이고, 무는 것은 제약이다 |

## Codex 리뷰의 고침 — `94cbd51` 뒤

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 124 | `applied_unit` 을 널 허용으로 되돌렸다(모델과 리비전을 함께) | `test_a_measurement_cannot_be_written_without_its_unit` — **대조 테스트는 초록이다**(둘을 함께 어긋냈으므로). 구조가 갈렸는지가 아니라 **무엇을 막는지**를 재는 검사라야 무는 자리다 |
| 125 | `if _measures(standards[...]):` 를 `if False:` 로 | `test_a_counted_reason_whose_standard_measures_is_refused` |
| 125 | 시드에서 `IQ-FM` 이 `이물` 대신 `입도`(재는 항목)를 가리키게 했다 | `test_no_counted_reason_points_at_a_measured_standard` · `test_every_standard_has_a_reason_that_can_use_it` |

## NC-126 의 고침 — `9bad48b` 뒤

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 126 | 단위 없는 기준을 세는 가드의 조건을 `AND FALSE` 로(CHECK 가 먼저 걸리게) | `test_upgrading_says_which_standard_measures_without_a_unit` |

## NC-127 의 고침 — `3e2e703` 뒤

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 127 | `ck_inspection_standard_measured_has_a_unit` 의 식을 `TRUE` 로 | `test_a_standard_that_measures_must_say_in_what_unit` · 대조 테스트 |
| 127 | `ck_inspection_standard_unit_means_something` 의 식을 `TRUE` 로 | `test_a_unit_that_only_looks_like_one_is_refused` · `test_even_a_standard_that_only_counts_cannot_hold_a_hollow_unit` · 대조 테스트 |
| 127 | `fk_inspection_measurement_unit` 을 통째로 지웠다 | `test_a_measurement_unit_that_only_looks_like_one_has_nowhere_to_land` · 대조 테스트 |
| 127 | 빈 단위 기준을 세는 **올릴 때 가드**를 `SELECT 1` 로 | `test_upgrading_says_which_standard_holds_a_unit_that_only_looks_like_one` |

**여기서 하나가 거뒀다.** 측정 줄에도 `is_present("applied_unit")` 를 걸었다가 **지워도
대조 테스트만 빨개졌다** — 그 CHECK 를 물게 하려면 「빈 단위를 든 기준」이 있어야 하는데,
같은 고침이 그런 기준을 설 수 없게 만들었기 때문이다. **물게 할 수 없는 제약**은 같은
명제의 둘째 자리라 거두고, 외래키가 그것을 이 줄까지 나른다는 것을 검사로 적었다.

