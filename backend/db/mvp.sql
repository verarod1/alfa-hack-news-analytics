-- Применять отдельно после согласования целевой БД. Исходные raw_* не меняются.
BEGIN;
CREATE TABLE IF NOT EXISTS news (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL CHECK (btrim(title) <> ''),
    text TEXT,
    published_at TIMESTAMPTZ,
    source_id TEXT,
    source_name TEXT,
    source_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    content_hash TEXT NOT NULL UNIQUE,
    is_synthetic BOOLEAN NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_news_published ON news(published_at DESC, id);

CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('ceo', 'cfo')),
    news_id TEXT NOT NULL REFERENCES news(id),
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    result JSONB,
    error_code TEXT,
    importance TEXT CHECK (importance IN ('normal', 'important', 'critical')),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    run_token TEXT,
    request_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((status = 'completed' AND result IS NOT NULL) OR
           (status <> 'completed' AND result IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_analyses_context ON analyses(company_id, role, created_at DESC, id);
CREATE INDEX IF NOT EXISTS idx_analyses_news ON analyses(news_id, company_id, role);

CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_request ON analyses(company_id,role,request_key) WHERE request_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analyses_queue ON analyses(status, created_at, id);
CREATE INDEX IF NOT EXISTS idx_analyses_attention ON analyses(company_id, role, importance, created_at DESC);

CREATE TABLE IF NOT EXISTS news_relevance (
    company_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('ceo', 'cfo')),
    news_id TEXT NOT NULL REFERENCES news(id),
    score DOUBLE PRECISION NOT NULL CHECK (score >= 0 AND score <= 1 AND score <> 'NaN'::float8),
    reasons JSONB NOT NULL CHECK (jsonb_typeof(reasons) = 'array' AND jsonb_array_length(reasons) > 0),
    method TEXT NOT NULL,
    method_version TEXT NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id, role, news_id)
);
CREATE INDEX IF NOT EXISTS idx_relevance_rank ON news_relevance(company_id, role, score DESC, news_id);

CREATE TABLE IF NOT EXISTS analysis_steps (
    analysis_id TEXT NOT NULL REFERENCES analyses(id),
    attempt INTEGER NOT NULL DEFAULT 1 CHECK (attempt > 0),
    step_order INTEGER NOT NULL CHECK (step_order > 0),
    name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    model TEXT,
    tool TEXT,
    summary TEXT,
    source_ids JSONB NOT NULL DEFAULT '[]',
    validation JSONB NOT NULL DEFAULT '{"performed":false,"passed":null}',
    PRIMARY KEY (analysis_id, attempt, step_order)
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    analysis_id TEXT NOT NULL UNIQUE REFERENCES analyses(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL CHECK (btrim(content) <> ''),
    evidence_ids JSONB NOT NULL DEFAULT '[]',
    request_key TEXT,
    reply_to TEXT UNIQUE REFERENCES chat_messages(id),
    response_token TEXT,
    response_updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    response_status TEXT CHECK (response_status IN ('queued','running','completed','failed')),
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_message_key ON chat_messages(conversation_id, request_key)
    WHERE role='user' AND request_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON chat_messages(conversation_id, created_at, id);
COMMIT;
