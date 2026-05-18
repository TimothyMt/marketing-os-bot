"""
Data models for session state management.
"""
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class TaskType(str, Enum):
    FULL        = "full"           # Phân tích toàn diện (6 bước)
    MARKET      = "market"         # Nghiên cứu thị trường
    COMPETITOR  = "competitor"     # Phân tích đối thủ
    CUSTOMER    = "customer"       # Customer Insight
    PRICING     = "pricing"        # Pricing Strategy
    SOCIAL      = "social"         # Social Listening
    STRATEGY    = "strategy"       # Marketing Strategy (SAVE + SMART)


class PipelineStage(str, Enum):
    IDLE = "idle"
    TASK_SELECT = "task_select"
    INTAKE = "intake"
    CONFIRMED = "confirmed"
    MARKET_RESEARCH = "market_research"
    COMPETITOR = "competitor"
    CUSTOMER_INSIGHT = "customer_insight"
    PSYCHOLOGY_PRICING = "psychology_pricing"
    SOCIAL_LISTENING = "social_listening"
    SYNTHESIS = "synthesis"
    COMPLETE = "complete"
    BRAND_SELECT = "brand_select"


@dataclass
class BusinessProfile:
    """Structured business profile extracted by Intake Agent."""
    industry: Optional[str] = None
    stage: Optional[str] = None
    business_name: Optional[str] = None
    product_service: Optional[str] = None
    target_customer: Optional[str] = None
    monthly_revenue: Optional[str] = None
    team_size: Optional[str] = None
    monthly_marketing_budget: Optional[str] = None
    primary_goal: Optional[str] = None
    current_channels: Optional[str] = None
    main_challenge: Optional[str] = None
    competitors: Optional[str] = None
    location: Optional[str] = None

    def is_ready_for_analysis(self) -> bool:
        """Check if we have enough info to start the pipeline."""
        required = [self.industry, self.product_service, self.target_customer]
        return all(f is not None for f in required)

    def to_context_string(self) -> str:
        """Format profile as context string for agent prompts."""
        lines = ["## Business Profile"]
        fields = {
            "Tên business": self.business_name,
            "Ngành": self.industry,
            "Stage": self.stage,
            "Sản phẩm/Dịch vụ": self.product_service,
            "Khách hàng mục tiêu": self.target_customer,
            "Doanh thu hiện tại": self.monthly_revenue,
            "Quy mô team": self.team_size,
            "Ngân sách marketing/tháng": self.monthly_marketing_budget,
            "Mục tiêu chính": self.primary_goal,
            "Kênh hiện tại": self.current_channels,
            "Thách thức lớn nhất": self.main_challenge,
            "Đối thủ": self.competitors,
            "Địa bàn": self.location,
        }
        for key, val in fields.items():
            if val:
                lines.append(f"- **{key}**: {val}")
        return "\n".join(lines)


@dataclass
class Session:
    """Full session state for a Telegram user."""
    user_id: int
    stage: PipelineStage = PipelineStage.IDLE
    selected_task: Optional[str] = None        # TaskType value
    profile: BusinessProfile = field(default_factory=BusinessProfile)

    # Conversation history for intake phase
    intake_history: list[dict] = field(default_factory=list)

    # Results from each pipeline stage
    results: dict[str, str] = field(default_factory=dict)

    # Raw user description (first message)
    raw_description: str = ""

    # Brand identification flow
    brand_candidates: list = field(default_factory=list)

    # Timestamps
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def add_to_history(self, role: str, content: str):
        self.intake_history.append({"role": role, "content": content})
        # Keep last MAX_HISTORY_TURNS turns
        if len(self.intake_history) > 20:
            self.intake_history = self.intake_history[-20:]

    def build_pipeline_context(self) -> str:
        """Build full context string for pipeline agents."""
        parts = [self.profile.to_context_string()]

        # Inject KPI framework
        from frameworks.kpi_library import get_framework_as_text
        if self.profile.industry:
            kpi_text = get_framework_as_text(self.profile.industry)
            parts.append(kpi_text)

        # Inject previous results as context
        stage_labels = {
            "market_research": "## Kết quả Nghiên cứu Thị trường",
            "competitor": "## Kết quả Phân tích Đối thủ",
            "customer_insight": "## Kết quả Customer Insight",
            "psychology_pricing": "## Kết quả Marketing Psychology & Pricing",
            "social_listening": "## Kết quả Social Listening Setup",
        }
        for key, label in stage_labels.items():
            if key in self.results:
                parts.append(f"{label}\n{self.results[key]}")

        return "\n\n---\n\n".join(parts)
