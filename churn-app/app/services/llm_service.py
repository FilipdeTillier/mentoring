"""
Unified LLM service for both OpenAI and Ollama.

Provides a common interface to invoke LLM models regardless of provider.
"""
import os
import logging
from typing import List, Dict, Optional

import requests
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from app.const import DEFAULT_MODEL

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


def check_ollama_health() -> Dict:
    """
    Check if Ollama is reachable and get its status.

    Returns:
        Dict with status information
    """
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
        response.raise_for_status()
        data = response.json()
        models = [m["name"] for m in data.get("models", [])]
        return {
            "status": "healthy",
            "host": OLLAMA_HOST,
            "models": models
        }
    except requests.exceptions.ConnectionError:
        return {
            "status": "unreachable",
            "host": OLLAMA_HOST,
            "error": "Cannot connect to Ollama"
        }
    except Exception as e:
        return {
            "status": "error",
            "host": OLLAMA_HOST,
            "error": str(e)
        }


def invoke_llm(
    messages: List[Dict[str, str]],
    local_llm: Optional[str] = None
) -> str:
    """
    Invoke an LLM with the given messages.

    Uses Ollama if local_llm is provided, otherwise uses OpenAI.

    Args:
        messages: List of message dicts with 'role' and 'content'
        local_llm: Optional Ollama model name. If provided, uses Ollama.

    Returns:
        The model's response content as string.

    Raises:
        Exception: If the LLM call fails.
    """
    if local_llm:
        return _invoke_ollama(messages, local_llm)
    else:
        return _invoke_openai(messages)


def _invoke_openai(messages: List[Dict[str, str]]) -> str:
    """Invoke OpenAI model."""
    langchain_messages = _convert_to_langchain_messages(messages)
    model = init_chat_model(DEFAULT_MODEL, model_provider="openai")
    response = model.invoke(langchain_messages)
    return response.content.strip()


def _invoke_ollama(messages: List[Dict[str, str]], model: str, retries: int = 2) -> str:
    """
    Invoke Ollama model with retry logic.

    Args:
        messages: List of message dicts
        model: Ollama model name
        retries: Number of retries on failure

    Returns:
        Model response content
    """
    url = f"{OLLAMA_HOST}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": "10m"  # Keep model in memory for 10 minutes
    }

    last_error = None
    for attempt in range(retries + 1):
        try:
            logger.info(f"Ollama request to {model} (attempt {attempt + 1}/{retries + 1})")
            # Longer timeout for CPU inference - 10 minutes
            response = requests.post(url, json=payload, timeout=600)
            response.raise_for_status()
            result = response.json()
            content = result.get("message", {}).get("content", "").strip()
            logger.info(f"Ollama response received ({len(content)} chars)")
            return content
        except requests.exceptions.ConnectionError as e:
            last_error = f"Cannot connect to Ollama at {OLLAMA_HOST}. Is Ollama running?"
            logger.error(last_error)
        except requests.exceptions.Timeout as e:
            last_error = f"Ollama request timed out after 600 seconds (attempt {attempt + 1})"
            logger.error(last_error)
        except requests.exceptions.HTTPError as e:
            error_text = e.response.text if e.response else str(e)
            last_error = f"Ollama HTTP error: {error_text}"
            logger.error(last_error)
            # Don't retry on HTTP errors (model not found, etc.)
            break
        except Exception as e:
            last_error = f"Ollama error: {str(e)}"
            logger.error(last_error)

        if attempt < retries:
            logger.info(f"Retrying in 5 seconds...")
            import time
            time.sleep(5)

    raise Exception(last_error)


def _convert_to_langchain_messages(messages: List[Dict[str, str]]):
    """Convert dict messages to LangChain message objects."""
    langchain_messages = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            langchain_messages.append(SystemMessage(content=content))
        else:
            langchain_messages.append(HumanMessage(content=content))
    return langchain_messages


def generate_keywords(content: str, local_llm: Optional[str] = None) -> List[str]:
    """
    Generate keywords from content using LLM.

    Args:
        content: The text to extract keywords from.
        local_llm: Optional Ollama model name.

    Returns:
        List of keywords.
    """
    if not content.strip():
        return []

    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "Jesteś pomocnym asystentem do ekstrakcji słów kluczowych z tekstu. "
                    "Zwróć TYLKO listę słów kluczowych oddzielonych przecinkami, nic więcej. "
                    "WAŻNE: Zawsze odpowiadaj WYŁĄCZNIE po polsku."
                )
            },
            {
                "role": "user",
                "content": f"Wyodrębnij 5-10 najważniejszych słów kluczowych z poniższego tekstu:\n\n{content}"
            }
        ]

        response = invoke_llm(messages, local_llm)
        keywords = [kw.strip() for kw in response.split(",") if kw.strip()]
        logger.debug(f"Generated {len(keywords)} keywords")
        return keywords
    except Exception as e:
        logger.warning(f"Failed to generate keywords: {e}")
        return []


def generate_section_context(content: str, local_llm: Optional[str] = None) -> str:
    """
    Generate a short context with key information for retrieval.

    Args:
        content: The content of the section.
        local_llm: Optional Ollama model name.

    Returns:
        A short context string with key information.
    """
    if not content.strip():
        return ""

    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "Jesteś asystentem do ekstrakcji kluczowych informacji. "
                    "Twoje zadanie to wyodrębnić najważniejsze słowa kluczowe i frazy z tekstu. "
                    "Odpowiedź powinna być krótka - maksymalnie 2-3 zdania lub lista słów kluczowych. "
                    "Skup się na: nazwach, terminach technicznych, datach, liczbach i kluczowych pojęciach. "
                    "WAŻNE: Zawsze odpowiadaj WYŁĄCZNIE po polsku."
                )
            },
            {
                "role": "user",
                "content": (
                    "Wyodrębnij kluczowe informacje z poniższej sekcji. "
                    "Podaj tylko najważniejsze słowa kluczowe i frazy (max 2-3 zdania):\n\n"
                    f"{content}"
                )
            }
        ]

        return invoke_llm(messages, local_llm)
    except Exception as e:
        logger.warning(f"Failed to generate context for section: {e}")
        return ""
