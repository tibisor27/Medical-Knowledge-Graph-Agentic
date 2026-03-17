import logging
from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from langfuse import observe, propagate_attributes

# from langfuse import observe, propagate_attributes  # TEMP: disabled for testing
# from src.utils.langfuse_client import observe  # STUB
from src.agent.state import ConversationState
from src.agent.agent_factory import get_medical_agent
from src.agent.prompt_builder import PromptBuilder
from src.agent.extractors import (
    extract_final_response, extract_tool_calls,
    extract_entities_from_tools, extract_nutrients_from_results,
    extract_products_from_results,
)
from src.utils.langfuse_client import get_langfuse_handler
logger = logging.getLogger(__name__)

class MedicalAgent:
    def __init__(self, session_id: str = None):
        self.session_state = ConversationState(session_id)
        self.prompt_builder = PromptBuilder()

    def chat(self, user_message: str) -> str:
        result = self.run_medical_query(user_message)
        return result.get("final_response", "Sorry, I couldnt process your request")

    @observe()
    def run_medical_query(self, user_message: str) -> Dict[str, Any]:
        try:
            with propagate_attributes(
                session_id=self.session_state.session_id,
                user_id=self.session_state.session_id or "anonymous"
            ):
                langfuse_handler = get_langfuse_handler()

            user_context = self.session_state.build_context_string()
            system_prompt = self.prompt_builder.build_system_prompt(user_context)

            messages = [SystemMessage(content=system_prompt)]

            messages.extend(self.session_state.history)

            messages.append(HumanMessage(content=user_message))

                
            agent = get_medical_agent()
            
            logger.info(f"  Context: meds={self.session_state.medications}, symptoms={self.session_state.symptoms}, nuts={self.session_state.nutrients}")
            
            result = agent.invoke(
                {"messages": messages},
                config={
                    "callbacks": [langfuse_handler],
                    "recursion_limit": 15
                }
            )

            final_response = extract_final_response(result)

            tool_calls = extract_tool_calls(result)
                
            logger.info(f"  Tools called: {[tc['tool'] for tc in tool_calls]}")
            # 6. Update state from tool calls (medications, symptoms from args)
            extract_entities_from_tools(result, self.session_state)
            # 7. Extract entities from tool RESULTS (nutrients from depletions)
            extract_nutrients_from_results(result.get("messages", []), self.session_state)
            extract_products_from_results(result.get("messages", []), self.session_state)
            logger.info(f"  Updated: meds={self.session_state.medications}, "
                        f"symptoms={self.session_state.symptoms}, "
                        f"nuts={self.session_state.nutrients}")
            # 8. Save conversation turn
            self.session_state.update_history(user_message, final_response)
            return {
                "final_response": final_response,
                "tool_calls": tool_calls,
                "medications": self.session_state.medications,
                "symptoms": self.session_state.symptoms,
                "nutrients": self.session_state.nutrients,
                "products": self.session_state.products,
            }
        except Exception as e:
            logger.error(f"ReAct agent error: {e}", exc_info=True)
            error_msg = "I'm sorry, I encountered an error processing your request. Could you please try again?"
            self.session_state.update_history(user_message, error_msg)
            return {
                "final_response": error_msg,
                "tool_calls": [],
                "error": str(e)
            }
    
    def clear_history(self):
        self.session_state.clear_history()
    
    def get_history(self):
        return self.session_state.history
