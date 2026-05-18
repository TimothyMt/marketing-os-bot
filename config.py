import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Cloud DB — Supabase PostgreSQL connection string
# Format: postgresql://user:password@host:port/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Webhook — Railway public domain (e.g. https://xxx.up.railway.app)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

# Railway sets PORT automatically; fallback 8000 for local testing
PORT = int(os.getenv("PORT", "8000"))

CLAUDE_MODEL = "claude-sonnet-4-6"

# Timeout per agent call (seconds)
AGENT_TIMEOUT = 120

# Max conversation history kept in session
MAX_HISTORY_TURNS = 20

# Industries supported
INDUSTRIES = [
    "fnb",
    "tech_saas",
    "ecommerce",
    "education",
    "health_beauty",
    "retail",
    "b2b_service",
    "real_estate",
]

# Business stages
STAGES = ["idea", "mvp", "growth", "scale"]
