"""
Operational skill instances — combines OperationalSkill generic + special subclasses.

Standard skills (6): instances of OperationalSkill driven by config.
Special skills (2): subclass with custom logic.
  - AdsCopySkill: tier batching (TOFU/MOFU/BOFU selection)
  - VideoScriptsSkill: 4 creator type variants
"""
from agents.operational_skill import OperationalSkill, OperationalSkillConfig
from agents.skills import (
    AgentSkill,
    OutputFormat,
    IntakePattern,
    ContextStrategy,
    PrimaryDeliverable,
)
from agents.operational_prompts import (
    CAMPAIGN_BRIEF_SYSTEM,
    CONTENT_CALENDAR_SYSTEM,
    CONTENT_GENERATOR_SYSTEM,
    ADS_COPY_SYSTEM,
    VIDEO_SCRIPTS_SYSTEM,
    LANDING_PAGE_SYSTEM,
    SALES_INBOX_SCRIPT_SYSTEM,
    EMAIL_ZALO_SEQUENCE_SYSTEM,
    COMPETITOR_SPY_SYSTEM,
    COMPETITOR_COMPARISON_SYSTEM,
    PERFORMANCE_AUDIT_SYSTEM,
    COMMENT_MINING_SYSTEM,
    BRAND_VOICE_SYSTEM,
    CONTENT_REPURPOSE_SYSTEM,
)
from agents.task_registry import OPERATIONAL_TASKS
from storage.models import Session


# ─────────────────────────────────────────────────────────────────
# STANDARD operational skills (6) — via generic OperationalSkill
# ─────────────────────────────────────────────────────────────────

def _config_for(skill_name: str, system_prompt: str, **overrides) -> OperationalSkillConfig:
    """Helper to build config from task_registry entry."""
    task = OPERATIONAL_TASKS.get(skill_name)
    if not task:
        raise ValueError(f"Unknown ops skill: {skill_name}")

    # Default user msg template — embeds intake fields with placeholder
    default_template = _build_default_template(task)

    defaults = dict(
        name=skill_name,
        label=task.label,
        system_prompt=system_prompt,
        user_msg_template=default_template,
        intake_fields=task.intake_fields,
        max_tokens=4000,
        output_format=OutputFormat.OPERATIONAL_DELIVERABLE,
        context_strategy=ContextStrategy.PROFILE_PLUS_STRATEGY,
        primary_deliverable=PrimaryDeliverable.HTML,
        enable_critic=False,
    )
    defaults.update(overrides)
    return OperationalSkillConfig(**defaults)


def _build_default_template(task) -> str:
    """Build user message template from task intake fields."""
    parts = [f"## Yêu cầu skill: {task.label}", ""]
    parts.append("**Thông tin user cung cấp:**")
    for f in task.intake_fields:
        parts.append(f"- **{f['label']}**: {{{f['key']}}}")
    parts.append("")
    parts.append("**Context business (từ profile đã thu thập):**")
    parts.append("- Ngành: {industry}")
    parts.append("- Tên business: {business_name}")
    parts.append("- Sản phẩm/dịch vụ: {product_service}")
    parts.append("- Khách hàng: {target_customer}")
    parts.append("- Địa bàn: {location}")
    parts.append("")
    parts.append(f"Hãy {task.description.lower()} dựa trên thông tin trên.")
    return "\n".join(parts)


# Instance factories — return fresh skill instance each call
def make_campaign_brief_skill() -> OperationalSkill:
    return OperationalSkill(_config_for(
        "campaign_brief",
        CAMPAIGN_BRIEF_SYSTEM,
        max_tokens=10000,  # bumped — 10-section brief is comprehensive
        context_strategy=ContextStrategy.PROFILE_PLUS_STRATEGY,
        primary_deliverable=PrimaryDeliverable.HTML,
    ))


def make_content_calendar_skill() -> OperationalSkill:
    """Sprint 3.4: Pillar % DYNAMIC theo stage + goal + challenge."""
    return OperationalSkill(_config_for(
        "content_calendar",
        CONTENT_CALENDAR_SYSTEM,
        max_tokens=10000,
        context_strategy=ContextStrategy.PROFILE_PLUS_CAMPAIGN,
        primary_deliverable=PrimaryDeliverable.EXCEL,
    ))


def calc_dynamic_pillar_mix(profile, synthesis: str = "") -> dict:
    """Sprint 3.4: Calculate Pillar % dynamically dựa profile + synthesis.
    Returns dict {educate, trust, engage, convert} that sums to 1.0.

    Heuristics:
    - MVP/Early stage → Educate cao (new brand cần educate)
    - Growth → balanced
    - Scale → Trust + Retention cao
    - Goal "brand_awareness" → Educate + Engage
    - Goal "revenue/conversion" → Convert cao
    - Goal "retention" → Trust cao
    """
    base = {"educate": 0.30, "trust": 0.30, "engage": 0.20, "convert": 0.20}

    # Stage adjustment
    stage = (profile.stage or "").lower() if profile else ""
    if stage in ("idea", "mvp"):
        base["educate"] += 0.15
        base["convert"] -= 0.10
        base["engage"] -= 0.05
    elif stage == "scale":
        base["trust"] += 0.10
        base["educate"] -= 0.05
        base["convert"] -= 0.05

    # Goal adjustment
    goal = (profile.primary_goal or "").lower() if profile else ""
    synthesis_lower = (synthesis or "").lower()

    if any(k in goal + synthesis_lower for k in ["awareness", "brand", "nhận diện"]):
        base["educate"] += 0.10
        base["engage"] += 0.05
        base["convert"] -= 0.15
    elif any(k in goal + synthesis_lower for k in ["revenue", "doanh thu", "conversion", "chốt"]):
        base["convert"] += 0.15
        base["educate"] -= 0.10
        base["trust"] -= 0.05
    elif any(k in goal + synthesis_lower for k in ["retention", "giữ chân", "repeat", "loyalty"]):
        base["trust"] += 0.15
        base["convert"] -= 0.05
        base["educate"] -= 0.10

    # Normalize (handle negatives or sum != 1.0)
    for k in base:
        if base[k] < 0.05:
            base[k] = 0.05
    total = sum(base.values())
    return {k: round(v / total, 2) for k, v in base.items()}


def make_landing_page_skill() -> OperationalSkill:
    return OperationalSkill(_config_for(
        "landing_page",
        LANDING_PAGE_SYSTEM,
        max_tokens=8000,  # bumped — 7 sections + checklist
        context_strategy=ContextStrategy.PROFILE_PLUS_CAMPAIGN,
        primary_deliverable=PrimaryDeliverable.MARKDOWN,
    ))


def make_sales_inbox_script_skill() -> OperationalSkill:
    return OperationalSkill(_config_for(
        "sales_inbox_script",
        SALES_INBOX_SCRIPT_SYSTEM,
        max_tokens=8000,  # bumped — 7 sections with objection handling
        context_strategy=ContextStrategy.PROFILE_PLUS_CAMPAIGN,
        primary_deliverable=PrimaryDeliverable.MARKDOWN,
    ))


def make_email_zalo_sequence_skill() -> OperationalSkill:
    return OperationalSkill(_config_for(
        "email_zalo_sequence",
        EMAIL_ZALO_SEQUENCE_SYSTEM,
        max_tokens=8000,  # bumped — multi-day sequence with email + zalo for each
        context_strategy=ContextStrategy.PROFILE_PLUS_CAMPAIGN,
        primary_deliverable=PrimaryDeliverable.MARKDOWN,
    ))


def make_content_generator_skill() -> OperationalSkill:
    """Sprint 3: NEW — gen content theo từng bài từ Content Calendar."""
    return OperationalSkill(_config_for(
        "content_generator",
        CONTENT_GENERATOR_SYSTEM,
        max_tokens=12000,  # output dài (1 tuần = 7-14 bài, mỗi bài 200-300 từ)
        context_strategy=ContextStrategy.PROFILE_PLUS_CAMPAIGN,
        primary_deliverable=PrimaryDeliverable.EXCEL,  # Table export — paste GG Sheet
    ))


def make_competitor_spy_skill() -> OperationalSkill:
    """Sprint 3: NEW — phân tích FB Ads Library của đối thủ.
    Hiện tại em không tự gọi FB API (chờ key). User paste ads content/screenshots → em phân tích."""
    return OperationalSkill(_config_for(
        "competitor_spy",
        COMPETITOR_SPY_SYSTEM,
        max_tokens=8000,
        context_strategy=ContextStrategy.PROFILE_PLUS_STRATEGY,
        primary_deliverable=PrimaryDeliverable.HTML,
    ))


def make_competitor_comparison_skill() -> OperationalSkill:
    """Sprint 4: Follow-up sau competitor analysis — so sánh business sếp vs đối thủ."""
    return OperationalSkill(_config_for(
        "competitor_comparison",
        COMPETITOR_COMPARISON_SYSTEM,
        max_tokens=6000,
        context_strategy=ContextStrategy.FULL_PIPELINE,  # Đọc cả competitor + profile
        primary_deliverable=PrimaryDeliverable.HTML,
    ))


def make_comment_mining_skill() -> OperationalSkill:
    """NEW (test branch): Mine insight từ comments → 7 content ideas."""
    return OperationalSkill(_config_for(
        "comment_mining",
        COMMENT_MINING_SYSTEM,
        max_tokens=8000,
        context_strategy=ContextStrategy.PROFILE_ONLY,
        primary_deliverable=PrimaryDeliverable.MARKDOWN,
    ))


def make_brand_voice_skill() -> OperationalSkill:
    """NEW (test branch): Build bộ quy tắc giọng văn brand."""
    return OperationalSkill(_config_for(
        "brand_voice",
        BRAND_VOICE_SYSTEM,
        max_tokens=8000,
        context_strategy=ContextStrategy.PROFILE_ONLY,
        primary_deliverable=PrimaryDeliverable.MARKDOWN,
    ))


def make_content_repurpose_skill() -> OperationalSkill:
    """NEW (test branch): 1 bài content → 5 phiên bản khác audience."""
    return OperationalSkill(_config_for(
        "content_repurpose",
        CONTENT_REPURPOSE_SYSTEM,
        max_tokens=10000,
        context_strategy=ContextStrategy.PROFILE_PLUS_STRATEGY,
        primary_deliverable=PrimaryDeliverable.MARKDOWN,
    ))


def make_performance_audit_skill() -> OperationalSkill:
    return OperationalSkill(_config_for(
        "performance_audit",
        PERFORMANCE_AUDIT_SYSTEM,
        max_tokens=10000,  # bumped — analysis output is data-heavy
        output_format=OutputFormat.OPERATIONAL_ANALYSIS,
        context_strategy=ContextStrategy.PROFILE_PLUS_CAMPAIGN,
        primary_deliverable=PrimaryDeliverable.EXCEL,
        enable_critic=True,
    ))


# ─────────────────────────────────────────────────────────────────
# SPECIAL skills (2) — custom subclasses with extra logic
# ─────────────────────────────────────────────────────────────────

class ContentCalendarDynamicSkill(OperationalSkill):
    """Sprint 3.4: Content Calendar với Pillar % dynamic theo business stage + goal."""

    def __init__(self):
        config = _config_for(
            "content_calendar",
            CONTENT_CALENDAR_SYSTEM,
            max_tokens=10000,
            context_strategy=ContextStrategy.PROFILE_PLUS_CAMPAIGN,
            primary_deliverable=PrimaryDeliverable.EXCEL,
        )
        super().__init__(config)

    def build_user_msg(self, session: Session) -> str:
        base_msg = super().build_user_msg(session)
        # Inject dynamic pillar mix
        synthesis = session.get_latest_result("synthesis") or ""
        pillar_mix = calc_dynamic_pillar_mix(session.profile, synthesis)
        pillar_str = " / ".join(
            f"{k.title()} {int(v*100)}%" for k, v in pillar_mix.items()
        )
        return (
            base_msg
            + "\n\n---\n\n**PILLAR MIX TÍNH ĐỘNG cho business này (dùng đúng số này, không tự thay):**\n"
            + pillar_str
            + "\n\n_(Tính dựa trên: stage = "
            + str(session.profile.stage or "unknown")
            + ", goal = "
            + str(session.profile.primary_goal or "unknown")
            + ")_"
        )


class AdsCopySkill(AgentSkill):
    """Special ops skill: user picks which tier(s) to generate.

    Reads `session.pending_intake["selected_tiers"]` to determine scope:
      - "tofu" / "mofu" / "bofu" → only that tier (2 variants)
      - "all" → 3 tiers × 2 variants = 6 copy units
    """
    name = "ads_copy"
    system_prompt = ADS_COPY_SYSTEM
    max_tokens = 12000  # bumped — full 3-tier × 2 variants × 2 platforms = 12 copy units
    enable_critic = False
    output_format = OutputFormat.OPERATIONAL_DELIVERABLE
    intake_pattern = IntakePattern.SINGLE_SHOT_FORM
    context_strategy = ContextStrategy.PROFILE_PLUS_CAMPAIGN
    primary_deliverable = PrimaryDeliverable.MARKDOWN  # For designer / media buyer
    accumulate_to_report = False

    def build_context(self, session: Session) -> str:
        parts = [session.profile.to_context_string()]
        # Inject campaign_brief if available for tone consistency
        campaign_brief = session.get_latest_result("campaign_brief")
        if campaign_brief:
            parts.append(f"## Campaign Brief context\n{campaign_brief}")
        return "\n\n---\n\n".join(parts)

    def build_user_msg(self, session: Session) -> str:
        intake = session.pending_intake or {}
        tier = (intake.get("selected_tiers") or "all").lower()
        profile = session.profile

        scope_instruction = {
            "tofu": "CHỈ generate TẦNG 1 — TOFU (2 variants). Bỏ qua MOFU/BOFU.",
            "mofu": "CHỈ generate TẦNG 2 — MOFU (2 variants). Bỏ qua TOFU/BOFU.",
            "bofu": "CHỈ generate TẦNG 3 — BOFU (2 variants). Bỏ qua TOFU/MOFU.",
            "all":  "Generate FULL 3 tầng (TOFU + MOFU + BOFU), mỗi tầng 2 variants. Tổng 6 copy units.",
        }.get(tier, "Generate FULL 3 tầng (TOFU + MOFU + BOFU).")

        return f"""## Yêu cầu: Viết Ads Copy cho campaign

**Sản phẩm/giá:** {intake.get('product', 'chưa có')}
**Insight cốt lõi:** {intake.get('insight', 'chưa có')}
**Mục tiêu campaign:** {intake.get('campaign_goal', 'chưa có')}
**Ưu đãi + deadline:** {intake.get('offer', 'chưa có')}

**Context business:**
- Ngành: {profile.industry or 'chưa xác định'}
- Khách hàng: {profile.target_customer or 'chưa xác định'}
- Địa bàn: {profile.location or 'Việt Nam'}

**Scope:** {scope_instruction}

Viết copy thật sự dùng được ngay, không generic."""


class VideoScriptsSkill(AgentSkill):
    """Special ops skill: 4 creator type variants.

    Reads `session.pending_intake["creator_type"]` to determine variant style:
      - "ugc" / "egc" / "fgc" / "kol"
    """
    name = "video_scripts"
    system_prompt = VIDEO_SCRIPTS_SYSTEM
    max_tokens = 8000  # bumped — 2 variants + production guide
    enable_critic = False
    output_format = OutputFormat.OPERATIONAL_DELIVERABLE
    intake_pattern = IntakePattern.SINGLE_SHOT_FORM
    context_strategy = ContextStrategy.PROFILE_PLUS_CAMPAIGN
    primary_deliverable = PrimaryDeliverable.MARKDOWN  # For creator brief
    accumulate_to_report = False

    def build_context(self, session: Session) -> str:
        parts = [session.profile.to_context_string()]
        campaign_brief = session.get_latest_result("campaign_brief")
        if campaign_brief:
            parts.append(f"## Campaign Brief context\n{campaign_brief}")
        return "\n\n---\n\n".join(parts)

    def build_user_msg(self, session: Session) -> str:
        intake = session.pending_intake or {}
        creator_type = (intake.get("creator_type") or "ugc").lower()
        profile = session.profile

        creator_guidance = {
            "ugc": "UGC (User-Generated Content) — khách hàng thật chia sẻ. Tone bình thản, kể chuyện với bạn thân. Authentic > polished. Style: tự nhiên, đứng trước cửa sổ.",
            "egc": "EGC (Employee-Generated Content) — nhân viên chia sẻ insider knowledge. Tone expert nhẹ, backstage style. Style: trong workspace, có sản phẩm/thiết bị xung quanh.",
            "fgc": "FGC (Founder-Generated Content) — founder tự quay storytelling. Tone depth + vision, lessons learned. Style: founder vibe, background chỉn chu.",
            "kol": "KOL/KOC (Paid Creator) — creator paid để promote. Tone theo persona của KOC, integrated organic. KOC tự quyết góc quay theo style của họ. Brief tập trung message + Do/Don't, không gò cách quay.",
        }.get(creator_type, "UGC — authentic style.")

        return f"""## Yêu cầu: Viết Video Script

**Topic / Sản phẩm:** {intake.get('topic', 'chưa có')}
**Tầng phễu:** {intake.get('funnel', 'TOFU')}
**Độ dài video:** {intake.get('duration', '30s')}

**Creator type (user đã chọn):** {creator_type.upper()}
**Hướng dẫn cho creator type này:**
{creator_guidance}

**Context business:**
- Ngành: {profile.industry or 'chưa xác định'}
- Khách hàng: {profile.target_customer or 'chưa xác định'}

Output 2 VARIANTS A/B với angle khác nhau. Mỗi variant: hook đúng dạng phù hợp creator type, script timing chi tiết, caption gợi ý, và hướng dẫn quay phù hợp creator type.

Lưu ý: KHÔNG bao gồm hợp đồng/commercial terms."""


# ─────────────────────────────────────────────────────────────────
# Registry: skill_name → factory function
# ─────────────────────────────────────────────────────────────────

OPS_SKILL_FACTORIES: dict[str, callable] = {
    "campaign_brief":      make_campaign_brief_skill,
    "content_calendar":    ContentCalendarDynamicSkill,  # Sprint 3.4 — Pillar dynamic
    "content_generator":   make_content_generator_skill,
    "competitor_spy":      make_competitor_spy_skill,
    "competitor_comparison": make_competitor_comparison_skill,
    "landing_page":        make_landing_page_skill,
    "sales_inbox_script":  make_sales_inbox_script_skill,
    "email_zalo_sequence": make_email_zalo_sequence_skill,
    "performance_audit":   make_performance_audit_skill,
    "ads_copy":            AdsCopySkill,
    "ads_generator":       AdsCopySkill,
    "video_scripts":       VideoScriptsSkill,
    # NEW skills (test branch)
    "comment_mining":      make_comment_mining_skill,
    "brand_voice":         make_brand_voice_skill,
    "content_repurpose":   make_content_repurpose_skill,
}


def get_operational_skill(skill_name: str) -> AgentSkill:
    """Factory entry point — returns an AgentSkill instance for the named operational skill."""
    factory = OPS_SKILL_FACTORIES.get(skill_name)
    if not factory:
        raise ValueError(f"Unknown operational skill: {skill_name}")
    return factory() if callable(factory) else factory
