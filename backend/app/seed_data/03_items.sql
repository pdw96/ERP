-- 품목 스물다섯과 2단 BOM.
--
-- **여기 있는 숫자는 시연용 임의값이다.** 유효기간 · 안전재고 · 준비시간 ·
-- 개당 시간 어느 것도 실제 공정에서 잰 값이 아니다. 실제 값이 생기면 이 파일의
-- 해당 열을 고친다 — 코드를 몰라도 고칠 수 있게 SQL 에 둔 이유다.
--
-- **다만 고쳐서 닿는 곳은 아직 심기지 않은 데이터베이스뿐이다.** 이미 심긴
-- 데이터베이스는 이 파일의 이후 수정을 받지 않는다 — 시드는 품목 표가 비어
-- 있을 때만 돌기 때문이다(그 조건이 사람이 화면에서 고친 값을 지키는 자리다).
-- **살아 있는 데이터베이스의 기준정보를 고치는 것은 마이그레이션이다.**
--
-- 품목의 `process` 는 그 품목이 **산출되는** 공정이다. 자재는 수입, 반제품은
-- 배합, 완제품은 적층경화에서 나온다. 코팅(반제품 IPQC)과 출하(완제품 OQC)는
-- 품목이 아니라 **검사 단계**가 고르는 공정이므로 여기 적히지 않는다 —
-- 품목 하나가 공정 하나를 갖는 구조에서 검사를 두 번 받는 품목을 적는 방법이다.

-- ── 원자재 열다섯 ───────────────────────────────────────────────────────────
-- 세 무리로 갈린다 — 분체 다섯 · 액상과 수지 여섯 · 시트와 필름 넷. 검사 항목이
-- 품목마다 다르지 않고 무리마다 다르므로, 품목이 늘어도 코드는 잘 늘지 않는다.
--
-- **그 무리가 이제 `material_group` 이다.** 적어 두기만 하던 구분을 칸으로 세워
-- 수입 검사 기준이 그것을 축으로 걸린다 — 분말에 점도를, 라이너에 입도를 재라고
-- 내밀지 않게 된다. 무리별 수는 재고단위와 맞는다: 시트·필름 넷이 `M2` 넷이고,
-- 액상·수지 여섯은 `L` 둘에 수지·페이스트 넷을 더한 것이다.
--
-- **경계에 선 둘은 판단이다.** `RM-12` 안정화 첨가제를 분체로, `RM-14` 기능성
-- 염료를 액상·수지로 두었다. 실제 자재의 성상이 다르면 이 열만 고치면 된다 —
-- 코드를 몰라도 고칠 수 있게 SQL 에 둔 이유다.
--
-- 시트와 필름은 유효기간을 두지 않는다. `RM-05` 접착 수지가 마흔나흘로 가장
-- 짧다 — 부족이 가장 먼저 걸릴 품목이다.
INSERT INTO items (code, name, item_type, process, process_group, stock_uom, stock_uom_group, material_group, material_group_group, phase, shelf_life_days, safety_stock) VALUES
  ('RM-01', '폴리머 베이스',   '원자재', '수입', 'PROCESS', 'KG', 'UOM', '액상수지', 'MATERIAL_GROUP', '양산', 180,  800),
  ('RM-02', '세라믹 분말',     '원자재', '수입', 'PROCESS', 'KG', 'UOM', '분체',     'MATERIAL_GROUP', '양산', 365,  400),
  ('RM-03', '광학 안료',       '원자재', '수입', 'PROCESS', 'KG', 'UOM', '분체',     'MATERIAL_GROUP', '양산', 365,  150),
  ('RM-04', '보강 섬유',       '원자재', '수입', 'PROCESS', 'M2', 'UOM', '시트필름', 'MATERIAL_GROUP', '양산', NULL, 600),
  ('RM-05', '접착 수지',       '원자재', '수입', 'PROCESS', 'KG', 'UOM', '액상수지', 'MATERIAL_GROUP', '양산',  44,  250),
  ('RM-06', '방열 첨가제',     '원자재', '수입', 'PROCESS', 'KG', 'UOM', '분체',     'MATERIAL_GROUP', '양산', 365,  200),
  ('RM-07', '차단 필름',       '원자재', '수입', 'PROCESS', 'M2', 'UOM', '시트필름', 'MATERIAL_GROUP', '양산', NULL, 500),
  ('RM-08', '표면 코팅제',     '원자재', '수입', 'PROCESS', 'L',  'UOM', '액상수지', 'MATERIAL_GROUP', '양산', 120,  300),
  ('RM-09', '미세 충전재',     '원자재', '수입', 'PROCESS', 'KG', 'UOM', '분체',     'MATERIAL_GROUP', '양산', 365,  350),
  ('RM-10', '유연 가소제',     '원자재', '수입', 'PROCESS', 'L',  'UOM', '액상수지', 'MATERIAL_GROUP', '양산', 180,  280),
  ('RM-11', '보호 라이너',     '원자재', '수입', 'PROCESS', 'M2', 'UOM', '시트필름', 'MATERIAL_GROUP', '양산', NULL, 450),
  ('RM-12', '안정화 첨가제',   '원자재', '수입', 'PROCESS', 'KG', 'UOM', '분체',     'MATERIAL_GROUP', '양산',  90,  180),
  ('RM-13', '전도성 페이스트', '원자재', '수입', 'PROCESS', 'KG', 'UOM', '액상수지', 'MATERIAL_GROUP', '양산',  60,  120),
  ('RM-14', '기능성 염료',     '원자재', '수입', 'PROCESS', 'KG', 'UOM', '액상수지', 'MATERIAL_GROUP', '양산', 240,  100),
  ('RM-15', '포장 라미네이트', '원자재', '수입', 'PROCESS', 'M2', 'UOM', '시트필름', 'MATERIAL_GROUP', '양산', NULL, 700);

-- ── 반제품 다섯 ─────────────────────────────────────────────────────────────
-- **표가 둘이던 때는 이 다섯 줄이 설 자리가 없었다.** 반제품은 만들어지면서
-- 쓰이므로 제품 표에도 자재 표에도 온전히 속하지 못했다.
--
-- 유효기간이 전부 NULL 인 것은 비워 둔 것이 아니라 **그렇게 정해진 것**이다 —
-- 제약이 그것을 강제한다. 안전재고도 비워 둔다: 반제품은 오더가 낳는 것이라
-- 「얼마를 늘 갖고 있을 것인가」가 아직 물음이 아니다.
INSERT INTO items (code, name, item_type, process, process_group, stock_uom, stock_uom_group, phase, shelf_life_days, safety_stock, setup_hours, hours_per_unit) VALUES
  ('SF-01', '아크솔 베이스', '반제품', '배합', 'PROCESS', 'KG', 'UOM', '양산', NULL, NULL, 2.0, 0.010),
  ('SF-02', '노바 베이스',   '반제품', '배합', 'PROCESS', 'KG', 'UOM', '양산', NULL, NULL, 2.5, 0.012),
  ('SF-03', '루멘 베이스',   '반제품', '배합', 'PROCESS', 'KG', 'UOM', '초기', NULL, NULL, 3.0, 0.015),
  ('SF-04', '벨로스 베이스', '반제품', '배합', 'PROCESS', 'KG', 'UOM', '양산', NULL, NULL, 2.0, 0.011),
  ('SF-05', '테라 베이스',   '반제품', '배합', 'PROCESS', 'KG', 'UOM', '양산', NULL, NULL, 2.2, 0.009);

-- ── 완제품 다섯 ─────────────────────────────────────────────────────────────
-- **안전재고를 비워 둔다.** 칸은 통합으로 생겼지만 값을 정한 사람이 아직 없다 —
-- 없는 값을 지어내면 화면에서는 있는 것처럼 보인다.
--
-- `SF-03` · `FG-03` 이 「초기」 단계인 것은 양산 전환 판정이 실제로 걸릴 자리를
-- 하나 두기 위해서다 — 전부 「양산」이면 그 화면이 빈 채로 선다.
INSERT INTO items (code, name, item_type, process, process_group, stock_uom, stock_uom_group, phase, shelf_life_days, safety_stock, setup_hours, hours_per_unit) VALUES
  ('FG-01', '아크솔 시트', '완제품', '적층경화', 'PROCESS', 'M2', 'UOM', '양산', 180, NULL, 1.5, 0.020),
  ('FG-02', '노바필름',   '완제품', '적층경화', 'PROCESS', 'M2', 'UOM', '양산', 180, NULL, 1.5, 0.018),
  ('FG-03', '루멘코트',   '완제품', '적층경화', 'PROCESS', 'M2', 'UOM', '초기', 150, NULL, 2.0, 0.025),
  ('FG-04', '벨로스랩',   '완제품', '적층경화', 'PROCESS', 'EA', 'UOM', '양산', 365, NULL, 1.8, 0.030),
  ('FG-05', '테라패널',   '완제품', '적층경화', 'PROCESS', 'EA', 'UOM', '양산', 365, NULL, 2.5, 0.040);

-- ── 2단 BOM ─────────────────────────────────────────────────────────────────
-- 1단은 완제품 ← 반제품, 2단은 반제품 ← 원자재. **단계가 양쪽 유형을 정하므로**
-- 3단은 적을 수가 없다.
--
-- `id` 는 순번이라 미리 알 수 없다. 코드로 찾아 넣는다.

-- 1단 — 완제품 하나에 반제품 하나.
INSERT INTO bom_components (parent_item_id, parent_item_type, child_item_id, child_item_type, level, unit_quantity)
SELECT p.id, p.item_type, c.id, c.item_type, 1, pair.qty
FROM (VALUES
  ('FG-01', 'SF-01', 1.20),
  ('FG-02', 'SF-02', 1.10),
  ('FG-03', 'SF-03', 1.35),
  ('FG-04', 'SF-04', 2.40),
  ('FG-05', 'SF-05', 3.10)
) AS pair(parent_code, child_code, qty)
JOIN items p ON p.code = pair.parent_code
JOIN items c ON c.code = pair.child_code;

-- 2단 — 반제품 하나에 원자재 여럿. `RM-01` 폴리머 베이스는 다섯 전부에 들어가는
-- 공통 기재다.
INSERT INTO bom_components (parent_item_id, parent_item_type, child_item_id, child_item_type, level, unit_quantity)
SELECT p.id, p.item_type, c.id, c.item_type, 2, pair.qty
FROM (VALUES
  ('SF-01', 'RM-01', 0.60), ('SF-01', 'RM-02', 0.25), ('SF-01', 'RM-05', 0.15), ('SF-01', 'RM-04', 0.30),
  ('SF-02', 'RM-01', 0.50), ('SF-02', 'RM-03', 0.10), ('SF-02', 'RM-08', 0.40), ('SF-02', 'RM-07', 0.25),
  ('SF-03', 'RM-01', 0.55), ('SF-03', 'RM-14', 0.05), ('SF-03', 'RM-10', 0.40),
  ('SF-04', 'RM-01', 0.40), ('SF-04', 'RM-06', 0.20), ('SF-04', 'RM-13', 0.40), ('SF-04', 'RM-11', 0.35),
  ('SF-05', 'RM-01', 0.45), ('SF-05', 'RM-09', 0.30), ('SF-05', 'RM-12', 0.25), ('SF-05', 'RM-15', 0.50)
) AS pair(parent_code, child_code, qty)
JOIN items p ON p.code = pair.parent_code
JOIN items c ON c.code = pair.child_code;
