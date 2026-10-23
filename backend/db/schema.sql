
CREATE TABLE IF NOT EXISTS raw_companies (
    row_id BIGSERIAL PRIMARY KEY,
    synthetic_u TEXT,
    raw_data JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_payments (
    row_id BIGSERIAL PRIMARY KEY,
    payer TEXT,
    beneficiary TEXT,
    pay_amt NUMERIC,
    pay_cnt BIGINT
);

CREATE TABLE IF NOT EXISTS raw_person_links (
    row_id BIGSERIAL PRIMARY KEY,
    synthetic_f TEXT,
    synthetic_u TEXT,
    raw_data JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_companies_u
ON raw_companies(synthetic_u);

CREATE INDEX IF NOT EXISTS idx_payments_payer
ON raw_payments(payer);

CREATE INDEX IF NOT EXISTS idx_payments_beneficiary
ON raw_payments(beneficiary);

CREATE INDEX IF NOT EXISTS idx_person_links_f
ON raw_person_links(synthetic_f);

CREATE INDEX IF NOT EXISTS idx_person_links_u
ON raw_person_links(synthetic_u);

CREATE INDEX IF NOT EXISTS idx_companies_group
ON raw_companies ((raw_data->>'GROUP_ID'));
