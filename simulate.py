"""
CLI Simulator — chạy Marketing OS pipeline ngay trong terminal.
Không cần Telegram, không cần deploy.

Chạy: python simulate.py
"""
import asyncio
import sys
import os

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(__file__))

from storage.models import Session, BusinessProfile, PipelineStage
from agents.pipeline import run_intake, run_targeted_pipeline

# ── ANSI colors ──────────────────────────────────────────────────
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

STAGE_HEADERS = {
    "market_research":    "📊 NGHIÊN CỨU THỊ TRƯỜNG (TAM/SAM/SOM)",
    "competitor":         "🕵️  PHÂN TÍCH ĐỐI THỦ CẠNH TRANH",
    "customer_insight":   "👥 CUSTOMER INSIGHT & ICP",
    "psychology_pricing": "💡 MARKETING PSYCHOLOGY & PRICING",
    "social_listening":   "📡 SOCIAL LISTENING SYSTEM",
    "synthesis":          "🚀 MARKETING STRATEGY TỔNG HỢP",
}

TASK_MENU = """
Chọn task (nhập số):
  1. Phân tích toàn diện (6 bước)
  2. Nghiên cứu thị trường
  3. Phân tích đối thủ
  4. Customer Insight
  5. Pricing Strategy
  6. Social Listening
  7. Marketing Strategy
"""

TASK_MAP = {
    "1": "full",
    "2": "market",
    "3": "competitor",
    "4": "customer",
    "5": "pricing",
    "6": "social",
    "7": "strategy",
}

TASK_LABELS = {
    "full":       "Phân tích toàn diện",
    "market":     "Nghiên cứu thị trường",
    "competitor": "Phân tích đối thủ",
    "customer":   "Customer Insight",
    "pricing":    "Pricing Strategy",
    "social":     "Social Listening",
    "strategy":   "Marketing Strategy",
}


def print_bot(text: str):
    import re
    text = re.sub(r'\*\*(.*?)\*\*', f'{BOLD}\\1{RESET}', text)
    text = re.sub(r'\*(.*?)\*', f'{CYAN}\\1{RESET}', text)
    text = re.sub(r'_(.*?)_', f'{DIM}\\1{RESET}', text)
    print(f"\n{GREEN}[Max]{RESET} {text}\n")


def print_stage(header: str, content: str):
    divider = "─" * 50
    print(f"\n{YELLOW}{BOLD}{header}{RESET}")
    print(f"{DIM}{divider}{RESET}")
    print(content)
    print(f"{DIM}{divider}{RESET}\n")


def print_user(text: str):
    print(f"{CYAN}[Bạn]{RESET} {text}")


async def run_simulator():
    session = Session(user_id=9999)

    print(f"\n{BOLD}{'='*55}")
    print("  Marketing OS — CLI Simulator")
    print(f"  Gõ 'quit' để thoát | 'reset' để bắt đầu lại")
    print(f"{'='*55}{RESET}\n")

    print_bot("👋 Xin chào! Tôi là Max — AI CMO của bạn.")

    while True:
        # ── TASK SELECTION ────────────────────────────────────────
        if session.stage in (PipelineStage.IDLE, PipelineStage.TASK_SELECT):
            print(TASK_MENU)
            try:
                choice = input(f"{CYAN}[Chọn]{RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nTạm biệt! 👋")
                break

            if choice.lower() == "quit":
                print("\nTạm biệt! 👋")
                break

            task_type = TASK_MAP.get(choice)
            if not task_type:
                print("Nhập số từ 1-7 nhé!")
                continue

            session.selected_task = task_type
            session.stage = PipelineStage.INTAKE

            from agents.prompts import TASK_OPENING_QUESTIONS
            opening = TASK_OPENING_QUESTIONS.get(task_type, "")
            label = TASK_LABELS.get(task_type, "Phân tích")
            print_bot(f"✅ {label}\n\n{opening}")

        # ── INTAKE ────────────────────────────────────────────────
        elif session.stage == PipelineStage.INTAKE:
            try:
                user_input = input(f"{CYAN}[Bạn]{RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nTạm biệt! 👋")
                break

            if not user_input:
                continue
            if user_input.lower() == "quit":
                print("\nTạm biệt! 👋")
                break
            if user_input.lower() == "reset":
                session = Session(user_id=9999)
                print_bot("Đã reset. Chọn task mới nhé!")
                continue

            print(f"\n{DIM}⏳ Đang phân tích...{RESET}")
            response, is_complete = await run_intake(session, user_input)

            import re
            clean = re.sub(r'```json.*?```', '', response, flags=re.DOTALL).strip()

            if is_complete:
                from frameworks.kpi_library import KPI_LIBRARY
                fw = KPI_LIBRARY.get(session.profile.industry or "")
                industry_name = fw.display_name if fw else (session.profile.industry or "Chưa xác định")

                task = session.selected_task or "full"
                label = TASK_LABELS.get(task, "Phân tích")

                print_bot(
                    f"✅ Tôi đã nắm được thông tin:\n\n"
                    f"🏢 Business: {session.profile.business_name or 'Business của bạn'}\n"
                    f"📦 Sản phẩm/DV: {session.profile.product_service}\n"
                    f"👥 Khách hàng: {session.profile.target_customer}\n"
                    f"📊 Ngành: {industry_name}\n"
                    f"🚀 Stage: {session.profile.stage}\n"
                    f"💰 Doanh thu: {session.profile.monthly_revenue or 'Chưa rõ'}\n\n"
                    f"Task: {label}\n\n"
                    f"Bắt đầu phân tích không? (gõ 'yes' để chạy)"
                )
                session.stage = PipelineStage.CONFIRMED
            else:
                print_bot(clean)

        # ── CONFIRMED ─────────────────────────────────────────────
        elif session.stage == PipelineStage.CONFIRMED:
            try:
                user_input = input(f"{CYAN}[Bạn]{RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nTạm biệt! 👋")
                break

            if user_input.lower() == "quit":
                print("\nTạm biệt! 👋")
                break
            if user_input.lower() == "reset":
                session = Session(user_id=9999)
                print_bot("Đã reset. Chọn task mới nhé!")
                continue

            if user_input.lower() in ("yes", "y", "ok", "có", "co", "bắt đầu", "run"):
                session.stage = PipelineStage.MARKET_RESEARCH
                task = session.selected_task or "full"
                label = TASK_LABELS.get(task, "Phân tích")
                print_bot(f"🚀 Bắt đầu {label}! Đang chạy...\n")

                async def progress_cb(msg: str):
                    import re
                    clean_msg = re.sub(r'\*', '', msg)
                    print(f"\n{DIM}⏳ {clean_msg}{RESET}")

                async for stage_key, result in run_targeted_pipeline(session, progress_callback=progress_cb):
                    header = STAGE_HEADERS.get(stage_key, stage_key.upper())
                    print_stage(header, result)
                    await asyncio.sleep(0.2)

                print_bot(
                    f"✅ Hoàn thành {label}!\n\n"
                    "Bạn có câu hỏi gì thêm không? Cứ nhắn thẳng vào đây.\n"
                    "(Gõ 'reset' để phân tích mới)"
                )
                session.stage = PipelineStage.COMPLETE
            else:
                print_bot("Gõ 'yes' để bắt đầu phân tích, hoặc 'reset' để nhập lại.")

        # ── COMPLETE — follow-up Q&A ──────────────────────────────
        elif session.stage == PipelineStage.COMPLETE:
            try:
                user_input = input(f"{CYAN}[Bạn]{RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nTạm biệt! 👋")
                break

            if not user_input:
                continue
            if user_input.lower() == "quit":
                print("\nTạm biệt! 👋")
                break
            if user_input.lower() == "reset":
                session = Session(user_id=9999)
                print_bot("Đã reset. Chọn task mới nhé!")
                continue

            print(f"\n{DIM}⏳ Đang trả lời...{RESET}")
            import anthropic
            from config import CLAUDE_MODEL, ANTHROPIC_API_KEY
            from agents.prompts import STRATEGY_SYNTHESIZER_SYSTEM

            client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
            context_str = session.build_pipeline_context()

            resp = await client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1500,
                system=STRATEGY_SYNTHESIZER_SYSTEM + "\n\nTrả lời câu hỏi follow-up dựa trên kết quả đã phân tích.",
                messages=[{"role": "user", "content": f"{context_str}\n\n---\n\nCâu hỏi: {user_input}"}],
            )
            print_bot(resp.content[0].text)


if __name__ == "__main__":
    asyncio.run(run_simulator())
