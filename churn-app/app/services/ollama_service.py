import os
import time
import logging
from typing import List, Dict, Any

import requests
import mlflow

from app.helpers.message_categorizer import categorize_messages

logger = logging.getLogger(__name__)

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"))
mlflow.set_experiment("llm-requests")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


def _convert_messages_to_ollama_format(choices: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Convert messages to Ollama format.

    Ollama uses the same format as OpenAI (role, content),
    so this is mainly for validation and consistency.
    """
    ollama_messages = []
    for msg in choices:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        ollama_messages.append({
            "role": role,
            "content": content
        })
    return ollama_messages


def _map_ollama_response_to_openai_format(
    ollama_response: Dict[str, Any],
    model: str,
    choices: List[Dict[str, str]]
) -> Dict[str, Any]:
    """
    Map Ollama response to OpenAI-compatible format.

    Ollama response structure:
    {
        "model": "llama2",
        "created_at": "2023-08-04T08:52:19.385406455Z",
        "message": {
            "role": "assistant",
            "content": "The sky is blue because..."
        },
        "done": true,
        "total_duration": 5043500667,
        "load_duration": 5025959,
        "prompt_eval_count": 26,
        "prompt_eval_duration": 325953000,
        "eval_count": 290,
        "eval_duration": 4709213000
    }

    OpenAI-compatible format we need:
    {
        "choices": [...messages..., {"role": "assistant", "content": "..."}],
        "model": "model_name",
        "usage": {
            "prompt_tokens": X,
            "completion_tokens": Y,
            "total_tokens": Z
        }
    }
    """
    message = ollama_response.get("message", {})
    assistant_content = message.get("content", "")

    # Map Ollama's token counts to OpenAI format
    prompt_tokens = ollama_response.get("prompt_eval_count", 0)
    completion_tokens = ollama_response.get("eval_count", 0)

    usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens
    }

    return {
        "choices": choices + [{"role": "assistant", "content": assistant_content}],
        "model": model,
        "usage": usage
    }


def chat_with_ollama(
    choices: List[Dict[str, str]],
    model: str
) -> Dict[str, Any]:
    """
    Chat with a local Ollama model.

    Args:
        choices: List of message dicts with 'role' and 'content'
        model: Name of the Ollama model to use (e.g., 'llama2', 'mistral', 'codellama')

    Returns:
        Dict with 'choices', 'model', and 'usage' in OpenAI-compatible format

    Raises:
        Exception: If Ollama API call fails
    """
    start_time = time.perf_counter()

    with mlflow.start_run():
        mlflow.log_param("model", model)
        mlflow.log_param("provider", "ollama")
        mlflow.log_param("num_messages", len(choices))

        try:
            ollama_messages = _convert_messages_to_ollama_format(choices)

            url = f"{OLLAMA_HOST}/api/chat"
            payload = {
                "model": model,
                "messages": ollama_messages,
                "stream": False
            }

            logger.info(f"Sending request to Ollama at {url} with model {model}")

            response = requests.post(
                url,
                json=payload,
                timeout=300  # 5 minute timeout for local models
            )
            response.raise_for_status()

            ollama_response = response.json()
            latency_ms = (time.perf_counter() - start_time) * 1000

            result = _map_ollama_response_to_openai_format(
                ollama_response,
                model,
                choices
            )

            mlflow.log_metrics({
                "prompt_tokens": result["usage"].get("prompt_tokens", 0),
                "completion_tokens": result["usage"].get("completion_tokens", 0),
                "total_tokens": result["usage"].get("total_tokens", 0),
                "latency_ms": latency_ms,
            })

            logger.info(f"Ollama response received in {latency_ms:.2f}ms")

            return result

        except requests.exceptions.ConnectionError as e:
            error_msg = f"Cannot connect to Ollama at {OLLAMA_HOST}. Is Ollama running?"
            mlflow.log_param("error", error_msg[:250])
            logger.error(error_msg)
            raise Exception(error_msg) from e

        except requests.exceptions.Timeout as e:
            error_msg = f"Ollama request timed out after 300 seconds"
            mlflow.log_param("error", error_msg)
            logger.error(error_msg)
            raise Exception(error_msg) from e

        except requests.exceptions.HTTPError as e:
            error_msg = f"Ollama API error: {e.response.text if e.response else str(e)}"
            mlflow.log_param("error", error_msg[:250])
            logger.error(error_msg)
            raise Exception(error_msg) from e

        except Exception as e:
            mlflow.log_param("error", str(e)[:250])
            logger.error(f"Ollama error: {str(e)}")
            raise Exception(f"Ollama API error: {str(e)}") from e


def list_available_models() -> List[str]:
    """
    List available models from Ollama.

    Returns:
        List of model names available in Ollama
    """
    try:
        url = f"{OLLAMA_HOST}/api/tags"
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()
        models = [model["name"] for model in data.get("models", [])]
        return models

    except Exception as e:
        logger.error(f"Failed to list Ollama models: {e}")
        return []


def pull_model(model: str) -> bool:
    """
    Pull a model from Ollama registry.

    Args:
        model: Name of the model to pull (e.g., 'llama2', 'mistral')

    Returns:
        True if successful, False otherwise
    """
    try:
        url = f"{OLLAMA_HOST}/api/pull"
        payload = {"name": model, "stream": False}

        logger.info(f"Pulling model {model} from Ollama...")
        response = requests.post(url, json=payload, timeout=600)
        response.raise_for_status()

        logger.info(f"Successfully pulled model {model}")
        return True

    except Exception as e:
        logger.error(f"Failed to pull model {model}: {e}")
        return False
