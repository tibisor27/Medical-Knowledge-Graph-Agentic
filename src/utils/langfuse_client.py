"""
Langfuse client — STUB for testing (langfuse not installed).
In production, integrate with real Langfuse observability.
"""

def observe(*args, **kwargs):
    """Stub decorator: does nothing."""
    def decorator(func):
        return func
    if args and callable(args[0]):
        return args[0]
    return decorator


def get_langfuse_handler():
    """Stub: return None for now."""
    return None


def get_prompt_from_langfuse(prompt_name: str, **kwargs):
    """Stub: return the prompt_name as-is. No actual Langfuse integration yet."""
    return ""
