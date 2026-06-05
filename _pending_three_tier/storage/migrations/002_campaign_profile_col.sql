-- Migration 002: Thêm cột campaign_profile vào sessions
ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS campaign_profile JSONB NOT NULL DEFAULT '{}';

-- Cập nhật 000_fresh_setup.sql đã thêm cột này rồi nếu chạy từ đầu,
-- migration này chỉ cần cho instance đang chạy sẵn.
