# _pending_three_tier — Backup code từ branch three-tier

> Giữ lại theo yêu cầu, KHÔNG xoá. Đây là các module của branch
> `claude/marketing-os-three-tier-RHBLx` mà quá trình hợp nhất (nice-gates làm gốc)
> đã quyết KHÔNG dùng — nhưng để dành phòng khi cần tham khảo/khôi phục.

## ⚠️ Lưu ý
- Thư mục này nằm NGOÀI package path (có dấu `_` đầu) → Python KHÔNG import,
  KHÔNG ảnh hưởng app đang chạy.
- Các file này import từ `storage.models` / `storage.session` / `config` của
  **kiến trúc three-tier** — KHÔNG chạy được trực tiếp trên nice-gates nếu copy
  thẳng ra. Muốn dùng lại phải adapt sang model/session của nice-gates.

## Vì sao không dùng (đã có bản tương đương tốt hơn ở nice-gates)
| File backup | nice-gates đã có |
|---|---|
| tier3/ads_operator.py, mcp_client.py | tools/fb_marketing.py + fb_ads_library.py (Graph API thật) |
| agents/tier2_*, tier3_* (pipeline/prompts/skills) | task_registry + operational_skill |
| storage/campaign_store.py | storage/campaign_history.py + v2/campaigns_v2.py |
| storage/spy_store.py, workers/spy_poller.py, spy_worker.py | workers/monitor_competitors.py + tracked_competitors.py |
| storage/crypto.py | (token lưu qua FB_ACCESS_TOKEN env, chưa cần per-user crypto) |

## Nội dung
```
tier3/ads_operator.py        — FB Ads Operator (Haiku router + 3 sub-agent, MCP CHƯA verify)
tier3/mcp_client.py          — Meta @meta/ads-cli MCP wrapper
agents/tier2_pipeline.py     — Campaign Brief + Content Calendar pipeline
agents/tier2_prompts.py      — prompt 9-phần campaign brief, 11-cột calendar
agents/tier2_skills.py       — CampaignBriefSkill, ContentCalendarSkill
agents/tier3_pipeline.py     — Ad copy / video / UGC / email pipeline
agents/tier3_prompts.py      — prompt tier 3
agents/tier3_skills.py       — skill tier 3
storage/campaign_store.py    — bảng campaigns phẳng (multi-campaign)
storage/spy_store.py         — CRUD spy_targets/spy_cache/fb_credentials
storage/crypto.py            — Fernet encrypt FB token
workers/spy_poller.py        — poll + Haiku analyze competitor ads
workers/spy_worker.py        — APScheduler entry (Railway Service #2)
storage/migrations/000_fresh_setup.sql   — schema sessions/spy/fb_credentials
storage/migrations/001_add_campaigns.sql — bảng campaigns
storage/migrations/002_campaign_profile_col.sql — cột campaign_profile
```

## Khôi phục
Bản gốc đầy đủ vẫn nằm ở branch `origin/claude/marketing-os-three-tier-RHBLx`
(lịch sử git còn nguyên). Thư mục backup này chỉ để tiện tham khảo tại chỗ.
