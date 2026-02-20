import os
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
import logging
import functools
 
logger = logging.getLogger(__name__)
 
_langfuse_client = None
 
def get_langfuse_client() -> Langfuse:
    global _langfuse_client
   
    if _langfuse_client is None:
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        host = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
       
        if not public_key or not secret_key:
            raise ValueError(
                "Langfuse credentials not configured. "
                "Please set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY"
            )
       
        _langfuse_client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
            debug=os.getenv("LANGFUSE_DEBUG", "false").lower() == "true"
        )
   
    return _langfuse_client
 
 
def get_prompt_from_langfuse(prompt_name: str, version: int = None, label: str = "production") -> str:
 
    langfuse = get_langfuse_client()
   
    try:
        logger.info(f"Fetching prompt '{prompt_name}' from Langfuse (label: {label})")
        prompt = langfuse.get_prompt(prompt_name, version=version, type="chat", label=label, cache_ttl_seconds=0)
        logger.info(f"Successfully fetched prompt '{prompt_name}' from Langfuse (label: {label})")
        return prompt #type is LangfusePrompt, not ChatPromptTemplate
    except Exception as e:
        logger.error(f"Error fetching prompt '{prompt_name}': {e}", exc_info=True)
        return None
 
def get_prompt_with_variables(prompt_name: str, variables: dict, version: int = None) -> str:
 
    langfuse = get_langfuse_client()
   
    try:
        prompt = langfuse.get_prompt(prompt_name, version=version)
        # Compile variables
        return prompt.compile(**variables)
    except Exception as e:
        logger.error(f"Error compiling prompt '{prompt_name}': {e}")
        return None
 
def get_langfuse_handler():
 
    return CallbackHandler()
 
 
def observe_span(name: str = None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            langfuse = get_langfuse_client()
            span_name = name or func.__name__
           
            # Create a new span
            span = langfuse.span(
                name=span_name,
                input={"args": args, "kwargs": kwargs}
            )
           
            try:
                result = func(*args, **kwargs)
                # End the span successfully
                span.end(output=result)
                return result
            except Exception as e:
                # End the span with an error and propagate it further
                span.end(level="ERROR", status_message=str(e))
                raise e
        return wrapper
    return decorator
 
 
def flush_langfuse():
    """Flush all pending events to Langfuse."""
    if _langfuse_client:
        _langfuse_client.flush()