-- ============================================================
-- Marketing OS Bot — Fresh Setup SQL
-- Chạy toàn bộ file này trong Supabase SQL Editor
-- Xoá hết bảng cũ và tạo lại từ đầu
-- ============================================================


-- ── BƯỚC 1: XOÁ SẠCH (thứ tự quan trọng vì FK) ─────────────

DROP TABLE IF EXISTS spy_cache        CASCADE;
DROP TABLE IF EXISTS spy_targets      CASCADE;
DROP TABLE IF EXISTS fb_credentials   CASCADE;
DROP TABLE IF EXISTS sessions         CASCADE;


-- ── BƯỚC 2: TẠO BẢNG ────────────────────────────────────────

-- sessions: trạng thái pipeline của mỗi user
-- results (JSONB) chứa toàn bộ output Tier 1/2/3 (~60-80KB khi full)
-- → get_session() chỉ load metadata (không có results) để tiết kiệm bandwidth
-- → get_session_with_results() load đầy đủ khi chạy pipeline
CREATE TABLE sessions (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              BIGINT      NOT NULL UNIQUE,
    stage                TEXT        NOT NULL DEFAULT 'idle',
    selected_task        TEXT        NOT NULL DEFAULT '',
    selected_campaign_id TEXT        NOT NULL DEFAULT '',
    campaign_profile     JSONB       NOT NULL DEFAULT '{}',
    profile              JSONB       NOT NULL DEFAULT '{}',
    intake_history       JSONB       NOT NULL DEFAULT '[]',
    results              JSONB       NOT NULL DEFAULT '{}',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- fb_credentials: FB Ads access token (Fernet encrypted tại application layer)
CREATE TABLE fb_credentials (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          BIGINT      NOT NULL UNIQUE,
    encrypted_token  TEXT        NOT NULL,
    ad_account_id    TEXT        NOT NULL DEFAULT '',
    page_id          TEXT        NOT NULL DEFAULT '',
    token_expires_at TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- spy_targets: fanpage đối thủ cần theo dõi
CREATE TABLE spy_targets (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         BIGINT      NOT NULL,
    fanpage_url     TEXT        NOT NULL,
    label           TEXT        NOT NULL DEFAULT '',
    poll_interval_h INT         NOT NULL DEFAULT 24
                                CHECK (poll_interval_h IN (6, 12, 24)),
    last_polled_at  TIMESTAMPTZ,
    is_active       BOOLEAN     NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- spy_cache: snapshot + Haiku analysis mỗi lần poll
CREATE TABLE spy_cache (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    target_id   UUID        NOT NULL REFERENCES spy_targets(id) ON DELETE CASCADE,
    snapshot    JSONB       NOT NULL DEFAULT '{}',
    analysis    TEXT,
    alert_sent  BOOLEAN     NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ── BƯỚC 3: INDEXES ─────────────────────────────────────────

-- sessions: lookup nhanh theo user_id
CREATE INDEX idx_sessions_user        ON sessions (user_id);

-- spy_targets: lấy targets active của 1 user
CREATE INDEX idx_spy_targets_user     ON spy_targets (user_id, is_active);

-- spy_cache: lấy snapshots mới nhất của 1 target
CREATE INDEX idx_spy_cache_target     ON spy_cache (target_id, created_at DESC);

-- spy_cache: worker dispatch chỉ query alert_sent=false
CREATE INDEX idx_spy_cache_unsent     ON spy_cache (alert_sent)
    WHERE alert_sent = false;


-- ── BƯỚC 4: AUTO-UPDATE updated_at ──────────────────────────

CREATE OR REPLACE FUNCTION _set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION _set_updated_at();

CREATE TRIGGER trg_fb_credentials_updated_at
    BEFORE UPDATE ON fb_credentials
    FOR EACH ROW EXECUTE FUNCTION _set_updated_at();


-- ── BƯỚC 5: KIỂM TRA ────────────────────────────────────────

SELECT
    table_name,
    (SELECT count(*) FROM information_schema.columns
     WHERE table_name = t.table_name
     AND table_schema = 'public') AS column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name IN ('sessions', 'fb_credentials', 'spy_targets', 'spy_cache')
ORDER BY table_name;
