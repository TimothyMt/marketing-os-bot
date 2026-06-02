-- Migration 009: Dream Engine — autonomous marketing idea generation.
-- Run in Supabase SQL Editor sau migration 008.
--
-- Bot "mơ" ban đêm: tua lại campaign history + brand voice + đối thủ đang track,
-- sinh ý tưởng marketing mới, lưu vào đây rồi gửi morning digest cho user.

CREATE TABLE IF NOT EXISTS user_dreams (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       BIGINT NOT NULL,

    -- Nội dung 1 ý tưởng ("dream")
    title         TEXT NOT NULL,         -- Tên ngắn gọn
    angle         TEXT,                  -- Góc tiếp cận / ý tưởng cốt lõi
    why_now       TEXT,                  -- Vì sao lúc này (timing / trigger từ ký ức)
    first_step    TEXT,                  -- Bước đầu tiên cụ thể
    inspired_by   TEXT,                  -- 'campaign_history' | 'competitor' | 'brand_voice' | 'mix'
    impact        TEXT,                  -- 'high' | 'medium'

    -- Metadata
    signature     TEXT,                  -- Title chuẩn hoá (lowercase, no accent) — dùng dedupe
    status        TEXT DEFAULT 'new',    -- 'new' | 'developed' | 'dismissed'
    batch_id      UUID,                  -- Group các dream cùng 1 lần mơ

    surfaced_at   TIMESTAMPTZ,           -- Khi đã gửi cho user qua Telegram
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Lookup nhanh dream theo user + recency
CREATE INDEX IF NOT EXISTS idx_dreams_user_created
    ON user_dreams(user_id, created_at DESC);

-- Lookup theo status (vd: list dream 'new' chưa xử lý)
CREATE INDEX IF NOT EXISTS idx_dreams_user_status
    ON user_dreams(user_id, status);
