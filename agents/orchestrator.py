"""
Multi-Agent Orchestrator — Tier-based parallel execution.

Inspired by Antigravity Orchestrator-Workers pattern (Sprint 8).

Mỗi `tier` = N agents chạy parallel với fault isolation. Tier-by-tier execution:
agents trong cùng tier không có dependency với nhau, agents giữa các tier có thể có.

Design principles:
- Fault isolation: 1 agent fail → others continue, NOT cancel
- Concurrency cap: Semaphore tránh burst rate limit khi N agents same provider
- Timeout per agent: cô lập slow agent không kéo tier
- Critical vs nice-to-have: must_have fail → abort pipeline, nice_to_have fail → log warning

S8.1 scope: chỉ primitives (data classes + run_tier + _safe_run).
Agent wrappers ở S8.2, TIER definitions ở S8.4, wire pipeline ở S8.5.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Awaitable, Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────

@dataclass
class AgentResult:
    """Output của 1 agent sau khi run.

    Đủ thông tin cho:
    - Pipeline orchestrator decide tier passes/fails
    - Monitoring/logging (latency, provider, tokens)
    - User-facing progress messages
    """
    agent_name: str
    success: bool
    output: str                          # Skill result text (prose hoặc serialized JSON)
    error: Optional[str] = None          # Exception type + message nếu fail
    latency_sec: float = 0.0
    provider_used: str = "unknown"       # "anthropic_sonnet" / "gemini_pro" / "openai_gpt4o"
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass
class TierConfig:
    """Định nghĩa 1 tier — N agents chạy parallel + rules.

    must_have: agents BẮT BUỘC success. Nếu 1 trong số này fail → PipelineAbortError.
    nice_to_have: có thể fail, pipeline continue (mark missing trong final output).
    timeout_per_agent: cô lập slow agent (mặc định 180s đủ cho Sonnet 10K out).
    max_concurrent: semaphore cap — Anthropic Tier 1-3 should ≤3 same model.
    """
    name: str
    agents: list[Callable[..., Awaitable[str]]]
    must_have: set[str] = field(default_factory=set)
    nice_to_have: set[str] = field(default_factory=set)
    timeout_per_agent: int = 180
    max_concurrent: int = 3


class PipelineAbortError(Exception):
    """Raised khi must_have agent fail trong tier — abort pipeline.

    Distinct from generic Exception so handler có thể catch riêng,
    show user message "X bước critical fail, pipeline dừng".
    """
    pass


# ─────────────────────────────────────────────────────────────────
# Core runners
# ─────────────────────────────────────────────────────────────────

async def run_tier(
    tier: TierConfig,
    session: Any,
    progress_callback: Optional[Callable[[str], Awaitable[None]]] = None,
) -> dict[str, AgentResult]:
    """Run all agents trong tier concurrently với fault isolation + concurrency cap.

    Args:
        tier: TierConfig định nghĩa agents + rules
        session: Session object pass vào mỗi agent (state share)
        progress_callback: async fn(msg) gọi trước/sau tier — UI progress

    Returns:
        dict {agent_name: AgentResult} — guaranteed có entry cho mọi agent trong tier

    Raises:
        PipelineAbortError: khi any must_have agent fail
    """
    if not tier.agents:
        logger.warning(f"Tier {tier.name} has no agents — skipping")
        return {}

    semaphore = asyncio.Semaphore(tier.max_concurrent)

    async def _bounded_run(agent_fn: Callable) -> AgentResult:
        async with semaphore:
            return await _safe_run(agent_fn, session, tier.timeout_per_agent)

    tasks = {
        agent.__name__: asyncio.create_task(_bounded_run(agent))
        for agent in tier.agents
    }

    if progress_callback:
        await progress_callback(
            f"🚀 {tier.name}: chạy {len(tasks)} agents parallel "
            f"(max {tier.max_concurrent} concurrent)..."
        )

    tier_start = time.monotonic()

    # Await all — _safe_run đã catch exception → trả AgentResult với success=False
    # KHÔNG dùng asyncio.gather(return_exceptions=True) vì _safe_run guarantee no raise
    results: dict[str, AgentResult] = {}
    for name, task in tasks.items():
        results[name] = await task

    tier_duration = time.monotonic() - tier_start

    # Validate must_have agents succeeded
    failed_critical = [
        name for name in tier.must_have
        if name not in results or not results[name].success
    ]
    if failed_critical:
        error_details = "; ".join(
            f"{n}: {results.get(n, AgentResult(n, False, '')).error or 'missing'}"
            for n in failed_critical
        )
        logger.error(
            f"Tier {tier.name}: critical agents failed: {error_details}"
        )
        raise PipelineAbortError(
            f"Tier {tier.name} critical fail: {failed_critical}. {error_details}"
        )

    # Log summary
    successful = sum(1 for r in results.values() if r.success)
    failed_nice = [
        name for name in tier.nice_to_have
        if name in results and not results[name].success
    ]
    if failed_nice:
        logger.warning(
            f"Tier {tier.name}: nice_to_have agents failed (pipeline continues): {failed_nice}"
        )

    logger.info(
        f"Tier {tier.name}: {successful}/{len(tasks)} agents succeeded "
        f"in {tier_duration:.1f}s"
    )

    if progress_callback:
        status_emoji = "✅" if successful == len(tasks) else "⚠️"
        await progress_callback(
            f"{status_emoji} {tier.name}: {successful}/{len(tasks)} agents thành công "
            f"({tier_duration:.1f}s)"
        )

    return results


async def _safe_run(
    agent_fn: Callable[..., Awaitable[str]],
    session: Any,
    timeout: int,
) -> AgentResult:
    """Cô lập exception + timeout cho 1 agent run.

    KHÔNG raise — luôn trả AgentResult. Caller có thể check .success.

    Provider detection: agent function có thể set `_provider` attribute,
    được pickup vào AgentResult.provider_used (mặc định "unknown").
    """
    name = getattr(agent_fn, "__name__", "anonymous_agent")
    provider = getattr(agent_fn, "_provider", "unknown")
    start = time.monotonic()

    try:
        output = await asyncio.wait_for(agent_fn(session), timeout=timeout)
        elapsed = time.monotonic() - start
        # Output có thể là string hoặc dict (future structured output)
        # Hiện tại normalize về string
        output_str = output if isinstance(output, str) else str(output)
        return AgentResult(
            agent_name=name,
            success=True,
            output=output_str,
            latency_sec=elapsed,
            provider_used=provider,
        )
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - start
        logger.warning(f"Agent {name} timeout after {timeout}s")
        return AgentResult(
            agent_name=name,
            success=False,
            output="",
            error=f"timeout after {timeout}s",
            latency_sec=elapsed,
            provider_used=provider,
        )
    except asyncio.CancelledError:
        # Re-raise — caller cancelled task, không phải agent crash
        raise
    except Exception as e:
        elapsed = time.monotonic() - start
        logger.exception(f"Agent {name} crashed after {elapsed:.1f}s: {e}")
        return AgentResult(
            agent_name=name,
            success=False,
            output="",
            error=f"{type(e).__name__}: {str(e)[:300]}",
            latency_sec=elapsed,
            provider_used=provider,
        )


# ─────────────────────────────────────────────────────────────────
# Smoke test — chạy `python -m agents.orchestrator` để verify
# ─────────────────────────────────────────────────────────────────

async def _smoke_test():
    """Dev helper — verify orchestrator primitives với mock agents."""
    print("=" * 60)
    print("S8.1 Smoke Test — Orchestrator Primitives")
    print("=" * 60)

    # Mock agents
    async def mock_fast(session):
        await asyncio.sleep(0.5)
        return "fast result"

    async def mock_slow(session):
        await asyncio.sleep(2)
        return "slow result"

    async def mock_fail(session):
        raise ValueError("intentional test fail")

    async def mock_timeout(session):
        await asyncio.sleep(10)  # Will exceed 3s timeout
        return "should never see this"

    # Test 1: All nice-to-have, mix success/fail/timeout
    print("\nTest 1: Fault isolation (3 agents — fast OK, slow OK, fail crash)")
    tier1 = TierConfig(
        name="T_FAULT_ISOLATION",
        agents=[mock_fast, mock_slow, mock_fail],
        nice_to_have={"mock_fast", "mock_slow", "mock_fail"},
        timeout_per_agent=5,
        max_concurrent=3,
    )

    progress_msgs = []
    async def capture_progress(msg):
        progress_msgs.append(msg)
        print(f"  [progress] {msg}")

    results = await run_tier(tier1, session=None, progress_callback=capture_progress)
    assert "mock_fast" in results and results["mock_fast"].success
    assert "mock_slow" in results and results["mock_slow"].success
    assert "mock_fail" in results and not results["mock_fail"].success
    assert "ValueError" in results["mock_fail"].error
    assert len(progress_msgs) == 2  # start + end
    print(f"  ✓ All 3 agents returned, 2 success + 1 fail (isolated)")
    print(f"  ✓ Latencies: fast={results['mock_fast'].latency_sec:.2f}s, "
          f"slow={results['mock_slow'].latency_sec:.2f}s, "
          f"fail={results['mock_fail'].latency_sec:.2f}s")

    # Test 2: Timeout cô lập
    print("\nTest 2: Timeout isolation (timeout agent should fail without blocking)")
    tier2 = TierConfig(
        name="T_TIMEOUT",
        agents=[mock_fast, mock_timeout],
        nice_to_have={"mock_fast", "mock_timeout"},
        timeout_per_agent=3,
    )
    start = time.monotonic()
    results2 = await run_tier(tier2, session=None)
    elapsed = time.monotonic() - start
    assert results2["mock_fast"].success
    assert not results2["mock_timeout"].success
    assert "timeout" in results2["mock_timeout"].error.lower()
    assert elapsed < 4  # Should NOT wait for mock_timeout's 10s
    print(f"  ✓ Tier completed in {elapsed:.1f}s (< 4s — timeout cô lập)")
    print(f"  ✓ mock_timeout error: {results2['mock_timeout'].error}")

    # Test 3: must_have fail → PipelineAbortError
    print("\nTest 3: must_have agent fail → PipelineAbortError")
    tier3 = TierConfig(
        name="T_CRITICAL",
        agents=[mock_fast, mock_fail],
        must_have={"mock_fail"},  # mock_fail is critical
        nice_to_have={"mock_fast"},
        timeout_per_agent=5,
    )
    try:
        await run_tier(tier3, session=None)
        print("  ✗ FAIL: should have raised PipelineAbortError")
    except PipelineAbortError as e:
        print(f"  ✓ Correctly raised PipelineAbortError: {e}")

    # Test 4: Concurrency cap
    print("\nTest 4: Semaphore concurrency cap (max 2, 4 agents → 2 batches)")
    async def a1(s): await asyncio.sleep(2); return "a1"
    async def a2(s): await asyncio.sleep(2); return "a2"
    async def a3(s): await asyncio.sleep(2); return "a3"
    async def a4(s): await asyncio.sleep(2); return "a4"

    tier4 = TierConfig(
        name="T_CONCURRENCY",
        agents=[a1, a2, a3, a4],
        nice_to_have={"a1", "a2", "a3", "a4"},
        timeout_per_agent=10,
        max_concurrent=2,
    )
    start = time.monotonic()
    results4 = await run_tier(tier4, session=None)
    elapsed = time.monotonic() - start
    assert all(r.success for r in results4.values())
    # With max_concurrent=2, 4 agents × 2s each = 2 batches × 2s = ~4s
    assert 3.5 < elapsed < 5, f"Expected ~4s, got {elapsed:.1f}s"
    print(f"  ✓ 4 agents × 2s with max_concurrent=2 → {elapsed:.1f}s (~4s expected)")

    print("\n" + "=" * 60)
    print("✅ ALL S8.1 SMOKE TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
    asyncio.run(_smoke_test())
