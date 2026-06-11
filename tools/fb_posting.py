"""Đăng bài lên Facebook Page qua Graph API — dùng Page Access Token
(manual-token connection system, storage/fb_connections.py).
"""
import logging

import httpx

from config import GRAPH_API_VERSION

logger = logging.getLogger(__name__)

GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


async def post_to_page(
    page_id: str,
    page_access_token: str,
    message: str,
    image_bytes: bytes | None = None,
    image_url: str | None = None,
    link: str | None = None,
) -> dict:
    """Đăng bài text (kèm link preview) hoặc ảnh lên Page.

    `image_bytes` (upload trực tiếp) được ưu tiên hơn `image_url` (FB tự fetch URL —
    chỉ dùng cho URL công khai, không chứa thông tin nhạy cảm).

    Raises RuntimeError nếu FB trả về lỗi.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        if image_bytes:
            resp = await client.post(
                f"{GRAPH_BASE}/{page_id}/photos",
                data={"caption": message, "access_token": page_access_token},
                files={"source": ("image.jpg", image_bytes)},
            )
        elif image_url:
            resp = await client.post(
                f"{GRAPH_BASE}/{page_id}/photos",
                data={
                    "url": image_url,
                    "caption": message,
                    "access_token": page_access_token,
                },
            )
        else:
            data = {"message": message, "access_token": page_access_token}
            if link:
                data["link"] = link
            resp = await client.post(f"{GRAPH_BASE}/{page_id}/feed", data=data)

        result = resp.json()
        if "error" in result:
            err = result["error"]
            raise RuntimeError(err.get("message", "Đăng bài FB thất bại"))
        return result
