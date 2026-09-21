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

## ⑨ 의 고침

| NC | 무엇을 어긋냈나 | 빨개진 검사 |
|---|---|---|
| 87 | `app.py` 의 `session_scope` 에서 `session.commit()` 을 지웠다 | `test_a_pass_is_actually_committed` — **그 전에는 294 개가 전부 초록이었다** |
| 88 | `_sessions()` 를 게으른 형태에서 **모듈 최상단**으로 되돌렸다 | `test_the_app_does_not_reach_for_the_default_database` · `test_a_pass_is_actually_committed` |
| 91 | `ck_lot_passed_after_arrival` 의 `>=` 를 `>` 로 | `test_a_lot_that_arrives_and_passes_on_the_same_day_stands` |
| 90 | `inspections` 에 `UNIQUE (supplier_id, item_id, supplier_lot_number)` 를 **더했다**(NC-67 의 결정을 뒤집는 변경) | `test_the_same_request_twice_makes_two_lots` · `test_a_split_delivery_of_the_same_supplier_lot_is_accepted`. **「둘째는 그날의 다음 일련을 받는다」는 통과했다** — 감사자가 예측한 그대로다 |
| 92 · 86 | `production.py` 의 문장을 「1단계에서는 표만 선다」로 되돌렸다 | `test_a_stage_that_closed_is_not_written_as_if_it_were_now` |
| 86 | 저장소 최상위에 `frontend/` 를 만들었다 | `test_there_is_still_no_screen` |

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
