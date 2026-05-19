# Marketing OS — Handoff Document

> Cập nhật lần cuối: 2026-05-18

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
| Web search | Google Custom Search API | Free 100/ngày, VN-focused qua curated site list (20 site VN) |
| Hosting | Railway | Auto-deploy từ GitHub, env vars management |

---

## Cấu trúc thư mục

```
marketing-os-bot/
├── bot/
│   ├── main.py            ← Entry point, webhook setup (production)
│   ├── handlers.py        ← Toàn bộ Telegram logic (message + callback)
│   └── keyboards.py       ← Inline keyboard definitions
├── agents/
│   ├── pipeline.py        ← Orchestration — gọi Claude cho từng bước
│   └── prompts.py         ← System prompts cho 8 agents + task-specific intake variants
├── frameworks/
│   ├── kpi_library.py     ← 8 ngành × KPI benchmarks đã calibrate
│   ├── save_framework.py  ← SAVE framework generator (thay thế 4P)
│   └── smart_framework.py ← SMART goals templates per ngành × stage
├── storage/
│   ├── models.py          ← DataClass: Session, BusinessProfile, PipelineStage
│   ├── session.py         ← Supabase read/write logic
│   └── __init__.py        ← Re-export get_session, save_session, reset_session
├── tools/
│   ├── search.py          ← Google CSE wrapper + WEB_SEARCH_TOOL definition
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
GOOGLE_API_KEY=AIzaSy...        # Google Cloud Console > Credentials
GOOGLE_CSE_ID=xxx               # programmablesearchengine.google.com
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
  │       ├─ Google CSE search brand name (curated VN sites)
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

## Vấn đề đang dở

**Brand detection chưa confirm hoạt động trên production**
- Code logic đúng: `_is_likely_brand_name()` — first message, ≤4 words, ≤45 chars, không có từ mô tả tiếng Việt
- Nghi vấn: Railway chưa deploy commit `d961012` khi test
- Cách test: `/start` → chọn task → gõ tên brand ngắn (phải là **tin đầu tiên** trong intake)

---

## Bước tiếp theo

- [ ] Confirm brand detection hoạt động sau khi Railway deploy `d961012`
- [ ] Merge `feature/web-search` → `master` nếu ổn
- [ ] Cải thiện brand search: thêm query tiếng Anh cho brand quốc tế
- [ ] Data lifecycle: auto-xóa sessions > 30 ngày
- [ ] Export PDF report sau khi phân tích xong
