-- Migration 012: Manual-token FB connections (thay thế OAuth flow)
-- User tự tạo FB App + lấy Access Token qua Graph API Explorer, paste vào bot.
-- Thêm storage cho Pages (đăng bài) bên cạnh Ad Account (báo cáo/tối ưu ads) đã có.

ALTER TABLE user_fb_connections
ADD COLUMN IF NOT EXISTS pages JSONB DEFAULT '[]'::jsonb,        -- [{"id","name","encrypted_token"}]
ADD COLUMN IF NOT EXISTS active_page_id TEXT,
ADD COLUMN IF NOT EXISTS active_page_name TEXT;
