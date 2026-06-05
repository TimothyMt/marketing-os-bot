"""
Industry Context — lớp bổ sung cho kpi_library, phục vụ McKinsey Discovery.

kpi_library.py đã có: KPI + benchmark + growth_levers + channel_priority + TAM.
Module này thêm 3 lớp mà Discovery cần:

  market_dynamics  — cấu trúc thị trường VN: mùa vụ, margin, mật độ cạnh tranh,
                     đặc thù regulatory/platform. CMO dùng để định khung chiến lược.
  buyer_triggers   — vì sao khách MUA + rào cản KHÔNG mua (objections). McKinsey
                     dùng để dựng hypotheses, CMO dùng cho positioning + content.
  search_keywords  — seed query (tiếng Việt) cho grounded web search: TAM, đối thủ,
                     trend. Phase 2 router nạp vào Gemini Grounded.

Thiết kế "8 ngành cùng sâu" — mọi ngành đều có đủ 3 lớp.
"""
from dataclasses import dataclass
from typing import Optional

from frameworks.kpi_library import (
    get_framework_as_text,
    get_kpi_framework,
    list_industries as _kpi_industries,
)


@dataclass
class IndustryContext:
    industry: str
    market_dynamics: str       # cấu trúc thị trường VN — mùa vụ, margin, cạnh tranh
    buyer_triggers: list[str]  # lý do mua
    buyer_barriers: list[str]  # rào cản không mua (objections)
    search_keywords: dict      # {"tam": [...], "competitor": [...], "trend": [...]}


INDUSTRY_CONTEXT: dict[str, IndustryContext] = {

    # ─────────────────────────────────────────────────────────────────
    "fnb": IndustryContext(
        industry="fnb",
        market_dynamics=(
            "Hyperlocal — 90% doanh thu đến từ khách trong bán kính 1-5km. Margin gộp "
            "60-70% nhưng net mỏng (10-15%) vì rent + nhân sự + COGS. Mùa vụ rõ: Tết "
            "(âm lịch) tăng đột biến, tháng 7 âm (Ngâu) giảm, mùa mưa miền Nam ảnh hưởng "
            "dine-in. Cạnh tranh cực gắt, rào cản gia nhập thấp → vòng đời quán trung bình "
            "12-24 tháng. Platform delivery (GrabFood/ShopeeFood) ăn 20-30% commission, "
            "nguy hiểm nếu phụ thuộc. Google Maps + review là chiến trường acquisition chính."
        ),
        buyer_triggers=[
            "Tiện đường / gần (location convenience)",
            "Review + ảnh đẹp trên Google Maps / TikTok (social proof)",
            "Bạn bè rủ / được giới thiệu (word-of-mouth)",
            "Combo/khuyến mãi hợp lý với giá trị nhận được",
            "Không gian phù hợp dịp (hẹn hò, làm việc, tụ tập)",
        ],
        buyer_barriers=[
            "Sợ dở / không hợp khẩu vị (rủi ro lần đầu)",
            "Giá cao hơn kỳ vọng so với phân khúc",
            "Chỗ đậu xe khó, xa",
            "Review xấu gần đây / vệ sinh đáng ngờ",
        ],
        search_keywords={
            "tam": ["quy mô thị trường F&B Việt Nam", "chi tiêu ăn uống ngoài hàng người Việt", "số lượng quán cà phê TP.HCM"],
            "competitor": ["quán {sản phẩm} {khu vực} review", "top quán {sản phẩm} nổi tiếng {thành phố}"],
            "trend": ["xu hướng F&B Việt Nam 2026", "món ăn trend TikTok", "concept quán cà phê hot"],
        },
    ),

    # ─────────────────────────────────────────────────────────────────
    "tech_saas": IndustryContext(
        industry="tech_saas",
        market_dynamics=(
            "Kinh tế đơn vị quyết định tất cả — churn cao giết growth dù acquisition tốt. "
            "Margin gộp 70-85% (gần như software thuần). Sales cycle B2C ngắn (self-serve), "
            "B2B dài 1-3 tháng. Thị trường VN còn non: khách quen 'mua đứt' hơn 'thuê bao', "
            "phải educate mô hình subscription. Cạnh tranh không chỉ nội địa mà cả global "
            "SaaS (Notion, Slack...). Đòn bẩy là product-led growth + content compound. "
            "CAC payback và LTV:CAC là hai số sống còn — đốt tiền acquisition mà churn cao = chết."
        ),
        buyer_triggers=[
            "Giải quyết pain cụ thể đang nhức (time-saving / cost-saving rõ ràng)",
            "Free trial / freemium để thử trước khi cam kết",
            "Case study + ROI chứng minh được",
            "Onboarding mượt, đạt aha-moment nhanh",
            "Integration với tool đang dùng",
        ],
        buyer_barriers=[
            "Ngại đổi quy trình / chi phí chuyển đổi (switching cost)",
            "Không rõ ROI, khó justify ngân sách",
            "Lo bảo mật dữ liệu / nhà cung cấp nhỏ biến mất",
            "Quen freebie, ngại trả phí định kỳ (đặc thù VN)",
        ],
        search_keywords={
            "tam": ["quy mô thị trường SaaS Việt Nam", "số doanh nghiệp SME Việt Nam", "chi tiêu phần mềm doanh nghiệp VN"],
            "competitor": ["phần mềm {chức năng} cho doanh nghiệp Việt", "{đối thủ} vs alternatives review"],
            "trend": ["xu hướng SaaS B2B 2026", "AI tools doanh nghiệp Việt Nam", "chuyển đổi số SME"],
        },
    ),

    # ─────────────────────────────────────────────────────────────────
    "ecommerce": IndustryContext(
        industry="ecommerce",
        market_dynamics=(
            "Sân chơi của Shopee/TikTok Shop/Lazada — traffic built-in nhưng commission "
            "5-15% + phí ads ăn margin. Blended ROAS quan trọng hơn ROAS từng kênh. "
            "Mega-sale (11/11, 12/12, Tết) chiếm tỷ trọng doanh thu lớn → dòng tiền dồn cục. "
            "TikTok Shop + livestream đang là conversion engine mạnh nhất 2025-2026. "
            "Cạnh tranh về giá khốc liệt, dễ vào race-to-bottom. Repeat purchase mới là "
            "profit thật — acquisition lần đầu thường lỗ. Return rate (đặc biệt fashion) bào margin."
        ),
        buyer_triggers=[
            "Giá tốt + flash sale / mã giảm",
            "Review + số lượng đã bán (social proof định lượng)",
            "Livestream demo trực tiếp, chốt nóng",
            "Freeship / freeship extra",
            "KOC/KOL giới thiệu đáng tin",
        ],
        buyer_barriers=[
            "Sợ hàng không giống hình / kém chất lượng",
            "Phí ship cao so với giá trị đơn",
            "Shop mới, ít review, chưa tin",
            "Thời gian giao lâu",
        ],
        search_keywords={
            "tam": ["quy mô thương mại điện tử Việt Nam", "GMV Shopee TikTok Shop Việt Nam", "doanh số ngành hàng {category} sàn TMĐT"],
            "competitor": ["shop bán {sản phẩm} bán chạy Shopee", "thương hiệu {category} nổi bật TikTok Shop"],
            "trend": ["xu hướng TMĐT Việt Nam 2026", "ngành hàng tăng trưởng Shopee", "livestream commerce trend"],
        },
    ),

    # ─────────────────────────────────────────────────────────────────
    "education": IndustryContext(
        industry="education",
        market_dynamics=(
            "Mua bằng niềm tin + kết quả kỳ vọng → social proof (testimonial outcome) là "
            "đòn bẩy conversion mạnh nhất. Margin cao (60-80% với online course) nhưng "
            "completion rate phản ánh chất lượng và quyết định referral. Mùa vụ theo lịch "
            "học/tuyển sinh + đầu năm (resolution). Funnel điển hình: free content → webinar "
            "→ enroll. Alumni network là moat dài hạn. Cạnh tranh từ free content (YouTube) → "
            "phải chứng minh vì sao trả tiền. Phụ huynh (K-12) vs người học (skill) có hành vi khác hẳn."
        ),
        buyer_triggers=[
            "Testimonial kết quả cụ thể (tăng lương X%, có việc, đỗ trường)",
            "Free value trước (webinar, ebook) tạo trust",
            "Giảng viên có authority / track record",
            "Trả góp / học trước trả sau (giảm barrier)",
            "Cộng đồng học viên + hỗ trợ sau khóa",
        ],
        buyer_barriers=[
            "Sợ học xong không áp dụng được / không có kết quả",
            "Giá cao, chưa thấy ROI rõ",
            "Không có thời gian học (sợ bỏ dở)",
            "Nội dung có thể tự học free trên mạng",
        ],
        search_keywords={
            "tam": ["quy mô thị trường edtech Việt Nam", "chi tiêu giáo dục hộ gia đình Việt Nam", "số người học online Việt Nam"],
            "competitor": ["khóa học {chủ đề} tốt nhất Việt Nam", "{đối thủ} review học viên"],
            "trend": ["xu hướng học online 2026", "kỹ năng hot thị trường lao động Việt Nam", "edtech trend"],
        },
    ),

    # ─────────────────────────────────────────────────────────────────
    "health_beauty": IndustryContext(
        industry="health_beauty",
        market_dynamics=(
            "Trust-based và phụ thuộc người thực hiện hơn thương hiệu. Margin dịch vụ cao "
            "(60-75%), retail sản phẩm bổ sung margin. Before/after là vũ khí viral mạnh "
            "nhất (TikTok/Instagram). Package trả trước = cash flow + retention. Vấn đề "
            "regulatory ngày càng chặt (quảng cáo dịch vụ thẩm mỹ, y tế bị kiểm soát). "
            "No-show và booking utilization là hai killer vận hành. Khách cực nhạy với review "
            "tiêu cực vì liên quan cơ thể/sức khỏe. Repeat + referral là hai số sống còn."
        ),
        buyer_triggers=[
            "Before/after ấn tượng, chân thực",
            "Review + đánh giá cao (đặc biệt từ người giống mình)",
            "Được người quen giới thiệu (trust transfer)",
            "Combo/package giá trị, cam kết kết quả",
            "Chuyên môn / chứng chỉ của người thực hiện",
        ],
        buyer_barriers=[
            "Sợ rủi ro (hỏng da, biến chứng, không an toàn)",
            "Sợ bị chèo kéo upsell quá mức",
            "Giá cao, sợ không xứng đáng",
            "Review tiêu cực / tin đồn xấu",
        ],
        search_keywords={
            "tam": ["quy mô thị trường làm đẹp spa Việt Nam", "chi tiêu làm đẹp phụ nữ Việt", "số lượng spa thẩm mỹ viện {thành phố}"],
            "competitor": ["spa {dịch vụ} {khu vực} review", "thẩm mỹ viện uy tín {thành phố}"],
            "trend": ["xu hướng làm đẹp Việt Nam 2026", "dịch vụ spa hot TikTok", "công nghệ thẩm mỹ mới"],
        },
    ),

    # ─────────────────────────────────────────────────────────────────
    "retail": IndustryContext(
        industry="retail",
        market_dynamics=(
            "Cạnh tranh bằng location + product mix + trải nghiệm. Margin theo ngành hàng: "
            "fashion 40-60%, FMCG 15-25%. Quản tồn kho và margin quan trọng HƠN marketing — "
            "đừng marketing business margin thấp. O2O (online đặt, offline lấy) là xu hướng. "
            "Foot traffic giảm dần do TMĐT → phải cho lý do đến cửa hàng (trải nghiệm, tức thì). "
            "Same-store sales growth là thước đo sức khỏe thật. Mùa vụ mạnh: Tết, back-to-school, "
            "mega-sale. Loyalty program + visual merchandising tăng conversion không tốn ad budget."
        ),
        buyer_triggers=[
            "Cần ngay, không chờ ship được (instant gratification)",
            "Được xem/thử trực tiếp trước khi mua",
            "Khuyến mãi tại cửa hàng / loyalty rewards",
            "Vị trí tiện, trên đường di chuyển",
            "Trải nghiệm mua sắm + tư vấn tốt",
        ],
        buyer_barriers=[
            "Giá cao hơn online cùng sản phẩm",
            "Ngại di chuyển, đậu xe",
            "Sản phẩm hết size/màu (stock-out)",
            "Mua online tiện hơn",
        ],
        search_keywords={
            "tam": ["quy mô bán lẻ Việt Nam ngành {category}", "chi tiêu bán lẻ hộ gia đình Việt Nam", "số cửa hàng {ngành} {khu vực}"],
            "competitor": ["cửa hàng {sản phẩm} {khu vực}", "chuỗi bán lẻ {category} lớn Việt Nam"],
            "trend": ["xu hướng bán lẻ Việt Nam 2026", "O2O retail trend", "hành vi mua sắm offline"],
        },
    ),

    # ─────────────────────────────────────────────────────────────────
    "b2b_service": IndustryContext(
        industry="b2b_service",
        market_dynamics=(
            "Bán bằng trust + track record, referral là kênh #1. Margin agency 50%, "
            "consulting 60%+. Retainer revenue là nền tảng, project revenue biến động nguy hiểm. "
            "Sales cycle dài (SME <30 ngày, enterprise 90+). Quyết định mua nhiều người "
            "(decision-making unit) → cần thuyết phục nhiều stakeholder. Thị trường VN chuộng "
            "quan hệ cá nhân + giới thiệu hơn inbound lạnh. Productize service giúp scale. "
            "Niche leader > generalist. Client success trước, marketing sau."
        ),
        buyer_triggers=[
            "Case study + kết quả cụ thể cho khách tương tự",
            "Được đối tác/đồng nghiệp giới thiệu",
            "Thought leadership / chuyên môn được công nhận",
            "Proposal rõ ràng, cam kết deliverable + KPI",
            "Chemistry + tin tưởng người làm trực tiếp",
        ],
        buyer_barriers=[
            "Sợ chọn sai nhà cung cấp (rủi ro cao, khó đổi giữa chừng)",
            "Ngân sách cần nhiều người duyệt (long approval)",
            "Khó so sánh chất lượng giữa các agency",
            "Đã có nhà cung cấp cũ, ngại chuyển",
        ],
        search_keywords={
            "tam": ["quy mô thị trường dịch vụ {ngành} B2B Việt Nam", "số doanh nghiệp cần {dịch vụ} Việt Nam"],
            "competitor": ["agency {dịch vụ} hàng đầu Việt Nam", "công ty tư vấn {lĩnh vực} uy tín"],
            "trend": ["xu hướng outsourcing Việt Nam 2026", "nhu cầu {dịch vụ} doanh nghiệp", "B2B marketing trend"],
        },
    ),

    # ─────────────────────────────────────────────────────────────────
    "real_estate": IndustryContext(
        industry="real_estate",
        market_dynamics=(
            "Giao dịch high-consideration, high-trust — khách research 3-12 tháng. Lead "
            "response time <5 phút là sống còn (lead nguội cực nhanh). Qualified lead quan "
            "trọng hơn số lượng — lead rác giết năng suất sales. Commission-based, giá trị "
            "giao dịch lớn nên CPL cao vẫn hợp lý. Cực nhạy chu kỳ thị trường + chính sách "
            "(lãi suất, pháp lý, quy hoạch). Facebook lead form + batdongsan.com.vn là kênh "
            "chính. Referral từ khách mua thành công là nguồn chất lượng nhất. Trust về pháp lý "
            "+ tài chính (kết nối vay vốn) là đòn bẩy chốt deal."
        ),
        buyer_triggers=[
            "Pháp lý rõ ràng, minh bạch",
            "Vị trí + tiềm năng tăng giá / khai thác",
            "Hỗ trợ vay vốn, phương án tài chính khả thi",
            "Môi giới phản hồi nhanh, tư vấn đáng tin",
            "Video tour / xem thực tế thuyết phục",
        ],
        buyer_barriers=[
            "Sợ rủi ro pháp lý (sổ, tranh chấp, quy hoạch)",
            "Số tiền lớn, sợ quyết định sai",
            "Lo thị trường xuống giá / thanh khoản kém",
            "Không tin môi giới (định kiến ngành)",
        ],
        search_keywords={
            "tam": ["thị trường bất động sản {khu vực} 2026", "số giao dịch BĐS {phân khúc} Việt Nam", "giá bất động sản {khu vực}"],
            "competitor": ["dự án {phân khúc} {khu vực}", "sàn môi giới BĐS {khu vực} uy tín"],
            "trend": ["xu hướng bất động sản Việt Nam 2026", "phân khúc BĐS tăng trưởng", "chính sách BĐS mới"],
        },
    ),
}


def get_industry_context(industry: str) -> Optional[IndustryContext]:
    """Return industry context, hoặc None nếu chưa định nghĩa."""
    return INDUSTRY_CONTEXT.get(industry)


def get_industry_context_as_text(industry: str) -> str:
    """Format context (market dynamics + buyer psychology) cho prompt injection.

    KHÔNG bao gồm search_keywords (cái đó cho router, không cho prompt).
    Dùng cho Discovery/Strategy agents.
    """
    ctx = get_industry_context(industry)
    if not ctx:
        return ""

    lines = [
        "### Động lực thị trường (VN):",
        ctx.market_dynamics,
        "",
        "### Lý do khách MUA (triggers):",
    ]
    lines += [f"- {t}" for t in ctx.buyer_triggers]
    lines += ["", "### Rào cản khách KHÔNG mua (objections):"]
    lines += [f"- {b}" for b in ctx.buyer_barriers]
    return "\n".join(lines)


def get_full_industry_brief(industry: str) -> str:
    """Gộp KPI framework (kpi_library) + industry context thành 1 block đầy đủ.

    Đây là context tổng để inject vào McKinsey Discovery + CMO Strategy.
    """
    parts = [get_framework_as_text(industry)]
    ctx_text = get_industry_context_as_text(industry)
    if ctx_text:
        parts += ["", "## Bối Cảnh Ngành (Market Dynamics & Buyer Psychology)", "", ctx_text]
    return "\n".join(parts)


def suggest_key_message_hint(
    industry: str,
    product_service: str = "",
    target_customer: str = "",
) -> str:
    """Gợi ý cách viết 'thông điệp chính' cho video — dựa trên Business của user
    (product_service / target_customer) ghép với tâm lý mua của ngành (KPI library
    + industry_context).

    Ý tưởng: 'thông điệp chính' mạnh nhất là câu neo vào ĐÚNG lý do khách mua
    (buyer_triggers) hoặc hoá giải ĐÚNG nỗi lo lớn nhất (buyer_barriers) của ngành,
    nói về sản phẩm cụ thể của business — thay vì 1 câu chung chung.

    Trả về block text ngắn (markdown) hiện dưới field key_message trong form.
    Rỗng nếu ngành chưa được định nghĩa → form fallback về example tĩnh.
    """
    ctx = get_industry_context(industry)
    fw = get_kpi_framework(industry)
    if not ctx and not fw:
        return ""

    subject = (product_service or "").strip() or "sản phẩm/dịch vụ của sếp"
    who = (target_customer or "").strip()
    name = fw.display_name if fw else industry

    lines = [f"💡 *Gợi ý cho ngành {name}* — thông điệp khách nhớ nhất thường neo vào:"]

    # Lý do khách MUA (trigger) — khuếch đại điều khách KHAO KHÁT
    if ctx and ctx.buyer_triggers:
        t = ctx.buyer_triggers[0]
        lines.append(f"• Điều khách muốn nhất: _{t}_")
        lines.append(f"  → vd: \"{subject} — {t.split('(')[0].strip().rstrip('.').lower()}\"")

    # Nỗi lo cần GỠ (barrier) — hoá giải rào cản khiến khách chần chừ
    if ctx and ctx.buyer_barriers:
        b = ctx.buyer_barriers[0]
        lines.append(f"• Nỗi lo cần gỡ: _{b}_")
        lines.append(f"  → vd: \"Đừng để {b.split('(')[0].strip().rstrip('.').lower()} cản bạn — {subject} ...\"")

    if who:
        lines.append(f"_(Viết cho đúng tệp: {who})_")

    lines.append("Chọn 1 góc, ghép với sản phẩm thành 1 câu duy nhất khách nhớ.")
    return "\n".join(lines)


def get_search_seeds(industry: str) -> dict:
    """Trả về search keywords seed cho grounded search (Phase 2 router).

    Returns {"tam": [...], "competitor": [...], "trend": [...]}.
    Placeholder {sản phẩm}/{khu vực}/{thành phố} sẽ được fill từ profile.
    """
    ctx = get_industry_context(industry)
    return ctx.search_keywords if ctx else {}


def list_industries() -> list[str]:
    """Danh sách industry keys (đồng bộ với kpi_library)."""
    return list(INDUSTRY_CONTEXT.keys())


def coverage_check() -> dict:
    """Dev helper — verify mọi ngành trong kpi_library đều có context."""
    kpi = set(_kpi_industries())
    ctx = set(INDUSTRY_CONTEXT.keys())
    return {
        "kpi_only":  sorted(kpi - ctx),   # ngành thiếu context
        "ctx_only":  sorted(ctx - kpi),   # context thừa
        "covered":   sorted(kpi & ctx),
        "complete":  kpi == ctx,
    }
