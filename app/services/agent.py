"""Browser-Use agent — natural-language browser tasks."""

import logging

from browser_use import Agent
from langchain_openai import ChatOpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def run_agent_task(
    task: str,
    *,
    start_url: str | None = None,
    max_steps: int = 15,
) -> dict:
    """
    Run a natural-language browser task using Browser-Use + DeepSeek.

    Returns dict with: final_result, steps_taken, history, tokens_used
    """
    if not settings.deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY not set")

    llm = ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=0.0,
    )

    full_task = task
    if start_url:
        full_task = f"Start at {start_url}. Then: {task}"

    agent = Agent(
        task=full_task,
        llm=llm,
        max_actions_per_step=4,
        use_vision=False,
        headless=settings.playwright_headless,
    )

    try:
        history = await agent.run(max_steps=max_steps)
    except Exception as e:
        logger.exception("Browser-Use agent failed")
        raise RuntimeError(f"Agent failed: {e}") from e

    # Extract result from history
    final_result = None
    steps_taken = 0
    if history and hasattr(history, "history"):
        steps_taken = len(history.history)
        if history.history:
            last = history.history[-1]
            final_result = (
                last.result
                if hasattr(last, "result")
                else str(last)
            )

    # Token accounting is best-effort
    total_tokens = None
    try:
        if history and hasattr(history, "total_tokens"):
            total_tokens = history.total_tokens
    except Exception:
        pass

    return {
        "final_result": final_result or "Task completed (no explicit result)",
        "steps_taken": steps_taken,
        "history": [
            h.model_dump() if hasattr(h, "model_dump") else str(h)
            for h in (history.history if history and hasattr(history, "history") else [])
        ],
        "tokens_used": total_tokens,
    }