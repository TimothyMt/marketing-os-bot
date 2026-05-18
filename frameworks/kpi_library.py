"""
KPI Library — Pre-calibrated frameworks for each industry.
Intake agent detects industry → load matching KPIFramework → inject into all downstream agents.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class KPIFramework:
    industry: str
    display_name: str
    primary_kpis: list[dict]       # KPIs mà mọi business trong ngành PHẢI đo
    secondary_kpis: list[dict]     # KPIs quan trọng nhưng tùy stage
    vanity_kpis: list[dict]        # KPIs trông đẹp nhưng không drive decision
    benchmarks: dict               # Benchmark numbers theo stage
    unit_economics: dict           # Công thức tính unit economics của ngành
    growth_levers: list[str]       # Đòn bẩy tăng trưởng chính của ngành
    channel_priority: list[str]    # Kênh marketing ưu tiên theo ngành
    tam_methodology: str           # Cách ước lượng TAM phù hợp ngành
    context_note: str              # Lưu ý đặc thù ngành cho AI agents


KPI_LIBRARY: dict[str, KPIFramework] = {

    # ─────────────────────────────────────────────────────────────────
    # F&B: Nhà hàng, Cà phê, Quán ăn, Food Delivery, Cloud Kitchen
    # ─────────────────────────────────────────────────────────────────
    "fnb": KPIFramework(
        industry="fnb",
        display_name="F&B (Nhà hàng / Cà phê / Quán ăn)",
        primary_kpis=[
            {"name": "Average Order Value (AOV)", "formula": "Doanh thu / Số đơn", "target": "Tăng 15-25% so với baseline"},
            {"name": "Table Turn Rate", "formula": "Số lượt khách / Số bàn / Ca", "target": "> 2.0 cho bữa trưa, > 1.5 cho tối"},
            {"name": "Repeat Visit Rate (30 ngày)", "formula": "Khách quay lại / Tổng khách", "target": "> 30% trong tháng đầu"},
            {"name": "Cost of Goods Sold (COGS) %", "formula": "Giá vốn / Doanh thu", "target": "< 30% cho café, < 35% cho nhà hàng"},
            {"name": "Revenue per Square Meter", "formula": "Doanh thu tháng / Diện tích (m²)", "target": "Benchmark theo phân khúc"},
            {"name": "Google Maps Rating × Review Volume", "formula": "Rating ≥ 4.3 + > 200 reviews", "target": "Cần cả hai yếu tố"},
        ],
        secondary_kpis=[
            {"name": "Delivery % of Total Revenue", "formula": "Doanh thu app / Tổng doanh thu", "target": "< 40% để không bị phụ thuộc platform"},
            {"name": "Customer Acquisition Cost (CAC)", "formula": "Chi phí marketing / Khách mới", "target": "< 1 lần AOV"},
            {"name": "Peak Hour Utilization", "formula": "Capacity used / Total capacity", "target": "> 80% trong giờ cao điểm"},
            {"name": "Staff Cost %", "formula": "Chi phí nhân sự / Doanh thu", "target": "< 30%"},
            {"name": "Net Promoter Score (NPS)", "formula": "% Promoters - % Detractors", "target": "> 50"},
        ],
        vanity_kpis=[
            {"name": "Lượt follow Facebook/Instagram", "why": "Không liên quan trực tiếp đến revenue"},
            {"name": "Reach/Impression của bài post", "why": "Không đo được conversion về offline"},
            {"name": "Số lượng check-in", "why": "Tốt nhưng không predict revenue"},
        ],
        benchmarks={
            "mvp": {"monthly_revenue": "30-80 triệu VND", "repeat_rate": "> 20%", "google_rating": "> 4.0"},
            "growth": {"monthly_revenue": "100-500 triệu VND", "repeat_rate": "> 30%", "google_rating": "> 4.3"},
            "scale": {"monthly_revenue": "> 500 triệu VND", "repeat_rate": "> 40%", "google_rating": "> 4.5"},
        },
        unit_economics={
            "ltv_formula": "AOV × Avg visits/year × Avg customer lifespan (years)",
            "payback_period": "CAC / (AOV × Gross Margin %)",
            "break_even": "Fixed costs / (1 - Variable cost %)",
        },
        growth_levers=[
            "Tăng AOV qua upsell & bundle (hiệu quả nhất, không tốn CAC)",
            "Tăng frequency qua loyalty program (stamp card, app points)",
            "Mở rộng giờ phục vụ / daypart mới (breakfast nếu chỉ có lunch)",
            "Delivery để mở rộng bán kính phục vụ mà không mở thêm mặt bằng",
            "UGC: Khuyến khích khách check-in, review đổi voucher",
            "Corporate catering / B2B để fill capacity ngày thường",
        ],
        channel_priority=[
            "Google Maps & Google Business Profile (priority #1 — intent-based)",
            "Facebook Ads (retargeting địa lý 3-5km)",
            "TikTok (viral food content — đặc biệt cà phê & món đặc sắc)",
            "Shopee Food / GrabFood (acquisition nhưng cẩn thận margin)",
            "Zalo OA (CRM & loyalty — chi phí thấp, reach cao)",
            "Instagram (thương hiệu, aesthetic)",
        ],
        tam_methodology="Bottom-up: (Dân số trong bán kính 3km × % target segment × Dining frequency/month × AOV) × 12",
        context_note="FnB là ngành hyperlocal — mọi strategy phải bắt đầu từ bán kính 1-5km. Repeat purchase và word-of-mouth quan trọng hơn acquisition. COGS và staff cost là hai killer chính — phải kiểm soát trước khi scale marketing.",
    ),

    # ─────────────────────────────────────────────────────────────────
    # Tech SaaS / App / Digital Product
    # ─────────────────────────────────────────────────────────────────
    "tech_saas": KPIFramework(
        industry="tech_saas",
        display_name="Tech SaaS / App / Digital Product",
        primary_kpis=[
            {"name": "Monthly Recurring Revenue (MRR)", "formula": "Số subscribers × ARPU", "target": "MoM growth > 15% ở giai đoạn growth"},
            {"name": "Churn Rate", "formula": "Khách hủy / Tổng khách đầu tháng", "target": "< 5%/tháng (B2C), < 2%/tháng (B2B)"},
            {"name": "LTV:CAC Ratio", "formula": "LTV / CAC", "target": "> 3:1 để sustainable, > 5:1 để scale"},
            {"name": "Activation Rate", "formula": "Users đạt aha-moment / Total signups", "target": "> 40% trong 7 ngày đầu"},
            {"name": "Net Revenue Retention (NRR)", "formula": "(MRR đầu + Expansion - Churn - Contraction) / MRR đầu", "target": "> 100% = healthy growth"},
            {"name": "CAC Payback Period", "formula": "CAC / (ARPU × Gross Margin %)", "target": "< 12 tháng (B2C), < 18 tháng (B2B)"},
        ],
        secondary_kpis=[
            {"name": "Daily/Monthly Active Users (DAU/MAU)", "formula": "DAU / MAU", "target": "> 20% DAU/MAU ratio = sticky product"},
            {"name": "Trial-to-Paid Conversion Rate", "formula": "Paid users / Trial users", "target": "> 15% (B2C), > 25% (B2B)"},
            {"name": "Expansion MRR", "formula": "Upsell + Cross-sell MRR/tháng", "target": "> 20% of new MRR"},
            {"name": "NPS Score", "formula": "% Promoters - % Detractors", "target": "> 40"},
            {"name": "Feature Adoption Rate", "formula": "Users dùng feature / Total users", "target": "Core feature > 60%"},
        ],
        vanity_kpis=[
            {"name": "Total registered users", "why": "Không phản ánh engagement hoặc revenue"},
            {"name": "App downloads", "why": "Download ≠ activation ≠ retention"},
            {"name": "Page views / Sessions", "why": "Không liên quan đến revenue nếu không track conversion"},
        ],
        benchmarks={
            "mvp": {"mrr": "< 50 triệu VND", "churn": "< 10%/tháng OK", "ltv_cac": "> 2:1 là ổn"},
            "growth": {"mrr": "50-500 triệu VND", "churn": "< 5%/tháng", "ltv_cac": "> 3:1"},
            "scale": {"mrr": "> 500 triệu VND", "churn": "< 2%/tháng", "ltv_cac": "> 5:1"},
        },
        unit_economics={
            "ltv_formula": "ARPU / Churn Rate",
            "cac_formula": "Total Sales & Marketing spend / New customers acquired",
            "magic_number": "Net New ARR / S&M Spend (> 0.75 là efficient)",
        },
        growth_levers=[
            "Product-led growth: Free tier → viral loop → paid conversion",
            "Content marketing + SEO: Compound, thấp CAC dài hạn",
            "Integration & partnerships: Distribution qua ecosystem của sản phẩm khác",
            "Community building: Users dạy users → giảm support cost, tăng retention",
            "Customer success: Proactive onboarding giảm churn, tăng expansion",
            "Referral program: B2B word-of-mouth có conversion rate cao nhất",
        ],
        channel_priority=[
            "SEO / Content Marketing (compound, low CAC dài hạn)",
            "Product Hunt / AppSumo (launch burst, early adopters)",
            "LinkedIn Ads (B2B targeting chính xác)",
            "Google Ads — intent keywords (người đang search solution)",
            "YouTube / TikTok tutorials (educate + convert)",
            "Partner/Integration marketplace",
        ],
        tam_methodology="Top-down: Tổng thị trường phần mềm phân khúc × % có thể tiếp cận. Bottom-up: Số ICP companies/users × ARPU × 12",
        context_note="SaaS là ngành mà retention quan trọng hơn acquisition — churn cao sẽ giết growth dù acquisition tốt. Tập trung activation (aha-moment trong 7 ngày đầu) trước khi scale paid acquisition. LTV:CAC là chỉ số kinh tế đơn vị quan trọng nhất.",
    ),

    # ─────────────────────────────────────────────────────────────────
    # E-commerce / Thương mại điện tử
    # ─────────────────────────────────────────────────────────────────
    "ecommerce": KPIFramework(
        industry="ecommerce",
        display_name="E-commerce / Thương mại điện tử",
        primary_kpis=[
            {"name": "Return on Ad Spend (ROAS)", "formula": "Doanh thu từ ads / Chi phí ads", "target": "> 3x (Shopee), > 4x (Meta/TikTok)"},
            {"name": "Repeat Purchase Rate", "formula": "Khách mua ≥ 2 lần / Tổng khách", "target": "> 25% trong 90 ngày"},
            {"name": "Cart Abandonment Rate", "formula": "Giỏ hàng bị bỏ / Tổng giỏ hàng tạo", "target": "< 70%"},
            {"name": "Average Order Value (AOV)", "formula": "Doanh thu / Số đơn hàng", "target": "Tăng 20%+ qua bundle/upsell"},
            {"name": "Return Rate", "formula": "Đơn hoàn hàng / Tổng đơn", "target": "< 5% (fashion < 15%)"},
            {"name": "Gross Merchandise Value (GMV)", "formula": "Tổng giá trị hàng bán ra", "target": "MoM growth > 20% ở giai đoạn growth"},
        ],
        secondary_kpis=[
            {"name": "Customer Acquisition Cost (CAC)", "formula": "Marketing spend / New customers", "target": "< 0.5 lần AOV"},
            {"name": "Conversion Rate (CVR)", "formula": "Đơn hàng / Lượt xem sản phẩm", "target": "> 2% (Shopee), > 1% (website)"},
            {"name": "Revenue per Visitor (RPV)", "formula": "Doanh thu / Số lượt visit", "target": "Benchmark theo category"},
            {"name": "Seller Rating", "formula": "Average star rating", "target": "> 4.7 trên Shopee/Lazada"},
            {"name": "Inventory Turnover", "formula": "COGS / Avg Inventory", "target": "> 6x/năm"},
        ],
        vanity_kpis=[
            {"name": "Shop followers", "why": "Không predict purchase intent"},
            {"name": "Wishlist count", "why": "High wishlist ≠ high conversion"},
            {"name": "Livestream viewers", "why": "Measure conversion rate, không phải viewer"},
        ],
        benchmarks={
            "mvp": {"monthly_gmv": "< 200 triệu VND", "roas": "> 2x chấp nhận được"},
            "growth": {"monthly_gmv": "200 triệu - 2 tỷ VND", "roas": "> 3.5x", "repeat_rate": "> 20%"},
            "scale": {"monthly_gmv": "> 2 tỷ VND", "roas": "> 4x", "repeat_rate": "> 35%"},
        },
        unit_economics={
            "ltv_formula": "AOV × Purchase frequency/year × Customer lifespan",
            "contribution_margin": "Revenue - COGS - Shipping - Platform fee - Ad spend",
            "blended_roas": "Total Revenue / Total Marketing Spend (quan trọng hơn channel ROAS)",
        },
        growth_levers=[
            "Tăng AOV: Bundle, cross-sell, minimum order free ship",
            "Tăng repeat purchase: Post-purchase flow, loyalty points, email/Zalo remarketing",
            "Tối ưu listing: Ảnh, video, review → tăng CVR không tốn thêm ad spend",
            "Flash sale & campaign: 11/11, 12/12, Brand Day",
            "Affiliate / KOC: Performance-based, low risk",
            "Livestream: TikTok Shop, Shopee Live — conversion rate cao nhất hiện tại",
        ],
        channel_priority=[
            "Shopee / TikTok Shop (volume + built-in traffic)",
            "TikTok Ads + Livestream (highest conversion rate hiện tại)",
            "Meta Ads (retargeting + lookalike)",
            "Zalo OA (CRM, remarketing cost-effective)",
            "Google Shopping (intent-based)",
            "KOC / Affiliate network",
        ],
        tam_methodology="Category approach: Tổng GMV category trên Shopee/Lazada × market share có thể đạt",
        context_note="E-commerce cạnh tranh bằng giá + tốc độ + trải nghiệm sau mua. Đừng chỉ tối ưu ROAS từng kênh riêng lẻ — nhìn blended ROAS và LTV. Repeat purchase là profit thật sự, acquisition chỉ là chi phí.",
    ),

    # ─────────────────────────────────────────────────────────────────
    # Education / Coaching / Online Course / Training
    # ─────────────────────────────────────────────────────────────────
    "education": KPIFramework(
        industry="education",
        display_name="Giáo dục / Coaching / Khóa học",
        primary_kpis=[
            {"name": "Enrollment Rate", "formula": "Học viên đăng ký / Lead tiếp cận", "target": "> 10% (online), > 20% (tư vấn trực tiếp)"},
            {"name": "Course Completion Rate", "formula": "Học viên hoàn thành / Tổng đăng ký", "target": "> 60% (live), > 30% (self-paced)"},
            {"name": "Referral Rate", "formula": "Học viên giới thiệu người khác / Tổng học viên", "target": "> 20%"},
            {"name": "Net Promoter Score (NPS)", "formula": "% Promoters - % Detractors", "target": "> 60"},
            {"name": "Revenue per Lead", "formula": "Doanh thu / Tổng leads", "target": "Benchmark theo price point"},
            {"name": "Alumni Upsell Rate", "formula": "Học viên mua khóa tiếp / Tổng alumni", "target": "> 30%"},
        ],
        secondary_kpis=[
            {"name": "Cost per Lead (CPL)", "formula": "Ad spend / Số leads", "target": "< 10% course price"},
            {"name": "Show-up Rate (Webinar/Demo)", "formula": "Người tham dự / Đăng ký", "target": "> 40%"},
            {"name": "Sales Call Conversion", "formula": "Chốt / Số cuộc gọi", "target": "> 25%"},
            {"name": "Content-to-Lead Rate", "formula": "Leads từ content / Tổng views", "target": "Benchmark theo niche"},
            {"name": "Lifetime Value per Student", "formula": "Revenue từ 1 học viên suốt vòng đời", "target": "LTV > 3x khóa đầu tiên"},
        ],
        vanity_kpis=[
            {"name": "Số người theo dõi fanpage", "why": "Follower không đăng ký khóa học"},
            {"name": "Video views", "why": "Views không = enrollment"},
            {"name": "Webinar registrations", "why": "Chỉ ý nghĩa khi kèm show-up rate"},
        ],
        benchmarks={
            "mvp": {"monthly_revenue": "< 100 triệu VND", "completion_rate": "> 40%"},
            "growth": {"monthly_revenue": "100-500 triệu VND", "nps": "> 50", "referral_rate": "> 15%"},
            "scale": {"monthly_revenue": "> 500 triệu VND", "alumni_upsell": "> 35%"},
        },
        unit_economics={
            "ltv_formula": "Avg revenue per student × Number of courses × Referral multiplier",
            "cpl_to_enrollment": "CPL / Enrollment rate = Cost per enrolled student",
            "cohort_value": "Revenue từ cohort / Số học viên trong cohort",
        },
        growth_levers=[
            "Outcome marketing: Testimonial kết quả cụ thể (lương tăng X%, việc làm Y)",
            "Webinar funnel: Free value → trust → enroll",
            "Alumni community: Mạng lưới alumni là moat cạnh tranh mạnh nhất",
            "Content authority: YouTube/TikTok dạy miễn phí → convert vào premium",
            "Partnership: Công ty trả học phí cho nhân viên (B2B2C)",
            "Installment / Study-now-pay-later: Giảm barrier to entry",
        ],
        channel_priority=[
            "YouTube (authority building, compound)",
            "Facebook Ads (lead gen, webinar traffic)",
            "TikTok (reach rộng, đặc biệt 18-30 tuổi)",
            "Email marketing (nurture leads, upsell alumni)",
            "LinkedIn (B2B, corporate training)",
            "Referral program (highest quality leads)",
        ],
        tam_methodology="Số người trong target demographic × % quan tâm chủ đề × % sẵn trả tiền học online",
        context_note="Education mua bằng niềm tin và kết quả kỳ vọng — social proof (testimonial + outcome) là conversion lever mạnh nhất. Completion rate phản ánh product quality; NPS cao thì referral tự nhiên tăng. Alumni network là growth engine dài hạn.",
    ),

    # ─────────────────────────────────────────────────────────────────
    # Health & Beauty / Spa / Clinic / Thẩm mỹ
    # ─────────────────────────────────────────────────────────────────
    "health_beauty": KPIFramework(
        industry="health_beauty",
        display_name="Sức khỏe & Làm đẹp / Spa / Clinic",
        primary_kpis=[
            {"name": "Repeat Client Rate", "formula": "Khách quay lại / Tổng khách", "target": "> 50% trong 60 ngày"},
            {"name": "Average Revenue per Visit", "formula": "Doanh thu / Số lượt khách", "target": "Tăng qua upsell treatment"},
            {"name": "Booking Utilization Rate", "formula": "Slot đã book / Tổng slot available", "target": "> 75%"},
            {"name": "Treatment Package Uptake", "formula": "Khách mua package / Tổng khách mới", "target": "> 40%"},
            {"name": "Google & Zalo Rating", "formula": "Rating ≥ 4.5 + review volume", "target": "Cần cả hai"},
            {"name": "Referral Rate", "formula": "Khách từ giới thiệu / Tổng khách mới", "target": "> 30%"},
        ],
        secondary_kpis=[
            {"name": "No-show Rate", "formula": "Lịch hẹn bị bỏ / Tổng lịch hẹn", "target": "< 10%"},
            {"name": "Retail Product Revenue %", "formula": "Doanh thu retail / Tổng doanh thu", "target": "> 15% (high margin)"},
            {"name": "Staff Utilization Rate", "formula": "Giờ làm việc tạo revenue / Tổng giờ làm", "target": "> 70%"},
            {"name": "Customer Acquisition Cost", "formula": "Marketing spend / Khách mới", "target": "< 1 lần avg visit value"},
            {"name": "Membership Conversion Rate", "formula": "Members / Tổng khách active", "target": "> 20%"},
        ],
        vanity_kpis=[
            {"name": "Instagram followers", "why": "Beauty content viral không = booking"},
            {"name": "TikTok views", "why": "Cần track từ view → DM → booking"},
            {"name": "Reach của bài quảng cáo", "why": "Đo số booking, không đo reach"},
        ],
        benchmarks={
            "mvp": {"monthly_revenue": "50-200 triệu VND", "repeat_rate": "> 35%"},
            "growth": {"monthly_revenue": "200 triệu - 1 tỷ VND", "repeat_rate": "> 50%", "referral_rate": "> 25%"},
            "scale": {"monthly_revenue": "> 1 tỷ VND", "booking_utilization": "> 80%"},
        },
        unit_economics={
            "ltv_formula": "Avg revenue per visit × Avg visits/year × Customer lifespan",
            "cac_recovery": "CAC / (Avg visit value × Gross margin %)",
            "package_value": "Package price × Gross margin % — đây là real profit driver",
        },
        growth_levers=[
            "Before/After content: TikTok & Instagram — cực kỳ viral trong ngành beauty",
            "Package deal: Commit nhiều session trả trước → cash flow + retention",
            "Referral program: Đưa bạn đến được giảm giá cho cả 2",
            "Membership tier: Bronze/Silver/Gold → loyalty + predictable revenue",
            "Corporate wellness: B2B với công ty, trả theo nhóm",
            "Đào tạo + chứng chỉ: Authority positioning, attract premium clients",
        ],
        channel_priority=[
            "TikTok Before/After content (viral, high intent)",
            "Google Maps (người search 'spa gần tôi')",
            "Instagram (portfolio, aesthetic, DM booking)",
            "Facebook Ads (remarketing, local targeting)",
            "Zalo OA (CRM, nhắc lịch, promotion)",
            "KOL/KOC beauty (trust transfer)",
        ],
        tam_methodology="Dân số target demographic trong bán kính × Spending on beauty/health per year × Market share có thể đạt",
        context_note="Health & Beauty là ngành trust-based — khách hàng mua bằng sự tin tưởng vào người thực hiện dịch vụ, không phải thương hiệu. Before/after results và testimonial là công cụ marketing mạnh nhất. Repeat rate và referral rate là hai chỉ số sống còn.",
    ),

    # ─────────────────────────────────────────────────────────────────
    # Retail / Bán lẻ offline / Chuỗi cửa hàng
    # ─────────────────────────────────────────────────────────────────
    "retail": KPIFramework(
        industry="retail",
        display_name="Bán lẻ / Chuỗi cửa hàng",
        primary_kpis=[
            {"name": "Same-store Sales Growth", "formula": "Revenue store hiện tại YoY", "target": "> 15% YoY"},
            {"name": "Conversion Rate (Store)", "formula": "Người mua / Người vào cửa hàng", "target": "> 30%"},
            {"name": "Average Transaction Value (ATV)", "formula": "Doanh thu / Số giao dịch", "target": "Tăng qua cross-sell"},
            {"name": "Gross Margin %", "formula": "(Revenue - COGS) / Revenue", "target": "> 40% (fashion), > 25% (FMCG)"},
            {"name": "Inventory Turnover", "formula": "COGS / Avg Inventory value", "target": "> 4x/năm"},
            {"name": "Revenue per Square Meter", "formula": "Doanh thu / Diện tích", "target": "Benchmark theo location tier"},
        ],
        secondary_kpis=[
            {"name": "Foot Traffic", "formula": "Số người vào cửa hàng / ngày", "target": "Tăng through marketing"},
            {"name": "Customer Loyalty Rate", "formula": "Khách có thẻ thành viên / Tổng khách", "target": "> 40%"},
            {"name": "Stock-out Rate", "formula": "SKU hết hàng / Tổng SKU", "target": "< 5%"},
            {"name": "Shrinkage Rate", "formula": "Hàng thất thoát / Tổng hàng nhập", "target": "< 1%"},
            {"name": "Units per Transaction (UPT)", "formula": "Tổng items / Tổng giao dịch", "target": "> 2.5"},
        ],
        vanity_kpis=[
            {"name": "Social media followers", "why": "Không drive foot traffic trực tiếp"},
            {"name": "Brand awareness score", "why": "Trừ khi đo được correlation với foot traffic"},
        ],
        benchmarks={
            "mvp": {"monthly_revenue": "100-500 triệu VND", "gross_margin": "> 30%"},
            "growth": {"monthly_revenue": "500 triệu - 5 tỷ VND", "conversion_rate": "> 25%"},
            "scale": {"monthly_revenue": "> 5 tỷ VND", "same_store_growth": "> 10% YoY"},
        },
        unit_economics={
            "four_wall_ebitda": "Revenue - COGS - Direct labor - Rent - Utilities",
            "payback_per_store": "Store setup cost / Monthly four-wall EBITDA",
            "ltv_formula": "ATV × Purchase frequency × Customer lifespan",
        },
        growth_levers=[
            "Loyalty program: Points, tiers, birthday rewards",
            "Omnichannel: Online đặt, offline lấy (O2O)",
            "Visual merchandising: Tăng conversion và UPT không tốn marketing budget",
            "Staff training: Upsell và cross-sell skills",
            "Hyper-local marketing: Leaflet, OOH trong bán kính 2km",
            "New store openings: Tận dụng brand recognition",
        ],
        channel_priority=[
            "Google Maps / Local SEO",
            "Facebook Ads (địa lý targeting hẹp)",
            "Zalo OA (thành viên thân thiết)",
            "In-store promotion (đã có khách — upsell ngay)",
            "OOH / Signage (brand visibility local)",
            "Influencer local",
        ],
        tam_methodology="Số hộ gia đình trong catchment area × Spending per category × Market share",
        context_note="Retail cạnh tranh bằng location, product mix, và trải nghiệm mua sắm. Online và offline phải bổ trợ nhau, không cạnh tranh. Quản lý tồn kho và margin quan trọng hơn marketing budget — đừng marketing một business có gross margin thấp.",
    ),

    # ─────────────────────────────────────────────────────────────────
    # B2B Services / Agency / Tư vấn / Outsourcing
    # ─────────────────────────────────────────────────────────────────
    "b2b_service": KPIFramework(
        industry="b2b_service",
        display_name="B2B Services / Agency / Tư vấn",
        primary_kpis=[
            {"name": "Monthly Recurring Revenue (MRR)", "formula": "Retainer contracts × Monthly value", "target": "Tỷ lệ retainer > 60% total revenue"},
            {"name": "Client Retention Rate", "formula": "Clients còn lại / Tổng clients", "target": "> 85%/năm"},
            {"name": "Revenue per Employee", "formula": "Total revenue / Headcount", "target": "> 150 triệu VND/người/năm"},
            {"name": "Net Revenue Retention", "formula": "(Start MRR + Expansion - Churn) / Start MRR", "target": "> 110%"},
            {"name": "Gross Margin %", "formula": "(Revenue - Direct delivery cost) / Revenue", "target": "> 50% (agency), > 60% (consulting)"},
            {"name": "Win Rate", "formula": "Proposals won / Proposals sent", "target": "> 30%"},
        ],
        secondary_kpis=[
            {"name": "Sales Cycle Length", "formula": "Ngày từ lead → close", "target": "< 30 ngày (SME), < 90 ngày (enterprise)"},
            {"name": "Referral Rate", "formula": "New clients từ giới thiệu / Tổng new clients", "target": "> 40%"},
            {"name": "Average Contract Value (ACV)", "formula": "Total contract value / Số hợp đồng", "target": "Tăng dần qua upsell"},
            {"name": "Utilization Rate", "formula": "Billable hours / Total hours", "target": "> 70%"},
            {"name": "Net Promoter Score (NPS)", "formula": "% Promoters - % Detractors", "target": "> 50"},
        ],
        vanity_kpis=[
            {"name": "LinkedIn followers", "why": "B2B mua qua mối quan hệ, không qua follower"},
            {"name": "Số awards / giải thưởng ngành", "why": "Tốt cho PR nhưng không drive revenue"},
            {"name": "Website traffic", "why": "Trừ khi B2B có inbound funnel rõ ràng"},
        ],
        benchmarks={
            "mvp": {"monthly_revenue": "50-200 triệu VND", "clients": "3-10 clients"},
            "growth": {"monthly_revenue": "200 triệu - 2 tỷ VND", "retention": "> 80%"},
            "scale": {"monthly_revenue": "> 2 tỷ VND", "mrr_ratio": "> 60%", "nrr": "> 110%"},
        },
        unit_economics={
            "ltv_formula": "ACV × Avg client lifespan (years)",
            "cac_formula": "Sales & marketing cost / New clients",
            "efficiency_ratio": "Revenue / (Salaries + Overhead) — target > 2x",
        },
        growth_levers=[
            "Case studies & referrals: Kết quả cụ thể cho khách hàng → referral tự nhiên",
            "Thought leadership: Content/speaking giúp inbound leads chất lượng cao",
            "Productize services: Đóng gói service thành package cố định → scalable hơn",
            "Upsell existing clients: Rẻ hơn 5-7x so với acquire client mới",
            "Strategic partnerships: Agency bổ sung nhau (design + dev + marketing)",
            "Niche specialization: Leader trong một niche > generalist mọi thứ",
        ],
        channel_priority=[
            "Referral network (priority #1 trong B2B)",
            "LinkedIn (content + outreach)",
            "Speaking / Events ngành",
            "Case study content (SEO + trust)",
            "Cold outreach (personalized, không spam)",
            "Partner ecosystem",
        ],
        tam_methodology="Số doanh nghiệp trong target segment × % cần dịch vụ × Average contract value",
        context_note="B2B service bán bằng trust và track record. Referral là kênh acquisition hiệu quả nhất — đầu tư vào client success trước, marketing sau. Retainer revenue là nền tảng — project revenue là biến động, nguy hiểm nếu phụ thuộc quá nhiều.",
    ),

    # ─────────────────────────────────────────────────────────────────
    # Real Estate / Bất động sản
    # ─────────────────────────────────────────────────────────────────
    "real_estate": KPIFramework(
        industry="real_estate",
        display_name="Bất động sản",
        primary_kpis=[
            {"name": "Lead-to-Viewing Rate", "formula": "Số lượt xem thực tế / Tổng leads", "target": "> 20%"},
            {"name": "Viewing-to-Offer Rate", "formula": "Số offer / Số lượt xem", "target": "> 15%"},
            {"name": "Cost per Qualified Lead (CPQL)", "formula": "Ad spend / Qualified leads", "target": "< 500k VND/lead (tùy phân khúc)"},
            {"name": "Sales Cycle Length", "formula": "Ngày từ lead → ký HĐ", "target": "< 30 ngày (mass-market), < 90 ngày (premium)"},
            {"name": "Transaction Volume", "formula": "Số giao dịch thành công / tháng", "target": "Tăng dần theo team size"},
            {"name": "Revenue per Agent", "formula": "Total commission / Số agent", "target": "Benchmark theo phân khúc"},
        ],
        secondary_kpis=[
            {"name": "Lead Response Time", "formula": "Thời gian từ lead → gọi lại", "target": "< 5 phút (critical!)"},
            {"name": "Referral Transaction Rate", "formula": "Giao dịch từ giới thiệu / Tổng giao dịch", "target": "> 25%"},
            {"name": "Online Listing CTR", "formula": "Clicks / Impressions trên listing site", "target": "> 3%"},
            {"name": "Brand Search Volume", "formula": "Search volume của tên brand/dự án", "target": "Tăng MoM"},
        ],
        vanity_kpis=[
            {"name": "Tổng leads (không qualified)", "why": "Lead rác giết năng suất sales team"},
            {"name": "Facebook reach", "why": "Chỉ ý nghĩa khi convert thành qualified leads"},
        ],
        benchmarks={
            "mvp": {"monthly_transactions": "2-5 giao dịch", "cpql": "< 1 triệu VND"},
            "growth": {"monthly_transactions": "5-20 giao dịch", "referral_rate": "> 20%"},
            "scale": {"monthly_transactions": "> 20 giao dịch", "revenue_per_agent": "> 50 triệu VND/tháng"},
        },
        unit_economics={
            "revenue_formula": "Transaction value × Commission rate %",
            "cost_per_transaction": "Total marketing + sales cost / Number of transactions",
            "agent_roi": "Commission earned by agent / (Salary + Lead cost allocated)",
        },
        growth_levers=[
            "Lead qualification system: Lọc leads ngay từ đầu để sales tập trung đúng chỗ",
            "Video tour & 3D walkthrough: Tăng viewing-to-offer rate",
            "Referral từ khách cũ: Happy buyers = best salespeople",
            "Local community trust: Zalo group khu vực, hội nhóm địa phương",
            "Content: Giáo dục thị trường (pháp lý, tài chính, quy hoạch)",
            "Bank partnership: Kết nối vay vốn → giảm barrier to purchase",
        ],
        channel_priority=[
            "Facebook Ads (lead gen form — hiệu quả nhất VN hiện tại)",
            "Batdongsan.com.vn / Nha.vn (intent-based)",
            "YouTube (project showcase, area review)",
            "Zalo OA + local groups",
            "Google Ads (brand + location keywords)",
            "Referral network của môi giới",
        ],
        tam_methodology="Số giao dịch BĐS trong khu vực × Avg transaction value × Commission rate",
        context_note="BĐS là giao dịch high-consideration, high-trust — khách có thể research 3-12 tháng trước khi mua. Lead response time < 5 phút là yếu tố sống còn. Qualified lead quan trọng hơn số lượng lead. Referral từ khách mua thành công là channel chất lượng nhất.",
    ),
}


def get_kpi_framework(industry: str) -> Optional[KPIFramework]:
    """Return KPI framework for a given industry key."""
    return KPI_LIBRARY.get(industry)


def get_framework_as_text(industry: str) -> str:
    """Format KPI framework as readable text for injection into agent prompts."""
    fw = get_kpi_framework(industry)
    if not fw:
        return "Ngành chưa được định nghĩa — sử dụng framework chung."

    lines = [
        f"## KPI Framework: {fw.display_name}",
        "",
        "### KPIs Cốt Lõi (BẮT BUỘC theo dõi):",
    ]
    for kpi in fw.primary_kpis:
        lines.append(f"- **{kpi['name']}**: {kpi['formula']} → Target: {kpi['target']}")

    lines += ["", "### KPIs Quan Trọng:"]
    for kpi in fw.secondary_kpis:
        lines.append(f"- **{kpi['name']}**: {kpi['formula']} → Target: {kpi['target']}")

    lines += ["", "### KPIs Nên Tránh (Vanity Metrics):"]
    for kpi in fw.vanity_kpis:
        lines.append(f"- ~~{kpi['name']}~~: {kpi['why']}")

    lines += ["", "### Đòn Bẩy Tăng Trưởng Chính:"]
    for lever in fw.growth_levers:
        lines.append(f"- {lever}")

    lines += ["", "### Kênh Marketing Ưu Tiên:"]
    for i, channel in enumerate(fw.channel_priority, 1):
        lines.append(f"{i}. {channel}")

    lines += [
        "",
        f"### Lưu ý đặc thù ngành:",
        fw.context_note,
    ]

    return "\n".join(lines)


def list_industries() -> list[str]:
    return list(KPI_LIBRARY.keys())
