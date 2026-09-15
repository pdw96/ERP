-- 공통코드에 딸린 속성 — 확장 표 셋과 「코드 × 단계」.

-- ── 확장 ① 수불유형 ────────────────────────────────────────────────────────
-- 짝은 **창고를 건너 두 줄이 나는** 유형끼리 서로를 가리킨다. 한쪽만 나는
-- 사고를 구조가 막는다.
INSERT INTO txn_type_attributes (group_code, code, total_effect, paired_code, source_document_type) VALUES
  ('TXN_TYPE', '전기이월',     '기준점', NULL, '월말 마감'),
  ('TXN_TYPE', '구매입고',     '증가',   NULL, '가입고'),
  ('TXN_TYPE', '구매반품출고', '감소',   NULL, '구매반품관리'),
  ('TXN_TYPE', '생산출고',     '감소',   NULL, '재고이동 처리'),
  ('TXN_TYPE', '생산입고',     '증가',   '생산출고', '재고이동 처리'),
  ('TXN_TYPE', '생산소모',     '감소',   NULL, '검사 기록'),
  ('TXN_TYPE', '생산산출',     '증가',   '생산소모', '검사 기록'),
  ('TXN_TYPE', '제품입고',     '증가',   NULL, '재고이동 처리'),
  ('TXN_TYPE', '판매출고',     '감소',   NULL, '출하 실적'),
  ('TXN_TYPE', '재고구분대체', '불변',   NULL, '양불이동'),
  ('TXN_TYPE', '조정',         '양방향', NULL, '재고조정'),
  ('TXN_TYPE', '폐기출고',     '감소',   NULL, '재작업 불가 · OQC 불합격');

-- 짝은 **양쪽에서** 서로를 가리켜야 한다. 위에서 한 방향만 적은 것은 넣는
-- 순서 때문이다 — 가리킬 줄이 아직 없으면 외래키가 막는다.
UPDATE txn_type_attributes SET paired_code = '생산입고' WHERE code = '생산출고';
UPDATE txn_type_attributes SET paired_code = '생산산출' WHERE code = '생산소모';

-- **「제품입고」의 짝이 비어 있다.** 설계도 표에 대응하는 출고 유형이 없다.
-- 완제품이 생산창고에서 제품창고로 건너가는데, 창고를 건너는 다른 이동은 두
-- 줄이 나는 반면 이것만 한 줄이다. 생산창고에서 빠지는 줄이 없으면 그 창고의
-- 완제품이 영원히 쌓인다. 재고이동이 실제로 서는 4단계에서 드러날 자리이며,
-- 여기서는 설계도 표를 그대로 옮긴다 — 값을 지어내지 않는다.

-- ── 확장 ② 불합격사유 ──────────────────────────────────────────────────────
-- 계량 열넷은 검사 항목을 가리킨다. 계수 다섯은 가리킬 항목이 없을 수 있다.
--
-- **코드와 항목은 1:1 이 아니다.** 단계가 다르면 같은 항목에 다른 코드가 붙는다
-- — 두께는 IQC 에서 `IQ-DIM`, FQC·OQC 에서 `FQ-THK` 다. 그래서 계량 코드는
-- 열넷이고 계량 항목은 열둘이다.
--
-- `IQ-DIM` 의 이름은 「치수 이탈」이지만 가리키는 항목은 **두께**다. 설계도가
-- 「치수 이탈(두께 · 폭)」이라 적었고, 수입 공정이 실제로 재는 것이 두께이기
-- 때문이다 — 이름이 아니라 **재는 것**을 가리켜야 기준이 끌려온다.
--
-- `IQ-EXP` 를 계수로 둔다. 재는 값이 아니라 **입고일 + 설정기간의 비교 결과**를
-- 시스템이 달아 주는 것이라, 관리도에 오를 측정값이 없다.
INSERT INTO nonconformity_attributes (group_code, code, measure_kind, inspection_item_group, inspection_item_code) VALUES
  ('NC_REASON', 'IQ-FM',  '계수', 'INSP_ITEM', '이물'),
  ('NC_REASON', 'IQ-DIM', '계량', 'INSP_ITEM', '두께'),
  ('NC_REASON', 'IQ-VIS', '계량', 'INSP_ITEM', '점도'),
  ('NC_REASON', 'IQ-PSD', '계량', 'INSP_ITEM', '입도'),
  ('NC_REASON', 'IQ-MOI', '계량', 'INSP_ITEM', '수분'),
  ('NC_REASON', 'IQ-COL', '계량', 'INSP_ITEM', '색차'),
  ('NC_REASON', 'IQ-EXP', '계수', 'INSP_ITEM', NULL),
  ('NC_REASON', 'IQ-PKG', '계수', 'INSP_ITEM', '포장'),
  ('NC_REASON', 'IQ-DOC', '계수', 'INSP_ITEM', '성적서'),
  ('NC_REASON', 'IP-TMP', '계량', 'INSP_ITEM', '공정온도'),
  ('NC_REASON', 'IP-VIS', '계량', 'INSP_ITEM', '혼합점도'),
  ('NC_REASON', 'IP-SPD', '계량', 'INSP_ITEM', '라인속도'),
  ('NC_REASON', 'IP-MIX', '계량', 'INSP_ITEM', '배합비'),
  ('NC_REASON', 'IP-THK', '계량', 'INSP_ITEM', '도포두께'),
  ('NC_REASON', 'FQ-THK', '계량', 'INSP_ITEM', '두께'),
  ('NC_REASON', 'FQ-GLS', '계량', 'INSP_ITEM', '광택'),
  ('NC_REASON', 'FQ-FM',  '계수', 'INSP_ITEM', '외관이물'),
  ('NC_REASON', 'FQ-ADH', '계량', 'INSP_ITEM', '접착력'),
  ('NC_REASON', 'FQ-COL', '계량', 'INSP_ITEM', '색차');

-- ── 처분 기본값은 「코드 × 단계」에 붙는다 ──────────────────────────────────
-- **줄이 있는 것 자체가 「그 단계에서 쓸 수 있는 코드」라는 뜻**이다.
--
-- 「고칠 수 있는가」가 처분을 가른다 — 고칠 수 없는 것은 폐기, 쓸 수는 있는
-- 것은 등급 하향이나 특채, 물건이 아니라 조건이 틀린 것은 재작업이다.
INSERT INTO nonconformity_stage_rules
  (reason_group, reason_code, stage_group, stage_code, disposition, special_acceptance_allowed) VALUES
  -- IQC — 자재. 특채가 열리는 자리는 셋뿐이다.
  ('NC_REASON', 'IQ-FM',  'INSP_STAGE', 'IQC', '반품', FALSE),
  ('NC_REASON', 'IQ-DIM', 'INSP_STAGE', 'IQC', '반품', FALSE),
  ('NC_REASON', 'IQ-VIS', 'INSP_STAGE', 'IQC', '반품', TRUE),
  ('NC_REASON', 'IQ-PSD', 'INSP_STAGE', 'IQC', '반품', FALSE),
  ('NC_REASON', 'IQ-MOI', 'INSP_STAGE', 'IQC', '반품', FALSE),
  ('NC_REASON', 'IQ-COL', 'INSP_STAGE', 'IQC', '반품', TRUE),
  ('NC_REASON', 'IQ-EXP', 'INSP_STAGE', 'IQC', '반품', FALSE),
  ('NC_REASON', 'IQ-PKG', 'INSP_STAGE', 'IQC', '환불', FALSE),
  ('NC_REASON', 'IQ-DOC', 'INSP_STAGE', 'IQC', '반품', TRUE),

  -- IPQC — 반제품. 조건이 틀린 것은 재작업, 물건이 틀린 것은 폐기.
  ('NC_REASON', 'IP-TMP', 'INSP_STAGE', 'IPQC', '재작업', FALSE),
  ('NC_REASON', 'IP-VIS', 'INSP_STAGE', 'IPQC', '재작업', FALSE),
  ('NC_REASON', 'IP-SPD', 'INSP_STAGE', 'IPQC', '재작업', FALSE),
  ('NC_REASON', 'IP-MIX', 'INSP_STAGE', 'IPQC', '폐기',   FALSE),
  ('NC_REASON', 'IP-THK', 'INSP_STAGE', 'IPQC', '재작업', FALSE),

  -- FQC — 완제품 배치. 아직 로트가 없으므로 고칠 수 있으면 재작업이다.
  ('NC_REASON', 'FQ-THK', 'INSP_STAGE', 'FQC', '재작업', FALSE),
  ('NC_REASON', 'FQ-GLS', 'INSP_STAGE', 'FQC', '재작업', FALSE),
  ('NC_REASON', 'FQ-FM',  'INSP_STAGE', 'FQC', '폐기',   FALSE),
  ('NC_REASON', 'FQ-ADH', 'INSP_STAGE', 'FQC', '폐기',   FALSE),
  ('NC_REASON', 'FQ-COL', 'INSP_STAGE', 'FQC', '재작업', FALSE),

  -- OQC — 출하 로트. **같은 코드인데 처분이 다르다** — 이미 로트가 있으므로
  -- 재작업이 아니라 양불이동이고, 그 다음이 등급 하향이나 폐기다.
  ('NC_REASON', 'FQ-THK', 'INSP_STAGE', 'OQC', '등급 하향', FALSE),
  ('NC_REASON', 'FQ-GLS', 'INSP_STAGE', 'OQC', '등급 하향', FALSE),
  ('NC_REASON', 'FQ-FM',  'INSP_STAGE', 'OQC', '폐기',      FALSE),
  ('NC_REASON', 'FQ-ADH', 'INSP_STAGE', 'OQC', '폐기',      FALSE),
  ('NC_REASON', 'FQ-COL', 'INSP_STAGE', 'OQC', '등급 하향', FALSE),

  -- 재검사 — 만료 로트. **경시 변화 항목만 본다**(수분 · 색차 · 점도 · 포장 ·
  -- 접착력 · 광택). 합격하면 유효기간이 갱신되고 불합격이면 폐기다.
  ('NC_REASON', 'IQ-MOI', 'INSP_STAGE', '재검사', '폐기', FALSE),
  ('NC_REASON', 'IQ-COL', 'INSP_STAGE', '재검사', '폐기', FALSE),
  ('NC_REASON', 'IQ-VIS', 'INSP_STAGE', '재검사', '폐기', FALSE),
  ('NC_REASON', 'IQ-PKG', 'INSP_STAGE', '재검사', '폐기', FALSE),
  ('NC_REASON', 'FQ-ADH', 'INSP_STAGE', '재검사', '폐기', FALSE),
  ('NC_REASON', 'FQ-GLS', 'INSP_STAGE', '재검사', '폐기', FALSE);

-- ── 확장 ③ 미납종결사유 ────────────────────────────────────────────────────
-- 성적 축이 **비어 있으면 공급사 성적에 잡히지 않는다.** 따로 「반영 여부」
-- 칸을 두지 않는 이유가 PO-EOL 이다 — 공급사 쪽인데 공급사의 잘못이 아니다.
INSERT INTO purchase_close_attributes (group_code, code, responsibility, scorecard_axis, reorder_default) VALUES
  ('PO_CLOSE', 'PO-SHT', '공급사', '수량 준수율',  '필요'),
  ('PO_CLOSE', 'PO-DLY', '공급사', '납기 준수율',  '필요'),
  ('PO_CLOSE', 'PO-STK', '공급사', '공급 가능성',  '필요'),
  ('PO_CLOSE', 'PO-EOL', '공급사', NULL,           '필요'),
  ('PO_CLOSE', 'PO-CHG', '자사',   NULL,           '불필요'),
  ('PO_CLOSE', 'PO-CAN', '자사',   NULL,           '불필요'),
  ('PO_CLOSE', 'PO-ERR', '자사',   NULL,           '건별');
