from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

from app.const import DEFAULT_MODEL

class Message(BaseModel):
    """Message model matching LangChain/OpenAI format."""
    role: Literal["system", "user", "assistant"] = Field(..., description="Message role: 'system', 'user', or 'assistant'")
    content: str = Field(..., description="Message content")
    
    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if isinstance(v, str):
            v_lower = v.lower().strip()
            if v_lower in ["system", "user", "assistant"]:
                return v_lower
        raise ValueError(f"Invalid role: '{v}'. Must be one of: 'system', 'user', 'assistant'")


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    choices: List[Message] = Field(..., description="Array of messages (history and current message)")
    model: Optional[str] = Field(
        default=DEFAULT_MODEL,
        description=f"OpenAI model to use (default: {DEFAULT_MODEL})"
    )
    file_ids: Optional[List[str]] = Field(
        default=None,
        description="Array of file IDs to filter Qdrant search. If empty or None, searches all files."
    )
    local_llm: Optional[str] = Field(
        default=None,
        description="Local Ollama model name (e.g., 'llama2', 'mistral', 'codellama'). "
                    "If provided, uses local Ollama instead of OpenAI."
    )

class Usage(BaseModel):
    """Token usage information from OpenAI."""
    prompt_tokens: int = Field(..., description="Number of prompt tokens used")
    completion_tokens: int = Field(..., description="Number of completion tokens generated")
    total_tokens: int = Field(..., description="Total number of tokens used")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    choices: List[Message] = Field(..., description="The assistant's response message")
    model: Optional[str] = Field(
        default=DEFAULT_MODEL,
        description=f"OpenAI model to use (default: {DEFAULT_MODEL})"
    )
    usage: Optional[Usage] = Field(
        default=None,
        description="Token usage information from OpenAI",
        examples=[
            {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        ]
    )
