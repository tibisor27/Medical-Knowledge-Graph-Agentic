import logging
from langchain_core.prompts import ChatPromptTemplate
from src.prompts import REACT_SYSTEM_PROMPT
from src.utils.langfuse_client import get_prompt_from_langfuse

logger = logging.getLogger(__name__)

FALLBACK_PROMPT = ChatPromptTemplate.from_messages([
    ("system", REACT_SYSTEM_PROMPT),
])


class PromptBuilder:

    def __init__(self, langfuse_prompt_name: str = "REACT_AGENT"):
        self.prompt_name = langfuse_prompt_name

    def build_system_prompt(self, context_string: str) -> str:
        try:
            langfuse_prompt = get_prompt_from_langfuse(self.prompt_name)

            if langfuse_prompt:
                logger.info(f"Langfuse Prompt Version: {langfuse_prompt.version}")
                #LangFuse prompt works with .compile()
                compiled_chat = langfuse_prompt.compile(user_context=context_string)

                for msg in compiled_chat:
                    if msg["role"] == "system":
                        return msg["content"]

        except Exception as e:
            logger.warning(f"Could not fetch prompt from Langfuse: {e}. Using fallback.")

        logger.info("FALLBACK ACTIVATED: Using local AGENT_PROMPT")
        return FALLBACK_PROMPT.format(user_context=context_string)