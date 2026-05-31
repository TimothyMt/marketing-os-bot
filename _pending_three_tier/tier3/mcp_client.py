"""Shared Meta MCP client helper.

Wraps @meta/ads-cli via stdio_client for all ads_operator sub-agents.
Each call opens a fresh MCP session — stateless, safe for concurrent use.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def call_meta_tool(
    tool_name: str,
    args: dict[str, Any],
    *,
    timeout: float = 30.0,
) -> Any:
    """Call a single Meta MCP tool and return parsed result.

    Returns None if mcp package is absent (feature degrades gracefully).
    Raises on network/tool errors so callers can surface them.
    """
    try:
        from contextlib import AsyncExitStack
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        logger.warning("mcp package not installed — Meta MCP unavailable")
        return None

    async with AsyncExitStack() as stack:
        params = StdioServerParameters(command="npx", args=["-y", "@meta/ads-cli"])
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()

        result = await asyncio.wait_for(
            session.call_tool(tool_name, args),
            timeout=timeout,
        )
        if result.content:
            first = result.content[0]
            if hasattr(first, "text"):
                try:
                    return json.loads(first.text)
                except json.JSONDecodeError:
                    return first.text
    return None


async def get_campaigns(ad_account_id: str) -> list[dict]:
    return await call_meta_tool("get_campaigns", {"account_id": ad_account_id}) or []


async def get_ad_insights(
    ad_account_id: str,
    date_preset: str = "last_7d",
    level: str = "ad",
) -> list[dict]:
    return (
        await call_meta_tool(
            "get_insights",
            {"account_id": ad_account_id, "date_preset": date_preset, "level": level},
        )
        or []
    )


async def get_page_ads(page_id_or_url: str) -> list[dict]:
    """Fetch active ads from a competitor's public page (Spy Radar).

    page_id_or_url: FB page URL or numeric page ID.
    """
    return (
        await call_meta_tool("get_page_ads", {"page_id": page_id_or_url})
        or []
    )
