"""
Multi-Agent session wrapper — manages conversation state across turns.

Bridges the stateless LangGraph compiled graph with persistent session context.
Each call reinjects persisted entities (medications, symptoms, nutrients, products)
into the graph state, then extracts updated entities from the result.
"""

import logging
from typing import Dict, Any

from langchain_core.messages import HumanMessage, AIMessage

from src.multi_agent.graph import build_multi_agent_graph

logger = logging.getLogger(__name__)

# Singleton compiled graph
_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_multi_agent_graph()
    return _compiled_graph


class MultiAgentSession:
    """
    Manages a conversation session with the multi-agent graph.

    Maintains persisted context (medications, symptoms, nutrients, products)
    across turns, and injects them back into each graph invocation.
    """

    def __init__(self, session_id: str = None):
        self.session_id = session_id
        self.history: list = []
        self.persisted_medications: list[str] = []
        self.persisted_symptoms: list[str] = []
        self.persisted_nutrients: list[str] = []
        self.persisted_products: list[str] = []

    def chat(self, user_message: str) -> str:
        """Send a message and get a response."""
        result = self.run(user_message)
        return result.get("final_response", "Sorry, I couldn't process your request.")

    def run(self, user_message: str) -> Dict[str, Any]:
        """
        Run the full multi-agent graph for one conversation turn.

        Returns the full result dict including final_response, execution_path, etc.
        """
        graph = _get_graph()

        # Build input state with conversation history and persisted context
        input_state = {
            "messages": self.history + [HumanMessage(content=user_message)],
            "session_id": self.session_id or "anonymous",
            "persisted_medications": self.persisted_medications,
            "persisted_symptoms": self.persisted_symptoms,
            "persisted_nutrients": self.persisted_nutrients,
            "persisted_products": self.persisted_products,
            # Reset per-turn fields
            "worker_results": [],
            "supervisor_reasoning": [],
            "supervisor_loop_count": 0,
            "guardrail_retry_count": 0,
            "guardrail_feedback": "",
            "guardrail_pass": True,
            "safety_flags": [],
            "execution_path": [],
        }

        try:
            result = graph.invoke(input_state, config={"recursion_limit": 20})

            final_response = result.get("final_response", "I couldn't generate a response.")
            execution_path = result.get("execution_path", [])

            # Update persisted context from result
            self.persisted_medications = result.get("persisted_medications", self.persisted_medications)
            self.persisted_symptoms = result.get("persisted_symptoms", self.persisted_symptoms)
            self.persisted_nutrients = result.get("persisted_nutrients", self.persisted_nutrients)
            self.persisted_products = result.get("persisted_products", self.persisted_products)

            # Update conversation history
            self.history.append(HumanMessage(content=user_message))
            self.history.append(AIMessage(content=final_response))

            logger.info(
                f"Multi-agent turn complete. "
                f"Path: {' → '.join(execution_path)}. "
                f"Context: meds={self.persisted_medications}, "
                f"symptoms={self.persisted_symptoms}, "
                f"nuts={self.persisted_nutrients}"
            )

            return {
                "final_response": final_response,
                "execution_path": execution_path,
                "medications": self.persisted_medications,
                "symptoms": self.persisted_symptoms,
                "nutrients": self.persisted_nutrients,
                "products": self.persisted_products,
            }

        except Exception as e:
            logger.error(f"Multi-agent graph error: {e}", exc_info=True)
            error_msg = "I'm sorry, I encountered an error. Could you please try again?"
            self.history.append(HumanMessage(content=user_message))
            self.history.append(AIMessage(content=error_msg))
            return {
                "final_response": error_msg,
                "execution_path": ["error"],
                "error": str(e),
            }

    def clear_history(self):
        """Reset the session."""
        self.history = []
        self.persisted_medications = []
        self.persisted_symptoms = []
        self.persisted_nutrients = []
        self.persisted_products = []

    def get_history(self):
        return self.history
