import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY", "")  # cho image gen (gpt-image-1)

# Admin Telegram user IDs — phân cách bằng dấu phẩy: "123456789,987654321"
ADMIN_IDS: set[int] = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
}

# Facebook APIs
FB_ACCESS_TOKEN    = os.getenv("FB_ACCESS_TOKEN", "")   # User/System token (ads_read, read_insights)
FB_APP_ID          = os.getenv("FB_APP_ID", "")         # App ID
FB_APP_SECRET      = os.getenv("FB_APP_SECRET", "")     # App Secret
FB_AD_ACCOUNT_ID   = os.getenv("FB_AD_ACCOUNT_ID", "")  # act_XXXXXXXXXX (để pull data ads của sếp)

# Supabase — dùng HTTPS (port 443), không bao giờ bị block
SUPABASE_URL       = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY       = os.getenv("SUPABASE_SERVICE_KEY", "")  # service_role key

# Webhook — Railway public domain (no trailing slash)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

# Railway sets PORT automatically; fallback 8000 for local testing
PORT = int(os.getenv("PORT", "8000"))

# 2-tier model: Haiku cho intake (classification + JSON extract, rẻ), Sonnet cho deep analysis + critic
CLAUDE_SONNET_MODEL = "claude-sonnet-4-6"
CLAUDE_HAIKU_MODEL  = "claude-haiku-4-5"
CLAUDE_MODEL        = CLAUDE_SONNET_MODEL  # backward-compat alias

# OpenAI models (S8.8 — Phase 1b multi-provider router)
GPT5_MODEL          = "gpt-5"           # Flagship — competitor + USP + psychology fallback
GPT5_MINI_MODEL     = "gpt-5-mini"      # Sweet spot — retention/winback/intake primary
GPT5_NANO_MODEL     = "gpt-5-nano"      # Cheap — bulk classify
GPT_4_1_MINI_MODEL  = "gpt-4.1-mini"    # Long context fallback (1M ctx)

# Pipeline timeouts (Sprint hotfix: synthesis với 8-stage pipeline cần buffer lớn hơn)
# Synthesis context ~70K input + 10K output có thể tốn 180-300s + retry → 540s+ wall time
AGENT_TIMEOUT  = 900  # 15 phút — buffer cho stage nặng (synthesis sau Sprint 2-3 mở rộng pipeline)
MAX_HISTORY_TURNS = 20

# Sprint 8 — Multi-Agent Orchestrator feature flag.
# True (default): task=full chạy qua Multi-Agent Orchestrator (parallel tier execution)
# False: fallback xuống run_targeted_pipeline cũ (sequential)
# Set qua env var để rollback nhanh: USE_MULTI_AGENT=false
USE_MULTI_AGENT_PIPELINE = os.getenv("USE_MULTI_AGENT", "true").lower() in ("true", "1", "yes")

# DB Refactor v2 — Normalized schema feature flag (Migration 006).
# False (default): dùng schema cũ (sessions monolithic)
# True: đọc/ghi qua v2 tables (users, user_business_profile, user_sessions_slim,
#       skill_runs, campaigns, posts)
# Roll-out: chỉ flip True sau khi:
#   1. Chạy migration 006_normalize_schema.sql trong Supabase
#   2. Run scripts/backfill_v2.py để migrate data cũ
#   3. Verify data integrity bằng SQL queries
USE_DB_V2 = os.getenv("USE_DB_V2", "false").lower() in ("true", "1", "yes")

INDUSTRIES = [
    "fnb", "tech_saas", "ecommerce", "education",
    "health_beauty", "retail", "b2b_service", "real_estate",
]
STAGES = ["idea", "mvp", "growth", "scale"]
