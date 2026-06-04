"""
Generate a sample content_calendar Excel showing the new per-channel format.
Runs through the real Excel renderer without needing LLM or Supabase.
"""
import sys, os, unittest.mock as mock

# Stub out DB/storage imports so renderer loads cleanly
for mod in ['supabase', 'asyncpg', 'storage', 'storage.session', 'storage.models',
            'storage.session_storage', 'agents', 'agents.skills', 'agents.pipeline',
            'agents.task_registry', 'config', 'frameworks', 'frameworks.kpi_library']:
    sys.modules[mod] = mock.MagicMock()

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot.renderers import render_excel_file, _extract_markdown_tables

# ── Enum stub ─────────────────────────────────────────────────────
class OutputFormat:
    OPERATIONAL_DELIVERABLE = "operational_deliverable"

# ── Realistic mock calendar — new per-channel format ────────────
MOCK_CALENDAR = """\
## Tổng quan kỳ

- **Theme/concept**: Xây dựng trust + chốt khách — Lotus Spa Q7 tháng 1/2026
- **Thời lượng**: 4 tuần — tháng 1/2026 (01/01 – 31/01)
- **Tổng số bài**: 24 (12 Facebook + 8 TikTok + 4 Zalo OA)
- **Pillar mix**: Educate 35% / Trust 30% / Engage 20% / Convert 15%

## Story Arc 4 Tuần

| Tuần | Theme | Funnel focus | Mục tiêu tuần | Audience chính |
|---|---|---|---|---|
| Tuần 1 — Awareness | Pain point chăm sóc da | TOFU | Nhận ra vấn đề | Mới |
| Tuần 2 — So sánh | Đông y vs skincare hiện đại | TOFU + MOFU | Thấy Lotus là option | Mới + Active |
| Tuần 3 — Proof | Testimonial + quy trình | MOFU | Tin tưởng brand | Active + Nguy cơ |
| Tuần 4 — Chốt | Deal Tết + urgency | BOFU | ACTION | Active + VIP |

## Pillar Breakdown

| Pillar | % | Số bài/kỳ | 3 angle chính | Framework ưu tiên |
|---|---|---|---|---|
| Educate | 35% | 8 | Kiến thức da; Đông y vs hiện đại; Mùa đông chăm da | PAS / Star-Story |
| Trust | 30% | 7 | Before/after thật; Review khách; Quy trình | BAB / AIDA |
| Engage | 20% | 5 | Poll; Q&A; Challenge | Star-Story / AIDA |
| Convert | 15% | 4 | Deal combo; Urgency; Booking | FAB / PAS |

## Weekly grid chi tiết — tách riêng theo kênh

#### 📘 Facebook — 12 bài/tháng

| Ngày | Pillar | Funnel | Nhóm khách | Format | Hook angle | Topic | Owner |
|---|---|---|---|---|---|---|---|
| 02/01 | Educate | TOFU | Mới | Bài viết dài | Tò mò | Da mùa đông cần gì khác ngày thường? | Content writer |
| 04/01 | Trust | TOFU | Mới | Carousel 5 ảnh | Thẩm quyền | 5 năm làm spa Đông y — điều em học được | Brand |
| 07/01 | Engage | TOFU | Mới | Poll + caption | Đồng cảm | Bạn đang gặp vấn đề da nào nhất? | Brand |
| 09/01 | Educate | MOFU | Mới + Active | Carousel tips | Trái ngược | Vì sao serum đắt tiền chưa chắc tốt hơn | Content writer |
| 12/01 | Trust | MOFU | Active | Before/after | Cảm xúc | Khách Lan Anh — 3 tháng điều trị nám | Brand |
| 14/01 | Educate | MOFU | Active | Bài viết | Thẩm quyền | Quy trình 5 bước tại Lotus Spa | Content writer |
| 16/01 | Engage | MOFU | Active + Nguy cơ | Q&A story | Đồng cảm | Liệu trình bao lâu mới thấy kết quả? | Brand |
| 19/01 | Trust | MOFU | Active | Video repost | Cảm xúc | Review tự nhiên của khách cũ | Brand |
| 21/01 | Convert | BOFU | Active | Deal post | Cảm xúc | Combo Tết 680K (gốc 850K) — còn 10 slot | Brand |
| 23/01 | Trust | BOFU | VIP | Exclusive post | Thẩm quyền | Khách VIP — ưu tiên đặt trước Tết | Brand |
| 26/01 | Convert | BOFU | Active | Urgency post | Tò mò | Còn 3 ngày — combo Tết còn 5 slot | Brand |
| 28/01 | Engage | BOFU | VIP + Active | Cảm ơn + CTA | Đồng cảm | Tổng kết tháng + lời cảm ơn khách | Brand |

#### 📱 TikTok — 8 video/tháng

| Ngày | Pillar | Funnel | Nhóm khách | Format | Hook angle | Topic | Kịch bản mở đầu | Owner |
|---|---|---|---|---|---|---|---|---|
| 03/01 | Educate | TOFU | Mới | Short video 45s | Tò mò | Vì sao da mùa đông hay bong tróc? | Bạn có biết 80% người dưỡng ẩm sai cách mùa đông không? | Founder |
| 06/01 | Trust | TOFU | Mới | Behind-the-scenes 30s | Đồng cảm | 1 ngày tại Lotus — không filter không dàn dựng | Đây là ngày bình thường tại spa của em. Không filter. Không dàn dựng. | Nhân viên |
| 10/01 | Educate | MOFU | Mới + Active | Tutorial 60s | Thẩm quyền | Đông y chăm da khác gì skincare thường? | 3 điều Đông y làm được mà serum 2 triệu không làm được — số 2 nhiều người không biết. | Founder |
| 13/01 | Trust | MOFU | Active | Before/after 30s | Cảm xúc | Hành trình 2 tháng của chị Mai | Đây là ảnh chị Mai gửi cho em trước khi đến — và đây là sau 2 tháng. | Brand |
| 17/01 | Engage | MOFU | Active | Q&A 45s | Trái ngược | Liệu trình spa có thực sự cần thiết không? | Em sẽ trả lời thật nhất có thể — kể cả khi câu trả lời là KHÔNG cần đến spa. | Founder |
| 20/01 | Trust | MOFU | Nguy cơ | Testimonial UGC 30s | Cảm xúc | Khách cũ quay lại sau 60 ngày | Chị Hoa nhắn em sau 60 ngày không quay lại — đây là lý do chị quay lại. | UGC (khách) |
| 24/01 | Convert | BOFU | Active | Offer video 30s | Tò mò | Combo Tết — tại sao 680K? | Em sẽ breakdown thật sự combo 680K này có gì — không phải để bán mà để sếp tự quyết. | Founder |
| 27/01 | Convert | BOFU | Active + VIP | Urgency 15s | Cảm xúc | Đếm ngược 3 ngày cuối | Còn đúng 3 ngày. 5 slot cuối. Em không nhận thêm sau 31/01. | Brand |

#### 💬 Zalo OA — 4 broadcast/tháng

| Ngày | Pillar | Funnel | Nhóm khách | Format | Hook angle | Topic | Owner |
|---|---|---|---|---|---|---|---|
| 05/01 | Educate | MOFU | Active | Tin nhắn ngắn | Thẩm quyền | Tips chăm da mùa đông — quà đầu năm | Brand |
| 12/01 | Trust | MOFU | Nguy cơ | Nhắc lịch | Đồng cảm | Lâu rồi chưa gặp — da sếp đang thế nào? | Brand |
| 20/01 | Convert | BOFU | Active | Deal broadcast | Cảm xúc | Combo Tết 680K — ưu tiên khách Zalo | Brand |
| 28/01 | Engage | BOFU | VIP | Exclusive | Thẩm quyền | Ưu đãi riêng khách VIP trước Tết | Brand |

## Repurpose Matrix 1:7

| Hero Content | Repurpose 6 dạng |
|---|---|
| Video TikTok Đông y vs skincare (10/01) | Facebook Reels / Instagram Reels / YouTube Shorts / Zalo OA snippet / Carousel screenshots / Quote card |
| Before/after chị Mai TikTok (13/01) | Facebook bài viết dài / Zalo broadcast / Instagram carousel / Ads MOFU / Story highlight / UGC repost |

## Năng lực team & phân công

| Người | Vai trò | Số content/tuần |
|---|---|---|
| Founder | FGC TikTok + approve | 2 video/tuần |
| Content Writer | Bài Facebook + caption | 3 bài/tuần |
| Brand | Carousel, deal post, broadcast | 2-3 post/tuần |
| Khách UGC | Testimonial tự nhiên | 1 video/tháng |

## AI Content Scoring

| Bài | Score | Lý do |
|---|---|---|
| Before/after chị Mai TikTok | High impact / Easy | Đã có ảnh, chỉ cần edit đơn giản |
| Tutorial Đông y vs skincare | High impact / Hard | Cần prep nội dung kỹ, viral cao |
| Deal Tết combo 680K Facebook | High impact / Easy | Template có sẵn, chỉ đổi số |
| Q&A founder TikTok | High impact / Hard | Cần founder tự tin on-cam |
| Poll Facebook | Low impact / Easy | Lấp lịch nhanh khi thiếu content |
"""


def main():
    parsed = {
        "deliverable": MOCK_CALENDAR,
        "summary": "",
        "raw": MOCK_CALENDAR,
    }

    print("Rendering Excel...")
    xlsx_bytes = render_excel_file(
        skill_name="content_calendar",
        skill_label="Lịch Nội Dung",
        parsed=parsed,
        output_format=OutputFormat.OPERATIONAL_DELIVERABLE,
        business_name="Lotus Spa",
    )

    if xlsx_bytes:
        out = "/home/user/marketing-os-bot/sample_calendar_lotus_spa.xlsx"
        with open(out, "wb") as f:
            f.write(xlsx_bytes)
        print(f"Done: {out} ({len(xlsx_bytes):,} bytes)")
    else:
        print("Renderer returned None")


if __name__ == "__main__":
    main()
