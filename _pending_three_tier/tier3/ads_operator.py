"""FB Ads Operator — Haiku router + 3 sub-agents (PR-303 + PR-304).

Flow:
  User message → AdsOperatorRouter (Haiku classify) → dispatch to:
    AdsAnalyzerAgent  — Sonnet + Critic, Andromeda 6-layer analysis
    AdsControllerAgent — Haiku, toggle/pause/budget rules
    AdsCreativeAgent  — Sonnet, copy + hook suggestions

Usage:
    router = AdsOperatorRouter()
    route, result = await router.route(ctx)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Literal

from agents.llm_router import router, LLMRequest
from storage.models import Session

logger = logging.getLogger(__name__)

AdsRoute = Literal["analyzer", "controller", "creative", "unknown"]

# ─── Router ─────────────────────────────────────────────────────────

_ROUTER_SYSTEM = """Bạn là router phân loại yêu cầu FB Ads. Trả lời JSON duy nhất: {"route":"<value>","reason":"<1 câu>"}

Routes:
- "analyzer" — phân tích hiệu suất, đọc số liệu, audit, ROAS/CTR/CPM
- "controller" — thay đổi: pause/resume campaign, tăng/giảm budget, tắt ad set
- "creative" — viết copy, hook, gợi ý creative
- "unknown" — không liên quan FB ads

Ví dụ: "phân tích campaign tuần qua"→analyzer | "tắt campaign A"→controller | "viết copy TOFU"→creative"""

# ─── Analyzer ───────────────────────────────────────────────────────

_ANALYZER_SYSTEM = """Bạn là **Performance Analyst** FB Ads — phân tích Andromeda 6-tầng.

## 6 tầng phân tích:
1. **CPM** — Chi phí/1,000 người. Cao > 80K VNĐ = creative/audience sai
2. **CTR** — Tỷ lệ click link. Thấp < 1% = hook yếu
3. **CPC** — Chi phí/click. Cao = CTR thấp hoặc audience không phù hợp
4. **CR Landing Page** — Tỷ lệ chuyển đổi. Thấp = offer/landing yếu
5. **CPLead/CPMessage** — Benchmark ngành VN 2025
6. **ROAS/ROI** — Target ≥ 3x ecommerce, ≥ 2x service

## Nguyên tắc:
- Nhận định → Số liệu → Nguyên nhân → Hành động 48h + 7 ngày
- So 3 chiều: vs mục tiêu / vs tuần trước / vs benchmark VN
- Range, không chính xác: "18–25K" không "21.3K"
- Không claim về performance brand cụ thể

## Benchmark VN 2025:
- FB CPM: 15–40K VNĐ | CTR: 1–3% | CPMessage ecomm: 8–25K | CPMessage service: 20–60K"""

# ─── Controller ─────────────────────────────────────────────────────

_CONTROLLER_SYSTEM = """Bạn là **Ads Controller** — xử lý lệnh thay đổi FB Ads.

Workflow:
1. Xác nhận rõ: action + scope + giá trị
2. User confirm → output JSON action để pipeline thực thi
3. KHÔNG tự thực thi nếu chưa confirm

JSON action format:
{"action":"pause_campaign|resume_campaign|update_budget|pause_adset","target_id":"...","target_name":"...","new_value":null,"confirm_message":"..."}

Quy tắc an toàn:
- Budget thay đổi > 50% → cảnh báo thêm
- Chỉ pause (không xóa)
- Không thay đổi targeting hoặc creative"""

# ─── Creative ───────────────────────────────────────────────────────

_CREATIVE_SYSTEM = """Bạn là **Creative Strategist** FB Ads — viết copy và hook cho thị trường VN.

## Framework:
- Hook 3s (≤125 ký tự đầu): Pain → Câu hỏi → Số sốc → Phản thường thức
- TOFU: awareness — pain point, story thật
- MOFU: consideration — giải pháp, social proof
- BOFU: conversion — offer, urgency, guarantee, CTA cụ thể

## Nguyên tắc:
- 2 phiên bản A/B mỗi request
- Giọng người thật, không giọng quảng cáo
- CTA cụ thể: "Nhắn tin ngay" > "Tìm hiểu thêm"
- KHÔNG impersonate thương hiệu khác
- Flag disclosure AI nếu cần (Nghị định 147/2024)"""


# ─── Context builder ────────────────────────────────────────────────


@dataclass
class AdsContext:
    user_message: str
    session: Session
    ad_account_id: str = ""


async def _build_context_str(ctx: AdsContext) -> str:
    parts = [ctx.session.profile.to_context_string()]
    for key, label in (
        ("synthesis", "Marketing Strategy"),
        ("campaign_brief", "Campaign Brief"),
    ):
        if key in ctx.session.results:
            parts.append(f"## {label}\n{ctx.session.results[key]}")

    if ctx.ad_account_id:
        try:
            from tier3.mcp_client import get_campaigns, get_ad_insights

            campaigns = await get_campaigns(ctx.ad_account_id)
            insights = await get_ad_insights(ctx.ad_account_id)
            if campaigns:
                parts.append(
                    "## Live Campaigns\n"
                    + json.dumps(campaigns[:10], ensure_ascii=False, indent=2)
                )
            if insights:
                parts.append(
                    "## Insights 7 ngày\n"
                    + json.dumps(insights[:20], ensure_ascii=False, indent=2)
                )
        except Exception as e:
            logger.warning("Meta MCP fetch failed: %s", e)
            parts.append("## FB Ads Data\n[Chưa thể lấy data — kiểm tra kết nối Meta MCP]")
    else:
        parts.append(
            "## FB Ads Data\n[Chưa kết nối tài khoản — dùng /connect_fb để phân tích campaign thật]"
        )
    return "\n\n---\n\n".join(parts)


# ─── Sub-agent runners ───────────────────────────────────────────────


async def _run_analyzer(ctx: AdsContext) -> str:
    context_str = await _build_context_str(ctx)

    analysis = (await router.complete(LLMRequest(
        system=_ANALYZER_SYSTEM,
        user=f"{context_str}\n\n---\n\nYêu cầu: {ctx.user_message}",
        max_tokens=4000,
        task_tag="analysis",
    ))).text

    # Critic pass — fast/cheap model checks data quality
    critic_result = await router.complete(LLMRequest(
        system=(
            "Review bản performance analysis này và sửa nếu:\n"
            "- Có số liệu cụ thể không có nguồn → đổi thành range\n"
            "- Claim performance của brand cụ thể → xóa\n"
            "- Thiếu hành động cụ thể → thêm\n"
            "Trả lại bản đã sửa. Nếu ổn, trả lại nguyên văn."
        ),
        user=analysis,
        max_tokens=800,
        task_tag="fast",
    ))
    return critic_result.text


async def _run_controller(ctx: AdsContext) -> str:
    context_str = await _build_context_str(ctx)
    result = await router.complete(LLMRequest(
        system=_CONTROLLER_SYSTEM,
        user=f"{context_str}\n\n---\n\nLệnh: {ctx.user_message}",
        max_tokens=1500,
        task_tag="classify",
    ))
    return result.text


async def _run_creative(ctx: AdsContext) -> str:
    context_str = await _build_context_str(ctx)
    result = await router.complete(LLMRequest(
        system=_CREATIVE_SYSTEM,
        user=f"{context_str}\n\n---\n\nYêu cầu: {ctx.user_message}",
        max_tokens=3000,
        task_tag="creative",
    ))
    return result.text


# ─── Router ─────────────────────────────────────────────────────────


class AdsOperatorRouter:
    """Haiku router — classifies intent, dispatches to correct sub-agent."""

    _UNKNOWN_REPLY = (
        "Tôi là *FB Ads Operator* — chuyên về:\n\n"
        "📊 Phân tích hiệu suất campaign\n"
        "🎛 Điều chỉnh budget/pause/resume\n"
        "✍️ Tạo copy & hook mới\n\n"
        "Hãy mô tả bạn muốn làm gì với FB Ads?"
    )

    async def route(self, ctx: AdsContext) -> tuple[AdsRoute, str]:
        """Classify intent and run the matching sub-agent. Returns (route, result)."""
        route = await self._classify(ctx.user_message)
        logger.info("Ads router: '%s...' → %s", ctx.user_message[:40], route)

        if route == "analyzer":
            return route, await _run_analyzer(ctx)
        if route == "controller":
            return route, await _run_controller(ctx)
        if route == "creative":
            return route, await _run_creative(ctx)
        return "unknown", self._UNKNOWN_REPLY

    async def _classify(self, message: str) -> AdsRoute:
        resp = await router.complete(LLMRequest(
            system=_ROUTER_SYSTEM,
            user=message,
            max_tokens=80,
            task_tag="classify",
            use_cache=False,
        ))
        raw = resp.text.strip()
        try:
            data = json.loads(raw)
            route = data.get("route", "unknown")
            return route if route in ("analyzer", "controller", "creative") else "unknown"
        except (json.JSONDecodeError, KeyError):
            return "unknown"
