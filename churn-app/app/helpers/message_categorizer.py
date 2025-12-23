from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

def categorize_messages(choices):
    categorized = []
    for i, msg in enumerate(choices):
        if not isinstance(msg, dict):
            raise ValueError(f"Message at index {i} must be a dictionary, got {type(msg).__name__}")
        role = msg.get("role")
        content = msg.get("content")
        if not role:
            raise ValueError(f"Message at index {i} is missing 'role' field")
        if not isinstance(role, str):
            raise ValueError(f"Message at index {i} has invalid role type: {type(role).__name__}, expected string")
        if content is None:
            raise ValueError(f"Message at index {i} is missing 'content' field")
        if not isinstance(content, str):
            raise ValueError(f"Message at index {i} has invalid content type: {type(content).__name__}, expected string")
        role_lower = role.lower().strip()
        if role_lower == "system":
            categorized.append(SystemMessage(content=content))
        elif role_lower == "user":
            categorized.append(HumanMessage(content=content))
        elif role_lower == "assistant":
            categorized.append(AIMessage(content=content))
        else:
            raise ValueError(f"Unknown message role: '{role}' (valid roles: 'system', 'user', 'assistant')")
    return categorized

