import os
import time
from typing import List, Dict, Any

import mlflow
from langchain.chat_models import init_chat_model

from app.helpers.message_categorizer import categorize_messages
from app.const import DEFAULT_MODEL

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"))
mlflow.set_experiment("llm-requests")


def chat_with_openai(
    choices: List[Dict[str, str]], model: str = DEFAULT_MODEL
) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    start_time = time.perf_counter()

    with mlflow.start_run():
        mlflow.log_param("model", model)
        mlflow.log_param("num_messages", len(choices))

        try:
            chat_model = init_chat_model(model)
            response = chat_model.invoke(categorize_messages(choices))

            usage = response.response_metadata.get("token_usage", {})
            latency_ms = (time.perf_counter() - start_time) * 1000

            mlflow.log_metrics({
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "latency_ms": latency_ms,
            })

            return {
                "choices": choices + [{"role": "assistant", "content": response.content}],
                "model": model,
                "usage": usage,
            }
        except Exception as e:
            mlflow.log_param("error", str(e)[:250])
            raise Exception(f"OpenAI API error: {str(e)}")
