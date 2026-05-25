"""
Agent wrappers — wrap existing AgentSkill classes thành async functions
cho orchestrator dùng.

Mỗi wrapper:
- Signature: `async def NAME(session: Session) -> str`
- Có `_provider` attribute: dùng cho monitoring + LLM Router routing
- Reuse logic của _run_skill từ pipeline.py (giữ Critic, format injection, token tracking)

S8.2 scope: 8 Digital Twin wrappers — Anna/Bình/Chi/David/Linh/Minh/Phương/Tâm
mapping với 8 strategic skill classes hiện có + 1 conditional logic cho USP.
"""
from __future__ import annotations

import logging
from typing import Optional

from storage.models import Session
from agents.skills import (
    MarketResearchSkill,
    CompetitorSkill,
    CustomerInsightSkill,
    PsychologyPricingSkill,
    UspDefinitionSkill,
    StrategySynthesisSkill,
    ContextStrategy,
)

logger = logging.getLogger(__name__)


# Helper marker — dùng để track provider per agent (S8.3 LLM Router sẽ override)
def _with_provider(provider_name: str):
    """Decorator gắn _provider attribute cho wrapper function."""
    def deco(fn):
        fn._provider = provider_name
        return fn
    return deco


# ─────────────────────────────────────────────────────────────────
# TIER 1 — Foundation agents (parallel, no deps)
# ─────────────────────────────────────────────────────────────────

@_with_provider("anthropic_sonnet")
async def market_research_agent(session: Session) -> str:
    """🌍 Anna — Sr Market Research Analyst.

    Foundation tier — không có dependency, chỉ cần profile.
    Output: TAM/SAM/SOM + Market Dynamics theo VN context.

    S8.3 sẽ route: primary=Perplexity Sonar Pro, fallback=Sonnet.
    """
    from agents.pipeline import _run_skill
    result = await _run_skill(MarketResearchSkill(), session)
    session.add_result("market_research", result)
    return result


@_with_provider("anthropic_sonnet")
async def competitor_agent(session: Session) -> str:
    """🕵️ Bình — Competitor Intelligence Analyst.

    Foundation tier — analyze landscape + market gap.
    S8.3 sẽ route: Perplexity (research) + GPT-4o (matrix), fallback Sonnet.
    """
    from agents.pipeline import _run_skill
    result = await _run_skill(CompetitorSkill(), session)
    session.add_result("competitor", result)
    return result


@_with_provider("anthropic_sonnet")
async def customer_insight_agent(session: Session) -> str:
    """👥 Chi — Consumer Psychologist VN.

    Foundation tier — ICP + JTBD + Pain-gain map với VN cultural depth.
    Sonnet giữ nguyên (em strong nhất cho VN psychographics).
    """
    from agents.pipeline import _run_skill
    result = await _run_skill(CustomerInsightSkill(), session)
    session.add_result("customer_insight", result)
    return result


# ─────────────────────────────────────────────────────────────────
# TIER 2 — Strategy synthesis (parallel after T1)
# ─────────────────────────────────────────────────────────────────

@_with_provider("anthropic_sonnet")
async def usp_definition_agent(session: Session) -> str:
    """🎯 Linh — USP Strategist.

    Tier 2 — depends on T1 outputs (market + competitor + customer).
    Conditional skip nếu profile.usp_confidence='clear'.
    """
    confidence = (session.profile.usp_confidence or "").lower()
    if confidence == "clear":
        # Skip — already have USP from intake
        skipped_msg = (
            "## USP — Skipped (đã có từ intake)\n\n"
            f'USP user đã định nghĩa: "{session.profile.usp or "N/A"}"\n\n'
            "Synthesis sẽ dùng USP này trực tiếp."
        )
        session.add_result("usp_definition", skipped_msg)
        return skipped_msg

    from agents.pipeline import _run_skill
    result = await _run_skill(UspDefinitionSkill(), session)
    session.add_result("usp_definition", result)
    return result


@_with_provider("anthropic_sonnet")
async def psychology_pricing_agent(session: Session) -> str:
    """🧠 David — Marketing Psychologist + Pricing Strategist.

    Tier 2 — combined psychology + pricing trong 1 call (giữ design hiện tại).
    S8.3 có thể split: psychology=Sonnet ∥ pricing=GPT-4o parallel sub-tasks.
    """
    from agents.pipeline import _run_skill
    result = await _run_skill(PsychologyPricingSkill(), session)
    session.add_result("psychology_pricing", result)
    return result


# ─────────────────────────────────────────────────────────────────
# TIER 3 — Customer Journey (sequential: Winback needs Retention)
# ─────────────────────────────────────────────────────────────────

@_with_provider("anthropic_sonnet")
async def retention_strategy_agent(session: Session) -> str:
    """🔄 Minh — Customer Retention Strategist.

    Tier 3 step 1 — reuse operational skill với FULL_PIPELINE context override.
    S8.3 sẽ route: GPT-4o (tier matrix structured).
    """
    from agents.operational_skills_config import get_operational_skill
    from agents.pipeline import _run_skill

    skill = get_operational_skill("retention_strategy")
    # Override context strategy — pipeline mode cần đọc full T1+T2, không chỉ profile+synthesis
    skill.context_strategy = ContextStrategy.FULL_PIPELINE
    if hasattr(skill, "_config"):
        skill._config.context_strategy = ContextStrategy.FULL_PIPELINE

    result = await _run_skill(skill, session)
    session.add_result("retention_strategy", result)
    return result


@_with_provider("anthropic_sonnet")
async def winback_vision_agent(session: Session) -> str:
    """🔁 Phương — Winback Campaign Specialist.

    Tier 3 step 2 — depends on Retention output (đã save vào session.results
    bởi retention_strategy_agent ngay trước).
    """
    from agents.operational_skills_config import get_operational_skill
    from agents.pipeline import _run_skill

    skill = get_operational_skill("winback_campaign")
    skill.context_strategy = ContextStrategy.FULL_PIPELINE
    if hasattr(skill, "_config"):
        skill._config.context_strategy = ContextStrategy.FULL_PIPELINE

    result = await _run_skill(skill, session)
    session.add_result("winback_campaign", result)
    return result


@_with_provider("anthropic_sonnet")
async def retention_then_winback_chain(session: Session) -> str:
    """🔄→🔁 Minh + Phương — Sequential chain.

    Tier 3 SEQUENTIAL chain — Winback đọc Retention output từ session.results.
    Wrap thành 1 function vì orchestrator T3 chỉ cần 1 "agent" trong sequential mode.

    Output: concatenated text của cả 2 stage cho Synthesis đọc.
    """
    retention_result = await retention_strategy_agent(session)
    winback_result = await winback_vision_agent(session)

    combined = (
        f"## Retention Strategy (Tier 3.1)\n\n{retention_result}\n\n"
        f"---\n\n"
        f"## Winback Vision (Tier 3.2)\n\n{winback_result}"
    )
    return combined


# ─────────────────────────────────────────────────────────────────
# TIER 4 — Final aggregation (long context)
# ─────────────────────────────────────────────────────────────────

@_with_provider("gemini_pro_with_haiku_polish")
async def synthesizer_agent(session: Session) -> str:
    """📋 Tâm — Chief Marketing Strategist (Synthesizer).

    Tier 4 — aggregate all T1-T3 outputs thành Marketing Strategy hoàn chỉnh.

    S8.3 sẽ route: PRIMARY=Gemini 2.5 Pro (1M context, $1.25/$10),
    POLISH=Haiku 4.5 (VN tone), FALLBACK=Sonnet.

    S8.2 hiện chỉ wrap existing Sonnet path — Gemini integration ở S8.3.
    """
    from agents.pipeline import _run_skill
    result = await _run_skill(StrategySynthesisSkill(), session)
    session.add_result("synthesis", result)
    return result


# ─────────────────────────────────────────────────────────────────
# Registry — agent_name → wrapper function (cho introspection)
# ─────────────────────────────────────────────────────────────────

ALL_AGENTS = {
    "market_research_agent":         market_research_agent,
    "competitor_agent":              competitor_agent,
    "customer_insight_agent":        customer_insight_agent,
    "usp_definition_agent":          usp_definition_agent,
    "psychology_pricing_agent":      psychology_pricing_agent,
    "retention_strategy_agent":      retention_strategy_agent,
    "winback_vision_agent":          winback_vision_agent,
    "retention_then_winback_chain":  retention_then_winback_chain,
    "synthesizer_agent":             synthesizer_agent,
}


def get_agent_provider(agent_name: str) -> str:
    """Lookup provider của 1 agent (cho monitoring/debug)."""
    agent = ALL_AGENTS.get(agent_name)
    if not agent:
        return "unknown"
    return getattr(agent, "_provider", "unknown")
