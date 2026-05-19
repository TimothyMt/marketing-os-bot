"""
Skill modularity: AgentSkill base class + concrete subclasses for each pipeline agent.

LƯU Ý KHI THÊM/SỬA SKILL MỚI:
1. GIỮ NGUYÊN system_prompt từ prompts.py — không cleanup wording
2. GIỮ NGUYÊN context_builder per-agent (vd: synthesis cần SAVE+SMART injection riêng)
3. GIỮ NGUYÊN max_tokens custom — không 1-size-fits-all
4. Test before/after: chạy cùng input qua skill class và verify output ~ identical
"""
from abc import ABC, abstractmethod
from storage.models import Session
from agents.prompts import (
    MARKET_RESEARCH_SYSTEM,
    COMPETITOR_SYSTEM,
    CUSTOMER_INSIGHT_SYSTEM,
    MARKETING_PSYCHOLOGY_SYSTEM,
    PRICING_STRATEGY_SYSTEM,
    SOCIAL_LISTENING_SYSTEM,
    STRATEGY_SYNTHESIZER_SYSTEM,
)
from frameworks.kpi_library import get_framework_as_text
from frameworks.save_framework import generate_save_analysis
from frameworks.smart_framework import format_smart_prompt


class AgentSkill(ABC):
    """Base class for a pipeline agent skill.
    Each concrete skill defines its prompt, context strategy, and user message template."""

    name: str = ""
    system_prompt: str = ""
    max_tokens: int = 4000
    enable_critic: bool = True

    @abstractmethod
    def build_context(self, session: Session) -> str:
        """Build context string injected before user message."""
        ...

    @abstractmethod
    def build_user_msg(self, session: Session) -> str:
        """Build the user message — agent-specific framing of the task."""
        ...


class MarketResearchSkill(AgentSkill):
    name = "market_research"
    system_prompt = MARKET_RESEARCH_SYSTEM
    max_tokens = 4000

    def build_context(self, session: Session) -> str:
        return session.profile.to_context_string()

    def build_user_msg(self, session: Session) -> str:
        kpi_text = get_framework_as_text(session.profile.industry or "")
        return f"""Hãy phân tích TAM/SAM/SOM cho business này.

{kpi_text}

Đặc biệt chú ý methodology ước tính TAM phù hợp với ngành {session.profile.industry}.
Location: {session.profile.location or 'Việt Nam'}
Target customer: {session.profile.target_customer}"""


class CompetitorSkill(AgentSkill):
    name = "competitor"
    system_prompt = COMPETITOR_SYSTEM
    max_tokens = 4000

    def build_context(self, session: Session) -> str:
        return session.build_pipeline_context()

    def build_user_msg(self, session: Session) -> str:
        competitors_known = session.profile.competitors or "chưa xác định"
        return f"""Phân tích landscape cạnh tranh cho business này.

Đối thủ founder đề cập: {competitors_known}

Hãy:
1. Phân tích các đối thủ đã biết (nếu có)
2. Identify thêm các đối thủ điển hình trong ngành {session.profile.industry} tại {session.profile.location or 'VN'}
3. Tìm market gaps rõ ràng nhất
4. Đề xuất positioning opportunity"""


class CustomerInsightSkill(AgentSkill):
    name = "customer_insight"
    system_prompt = CUSTOMER_INSIGHT_SYSTEM
    max_tokens = 4000

    def build_context(self, session: Session) -> str:
        return session.build_pipeline_context()

    def build_user_msg(self, session: Session) -> str:
        return f"""Xây dựng Customer Insight đầy đủ cho business này.

Product/Service: {session.profile.product_service}
Target customer: {session.profile.target_customer}
Location: {session.profile.location or 'Việt Nam'}

Hãy đào sâu vào psychographics, JTBD, và Vietnamese cultural context của ngành {session.profile.industry}."""


class PsychologyPricingSkill(AgentSkill):
    """Combines Marketing Psychology + Pricing Strategy in 1 call to save latency."""
    name = "psychology_pricing"
    max_tokens = 5000

    @property
    def system_prompt(self) -> str:
        return f"""{MARKETING_PSYCHOLOGY_SYSTEM}

---

{PRICING_STRATEGY_SYSTEM}

Hãy output CẢ HAI phần: Psychology Application VÀ Pricing Strategy trong một response duy nhất, chia section rõ ràng."""

    def build_context(self, session: Session) -> str:
        return session.build_pipeline_context()

    def build_user_msg(self, session: Session) -> str:
        return f"""Áp dụng Marketing Psychology VÀ đề xuất Pricing Strategy cho business này.

Budget marketing: {session.profile.monthly_marketing_budget or 'chưa xác định'}
Mục tiêu: {session.profile.primary_goal}
Stage: {session.profile.stage}

Phần 1: Map psychological principles vào từng touchpoint của funnel
Phần 2: Đề xuất pricing model và tactics cụ thể (với số liệu)"""


class SocialListeningSkill(AgentSkill):
    """Tạm tắt — chờ web search VN coverage tốt hơn. Giữ skill để dễ enable lại."""
    name = "social_listening"
    system_prompt = SOCIAL_LISTENING_SYSTEM
    max_tokens = 4000

    def build_context(self, session: Session) -> str:
        return session.build_pipeline_context()

    def build_user_msg(self, session: Session) -> str:
        return f"""Thiết kế Social Listening System cho business này.

Business: {session.profile.business_name or session.profile.product_service}
Ngành: {session.profile.industry}
Team size: {session.profile.team_size or 'nhỏ'}
Đối thủ biết đến: {session.profile.competitors or 'chưa xác định'}

Tạo system thực tế, phù hợp với team nhỏ, tập trung vào platform VN."""


class StrategySynthesisSkill(AgentSkill):
    name = "synthesis"
    system_prompt = STRATEGY_SYNTHESIZER_SYSTEM
    max_tokens = 5000

    def build_context(self, session: Session) -> str:
        return session.build_pipeline_context()

    def build_user_msg(self, session: Session) -> str:
        save_prompt = generate_save_analysis(
            industry=session.profile.industry or "",
            business_description=session.profile.product_service or "",
            target_customer=session.profile.target_customer or "",
            product_service=session.profile.product_service or "",
        )
        smart_prompt = format_smart_prompt(
            industry=session.profile.industry or "",
            stage=session.profile.stage or "growth",
            goals=[session.profile.primary_goal or "tăng doanh thu"],
        )
        return f"""Tổng hợp tất cả insights đã phân tích thành Marketing Strategy hoàn chỉnh.

{save_prompt}

{smart_prompt}

Yêu cầu:
- Apply SAVE Framework cụ thể cho {session.profile.business_name or 'business này'}
- Tạo 2-3 SMART goals với số liệu thực tế
- 90-day roadmap cụ thể, actionable
- KPI dashboard với targets 30/60/90 ngày
- Quick wins có thể làm ngay trong 2 tuần đầu
- Budget allocation đề xuất"""


# Registry — used by pipeline.py to look up skill by stage_key
SKILL_REGISTRY: dict[str, type[AgentSkill]] = {
    "market_research":    MarketResearchSkill,
    "competitor":         CompetitorSkill,
    "customer_insight":   CustomerInsightSkill,
    "psychology_pricing": PsychologyPricingSkill,
    "social_listening":   SocialListeningSkill,
    "synthesis":          StrategySynthesisSkill,
}
