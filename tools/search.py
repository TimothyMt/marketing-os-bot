"""
Google Custom Search Engine (CSE) wrapper for pipeline agents.
CSE được setup với curated list of VN sites → mọi search đều VN-focused.
"""
import logging
import httpx
from config import GOOGLE_API_KEY, GOOGLE_CSE_ID

logger = logging.getLogger(__name__)
CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=15.0)
    return _client


async def _do_cse_search(query: str, num: int = 5) -> list[dict]:
    """Raw Google CSE call. Returns list of result items (or [] on failure)."""
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return []
    params = {
        "key": GOOGLE_API_KEY,
        "cx":  GOOGLE_CSE_ID,
        "q":   query,
        "num": min(max(num, 1), 10),  # Google CSE max 10 per request
        "gl":  "vn",  # geolocation: Vietnam
        "hl":  "vi",  # interface language: Vietnamese
    }
    try:
        client = get_client()
        resp = await client.get(CSE_ENDPOINT, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", []) or []
    except httpx.HTTPStatusError as e:
        logger.warning("Google CSE HTTP %s for '%s': %s",
                       e.response.status_code, query, e.response.text[:200])
        return []
    except Exception as e:
        logger.warning("Google CSE error for '%s': %s", query, e)
        return []


async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web and return formatted results as a string for agents."""
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return "Web search không khả dụng (thiếu Google CSE credentials)."

    items = await _do_cse_search(query, num=max_results)
    if not items:
        return f"Không tìm thấy kết quả cho: {query}"

    parts = []
    for r in items:
        title = r.get("title", "")
        url = r.get("link", "")
        snippet = (r.get("snippet") or "")[:600]
        parts.append(f"[{title}]({url})\n{snippet}")
    return "\n\n---\n\n".join(parts)


async def search_brand_candidates(brand_name: str) -> list[dict]:
    """Search brand candidates from curated VN sites via Google CSE.
    Returns up to 4 distinct candidates (deduped by domain).
    """
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return []
    from urllib.parse import urlparse

    items = await _do_cse_search(brand_name, num=10)
    if not items:
        return []

    seen_domains: set[str] = set()
    candidates: list[dict] = []
    for r in items:
        url = r.get("link", "")
        domain = urlparse(url).netloc.replace("www.", "")
        if not domain or domain in seen_domains:
            continue
        seen_domains.add(domain)

        title = r.get("title", "")
        # Strip common title suffixes
        clean_name = title.split(" - ")[0].split(" | ")[0].split(" – ")[0].strip()
        if len(clean_name) > 60 or not clean_name:
            clean_name = brand_name

        snippet = (r.get("snippet") or "")[:150].strip()
        candidates.append({
            "name": clean_name,
            "description": snippet,
            "url": url,
            "domain": domain,
        })
        if len(candidates) >= 4:
            break

    return candidates


# Claude tool definition (interface giữ nguyên — pipeline.py không cần đổi)
WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": (
        "Tìm kiếm thông tin trên web Việt Nam. Dùng để research brand, công ty, "
        "đối thủ cạnh tranh, số liệu thị trường, social mentions, giá cả. "
        "Kết quả là thông tin thực từ các site VN uy tín."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Câu truy vấn tìm kiếm. Cụ thể, bao gồm tên brand/ngành nếu có.",
            }
        },
        "required": ["query"],
    },
}
