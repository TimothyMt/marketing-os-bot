# Marketing OS — Handoff Document

> Cập nhật lần cuối: 2026-05-18 (Priority 1 hardening pass)

---

## Dự án là gì?

Telegram bot tên **Max — AI CMO**, giúp founder Việt Nam phân tích marketing chỉ bằng cách chat tự nhiên.  
User nhắn mô tả business → Max hỏi thêm nếu cần → chạy phân tích → trả về strategy hoàn chỉnh.

- **GitHub**: https://github.com/TimothyMt/marketing-os-bot
- **Deploy**: Railway (auto-deploy từ GitHub branch)
- **Local path**: tùy máy (vd `C:\Users\<your-user>\projects\marketing-os-bot\`)

---

## ⚡ Quick Start trên máy mới

Branch hoạt động hiện tại: **`fix/critical-issues`** (chứa Priority 1 hardening).

```bash
# 1. Clone repo
git clone https://github.com/TimothyMt/marketing-os-bot
cd marketing-os-bot

# 2. Checkout branch đang làm
git fetch origin
git checkout fix/critical-issues

# 3. Verify đúng commit gần nhất
git log --oneline -1
# Expect: 9eb6081 fix: Priority 1 hardening — timeouts, error handling, ...

# 4. Cài dependencies (đã có thêm tavily-python)
pip install -r requirements.txt

# 5. Tạo .env (xem section "Env vars" bên dưới)
# Tối thiểu: ANTHROPIC_API_KEY + TAVILY_API_KEY để chạy simulate.py

# 6. Test nhanh không cần Telegram/Supabase
python simulate.py

# 7. Đọc thứ tự để hiểu Priority 1:
#    HANDOFF.md (file này) → section "Priority 1 Hardening" bên dưới
#    AUDIT_REPORT_20250518.md — rationale + danh sách 20 issues
#    BUG_ANALYSIS_BRAND_DETECTION.md — 5 bugs brand search + code fixes
#    IMPROVEMENTS_IMPLEMENTATION.md — implementation guide Priority 1+2
```

> **Lưu ý git identity**: nếu commit lần đầu trên máy mới, set local cho repo:
> `git config user.email "your@email"` + `git config user.name "Your Name"`.
> Commit gần nhất do `dev@local` tạo (inline identity, không lưu config).

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

## Flow hoàn chỉnh (sau Priority 1 hardening)

```
/start
  └─→ @safe_handler bao bọc — mọi lỗi → "😅 Xin lỗi + gõ lại tin nhắn"
  └─→ stage = TASK_SELECT
      └─→ WELCOME_MESSAGE + 7-nút task keyboard

User chọn task (vd: "📡 Social Listening")
  └─→ validate_task_type() chặn callback giả mạo (task_invalid)
  └─→ selected_task = "social", stage = INTAKE
      └─→ Gửi câu hỏi mở đầu riêng cho task đó

User nhắn tin (stage = INTAKE):
  ├─ validate_user_input() — chặn empty / >2000 chars / spam ngay ở boundary
  │
  ├─ _is_likely_brand_name() — Tin đầu, ≤3 words, ≤30 chars, charset whitelist,
  │   không terminator (.?!,), không từ mô tả (tôi/bán/shop/...)
  │   └─→ Brand Search Flow:
  │       ├─ status_msg "🔍 Đang tìm kiếm..."
  │       ├─ search_brand_candidates() — timeout 30s, không retry
  │       ├─ 1 kết quả  → keyboard [✅ Đúng / ❌ Không phải]
  │       ├─ 2-4 kết quả → show options + [❌ Không phải]
  │       │   stage = BRAND_SELECT (callback có race-guard)
  │       └─ 0 kết quả/timeout/error → "😅 Xin lỗi không tìm được"
  │           → Guided Wizard 5 bước (xem section "Priority 1 #5")
  │
  └─ Normal intake
      └─→ with_heartbeat() wrap toàn bộ:
          - typing indicator refresh mỗi 4s
          - progress messages tại 30s/75s/150s
      └─→ run_intake() @with_timeout(AGENT_TIMEOUT=120s)
          Claude có thể tự gọi web_search (tool-use loop)
          web_search() timeout 30s mỗi call, return error string nếu fail
          Khi đủ info → trả JSON profile trong ```json``` block
          └─→ stage = CONFIRMED + _send_confirm_card()
              [✅ Đúng rồi, bắt đầu! / ✏️ Sửa thông tin]

User click [✅ Đúng rồi, bắt đầu!]
  └─→ Race-guard: chỉ process nếu stage == CONFIRMED
  └─→ stage = MARKET_RESEARCH
  └─→ _run_pipeline_sequentially() — chỉ stages của task đã chọn

      "full"       → market → competitor → customer → pricing → social → synthesis
      "market"/"competitor"/.../"strategy" → 1 stage tương ứng

      Mỗi stage:
        1. progress_cb gửi "🔍 Đang nghiên cứu..."
        2. with_heartbeat wrap stage call — typing + progress 30/75/150s
        3. stage_fn() @with_timeout(AGENT_TIMEOUT=120s) hoặc
           _run_agent_with_tools @with_timeout(PIPELINE_STAGE_TIMEOUT=240s)
        4. Gửi kết quả ngay, save_session
        5. Stage cuối: keyboard [🔄 Phân tích mới / ❓ Hỏi thêm]

stage = COMPLETE
  └─→ User hỏi thêm → _handle_followup() → run_followup() có timeout + heartbeat
```

**Khi có lỗi/timeout bất kỳ chỗ nào trên flow**:
- `@with_timeout` raise `AgentTimeoutError` / `AgentExecutionError`
- Bubble lên `@safe_handler` ở top-level (cmd_*/handle_message/handle_callback)
- User nhận message tiếng Việt rõ ràng: "😅 Xin lỗi + gõ lại tin nhắn vừa rồi"
- Session **không reset** — user chỉ cần gõ lại 1 tin nhắn để tiếp tục

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
                               # → guided_intake (nếu brand search fail)
                               # → confirmed → [pipeline stages] → complete
    selected_task: str         # "full"/"market"/"competitor"/"customer"/"pricing"/"social"/"strategy"
    profile: BusinessProfile   # Extracted từ intake conversation hoặc guided wizard
    intake_history: list[dict] # [{"role": "user/assistant", "content": "..."}] max 20 turns
    results: dict[str, str]    # {"market_research": "...", "_guided_step": "industry", ...}
    raw_description: str
    brand_candidates: list     # Tạm lưu kết quả search brand (xóa sau khi confirm)
```

> ⚠️ **Quan trọng**: Các field "ngoài DataClass schema" được lưu bằng cách nhét vào `results` dict với prefix `_` — không cần thêm column Supabase. Hiện có:
> - `_selected_task` — task user chọn
> - `_brand_candidates` — kết quả Tavily brand search
> - `_guided_step` — step hiện tại trong guided wizard ("industry"/"stage"/"product"/"customer"/"location")
> - `_guided_await_other` — step nào đang chờ user gõ free text (sau khi tap "Khác")
>
> Logic encode/decode trong `storage/session.py`.

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

| Branch | Trạng thái | Commit gần nhất | Mô tả |
|---|---|---|---|
| `master` | ✅ Stable production | `772a967` | Task-first UX, KHÔNG có web search/brand/Priority 1 |
| `feature/web-search` | 🧪 Testing | `d961012` | Thêm Tavily + brand identification (chưa hardening) |
| **`fix/critical-issues`** | 🚧 **Active dev** | **`9eb6081`** | **Branch hiện tại — Priority 1 hardening** (từ feature/web-search) |

**Quan hệ branches**:
```
master ──┐
         └─→ feature/web-search ──→ fix/critical-issues  ← bạn đang ở đây
```

**Rollback**: Railway → Deployments → chọn deploy từ `master` → instant.
**Để deploy Priority 1 sau khi test**: merge `fix/critical-issues` → `master`.

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

### `AUDIT_REPORT_20250518.md` (4.6K)
Architecture review + đánh giá codebase health 7.5/10.
- Strengths: async-first, prompt caching, state machine rõ ràng
- Critical issues: timeouts, error handling, race conditions
- Roadmap Priority 1 (đã làm) + Priority 2 (chưa làm)
- **Đọc đầu tiên** để hiểu rationale.

### `BUG_ANALYSIS_BRAND_DETECTION.md` (8.6K)
Chi tiết 5 bugs trên `feature/web-search` branch + code fix:
1. No timeout on Tavily search → đã fix (timeout 30s)
2. Race condition brand selection → đã fix (stage guard)
3. Missing error handling → đã fix (@safe_handler bubble up)
4. Brand matching too aggressive → đã fix (≤3 words, charset whitelist)
5. No recovery flow → đã fix (Guided Wizard)

### `IMPROVEMENTS_IMPLEMENTATION.md` (11K)
Implementation guide với code examples cho:
- Priority 1 (timeout decorator, error handler, validators, brand fixes) — **đã làm**
- Priority 2 (logging, cleanup, PDF export, rate limiting) — **chưa làm**
- Testing strategy (unit + integration + staging)
- Deployment plan (staging → production)

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
