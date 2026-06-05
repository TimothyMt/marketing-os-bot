from abc import abstractmethod
from agents.skills import AgentSkill
from agents.tier2_prompts import CAMPAIGN_BRIEF_SYSTEM, CONTENT_CALENDAR_SYSTEM
from storage.models import Session


class CampaignBriefSkill(AgentSkill):
    name = "campaign_brief"
    system_prompt = CAMPAIGN_BRIEF_SYSTEM
    max_tokens = 5000
    enable_critic = False

    def build_context(self, session: Session) -> str:
        parts = [session.profile.to_context_string()]

        if "synthesis" in session.results:
            parts.append(f"## Kết quả Phân tích Tier 1 (Marketing Strategy)\n{session.results['synthesis']}")

        for key in ("market_research", "competitor", "customer_insight", "psychology_pricing"):
            if key in session.results:
                labels = {
                    "market_research": "Nghiên cứu Thị trường",
                    "competitor": "Phân tích Đối thủ",
                    "customer_insight": "Customer Insight",
                    "psychology_pricing": "Marketing Psychology & Pricing",
                }
                parts.append(f"## {labels[key]}\n{session.results[key]}")

        cp = session.campaign_profile
        campaign_lines = ["## Campaign Profile"]
        if cp.campaign_type:
            campaign_lines.append(f"- **Loại chiến dịch**: {cp.campaign_type}")
        if cp.campaign_goal:
            campaign_lines.append(f"- **Mục tiêu**: {cp.campaign_goal}")
        if cp.campaign_budget:
            campaign_lines.append(f"- **Ngân sách**: {cp.campaign_budget}")
        if cp.campaign_duration:
            campaign_lines.append(f"- **Thời gian**: {cp.campaign_duration}")
        if cp.campaign_channels:
            campaign_lines.append(f"- **Kênh**: {cp.campaign_channels}")
        if cp.campaign_kpi:
            campaign_lines.append(f"- **KPI mục tiêu**: {cp.campaign_kpi}")
        if cp.content_tone:
            campaign_lines.append(f"- **Tone nội dung**: {cp.content_tone}")
        if len(campaign_lines) > 1:
            parts.append("\n".join(campaign_lines))

        return "\n\n---\n\n".join(parts)

    def build_user_msg(self, session: Session) -> str:
        cp = session.campaign_profile
        campaign_type = cp.campaign_type or "performance"
        campaign_goal = cp.campaign_goal or "tăng doanh thu"
        duration = cp.campaign_duration or "30_days"
        channels = cp.campaign_channels or "facebook,tiktok"

        return f"""Tạo Campaign Brief hoàn chỉnh 9 phần cho chiến dịch sau:

- Loại chiến dịch: {campaign_type}
- Mục tiêu: {campaign_goal}
- Thời gian: {duration}
- Kênh triển khai: {channels}

Dựa trên toàn bộ context business và kết quả phân tích Tier 1 đã cung cấp.
Brief phải cụ thể cho business này — không dùng ví dụ chung chung.
Output đầy đủ 9 phần với bảng markdown."""


class ContentCalendarSkill(AgentSkill):
    name = "content_calendar"
    system_prompt = CONTENT_CALENDAR_SYSTEM
    max_tokens = 5000
    enable_critic = False

    def build_context(self, session: Session) -> str:
        parts = [session.profile.to_context_string()]

        if "campaign_brief" in session.results:
            parts.append(f"## Campaign Brief (Tier 2)\n{session.results['campaign_brief']}")

        if "synthesis" in session.results:
            parts.append(f"## Marketing Strategy (Tier 1)\n{session.results['synthesis']}")

        cp = session.campaign_profile
        calendar_lines = ["## Thông số lịch nội dung"]
        if cp.campaign_channels:
            calendar_lines.append(f"- **Kênh**: {cp.campaign_channels}")
        if cp.campaign_duration:
            calendar_lines.append(f"- **Thời gian**: {cp.campaign_duration}")
        if cp.content_tone:
            calendar_lines.append(f"- **Tone**: {cp.content_tone}")
        if cp.selected_creator_type:
            calendar_lines.append(f"- **Creator type ưu tiên**: {cp.selected_creator_type}")
        if len(calendar_lines) > 1:
            parts.append("\n".join(calendar_lines))

        return "\n\n---\n\n".join(parts)

    def build_user_msg(self, session: Session) -> str:
        cp = session.campaign_profile
        channels = cp.campaign_channels or "facebook,tiktok"
        duration = cp.campaign_duration or "30_days"
        business = session.profile.business_name or session.profile.product_service or "business này"

        return f"""Tạo lịch nội dung 30 ngày cho {business}.

Kênh: {channels}
Thời gian chiến dịch: {duration}

Yêu cầu:
- Bảng đầy đủ 11 cột theo format đã định
- Phân bổ pillar: Education 35% / Trust 30% / Engage 20% / Convert 15%
- Source mix: UGC 40% / EGC 25% / FGC 15% / Brand 20%
- Hook cụ thể, không chung chung
- Bảng tóm tắt phân bổ sau lịch
- Batch production plan theo tuần"""


TIER2_SKILL_REGISTRY: dict[str, type[AgentSkill]] = {
    "campaign_brief":    CampaignBriefSkill,
    "content_calendar":  ContentCalendarSkill,
}
