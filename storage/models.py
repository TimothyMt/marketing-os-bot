"""
Data models for session state management.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Union
from enum import Enum


class TaskType(str, Enum):
    # Strategic skills
    FULL        = "full"           # Phân tích toàn diện
    MARKET      = "market"
    COMPETITOR  = "competitor"
    CUSTOMER    = "customer"
    PRICING     = "pricing"
    SOCIAL      = "social"         # tạm tắt
    STRATEGY    = "strategy"       # Marketing Strategy (SAVE + SMART)

    # Operational skills (mới)
    CAMPAIGN_BRIEF       = "campaign_brief"
    CONTENT_CALENDAR     = "content_calendar"
    ADS_COPY             = "ads_copy"
    VIDEO_SCRIPTS        = "video_scripts"
    LANDING_PAGE         = "landing_page"
    SALES_INBOX_SCRIPT   = "sales_inbox_script"
    EMAIL_ZALO_SEQUENCE  = "email_zalo_sequence"
    PERFORMANCE_AUDIT    = "performance_audit"


class PipelineStage(str, Enum):
    IDLE = "idle"
    TASK_SELECT = "task_select"
    INTAKE = "intake"
    CONFIRMED = "confirmed"
    MARKET_RESEARCH = "market_research"
    COMPETITOR = "competitor"
    CUSTOMER_INSIGHT = "customer_insight"
    PSYCHOLOGY_PRICING = "psychology_pricing"
    USP_DEFINITION = "usp_definition"          # Sprint 2 — NEW
    RETENTION_STRATEGY = "retention_strategy"  # Sprint 3 — NEW (Full Pipeline integration)
    WINBACK_VISION = "winback_vision"          # Sprint 3 — NEW
    SOCIAL_LISTENING = "social_listening"
    SYNTHESIS = "synthesis"
    COMPLETE = "complete"


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

    # Sprint 2 — USP layer
    # usp: 1 câu USP user đã có (nếu confidence='clear') hoặc draft (nếu 'draft')
    # usp_confidence: "clear" | "draft" | "missing" | None (chưa hỏi)
    #   - clear   = user khẳng định đã có USP rõ ràng → skip USP definition skill
    #   - draft   = user có ý tưởng nhưng chưa rõ → USP skill REFINE
    #   - missing = user chưa có → USP skill FIND từ market+competitor+customer
    #   - None    = intake chưa hỏi (legacy users hoặc skip)
    usp: Optional[str] = None
    usp_confidence: Optional[str] = None

    def is_ready_for_analysis(self) -> bool:
        """Legacy global check — kept for backward compat.
        Use is_ready_for(task_name) for per-task field requirements (Phase 1.2)."""
        required = [self.industry, self.product_service, self.target_customer]
        return all(f for f in required)

    def is_ready_for(self, task_name: str) -> bool:
        """Per-task readiness check using task_registry intake_required_fields.
        Phase 1.2 — skill-aware intake skip."""
        try:
            from agents.task_registry import get_task
        except ImportError:
            return self.is_ready_for_analysis()
        task = get_task(task_name)
        if not task or not task.intake_required_fields:
            return self.is_ready_for_analysis()
        for f_key in task.intake_required_fields:
            value = getattr(self, f_key, None)
            if not value or (isinstance(value, str) and not value.strip()):
                return False
        return True

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
        # USP block — chỉ render nếu user đã trả lời intake
        if self.usp_confidence:
            usp_line = f"- **USP**: {self.usp}" if self.usp else "- **USP**: (chưa định nghĩa rõ ràng)"
            confidence_label = {
                "clear":   "đã có USP rõ ràng",
                "draft":   "có ý tưởng USP nhưng cần refine",
                "missing": "chưa có USP — cần Max tìm",
            }.get(self.usp_confidence, self.usp_confidence)
            lines.append(usp_line)
            lines.append(f"- **USP confidence**: {confidence_label}")
        return "\n".join(lines)


MAX_VERSIONS_PER_SKILL = 5  # FIFO cap to avoid Supabase bloat


@dataclass
class VersionedResult:
    """One version of a skill output. Operational skills may have multiple versions."""
    content: str
    version: int = 1
    created_at: Optional[str] = None  # ISO format

    @classmethod
    def new(cls, content: str, version: int = 1) -> "VersionedResult":
        return cls(content=content, version=version, created_at=datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {"content": self.content, "version": self.version, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, data: dict) -> "VersionedResult":
        return cls(
            content=data.get("content", ""),
            version=data.get("version", 1),
            created_at=data.get("created_at"),
        )


@dataclass
class Session:
    """Full session state for a Telegram user.

    `results` schema: dict[skill_key, list[VersionedResult]]
    FIFO max 5 versions per skill to keep Supabase storage bounded.

    For backward-compat: if stored as str (old schema), automatically wrapped to v1 on read.
    """
    user_id: int
    stage: PipelineStage = PipelineStage.IDLE
    selected_task: Optional[str] = None
    profile: BusinessProfile = field(default_factory=BusinessProfile)

    intake_history: list[dict] = field(default_factory=list)

    # Versioned results — FIFO max 5 per skill
    results: dict[str, list[VersionedResult]] = field(default_factory=dict)

    # Pending intake answers for single-shot ops skills (cleared after use)
    pending_intake: dict[str, str] = field(default_factory=dict)

    # User preferences (set once at first /start)
    # - en_level: "none" / "moderate" / "fluent"
    # - other future settings: notification time, default platform...
    preferences: dict[str, str] = field(default_factory=dict)

    # Feedback collected per skill (rating + correction notes)
    # Schema: {skill_name: [{"version": int, "rating": 1-5, "feedback": str, "created_at": iso}]}
    feedback: dict[str, list[dict]] = field(default_factory=dict)

    # When user opts to "Chạy A→Z, rồi quay lại task này", store the original task here.
    # After pipeline completes, bot auto-launches this skill.
    pending_followup_skill: Optional[str] = None

    # Sprint 6 — Tone calibration state cho Content Writing loop.
    # Schema khi đang chạy loop:
    #   {
    #     "campaign_id": "...",
    #     "stage": "waiting_first" | "checking_tone" | "locked" | "generating_rest" | "done",
    #     "rejection_count": 0,
    #     "current_attempt": {...},        # current draft of post 1 (full content dict)
    #     "locked_signals": {...},          # populated after user OK — inject vào prompt N-1
    #     "calendar_remaining": [...],      # N-1 posts to gen sau khi lock
    #     "sample_content": str | None,     # PA1 fallback nếu rejection >= 3
    #   }
    tone_calibration: dict = field(default_factory=dict)

    # Sprint 7 — Content outputs với mã ID `POST-XXX`.
    # Schema: {
    #   "POST-001": {
    #     "campaign_id": "...",
    #     "week": 1, "day": "Mon",
    #     "channel": "facebook",
    #     "pillar": "Educate", "funnel": "TOFU",
    #     "content": {hook, body, cta, hashtags, visual_brief},
    #     "adapted_versions": ["POST-001-TT", "POST-001-ZALO"],
    #     "status": "draft" | "approved" | "posted",
    #     "created_at": "ISO timestamp",
    #     "updated_at": "ISO timestamp",
    #   },
    #   "POST-001-TT": {
    #     "parent_id": "POST-001",
    #     "channel": "tiktok",
    #     "content": {...},
    #     ...
    #   },
    # }
    content_outputs: dict = field(default_factory=dict)

    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # ─── Intake history ───────────────────────────────────────────

    def add_to_history(self, role: str, content: str):
        self.intake_history.append({"role": role, "content": content})
        if len(self.intake_history) > 20:
            self.intake_history = self.intake_history[-20:]

    # ─── Results helpers ──────────────────────────────────────────

    def add_result(self, skill_key: str, content: str) -> int:
        """Add new version of a skill result. Returns version number."""
        versions = self.results.setdefault(skill_key, [])
        next_version = (versions[-1].version + 1) if versions else 1
        versions.append(VersionedResult.new(content, version=next_version))
        # FIFO trim
        if len(versions) > MAX_VERSIONS_PER_SKILL:
            self.results[skill_key] = versions[-MAX_VERSIONS_PER_SKILL:]
        return next_version

    def get_latest_result(self, skill_key: str) -> Optional[str]:
        """Get the latest version content of a skill result."""
        versions = self.results.get(skill_key, [])
        if not versions:
            return None
        return versions[-1].content

    def has_result(self, skill_key: str) -> bool:
        return bool(self.results.get(skill_key))

    # ─── Pipeline context builder ─────────────────────────────────

    def build_pipeline_context(self) -> str:
        """Build full context string for pipeline agents (uses latest of each skill)."""
        parts = [self.profile.to_context_string()]

        from frameworks.kpi_library import get_framework_as_text
        if self.profile.industry:
            kpi_text = get_framework_as_text(self.profile.industry)
            parts.append(kpi_text)

        # Strategic skill results — inject latest version
        stage_labels = {
            "market_research":    "## Kết quả Nghiên cứu Thị trường",
            "competitor":         "## Kết quả Phân tích Đối thủ",
            "customer_insight":   "## Kết quả Customer Insight",
            "psychology_pricing": "## Kết quả Marketing Psychology & Pricing",
            "usp_definition":     "## Kết quả USP Definition",          # Sprint 2
            "retention_strategy": "## Kết quả Retention Strategy",       # Sprint 3
            "winback_campaign":   "## Kết quả Winback Vision",            # Sprint 3
            "social_listening":   "## Kết quả Social Listening Setup",
            "synthesis":          "## Kết quả Marketing Strategy",
        }
        for key, label in stage_labels.items():
            content = self.get_latest_result(key)
            if content:
                parts.append(f"{label}\n{content}")

        return "\n\n---\n\n".join(parts)
