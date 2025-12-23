import os
from typing import List, Dict, Any
from app.helpers.message_categorizer import categorize_messages

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

 

def chat_with_openai(
    choices: List[Dict[str, str]], model: str = "gpt-3.5-turbo"
) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    os.environ["OPENAI_API_KEY"] = api_key

    try:
        chat_model = init_chat_model(model)
        categorized_messages = categorize_messages(choices)
        response = chat_model.invoke(categorized_messages)

        usage = {}
        if hasattr(response, "response_metadata") and response.response_metadata:
            token_usage = response.response_metadata.get("token_usage", {})
            usage = {
                "prompt_tokens": token_usage.get("prompt_tokens", 0),
                "completion_tokens": token_usage.get("completion_tokens", 0),
                "total_tokens": token_usage.get("total_tokens", 0),
            }
        

        return {
            "choices": choices + [{"role": "assistant", "content": response.content}],
            "model": model,
            "usage": usage,
        }
    except Exception as e:
        raise Exception(f"OpenAI API error: {str(e)}")
