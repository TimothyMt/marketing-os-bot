-- Migration 011: Multi-account ads subscriptions + per-account notify time
-- Tách phần "digest settings" ra khỏi user_fb_connections để 1 user có thể nhận
-- daily digest cho NHIỀU ad account cùng lúc (mỗi cái có notify_time/tracked_metrics
-- /ngưỡng alert riêng), thay vì chỉ 1 account active gần nhất như trước.
--
-- user_fb_connections giữ: token + ad_account_id (active cho live tasks) + available_accounts.
-- user_ads_subscriptions (mới): 1 row / (user × ad_account) cho digest settings.

-- ── 1. Bảng subscription per-account ────────────────────────────
CREATE TABLE IF NOT EXISTS user_ads_subscriptions (
    user_id              BIGINT      NOT NULL,
    ad_account_id        TEXT        NOT NULL,        -- "act_XXXXXXXXXX"
    account_name         TEXT,                        -- friendly name (snapshot tại thời điểm subscribe)

    notification_enabled BOOLEAN     DEFAULT TRUE,
    notify_time          TEXT        DEFAULT '08:00', -- "HH:MM" — preset (06/07/08/09/10/12)

    tracked_metrics      TEXT[]      DEFAULT ARRAY['spend','roas','cpl','frequency'],

    -- Ngưỡng alert — NULL = dùng benchmark ngành (Frequency 5.0, ROAS drop 20%, CPM spike 30%)
    alert_frequency_max  FLOAT,
    alert_roas_drop_pct  FLOAT,
    alert_cpm_spike_pct  FLOAT,

    last_pull_at         TIMESTAMPTZ,                 -- lần cuối scheduler pull thành công cho sub này
    created_at           TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (user_id, ad_account_id),
    FOREIGN KEY (user_id) REFERENCES user_fb_connections(user_id) ON DELETE CASCADE
);

-- Scheduler query "subs cần fire vào 08:00" — index theo (enabled, notify_time)
CREATE INDEX IF NOT EXISTS idx_subs_notify
    ON user_ads_subscriptions (notification_enabled, notify_time);

-- ── 2. Backfill từ user_fb_connections hiện có ──────────────────
-- Mỗi connection cũ → 1 subscription cho ad_account_id đang active của user đó,
-- copy nguyên trạng settings (tracked_metrics/alert thresholds/notify_time).
INSERT INTO user_ads_subscriptions (
    user_id, ad_account_id, account_name,
    notification_enabled, notify_time,
    tracked_metrics,
    alert_frequency_max, alert_roas_drop_pct, alert_cpm_spike_pct,
    last_pull_at
)
SELECT
    user_id,
    ad_account_id,
    account_name,
    COALESCE(notification_enabled, TRUE),
    COALESCE(notify_time, '08:00'),
    COALESCE(tracked_metrics, ARRAY['spend','roas','cpl','frequency']),
    alert_frequency_max,
    alert_roas_drop_pct,
    alert_cpm_spike_pct,
    last_pull_at
FROM user_fb_connections
ON CONFLICT (user_id, ad_account_id) DO NOTHING;

-- ── 3. Snapshots: thêm ad_account_id + đổi PK ──────────────────
-- Trước: PK (user_id, snapshot_date, campaign_id) — không phân biệt account.
-- Sau:   PK (user_id, ad_account_id, snapshot_date, campaign_id) — 2 account
-- của cùng 1 user không đè lên nhau.
ALTER TABLE ads_snapshots
    ADD COLUMN IF NOT EXISTS ad_account_id TEXT;

-- Backfill ad_account_id cho snapshot lịch sử (lấy từ active account hiện tại của user)
UPDATE ads_snapshots s
SET    ad_account_id = c.ad_account_id
FROM   user_fb_connections c
WHERE  s.user_id = c.user_id
  AND  s.ad_account_id IS NULL;

ALTER TABLE ads_snapshots
    ALTER COLUMN ad_account_id SET NOT NULL;

ALTER TABLE ads_snapshots DROP CONSTRAINT IF EXISTS ads_snapshots_pkey;
ALTER TABLE ads_snapshots
    ADD CONSTRAINT ads_snapshots_pkey
    PRIMARY KEY (user_id, ad_account_id, snapshot_date, campaign_id);

DROP INDEX IF EXISTS idx_ads_snapshots_user_date;
CREATE INDEX IF NOT EXISTS idx_ads_snapshots_user_acct_date
    ON ads_snapshots (user_id, ad_account_id, snapshot_date DESC);

-- ── 4. Alert cooldowns: scope theo account ─────────────────────
ALTER TABLE ads_alert_cooldowns
    ADD COLUMN IF NOT EXISTS ad_account_id TEXT;

UPDATE ads_alert_cooldowns a
SET    ad_account_id = c.ad_account_id
FROM   user_fb_connections c
WHERE  a.user_id = c.user_id
  AND  a.ad_account_id IS NULL;

ALTER TABLE ads_alert_cooldowns
    ALTER COLUMN ad_account_id SET NOT NULL;

ALTER TABLE ads_alert_cooldowns DROP CONSTRAINT IF EXISTS ads_alert_cooldowns_pkey;
ALTER TABLE ads_alert_cooldowns
    ADD CONSTRAINT ads_alert_cooldowns_pkey
    PRIMARY KEY (user_id, ad_account_id, campaign_id, alert_type);

-- ── 5. Drop cột digest cũ trên user_fb_connections ─────────────
-- (Settings đã chuyển hết sang user_ads_subscriptions — không cần giữ.)
ALTER TABLE user_fb_connections DROP COLUMN IF EXISTS notification_enabled;
ALTER TABLE user_fb_connections DROP COLUMN IF EXISTS notify_time;
ALTER TABLE user_fb_connections DROP COLUMN IF EXISTS timezone;
ALTER TABLE user_fb_connections DROP COLUMN IF EXISTS tracked_metrics;
ALTER TABLE user_fb_connections DROP COLUMN IF EXISTS alert_frequency_max;
ALTER TABLE user_fb_connections DROP COLUMN IF EXISTS alert_roas_drop_pct;
ALTER TABLE user_fb_connections DROP COLUMN IF EXISTS alert_cpm_spike_pct;
ALTER TABLE user_fb_connections DROP COLUMN IF EXISTS last_pull_at;
