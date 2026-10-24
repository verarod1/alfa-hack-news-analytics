-- Только если прежний mvp.sql уже применён. Данные raw_* не изменяются.
-- Применять вручную после согласования БД и остановки старых обработчиков.
BEGIN;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS importance TEXT;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS run_token TEXT;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS request_key TEXT;
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM analyses WHERE result->>'importance' NOT IN ('normal','important','critical')) THEN
        RAISE EXCEPTION 'Legacy importance requires manual review before migration';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='analyses'::regclass AND conname='analyses_importance_check') THEN
        ALTER TABLE analyses ADD CONSTRAINT analyses_importance_check CHECK (importance IN ('normal','important','critical'));
    END IF;
END $$;
UPDATE analyses SET importance=result->>'importance'
WHERE importance IS NULL AND result->>'importance' IN ('normal','important','critical');
ALTER TABLE analysis_steps ADD COLUMN IF NOT EXISTS attempt INTEGER NOT NULL DEFAULT 1;
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='analysis_steps'::regclass AND contype='p'
               AND pg_get_constraintdef(oid) NOT LIKE '%attempt%') THEN
        -- Меняется только ключ новых таблиц, строки и исходные таблицы сохраняются.
        ALTER TABLE analysis_steps DROP CONSTRAINT analysis_steps_pkey;
        ALTER TABLE analysis_steps ADD PRIMARY KEY (analysis_id,attempt,step_order);
    END IF;
END $$;
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS request_key TEXT;
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS reply_to TEXT UNIQUE REFERENCES chat_messages(id);
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS response_status TEXT;
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS response_token TEXT;
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS response_updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}';
COMMIT;
-- Затем выполнить текущий mvp.sql: он создаст news_relevance и новые индексы.
-- Старые completed-результаты отдельно проверить на новый DTO statements/sources.
