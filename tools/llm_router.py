"""
Multi-Provider LLM Router (Sprint 8.3 stub).

Single entry point cho mọi LLM call. Routing decision based on `task_type`:
- Mỗi TaskType có routing chain (primary → fallback1 → fallback2)
- Auto failover khi provider raise RateLimitError / ProviderUnavailable
- Token tracking + provider monitoring built-in

S8.3 scope:
- ✅ Provider enum + TaskType enum
- ✅ ROUTING_TABLE config-driven
- ✅ Working Anthropic Sonnet + Haiku paths
- ⏳ Gemini Pro/Flash: stub (NotImplementedError) — wire khi có GEMINI_API_KEY (S8.7)
- ⏳ OpenAI GPT-4o/mini: stub — wire khi có OPENAI_API_KEY
- ⏳ Perplexity Sonar: stub — wire khi có PERPLEXITY_API_KEY

Backward compat: nếu router không gọi được (chưa wire), fallback xuống Anthropic
Sonnet — pipeline hiện tại vẫn chạy.
"""
from __future__ import annotations

import logging
import os
import time
from enum import Enum
from typing import Optional

import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_SONNET_MODEL, CLAUDE_HAIKU_MODEL

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# Provider enum
# ─────────────────────────────────────────────────────────────────

class Provider(str, Enum):
    """Available LLM providers. Order matters: primary first, fallbacks after."""
    ANTHROPIC_SONNET   = "anthropic_sonnet"      # claude-sonnet-4-6
    ANTHROPIC_HAIKU    = "anthropic_haiku"       # claude-haiku-4-5
    GEMINI_PRO         = "gemini_pro"            # gemini-2.5-pro (1M context)
    GEMINI_FLASH       = "gemini_flash"          # gemini-2.5-flash (cheap)
    OPENAI_GPT4O       = "openai_gpt4o"          # gpt-4o (structured)
    OPENAI_GPT4O_MINI  = "openai_gpt4o_mini"     # gpt-4o-mini (bulk cheap)
    PERPLEXITY_SONAR   = "perplexity_sonar"      # research + citations


# ─────────────────────────────────────────────────────────────────
# TaskType enum — semantic intent của call
# ─────────────────────────────────────────────────────────────────

class TaskType(str, Enum):
    # Strategic stages
    MARKET_RESEARCH_DATA      = "market_research_data"       # → Perplexity primary
    MARKET_RESEARCH_NARRATIVE = "market_research_narrative"  # → Haiku VN polish
    COMPETITOR_RESEARCH       = "competitor_research"
    COMPETITOR_MATRIX         = "competitor_matrix"
    CUSTOMER_INSIGHT          = "customer_insight"
    PSYCHOLOGY                = "psychology"
    PRICING_MATH              = "pricing_math"
    USP_CREATIVE              = "usp_creative"
    RETENTION_MATRIX          = "retention_matrix"
    WINBACK_STRATEGY          = "winback_strategy"
    SYNTHESIS_LONG_CONTEXT    = "synthesis_long_context"     # → Gemini Pro primary

    # Operational
    INTAKE_JSON               = "intake_json"
    CRITIC_REVIEW             = "critic_review"
    CONTENT_TABLE             = "content_table"
    CONTENT_HERO              = "content_hero"
    CONTENT_BULK              = "content_bulk"
    CHANNEL_ADAPT             = "channel_adapt"
    CLASSIFICATION            = "classification"
    VISION_ANALYSIS           = "vision_analysis"

    # Generic fallbacks
    GENERIC_CREATIVE          = "generic_creative"
    GENERIC_STRUCTURED        = "generic_structured"


# ─────────────────────────────────────────────────────────────────
# Routing table — task → ordered provider chain (primary → fallbacks)
# ─────────────────────────────────────────────────────────────────

ROUTING_TABLE: dict[TaskType, list[Provider]] = {
    # Research stages — Perplexity primary (real-time + citations)
    TaskType.MARKET_RESEARCH_DATA:       [Provider.PERPLEXITY_SONAR, Provider.GEMINI_PRO, Provider.ANTHROPIC_SONNET],
    TaskType.MARKET_RESEARCH_NARRATIVE:  [Provider.ANTHROPIC_HAIKU, Provider.OPENAI_GPT4O_MINI],
    TaskType.COMPETITOR_RESEARCH:        [Provider.PERPLEXITY_SONAR, Provider.GEMINI_PRO, Provider.ANTHROPIC_SONNET],
    TaskType.COMPETITOR_MATRIX:          [Provider.OPENAI_GPT4O, Provider.ANTHROPIC_SONNET],

    # Creative VN — Anthropic Sonnet primary
    TaskType.CUSTOMER_INSIGHT:           [Provider.ANTHROPIC_SONNET, Provider.GEMINI_PRO],
    TaskType.PSYCHOLOGY:                 [Provider.ANTHROPIC_SONNET, Provider.OPENAI_GPT4O],
    TaskType.USP_CREATIVE:               [Provider.ANTHROPIC_SONNET, Provider.GEMINI_PRO],
    TaskType.CONTENT_HERO:               [Provider.ANTHROPIC_SONNET],

    # Structured/Math — OpenAI primary
    TaskType.PRICING_MATH:               [Provider.OPENAI_GPT4O, Provider.ANTHROPIC_SONNET],
    TaskType.RETENTION_MATRIX:           [Provider.OPENAI_GPT4O, Provider.ANTHROPIC_SONNET],
    TaskType.WINBACK_STRATEGY:           [Provider.OPENAI_GPT4O, Provider.ANTHROPIC_SONNET],
    TaskType.CONTENT_TABLE:              [Provider.OPENAI_GPT4O, Provider.ANTHROPIC_SONNET],

    # Long context aggregation — Gemini Pro primary (1M context champion)
    TaskType.SYNTHESIS_LONG_CONTEXT:     [Provider.GEMINI_PRO, Provider.GEMINI_FLASH, Provider.ANTHROPIC_SONNET],

    # Cheap/fast tasks — Haiku or mini
    TaskType.INTAKE_JSON:                [Provider.ANTHROPIC_HAIKU, Provider.OPENAI_GPT4O_MINI],
    TaskType.CRITIC_REVIEW:              [Provider.ANTHROPIC_HAIKU, Provider.OPENAI_GPT4O_MINI],
    TaskType.CONTENT_BULK:               [Provider.OPENAI_GPT4O, Provider.ANTHROPIC_SONNET],
    TaskType.CHANNEL_ADAPT:              [Provider.OPENAI_GPT4O_MINI, Provider.ANTHROPIC_HAIKU],
    TaskType.CLASSIFICATION:             [Provider.OPENAI_GPT4O_MINI, Provider.GEMINI_FLASH, Provider.ANTHROPIC_HAIKU],

    # Vision (Anthropic vision strong)
    TaskType.VISION_ANALYSIS:            [Provider.ANTHROPIC_SONNET, Provider.OPENAI_GPT4O],

    # Generic fallbacks
    TaskType.GENERIC_CREATIVE:           [Provider.ANTHROPIC_SONNET, Provider.GEMINI_PRO],
    TaskType.GENERIC_STRUCTURED:         [Provider.OPENAI_GPT4O, Provider.ANTHROPIC_SONNET],
}


# ─────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────

class ProviderUnavailable(Exception):
    """Provider chưa setup (missing API key) hoặc temporarily down."""
    pass


class AllProvidersFailedError(Exception):
    """Cả primary + fallback chain đều fail."""
    pass


# ─────────────────────────────────────────────────────────────────
# Anthropic client (singleton — shared với pipeline.py)
# ─────────────────────────────────────────────────────────────────

_anthropic_client: Optional[anthropic.AsyncAnthropic] = None


def _get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic(
            api_key=ANTHROPIC_API_KEY,
            timeout=180.0,
            max_retries=1,  # match pipeline.py hotfix
        )
    return _anthropic_client


# ─────────────────────────────────────────────────────────────────
# Provider call functions
# ─────────────────────────────────────────────────────────────────

async def _call_anthropic_sonnet(
    system: str, user: str, max_tokens: int = 4000, **kwargs
) -> dict:
    """Call Anthropic Sonnet 4.6. Returns {output, tokens_in, tokens_out, provider}."""
    client = _get_anthropic_client()
    response = await client.messages.create(
        model=CLAUDE_SONNET_MODEL,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    return {
        "output": response.content[0].text,
        "tokens_in": getattr(response.usage, "input_tokens", 0),
        "tokens_out": getattr(response.usage, "output_tokens", 0),
        "provider": Provider.ANTHROPIC_SONNET.value,
    }


async def _call_anthropic_haiku(
    system: str, user: str, max_tokens: int = 2048, **kwargs
) -> dict:
    """Call Anthropic Haiku 4.5 — cheap classification + critic."""
    client = _get_anthropic_client()
    response = await client.messages.create(
        model=CLAUDE_HAIKU_MODEL,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    return {
        "output": response.content[0].text,
        "tokens_in": getattr(response.usage, "input_tokens", 0),
        "tokens_out": getattr(response.usage, "output_tokens", 0),
        "provider": Provider.ANTHROPIC_HAIKU.value,
    }


async def _call_gemini_pro(
    system: str, user: str, max_tokens: int = 10000, **kwargs
) -> dict:
    """Call Gemini 2.5 Pro. STUB — wire khi có GEMINI_API_KEY (S8.7).

    Sau khi wire:
    ```python
    from google import genai
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = await client.aio.models.generate_content(
        model="gemini-2.5-pro",
        contents=[{"role": "user", "parts": [{"text": user}]}],
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=0.7,
            thinking_config=types.ThinkingConfig(thinking_budget=8000),
        ),
    )
    return {"output": response.text, ...}
    ```
    """
    if not os.getenv("GEMINI_API_KEY"):
        raise ProviderUnavailable(
            "Gemini 2.5 Pro chưa setup — thiếu GEMINI_API_KEY env var"
        )
    # TODO S8.7: actual implementation when API key available
    raise NotImplementedError(
        "Gemini Pro integration deferred to S8.7. "
        "Use Anthropic Sonnet fallback for now."
    )


async def _call_gemini_flash(
    system: str, user: str, max_tokens: int = 10000, **kwargs
) -> dict:
    """Call Gemini 2.5 Flash — cheap fallback for Pro. STUB."""
    if not os.getenv("GEMINI_API_KEY"):
        raise ProviderUnavailable("Gemini Flash chưa setup")
    raise NotImplementedError("Gemini Flash deferred to S8.7")


async def _call_openai_gpt4o(
    system: str, user: str, max_tokens: int = 4000, json_schema: Optional[dict] = None, **kwargs
) -> dict:
    """Call OpenAI GPT-4o. STUB — wire khi có OPENAI_API_KEY."""
    if not os.getenv("OPENAI_API_KEY"):
        raise ProviderUnavailable("OpenAI chưa setup")
    raise NotImplementedError("OpenAI GPT-4o deferred (post-S8)")


async def _call_openai_gpt4o_mini(
    system: str, user: str, max_tokens: int = 2048, **kwargs
) -> dict:
    """Call OpenAI GPT-4o-mini — bulk cheap. STUB."""
    if not os.getenv("OPENAI_API_KEY"):
        raise ProviderUnavailable("OpenAI chưa setup")
    raise NotImplementedError("OpenAI GPT-4o-mini deferred")


async def _call_perplexity_sonar(
    system: str, user: str, max_tokens: int = 4000, **kwargs
) -> dict:
    """Call Perplexity Sonar Pro — research + citations. STUB."""
    if not os.getenv("PERPLEXITY_API_KEY"):
        raise ProviderUnavailable("Perplexity chưa setup")
    raise NotImplementedError("Perplexity Sonar deferred (post-S8)")


# Provider → call function mapping
PROVIDER_CALLERS = {
    Provider.ANTHROPIC_SONNET:   _call_anthropic_sonnet,
    Provider.ANTHROPIC_HAIKU:    _call_anthropic_haiku,
    Provider.GEMINI_PRO:         _call_gemini_pro,
    Provider.GEMINI_FLASH:       _call_gemini_flash,
    Provider.OPENAI_GPT4O:       _call_openai_gpt4o,
    Provider.OPENAI_GPT4O_MINI:  _call_openai_gpt4o_mini,
    Provider.PERPLEXITY_SONAR:   _call_perplexity_sonar,
}


# ─────────────────────────────────────────────────────────────────
# Top-level router
# ─────────────────────────────────────────────────────────────────

async def call(
    task_type: TaskType,
    system: str,
    user: str,
    max_tokens: int = 4000,
    json_schema: Optional[dict] = None,
) -> dict:
    """Single entry point — router picks provider per task_type với failover chain.

    Returns: dict {output, tokens_in, tokens_out, provider, latency_sec}

    Raises:
        AllProvidersFailedError: nếu cả primary + fallback chain đều fail
    """
    providers = ROUTING_TABLE.get(task_type, [Provider.ANTHROPIC_SONNET])

    last_error: Optional[Exception] = None

    for provider in providers:
        caller = PROVIDER_CALLERS.get(provider)
        if not caller:
            logger.error(f"No caller registered for provider {provider}")
            continue

        start = time.monotonic()
        try:
            result = await caller(
                system=system,
                user=user,
                max_tokens=max_tokens,
                json_schema=json_schema,
            )
            result["latency_sec"] = time.monotonic() - start
            logger.info(
                f"[router] task={task_type.value} provider={provider.value} "
                f"in={result.get('tokens_in')} out={result.get('tokens_out')} "
                f"latency={result['latency_sec']:.1f}s"
            )
            return result

        except ProviderUnavailable as e:
            # Provider chưa setup — silently failover
            logger.debug(f"Provider {provider} unavailable, failing over: {e}")
            last_error = e
            continue

        except NotImplementedError as e:
            # Stub provider — failover
            logger.debug(f"Provider {provider} not yet implemented, failing over: {e}")
            last_error = e
            continue

        except anthropic.RateLimitError as e:
            logger.warning(f"Provider {provider} rate limit, failing over: {e}")
            last_error = e
            continue

        except anthropic.APITimeoutError as e:
            logger.warning(f"Provider {provider} timeout, failing over: {e}")
            last_error = e
            continue

        except Exception as e:
            logger.warning(
                f"Provider {provider} unexpected error, failing over: "
                f"{type(e).__name__}: {str(e)[:200]}"
            )
            last_error = e
            continue

    raise AllProvidersFailedError(
        f"All providers failed for task={task_type.value}. "
        f"Tried: {[p.value for p in providers]}. "
        f"Last error: {last_error}"
    )


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def is_provider_available(provider: Provider) -> bool:
    """Check provider khả dụng (API key setup)."""
    if provider in (Provider.ANTHROPIC_SONNET, Provider.ANTHROPIC_HAIKU):
        return bool(ANTHROPIC_API_KEY)
    if provider in (Provider.GEMINI_PRO, Provider.GEMINI_FLASH):
        return bool(os.getenv("GEMINI_API_KEY"))
    if provider in (Provider.OPENAI_GPT4O, Provider.OPENAI_GPT4O_MINI):
        return bool(os.getenv("OPENAI_API_KEY"))
    if provider == Provider.PERPLEXITY_SONAR:
        return bool(os.getenv("PERPLEXITY_API_KEY"))
    return False


def availability_report() -> str:
    """Trạng thái providers — useful cho /settings hoặc debug."""
    lines = ["## LLM Router — Provider Availability"]
    for p in Provider:
        status = "✅" if is_provider_available(p) else "❌"
        lines.append(f"- {status} {p.value}")
    return "\n".join(lines)
