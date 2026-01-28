from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.models.openai import Message, ChatRequest, ChatResponse
from app.services.chat_service import chat_with_openai
from app.services.ollama_service import chat_with_ollama, list_available_models, pull_model
from app.services.llm_service import check_ollama_health
from app.models.ollama import OllamaModelsResponse, OllamaPullRequest, OllamaPullResponse, OllamaHealthResponse
from app.services.qdrant_service import QdrantService
from app.const import DEFAULT_MODEL


router = APIRouter()

# System instructions only - no context here
SYSTEM_INSTRUCTIONS = """Jesteś pomocnym asystentem. Przestrzegaj poniższych zasad:

1. Odpowiadaj WYŁĄCZNIE na podstawie dostarczonego kontekstu z dokumentów.
2. Jeśli kontekst nie zawiera informacji potrzebnych do odpowiedzi, poinformuj użytkownika: "Nie znalazłem informacji na ten temat w dostępnych dokumentach."
3. NIE wymyślaj odpowiedzi ani nie korzystaj z wiedzy spoza kontekstu.
4. Zawsze odpowiadaj w tym samym języku, w którym użytkownik zadał pytanie.
5. Jeśli użytkownik pyta o konkretną stronę, sekcję lub plik - używaj TYLKO informacji z tych źródeł.
6. Na końcu odpowiedzi podaj źródła w formacie: "(Źródło: [nazwa pliku], strona [numer])"
7. Jeśli znaleziono informacje w wielu miejscach, wymień wszystkie źródła."""


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with LLM (OpenAI or local Ollama)",
    description="Send a chat message to OpenAI or local Ollama model. Accepts an array of messages (conversation history and current message) with roles: 'system', 'user', or 'assistant'. Use 'local_llm' parameter to use a local Ollama model instead of OpenAI.",
    response_description="The assistant's response with message content, role, model, and token usage information.",
    tags=["chat"]
)
async def chat_endpoint(request: ChatRequest):
    """
    Chat endpoint that accepts an array of messages and returns LLM response.

    The messages array should include conversation history and the current message.
    Each message should have a 'role' ('system', 'user', or 'assistant') and 'content'.

    - **messages**: Array of message objects with role and content
    - **model**: Optional OpenAI model name (default: DEFAULT_MODEL)
    - **local_llm**: Optional local Ollama model name (e.g., 'llama2', 'mistral'). If provided, uses Ollama instead of OpenAI.
    - **file_ids**: Optional array of file IDs to filter search (searches all if empty)
    """
    try:
        # Extract last user message for context search
        last_user_message = next(
            (msg.content for msg in reversed(request.choices) if msg.role == "user"),
            None
        )
        context = ""

        if last_user_message:
            try:
                qdrant_service = QdrantService()
                context = qdrant_service.hybrid_search(
                    query=last_user_message,
                    limit=3,
                    file_ids=request.file_ids
                )
            except Exception as e:
                print(f"Error fetching context: {e}")

        messages_dict = []

        messages_dict.append({
            "role": "system",
            "content": SYSTEM_INSTRUCTIONS
        })

        if context:
            context_message = f"""Poniżej znajduje się kontekst z dokumentów, który pomoże Ci odpowiedzieć na pytanie użytkownika:

                ---
                {context}
                ---

            Użyj powyższego kontekstu do udzielenia odpowiedzi. Pamiętaj o podaniu źródeł."""
            messages_dict.append({
                "role": "user",
                "content": f"""
                    ============== PYTANIE ==============
                    {context_message}
                """
            })
        else:
            messages_dict.append({
                "role": "user",
                "content": "Nie znaleziono żadnych dokumentów pasujących do zapytania."
            })
            messages_dict.append({
                "role": "assistant",
                "content": "Rozumiem. Poinformuję użytkownika, że nie mam dostępu do dokumentów na ten temat."
            })

        for msg in request.choices:
            if msg.role != "system":
                messages_dict.append({"role": msg.role, "content": msg.content})
                
        if request.local_llm:
            result = chat_with_ollama(
                choices=messages_dict,
                model=request.local_llm
            )
        else:
            result = chat_with_openai(
                choices=messages_dict,
                model=request.model or DEFAULT_MODEL
            )

        return ChatResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        provider = "Ollama" if request.local_llm else "OpenAI"
        raise HTTPException(status_code=500, detail=f"Error calling {provider}: {str(e)}")


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


@router.get(
    "/ollama/models",
    response_model=OllamaModelsResponse,
    summary="List available Ollama models",
    description="Get a list of all models available in the local Ollama instance.",
    tags=["ollama"]
)
async def list_ollama_models():
    """List all available models in Ollama."""
    try:
        models = list_available_models()
        return OllamaModelsResponse(models=models)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing Ollama models: {str(e)}")


@router.post(
    "/ollama/pull",
    response_model=OllamaPullResponse,
    summary="Pull an Ollama model",
    description="Download a model from the Ollama registry to the local instance.",
    tags=["ollama"]
)
async def pull_ollama_model(request: OllamaPullRequest):
    """Pull a model from Ollama registry."""
    try:
        success = pull_model(request.model)
        if success:
            return OllamaPullResponse(
                success=True,
                model=request.model,
                message=f"Model '{request.model}' pulled successfully"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to pull model '{request.model}'"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error pulling model: {str(e)}")


class OllamaHealthResponse(BaseModel):
    """Response model for Ollama health check."""
    status: str = Field(..., description="Health status: 'healthy', 'unreachable', or 'error'")
    host: str = Field(..., description="Ollama host URL")
    models: Optional[List[str]] = Field(default=None, description="List of available models if healthy")
    error: Optional[str] = Field(default=None, description="Error message if not healthy")


@router.get(
    "/ollama/health",
    response_model=OllamaHealthResponse,
    summary="Check Ollama health",
    description="Check if Ollama is reachable and list available models.",
    tags=["ollama"]
)
async def check_ollama_status():
    """Check Ollama health and connectivity."""
    result = check_ollama_health()
    return OllamaHealthResponse(**result)
