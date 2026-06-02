"""
Dreamer — orchestration cho Dream Engine.

Luồng:
  1. gather_memory(user_id)  → gom ký ức: campaign history + brand voice + đối thủ.
  2. generate_dreams(...)     → llm_router sinh 3 ý tưởng (JSON), dedupe theo signature.
  3. expand_dream(...)        → mở rộng 1 ý tưởng thành mini campaign plan.

Ánh xạ khái niệm AI dreaming:
  - generative replay  → campaign_history
  - latent imagination → llm_router mô phỏng ý tưởng không tốn ad spend
  - deepdream          → brand_voice + động thái đối thủ khuếch đại
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from tools.llm_router import call, TaskType
from storage.campaign_history import get_latest_campaign
from storage.brand_voice import get_brand_voice
from storage.tracked_competitors import list_tracked_by_user
from storage.dreams import recent_signatures, make_signature
from agents.dream_prompts import (
    DREAM_SYSTEM,
    DREAM_EXPAND_SYSTEM,
    build_dream_user_msg,
    build_expand_user_msg,
)

logger = logging.getLogger(__name__)

# Cap text dài để tránh bloat token khi ghép memory block
_MAX_FIELD_CHARS = 1500


def _truncate(text: Optional[str], n: int = _MAX_FIELD_CHARS) -> str:
    if not text:
        return ""
    return text[:n] if len(text) > n else text


async def gather_memory(user_id: int) -> Optional[str]:
    """
    Gom 3 nguồn ký ức thành 1 context block. Returns None nếu KHÔNG có ký ức
    đáng kể (không có campaign history → bot không có gì để mơ).
    """
    campaign = await get_latest_campaign(user_id)
    if not campaign:
        return None  # Không có ký ức nền → skip user này

    parts: list[str] = ["## 🧠 Ký ức: Business & Chiến lược gần nhất"]
    label_map = {
        "business_name":    "Business",
        "industry":         "Ngành",
        "stage":            "Stage",
        "primary_goal":     "Mục tiêu chính",
        "usp":              "USP",
    }
    for key, label in label_map.items():
        val = campaign.get(key)
        if val:
            parts.append(f"- {label}: {val}")

    for key, label in (
        ("synthesis",        "## 🧠 Ký ức: Marketing Strategy (synthesis)"),
        ("customer_insight", "## 🧠 Ký ức: Customer Insight"),
        ("competitor",       "## 🧠 Ký ức: Phân tích đối thủ (đã làm)"),
    ):
        val = _truncate(campaign.get(key))
        if val:
            parts.append(f"{label}\n{val}")

    # Brand voice (nếu có)
    try:
        bv = await get_brand_voice(user_id)
        if bv and not bv.is_empty():
            parts.append(bv.to_prompt_block(max_chars=1200))
    except Exception as e:
        logger.debug("gather_memory brand_voice skip (user=%d): %s", user_id, e)

    # Đối thủ đang theo dõi + động thái gần đây
    try:
        tracked = await list_tracked_by_user(user_id)
        if tracked:
            lines = ["## 🧠 Ký ức: Đối thủ đang theo dõi (Spy Radar)"]
            for t in tracked[:8]:
                name = t.get("page_name") or "đối thủ"
                n_ads = len(t.get("last_ad_ids") or [])
                lines.append(f"- {name}: hiện đang chạy ~{n_ads} ads (theo dõi qua FB Ads Library)")
            parts.append("\n".join(lines))
    except Exception as e:
        logger.debug("gather_memory tracked skip (user=%d): %s", user_id, e)

    return "\n\n".join(parts)


def _parse_dreams_json(raw: str) -> list[dict]:
    """Robust parse JSON object {dreams:[...]} từ output LLM (có thể lẫn markdown fence)."""
    if not raw:
        return []
    text = raw.strip()
    # Bóc ```json ... ``` fence nếu có
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # Tìm JSON object đầu tiên
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        text = brace.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("dream JSON parse failed: %s | raw head: %s", e, raw[:200])
        return []
    dreams = data.get("dreams") if isinstance(data, dict) else None
    if not isinstance(dreams, list):
        return []
    # Sanitize từng dream
    cleaned: list[dict] = []
    for d in dreams:
        if not isinstance(d, dict):
            continue
        title = (d.get("title") or "").strip()
        if not title:
            continue
        cleaned.append({
            "title":       title,
            "angle":       (d.get("angle") or "").strip(),
            "why_now":     (d.get("why_now") or "").strip(),
            "first_step":  (d.get("first_step") or "").strip(),
            "inspired_by": (d.get("inspired_by") or "mix").strip(),
            "impact":      (d.get("impact") or "medium").strip().lower(),
        })
    return cleaned


async def generate_dreams(user_id: int, memory_block: str) -> list[dict]:
    """
    Sinh 3 ý tưởng từ memory block. Dedupe với dreams đã mơ trước đó (signature).
    Returns list dream dicts (có thể < 3 sau dedupe). Raise nếu LLM fail hoàn toàn.
    """
    avoid_sigs = set(await recent_signatures(user_id, limit=40))
    # avoid_titles cho prompt: ta chỉ có signatures — vẫn hữu ích như gợi ý tránh lặp
    result = await call(
        task_type=TaskType.GENERIC_CREATIVE,
        system=DREAM_SYSTEM,
        user=build_dream_user_msg(memory_block, avoid_titles=list(avoid_sigs)),
        max_tokens=2500,
    )
    dreams = _parse_dreams_json(result.get("output", ""))

    # Dedupe theo signature
    fresh: list[dict] = []
    seen_now: set[str] = set()
    for d in dreams:
        sig = make_signature(d["title"])
        if sig in avoid_sigs or sig in seen_now:
            continue
        seen_now.add(sig)
        fresh.append(d)
    return fresh


async def expand_dream(dream: dict, memory_block: str) -> str:
    """Mở rộng 1 dream → mini campaign plan (markdown)."""
    result = await call(
        task_type=TaskType.GENERIC_CREATIVE,
        system=DREAM_EXPAND_SYSTEM,
        user=build_expand_user_msg(dream, memory_block),
        max_tokens=3000,
    )
    return result.get("output", "").strip()
