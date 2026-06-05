-- ============================================================
-- Migration 001: Thêm bảng campaigns + cột selected_campaign_id
-- Chạy sau 000_fresh_setup.sql
-- ============================================================

-- ── Bảng campaigns ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS campaigns (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          BIGINT      NOT NULL,
    name             TEXT        NOT NULL DEFAULT 'Campaign mới',
    brief            TEXT,
    content_calendar TEXT,
    ad_copy          TEXT,
    video_script     TEXT,
    ugc_brief        TEXT,
    email_zalo       TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_campaigns_user
    ON campaigns (user_id, created_at DESC);

CREATE TRIGGER trg_campaigns_updated_at
    BEFORE UPDATE ON campaigns
    FOR EACH ROW EXECUTE FUNCTION _set_updated_at();

-- ── Thêm cột vào sessions ────────────────────────────────────
ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS selected_campaign_id TEXT NOT NULL DEFAULT '';

-- ── Kiểm tra ────────────────────────────────────────────────
SELECT table_name,
       (SELECT count(*) FROM information_schema.columns
        WHERE table_name = t.table_name AND table_schema = 'public') AS col_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name IN ('sessions', 'campaigns')
ORDER BY table_name;
