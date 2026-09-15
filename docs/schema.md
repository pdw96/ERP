# 1단계 스키마 초안

> 아직 코드가 없으므로 표로 적는다. `backend/app/db/` 에 SQLAlchemy 모델이
> 서는 순간 이 문서는 **그 코드를 가리키는 색인**이 되고, 칸의 진실은 코드로
> 옮겨간다. 두 벌을 유지하지 않는다.
>
> 근거는 전부 [설계도 42판](https://claude.ai/artifact/GMJpbFywKh8wj6N4vEukT6)에
> 있다. 여기에는 **무엇이 있는가**만 적고 **왜**는 설계도에 둔다.

## 표 열넷

| # | 표 | 모듈 | 무엇인가 |
|---|---|---|---|
| 1 | `items` | 전사 기준정보 | 품목 한 표 — 완제품 · 반제품 · 원자재 |
| 2 | `bom_components` | 생산 기준정보 | 2단 고정 BOM |
| 3 | `partners` | 전사 기준정보 | 거래처 — 공급사 · 고객사 |
| 4 | `code_groups` | 시스템 관리 | 공통코드 그룹 23 |
| 5 | `common_codes` | 시스템 관리 | 공통코드 본체 |
| 6 | `txn_type_attributes` | 시스템 관리 | 확장 ① 수불유형 |
| 7 | `nonconformity_attributes` | 시스템 관리 | 확장 ② 불합격사유 |
| 8 | `nonconformity_stage_rules` | 시스템 관리 | 불합격코드 × 검사단계 |
| 9 | `purchase_close_attributes` | 시스템 관리 | 확장 ③ 미납종결사유 |
| 10 | `shift_patterns` | 생산 기준정보 | 근무형태 3 |
| 11 | `non_working_periods` | 생산 기준정보 | 비가동 구간 |
| 12 | `process_inspection_standards` | 품질 기준정보 | 공정 × 검사항목 |
| 13 | `supplier_items` | 구매 기준정보 | 공급사별 품목 |
| 14 | `lots` | 재고관리 | 재고 로트 (통합) |

1–13은 기준정보라 **비어 있으면 안 된다.** 14는 거래 표라 **비어 있는 것이
정상**이다 — 1단계에는 표만 서고 채우는 것은 2단계(IQC 합격)의 일이다.

---

## 1. `items` — 품목 한 표

반제품은 **만들어지면서 쓰인다.** 표가 둘로 갈려 있으면 앉을 자리가 없다.

| 칸 | 형 | 비고 |
|---|---|---|
| `id` | PK | |
| `code` | str(50) UQ | `FG-01` · `SF-01` · `RM-01`. 접두는 유형과 유일성만 맡는다 |
| `name` | str(200) | |
| `item_type` | str(20) | `ITEM_TYPE` — 완제품 · 반제품 · 원자재 |
| `process` | str(30) NULL | `PROCESS` 참조. 검사 기준을 끌어오는 라벨. 접두가 아니라 명시적인 열 |
| `stock_uom` | str(30) | `UOM` 참조. **모든 수량이 이 단위로 저장된다** |
| `phase` | str(10) | `ITEM_PHASE` — 초기 · 양산 |
| `shelf_life_days` | int NULL | 설정기간. NULL 이면 무기한. **반제품은 NULL 이어야 한다** |
| `safety_stock` | float NULL | **원자재는 NOT NULL 이어야 한다** |
| `setup_hours` | float NULL | 준비시간 |
| `hours_per_unit` | float NULL | 개당 시간 |

**제약**
- `CHECK item_type IN (…)` · `CHECK` 코드 접두가 유형과 맞는가
- `UNIQUE (id, item_type)` — 복합 외래키의 상대가 되기 위해. 「이 로트의 품목은
  원자재여야 한다」를 거는 쪽이 `(id, 유형)` 쌍을 가리킬 수 있어야 한다
- `FK (process_group, process) → common_codes` — `process_group` 은 상수 `PROCESS`
- `FK (stock_uom_group, stock_uom) → common_codes` — 같은 모양
- `CHECK item_type='반제품' → shelf_life_days IS NULL`
- `CHECK item_type='원자재' → safety_stock IS NOT NULL`
- `CHECK setup_hours >= 0 AND hours_per_unit >= 0`

> **미결 — `stock_uom` 을 고치면 지나간 수량의 뜻이 바뀐다.** 어느 표에도 단위
> 사본이 없으므로 `EA` 를 `m2` 로 고치면 이미 쌓인 500개가 조용히 500 m² 가
> 된다. 1단계에는 품목을 고치는 경로가 없어 지금은 열리지 않는 구멍이다.
> 품목 수정 화면이 서는 단계에서 정한다 — 답은 아마 **「단위 변경은 수정이
> 아니라 새 품목」**이다.

## 2. `bom_components` — 2단 고정

| 칸 | 형 | 비고 |
|---|---|---|
| `id` | PK | |
| `parent_item_id` | FK items | |
| `parent_item_type` | str(20) | 복합 외래키의 절반 — 파생값이 아니다 |
| `child_item_id` | FK items | |
| `child_item_type` | str(20) | 〃 |
| `level` | int | 1 = 완제품 ← 반제품 · 2 = 반제품 ← 원자재 |
| `unit_quantity` | float | |

**제약** — `UNIQUE (parent, child)` · `CHECK unit_quantity >= 0` ·
`CHECK parent <> child` · 복합 FK `(parent_item_id, parent_item_type) → items` ·
같은 모양의 child FK · **`CHECK` 단계가 양쪽 유형을 정한다**

### 「단계」가 재귀를 막는 것을 규칙이 아니라 구조로 둔다

설계도는 「단계 열 하나가 재귀를 막는다」고 적었고, 그것이 어떻게 강제되는지는
적지 않았다. `level` 을 1·2로 제한하는 CHECK 만으로는 **1단에 원자재를 하위로
넣는 줄**이 선다 — 전개가 두 번이어도 잘못된 두 번이 된다.

`items` 의 `UNIQUE (id, item_type)` 이 여기서 값을 한다. 유형을 BOM 줄에 함께
적고 복합 외래키로 품목을 가리키면, 한 CHECK 가 단계와 양쪽 유형을 묶을 수 있다:

```
(level = 1 AND parent_item_type = '완제품' AND child_item_type = '반제품')
OR
(level = 2 AND parent_item_type = '반제품' AND child_item_type = '원자재')
```

그래서 3단이 **적을 수가 없다** — 원자재를 상위로 둔 줄은 어느 단계로도 서지
않는다. 유형 두 칸은 파생값을 저장한 것이 아니라 복합 외래키의 절반이며,
품목의 유형과 다를 수 없다는 것을 데이터베이스가 보증한다. 덤으로 품목의
유형을 나중에 바꾸는 것도 막힌다.

**설계도보다 한 걸음 나간 자리다.** 42판은 강제 수단을 정하지 않았고, 기존
저장소에는 유형 칸도 복합 외래키도 없었다.

> **미결 — 손실률 칸(지적 ㉜).** 투입과 산출을 견주는 자리가 없으면 손실이
> 재고조정으로 숨는다. 견줄 실적이 생기는 5단계의 일이므로 1단계에는 두지
> 않는다.

## 3. `partners` — 거래처

| 칸 | 형 | 비고 |
|---|---|---|
| `id` | PK | |
| `code` | str(20) UQ | |
| `name` | str(100) | |
| `partner_type` | str(10) | 공급사 · 고객사 |
| `is_active` | bool | |

`UNIQUE (id, partner_type)` — `supplier_items` 가 「공급사여야 한다」를 걸기 위해.

## 4–5. `code_groups` · `common_codes`

**그룹은 전부 Major다.** 프로그램이 이름으로 부르므로 화면에서 하나도 더할 수
없고 지울 수 없다. 갈리는 것은 그룹이 아니라 **그 안의 값**이다.

`code_groups` — `group_code` PK · `name` · `value_fixed` bool · `description`

`common_codes` — `(group_code, code)` PK · `name` · `description` ·
`sort_order` · `is_active`

**삭제 칸이 없다.** 지우면 그 코드로 적힌 과거 기록이 뜻을 잃으므로 `is_active`
를 끈다 — 새 기록에서는 못 고르고 옛 기록에서는 읽힌다 (원칙 ⑦의 코드판).
**코드값은 이름이 아니라 주소다** — 명칭은 고쳐도 코드값은 고치지 않는다.

### 값이 고정된 그룹 열다섯 — 프로그램이 분기한다

`WAREHOUSE`(3) · `STOCK_TYPE`(2) · `ITEM_TYPE`(3) · `TXN_TYPE`(12) ·
`INSP_STAGE`(5) · `ORDER_TYPE`(2) · `ORDER_MODE`(2) · `SHIP_TYPE`(2) ·
`ITEM_PHASE`(2) · `MEAS_KIND`(2) · `SIGMA_SRC`(3) · `WE_RULE`(4) · `SHIFT`(3) ·
`SETTLE_TYPE`(2) · `RISK_STATUS`(3)

### 값이 늘 수 있는 그룹 여덟 — 세기만 한다

`NC_REASON`(19) · `PO_CLOSE`(7) · `SP_REASON`(5) · `ADJ_REASON`(0) ·
`PROCESS`(5) · `INSP_ITEM`(18) · `DEPT` · `UOM`

`ADJ_REASON` 이 0인 것은 빠진 것이 아니다 — 실제로 조정을 내 보아야 목록이
나온다.

> `RISK_STATUS` 는 경보 층이 이 저장소에 없는데도 둔다. 값이 셋뿐이고 경보가
> 돌아올 때 그룹을 새로 만드는 것보다 낫다. **빼도 다른 결정에 얽히지
> 않는다** — 이 줄 하나를 지우면 22그룹이 된다.

## 6. `txn_type_attributes` — 확장 ① 수불유형

`(group_code, code)` PK, `group_code` 는 상수 `TXN_TYPE`

| 칸 | 값 |
|---|---|
| `total_effect` | 증가 · 감소 · 양방향 · 불변 · 기준점 |
| `paired_code` | 같은 표의 다른 줄. NULL 가능 |
| `source_document_type` | 재고이동 처리 · 출하 실적 · 재고조정 … |

`paired_code` 는 **공통코드가 아니라 이 표**를 가리킨다. 공통코드를 가리키면
속성 줄이 없는 코드를 짝으로 적어도 통과하고, 짝을 따라간 자리에 총량 영향도
원천 문서도 없다.

> **제약이 못 보는 자리** — A가 B를 짝으로 적고 B가 C를 적어도 두 줄 다
> 통과한다. 같은 표의 다른 줄을 보는 조건은 CHECK 로 적을 수 없다. 1단계에는
> 시드가 유일한 쓰기 경로라 정합 테스트가 지키고, 화면에서 코드를 만드는 길이
> 생기는 날 쓰기 시점 검증이 함께 서야 한다.

## 7–8. 불합격사유 — 코드에 둘, 관계에 둘

`nonconformity_attributes` `(group_code, code)` PK
- `measure_kind` — 계량 · 계수
- `(inspection_item_group, inspection_item_code)` → `common_codes`. **계량이면 필수**

계량 코드는 사람이 만들지 않는다 — 검사 항목에서 따라 나온다. 목록을 두 벌
두면 반드시 갈린다.

`nonconformity_stage_rules` `(reason_code, stage_code)` PK
- `disposition` — 반품 · 환불 · 재작업 · 폐기 · 등급 하향
- `special_acceptance_allowed` bool

**처분 기본값은 코드가 아니라 「코드 × 단계」에 붙는다.** `FQ-THK` 는 FQC에서
나면 재작업이고 OQC에서 나면 등급 하향이다. **줄이 있는 것 자체가 「그 단계에서
쓸 수 있는 코드」**라는 뜻이므로 별도의 「적용 단계」 칸이 없다.

## 9. `purchase_close_attributes` — 확장 ③ 미납종결사유

`responsibility`(공급사·자사) · `scorecard_axis`(NULL 가능) · `reorder_default`

**「성적 반영 여부」 칸이 없다** — 축이 비어 있는가로 그대로 나온다. 따로 두면
둘이 어긋나고, 어긋나면 `PO-EOL`(단종)처럼 예외인 줄에서 어긋난다.

## 10–11. 근무형태 · 비가동 구간

`shift_patterns` — `(group_code, code)` PK · `starts_at` · `ends_at` · `on_site`
현장 주간 09–21 · 현장 야간 21–09 · 사무 0830–1730

`non_working_periods` — `id` · `starts_at` · `ends_at` · `reason`

**365행이 아니라 연 몇 행이다.** 24시간 가동이 캘린더를 두 조 + 예외 목록으로
줄였다. 실사 창 09:00–17:30 은 두 근무가 겹치는 구간에서 **파생**되며 칸이 아니다.

> **시드하지 않는다** — 비가동 구간은 날짜를 가지므로 기준정보 SQL 에 넣을 수
> 없다(「오늘」이 나오면 파이썬). 표만 선다.

## 12. `process_inspection_standards` — 공정 × 검사항목

`(process_code, item_code)` PK, 둘 다 복합 외래키로 `common_codes` 참조

| 칸 | 누가 정하는가 |
|---|---|
| `upper_spec_limit` · `lower_spec_limit` | 고객 (지금은 임의) |
| `center_line` | 사람 |
| `warning_ratio` | 사람. 기본 0.70 |
| `sigma` | 비워 둔다 |
| `sigma_source` | 미정 · 임의 · 실측 |
| `time_variant` | 품질 — 「시간이 이 값을 바꿀 수 있는가」 |
| `unit` | |

**σ 를 비워 둔다.** 규격에서 뽑은 σ 는 어떤 계수를 쓰든 Cpk 를 그 계수의
역수로 못박는다. 경고선과 WE 규칙 4 는 σ 없이 그대로 돈다.

> **칸 넷을 1단계에 두지 않기로 했다** — 부분군 크기 · 상시 목표 Cpk(1.33) ·
> 전환 게이트 Ppk(1.67) · WE 규칙 켬/끔. 설계도 메뉴 절이 이 표에 적어 둔
> 값들이지만, 넷 다 **읽는 쪽이 8단계(관리도 · 공정능력)에 선다.** 지금 두면
> 아무도 읽지 않는 칸에 값을 채워야 하고, 채우지 않으면 빈 기준정보가 된다.
>
> 대가는 그 단계에서 마이그레이션이 하나 는다는 것뿐이다. 값을 읽는 코드와
> 함께 서는 편이 낫다.

**σ 와 σ 출처는 양방향으로 묶었다.** `(sigma IS NULL) = (sigma_source = '미정')`
— 한쪽만 걸면 다른 쪽으로 샌다: 숫자는 있는데 어디서 왔는지 모르는 σ 나,
「실측」이라 적혔는데 값이 없는 줄이 선다. 그러면 화면의 Cpk 가 진짜인지
자리표시자인지 아무도 모른다.

## 13. `supplier_items` — 공급사별 품목

`(partner_id, item_id)` PK · `lead_time_hours` · `purchase_uom` ·
`conversion_factor`

**단위를 바꾸는 경계는 여기 하나뿐이다.** 구매 단위로 발주하고 재고 단위로
저장한다. 리드타임이 시간인 것은 생산 리드타임과 단위를 맞추기 위해서다.

`FK (partner_id, partner_type) → partners` 로 「공급사여야 한다」를 건다.

## 14. `lots` — 재고 로트 (통합)

**이번 착공에서 설계도와 갈라지는 유일한 자리다.** 42판은 자재 로트와 완제품
로트를 두 표로 두었는데, 그것은 통합할 수 없는 기존 구조를 물려받은 결과다.
품목을 한 표로 묶은 논리가 로트에도 그대로 적용된다 — **반제품 로트는 두 표
어느 쪽에도 앉을 자리가 없다.**

| 칸 | 형 | 비고 |
|---|---|---|
| `id` | PK | |
| `item_id` | FK items | |
| `lot_number` | str(50) | 자재는 공급사 번호 · 자사는 배치 번호 |
| `lot_origin` | str(10) | 공급사 · 자사. **번호의 출처만 다르다** |
| `warehouse` | str(20) | `WAREHOUSE` |
| `stock_type` | str(10) | `STOCK_TYPE` — 양품 · 불량품 |
| `quantity` | float | `items.stock_uom` 단위 |
| `received_date` | date NULL | 자재 입고일 |
| `produced_date` | date NULL | 자사 생산일 |
| `passed_date` | date NULL | 합격일. 완제품 유효기간의 기산점 |
| `expiry_date` | date NULL | 파생해 저장한다 — 라벨에 찍혀 나갔으므로 설정기간을 바꿔도 안 바뀐다 |
| `reworked` | bool | 재작업 여부. **번호를 잘라 읽지 않는다** |

**제약**
- `CHECK quantity >= 0`
- `CHECK lot_origin='공급사' → received_date IS NOT NULL AND produced_date IS NULL`
- `CHECK lot_origin='자사' → produced_date IS NOT NULL`
- `CHECK` 재작업은 자사 로트에만
- **단방향** — `stock_type = '불량품'` ⇒ `warehouse = '제품'`
- **창고가 담는 품목 유형** — 원재료창고는 자재만, 제품창고는 완제품만,
  생산창고는 셋 다 (투입 대기 자재 · 반제품 · 완제품)

> **여기서 설계도를 한 번 잘못 읽었다.** 이 문서는 처음에 「양방향 CHECK(지적
> ①)」라고 적었는데, 지적 ①의 제목은 **「양방향 CHECK를 버려야 한다」**이다.
> 기존 저장소가 「제품창고 ⟺ OQC 합격」을 양방향으로 묶어 두었고, 그러면
> 제품창고 안에 함께 있는 OQC 불합격분이 설 자리가 없다. 개선안이 **단방향
> 둘**이었다. 여기서는 로트에 상태 칸이 없으므로(원칙 ①) 그중 재고구분 쪽
> 한 줄만 1단계에 선다.

`reworked` 가 예/아니오인 것은 **재작업 2회인 로트가 존재할 수 없기**
때문이다. 로트는 합격 후에만 생기므로, 재작업분이 재검사에서 또 떨어지면 로트가
아예 만들어지지 않고 폐기된다. 번호는 `...R` 로 남는다 — 창고의 라벨과 장부가
같아야 사람이 찾을 수 있고, `LOT-123` 과 `LOT-123R` 은 실제로 다른 물건이다.
**바뀌는 것은 하나뿐이다 — 판정을 문자열에서 하지 않는다.**

> **미결 — FIFO 정렬 키.** 출고 순서는 FIFO이고 기준은 입고일인데, 통합 표에서
> 「입고일」이 자재는 `received_date` 이고 자사는 `passed_date` 다. 파생으로
> 낼지 칸 하나(`stocked_date`)를 둘지는 **출고가 생기는 2단계에서 정한다.**
> 1단계에 정할 근거가 없다.

---

## 미룬 것과 새로 드러난 것

1단계를 지으면서 **정할 근거가 없어 미룬 자리**들이다. 미룬다는 사실 자체를
적어 두는 것이 목적이며, 값을 지어내지 않기 위해서다.

| 미결 | 언제 정하는가 |
|---|---|
| 재고 단위를 고치면 지나간 수량의 뜻이 바뀐다 | 품목 수정 화면이 서는 단계 |
| BOM 손실률 — 투입과 산출을 견주는 자리가 없다 | 견줄 실적이 생기는 5단계 |
| FIFO 정렬 키 — 통합 표에서 「입고일」이 자재는 `received_date`, 자사는 `passed_date` 다 | 출고가 생기는 2단계 |
| **「제품입고」의 짝이 없다** — 창고를 건너는 다른 이동은 두 줄인데 이것만 한 줄이라, 생산창고에서 빠지는 줄이 없으면 완제품이 그 창고에 영원히 쌓인다 | 재고이동이 서는 4단계 |
| **품목의 공정은 하나인데 검사는 두 단계를 받는다** — 반제품은 배합과 코팅, 완제품은 적층경화와 출하. 지금은 「산출되는 공정」을 적고 나머지는 검사 단계가 고르게 두었다 | 검사 화면이 서는 2 · 6단계 |
| **검사 항목이 17인가 18인가** — 설계도는 18이라 적었으나 공정별 표에서 실제로 나오는 것은 17이다. 「폭」을 세우면 18이 되지만 그것을 가리키는 불합격 코드가 없어 **불합격을 적을 수 없는 항목**이 남는다 | 폭을 따로 재기로 할 때 |

그리고 **1단계에 두지 않기로 정한 것** — 검사 기준의 칸 넷(부분군 크기 ·
목표 Cpk · 게이트 Ppk · WE 규칙 켬끔). 넷 다 읽는 쪽이 8단계에 서므로, 지금
두면 아무도 읽지 않는 칸에 값을 채우거나 빈 기준정보를 남기게 된다.

## 표에 없는 것

| 무엇 | 왜 없는가 |
|---|---|
| 상태 칸 전부 | 검사 대기 · 발주 종결 · 가용 · 만료 — 기록의 있고 없음이나 두 값의 견줌에서 나온다. 저장하는 상태는 `items.phase` 와 `RISK_STATUS` 둘뿐이고 **둘 다 사람이 하는 일이라** 남았다 |
| `tenant_id` | 단일 테넌트 |
| 수불 원장 | 2단계 — 로트가 생기는 것이 곧 재고가 생기는 것이라 함께 선다 |
| 검사 기록 · 측정값 줄 | 2단계 |
| 발주 · 오더 · 생산실적 · 출하 | 3단계 이후 |
| 사용자 · 권한 | 사람이 늘어나는 날 |
