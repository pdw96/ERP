# 조각 3 — 이동 (2026-10-19 착공)

요구사항이다 — **무엇을 · 왜.** 어떻게 · 경계는 같은 폴더의 `design.md`, 대안이 있던 결정은 ADR.

## 문제

원재료창고의 자재가 생산 라인 옆으로 불려 가도 장부는 그것을 원재료창고에 둔다. 로트는 태어난 창고에 영원히
있고, 생산창고에 무엇이 투입을 기다리는지 아무도 셀 수 없다(`PRD.md` 「문제」). 원장 줄은 창고를 이미
들고 있지만(조각 「원장 줄의 창고」, ADR 0022) 창고를 건너는 줄이 아직 하나도 없다 — 그 줄을 내는 요청 ·
처리 · 취소가 없기 때문이다.

창고를 건너는 줄이 서면 **로트 단위로 세던 규칙이 창고를 골라야 한다.** 잔량은 로트 × 창고로 세고, 나뉜
로트가 재검사에서 떨어지면 폐기 줄이 창고마다 선다. 폐기 줄 id 하나를 돌려주는 재검사 응답은 그것을 다
돌려줄 수 없다 — 이 조각이 공개 계약을 깨는 자리다.

## 핵심 사용자와 시나리오

- 사용자: 생산 쪽 요청자와 자재 담당 처리자. 계정은 없고 이름을 식별 칸에 적는다(`CLAUDE.md` 「판정자는 칸이고
  표가 아니다」)
- 시나리오: 생산 쪽이 로트 A(원재료창고 50)의 20 을 옮겨 달라는 요청을 낸다 → 자재 담당이 그 요청을 처리한다 →
  원장에 원재료창고의 `생산출고` 20 과 생산창고의 `생산입고` 20 이 처리와 한 트랜잭션으로 선다. 로트 A 는 이제
  원재료창고 30 · 생산창고 20 이다 → 다음 날 로트 A 가 만료돼 재검사에서 떨어진다 → 폐기 줄이 원재료창고 30 ·
  생산창고 20 두 장 서고, 재검사 응답이 두 줄의 id 를 함께 돌려준다. 잘못 낸 다른 요청은 처리되기 전에 누구든
  취소하고, 취소한 사람의 이름이 남는다

## 성공 기준

- **`PRD.md` 성공 기준 1 ~ 8 과 10 이 이 조각의 것이다** — 잔량 · 처리의 한 트랜잭션 · 종결은 하나 · 전부 처리 ·
  만료된 로트의 처리 거부 · 나뉜 로트의 폐기 · 식별 칸 · 기존 원장 줄 · 마이그레이션 대조. 여기에 옮겨 적지 않는다.
  성공 기준 9(창고별 잔량을 읽는 엔드포인트)는 다음 조각 「이동-읽기」의 것이다
- **요청과 종결을 HTTP 로 낸다** — `POST /stock-transfer-requests` 가 요청을, `POST /stock-transfer-closures` 가 처리
  또는 취소를 받는다. 트리거가 막는 것(잔량 · 만료 · 종결 중복)을 쓰기 경로가 먼저 **업무 거절의 이름으로** 막고,
  이름은 경로마다 열거 하나다(ADR 0014)
- **취소는 누구나 낸다** — 취소자 칸이 요청자와 같은지 묻지 않는다. 처리된 요청의 취소와 취소된 요청의 처리는
  이름 있는 거절이다
- **재검사 응답이 폐기 줄 id 를 목록으로 돌려준다** — 나뉜 로트의 불합격이면 줄이 창고마다 하나씩 실린다. 옛 칸
  `ledger_entry_id` 는 사라지고 판은 `2.0` 이다. 판정 테스트가 그 판을 깨는 변경으로 가르는 것을 본다(ADR 0025)
- **구매반품은 원재료창고의 잔량을 넘지 못한다** — 생산창고로 옮긴 분량은 반품으로 나가지 않는다(`PRD.md`
  「착공에서 답을 받은 것」). 쓰기 경로가 있는 거절 이름(`more_than_the_lot_holds`)으로 막는다
- **새 검사마다 어긋내서 빨갛게 되는 것을 본다** — 기록은 `docs/audit/mutations.md`

## 하지 않을 일

1. **창고별 잔량과 처리를 기다리는 요청을 읽는 엔드포인트를 세우지 않는다** — 다음 조각 「이동-읽기」의 일이다.
   이 조각의 응답은 쓴 것을 돌려줄 뿐이다
2. **취소를 막는 사람 대조를 하지 않는다** — 계정이 없어 이름 대조는 아무것도 지키지 않는다(소유자, 2026-10-19)
3. **재검사 응답의 옛 칸을 남겨 두지 않는다** — 두 장일 때 비우든 한 장만 적든 옛 칸만 읽는 쪽이 잘못 읽는다(ADR 0025)
4. **요청을 고치는 경로를 세우지 않는다** — 잘못 낸 요청은 취소하고 새로 낸다(원칙 ⑦)
5. **`PRD.md` 「하지 않을 일」이 그대로 선다** — 원재료창고 → 생산창고 밖의 이동 · 부분 처리 · 재고를 잡는 요청 ·
   사용자 표 · 상쇄 경로 · 화면 · 배포. 여기에 옮겨 적지 않는다

## 제약

- **스택과 비용**: `PRD.md` 「제약」 그대로 — 새 의존성 없음 · 로컬 Docker Compose · 월 0원
- **스키마 변경은 마이그레이션과 함께**, 리비전을 낸 뒤 `tests/test_migrations.py` 를 돌린다(`CLAUDE.md` 「금지」)
- **조이기 전에 묻는다** — 잔량을 로트 × 창고로 세기 전에, 그 셈에서 음수가 되는 기존 줄과 0 짜리 폐기 줄을 가드가
  먼저 세고 로트 번호를 말한다(감사 ㊸ OB-1, `docs/schema-4단계.md`)
- **리뷰 한도**: `docs/리뷰-루프.md` 가 정한다 — 점수 · 쏠림 신호 · 소유자에게 묻는 문턱
- **닫기 전에 감사 회차** — 스키마가 움직이므로 `audit-data`, 공개 계약이 깨지므로 `audit-contract`

## 닫으며 (2026-10-21)

설계 ⑥ 의 세 PR — A #119 · B #121 · C #124 — 이 모두 머지됐고, 「제약」이 정한 닫기 전의 감사 회차를 돌렸다(㊹ `audit-data` ·
㊺ `audit-contract`, `docs/audit/회차-기록.md`). 배포는 `PRD.md` 「하지 않을 일」이라 절차의 「배포 · 롤백」은 `없음 — 배포처가 없다`.

**돌린 결과** — `c80bcbf`(= 닫을 때의 `main`)에서 CI 와 같은 Python 3.12 로 전체 시험 910 통과, `ERP_CONTRACT_BASELINE=190bfe0` 으로
판정 시험 111 통과. CI(`backend`)는 세 PR 과 그 뒤의 의존성 올림 #118 에서 모두 초록이었다.

### 성공 기준마다 무엇에 대어 봤나

| 성공 기준 | 무엇에 대어 봤나 | 결과 |
|---|---|---|
| `PRD.md` 1 · 잔량을 로트 × 창고로, 동시에 와도 | `test_a_transfer_takes_no_more_than_the_raw_warehouse_holds` · `test_two_processings_of_one_lot_at_once_do_not_both_take_it` · 경로 쪽 `test_two_processings_of_one_lot_at_once_the_second_is_named` | 맞음 |
| `PRD.md` 2 · 종결 · 출고 · 입고가 한 트랜잭션, 같은 로트 · 수량 · 시각 | `test_processing_takes_both_ledger_lines` · `test_a_transfer_line_says_what_its_processing_says` · `test_a_transfer_runs_from_raw_to_production` · `test_processing_moves_the_quantity_in_one_transaction` · `test_a_201_means_the_commit_passed_the_deferred_check` | 맞음 |
| `PRD.md` 3 · 요청 하나에 종결 하나 — 유일키로 | `test_one_request_has_one_end` · `test_processing_and_cancelling_one_request_at_once` | 맞음 |
| `PRD.md` 4 · 한 번에 전부 처리 | `test_an_end_carries_what_its_request_says` | 맞음 |
| `PRD.md` 5 · 만료된 로트의 처리 거부, 요청은 막지 않음 | `test_an_expired_lot_is_not_moved` · `test_a_request_for_an_expired_lot_still_stands_and_can_be_cancelled` · `test_a_renewal_judged_after_the_processing_does_not_cover_it` · `test_processing_and_retest_share_one_boundary` | 맞음 |
| `PRD.md` 6 · 나뉜 로트의 폐기는 창고마다 한 줄, 합쳐서 잔량 전부 | `test_a_split_lot_is_disposed_of_in_each_warehouse` · `test_a_disposal_that_misses_a_warehouse_does_not_stand` · `test_one_retest_takes_one_disposal_line_in_each_warehouse` · 쓰기 경로 `test_a_split_lot_is_thrown_away_in_each_warehouse` | 맞음 |
| `PRD.md` 7 · 요청자 · 처리자 · 취소자 | `test_a_request_names_who_asked` · `test_an_end_names_who_closed_it` | 맞음 |
| `PRD.md` 8 · 기존 원장 줄이 창고를 얻고, 못 채우면 가드가 말한다 | 칸과 채우기는 조각 「원장 줄의 창고」가 섰다. 이 조각의 몫 — 로트 × 창고로 세기 전에 묻는 가드 — 는 `test_upgrading_says_which_lot_goes_below_zero_in_a_warehouse` · `test_upgrading_says_which_lot_holds_a_disposal_of_nothing`, 감사 ㊹ 가 ㊸ OB-1 을 해소로 판정 | 맞음 |
| `PRD.md` 10 · 마이그레이션이 모델과 같다 · 화면 0 | `tests/test_migrations.py` 의 대조(함수 본문 · 트리거 정의까지) · 감사 ㊹ 체크 1. 프론트엔드 폴더가 없다 | 맞음 |
| 요청과 종결을 HTTP 로, 거절은 경로마다 열거 하나 | `tests/test_transfer_api.py` 전부 — 특히 `test_what_the_database_would_break_on_is_refused_at_the_request_boundary` · `…_closure_boundary` · `test_the_spec_lists_every_transfer_refusal_name` | 맞음 |
| 취소는 누구나, 끝난 요청은 이름 있는 거절 | `test_anyone_may_cancel_and_a_cancellation_moves_nothing` · `test_a_request_closes_once` | 맞음 |
| 재검사 응답이 폐기 줄 id 를 목록으로, 판 `2.0` | `test_a_split_lot_comes_back_with_a_disposal_line_for_each_warehouse` · `test_the_version_moves_as_far_as_the_contract_moved` — 판 `1.1` 에서 빨개지는 것(`docs/audit/mutations.md` 「이동 PR B」) · 감사 ㊺ 가 ㊸ 이 넘긴 자리를 적합으로 닫음 | 맞음 |
| 구매반품은 원재료창고의 잔량을 넘지 못한다 | `test_what_moved_to_production_is_not_returned` · `test_a_return_counts_only_what_is_left_in_the_raw_warehouse` | 맞음 |
| 새 검사마다 어긋내서 빨갛게 | `docs/audit/mutations.md` 「4단계 조각 3 — 이동 PR A」 · 「PR B」 · 「PR C」 | 맞음 |

못 미친 성공 기준은 없다. `PRD.md` 성공 기준 9(창고별 잔량을 읽는 엔드포인트)는 처음부터 「이동-읽기」의 것이다.

### 넘긴 것

- **같은 이동 요청을 두 번 보내면 요청이 둘 서고 둘 다 처리될 수 있다**(NC-230, 보통) → 조각 「이동-읽기」. 설계 ② 가 알려진 한계로
  적으며 「NC-67 · 226 과 같은 자리」라고 가리켰지만 그 두 줄의 기한으로는 닫히지 않는다는 것이 감사 ㊹ 의 지적이다. 지금 막지 않고
  처리를 기다리는 요청이 처음 보이는 조각에서 멱등 키와 함께 본다(저장소 소유자, 2026-10-21)
- **반품의 거절 이름과 `balance` 의 뜻을 스펙 산문에 적는 것**(감사 ㊺ OB-1) → 조각 「이동-읽기」. 창고별 잔량이 밖으로 나갈 때
  `more_than_the_lot_holds` 가 원재료창고의 잔량을 넘었다는 뜻이고 `balance` 가 모든 창고의 합이라는 것을 함께 적는다
- **스펙 산문에 내부 이름을 싣지 않는 규칙을 세울지**(감사 ㊺ OB-3, 세 번째) → 저장소 소유자의 판단. 이 조각에서 정하지 않았다
- 감사 ㊹ · ㊺ 가 다른 담당에 넘긴 것(동시성 시험의 무는 힘 → `audit-quality`, 종결 거절이 로트 정보를 되비춤 → `audit-secrets`)은
  그 회차 절이 든다
- 잘못 처리된 이동을 되돌리는 길은 넘기지 않는다 — `PRD.md` 「하지 않을 일」 2 가 정한 범위다

### 다음 조각

**이동-읽기** — `docs/master-plan.md` 조각 나눔의 4. 의존한 「이동」이 닫혔다. 착공 전에 대장(`docs/audit/README.md`)의 NC-230 과
이 절의 넘긴 것을 읽는다.
