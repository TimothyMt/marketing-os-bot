import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "sessions.db")

CLAUDE_MODEL = "claude-sonnet-4-6"

# Timeout per agent call (seconds)
AGENT_TIMEOUT = 120

# Max conversation history kept in session
MAX_HISTORY_TURNS = 10

# Industries supported
INDUSTRIES = [
    "fnb",           # F&B: nhà hàng, cà phê, food delivery
    "tech_saas",     # Tech SaaS / App
    "ecommerce",     # Thương mại điện tử
    "education",     # Giáo dục / Coaching / Khóa học
    "health_beauty", # Sức khỏe / Làm đẹp / Spa / Clinic
    "retail",        # Bán lẻ offline / Chuỗi cửa hàng
    "b2b_service",   # Dịch vụ B2B / Agency / Tư vấn
    "real_estate",   # Bất động sản
]

# Business stages
STAGES = ["idea", "mvp", "growth", "scale"]
