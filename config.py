import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY", "")  # cho image gen (gpt-image-1)

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

AGENT_TIMEOUT  = 500  # ~8 phút — buffer rộng cho cả trường hợp Claude API chậm
MAX_HISTORY_TURNS = 20

INDUSTRIES = [
    "fnb", "tech_saas", "ecommerce", "education",
    "health_beauty", "retail", "b2b_service", "real_estate",
]
STAGES = ["idea", "mvp", "growth", "scale"]
