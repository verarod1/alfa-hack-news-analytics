-- Entirely artificial acceptance data, not the hackathon dataset.
-- Applied only on first initialization of compose.review.yml's own volume.
BEGIN;
INSERT INTO raw_companies (synthetic_u, raw_data) VALUES
('U_44564', '{"SYNTHETIC_U":"U_44564","CL_TYPE":"CLIENT","MAINOKVED_NAME":"[ТЕСТ] Производство","REGION":"Учебный регион","REVENUE_COMPANY":"120000000","GROUP_ID":"review_group","CL_PRODUCT_LOA_MARK":"1"}'),
('U_19717', '{"SYNTHETIC_U":"U_19717","CL_TYPE":"CLIENT","MAINOKVED_NAME":"[ТЕСТ] Торговля","REGION":"Учебный регион","REVENUE_COMPANY":"80000000","GROUP_ID":"review_group","CL_PRODUCT_RKO_MARK":"1"}'),
('U_9250', '{"SYNTHETIC_U":"U_9250","CL_TYPE":"CLIENT","MAINOKVED_NAME":"[ТЕСТ] Логистика","REGION":"Учебный регион","REVENUE_COMPANY":"60000000","CL_PRODUCT_LEA_MARK":"1"}');
INSERT INTO raw_payments (payer, beneficiary, pay_amt, pay_cnt) VALUES
('U_44564','U_19717',120000,3), ('U_19717','U_9250',80000,2);
INSERT INTO raw_person_links (synthetic_f, synthetic_u, raw_data) VALUES
('F_review','U_44564','{"SYNTHETIC_F":"F_review","SYNTHETIC_U":"U_44564"}'),
('F_review','U_19717','{"SYNTHETIC_F":"F_review","SYNTHETIC_U":"U_19717"}');
INSERT INTO news (id,title,text,published_at,source_id,source_name,source_url,content_hash,is_synthetic)
SELECT 'review_news_' || n,
       '[ТЕСТ] Учебная новость ' || n,
       'Полностью синтетический сценарий изменения стоимости финансирования, доставки и оборудования. Не является реальной публикацией. Пример номер ' || n,
       '2026-10-26T09:00:00Z'::timestamptz,
       'review_local','Синтетический проверочный набор',NULL,md5('review-v1-' || n),true
FROM generate_series(1,3) AS n;
COMMIT;
