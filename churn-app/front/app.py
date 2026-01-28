import os
import chainlit as cl
import requests
import sys
sys.path.insert(0, '..')

from app.const import DEFAULT_MODEL

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/api")


async def fetch_available_files():
    """Fetch list of available files from backend."""
    try:
        response = requests.get(f"{BACKEND_URL}/files")
        response.raise_for_status()
        data = response.json()
        return data.get("files", [])
    except Exception as e:
        print(f"Error fetching files: {e}")
        return []


async def upload_files_to_backend(files):
    """Upload files to backend and return job_id."""
    try:
        files_data = []
        for file in files:
            files_data.append(
                ("files", (file.name, open(file.path, "rb")))
            )

        response = requests.post(
            f"{BACKEND_URL}/upload",
            files=files_data
        )
        response.raise_for_status()

        for _, (_, f) in files_data:
            f.close()

        return response.json()
    except Exception as e:
        print(f"Error uploading files: {e}")
        return None


@cl.on_chat_start
async def start():
    """Initialize chat session with file selection."""
    cl.user_session.set("conversation_history", [])
    cl.user_session.set("selected_file_ids", [])

    await cl.Message(
        content="Welcome! I am connected to your RAG backend.\n\n"
                "You can:\n"
                "- **Upload files** by attaching them to your message\n"
                "- **Select files** to search using the settings panel (click ⚙️)\n\n"
                "Send a message to start chatting!"
    ).send()

    await update_file_settings()


async def update_file_settings():
    """Update the settings panel with available files."""
    files = await fetch_available_files()

    if files:
        file_options = {f["file_name"]: f["file_id"] for f in files}
        cl.user_session.set("file_options", file_options)

        settings = await cl.ChatSettings(
            [
                cl.input_widget.Select(
                    id="selected_files",
                    label="Search in files (leave empty for all)",
                    values=["All files"] + list(file_options.keys()),
                    initial_value="All files"
                )
            ]
        ).send()


@cl.on_settings_update
async def handle_settings_update(settings):
    """Handle settings changes."""
    selected = settings.get("selected_files", "All files")
    file_options = cl.user_session.get("file_options", {})

    if selected == "All files":
        cl.user_session.set("selected_file_ids", [])
    else:
        file_id = file_options.get(selected)
        if file_id:
            cl.user_session.set("selected_file_ids", [file_id])

    await cl.Message(
        content=f"📁 File filter updated: **{selected}**"
    ).send()


@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages and file uploads."""

    # Handle file uploads
    if message.elements:
        files_to_upload = [el for el in message.elements if isinstance(el, cl.File)]

        if files_to_upload:
            upload_msg = cl.Message(content="📤 Uploading files...")
            await upload_msg.send()

            result = await upload_files_to_backend(files_to_upload)

            if result:
                job_id = result.get("job_id", "unknown")
                file_count = result.get("file_count", 0)
                upload_msg.content = (
                    f"✅ Successfully uploaded {file_count} file(s).\n"
                    f"Job ID: `{job_id}`\n\n"
                    "Files are being processed in the background. "
                    "They will be available for search shortly."
                )
                await upload_msg.update()

                # Refresh file list after a short delay
                await cl.sleep(2)
                await update_file_settings()
            else:
                upload_msg.content = "❌ Failed to upload files. Please try again."
                await upload_msg.update()

            # If only files were sent (no text), return
            if not message.content.strip():
                return

    # Handle chat messages
    conversation_history = cl.user_session.get("conversation_history", [])
    selected_file_ids = cl.user_session.get("selected_file_ids", [])

    user_message = {
        "role": "user",
        "content": message.content
    }
    conversation_history.append(user_message)
    cl.user_session.set("conversation_history", conversation_history)

    payload = {
        "choices": conversation_history,
        "model": DEFAULT_MODEL,
        "file_ids": selected_file_ids if selected_file_ids else None
    }

    try:
        async with cl.Step(name="Thinking", type="llm") as step:
            response = requests.post(
                f"{BACKEND_URL}/chat",
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
