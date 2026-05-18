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
    """Search for brand and return up to 4 distinct candidates."""
    if not TAVILY_API_KEY:
        return []
    try:
        from urllib.parse import urlparse
        client = get_client()
        response = await client.search(
            query=brand_name,
            max_results=10,
            search_depth="basic",
        )
        results = response.get("results", [])

        seen_domains: set[str] = set()
        candidates: list[dict] = []
        for r in results:
            url = r.get("url", "")
            domain = urlparse(url).netloc.replace("www.", "")
            if domain in seen_domains:
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
