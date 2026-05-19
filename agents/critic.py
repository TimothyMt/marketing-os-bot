"""
Critic Review Layer — Sonnet reviews agent output before sending to user.
Catches hallucinations: fabricated stats, internal contradictions, fake citations.
Post-processes to add hyperlinks for known VN data sources.
"""
import re
import logging
import anthropic

from config import CLAUDE_HAIKU_MODEL, ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _client


CRITIC_SYSTEM = """Bạn là Senior Marketing Analyst review output của AI advisor cho founder Việt Nam.

Nhiệm vụ: Đọc output dưới đây, PHÁT HIỆN và SỬA các vấn đề:

**1. Số liệu bịa / không hợp lý**
- Phát hiện số cụ thể (TAM, %, số khách, doanh thu, CAC, ROAS...) mà:
  + Không có nguồn rõ
  + Quá tròn (50000, 1 triệu) — dấu hiệu Claude bịa
  + Không hợp lý cho VN (vd: TAM ngành F&B "100 tỷ USD")
- → Sửa thành "ước tính dựa trên benchmark ngành" hoặc xóa nếu off-mark

**2. Mâu thuẫn nội bộ**
- Phát hiện 2 con số khác nhau cho cùng 1 thứ trong cùng output
- → Chọn version hợp lý nhất, sửa cho nhất quán

**3. Cite nguồn nghi ngờ**
- Nếu cite "Theo Statista 2024..." mà không có link cụ thể
- → Giữ tên nguồn (sẽ được post-process thêm hyperlink)
- Nếu cite nguồn không tồn tại (vd: "Báo cáo XYZ Vietnam 2025" mà tổ chức không có report đó)
- → Xóa cite, giữ insight nhưng đổi thành "industry estimate"

**4. Brand/người cụ thể**
- Phát hiện claim cụ thể về 1 brand (vd: "Cocoon có 50,000 customers", "M.O.I founded 2018")
- → Sửa thành phát biểu chung ("các brand local lớn") hoặc xóa con số cụ thể nếu nghi bịa

**QUY TẮC NGHIÊM:**
- KHÔNG rewrite toàn bộ output — chỉ sửa các vấn đề trên
- GIỮ NGUYÊN cấu trúc 4 sections: ## 💡 Insight, ## 🎯 Tóm tắt, ## 📊 Benchmarks, ## 📄 Phân tích chi tiết
- GIỮ NGUYÊN tone tiếng Việt + style viết
- KHÔNG thêm disclaimer thừa kiểu "lưu ý đây là ước tính" — chỉ sửa nội dung
- KHÔNG thêm comment giải thích — output trực tiếp version đã sửa
- GIỮ NGUYÊN tables, bullet lists, headings

Output: Toàn bộ text đã review/sửa, ready để gửi user."""


# Mapping nguồn data VN phổ biến → URL chính thức
# Critic giữ tên nguồn, post-process inject hyperlink
KNOWN_SOURCES: dict[str, str] = {
    "Statista":              "https://www.statista.com/markets/vietnam/",
    "GSO":                   "https://www.gso.gov.vn/en/",
    "Tổng cục Thống kê":     "https://www.gso.gov.vn/",
    "WorldBank":             "https://www.worldbank.org/en/country/vietnam",
    "World Bank":            "https://www.worldbank.org/en/country/vietnam",
    "Nielsen":               "https://www.nielsen.com/vn/",
    "Q&Me":                  "https://qandme.net/en/",
    "Decision Lab":          "https://www.decisionlab.co/",
    "Vietcetera":            "https://vietcetera.com/",
    "CafeF":                 "https://cafef.vn/",
    "VnEconomy":             "https://vneconomy.vn/",
    "Brands Vietnam":        "https://www.brandsvietnam.com/",
    "Advertising Vietnam":   "https://advertisingvietnam.com/",
    "iPrice":                "https://iprice.vn/insights/",
    "Cốc Cốc":               "https://coccoc.com/",
    "Adsota":                "https://adsota.com/",
    "Kantar":                "https://www.kantar.com/vi/",
}


def _add_hyperlinks(text: str) -> str:
    """Pattern match known VN sources, add Markdown hyperlinks if not already linked."""
    for source, url in KNOWN_SOURCES.items():
        # Match source name not already inside a Markdown link [text](url)
        # Negative lookbehind: not preceded by '['
        # Negative lookahead: not immediately followed by ']('
        # Only replace first occurrence per source to avoid spamming
        pattern = rf'(?<!\[){re.escape(source)}(?!\])'
        if re.search(pattern, text):
            text = re.sub(pattern, f'[{source}]({url})', text, count=1)
    return text


async def run_critic(agent_output: str, agent_name: str = "agent") -> str:
    """Run critic review on agent output, return reviewed text with hyperlinks."""
    if not agent_output or not agent_output.strip():
        return agent_output

    try:
        client = _get_client()
        response = await client.messages.create(
            model=CLAUDE_HAIKU_MODEL,
            max_tokens=5000,
            system=[
                {
                    "type": "text",
                    "text": CRITIC_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": agent_output}],
        )
        reviewed = response.content[0].text
        if not reviewed or not reviewed.strip():
            logger.warning("Critic returned empty for %s, falling back to original", agent_name)
            return agent_output

        # Post-process: add hyperlinks for known sources
        reviewed = _add_hyperlinks(reviewed)
        return reviewed
    except Exception as e:
        logger.warning("Critic failed for %s: %s — using original output", agent_name, e)
        return agent_output
