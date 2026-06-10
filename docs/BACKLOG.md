# Backlog — Vấn đề để giải quyết sau

Các ý tưởng / tính năng / vấn đề đã bàn nhưng chưa triển khai. Ghi lại để không mất.

---

## 1. So sánh 1-1 với đối thủ cụ thể (Competitor 1-on-1)

**Vấn đề hiện tại:**
`competitor_comparison` ("🆚 So Sánh Với Đối Thủ") chỉ xuất hiện 1 lần duy nhất sau khi chạy xong "Phân tích đối thủ" — nếu bỏ qua thì không có cách quay lại. Khi chạy, skill này không nhận tên đối thủ cụ thể (`intake_fields=[]`) — chỉ đọc lại bản phân tích landscape cũ (`session.results["competitor"]`) → output chung chung, cảm giác "dùng lại bài gốc".

**Hướng giải quyết đã bàn:**
1. Thêm intake field "Tên đối thủ muốn so sánh trực tiếp" (required) + "Thông tin sếp biết về đối thủ này" (optional)
2. Dùng `Provider.GEMINI_PRO_GROUNDED` (`tools/llm_router.py:360`) — Gemini 2.5 Pro + Google Search grounding — để search thông tin công khai về đối thủ cụ thể đó (website, Google Maps, review...) trước khi chạy comparison
3. Kết hợp: grounded search result + `session.results["competitor"]` (nếu đối thủ đó đã được nhắc) + `session.results["competitor_spy"]` (nếu đã spy) + thông tin sếp tự cung cấp
4. Áp dụng anti-hallucination rule — nếu thiếu data, Max báo thẳng + hướng dẫn sếp bổ sung (pattern giống `competitor_spy`)
5. Thêm vào `owns_skills` của Max persona, chỉ hiện nút khi đã có `session.has_result("competitor")`

**Giới hạn cần nhớ:**
- Gemini grounded search chỉ thấy nội dung công khai đã được Google index — đối thủ nhỏ/local thì data có thể rất ít (metadata fanpage, vài review)
- Facebook fanpage: Gemini chỉ lấy được metadata bề mặt (tên trang, about, rating) — nội dung bài đăng/ads nằm sau login wall, không index được; phải dùng `competitor_spy` (FB Ads Library) để lấy data ads

**Đầu mục so sánh đề xuất (7 mục):**
1. Định vị & thông điệp chủ đạo
2. Sản phẩm/dịch vụ & USP
3. Giá & mô hình kinh doanh
4. Kênh phân phối / cách tiếp cận khách hàng
5. Tín hiệu uy tín (review, chứng nhận, social proof)
6. Điểm mạnh/yếu đối đầu trực diện (head-to-head)
7. Cơ hội khác biệt hoá riêng trước đối thủ này

**File liên quan:**
- `agents/task_registry.py:336` — TaskConfig `competitor_comparison`
- `agents/operational_prompts.py:1771` — `COMPETITOR_COMPARISON_SYSTEM`
- `agents/operational_skills_config.py:384` — `make_competitor_comparison_skill()`
- `tools/llm_router.py:360` — `_call_gemini_pro_grounded()`
- `bot/handlers.py:4704` — follow-up button hiện tại (sau khi chạy competitor)
- `bot/keyboards.py:107` — `COMPARE_PROMPT_KEYBOARD`

> ⚠️ Update 2026-06-10: `competitor_comparison` đã TẠM TẮT (gỡ TaskConfig khỏi registry,
> bỏ khỏi owns_skills của Minh). Prompt + factory vẫn còn. Khi làm mục này thì thêm lại
> TaskConfig theo hướng trên.

---

## 2. Đã chốt với sếp — làm theo thứ tự (2026-06-10)

### 2.1. Xoá dead code `run_ads_after_cal`
Handler `bot/handlers.py` (`if data == "run_ads_after_cal"`) không có button nào emit
callback này — Calendar → Ads tắt thẳng không qua Nam chưa bao giờ chạy được. Xoá block.

### 2.2. Build skill `brand_positioning` cho Linh (Brand Manager)
Flow đã chốt:
- **Input** (tự đọc từ session, KHÔNG bắt user nhập lại):
  - `usp_definition` (T2) — USP đã chốt + options + reasoning
  - `synthesis` (T4) — `positioning.statement` + 4 trục SAVE
  - `customer_insight` — segments để chia key message
  - Brand Voice DB (nếu có) — tone phải khớp
- **Output — Messaging House** (1 file HTML):
  1. Positioning statement (refine từ T4, không làm lại từ đầu)
  2. Tagline 3-5 option (mài từ USP)
  3. Value prop ladder (functional → emotional → self-expressive)
  4. Key messages per segment (1 thông điệp chính + 2-3 supporting + proof point)
  5. Do's / Don'ts khi viết (cầu nối sang brand_voice)
- **Revise loop (sếp yêu cầu):** sau khi gửi output → hỏi "Sếp muốn sửa gì không?"
  → nhận feedback → LLM update → **ghi bản đã chốt vào session tổng**
  (lưu `brand_positioning` result; các skill sau ưu tiên đọc bản này thay vì
  `synthesis.positioning` gốc)
- Gắn vào `owns_skills` của Linh + gate: chưa có T2/T4 thì gợi ý chạy
  "Nghiên Cứu & Phân Tích Thị Trường" trước (pattern STRATEGY_GATED)
- Messaging house sau đó inject vào context của Nam/Trang/post_voice_check
  (giống pattern tactical_playbook)

### 2.3. Cải tiến `ads_generator` (3 gap đã phát hiện — chưa chốt ưu tiên)
1. `ads_format` (Video/Ảnh chọn ở bước 2) KHÔNG được truyền vào prompt —
   copy gen ra giống nhau bất kể format
2. `build_context` chưa inject `usp_definition` — headline ads lẽ ra phải bám USP
3. Platform cứng trong prompt (Meta/TikTok/Google/Zalo) — chưa đọc wedge
   channels từ synthesis để chỉ gen cho đúng kênh mũi nhọn

---
