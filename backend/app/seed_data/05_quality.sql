-- 공정별 검사 기준 — (공정 × 검사항목).
--
-- **규격 상·하한과 중심선은 전부 시연용 임의값이다.** 설계도가 「규격은 고객이
-- 정한다 — 지금은 임의 설정」이라 적어 둔 그대로이며, 실제 값은 고객 도면이
-- 있어야 나온다. 이 파일의 숫자를 근거로 어떤 판단도 하면 안 된다.
--
-- **σ 는 전부 비어 있고 출처는 「미정」이다.** 규격에서 뽑은 σ 는 어떤 계수를
-- 쓰든 Cpk 를 그 계수의 역수로 못박아, 어떤 공정에서든 같은 숫자가 나온다.
-- 경고선과 WE 규칙 4 는 σ 없이 그대로 도므로 비워 두는 편이 안전하다 —
-- 측정값이 쌓이면 실측으로 채운다. **그 채우기는 이 파일이 아니라 돌고 있는
-- 데이터베이스에서 일어난다** — 이미 심긴 곳은 이 파일의 수정을 받지 않는다.
--
-- 경시 변화(`time_variant`)가 켜진 항목은 여섯이다 — 수분 · 색차 · 점도 ·
-- 포장 · 접착력 · 광택. 만료 로트의 재검사가 다시 보는 것은 이것뿐이다:
-- 「시간이 이 값을 바꿀 수 있는가」가 유일한 잣대다.

-- ── 수입 (IQC) ─────────────────────────────────────────────────────────────
INSERT INTO process_inspection_standards
  (process_group, process_code, item_group, item_code,
   upper_spec_limit, lower_spec_limit, center_line, warning_ratio, sigma, sigma_source, time_variant, unit) VALUES
  ('PROCESS', '수입', 'INSP_ITEM', '입도',   50.0,   10.0,   30.0, 0.70, NULL, '미정', FALSE, 'µm'),
  ('PROCESS', '수입', 'INSP_ITEM', '수분',    0.50,  NULL,    0.20, 0.70, NULL, '미정', TRUE,  '%'),
  ('PROCESS', '수입', 'INSP_ITEM', '점도', 4000.0, 2000.0, 3000.0, 0.70, NULL, '미정', TRUE,  'cP'),
  ('PROCESS', '수입', 'INSP_ITEM', '두께',  105.0,   95.0,  100.0, 0.70, NULL, '미정', FALSE, 'µm'),
  ('PROCESS', '수입', 'INSP_ITEM', '색차',    1.00,  NULL,    0.30, 0.70, NULL, '미정', TRUE,  'ΔE'),
  -- 계수 항목은 재는 것이 아니라 세는 것이라 규격도 중심선도 없다.
  ('PROCESS', '수입', 'INSP_ITEM', '이물',   NULL,   NULL,   NULL, 0.70, NULL, '미정', FALSE, NULL),
  ('PROCESS', '수입', 'INSP_ITEM', '포장',   NULL,   NULL,   NULL, 0.70, NULL, '미정', TRUE,  NULL),
  ('PROCESS', '수입', 'INSP_ITEM', '성적서', NULL,   NULL,   NULL, 0.70, NULL, '미정', FALSE, NULL);

-- ── 배합 (IPQC) ────────────────────────────────────────────────────────────
INSERT INTO process_inspection_standards
  (process_group, process_code, item_group, item_code,
   upper_spec_limit, lower_spec_limit, center_line, warning_ratio, sigma, sigma_source, time_variant, unit) VALUES
  ('PROCESS', '배합', 'INSP_ITEM', '공정온도',   85.0,   75.0,   80.0, 0.70, NULL, '미정', FALSE, '°C'),
  ('PROCESS', '배합', 'INSP_ITEM', '혼합점도', 3500.0, 2500.0, 3000.0, 0.70, NULL, '미정', FALSE, 'cP'),
  ('PROCESS', '배합', 'INSP_ITEM', '배합비',    102.0,   98.0,  100.0, 0.70, NULL, '미정', FALSE, '%');

-- ── 코팅 (IPQC) ────────────────────────────────────────────────────────────
INSERT INTO process_inspection_standards
  (process_group, process_code, item_group, item_code,
   upper_spec_limit, lower_spec_limit, center_line, warning_ratio, sigma, sigma_source, time_variant, unit) VALUES
  ('PROCESS', '코팅', 'INSP_ITEM', '도포두께', 22.0, 18.0, 20.0, 0.70, NULL, '미정', FALSE, 'µm'),
  ('PROCESS', '코팅', 'INSP_ITEM', '라인속도', 12.0,  8.0, 10.0, 0.70, NULL, '미정', FALSE, 'm/min');

-- ── 적층 · 경화 (FQC) ──────────────────────────────────────────────────────
INSERT INTO process_inspection_standards
  (process_group, process_code, item_group, item_code,
   upper_spec_limit, lower_spec_limit, center_line, warning_ratio, sigma, sigma_source, time_variant, unit) VALUES
  ('PROCESS', '적층경화', 'INSP_ITEM', '두께',   105.0,  95.0, 100.0, 0.70, NULL, '미정', FALSE, 'µm'),
  ('PROCESS', '적층경화', 'INSP_ITEM', '광택',    95.0,  80.0,  88.0, 0.70, NULL, '미정', TRUE,  'GU'),
  ('PROCESS', '적층경화', 'INSP_ITEM', '색차',     1.00, NULL,   0.30, 0.70, NULL, '미정', TRUE,  'ΔE'),
  ('PROCESS', '적층경화', 'INSP_ITEM', '접착력',  NULL,   3.00,  4.00, 0.70, NULL, '미정', TRUE,  'N/mm'),
  -- `FQ-FM`(외관 이물 검출)이 FQC 에서 난다 — 그 단계에서 쓸 수 있는 코드인데
  -- 기준이 없으면 무엇을 보고 판정하는지 표가 말하지 못한다.
  ('PROCESS', '적층경화', 'INSP_ITEM', '외관이물', NULL,  NULL,  NULL, 0.70, NULL, '미정', FALSE, NULL);

-- ── 출하 (OQC) ─────────────────────────────────────────────────────────────
-- FQC 와 **같은 다섯을 다시 본다.** 시점과 대상이 다르기 때문이다 — FQC 는
-- 배치를 보고 OQC 는 출하 로트를 본다. 같은 코드가 어느 단계에서 났는지를
-- 셀 수 있게 되는 것이 코드화의 진짜 이득이다.
--
-- **설계도 공정표는 여기에 「치수」를 넣었다.** 뺀 이유는 그것을 가리키는 OQC
-- 불합격 코드가 없기 때문이다 — 잴 수는 있어도 불합격을 적을 수 없는 항목이라,
-- 「폭」을 뺀 것과 같은 자리다. 치수를 따로 재기로 하면 항목과 코드를 함께 더한다.
INSERT INTO process_inspection_standards
  (process_group, process_code, item_group, item_code,
   upper_spec_limit, lower_spec_limit, center_line, warning_ratio, sigma, sigma_source, time_variant, unit) VALUES
  ('PROCESS', '출하', 'INSP_ITEM', '두께',     105.0,  95.0, 100.0, 0.70, NULL, '미정', FALSE, 'µm'),
  ('PROCESS', '출하', 'INSP_ITEM', '광택',      95.0,  80.0,  88.0, 0.70, NULL, '미정', TRUE,  'GU'),
  ('PROCESS', '출하', 'INSP_ITEM', '색차',       1.00, NULL,   0.30, 0.70, NULL, '미정', TRUE,  'ΔE'),
  ('PROCESS', '출하', 'INSP_ITEM', '접착력',    NULL,   3.00,  4.00, 0.70, NULL, '미정', TRUE,  'N/mm'),
  ('PROCESS', '출하', 'INSP_ITEM', '외관이물',  NULL,  NULL,  NULL, 0.70, NULL, '미정', FALSE, NULL);
