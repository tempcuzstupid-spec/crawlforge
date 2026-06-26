"""LLM summarization via DeepSeek (OpenAI-compatible API)."""

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def get_llm(temperature: float = 0.3, max_tokens: int = 1024) -> ChatOpenAI:
    """Return a DeepSeek-backed ChatOpenAI client."""
    if not settings.deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY not set")
    return ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=temperature,
        max_tokens=max_tokens,
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
async def summarize(
    content: str,
    prompt: str = "Provide a concise summary of the main content in 3-5 bullet points.",
    *,
    max_tokens: int = 1024,
) -> tuple[str, int]:
    """Summarize `content` using DeepSeek. Returns (summary, tokens_used)."""
    llm = get_llm(max_tokens=max_tokens)
    messages = [
        SystemMessage(content="You are a helpful assistant that summarizes web content accurately."),
        HumanMessage(content=f"{prompt}\n\n---\n\n{content[:12000]}"),
    ]
    response = await llm.ainvoke(messages)
    tokens = response.response_metadata.get("token_usage", {}).get("total_tokens", 0)
    return response.content, tokens


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
async def extract_structured(
    content: str,
    schema_description: str,
    *,
    max_tokens: int = 1024,
) -> tuple[dict, int]:
    """Extract structured data from content using a schema description."""
    import json
    import re

    llm = get_llm(temperature=0.0, max_tokens=max_tokens)
    prompt = f"""Extract structured information from the following web content.

SCHEMA:
{schema_description}

Return ONLY a valid JSON object matching the schema. No markdown fences, no commentary.

CONTENT:
{content[:12000]}"""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    text = response.content.strip()
    # Strip code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    tokens = response.response_metadata.get("token_usage", {}).get("total_tokens", 0)
    try:
        return json.loads(text), tokens
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON from LLM: {e}\nRaw: {text[:500]}")
        return {"raw": text, "parse_error": str(e)}, tokens