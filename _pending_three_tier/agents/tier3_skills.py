from agents.skills import AgentSkill
from agents.tier3_prompts import (
    AD_COPY_SYSTEM,
    VIDEO_SCRIPT_SYSTEM,
    UGC_BRIEF_SYSTEM,
    EMAIL_ZALO_SYSTEM,
)
from storage.models import Session


def _build_tier3_context(session: Session) -> str:
    parts = [session.profile.to_context_string()]

    if "synthesis" in session.results:
        parts.append(f"## Marketing Strategy (Tier 1)\n{session.results['synthesis']}")

    if "campaign_brief" in session.results:
        parts.append(f"## Campaign Brief (Tier 2)\n{session.results['campaign_brief']}")

    if "customer_insight" in session.results:
        parts.append(f"## Customer Insight\n{session.results['customer_insight']}")

    cp = session.campaign_profile
    profile_lines = ["## Campaign Context"]
    if cp.campaign_type:
        profile_lines.append(f"- **Loại chiến dịch**: {cp.campaign_type}")
    if cp.campaign_goal:
        profile_lines.append(f"- **Mục tiêu**: {cp.campaign_goal}")
    if cp.campaign_channels:
        profile_lines.append(f"- **Kênh**: {cp.campaign_channels}")
    if cp.content_tone:
        profile_lines.append(f"- **Tone**: {cp.content_tone}")
    if len(profile_lines) > 1:
        parts.append("\n".join(profile_lines))

    return "\n\n---\n\n".join(parts)


class AdCopySkill(AgentSkill):
    name = "ad_copy"
    system_prompt = AD_COPY_SYSTEM
    max_tokens = 5000
    enable_critic = False

    def build_context(self, session: Session) -> str:
        return _build_tier3_context(session)

    def build_user_msg(self, session: Session) -> str:
        cp = session.campaign_profile
        tier = cp.selected_ad_tier or "all"
        channels = cp.campaign_channels or "facebook,tiktok"
        product = session.profile.product_service or "sản phẩm/dịch vụ"
        tone = cp.content_tone or "conversational"

        return f"""Viết ad copy cho chiến dịch này.

Sản phẩm/dịch vụ: {product}
Kênh: {channels}
Tầng phễu cần: {tier}
Tone: {tone}

Tạo 6 variants × {'3 tầng TOFU/MOFU/BOFU' if tier == 'all' else f'tầng {tier.upper()}'}.
Mỗi variant đầy đủ: Primary text (≤125 ký tự hook) + Headline + Description + CTA button.
Cuối thêm notes cho media buyer."""


class VideoScriptSkill(AgentSkill):
    name = "video_script"
    system_prompt = VIDEO_SCRIPT_SYSTEM
    max_tokens = 5000
    enable_critic = False

    def build_context(self, session: Session) -> str:
        return _build_tier3_context(session)

    def build_user_msg(self, session: Session) -> str:
        cp = session.campaign_profile
        creator_type = cp.selected_creator_type or "ugc"
        product = session.profile.product_service or "sản phẩm/dịch vụ"
        channels = cp.campaign_channels or "tiktok"

        return f"""Viết script video cho loại creator: {creator_type.upper()}

Sản phẩm/dịch vụ: {product}
Kênh đăng: {channels}

Tạo 2 phiên bản A/B với đầy đủ 5 act (Hook 3s / Problem 10s / Solution 20s / Social Proof 10s / CTA 7s).
Bao gồm dialogue, visual direction, on-screen text, và production notes.
Kết thúc với A/B test recommendation."""


class UGCBriefSkill(AgentSkill):
    name = "ugc_brief"
    system_prompt = UGC_BRIEF_SYSTEM
    max_tokens = 4000
    enable_critic = False

    def build_context(self, session: Session) -> str:
        return _build_tier3_context(session)

    def build_user_msg(self, session: Session) -> str:
        cp = session.campaign_profile
        creator_type = cp.selected_creator_type or "ugc"
        product = session.profile.product_service or "sản phẩm/dịch vụ"
        business = session.profile.business_name or "brand"
        budget = cp.campaign_budget or "thỏa thuận"

        return f"""Tạo Creator Brief cho chiến dịch {business}.

Loại creator: {creator_type.upper()}
Sản phẩm/dịch vụ: {product}
Ngân sách creator: {budget}

Brief phải đầy đủ 8 phần: Tổng quan / Mục tiêu / Hướng sáng tạo / Script framework / Yêu cầu kỹ thuật / Quy trình giao nhận / Điều khoản pháp lý / Thanh toán.
Viết ngôn ngữ thân thiện, creator đọc xong tự làm được không cần hỏi thêm."""


class EmailZaloSkill(AgentSkill):
    name = "email_zalo"
    system_prompt = EMAIL_ZALO_SYSTEM
    max_tokens = 5000
    enable_critic = False

    def build_context(self, session: Session) -> str:
        return _build_tier3_context(session)

    def build_user_msg(self, session: Session) -> str:
        cp = session.campaign_profile
        product = session.profile.product_service or "sản phẩm/dịch vụ"
        business = session.profile.business_name or "brand"
        goal = cp.campaign_goal or "nurture leads"
        tone = cp.content_tone or "professional"
        target = session.profile.target_customer or "khách hàng tiềm năng"

        return f"""Tạo chuỗi email nurture + Zalo OA cho {business}.

Sản phẩm/dịch vụ: {product}
Đối tượng: {target}
Mục tiêu chuỗi: {goal}
Tone: {tone}

Tạo đầy đủ:
- 5 email với subject line, preview text, và body copy hoàn chỉnh (viết sẵn, không để placeholder)
- 3 tin nhắn Zalo OA (xác nhận / nhắc nhở / promo broadcast)
Mỗi email/tin nhắn có đúng 1 CTA."""


TIER3_SKILL_REGISTRY: dict[str, type[AgentSkill]] = {
    "ad_copy":       AdCopySkill,
    "video_script":  VideoScriptSkill,
    "ugc_brief":     UGCBriefSkill,
    "email_zalo":    EmailZaloSkill,
}
