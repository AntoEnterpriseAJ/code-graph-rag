from __future__ import annotations

import asyncio
from typing import Any, Literal, cast

from config import detect_provider_from_model, settings
from langchain.schema import AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai import ChatVertexAI
from langchain_openai import ChatOpenAI
from loguru import logger
from nl2cypher.prompts import (
    CYPHER_SYSTEM_PROMPT,
    LOCAL_CYPHER_SYSTEM_PROMPT,
)

Provider = Literal["openai", "gemini", "local"]


class LLMGenerationError(RuntimeError):
    """Raised when the underlying chat model fails or returns junk."""


def _clean_cypher_response(raw: str) -> str:
    txt = raw.strip().replace("`", "")
    if txt.lower().startswith("cypher"):
        txt = txt[6:].strip()
    return txt if txt.endswith(";") else txt + ";"


def _make_chat_model(model_id: str, *, provider: Provider) -> Any:
    if provider == "openai":
        return ChatOpenAI(
            model=model_id,
            api_key=settings.OPENAI_API_KEY,
            streaming=False,
        )
    if provider == "local":
        # OpenAI-compatible endpoint
        return ChatOpenAI(
            model=model_id,
            api_key=settings.LOCAL_MODEL_API_KEY,
            base_url=str(settings.LOCAL_MODEL_ENDPOINT),
            streaming=False,
        )
    if provider == "gemini" and settings.GEMINI_PROVIDER == "vertex":
        return ChatVertexAI(
            model_name=model_id,
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_REGION,
            credentials_path=settings.GCP_SERVICE_ACCOUNT_FILE,
            convert_system_message_to_human=True,
        )
    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=model_id,
            google_api_key=settings.GEMINI_API_KEY,
            safety_settings={"HARASSMENT": "BLOCK_NONE"},
        )
    raise ValueError(f"Unhandled provider: {provider}")


class CypherGenerator:
    def __init__(self) -> None:
        model_id = settings.active_cypher_model
        provider = cast(Provider, detect_provider_from_model(model_id))
        self.system_prompt = (
            CYPHER_SYSTEM_PROMPT if provider != "local" else LOCAL_CYPHER_SYSTEM_PROMPT
        )
        self.chat = _make_chat_model(model_id, provider=provider)

    async def generate(self, nl_query: str) -> str:
        logger.info(f"[CypherGenerator] NL → Cypher for: {nl_query!r}")
        try:
            msg = await self.chat.ainvoke(
                [
                    SystemMessage(content=self.system_prompt),
                    AIMessage(content=nl_query),  # LangChain treats this as “user”
                ]
            )
        except Exception as exc:  # network, creds, quota, …
            raise LLMGenerationError(str(exc)) from exc

        text = str(msg.content)
        if "MATCH" not in text.upper():
            raise LLMGenerationError(
                f"Model returned something that doesn’t look like Cypher: {text!r}"
            )
        cleaned = _clean_cypher_response(text)
        logger.info(f"[CypherGenerator] ✅  {cleaned}")
        return cleaned


def generate_sync(nl_query: str) -> str:
    """Blocking wrapper so call-sites don’t have to care about asyncio."""
    return asyncio.run(CypherGenerator().generate(nl_query))
