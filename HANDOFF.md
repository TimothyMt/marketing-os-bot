# Marketing OS — Handoff Document

> Cập nhật lần cuối: 2026-05-19 (chiều)
> Trạng thái: **Strategic layer ✅ trên master · Operational layer ✅ trên feature/operational-layer (chưa merge, cần test Railway)**

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
│   ├── main.py                       ← Entry point, webhook setup (production)
│   ├── handlers.py                   ← Telegram message + callback logic
│   ├── keyboards.py                  ← Inline keyboards (multi-tier menu) [NEW: ops layer]
│   ├── html_report.py                ← HTML accordion report (strategic + ops single-skill)
│   └── renderers.py                  ← Parse + Telegram card + Markdown/Excel render [NEW]
├── agents/
│   ├── pipeline.py                   ← Orchestration: run_intake, _run_skill, run_operational_skill
│   ├── skills.py                     ← AgentSkill base + enums + 6 strategic concrete skills
│   ├── critic.py                     ← Haiku critic + auto-hyperlink known VN sources
│   ├── prompts.py                    ← Strategic system prompts + intake variants
│   ├── task_registry.py              ← Unified TaskConfig dict (14 tasks) [NEW]
│   ├── output_formats.py             ← 3 OUTPUT_FORMAT instructions + shared rules [NEW]
│   ├── operational_skill.py          ← Generic OperationalSkill class [NEW]
│   ├── operational_prompts.py        ← 8 ops system prompts [NEW]
│   └── operational_skills_config.py  ← Skill factories: 6 generic + 2 subclass [NEW]
├── frameworks/
│   ├── kpi_library.py                ← 8 ngành × KPI benchmarks
│   ├── save_framework.py             ← SAVE framework generator
│   └── smart_framework.py            ← SMART goals templates
├── storage/
│   ├── models.py                     ← Session + VersionedResult + add_result helpers
│   ├── session.py                    ← Supabase read/write (handles backward-compat)
│   └── __init__.py
├── config.py                         ← Env vars + model names + AGENT_TIMEOUT (500s)
├── simulate.py                       ← CLI test
└── run_local.py                      ← Bot polling mode (dev)
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

## ⚠️ TRẠNG THÁI HIỆN TẠI

### `master` branch — Strategic Layer (production, đã deploy)
- ✅ Market Research (TAM/SAM/SOM)
- ✅ Competitor Analysis
- ✅ Customer Insight & ICP
- ✅ Psychology + Pricing Strategy
- ✅ Marketing Strategy Synthesis (SAVE + SMART + 90-day roadmap)

### `feature/operational-layer` branch — Operational Layer (NEW, chờ test + merge)

**8 skills mới đã build, đợi test trên Railway:**

| Cluster | Skill | Output format | Primary deliverable | Critic |
|---|---|---|---|---|
| Planning | `campaign_brief` | Deliverable | HTML | OFF |
| Planning | `content_calendar` | Deliverable | **Excel** (table grid) | OFF |
| Production | `ads_copy` | Deliverable | **Markdown** (cho designer) | OFF |
| Production | `video_scripts` | Deliverable | **Markdown** (cho creator) | OFF |
| Production | `landing_page` | Deliverable | **Markdown** (cho dev) | OFF |
| Production | `sales_inbox_script` | Deliverable | **Markdown** (cho team) | OFF |
| Production | `email_zalo_sequence` | Deliverable | **Markdown** | OFF |
| Analysis | `performance_audit` | **Analysis** (5 sections) | **Excel** (KPI tables) | **ON** |

**Special skills có variant chooser:**
- `ads_copy` — user pick tier trước (TOFU / MOFU / BOFU / Full 3 tầng)
- `video_scripts` — user pick creator type (UGC / EGC / FGC / KOL)

**5 commits trên `feature/operational-layer`:**
```
039d2d3 Phase 1: architecture foundation (enums, AgentSkill expansion, VersionedResult, task_registry)
5e0e48e Phase 2: OperationalSkill generic + 3 output format variants
71ba334 Phase 3: output renderers — HTML/Excel/Markdown
3531cdc Phase 4: 8 operational skills (system prompts + factories + runner)
3f5a8f1 Phase 5: multi-tier UI + single-shot intake + variant choosers
```

---

## 🏗️ ARCHITECTURE OPERATIONAL LAYER

### New files

```
agents/
├── task_registry.py          ← Unified TaskConfig dict (14 tasks, single source of truth)
├── output_formats.py         ← 3 OUTPUT_FORMAT_INSTRUCTION variants + shared rules
├── operational_skill.py      ← Generic OperationalSkill class (config-driven)
├── operational_prompts.py    ← 8 system prompts (Marketing OS branded, no external)
└── operational_skills_config.py  ← Factories: 6 generic + 2 subclass (AdsCopy, VideoScripts)

bot/
└── renderers.py              ← parse_by_format + Telegram card + Markdown/Excel renderers
```

### Key patterns

**1. Enums driving behavior (in `agents/skills.py`):**
```python
class OutputFormat(Enum):       # STRATEGIC_4_SECTION / OPERATIONAL_DELIVERABLE / OPERATIONAL_ANALYSIS
class IntakePattern(Enum):      # MULTI_TURN / SINGLE_SHOT_FORM / NO_INTAKE
class ContextStrategy(Enum):    # PROFILE_ONLY / FULL_PIPELINE / PROFILE_PLUS_STRATEGY / PROFILE_PLUS_CAMPAIGN / PROFILE_PLUS_KPI
class PrimaryDeliverable(Enum): # HTML / EXCEL / MARKDOWN
```

**2. Hybrid skill instantiation:**
- **Generic**: 6 standard ops skills via `OperationalSkill(config)` — config-driven
- **Subclass**: `AdsCopySkill`, `VideoScriptsSkill` — custom logic (tier batching, creator type variants)
- Both implement `AgentSkill` interface so pipeline `_run_skill()` treats them identically

**3. Versioned results (FIFO max 5/skill):**
```python
session.results: dict[skill_key, list[VersionedResult]]
session.add_result(skill_key, content)       # Append new version, FIFO trim
session.get_latest_result(skill_key)         # Get latest content
```
Backward-compat: old `dict[str, str]` auto-wrapped to v1 on load.

**4. Pending intake (single-shot form for ops):**
```python
session.pending_intake: dict[str, str]  # Filled by user template paste
# Special markers:
# - "ops_intake_awaiting": skill_name (set when form sent, cleared after parse)
# - "selected_tiers": "tofu"/"mofu"/"bofu"/"all" (for ads_copy)
# - "creator_type": "ugc"/"egc"/"fgc"/"kol" (for video_scripts)
```

**5. Marketing OS Content Pillar Framework** (replaces Run By Linh):
- 4 Pillars: Educate 35% / Trust 30% / Engage 20% / Convert 15%
- Funnel × Pillar mix matrix (TOFU/MOFU/BOFU per pillar)
- Source mix: UGC 40% / EGC 25% / FGC 15% / Brand 20%

---

## 🧪 TEST PLAN — Trước khi merge vào master

### Bước 1: Deploy feature branch
1. Railway → Service → Settings → Source → Branch = `feature/operational-layer`
2. Trigger redeploy
3. Đợi ~2 phút

### Bước 2: Test smoke flow
1. **`/start`** → phải hiện main menu với 4 nút:
   - 🎯 Chiến lược (Strategic)
   - ⚙️ Sản xuất (Operational)
   - 📊 Đánh giá (Analysis)
   - 🔍 Phân tích toàn diện (Full)

2. **Click "Chiến lược"** → menu 5 strategic skills + nút "← Quay lại"
3. **Click "Sản xuất"** → menu 7 ops skills + back
4. **Click "Đánh giá"** → Performance Audit + back

### Bước 3: Test 1 ops skill đơn giản (Campaign Brief)
1. Click "📋 Campaign Brief"
2. Bot gửi template paste với "mớm lời" example
3. Reply theo format template
4. Bot chạy ~30-60s, gửi:
   - Telegram bullet card
   - File HTML đính kèm

### Bước 4: Test variant chooser
1. Click "✍️ Ads Copy" → phải hiện 4 nút tier (TOFU/MOFU/BOFU/Full)
2. Click "🌐 TOFU" → bot gửi template form
3. Reply template → bot gen ads copy CHỈ tier TOFU + gửi HTML + Markdown

### Bước 5: Test Excel output
1. Click "📅 Content Calendar"
2. Fill form → bot gen calendar + gửi HTML + **Excel**
3. Mở Excel → check tables render đúng

### Bước 6: Test Performance Audit (có critic)
1. Click "📈 Performance Audit"
2. Paste data campaign (theo template với KPI dump)
3. Bot chạy ~60-90s (Sonnet agent + Haiku critic + Excel render)
4. Output format = Analysis (Verdict + KPI table + Root Cause + Next Actions + Forecast)

### Bước 7: Test brand context reuse
1. Chạy strategic phase trước (`Marketing Strategy`)
2. Sau đó chạy `Campaign Brief` — phải có context từ synthesis (không hỏi lại profile)
3. Sau đó chạy `Sales/Inbox Script` — phải có context từ Campaign Brief (tone phù hợp)

---

## ⚠️ ĐIỂM CẦN CHÚ Ý KHI TEST

### Có thể gặp issue:

1. **Single-shot intake parser** — nếu user reply không đúng format template:
   - Parser sẽ extract những gì matched
   - Field missing → template fallback "[missing: field_name]"
   - **Solution if buggy**: Cải thiện regex trong `_parse_single_shot_intake()` (bot/handlers.py)

2. **Excel render** — yêu cầu `openpyxl` đã trong requirements
   - Nếu Railway log error import → check `pip install` đã chạy
   - Excel chỉ render nếu agent output có markdown tables

3. **Critic timeout** — chỉ apply cho performance_audit
   - Agent Sonnet ~60-90s + Haiku critic ~15-20s = ~110s total
   - Timeout hiện 500s → có buffer rộng

4. **HTML render trên mobile** — tabs là CSS-only (radio buttons), no JS
   - Test trên Telegram in-app browser + Chrome mobile

5. **Versioning growth** — mỗi skill chạy lại = +1 version
   - FIFO max 5 → cap storage ~30KB/skill/user
   - Watch Supabase storage usage sau 1 tuần test

### Việc cần làm sau khi test xong:

| Status | Việc | Note |
|---|---|---|
| TODO | Test 8 ops skills end-to-end | Theo bước 2-7 trên |
| TODO | Iterate prompts dựa trên output thực | Nhất là `content_calendar` cần check Pillar mix có hợp lý cho VN F&B |
| TODO | Verify Excel render cho `content_calendar` + `performance_audit` | Mở file Excel kiểm tra |
| TODO | Verify Markdown render cho 5 production skills | Mở .md để check usable |
| TODO | Merge `feature/operational-layer` → `master` | Sau khi test pass |
| TODO | Xoá branch sau merge | `git branch -d feature/operational-layer` |

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

### feature/operational-layer (chưa merge — 5 commits)
| Commit | Mô tả |
|---|---|
| `3f5a8f1` | Phase 5: multi-tier UI + single-shot intake + variant choosers |
| `3531cdc` | Phase 4: 8 operational skills (system prompts + factories + runner) |
| `71ba334` | Phase 3: output renderers — HTML/Excel/Markdown |
| `5e0e48e` | Phase 2: OperationalSkill generic + 3 output format variants |
| `039d2d3` | Phase 1: architecture foundation (enums, AgentSkill, VersionedResult, task_registry) |

### master (đã deploy production)
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

### Tối nay — Test + Merge Operational Layer
- [ ] Deploy `feature/operational-layer` lên Railway (đổi branch trong Settings)
- [ ] Test 8 ops skills theo bước 2-7 ở section "TEST PLAN"
- [ ] Note ra bug/improvement cần fix
- [ ] Iterate prompts nếu output chưa đủ depth (đặc biệt `content_calendar` cho VN F&B/beauty)
- [ ] Merge `feature/operational-layer` → `master` khi pass tests
- [ ] Xoá branch sau merge

### Tuần này — Polish & Real test
- [ ] Test với 1-2 founder thật (chạy full workflow Strategic → Operational)
- [ ] Tune prompt cho skill nào output yếu
- [ ] Check Supabase storage usage sau 1 tuần dùng thật
- [ ] Decide: cần thêm skill nào không (vd: KOL contract template separate)

### Sau test xong — Optimization
- [ ] Re-enable Social Listening khi có web search VN tốt
- [ ] Export PDF report (hiện chỉ HTML/Excel/Markdown)
- [ ] A/B test prompts (versioning đã có sẵn)
- [ ] Add analytics: skill usage frequency, time-to-result, NPS sau mỗi skill

### Data lifecycle (chưa gấp)
- [ ] TTL cleanup sessions > 30 ngày trong Supabase
- [ ] Monitor pending_intake leak (nếu user bỏ giữa form, marker không cleared)
