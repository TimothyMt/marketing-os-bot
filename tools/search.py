"""
Tavily web search wrapper for pipeline agents.
"""
import logging
from tavily import AsyncTavilyClient
from config import TAVILY_API_KEY

logger = logging.getLogger(__name__)

_client: AsyncTavilyClient | None = None


def get_client() -> AsyncTavilyClient:
    global _client
    if _client is None:
        _client = AsyncTavilyClient(api_key=TAVILY_API_KEY)
    return _client


async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web and return formatted results as a string."""
    if not TAVILY_API_KEY:
        return "Web search không khả dụng (thiếu TAVILY_API_KEY)."
    try:
        client = get_client()
        response = await client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
        )
        results = response.get("results", [])
        if not results:
            return f"Không tìm thấy kết quả cho: {query}"

        parts = []
        for r in results:
            title = r.get("title", "")
            url = r.get("url", "")
            content = r.get("content", "")[:600]
            parts.append(f"[{title}]({url})\n{content}")
        return "\n\n---\n\n".join(parts)
    except Exception as e:
        logger.warning("Tavily search error for '%s': %s", query, e)
        return f"Lỗi tìm kiếm: {str(e)[:150]}"


async def search_brand_candidates(brand_name: str) -> list[dict]:
    """Search for brand and return up to 4 distinct candidates.
    Runs 2 parallel queries (general + Vietnam-context) to catch both
    international brands and local Vietnamese businesses.
    """
    if not TAVILY_API_KEY:
        return []
    import asyncio
    from urllib.parse import urlparse

    client = get_client()

    async def _do_search(query: str) -> list[dict]:
        try:
            resp = await client.search(query=query, max_results=6, search_depth="basic")
            return resp.get("results", []) or []
        except Exception as e:
            logger.warning("Tavily search error for '%s': %s", query, e)
            return []

    try:
        # Parallel: catch international brands + local VN businesses
        results_a, results_b = await asyncio.gather(
            _do_search(brand_name),
            _do_search(f"{brand_name} Việt Nam"),
        )
        all_results = results_a + results_b

        seen_domains: set[str] = set()
        candidates: list[dict] = []
        for r in all_results:
            url = r.get("url", "")
            domain = urlparse(url).netloc.replace("www.", "")
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)

            title = r.get("title", "")
            # Strip common suffixes: "Brand - tagline | site"
            clean_name = title.split(" - ")[0].split(" | ")[0].split(" – ")[0].strip()
            if len(clean_name) > 60 or not clean_name:
                clean_name = brand_name

            description = r.get("content", "")[:150].strip()
            candidates.append({
                "name": clean_name,
                "description": description,
                "url": url,
                "domain": domain,
            })
            if len(candidates) >= 4:
                break

        return candidates
    except Exception as e:
        logger.warning("search_brand_candidates error for '%s': %s", brand_name, e)
        return []


# Claude tool definition
WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": (
        "Tìm kiếm thông tin trên web. Dùng để research brand, công ty, đối thủ cạnh tranh, "
        "số liệu thị trường, social mentions, giá cả. Kết quả là thông tin thực từ internet."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Câu truy vấn tìm kiếm. Nên cụ thể, bao gồm tên brand/ngành/địa điểm nếu có.",
            }
        },
        "required": ["query"],
    },
}
