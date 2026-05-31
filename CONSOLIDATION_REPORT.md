# Báo cáo Hợp nhất — nice-gates làm gốc

> Branch: `integration/consolidated` (gốc = nice-gates).
> Mục đích: gom three-tier + viral-analyzer + master vào nice-gates.
> File này liệt kê điểm TRÙNG để bạn quyết định giữ bản nào.

---

## A. MASTER — không đóng góp gì
Master không có file nào mà nice-gates thiếu. **Bỏ qua hoàn toàn.**

---

## B. CLEAN ADD — không cần quyết, thêm thẳng
Từ `viral-analyzer` (chỉ 2 file, nice-gates chưa có):
- `tools/video_vision.py` — vision phân tích video
- `tools/krillin_client.py` — client viral analyzer

⚠️ Cần kèm wiring skill viral vào `task_registry.py` + `handlers.py` (port thêm).

---

## C. FEATURE OVERLAP — three-tier vs nice-gates (CẦN BẠN QUYẾT)

Mỗi dòng = 1 feature mà CẢ HAI đều có, khác implementation:

| # | Feature | three-tier | nice-gates | Khuyến nghị |
|---|---|---|---|---|
| 1 | Multi-LLM router | `agents/llm_router.py` | `tools/llm_router.py` (failover + token tracking) | **nice-gates** (mature hơn) |
| 2 | Theo dõi đối thủ | Spy Radar: `spy_store/poller/worker` + MCP, interval 6/12/24h | `tracked_competitors.py` + `workers/monitor_competitors.py` | ⚖️ **QUYẾT** — cách làm khác hẳn |
| 3 | FB Ads | `tier3/ads_operator.py` (MCP, chưa verify) | `fb_marketing.py` + `fb_ads_library.py` (Graph API thật) | **nice-gates** (API thật) |
| 4 | Multi-campaign | `campaign_store.py` (bảng campaigns) | `campaign_history.py` + `v2/campaigns_v2.py` | ⚖️ **QUYẾT** |
| 5 | Campaign intake | `campaign_intake.py` (87 dòng) | `campaign_intake.py` (337) + `campaign_scope_library.py` | **nice-gates** (giàu hơn) |
| 6 | Pipeline structure | tier2/tier3 tuần tự | `task_registry` + `operational_skill` | **nice-gates** (registry) |

---

## D. PURE DATA MERGE — bổ sung, khuyến nghị rõ

| File | three-tier | nice-gates | Khuyến nghị |
|---|---|---|---|
| `frameworks/kpi_library.py` | **14 ngành** | 7 ngành | **Lấy three-tier** — superset (đủ 7 ngành nice-gates + 7 ngành mới: health_clinic, agency, fashion_retail, travel_hospitality, interior_design, pet_care, events_wedding). Cần verify dataclass `KPIFramework` khớp field. |
| `config.py` | thêm: FERNET_KEY, GEMINI_API_KEY, META_*, GRAPH_API_VERSION, SPY_CHECK_INTERVAL | thêm: ADMIN_IDS, DB_V2, FB_*, GPT_*, USE_MULTI_AGENT_PIPELINE | **UNION** cả hai (gộp biến của 2 bên) |

---

## E. ARCHITECTURE CORE — nice-gates thắng (vì là gốc)

21 file core trùng tên khác nội dung. Vì chọn nice-gates làm gốc, các file này **giữ nguyên nice-gates**, chỉ sửa khi port feature cần:

`handlers.py` (5410 vs 1274) · `pipeline.py` · `prompts.py` · `skills.py` · `models.py` · `session.py` · `keyboards.py` · `main.py` · `html_report.py` · `critic.py` · `__init__.py` các package

---

## KẾT LUẬN — việc thực sự cần làm rất ÍT

Vì nice-gates đã làm tốt/đầy đủ hơn ở hầu hết feature, hợp nhất chỉ còn:

1. ✅ **Port kpi_library 14 ngành** từ three-tier (data thuần, lợi rõ)
2. ✅ **Union config.py** (gộp env vars 2 bên)
3. ✅ **Port viral video analyzer** từ viral-analyzer (2 tool + wiring)
4. ⚖️ **QUYẾT #2 (theo dõi đối thủ)**: Spy Radar three-tier (interval user-set, MCP) HAY monitor_competitors nice-gates?
5. ⚖️ **QUYẾT #4 (multi-campaign)**: campaign_store three-tier HAY campaign_history nice-gates?

→ Các phần còn lại của three-tier (llm_router, ads_operator, campaign_intake, tier pipeline) là **reimplementation thừa** — nice-gates đã có bản tốt hơn. Khuyến nghị BỎ.

---

## 2 câu hỏi cần bạn trả lời

**Q1 — Theo dõi đối thủ:** giữ Spy Radar (three-tier) hay monitor_competitors (nice-gates)?
**Q2 — Multi-campaign:** giữ campaign_store (three-tier) hay campaign_history/v2 (nice-gates)?
