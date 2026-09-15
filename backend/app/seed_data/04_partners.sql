-- 거래처와 공급사별 품목.
--
-- **구매 리드타임은 시연용 임의값이다.** 실제 값은 공급사와의 거래에서 나온다.
-- 단위를 시간으로 두는 것은 생산 리드타임과 자를 맞추기 위해서다 — 역산이 두
-- 겹을 같은 자로 재야 「지금 발주해야 늦지 않는다」를 말할 수 있다.

INSERT INTO partners (code, name, partner_type) VALUES
  ('SUP-01', '한성케미칼',   '공급사'),
  ('SUP-02', '대영소재',     '공급사'),
  ('SUP-03', '정우필름',     '공급사'),
  ('SUP-04', '미래안료',     '공급사'),
  ('CUS-01', '동해전자',     '고객사'),
  ('CUS-02', '남광디스플레이', '고객사'),
  ('CUS-03', '서일산업',     '고객사');

-- **단위를 바꾸는 경계는 여기 하나뿐이다.** 포대로 사서 킬로그램으로 세고,
-- 롤로 사서 제곱미터로 센다. 경계가 둘이면 어느 쪽이 진실인지 알 수 없어지고
-- 원장의 합이 성립하지 않는다.
INSERT INTO supplier_items (partner_id, partner_type, item_id, lead_time_hours, purchase_uom, purchase_uom_group, conversion_factor)
SELECT s.id, s.partner_type, i.id, pair.hours, pair.uom, 'UOM', pair.factor
FROM (VALUES
  ('SUP-01', 'RM-01',  72.0, 'DRM', 200.0),
  ('SUP-01', 'RM-05',  48.0, 'DRM', 180.0),
  ('SUP-01', 'RM-08',  96.0, 'DRM', 200.0),
  ('SUP-01', 'RM-10',  96.0, 'DRM', 200.0),
  ('SUP-02', 'RM-02', 120.0, 'BAG',  25.0),
  ('SUP-02', 'RM-06', 120.0, 'BAG',  25.0),
  ('SUP-02', 'RM-09', 144.0, 'BAG',  25.0),
  ('SUP-02', 'RM-12',  72.0, 'BAG',  20.0),
  ('SUP-03', 'RM-04', 168.0, 'ROL', 300.0),
  ('SUP-03', 'RM-07', 168.0, 'ROL', 250.0),
  ('SUP-03', 'RM-11', 120.0, 'ROL', 250.0),
  ('SUP-03', 'RM-15',  96.0, 'ROL', 400.0),
  ('SUP-04', 'RM-03',  96.0, 'BAG',  10.0),
  ('SUP-04', 'RM-13', 168.0, 'KG',    1.0),
  ('SUP-04', 'RM-14', 120.0, 'BAG',  10.0)
) AS pair(supplier_code, item_code, hours, uom, factor)
JOIN partners s ON s.code = pair.supplier_code
JOIN items i ON i.code = pair.item_code;
