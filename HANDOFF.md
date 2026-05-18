# Marketing OS — Handoff Document

> Cập nhật lần cuối: 2026-05-18 (Priority 1 hardening pass)

---

## Dự án là gì?

Telegram bot tên **Max — AI CMO**, giúp founder Việt Nam phân tích marketing chỉ bằng cách chat tự nhiên.  
User nhắn mô tả business → Max hỏi thêm nếu cần → chạy phân tích → trả về strategy hoàn chỉnh.

- **GitHub**: https://github.com/TimothyMt/marketing-os-bot
- **Deploy**: Railway (auto-deploy từ GitHub branch)
- **Local path**: `C:\Users\dtnhien\marketing-os-bot\`

---

## Stack kỹ thuật

| Layer | Tool | Lý do chọn |
|---|---|---|
| Bot framework | `python-telegram-bot` v21 async | Webhook + async native |
| AI | Anthropic `claude-sonnet-4-6` | Tốt nhất cho tiếng Việt + tool use |
| Database | Supabase PostgreSQL | HTTPS REST — Railway block TCP 5432, không block 443 |
| Web search | Tavily API | Thiết kế cho AI agents, 1000 req/tháng free |
| Hosting | Railway | Auto-deploy từ GitHub, env vars management |

---

## Cấu trúc thư mục

```
marketing-os-bot/
├── bot/
│   ├── main.py            ← Entry point, webhook setup (production)
│   ├── handlers.py        ← Toàn bộ Telegram logic (message + callback)
│   ├── keyboards.py       ← Inline keyboard definitions (+ guided wizard kb)
│   ├── _error_handler.py  ← @safe_handler — exception → Vietnamese message
│   ├── _validators.py     ← Input + enum validation at Telegram boundary
│   ├── _guided_intake.py  ← Wizard flow khi brand search không tìm được
│   └── _heartbeat.py      ← Typing + progress messages cho long operations
├── agents/
│   ├── pipeline.py        ← Orchestration — gọi Claude cho từng bước
│   ├── prompts.py         ← System prompts cho 8 agents + task-specific intake variants
│   └── _decorators.py     ← @with_timeout + AgentTimeoutError/AgentExecutionError
├── frameworks/
│   ├── kpi_library.py     ← 8 ngành × KPI benchmarks đã calibrate
│   ├── save_framework.py  ← SAVE framework generator (thay thế 4P)
│   └── smart_framework.py ← SMART goals templates per ngành × stage
├── storage/
│   ├── models.py          ← DataClass: Session, BusinessProfile, PipelineStage
│   ├── session.py         ← Supabase read/write logic
│   └── __init__.py        ← Re-export get_session, save_session, reset_session
├── tools/
│   ├── search.py          ← Tavily wrapper + WEB_SEARCH_TOOL definition
│   └── __init__.py
├── config.py              ← Tất cả env vars + constants
├── simulate.py            ← CLI test không cần Telegram/Supabase
└── run_local.py           ← Chạy bot local bằng polling mode
```

---

## Env vars (Railway Variables)

```env
TELEGRAM_BOT_TOKEN=        # @BotFather
ANTHROPIC_API_KEY=         # console.anthropic.com
SUPABASE_URL=              # Project URL từ Supabase dashboard
SUPABASE_SERVICE_KEY=      # service_role key (KHÔNG dùng anon key)
WEBHOOK_URL=               # Railway domain, vd: https://xxx.up.railway.app
PORT=8000
TAVILY_API_KEY=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
```

---

## Flow hoàn chỉnh

```
/start
  └─→ stage = TASK_SELECT
      └─→ WELCOME_MESSAGE + 7-nút task keyboard

User chọn task (vd: "📡 Social Listening")
  └─→ selected_task = "social", stage = INTAKE
      └─→ Gửi câu hỏi mở đầu riêng cho task đó

User nhắn tin (stage = INTAKE):
  ├─ Tin đầu tiên + ≤4 words + ≤45 chars + không có từ mô tả
  │   └─→ Brand Search Flow (B1 → B2 → B3):
  │       ├─ Tavily search brand name
  │       ├─ 1 kết quả  → keyboard [✅ Đúng rồi / ❌ Không phải]
  │       ├─ 2-4 kết quả → show options + [❌ Không phải những cái trên]
  │       └─ 0 kết quả  → fallback về normal intake
  │
  └─ Normal intake
      └─→ run_intake() — Claude hỏi cho đến khi đủ info
          Claude có thể tự gọi web_search nếu cần
          Tool calls chạy local loop, KHÔNG ghi vào intake_history
          Khi đủ → trả JSON profile trong ```json``` block
          └─→ stage = CONFIRMED + confirm card
              [✅ Đúng rồi, bắt đầu! / ✏️ Sửa thông tin]

User nhấn [✅ Đúng rồi, bắt đầu!]
  └─→ run_targeted_pipeline() — chỉ chạy stages của task đã chọn

      "full"       → market → competitor → customer → pricing → social → synthesis (6 bước)
      "market"     → market_research (1 bước)
      "competitor" → competitor (1 bước)
      "customer"   → customer_insight (1 bước)
      "pricing"    → psychology_pricing (1 bước)
      "social"     → social_listening (1 bước)
      "strategy"   → synthesis (1 bước)

      Mỗi bước:
        1. Gửi progress message
        2. Gọi Claude với web_search tool available
        3. Gửi kết quả ngay (không chờ hết pipeline)
        4. Bước cuối: keyboard [🔄 Phân tích mới / ❓ Hỏi thêm]

stage = COMPLETE
  └─→ User hỏi thêm → _handle_followup() — Q&A không giới hạn
```

---

## Agents & Prompts

File: `agents/prompts.py`

| Agent | Prompt | Web search | Ghi chú |
|---|---|---|---|
| Intake full/strategy | `INTAKE_SYSTEM` | ✅ | |
| Intake market | `INTAKE_MARKET_SYSTEM` | ✅ | Chỉ hỏi fields cần cho market research |
| Intake competitor | `INTAKE_COMPETITOR_SYSTEM` | ✅ | Hỏi thêm về đối thủ cụ thể |
| Intake customer | `INTAKE_CUSTOMER_SYSTEM` | ✅ | Hỏi sâu về pain point |
| Intake pricing | `INTAKE_PRICING_SYSTEM` | ✅ | Hỏi giá hiện tại + vấn đề đang gặp |
| Intake social | `INTAKE_SOCIAL_SYSTEM` | ✅ | Hỏi tên brand + đối thủ cần monitor |
| Market Research | `MARKET_RESEARCH_SYSTEM` | ✅ | TAM/SAM/SOM |
| Competitor | `COMPETITOR_SYSTEM` | ✅ | 8 chiều phân tích + market gap |
| Customer Insight | `CUSTOMER_INSIGHT_SYSTEM` | ❌ | ICP + JTBD + Pain-Gain Map |
| Psychology + Pricing | `MARKETING_PSYCHOLOGY_SYSTEM` + `PRICING_STRATEGY_SYSTEM` | ❌ | Gộp 1 call, tiết kiệm ~30s latency |
| Social Listening | `SOCIAL_LISTENING_SYSTEM` | ✅ | Keyword clusters + monitoring routine |
| Strategy Synthesis | `STRATEGY_SYNTHESIZER_SYSTEM` | ❌ | Inject SAVE + SMART vào context |

**Hàm quan trọng**:
- `get_intake_system(task_type)` → trả đúng prompt cho task được chọn
- `_run_agent_with_tools()` → agent runner có web search loop
- `run_targeted_pipeline()` → chạy đúng stages theo `TASK_PIPELINE_MAP`

---

## Session State

```python
@dataclass
class Session:
    user_id: int
    stage: PipelineStage       # idle → task_select → intake → brand_select
                               # → confirmed → [pipeline stages] → complete
    selected_task: str         # "full"/"market"/"competitor"/"customer"/"pricing"/"social"/"strategy"
    profile: BusinessProfile   # Extracted từ intake conversation
    intake_history: list[dict] # [{"role": "user/assistant", "content": "..."}] max 20 turns
    results: dict[str, str]    # {"market_research": "...", "competitor": "...", ...}
    raw_description: str
    brand_candidates: list     # Tạm lưu kết quả search brand (xóa sau khi confirm)
```

> ⚠️ **Quan trọng**: `selected_task` và `brand_candidates` được lưu bằng cách nhét vào `results` dict với key `_selected_task` / `_brand_candidates` — **không cần thêm column Supabase**. Logic xử lý trong `storage/session.py`.

---

## Frameworks

### KPI Library (`frameworks/kpi_library.py`)
8 ngành pre-calibrated: `fnb`, `tech_saas`, `ecommerce`, `education`, `health_beauty`, `retail`, `b2b_service`, `real_estate`

Mỗi ngành có:
- Primary KPIs, Secondary KPIs, Vanity KPIs (cảnh báo không nên dùng)
- Benchmarks theo stage (mvp / growth / scale)
- Unit economics formulas
- Growth levers + Channel priority
- TAM methodology phù hợp ngành

Dùng: `get_framework_as_text(industry)` → inject vào Market Research agent.

### SAVE Framework (`frameworks/save_framework.py`)
Thay 4P truyền thống bằng góc nhìn từ phía khách hàng:

| Thay | Bằng | Nguyên tắc |
|---|---|---|
| Product | **S**olution | Frame theo vấn đề giải quyết, không phải tính năng |
| Place | **A**ccess | Tối ưu cách mua của KH, không phải kênh phân phối |
| Price | **V**alue | Communicate total value, không phải số tiền trả |
| Promotion | **E**ducation | Dạy KH trước khi bán |

Dùng: `generate_save_analysis(industry, business_description, target_customer, product_service)` → inject vào Synthesis agent.

### SMART Framework (`frameworks/smart_framework.py`)
Goal templates calibrated per ngành × stage. Mỗi ngành 2-3 templates với KPIs cụ thể và số thực tế.

Dùng: `format_smart_prompt(industry, stage, goals)` → inject vào Synthesis agent.

---

## Branches & Rollback

| Branch | Trạng thái | Commits |
|---|---|---|
| `master` | ✅ Stable — task-first UX hoàn chỉnh | `772a967` |
| `feature/web-search` | 🧪 Testing — web search + brand ID | `d961012` |

**Rollback**: Railway → Deployments → chọn deploy từ `master` → instant.

---

## Chạy local

```bash
# 1. Clone và cài dependencies
git clone https://github.com/TimothyMt/marketing-os-bot
cd marketing-os-bot
pip install -r requirements.txt

# 2. Tạo file .env
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-dev-...
# (Thêm TELEGRAM_BOT_TOKEN + Supabase nếu dùng run_local.py)

# 3a. CLI simulator — không cần Telegram, không cần Supabase
python simulate.py

# 3b. Bot thật, polling mode — cần đủ env vars
python run_local.py
```

---

## Priority 1 Hardening — đã xong (branch `fix/critical-issues`)

Branch hiện tại bắt đầu từ `feature/web-search`, thêm các lớp bảo vệ và UX:

### 1. Timeouts có cấu trúc
- `agents/_decorators.py` mới — decorator `@with_timeout(secs)` + 2 exception types:
  - `AgentTimeoutError` — gọi mất quá lâu, user nên thử lại
  - `AgentExecutionError` — lỗi logic, gợi ý /reset
- Áp lên `run_intake`, `_run_agent`, `_run_agent_with_tools`, `run_followup`
- Constants mới ở `config.py`:
  - `AGENT_TIMEOUT = 120s` — một agent đơn lẻ
  - `TAVILY_TIMEOUT = 30s` — một call Tavily (raised từ 15s)
  - `PIPELINE_STAGE_TIMEOUT = 240s` — stage có tool-use loop
- `tools/search.py`: `asyncio.wait_for` quanh Tavily, **không loop retry**, return error string để Claude tự xử lý

### 2. Error handling tập trung
- `bot/_error_handler.py` mới — `@safe_handler` decorator:
  - Map exception class → user message tiếng Việt
  - Mọi message bắt đầu bằng "😅 Xin lỗi" và bảo user **"gõ lại tin nhắn vừa rồi"** (session không mất)
  - Markdown rendering với plain-text fallback
  - Log full traceback (`exc_info=True`) cho production
- Wrapped: `cmd_start`, `cmd_reset`, `cmd_help`, `handle_message`, `handle_callback`
- `_handle_followup` refactor → dùng `run_followup()` thay vì raw client call

### 3. Validation ở boundary
- `bot/_validators.py` mới:
  - `validate_user_input()` — reject empty/>2000 chars/spam (`MAX_INPUT_LENGTH=2000` ở config)
  - `validate_task_type()` — chặn `task_invalid` giả mạo từ callback
- Apply trong `handle_message` (trước khi load session) và `handle_callback` (task_ branch)

### 4. Brand detection hardening
- `_is_likely_brand_name()` siết:
  - Từ ≤4 words / ≤45 chars xuống **≤3 words / ≤30 chars**
  - Char whitelist (chặn emoji, special chars)
  - Reject câu hỏi (`?!.,`)
  - Mở rộng `_DESCRIPTIVE_TOKENS` (anh/chị/em/bạn/đã/sẽ...)
- Race condition guard: callback `brand_pick_` check `session.stage == BRAND_SELECT` trước khi process; transition stage NGAY trước async work
- Recovery flow đổi từ "mô tả thêm" sang **Guided Intake Wizard** (xem #5)

### 5. Guided Intake Wizard (mới)
Khi brand search fail HOẶC user click "❌ Không phải", thay vì để user gõ free-form:
- `bot/_guided_intake.py` mới — 5-step wizard với keyboard
  1. Ngành (8 options + "Khác")
  2. Stage (4 options + "Khác")
  3. Sản phẩm/dịch vụ (text với ví dụ)
  4. Khách hàng (text với ví dụ)
  5. Địa bàn (5 options + "Khác")
- State tracker: `session.results["_guided_step"]` + `["_guided_await_other"]`
- Tap nút "Khác" → wait next text message → save vào field tương ứng
- Sau step 5 → reuse `_send_confirm_card()` → user xác nhận → pipeline chạy
- New `PipelineStage.GUIDED_INTAKE` enum value
- Keyboards mới: `INDUSTRY_KEYBOARD`, `STAGE_KEYBOARD`, `LOCATION_KEYBOARD`

### 6. Progress Heartbeat (mới)
- `bot/_heartbeat.py` mới — `with_heartbeat(coro_factory, message, bot)`:
  - Refresh typing indicator mỗi 4s
  - 3-tier progress messages tại 30s / 75s / 150s
  - Tự cancel khi operation hoàn tất → không spam
  - Telegram errors bên trong heartbeat được swallow → không kill main flow
- Apply trong `_handle_intake`, `_handle_followup`, `_run_pipeline_sequentially`
- Pipeline runner refactor `async for` thành manual `__anext__()` để wrap mỗi stage

### Trải nghiệm user mới
- Lỗi/timeout → bot xin lỗi rõ ràng + bảo gõ lại 1 tin nhắn, **session không reset**
- Long operation (60s+) → user thấy typing liên tục + tin nhắn progress
- Pipeline 240s timeout → vẫn báo lại + bảo gõ lại
- Brand không tìm được → wizard với button thay vì hỏi 5 câu open-ended

---

## Tham chiếu Audit

3 file MD ở root branch `fix/critical-issues`:
- `AUDIT_REPORT_20250518.md` — kiến trúc review + danh sách issues
- `BUG_ANALYSIS_BRAND_DETECTION.md` — 5 bugs cụ thể của brand search + fix code
- `IMPROVEMENTS_IMPLEMENTATION.md` — implementation guide cho cả Priority 1 + 2

---

## Bước tiếp theo

### Trước khi merge `fix/critical-issues` → `master`
- [ ] Test trên Railway staging với TAVILY_API_KEY thật
- [ ] Manual test 7 task flows (full, market, competitor, customer, pricing, social, strategy)
- [ ] Test brand wizard: gõ "Nike" → keyboard flow → confirm
- [ ] Test heartbeat: simulate slow Claude (mock) → verify thấy progress messages
- [ ] Test error: kill TAVILY_API_KEY trong env → verify graceful fallback

### Priority 2 — chưa làm
- [ ] Structured JSON logging (bot/_logging_config.py)
- [ ] Session TTL cleanup job (xóa session > 30 ngày)
- [ ] PDF export report (reportlab)
- [ ] Rate limiting per user_id

### Có thể làm thêm (đề xuất từ session)
- [ ] Auto-retry sau timeout (Option A — phức tạp, tốn quota)
- [ ] `/status` command để user check bot health
- [ ] "Bot recovered" notification sau outage
- [ ] Thêm tokens không dấu vào `_DESCRIPTIVE_TOKENS` (vd "toi", "ban") — giảm false positive brand detection
