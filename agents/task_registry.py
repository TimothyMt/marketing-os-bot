"""
Unified Task Registry — single source of truth for all skills.

THÊM SKILL MỚI = thêm 1 entry vào TASK_REGISTRY (KHÔNG sửa 4 file scattered).

Each TaskConfig defines:
- Identity (name, label, emoji)
- UI (category, description, intake hint)
- Skill class (concrete AgentSkill subclass or generic OperationalSkill)
- Pipeline behavior (for full-mode pipeline composition)
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TaskConfig:
    """Config for one user-facing task."""
    # Identity
    name: str
    label: str
    button_emoji: str

    # Category for multi-tier menu
    category: str  # "strategic" / "operational" / "analysis" / "full"

    # Description shown in confirm card / docs
    description: str = ""

    # Opening question (for first user message after task selection)
    opening_question: str = ""

    # Skill class reference (str — late binding to avoid import cycle)
    skill_class_name: str = ""

    # Pipeline composition (for "full" task that runs multiple stages)
    pipeline_stages: list[str] = field(default_factory=list)

    # Intake fields (declared upfront — used by SingleShotIntake to build template)
    intake_fields: list[dict] = field(default_factory=list)
    # Each field: {key, label, example, required}

    # Profile fields ESSENTIAL để task này chạy (Phase 1.2)
    # Khi check needs_intake(): nếu session.profile có ĐỦ các fields này → skip intake
    # Strategic tasks: ánh xạ sang BusinessProfile fields
    # Operational tasks: thường rỗng vì dùng pending_intake template paste
    intake_required_fields: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────
# Strategic skills (existing — 6 skills + full mode)
# ─────────────────────────────────────────────────────────────────

STRATEGIC_TASKS: dict[str, TaskConfig] = {
    "full": TaskConfig(
        name="full",
        label="Phân tích toàn diện",
        button_emoji="🔍",
        category="full",
        description="Chạy 5 bước phân tích chiến lược tuần tự",
        skill_class_name="",  # Composite
        pipeline_stages=["market_research", "competitor", "customer_insight", "psychology_pricing", "synthesis"],
        # Full mode cần full profile — yêu cầu nhiều fields
        intake_required_fields=[
            "industry", "product_service", "target_customer",
            "monthly_revenue", "primary_goal", "main_challenge",
        ],
    ),
    "market": TaskConfig(
        name="market",
        label="Nghiên cứu thị trường",
        button_emoji="📊",
        category="strategic",
        description="TAM/SAM/SOM + Market Dynamics",
        skill_class_name="MarketResearchSkill",
        pipeline_stages=["market_research"],
        intake_required_fields=["industry", "product_service", "target_customer", "location"],
        intake_fields=[
            {"key": "product_service", "label": "Sản phẩm/dịch vụ", "example": "Spa làm đẹp · combo facial 680K", "required": True},
            {"key": "target_customer", "label": "Khách hàng mục tiêu", "example": "Phụ nữ 25-40, đi làm văn phòng", "required": True},
            {"key": "location",        "label": "Thị trường nào",     "example": "HCM nội thành (Q1, Q3, Q7)", "required": True},
            {"key": "industry",        "label": "Ngành (tự động map nếu không nhập)", "example": "health_beauty", "required": False},
        ],
    ),
    "competitor": TaskConfig(
        name="competitor",
        label="Phân tích đối thủ",
        button_emoji="🕵️",
        category="strategic",
        description="8 chiều phân tích + Market Gap",
        skill_class_name="CompetitorSkill",
        pipeline_stages=["competitor"],
        intake_required_fields=["industry", "product_service", "target_customer", "competitors"],
        intake_fields=[
            {"key": "product_service", "label": "Sản phẩm/dịch vụ",         "example": "Spa làm đẹp Q1 HCM", "required": True},
            {"key": "target_customer", "label": "Khách hàng mục tiêu",      "example": "Phụ nữ 25-40", "required": True},
            {"key": "competitors",     "label": "Đối thủ đã biết (tên cụ thể nếu có)", "example": "Cocoon, M.O.I, Lemonade — hoặc 'chưa biết' để Max tự research", "required": True},
            {"key": "location",        "label": "Địa bàn cạnh tranh",        "example": "HCM nội thành", "required": False},
        ],
    ),
    "customer": TaskConfig(
        name="customer",
        label="Customer Insight",
        button_emoji="👥",
        category="strategic",
        description="ICP + Jobs-to-be-Done + Pain-Gain Map",
        skill_class_name="CustomerInsightSkill",
        pipeline_stages=["customer_insight"],
        intake_required_fields=["industry", "product_service", "target_customer", "main_challenge"],
        intake_fields=[
            {"key": "product_service",  "label": "Sản phẩm/dịch vụ",                "example": "Spa làm đẹp · combo Tết 680K", "required": True},
            {"key": "target_customer",  "label": "Khách hàng mục tiêu hiện tại",     "example": "Phụ nữ 28-38 thu nhập 25-50tr", "required": True},
            {"key": "main_challenge",   "label": "Vấn đề lớn nhất với khách hàng",   "example": "Khách 1 lần đi rồi không quay lại", "required": True},
            {"key": "location",         "label": "Địa bàn",                          "example": "HCM", "required": False},
        ],
    ),
    "pricing": TaskConfig(
        name="pricing",
        label="Pricing Strategy",
        button_emoji="💰",
        category="strategic",
        description="Pricing Model + Psychology Tactics",
        skill_class_name="PsychologyPricingSkill",
        pipeline_stages=["psychology_pricing"],
        intake_required_fields=["industry", "product_service", "target_customer", "monthly_revenue"],
        intake_fields=[
            {"key": "product_service",  "label": "Sản phẩm/dịch vụ + giá hiện tại",  "example": "Combo Tết spa hiện 850K, đang test giảm 20%", "required": True},
            {"key": "target_customer",  "label": "Khách hàng + khả năng chi tiêu",   "example": "Phụ nữ 28-40 thu nhập 25-50tr", "required": True},
            {"key": "monthly_revenue",  "label": "Doanh thu hiện tại",               "example": "80 triệu/tháng", "required": True},
            {"key": "primary_goal",     "label": "Mục tiêu pricing",                  "example": "Tăng margin / Tăng volume / Giảm churn", "required": False},
        ],
    ),
    "strategy": TaskConfig(
        name="strategy",
        label="Marketing Strategy",
        button_emoji="🎯",
        category="strategic",
        description="SAVE Framework + SMART Goals + 90-day Roadmap",
        skill_class_name="StrategySynthesisSkill",
        pipeline_stages=["synthesis"],
        # Strategy là output cuối — cần full profile
        intake_required_fields=[
            "industry", "product_service", "target_customer",
            "monthly_revenue", "primary_goal", "main_challenge",
        ],
        # KHÔNG có intake_fields → vẫn dùng multi-turn intake
    ),
}


# ─────────────────────────────────────────────────────────────────
# Operational skills (NEW — 8 skills)
# ─────────────────────────────────────────────────────────────────

OPERATIONAL_TASKS: dict[str, TaskConfig] = {
    "campaign_brief": TaskConfig(
        name="campaign_brief",
        label="Campaign Brief",
        button_emoji="📋",
        category="operational",
        description="Bridge Strategy → Tactical — Brief campaign 10 sections",
        skill_class_name="CampaignBriefSkill",  # Generic OperationalSkill
        intake_fields=[
            {"key": "campaign_name", "label": "Tên campaign", "example": "Combo Tết \"Tặng Mình Trước\"", "required": True},
            {"key": "campaign_goal", "label": "Mục tiêu chính", "example": "Thu 6000 mess, doanh thu 500 triệu", "required": True},
            {"key": "duration",      "label": "Thời gian chạy", "example": "25/12/2025 → 04/02/2026 (40 ngày)", "required": True},
            {"key": "key_offer",     "label": "Offer chính", "example": "Combo 680K (gốc 850K, giảm 20%), hết hạn 04/02", "required": True},
        ],
    ),
    "content_calendar": TaskConfig(
        name="content_calendar",
        label="Content Calendar",
        button_emoji="📅",
        category="operational",
        description="Lịch content tháng — Pillar + Funnel + Source mix",
        skill_class_name="ContentCalendarSkill",
        intake_fields=[
            {"key": "channels", "label": "Kênh", "example": "TikTok + Facebook + Zalo OA", "required": True},
            {"key": "duration", "label": "Lên cho tuần hay tháng?", "example": "Tháng 1/2026", "required": True},
            {"key": "team_size", "label": "Số người trong team content", "example": "2 người: 1 content + 1 video editor", "required": False},
            {"key": "current_campaign", "label": "Có campaign nào đang chạy không?", "example": "Combo Tết \"Tặng Mình Trước\"", "required": False},
        ],
    ),
    "ads_copy": TaskConfig(
        name="ads_copy",
        label="Ads Copy",
        button_emoji="✍️",
        category="operational",
        description="Copy ads Meta + TikTok, 3-tier TOFU/MOFU/BOFU × 2 variants",
        skill_class_name="AdsCopySkill",  # Subclass — has tier selection logic
        intake_fields=[
            {"key": "product",       "label": "Sản phẩm/dịch vụ và giá", "example": "Combo Tết spa 680K (gốc 850K)", "required": True},
            {"key": "insight",       "label": "Insight cốt lõi của tệp", "example": "Phụ nữ muốn được chăm sóc nhưng cần \"lý do\"", "required": True},
            {"key": "campaign_goal", "label": "Mục tiêu campaign", "example": "Thu Mess / Lead / Chốt đơn / Awareness", "required": True},
            {"key": "offer",         "label": "Ưu đãi + deadline", "example": "Giảm 20% đến hết 04/02/2026", "required": True},
        ],
    ),
    "video_scripts": TaskConfig(
        name="video_scripts",
        label="Video Scripts",
        button_emoji="🎬",
        category="operational",
        description="Script video TikTok/Reels/Shorts — 4 variants creator type (UGC/EGC/FGC/KOL)",
        skill_class_name="VideoScriptsSkill",  # Subclass — has creator type selector
        intake_fields=[
            {"key": "topic",     "label": "Sản phẩm/thông điệp",        "example": "Combo Tết spa — message: yêu bản thân", "required": True},
            {"key": "funnel",    "label": "Tầng phễu",                  "example": "TOFU (awareness) / MOFU / BOFU", "required": True},
            {"key": "duration",  "label": "Độ dài video (giây)",         "example": "15s / 30s / 45s / 60s", "required": True},
            # creator_type chọn qua button, không qua intake form
        ],
    ),
    "landing_page": TaskConfig(
        name="landing_page",
        label="Landing Page Brief",
        button_emoji="🌐",
        category="operational",
        description="Brief landing page hoàn chỉnh cho dev/designer",
        skill_class_name="LandingPageSkill",
        intake_fields=[
            {"key": "page_goal",       "label": "Mục tiêu trang",                    "example": "Thu lead booking / Chốt đơn / Đặt lịch", "required": True},
            {"key": "traffic_source",  "label": "Traffic từ đâu",                    "example": "Meta Ads / TikTok Ads / Email / Organic", "required": True},
            {"key": "product_offer",   "label": "Sản phẩm/offer cụ thể và giá",      "example": "Combo Tết 680K (gốc 850K, giảm 20%)", "required": True},
            {"key": "urgency_deadline","label": "Ưu đãi có deadline không?",          "example": "Hết hạn 04/02/2026", "required": False},
        ],
    ),
    "sales_inbox_script": TaskConfig(
        name="sales_inbox_script",
        label="Sales/Inbox Script",
        button_emoji="💬",
        category="operational",
        description="Script chat cho team sales/inbox — base on campaign tone",
        skill_class_name="SalesInboxScriptSkill",
        intake_fields=[
            {"key": "channel",      "label": "Kênh chat",                  "example": "Facebook Messenger / Zalo OA / Instagram DM", "required": True},
            {"key": "common_query", "label": "Câu hỏi/tình huống phổ biến nhất", "example": "Khách hỏi giá rồi im, khách hỏi địa chỉ", "required": True},
            {"key": "team_size",    "label": "Số nhân viên chat",           "example": "3 người, làm ca sáng/chiều/tối", "required": False},
        ],
    ),
    "email_zalo_sequence": TaskConfig(
        name="email_zalo_sequence",
        label="Email/Zalo Nurture",
        button_emoji="📧",
        category="operational",
        description="Chuỗi nurture Email + Zalo OA cho lead",
        skill_class_name="EmailZaloSequenceSkill",
        intake_fields=[
            {"key": "audience_segment", "label": "Tệp nurture",             "example": "Khách đã inbox chưa book / Khách book chưa đến / Khách 1 lần", "required": True},
            {"key": "sequence_goal",    "label": "Mục tiêu chuỗi",          "example": "Đưa khách quay lại đặt lịch / Upsell / Reactivation", "required": True},
            {"key": "channel_preference","label": "Email / Zalo / Cả 2",    "example": "Cả 2 — Email cho long-form, Zalo cho short reminder", "required": True},
            {"key": "duration",         "label": "Dài chuỗi (số ngày)",     "example": "7 ngày / 14 ngày / 30 ngày", "required": False},
        ],
    ),
    "performance_audit": TaskConfig(
        name="performance_audit",
        label="Performance Audit",
        button_emoji="📈",
        category="analysis",
        description="Audit campaign — VN benchmarks + diagnostic + next actions",
        skill_class_name="PerformanceAuditSkill",
        intake_fields=[
            {"key": "campaign_name",   "label": "Tên campaign cần audit",        "example": "Tết \"Tặng Mình Trước\" — 25/12/2025 → 14/01/2026", "required": True},
            {"key": "budget_spent",    "label": "Budget đã chi + tổng KPI",      "example": "Đã chi 52tr/150tr tổng. KPI: 6000 mess, 2174 booking, 500tr revenue", "required": True},
            {"key": "channels_data",   "label": "Số liệu theo kênh (Mess/Reach/Lead/Booking/Revenue)", "example": "Meta: 800 mess, CPMess 19K, ...\nTikTok: 220 mess, CPMess 27K, ...", "required": True},
            {"key": "key_concern",     "label": "Vấn đề lo lắng nhất",            "example": "Lead nhiều nhưng booking thấp", "required": False},
        ],
    ),
}


# ─────────────────────────────────────────────────────────────────
# Unified registry — combines all tasks
# ─────────────────────────────────────────────────────────────────

TASK_REGISTRY: dict[str, TaskConfig] = {
    **STRATEGIC_TASKS,
    **OPERATIONAL_TASKS,
}


def get_task(name: str) -> Optional[TaskConfig]:
    """Lookup task by name."""
    return TASK_REGISTRY.get(name)


def list_by_category(category: str) -> list[TaskConfig]:
    """List all tasks in a category, preserving registration order."""
    return [t for t in TASK_REGISTRY.values() if t.category == category]


def needs_intake(session, task_name: str) -> bool:
    """Phase 1.3 helper: Check if session.profile already has fields needed for task.
    If all required fields present → user has done intake before → SKIP repeat intake.
    Returns True = need intake; False = can skip and go straight to confirm/execute.
    """
    task = get_task(task_name)
    if not task or not task.intake_required_fields:
        return True  # safe default — if no requirements declared, do intake
    profile = session.profile
    if not profile:
        return True
    for field_key in task.intake_required_fields:
        value = getattr(profile, field_key, None)
        if not value or (isinstance(value, str) and not value.strip()):
            return True  # missing field → need intake
    return False  # all required fields present → skip intake
