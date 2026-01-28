from typing import List, Optional
from pydantic import BaseModel, Field


class OllamaModelsResponse(BaseModel):
    """Response model for listing Ollama models."""
    models: List[str] = Field(..., description="List of available Ollama model names")


class OllamaPullRequest(BaseModel):
    """Request model for pulling an Ollama model."""
    model: str = Field(..., description="Name of the model to pull (e.g., 'llama2', 'mistral', 'codellama')")


class OllamaPullResponse(BaseModel):
    """Response model for pulling an Ollama model."""
    success: bool = Field(..., description="Whether the model was pulled successfully")
    model: str = Field(..., description="Name of the model that was pulled")
    message: str = Field(..., description="Status message")


class OllamaHealthResponse(BaseModel):
    """Response model for Ollama health check."""
    status: str = Field(..., description="Health status: 'healthy', 'unreachable', or 'error'")
    host: str = Field(..., description="Ollama host URL")
    models: Optional[List[str]] = Field(default=None, description="List of available models if healthy")
    error: Optional[str] = Field(default=None, description="Error message if not healthy")
