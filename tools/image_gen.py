"""
OpenAI Image Generation wrapper — gpt-image-2.
Used by Ads Generator skill when user wants to generate actual images from brief.

Cost reference (2026 pricing):
- quality "low"    1024x1024: ~$0.02/image
- quality "medium" 1024x1024: ~$0.07/image
- quality "high"   1024x1024: ~$0.19/image
- quality "auto"   → OpenAI tự chọn tối ưu
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
    quality: str = "medium",
    n: int = 1,
) -> list[bytes]:
    """Generate image(s) via OpenAI gpt-image-2.

    Args:
        prompt: Image description (English works best, but VN works too)
        size: "1024x1024" (square) / "1024x1536" (vertical, story) / "1536x1024" (horizontal, feed)
        quality: "low" (~$0.02) / "medium" (~$0.07) / "high" (~$0.19) / "auto"
        n: number of images (1-4)

    Returns:
        List of image bytes (PNG format)
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY chưa setup trong env vars")

    client = _get_client()

    response = await client.images.generate(
        model="gpt-image-2",
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
    """Estimate USD cost for gpt-image-2 generation."""
    base_cost = {
        ("low",    "1024x1024"):  0.02,
        ("low",    "1024x1536"):  0.03,
        ("low",    "1536x1024"):  0.03,
        ("medium", "1024x1024"):  0.07,
        ("medium", "1024x1536"):  0.10,
        ("medium", "1536x1024"):  0.10,
        ("high",   "1024x1024"):  0.19,
        ("high",   "1024x1536"):  0.25,
        ("high",   "1536x1024"):  0.25,
        ("auto",   "1024x1024"):  0.07,
        ("auto",   "1024x1536"):  0.10,
        ("auto",   "1536x1024"):  0.10,
    }
    return base_cost.get((quality, size), 0.07) * n


def is_available() -> bool:
    """Check if image gen is configured."""
    return bool(OPENAI_API_KEY)
