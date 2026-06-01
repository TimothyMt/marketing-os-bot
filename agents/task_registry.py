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
        label="Trọn Bộ A→Z",
        button_emoji="🔍",
        category="full",
        description="Phân tích chiến lược toàn diện — Market + Competitor + Customer + Pricing + USP + Retention + Synthesis",
        skill_class_name="",  # Composite
        pipeline_stages=[
            "market_research",
            "competitor",
            "customer_insight",
            "psychology_pricing",
            "usp_definition",
            "retention_strategy",
            "winback_campaign",
            "synthesis",
        ],
        intake_required_fields=[
            "industry", "product_service", "target_customer",
            "monthly_revenue", "primary_goal", "main_challenge",
        ],
        # intake_fields khai báo đủ để smart pre-fill hoạt động:
        # Fields đã có từ McKinsey Gate (industry/product/target/goal) sẽ tự pre-fill,
        # bot chỉ hỏi những gì còn thiếu (monthly_revenue, main_challenge).
        intake_fields=[
            {"key": "product_service",  "label": "Sản phẩm/dịch vụ chính", "example": "Spa laser trị mụn, combo 3 buổi 1.2M", "required": True},
            {"key": "target_customer",  "label": "Khách hàng mục tiêu",     "example": "Phụ nữ 25-35 đi làm văn phòng HCM", "required": True},
            {"key": "monthly_revenue",  "label": "Doanh thu tháng hiện tại","example": "80-120 triệu/tháng (hoặc 'mới mở chưa có')", "required": True},
            {"key": "primary_goal",     "label": "Mục tiêu 90 ngày tới",   "example": "Tăng doanh thu 30%, mở thêm kênh TikTok", "required": True},
            {"key": "main_challenge",   "label": "Khó khăn lớn nhất hiện tại", "example": "Chi phí ads cao, khách không quay lại", "required": True},
            {"key": "industry",         "label": "Ngành (tự map nếu không nhập)", "example": "health_beauty", "required": False},
        ],
    ),
    "market": TaskConfig(
        name="market",
        label="Tìm Hiểu Thị Trường",
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
        label="Phân Tích Đối Thủ",
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
        label="Insight Khách Hàng",
        button_emoji="👥",
        category="strategic",
        description="ICP + Jobs-to-be-Done + Pain-Gain Map",
        skill_class_name="CustomerInsightSkill",
        pipeline_stages=["customer_insight"],
        intake_required_fields=["industry", "product_service", "target_customer"],
        intake_fields=[
            {"key": "product_service",  "label": "Sản phẩm/dịch vụ",                  "example": "Spa làm đẹp · combo Tết 680K", "required": True},
            {"key": "target_customer",  "label": "Khách hàng mục tiêu hiện tại",       "example": "Phụ nữ 28-38 thu nhập 25-50tr", "required": True},
            {"key": "main_challenge",   "label": "Sếp nghĩ khách tiềm năng đang gặp khó khăn gì?", "example": "Khách không biết chọn sản phẩm phù hợp — hoặc 'chưa biết, em research'", "required": False},
            {"key": "location",         "label": "Địa bàn",                            "example": "HCM", "required": False},
        ],
    ),
    "pricing": TaskConfig(
        name="pricing",
        label="Chiến Lược Giá",
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
        label="Lập Kế Hoạch Tổng",
        button_emoji="🎯",
        category="strategic",
        description="SAVE Framework + SMART Goals + 90-day Roadmap",
        skill_class_name="StrategySynthesisSkill",
        pipeline_stages=["synthesis"],
        intake_required_fields=[
            "industry", "product_service", "target_customer",
            "monthly_revenue", "primary_goal", "main_challenge",
        ],
    ),
}


# ─────────────────────────────────────────────────────────────────
# Operational skills (NEW — 8 skills)
# ─────────────────────────────────────────────────────────────────

OPERATIONAL_TASKS: dict[str, TaskConfig] = {
    "campaign_brief": TaskConfig(
        name="campaign_brief",
        label="Viết Brief Campaign",
        button_emoji="📋",
        category="operational",
        description="Bridge Strategy → Tactical — Brief campaign 10 sections",
        skill_class_name="CampaignBriefSkill",
        intake_fields=[
            {"key": "campaign_name", "label": "Tên campaign", "example": "Combo Tết \"Tặng Mình Trước\"", "required": True},
            {"key": "campaign_goal", "label": "Mục tiêu chính", "example": "Thu 6000 mess, doanh thu 500 triệu", "required": True},
            {"key": "duration",      "label": "Thời gian chạy", "example": "25/12/2025 → 04/02/2026 (40 ngày)", "required": True},
            {"key": "key_offer",     "label": "Offer chính", "example": "Combo 680K (gốc 850K, giảm 20%), hết hạn 04/02", "required": True},
        ],
    ),
    "content_calendar": TaskConfig(
        name="content_calendar",
        label="Lịch Nội Dung",
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
    "content_generator": TaskConfig(
        name="content_generator",
        label="Sản Xuất Nội Dung",
        button_emoji="✍️",
        category="operational",
        description="Sản xuất toàn bộ content package: bài đăng + UGC brief — output 2 files Excel",
        skill_class_name="ContentGeneratorPipeline",
        intake_fields=[
            {"key": "scope",     "label": "Sản xuất cho ngày nào / tuần nào?", "example": "Tuần 1 (5-11/01/2026) — 14 bài", "required": True},
            {"key": "tone_note", "label": "Tone cần đặc biệt note?",            "example": "Tết — vibe ấm áp + urgency mềm", "required": False},
        ],
    ),
    "social_posts": TaskConfig(
        name="social_posts",
        label="Viết Bài Đăng",
        button_emoji="📝",
        category="operational",
        description="Viết bài đăng Facebook/Zalo/Instagram từ Calendar — output Excel Content Calendar",
        skill_class_name="SocialPostsSkill",
        intake_fields=[
            {"key": "scope",     "label": "Viết cho ngày / tuần nào?",  "example": "Tuần 1 (5-11/01) — 7 bài Facebook + Zalo", "required": True},
            {"key": "tone_note", "label": "Tone note đặc biệt?",         "example": "Tết — vibe ấm áp + urgency nhẹ",           "required": False},
        ],
    ),
    "video_script_gen": TaskConfig(
        name="video_script_gen",
        label="Kịch Bản Video (từ Calendar)",
        button_emoji="🎬",
        category="operational",
        description="Kịch bản video chuyên sâu cho các slot video trong Lịch — output Excel Video Script",
        skill_class_name="VideoScriptGenSkill",
        intake_fields=[
            {"key": "scope",     "label": "Viết kịch bản cho video nào / tuần nào?", "example": "Tuần 1 — 4 video TikTok + 2 Reels", "required": True},
            {"key": "tone_note", "label": "Tone/format note đặc biệt?",              "example": "TikTok trend; founder tự quay", "required": False},
        ],
    ),
    "ugc_brief": TaskConfig(
        name="ugc_brief",
        label="Brief Creator UGC",
        button_emoji="🤝",
        category="operational",
        description="Viết Creator Brief chi tiết cho UGC/KOL/EGC — output Excel UGC Brief",
        skill_class_name="UGCBriefSkill",
        intake_fields=[
            {"key": "creator_types", "label": "Loại creator nào?",     "example": "2 UGC micro (1K-10K) + 1 KOL (100K+)",    "required": True},
            {"key": "campaign_goal", "label": "Mục tiêu campaign UGC?", "example": "Trust-building + tăng review organic",     "required": False},
        ],
    ),
    "ads_generator": TaskConfig(
        name="ads_generator",
        label="Sản Xuất Nội Dung Ads",
        button_emoji="📢",
        category="operational",
        description="Gen ads cho Meta + TikTok — Video script hoặc Brief ảnh",
        skill_class_name="AdsCopySkill",  # Subclass — has tier + format selector (Sprint 3 sẽ refactor)
        intake_fields=[
            {"key": "product",       "label": "Sản phẩm/dịch vụ và giá", "example": "Combo Tết spa 680K (gốc 850K)", "required": True},
            {"key": "insight",       "label": "Insight cốt lõi của tệp", "example": "Phụ nữ muốn được chăm sóc nhưng cần \"lý do\"", "required": True},
            {"key": "campaign_goal", "label": "Mục tiêu campaign", "example": "Thu Mess / Lead / Chốt đơn / Awareness", "required": True},
            {"key": "offer",         "label": "Ưu đãi + deadline", "example": "Giảm 20% đến hết 04/02/2026", "required": True},
        ],
    ),
    "video_scripts": TaskConfig(
        name="video_scripts",
        label="Viết Kịch Bản Video",
        button_emoji="🎬",
        category="operational",
        description="Kịch bản video TikTok/Reels/Shorts — mạnh về social/organic",
        skill_class_name="VideoScriptsSkill",
        intake_fields=[
            {"key": "topic",     "label": "Sản phẩm/thông điệp",        "example": "Combo Tết spa — message: yêu bản thân", "required": True},
            {"key": "funnel",    "label": "Tầng phễu",                  "example": "TOFU (awareness) / MOFU / BOFU", "required": True},
            {"key": "duration",  "label": "Độ dài video (giây)",         "example": "15s / 30s / 45s / 60s", "required": True},
        ],
    ),
    "landing_page": TaskConfig(
        name="landing_page",
        label="Thiết Kế Website",
        button_emoji="🌐",
        category="operational",
        description="Brief + HTML landing page hoàn chỉnh cho dev/designer",
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
        label="Kịch Bản Sales",
        button_emoji="💬",
        category="operational",
        description="Script chat cho team sales — tone match với campaign brief",
        skill_class_name="SalesInboxScriptSkill",
        intake_fields=[
            {"key": "channel",      "label": "Kênh chat",                  "example": "Facebook Messenger / Zalo OA / Instagram DM", "required": True},
            {"key": "common_query", "label": "Câu hỏi/tình huống phổ biến nhất", "example": "Khách hỏi giá rồi im, khách hỏi địa chỉ", "required": True},
            {"key": "team_size",    "label": "Số nhân viên chat",           "example": "3 người, làm ca sáng/chiều/tối", "required": False},
        ],
    ),
    "email_zalo_sequence": TaskConfig(
        name="email_zalo_sequence",
        label="Chăm Sóc Khách Hàng",
        button_emoji="📧",
        category="operational",
        description="Chuỗi nurture Email + Zalo OA cho lead/khách cũ",
        skill_class_name="EmailZaloSequenceSkill",
        intake_fields=[
            {"key": "audience_segment", "label": "Tệp nurture",             "example": "Khách đã inbox chưa book / Khách book chưa đến / Khách 1 lần", "required": True},
            {"key": "sequence_goal",    "label": "Mục tiêu chuỗi",          "example": "Đưa khách quay lại đặt lịch / Upsell / Reactivation", "required": True},
            {"key": "channel_preference","label": "Email / Zalo / Cả 2",    "example": "Cả 2 — Email cho long-form, Zalo cho short reminder", "required": True},
            {"key": "duration",         "label": "Dài chuỗi (số ngày)",     "example": "7 ngày / 14 ngày / 30 ngày", "required": False},
        ],
    ),
    "competitor_spy": TaskConfig(
        name="competitor_spy",
        label="Theo Dõi Đối Thủ",
        button_emoji="🔍",
        category="operational",
        description="Phân tích Facebook Ads Library của đối thủ — pattern + insight",
        skill_class_name="CompetitorSpySkill",
        intake_fields=[
            {"key": "competitor_name", "label": "Tên đối thủ",                          "example": "Cocoon Vietnam",                                  "required": True},
            {"key": "fanpage_url",     "label": "Link Facebook Page (nếu có, để chính xác)", "example": "https://facebook.com/cocoonvn",              "required": False},
            {"key": "focus_area",      "label": "Sếp muốn em focus phân tích gì",       "example": "Hook style / Offer mechanics / Creative format",  "required": False},
            {"key": "pasted_ads",      "label": "Paste ads tay (nếu FB API chưa setup, mở https://facebook.com/ads/library copy 3-10 ads vào đây)", "example": "Ad 1: 'CEO sẽ hỏi gì?...' / Ad 2: ...", "required": False},
        ],
    ),
    "competitor_comparison": TaskConfig(
        name="competitor_comparison",
        label="So Sánh Với Đối Thủ",
        button_emoji="🆚",
        category="operational",
        description="So sánh business của sếp với đối thủ đã phân tích",
        skill_class_name="CompetitorComparisonSkill",
        # KHÔNG có intake_fields — đọc full từ session.results
        intake_fields=[],
    ),
    "comment_mining": TaskConfig(
        name="comment_mining",
        label="Phân Tích Comment",
        button_emoji="💬",
        category="operational",
        description="Khai thác insight từ comments → 7 content idea mới",
        skill_class_name="CommentMiningSkill",
        intake_fields=[
            {"key": "comments_text",  "label": "Paste danh sách comments (1 dòng/comment, càng nhiều càng tốt)", "example": "1. Sản phẩm có gây kích ứng không?\n2. Da khô có dùng được không?\n...", "required": True},
            {"key": "topic_context",  "label": "Comments này về chủ đề/sản phẩm gì",                              "example": "Skincare cho da nhạy cảm", "required": True},
            {"key": "platform",       "label": "Comments từ kênh nào",                                            "example": "Facebook Page / TikTok / Shopee / Group", "required": False},
        ],
    ),
    "brand_voice": TaskConfig(
        name="brand_voice",
        label="Bộ Quy Tắc Brand Voice",
        button_emoji="🎙️",
        category="operational",
        description="Build bộ quy tắc giọng văn cho team content dùng nhất quán",
        skill_class_name="BrandVoiceSkill",
        intake_fields=[
            {"key": "do_list",         "label": "3-5 điều NÊN làm khi viết (tone, kiểu câu)",   "example": "Xưng em với khách / kể chuyện cá nhân / dùng emoji vừa phải", "required": True},
            {"key": "dont_list",       "label": "3-5 điều KHÔNG nên làm",                       "example": "Tránh 'tuyệt vời nhất' / không dùng từ tiếng Anh không giải thích / không pressure mua", "required": True},
            {"key": "sample_content",  "label": "Paste 1-2 đoạn nội dung cũ của brand (để em phân tích style)", "example": "Hôm nay shop xin chia sẻ sản phẩm mới của mình...", "required": True},
        ],
    ),
    "content_repurpose": TaskConfig(
        name="content_repurpose",
        label="Tái Sử Dụng Content",
        button_emoji="♻️",
        category="operational",
        description="Biến 1 bài content gốc thành 5 phiên bản khác nhau (newcomer/trust/debate/personal/action)",
        skill_class_name="ContentRepurposeSkill",
        intake_fields=[
            {"key": "original_content", "label": "Paste content gốc cần repurpose",          "example": "Bài blog dài 800 chữ về 5 lợi ích serum Vitamin C...", "required": True},
            {"key": "repurpose_goal",   "label": "Mục tiêu repurpose chính",                  "example": "Tăng reach mới / tăng engagement / chốt sale cuối tháng", "required": True},
        ],
    ),
    "retention_strategy": TaskConfig(
        name="retention_strategy",
        label="Chiến Lược Giữ Chân Khách",
        button_emoji="🔄",
        category="strategic",
        description="Hệ thống retention 3 giai đoạn (mới mở / tăng trưởng / ổn định) — phân tầng 4 nhóm khách",
        skill_class_name="RetentionStrategySkill",
        intake_fields=[
            {"key": "business_stage",   "label": "Doanh nghiệp đang ở giai đoạn nào",  "example": "Mới mở (0-6 tháng) / Tăng trưởng (6-24 tháng) / Ổn định (2 năm+)", "required": True},
            {"key": "customer_volume",  "label": "Số khách hiện có (ước tính)",         "example": "500 khách (300 mua 1 lần, 150 active, 50 VIP)", "required": True},
            {"key": "current_retention","label": "Repeat rate / Churn rate hiện tại (nếu có data)", "example": "Repeat ~25%, churn 90d ~45%", "required": False},
            {"key": "main_concern",     "label": "Vấn đề retention sếp đang lo nhất",    "example": "Khách mua 1 lần rồi không quay / không có hệ thống nhắc", "required": False},
            {"key": "segments_data",    "label": "Phân bổ 4 nhóm khách cụ thể (nếu có)", "example": "Mới 200, Active 80, Nguy cơ 50, Đã bỏ 30 / bỏ trống nếu chưa rõ", "required": False},
            {"key": "top_products",     "label": "Top 3 SP/DV bán chạy + giá (nếu có)",  "example": "Liệu trình HydraFacial 1.5tr / Combo skincare 800k / Mask đơn lẻ 250k", "required": False},
            {"key": "churn_pattern",    "label": "Khách thường bỏ sau bao lâu / sau hành vi gì (nếu rõ)", "example": "Bỏ sau lần 1 (~60%), bỏ sau 90 ngày không nhắc, bỏ khi giá tăng", "required": False},
        ],
    ),
    "winback_campaign": TaskConfig(
        name="winback_campaign",
        label="Winback Khách Cũ",
        button_emoji="🔁",
        category="strategic",
        description="Re-engage khách đã bỏ — sequence 3 bước, script + offer Tier, test 10% trước scale",
        skill_class_name="WinbackCampaignSkill",
        intake_fields=[
            {"key": "target_segment",   "label": "Nhóm khách cần winback",              "example": "Khách mua 1 lần >60 ngày chưa quay / VIP cũ mất liên lạc >6 tháng / Khách mua nhiều lần đột ngột dừng >90 ngày", "required": True},
            {"key": "list_size",        "label": "Số lượng ước tính",                     "example": "~120 khách trong danh sách", "required": True},
            {"key": "suspected_reasons","label": "Lý do bỏ nghi ngờ (nếu có ý)",          "example": "Đa số quên vì busy / 1 vài người có phàn nàn cũ về thời gian chờ", "required": False},
            {"key": "available_offer",  "label": "Offer có thể đưa ra (range)",           "example": "Có thể giảm tối đa 15-20% / có thể tặng free 1 buổi mask", "required": False},
            {"key": "last_purchase_data","label": "Phân bố ngày mua cuối (nếu có)",        "example": "50 khách 60-90 ngày, 40 khách 90-180 ngày, 30 khách >180 ngày", "required": False},
            {"key": "avg_order_value",  "label": "AOV cũ của nhóm winback (nếu rõ)",       "example": "AOV ~1.2tr/lần, top 20% ~3tr", "required": False},
            {"key": "past_winback_tried","label": "Đã thử winback chưa, kết quả?",         "example": "Có thử SMS giảm 20% tháng trước, reply <5%, 1 vài người block", "required": False},
        ],
    ),
    # ─────────────────────────────────────────────────────────────
    # CONTENT SUITE v2 — 6 skills chuyên content production
    # (inspired by Hồng Phương narrative + CMO/CTO architecture)
    # ─────────────────────────────────────────────────────────────
    "post_write": TaskConfig(
        name="post_write",
        label="Viết 1 Bài Content",
        button_emoji="✍️",
        category="operational",
        description="Single Post Generator — input 1 row Calendar → output Hook 3 variants + Body + CTA + Visual brief",
        skill_class_name="PostWriteSkill",
        intake_fields=[
            {"key": "date_channel", "label": "Ngày + Kênh đăng",          "example": "Thứ 2 8:30 sáng — Facebook Page", "required": True},
            {"key": "topic",        "label": "Chủ đề bài viết",            "example": "Hướng dẫn chọn bảng trắng phòng họp B2B", "required": True},
            {"key": "pillar_funnel","label": "Pillar + Funnel",            "example": "Educate / TOFU", "required": True},
            {"key": "audience",     "label": "Đối tượng cụ thể",           "example": "Office manager 28-40 tuổi SME 50-200 người", "required": False},
        ],
    ),
    "post_adapt": TaskConfig(
        name="post_adapt",
        label="Adapt sang Channel Khác",
        button_emoji="🔄",
        category="operational",
        description="Channel Adapter — 1 bài gốc → FB / TikTok / Zalo / Instagram (4 format khác nhau)",
        skill_class_name="PostAdaptSkill",
        intake_fields=[
            {"key": "source_post",     "label": "Paste bài gốc (Facebook/Blog/Email)", "example": "Bài blog 800 chữ về 5 lợi ích serum Vitamin C...", "required": True},
            {"key": "target_channels", "label": "Channels muốn adapt sang",            "example": "TikTok + Zalo OA + Instagram Carousel", "required": True},
        ],
    ),
    "post_voice_check": TaskConfig(
        name="post_voice_check",
        label="Check Brand Voice",
        button_emoji="✅",
        category="operational",
        description="Voice Lock — check draft theo Brand Voice Rules + suggest fix",
        skill_class_name="PostVoiceCheckSkill",
        intake_fields=[
            {"key": "draft_post",        "label": "Paste draft post cần check",         "example": "Hôm nay shop xin giới thiệu sản phẩm mới...", "required": True},
            {"key": "brand_voice_rules", "label": "10 brand voice rules (paste)",       "example": "1. Xưng em với khách\n2. Tránh 'tuyệt vời nhất'\n...", "required": True},
        ],
    ),
    "post_hooks": TaskConfig(
        name="post_hooks",
        label="Hook Bank — 15 hooks",
        button_emoji="🪝",
        category="operational",
        description="Hook Generator — 15 hooks chia 5 nhóm psychological + recommend top 5",
        skill_class_name="PostHooksSkill",
        intake_fields=[
            {"key": "topic",         "label": "Chủ đề / Sản phẩm",           "example": "Skincare cho da nhạy cảm", "required": True},
            {"key": "audience",      "label": "Audience target",              "example": "Phụ nữ 25-35, da nhạy cảm, từng dùng nhiều brand", "required": True},
            {"key": "funnel_stage",  "label": "Funnel stage",                  "example": "TOFU / MOFU / BOFU", "required": True},
        ],
    ),
    "post_visual": TaskConfig(
        name="post_visual",
        label="Visual Brief cho Designer",
        button_emoji="🎨",
        category="operational",
        description="Visual Brief Generator — convert post text → brief chi tiết cho designer/videographer",
        skill_class_name="PostVisualSkill",
        intake_fields=[
            {"key": "post_text",     "label": "Paste post text cần làm visual",  "example": "Hook: Tại sao 80% phụ nữ dùng serum sai cách?\nBody: ...", "required": True},
            {"key": "format_type",   "label": "Format",                           "example": "Image / Carousel 5 slides / Reel 30s", "required": True},
            {"key": "channel",       "label": "Channel đăng",                     "example": "Instagram / TikTok / Facebook", "required": True},
        ],
    ),
    "post_batch": TaskConfig(
        name="post_batch",
        label="Batch — Tuần Content",
        button_emoji="📚",
        category="operational",
        description="Batch Producer — gen 7-14 bài content cùng lúc cho 1 tuần (rút gọn so Single Post)",
        skill_class_name="PostBatchSkill",
        intake_fields=[
            {"key": "week_label",   "label": "Tuần nào",                        "example": "Tuần 1 — 5-11/01/2026", "required": True},
            {"key": "post_count",   "label": "Số bài muốn gen",                  "example": "7 bài (1 bài/ngày)", "required": True},
            {"key": "theme",        "label": "Theme/concept tuần",               "example": "Awareness — Pain point chọn skincare", "required": False},
        ],
    ),
    "performance_audit": TaskConfig(
        name="performance_audit",
        label="Báo Cáo Ads",
        button_emoji="📊",
        category="analysis",
        description="Báo cáo + Audit campaign — VN benchmarks + diagnostic + next actions",
        skill_class_name="PerformanceAuditSkill",
        intake_fields=[
            {"key": "campaign_name",   "label": "Tên campaign cần audit",        "example": "Tết \"Tặng Mình Trước\" — 25/12/2025 → 14/01/2026", "required": True},
            {"key": "budget_spent",    "label": "Budget đã chi + tổng KPI",      "example": "Đã chi 52tr/150tr tổng. KPI: 6000 mess, 2174 booking, 500tr revenue", "required": True},
            {"key": "channels_data",   "label": "Số liệu theo kênh (Mess/Reach/Lead/Booking/Revenue)", "example": "Meta: 800 mess, CPMess 19K, ...\nTikTok: 220 mess, CPMess 27K, ...", "required": True},
            {"key": "key_concern",     "label": "Vấn đề lo lắng nhất",            "example": "Lead nhiều nhưng booking thấp", "required": False},
        ],
    ),
    "ads_analytics": TaskConfig(
        name="ads_analytics",
        label="Analytics Ads Tự Động",
        button_emoji="📈",
        category="analysis",
        description="Pull live data FB Ad Account → phân tích portfolio: winners/losers, creative fatigue, budget efficiency",
        skill_class_name="AdsAnalyticsSkill",
        intake_fields=[
            {"key": "date_range",      "label": "Khoảng thời gian",                    "example": "30 ngày / 7 ngày / tháng trước / tháng này", "required": True},
            {"key": "level",           "label": "Mức độ phân tích",                     "example": "campaign (mặc định) / adset / ad", "required": False},
            {"key": "focus_area",      "label": "Muốn focus vào gì",                    "example": "tổng quan / frequency radar / winners / budget reallocation", "required": False},
            {"key": "campaign_filter", "label": "Lọc campaign cụ thể (bỏ trống = toàn account)", "example": "FT09 / Tết 2026", "required": False},
        ],
    ),
    "ads_optimizer": TaskConfig(
        name="ads_optimizer",
        label="Tối Ưu Ads Trực Tiếp",
        button_emoji="⚡",
        category="analysis",
        description="Phân tích Andromeda signals → đề xuất + thực thi actions (pause/activate/budget) trên campaigns có sẵn",
        skill_class_name="AdsOptimizerSkill",
        intake_fields=[
            {"key": "target",     "label": "Campaign / Ad Set / Ad cần thao tác",    "example": "FT09 / Lookalike 1% / toàn account", "required": True},
            {"key": "action",     "label": "Hành động muốn thực hiện",                "example": "pause campaign yếu / tăng budget FT09 lên 500k / bật lại adset Lookalike 2%", "required": True},
            {"key": "reason",     "label": "Lý do / metric tham chiếu (tuỳ chọn)",   "example": "Frequency 6.5, CPM 180K > benchmark", "required": False},
        ],
    ),
    "viral_video_analyzer": TaskConfig(
        name="viral_video_analyzer",
        label="Phân Tích Video Viral",
        button_emoji="🎥",
        category="analysis",
        description="Reverse-engineer kịch bản video viral → công thức replicate + production brief shoot-ready",
        skill_class_name="ViralVideoAnalyzerSkill",
        intake_fields=[
            {"key": "video_source",      "label": "Link video HOẶC paste transcript",
             "example": "https://www.tiktok.com/@xyz/video/123  HOẶC paste lời thoại nếu không có link", "required": True},
            {"key": "platform",          "label": "Platform",
             "example": "TikTok / Reels / Shorts / YouTube", "required": True},
            {"key": "niche_context",     "label": "Niche / chủ đề video (để Max so sánh với business sếp)",
             "example": "Review skincare cho da dầu — tệp nữ 22-30", "required": True},
            {"key": "creator_persona",   "label": "Ai sẽ quay (để Max tailor shot list + script)",
             "example": "Em founder nữ 30t, ngại lên hình / Có nhân viên nữ 24t sweet vibe / Sẽ thuê KOC", "required": True},
            {"key": "engagement_data",   "label": "Số liệu video (view / like / comment / share — nếu biết)",
             "example": "2.4M view, 180K like, 5K comment — hoặc 'không rõ'", "required": False},
            {"key": "why_picked",        "label": "Vì sao sếp chọn video này để phân tích",
             "example": "Hook 3s đầu rất mạnh, muốn học công thức", "required": False},
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
