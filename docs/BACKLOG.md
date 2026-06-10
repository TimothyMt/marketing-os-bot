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

### 2.4. Tái cấu trúc `content_calendar` (CONTENT_CALENDAR_SYSTEM) — chống quá tải (2026-06-10)

**Vấn đề:** prompt hiện có 9 section bắt buộc trong 1 output → model dễ làm mỏng
từng phần. Đồng thời `content_calendar` đã nhận T4 (synthesis + dynamic pillar mix)
và T5 (tactical_playbook) qua `ContextStrategy.PROFILE_PLUS_CAMPAIGN`, nhưng
**CHƯA nhận archetype block** (trust_building/demand_gen/impulse) — khác với
`funnel_mapper` đã archetype-aware.

**Hướng đã thống nhất:**
1. Rút từ 9 section bắt buộc xuống **5 core**:
   - 1. Tổng quan kỳ
   - 2. Story Arc (4-week table)
   - 3. Pillar breakdown (dùng dynamic pillar mix đã tính sẵn)
   - 4. Weekly grid per channel (gộp luôn Content Format Guide vào đây thay vì
     tách section riêng)
   - 5. Vận hành (rút gọn)
2. **2 section optional** (chỉ xuất hiện nếu có input phù hợp):
   - Năng lực team & phân công — chỉ hiện nếu `profile.team_size` có giá trị
   - AI Content Scoring — optional, không bắt buộc
3. **Bỏ hẳn Repurpose Matrix 1:7** — thay bằng 1 dòng pointer: "Muốn nhân bản
   1 bài thành nhiều phiên bản theo audience khác → dùng skill `content_repurpose`"
4. **Fix gap archetype**: inject ARCHETYPE block (giống cách `funnel_mapper.py`
   dùng `resolve_archetype()` + `format_archetype_block()` từ
   `frameworks/industry_context.py`) vào context của `content_calendar`, để
   weekly grid + pillar mix bám đúng semantic phễu theo archetype (vd
   trust_building → thiên Industry/Personal content; impulse → thiên Offer/Convert).
   Cân nhắc luôn: cho `calc_dynamic_pillar_mix()` đọc thêm archetype (hiện chỉ
   đọc `stage` + `primary_goal`).

**File liên quan:**
- `agents/operational_prompts.py` — `CONTENT_CALENDAR_SYSTEM`
- `agents/operational_skills_config.py` — `ContentCalendarDynamicSkill`,
  `calc_dynamic_pillar_mix()`
- `frameworks/industry_context.py` — `resolve_archetype()`, `format_archetype_block()`
- `agents/funnel_mapper.py` — pattern tham khảo cho archetype injection

### 2.5. Dọn skill của Nam — đã chốt với sếp (2026-06-10)

**a) Xoá hẳn 2 skill** (pattern giống landing_page/performance_audit — gỡ TaskConfig,
factory, prompt, OPERATIONAL_SYSTEMS, owns_skills, html_report/renderers/llm_router
mapping, handlers refs, docs; GIỮ TaskType enum trong storage/models.py):
- **`comment_mining`** — PROFILE_ONLY, không đọc gì từ T1-T5, tách biệt hoàn toàn
- **`post_visual`** — PROFILE_ONLY + output trùng với section "🎨 Visual Brief"
  đã có sẵn trong `post_write`
- Lưu ý khi xoá: cả 2 đang nằm trong `BV_INJECTED_SKILLS` (`agents/pipeline.py:372`,
  post_visual) — gỡ luôn khỏi set đó. `tests/test_content_pipeline_e2e.py` có
  reference comment_mining/post_visual — sửa test.

**b) Xoá hẳn `social_posts`** — trùng vai với `post_batch` (cùng là bài đăng hữu cơ
batch). Lưu ý: `social_posts` đang nằm trong `CALENDAR_DRIVEN_SKILLS`
(`agents/pipeline.py:391`) và `BV_INJECTED_SKILLS` — gỡ khỏi cả 2 set.
KHÔNG nằm trong `ContentGeneratorPipeline.SUB_SKILLS` (pipeline dùng post_batch)
→ xoá không vỡ pipeline.

**c) Chuyển `content_calendar` + `campaign_brief` sang Max (CMO) cầm:**
- Gỡ 2 skill này khỏi `owns_skills` của Nam → thêm vào `owns_skills` của Max
  (`agents/manager_personas.py`, persona key="cmo")
- Lý do: đây là deliverable tầng kế hoạch — Max cầm để Nam/Trang/Linh đều
  truy cập được output từ session (các skill consume qua
  `session.get_latest_result("content_calendar")` / `CALENDAR_DRIVEN_SKILLS`
  và `PROFILE_PLUS_CAMPAIGN` nên KHÔNG phụ thuộc ai own — chỉ đổi người trigger)
- Cập nhật system_prompt của Nam (bỏ mention calendar/brief ở phần "SKILLS BẠN
  GỌI ĐƯỢC") + system_prompt của Max (thêm 2 skill mới)
- Gỡ `campaign_brief` khỏi owns_skills của Hương (marcon_pr, inactive) nếu muốn
  sạch — hoặc giữ vì persona inactive
- Check `trigger_keywords` của Nam ("lịch đăng", "content calendar") — chuyển
  sang Max hoặc giữ ở Nam để route user về đúng chỗ rồi Nam chỉ sang Max

**owns_skills của Nam sau khi dọn:**
`["content_generator", "post_write", "post_batch", "post_hooks", "post_adapt", "post_voice_check"]`

**d) Soft-gate khi chưa có content_calendar/campaign_brief:**
Nếu user gọi thẳng skill của Nam/Trang (vd `post_batch`, `video_script_gen`,
`ugc_brief`, `video_scripts`) khi `session.results` CHƯA có `content_calendar`
(hoặc `campaign_brief`), context vẫn chạy bình thường (chỉ mỏng hơn — chỉ có
profile + synthesis) — không chặn cứng, nhưng nên thêm 1 dòng gợi ý mềm kiểu:
"Chưa có Content Calendar — chạy với Max trước (`content_calendar`) thì kết quả
sẽ bám đúng kế hoạch hơn. Vẫn muốn chạy luôn không?"
Vị trí thêm: `build_user_msg`/`build_context` của các `CALENDAR_DRIVEN_SKILLS`
(`agents/pipeline.py:391`) hoặc handler trước khi dispatch.

---
