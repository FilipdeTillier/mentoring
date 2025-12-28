import chainlit as cl
import requests
import json

BACKEND_URL = "http://localhost:8000/api/chat"
Model_Name = "gpt-3.5-turbo"

@cl.on_chat_start
async def start():
    """
    This function runs when the chat session starts.
    You can use it to set up initial context or welcome messages.
    """
    cl.user_session.set("conversation_history", [])
    await cl.Message(content="Welcome! I am connected to your RAG backend.").send()

@cl.on_message
async def main(message: cl.Message):
    """
    This function is triggered when the user sends a message.
    """
    
    conversation_history = cl.user_session.get("conversation_history", [])

    user_message = {
        "role": "user",
        "content": message.content
    }
    conversation_history.append(user_message)
    
    cl.user_session.set("conversation_history", conversation_history)
    
    payload = {
        "choices": conversation_history,
        "model": Model_Name
    }

    try:
        response = requests.post(
            BACKEND_URL, 
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()

        response_data = response.json()

        choices = response_data.get("choices", [])
        if choices:
    
            last_message = choices[-1]
            
    
            if last_message.get("role") == "assistant":
                assistant_content = last_message.get("content", "No response content")
                
                conversation_history.append(last_message)
        
                cl.user_session.set("conversation_history", conversation_history)
        
                assistant_msg = cl.Message(
                    content=assistant_content,
                    author="Assistant"
                )
                await assistant_msg.send()
            else:
                error_msg = cl.Message(content="Unexpected response format from backend")
                await error_msg.send()
        else:
            error_msg = cl.Message(content="No response received from backend")
            await error_msg.send()

    except requests.exceptions.RequestException as e:
        error_msg = cl.Message(content=f"**Error connecting to backend:** {e}")
        await error_msg.send()
        