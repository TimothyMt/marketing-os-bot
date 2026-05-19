# Marketing OS — Handoff Document

> Cập nhật lần cuối: 2026-05-19
> Trạng thái: **Strategic layer hoàn chỉnh. Operational layer chưa có.**

---

## Dự án là gì?

Telegram bot tên **Max — AI CMO**, giúp founder Việt Nam phân tích marketing chỉ bằng cách chat tự nhiên.
User nhắn mô tả business → Max hỏi thêm nếu cần → chạy pipeline phân tích → trả về Telegram cards + HTML report đầy đủ.

- **GitHub**: https://github.com/TimothyMt/marketing-os-bot
- **Deploy**: Railway (auto-deploy từ branch `master`)
- **Local path**: `C:\Users\dtnhien\marketing-os-bot\`

---

## Stack kỹ thuật

| Layer | Tool | Lý do chọn |
|---|---|---|
| Bot framework | `python-telegram-bot` v21 async | Webhook + async native |
| AI executor | Anthropic `claude-sonnet-4-6` | Tốt nhất cho strategic analysis VN |
| AI intake + critic | Anthropic `claude-haiku-4-5` | Rẻ + nhanh, đủ cho classification + review |
| Database | Supabase PostgreSQL | HTTPS REST — Railway block TCP 5432, không block 443 |
| Hosting | Railway | Auto-deploy từ GitHub, env vars management |
| HTML render | `markdown` lib + CSS tabs | Mobile-safe accordion |

---

## Env vars (Railway Variables)

```env
TELEGRAM_BOT_TOKEN=        # @BotFather
ANTHROPIC_API_KEY=         # console.anthropic.com
SUPABASE_URL=              # Project URL từ Supabase dashboard
SUPABASE_SERVICE_KEY=      # service_role key (KHÔNG dùng anon key)
WEBHOOK_URL=               # Railway domain, vd: https://xxx.up.railway.app
PORT=8000
```

---

## Cấu trúc thư mục

```
marketing-os-bot/
├── bot/
│   ├── main.py            ← Entry point, webhook setup (production)
│   ├── handlers.py        ← Telegram message + callback logic
│   ├── keyboards.py       ← Inline keyboard definitions
│   └── html_report.py     ← HTML accordion report generator
├── agents/
│   ├── pipeline.py        ← Orchestration: run_intake, run_targeted_pipeline, _run_skill
│   ├── skills.py          ← AgentSkill base class + 6 concrete skills
│   ├── critic.py          ← Haiku critic + auto-hyperlink known VN sources
│   └── prompts.py         ← System prompts + task-specific intake variants + opening Q's
├── frameworks/
│   ├── kpi_library.py     ← 8 ngành × KPI benchmarks
│   ├── save_framework.py  ← SAVE framework generator (thay 4P)
│   └── smart_framework.py ← SMART goals templates per ngành × stage
├── storage/
│   ├── models.py          ← DataClass: Session, BusinessProfile, PipelineStage
│   ├── session.py         ← Supabase read/write
│   └── __init__.py
├── config.py              ← Env vars + model names + AGENT_TIMEOUT (500s)
├── simulate.py            ← CLI test không cần Telegram/Supabase
└── run_local.py           ← Bot polling mode (dev)
```

---

## Architecture — 2-tier model + Critic + Skill modularity

### 2-tier AI model

```
INTAKE (classification + JSON extract)
  └─→ Haiku 4.5 (rẻ, nhanh, đủ thông minh)

PIPELINE AGENTS (deep strategic analysis)
  └─→ Sonnet 4.6 (quality cao)

CRITIC (hallucination review)
  └─→ Haiku 4.5 (review tasks không cần quá thông minh)
```

### Pipeline flow chi tiết

```
/start → TASK_SELECT (menu 6 buttons)
  ↓
User chọn task → INTAKE (Haiku)
  ↓
Multi-turn conversation → JSON profile extracted
  ↓
CONFIRMED + confirm card → User confirm
  ↓
run_targeted_pipeline() — chạy stages của task:
  - "full":       market → competitor → customer → pricing → synthesis (5 stages)
  - "market":     market_research (1 stage)
  - "competitor": competitor (1 stage)
  - "customer":   customer_insight (1 stage)
  - "pricing":    psychology_pricing (1 stage)
  - "strategy":   synthesis (1 stage)
  (social listening tạm tắt)

  Mỗi stage:
    1. AgentSkill.build_context() + build_user_msg()
    2. Sonnet executor call → raw output (4-section format)
    3. Haiku critic review → fix hallucination, soften brand claims
    4. Post-process: auto-hyperlink known VN sources
    5. Parse 4 sections → Telegram card (Insight + Tóm tắt + Benchmarks)
    6. Detail section → accumulate vào HTML buffer
  ↓
COMPLETE → Send HTML report file → Q&A free
```

### Critic Review layer (`agents/critic.py`)

Haiku reviews mỗi agent output, sửa:
1. **Số liệu bịa** → đổi thành range hoặc "industry estimate"
2. **Mâu thuẫn nội bộ** → fix nhất quán
3. **Cite ngụy** → xóa hoặc đổi tên nguồn về list known
4. **Brand-specific claims** → làm mờ thành mô tả chung

Post-process: regex match 17 nguồn known (`Statista`, `GSO`, `WorldBank`, `Nielsen`, `Q&Me`, `Decision Lab`, `Vietcetera`, `CafeF`, `Brands Vietnam`, `Advertising Vietnam`, etc.) → inject Markdown hyperlink.

Critic fail → fallback original output, không block pipeline.

### Skill modularity (`agents/skills.py`)

```python
class AgentSkill(ABC):
    name: str
    system_prompt: str
    max_tokens: int
    enable_critic: bool = True
    @abstractmethod
    def build_context(self, session) -> str: ...
    @abstractmethod
    def build_user_msg(self, session) -> str: ...
```

6 concrete skills:
- `MarketResearchSkill` (max_tokens 4000)
- `CompetitorSkill` (4000)
- `CustomerInsightSkill` (4000)
- `PsychologyPricingSkill` (5000, combined call)
- `SocialListeningSkill` (4000, disabled)
- `StrategySynthesisSkill` (5000, +SAVE/SMART context)

Registry: `SKILL_REGISTRY: dict[str, type[AgentSkill]]`

Pipeline public API (`run_market_research`, `run_competitor_analysis`, ...) là wrapper gọi `_run_skill(SkillClass(), session)`.

---

## Output format

Mỗi agent BẮT BUỘC output 4 sections (enforced via `OUTPUT_FORMAT_INSTRUCTION` injected vào system prompt):

```markdown
## 💡 Insight quan trọng nhất
[1-2 câu cốt lõi trong dấu ngoặc kép]

## 🎯 Tóm tắt
- bullet 1
- bullet 2

## 📊 Benchmarks
[KPI/data points cụ thể]

## 📄 Phân tích chi tiết
[Full analysis, tables, sub-headings]
```

**Data discipline rules** (in OUTPUT_FORMAT_INSTRUCTION):
- Cite nguồn CHỈ từ list known (Statista/GSO/Nielsen/Q&Me/etc.)
- Không chắc → dùng RANGE: "50-80 nghìn tỷ" thay vì "60 nghìn tỷ"
- Brand cụ thể → mô tả chung, không bịa con số
- Cấm tuyệt đối: số chính xác không có nguồn

**Language rules** (in OUTPUT_FORMAT_INSTRUCTION):
- Thuật ngữ EN BẮT BUỘC kèm giải thích VN trong ngoặc lần đầu: "TAM (Total Addressable Market — tổng quy mô thị trường tối đa)"
- SMART/SAVE Goals viết full mỗi letter: "S (Specific — Cụ thể):"
- Tránh dịch literal — dùng từ tự nhiên ngữ cảnh VN

**Telegram card (Format B):**
- Insight quote
- Tóm tắt bullets
- Benchmarks
- "Xem full analysis trong file HTML cuối"

**HTML report (`bot/html_report.py`):**
- CSS-only tabs (radio + label) — mobile-safe, không cần JS
- Mỗi stage 1 tab
- Order: Insight (top) → Detail → Tóm tắt → Benchmarks (đáy)
- Hyperlinks render được trong browser

---

## Session State

```python
@dataclass
class Session:
    user_id: int
    stage: PipelineStage       # idle → task_select → intake → confirmed → [pipeline stages] → complete
    selected_task: str         # "full"/"market"/"competitor"/"customer"/"pricing"/"strategy"
    profile: BusinessProfile   # 13 fields extracted từ intake
    intake_history: list[dict] # Cleared khi vào CONFIRMED
    results: dict[str, str]    # {stage_key: result_text}
```

> `selected_task` được lưu vào `results["_selected_task"]` (nhét vào JSONB) — không cần thêm column Supabase.

---

## Frameworks

### KPI Library (`frameworks/kpi_library.py`)
8 ngành: `fnb`, `tech_saas`, `ecommerce`, `education`, `health_beauty`, `retail`, `b2b_service`, `real_estate`

Mỗi ngành: Primary/Secondary/Vanity KPIs, Benchmarks per stage (mvp/growth/scale), Unit economics, Growth levers, Channel priority, TAM methodology.

### SAVE Framework (`frameworks/save_framework.py`)
Solution / Access / Value / Education — thay thế 4P.

### SMART Framework (`frameworks/smart_framework.py`)
Goal templates calibrated per ngành × stage.

---

## ⚠️ LIMITATION: Đang chỉ có TẦNG CHIẾN LƯỢC

**Current scope = Strategic Layer:**
- ✅ Market Research (TAM/SAM/SOM)
- ✅ Competitor Analysis
- ✅ Customer Insight & ICP
- ✅ Psychology + Pricing Strategy
- ✅ Marketing Strategy Synthesis (SAVE + SMART + 90-day roadmap)

**Còn thiếu — Operational Layer:**
- ❌ Content calendar tháng
- ❌ Campaign brief (10 sections)
- ❌ Performance review + diagnostics
- ❌ Video script TikTok/Reels
- ❌ Ad copy đa platform
- ❌ UGC/EGC/KOC brief
- ❌ Email sequence
- ❌ KOL/Influencer brief

---

## 🔑 KHI THÊM TẦNG OPERATIONAL — LƯU Ý ĐỂ TRÁNH PHẢI SỬA NHIỀU

### Pattern thêm 1 operational skill mới — checklist 6 files:

```
1. agents/prompts.py
   - Thêm SYSTEM_PROMPT mới (vd: AD_COPY_SYSTEM)
   - Thêm INTAKE_XXX_SYSTEM nếu cần intake riêng
   - Thêm entry vào TASK_OPENING_QUESTIONS

2. agents/skills.py
   - Thêm AgentSkillXxx subclass (build_context, build_user_msg)
   - Thêm vào SKILL_REGISTRY

3. agents/pipeline.py
   - Thêm wrapper function: async def run_xxx(session) → _run_skill(XxxSkill(), session)
   - Thêm entry vào TASK_PIPELINE_MAP

4. bot/keyboards.py
   - Thêm button vào TASK_SELECT_KEYBOARD

5. bot/handlers.py
   - Thêm entry TASK_LABELS, TASK_PIPELINE_STEPS, TASK_STAGE_COUNT

6. agents/prompts.py (lần 2)
   - Thêm entry vào get_intake_system() mapping
```

### ⚠️ Sửa trước khi thêm Operational để giảm chỗ phải động:

**Refactor 1: Hợp nhất 4 dict scattered → 1 unified TASK_CONFIG**

Hiện tại 1 task được khai báo ở 4 chỗ khác nhau:
- `bot/handlers.py`: TASK_LABELS, TASK_PIPELINE_STEPS, TASK_STAGE_COUNT
- `agents/prompts.py`: TASK_OPENING_QUESTIONS
- `agents/pipeline.py`: TASK_PIPELINE_MAP
- `bot/keyboards.py`: TASK_SELECT_KEYBOARD (manual)

→ Nên gom thành 1 file `agents/task_registry.py`:
```python
TASK_REGISTRY = {
    "market": TaskConfig(
        label="Nghiên cứu thị trường",
        button_emoji="📊",
        opening_question="...",
        pipeline_steps_desc="📊 Phân tích TAM/SAM/SOM...",
        stages=[(MarketResearchSkill, "market_research")],
        intake_system_prompt=INTAKE_MARKET_SYSTEM,
    ),
    ...
}
```
→ Thêm task mới = thêm 1 entry, KHÔNG sửa 4 file.

### ⚠️ Operational skill khác Strategic skill — cần kiến trúc riêng:

**1. Output format khác:**
- Strategic: 4 sections (Insight + Tóm tắt + Benchmarks + Detail) — đã chuẩn
- Operational:
  - Ad copy → output = list of 3-5 copy variants (không cần 4 sections)
  - Content calendar → output = table 30 ngày
  - Brief → output = 10 sections cấu trúc cố định
- → `OUTPUT_FORMAT_INSTRUCTION` hiện hardcode 4 sections — cần làm **per-skill output format**:
  ```python
  class AgentSkill:
      output_format: OutputFormat = OutputFormat.STRATEGIC_4_SECTIONS
      # hoặc OPERATIONAL_FREE, OPERATIONAL_TABLE, OPERATIONAL_BRIEF_10
  ```

**2. Intake flow khác:**
- Strategic: cần full profile (13 fields) → multi-turn
- Operational: thường chỉ cần brand context + specific request
  - "Viết ad copy cho campaign Tết, target dân văn phòng 25-35"
  - Nếu user đã có profile từ session trước → SKIP intake, chỉ hỏi 1 câu specific
- → Thêm `AgentSkill.skip_intake_if_profile_complete: bool = False`

**3. Critic có thể không cần:**
- Strategic: critic catch số bịa — quan trọng
- Operational: ad copy không có số, không cần critic
- → `AgentSkill.enable_critic = False` đã sẵn — set cho operational skills

**4. HTML report aggregation khác:**
- Strategic: 1 HTML cuối pipeline cho cả 5 stages
- Operational: mỗi task có thể là deliverable riêng (1 ad copy = 1 file ngắn, không cần HTML report)
- → Có thể skip `_send_html_report` cho ops tasks; thay bằng inline output dài hơn

**5. Frequency dùng khác:**
- Strategic: 1-2 lần/quý
- Operational: hàng tuần
- → Cost cần thấp hơn per call (cân nhắc Haiku cho operational executor luôn)

**6. Session results accumulation:**
- Strategic pipeline: results overwrite key cũ
- Operational: user có thể "ad copy lần 1" rồi "ad copy lần 2" — cần versioning
- → Thay key `results["ad_copy"]` bằng `results["ad_copy_v1"]`, `results["ad_copy_v2"]` hoặc dùng list

### ⚠️ UI menu phân nhóm:

Hiện tại 6 buttons trong 1 keyboard. Khi có +7 operational tasks = 13 buttons → quá tải.

→ Cần keyboard 2 tier:
```
[🎯 Chiến lược]  →  Market / Competitor / Customer / Pricing / Strategy
[⚙️ Sản xuất]    →  Ad Copy / Content Calendar / Brief / Script / UGC
[📊 Đánh giá]    →  Performance Review
[🔍 Full Auto]   →  Phân tích toàn diện
```

→ Cần refactor:
- `bot/keyboards.py`: thêm `MAIN_MENU_KEYBOARD` + `STRATEGIC_KEYBOARD` + `OPERATIONAL_KEYBOARD`
- `bot/handlers.py`: handle thêm callback `menu_strategic`, `menu_operational`, `back_to_main`

### ⚠️ Brand context reuse:

Khi user đã chạy strategic analysis → profile đầy đủ trong session. Operational task tiếp theo:
- KHÔNG nên hỏi lại "Bạn bán gì, target ai" — đã có
- Hỏi thẳng câu specific: "Bạn muốn ad copy cho campaign gì? Mục tiêu là gì?"

→ Logic detect "profile đã đủ → skip basic intake" cần code centralize:
```python
def needs_intake(session, task) -> bool:
    if task.skip_intake_if_profile_complete and session.profile.is_ready_for_analysis():
        return False
    return True
```

---

## 🛠 QUY TẮC KHI SỬA CODE (cho Claude session sau này)

Đây là pattern observed cần follow để tiết kiệm token + giảm risk break code:

### ❌ ANTI-PATTERN: Rewrite-from-scratch

Khi user báo lỗi hoặc yêu cầu thay đổi nhỏ, KHÔNG được:
- Viết lại toàn bộ file
- Generate full content mới khi chỉ cần đổi 5-10 dòng
- Dùng `Write` tool để overwrite file khi chỉ cần `Edit` 1 chỗ

**Tại sao tránh:**
- Tốn nhiều tokens không cần thiết (file 300 dòng generate lại = 5000+ tokens)
- Dễ vô tình thay đổi code khác không liên quan (introduce regression)
- Khó review diff — user phải đọc lại cả file thay vì xem 5 dòng đổi

### ✅ PATTERN ĐÚNG: Surgical edit

Khi user báo "X không hoạt động" hoặc "đổi Y thành Z":

**Bước 1: Locate**
- Dùng `Grep` để tìm chính xác chỗ liên quan
- Đọc context xung quanh (5-10 dòng trước/sau) bằng `Read` với offset/limit

**Bước 2: Identify minimum change**
- Xác định nhỏ nhất bao nhiêu dòng phải đổi để fix
- Identify chỗ KHÁC có liên quan (nếu có) — ví dụ: đổi function signature → check tất cả call sites

**Bước 3: Edit precisely**
- Dùng `Edit` tool với `old_string`/`new_string` đúng phần cần đổi
- Nếu nhiều chỗ đổi → nhiều Edit calls riêng biệt, mỗi cái có context rõ ràng
- KHÔNG dùng `Write` overwrite file trừ khi tạo file mới hoặc refactor toàn bộ

**Bước 4: Verify scope**
- Sau khi edit, syntax check
- KHÔNG cần re-read file sau khi Edit (Edit tool đã đảm bảo)

### Ví dụ cụ thể

**User**: "Bot không chạy khi click Phân tích business mới"

**❌ Cách sai:**
```
1. Read toàn bộ bot/handlers.py (400 dòng)
2. Write lại toàn bộ file với fix nằm trong đó
   → 5000+ tokens output
   → Risk: thay đổi format các handler khác
```

**✅ Cách đúng:**
```
1. Grep "restart" trong bot/handlers.py → tìm line 340
2. Read offset=340, limit=15 → xem callback hiện tại
3. Edit chỉ block restart handler (~10 dòng)
   → 300 tokens output
   → Chỉ đổi 1 chỗ, không ảnh hưởng khác
```

### Khi NÀO mới được rewrite-from-scratch:

- ✅ Tạo file mới (chưa tồn tại)
- ✅ Refactor lớn toàn bộ file (user explicit yêu cầu)
- ✅ File quá nát/messy không thể edit surgical (rare)

**Không bao gồm:**
- ❌ Fix 1 bug
- ❌ Thêm 1 feature nhỏ
- ❌ Đổi vài config values
- ❌ Update 1 vài prompts

---

## Branches & Rollback

| Branch | Trạng thái |
|---|---|
| `master` | ✅ Stable — Strategic layer hoàn chỉnh, commit `6a76a4b` (merged from feature/critic-and-modular) |

**Rollback**: Railway → Deployments → chọn commit cũ → instant.

---

## Chạy local

```bash
git clone https://github.com/TimothyMt/marketing-os-bot
cd marketing-os-bot
pip install -r requirements.txt

# .env
ANTHROPIC_API_KEY=sk-ant-...

python simulate.py        # CLI, không cần Telegram/Supabase
python run_local.py       # Bot polling, cần đủ env
```

---

## Recent changes log

| Commit | Mô tả |
|---|---|
| `6a76a4b` | merge: critic + skill modularity + 2-tier model + VN-friendly output |
| `6f4b9db` | feat: Vietnamese-friendly output + clarify SMART/SAVE acronyms |
| `9843698` | fix: restart callback silent fail + global error handler |
| `8d66a47` | config: AGENT_TIMEOUT 180s → 500s |
| `e82a044` | fix: hybrid data discipline + Haiku critic + 180s timeout |
| `f2a84a7` | feat: critic review + skill modularity + 2-tier model |
| `7d470d4` | fix: CSS-only tabs for mobile (no JS) |
| `b3b2f57` | fix: increase max_tokens + tabbed HTML + reorder sections |
| `4185af8` | feat: structured agent output + Telegram cards + HTML report |
| `65d9ca1` | fix: strip code fences from agent outputs |
| `fcff2e8` | fix: prevent pipeline halt when Claude generates malformed markdown |

---

## Bước tiếp theo (Roadmap)

### Operational layer (next major task):
- [ ] **Refactor trước**: Hợp nhất 4 task config dicts → `agents/task_registry.py`
- [ ] **UI refactor**: Multi-tier menu (Chiến lược / Sản xuất / Đánh giá)
- [ ] **AgentSkill enhancements**: output_format, skip_intake_if_profile_complete
- [ ] Thêm skills: ad copy → content calendar → brief → script → performance review

### Optimization:
- [ ] Test với 5-10 founder thật, iterate prompts
- [ ] Re-enable Social Listening khi có web search VN tốt
- [ ] Export PDF report (hiện tại chỉ HTML)
- [ ] Skill versioning để A/B test prompts

### Data lifecycle (chưa gấp):
- [ ] TTL cleanup sessions > 30 ngày trong Supabase
