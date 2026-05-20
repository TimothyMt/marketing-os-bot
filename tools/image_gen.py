"""
OpenAI Image Generation wrapper — gpt-image-1.
Used by Ads Generator skill when user wants to generate actual images from brief.

Cost reference (2026 pricing):
- 1024x1024 standard: $0.04/image
- 1024x1024 HD: $0.08/image
- 1024x1536 (vertical, story): $0.06/image
- 1536x1024 (horizontal, feed): $0.06/image
"""
import io
import base64
import logging
from typing import Optional

from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

_openai_client = None


def _get_client():
    """Lazy init OpenAI async client."""
    global _openai_client
    if _openai_client is None:
        try:
            from openai import AsyncOpenAI
            _openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        except ImportError:
            logger.error("openai package not installed — add 'openai' to requirements.txt")
            raise
    return _openai_client


async def generate_image(
    prompt: str,
    size: str = "1024x1024",
    quality: str = "standard",
    n: int = 1,
) -> list[bytes]:
    """Generate image(s) via OpenAI gpt-image-1.

    Args:
        prompt: Image description (English works best, but VN works too)
        size: "1024x1024" (square) / "1024x1536" (vertical, story) / "1536x1024" (horizontal, feed)
        quality: "standard" ($0.04) or "hd" ($0.08)
        n: number of images (1-4)

    Returns:
        List of image bytes (PNG format)
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY chưa setup trong env vars")

    client = _get_client()

    response = await client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size=size,
        quality=quality,
        n=n,
    )

    images_bytes = []
    for img in response.data:
        # gpt-image-1 returns b64_json by default
        if img.b64_json:
            images_bytes.append(base64.b64decode(img.b64_json))
        elif img.url:
            # Fallback if URL returned
            import httpx
            async with httpx.AsyncClient() as h:
                r = await h.get(img.url)
                images_bytes.append(r.content)

    return images_bytes


def estimate_cost(quality: str, size: str, n: int) -> float:
    """Estimate USD cost for image generation."""
    base_cost = {
        ("standard", "1024x1024"): 0.04,
        ("standard", "1024x1536"): 0.06,
        ("standard", "1536x1024"): 0.06,
        ("hd", "1024x1024"): 0.08,
        ("hd", "1024x1536"): 0.12,
        ("hd", "1536x1024"): 0.12,
    }
    return base_cost.get((quality, size), 0.04) * n


def is_available() -> bool:
    """Check if image gen is configured."""
    return bool(OPENAI_API_KEY)
