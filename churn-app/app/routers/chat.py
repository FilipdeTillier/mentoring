from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.models.openai import Message, ChatRequest, ChatResponse
from app.services.chat_service import chat_with_openai


router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with OpenAI",
    description="Send a chat message to OpenAI using LangChain. Accepts an array of messages (conversation history and current message) with roles: 'system', 'user', or 'assistant'.",
    response_description="The assistant's response with message content, role, model, and token usage information.",
    tags=["chat"]
)
async def chat_endpoint(request: ChatRequest):
    """
    Chat endpoint that accepts an array of messages and returns OpenAI's response.
    
    The messages array should include conversation history and the current message.
    Each message should have a 'role' ('system', 'user', or 'assistant') and 'content'.
    
    - **messages**: Array of message objects with role and content
    - **model**: Optional model name (default: gpt-3.5-turbo)
    """
    try:
        messages_dict = [{"role": msg.role, "content": msg.content} for msg in request.choices]
        
        result = chat_with_openai(
            choices=messages_dict,
            model=request.model or "gpt-3.5-turbo"
        )
        
        return ChatResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calling OpenAI: {str(e)}")

