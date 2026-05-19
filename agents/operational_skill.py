"""
OperationalSkill — generic class for standard operational skills.

Standard ops skills follow same pattern: single-shot intake → fill template → output deliverable.
This generic class handles 6 of 8 ops skills via config.

Special ops skills (AdsCopySkill, VideoScriptsSkill) have custom logic — keep as subclass.
"""
from dataclasses import dataclass, field
from typing import Optional

from agents.skills import (
    AgentSkill,
    OutputFormat,
    IntakePattern,
    ContextStrategy,
    PrimaryDeliverable,
)
from storage.models import Session


@dataclass
class OperationalSkillConfig:
    """Config for one standard operational skill — drives OperationalSkill behavior."""
    name: str
    label: str

    # Prompt
    system_prompt: str
    user_msg_template: str           # Template with {placeholder} for intake fields + session data
    max_tokens: int = 4000

    # Behavior
    output_format: OutputFormat = OutputFormat.OPERATIONAL_DELIVERABLE
    context_strategy: ContextStrategy = ContextStrategy.PROFILE_PLUS_STRATEGY
    primary_deliverable: PrimaryDeliverable = PrimaryDeliverable.HTML
    enable_critic: bool = False       # Most ops skills don't need critic

    # Intake (declared in task_registry, but cached here too for skill self-containment)
    intake_fields: list[dict] = field(default_factory=list)


class OperationalSkill(AgentSkill):
    """Generic operational skill — behavior driven by OperationalSkillConfig.

    Reads context from session.profile + (optionally) session.results based on context_strategy.
    Builds user message by filling template with session.pending_intake answers.

    Used for 6 of 8 ops skills:
      campaign_brief, content_calendar, landing_page, sales_inbox_script,
      email_zalo_sequence, performance_audit

    AdsCopySkill + VideoScriptsSkill are custom subclasses (separate file) due to:
      - AdsCopy: tier batching (TOFU/MOFU/BOFU selection)
      - VideoScripts: 4 creator type variants
    """

    intake_pattern = IntakePattern.SINGLE_SHOT_FORM
    accumulate_to_report = False  # Each ops deliverable is standalone

    def __init__(self, config: OperationalSkillConfig):
        self._config = config
        # Copy config values to instance attrs (AgentSkill API)
        self.name = config.name
        self.system_prompt = config.system_prompt
        self.max_tokens = config.max_tokens
        self.output_format = config.output_format
        self.context_strategy = config.context_strategy
        self.primary_deliverable = config.primary_deliverable
        self.enable_critic = config.enable_critic

    # ─── Context builder — resolves based on context_strategy ─────

    def build_context(self, session: Session) -> str:
        """Build context string based on configured strategy."""
        from frameworks.kpi_library import get_framework_as_text

        if self.context_strategy == ContextStrategy.PROFILE_ONLY:
            return session.profile.to_context_string()

        elif self.context_strategy == ContextStrategy.FULL_PIPELINE:
            return session.build_pipeline_context()

        elif self.context_strategy == ContextStrategy.PROFILE_PLUS_STRATEGY:
            parts = [session.profile.to_context_string()]
            synthesis = session.get_latest_result("synthesis")
            if synthesis:
                parts.append(f"## Kết quả Marketing Strategy (đã có từ trước)\n{synthesis}")
            return "\n\n---\n\n".join(parts)

        elif self.context_strategy == ContextStrategy.PROFILE_PLUS_CAMPAIGN:
            parts = [session.profile.to_context_string()]
            synthesis = session.get_latest_result("synthesis")
            if synthesis:
                parts.append(f"## Marketing Strategy nền\n{synthesis}")
            campaign_brief = session.get_latest_result("campaign_brief")
            if campaign_brief:
                parts.append(f"## Campaign Brief hiện tại\n{campaign_brief}")
            return "\n\n---\n\n".join(parts)

        elif self.context_strategy == ContextStrategy.PROFILE_PLUS_KPI:
            parts = [session.profile.to_context_string()]
            if session.profile.industry:
                kpi_text = get_framework_as_text(session.profile.industry)
                parts.append(kpi_text)
            return "\n\n---\n\n".join(parts)

        # Fallback
        return session.profile.to_context_string()

    # ─── User message builder — fills template ────────────────────

    def build_user_msg(self, session: Session) -> str:
        """Fill user_msg_template with intake answers + safe defaults."""
        # Pending intake answers (from single-shot form)
        intake = dict(session.pending_intake or {})

        # Common profile fallbacks accessible in template
        profile = session.profile
        intake.setdefault("industry",         profile.industry or "chưa xác định")
        intake.setdefault("business_name",    profile.business_name or "business của bạn")
        intake.setdefault("product_service",  profile.product_service or "chưa xác định")
        intake.setdefault("target_customer",  profile.target_customer or "chưa xác định")
        intake.setdefault("location",         profile.location or "Việt Nam")
        intake.setdefault("monthly_revenue",  profile.monthly_revenue or "chưa rõ")
        intake.setdefault("primary_goal",     profile.primary_goal or "tăng doanh thu")
        intake.setdefault("main_challenge",   profile.main_challenge or "chưa xác định")

        try:
            return self._config.user_msg_template.format(**intake)
        except KeyError as e:
            # Missing field — return template with placeholder warning
            return self._config.user_msg_template.replace(
                "{" + str(e).strip("'") + "}",
                f"[missing: {e}]"
            ).format(**{k: v for k, v in intake.items()})

    # ─── Intake helpers ───────────────────────────────────────────

    def get_intake_fields(self) -> list[dict]:
        """Return declared intake fields (for single-shot form template)."""
        return list(self._config.intake_fields)

    def missing_intake_fields(self, session: Session) -> list[dict]:
        """Return only fields that need to be asked (not in session.pending_intake)."""
        provided = set((session.pending_intake or {}).keys())
        return [f for f in self._config.intake_fields if f.get("key") not in provided]
