import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
TAVILY_API_KEY     = os.getenv("TAVILY_API_KEY", "")

# Supabase — dùng HTTPS (port 443), không bao giờ bị block
SUPABASE_URL       = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY       = os.getenv("SUPABASE_SERVICE_KEY", "")  # service_role key

# Webhook — Railway public domain (no trailing slash)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

# Railway sets PORT automatically; fallback 8000 for local testing
PORT = int(os.getenv("PORT", "8000"))

CLAUDE_MODEL   = "claude-sonnet-4-6"
AGENT_TIMEOUT  = 120          # Max time for a single agent (intake/pipeline stage)
TAVILY_TIMEOUT = 30           # Max time for one Tavily web search call (raised
                              # from 15s — Tavily can spike on cold starts, and
                              # the cost of timing out is worse than waiting a bit)
PIPELINE_STAGE_TIMEOUT = 240  # Max time for full pipeline stage (incl. tool loops);
                              # bumped to accommodate longer Tavily budget
MAX_HISTORY_TURNS = 20
MAX_INPUT_LENGTH = 2000       # Max chars per user message

INDUSTRIES = [
    "fnb", "tech_saas", "ecommerce", "education",
    "health_beauty", "retail", "b2b_service", "real_estate",
]
STAGES = ["idea", "mvp", "growth", "scale"]
