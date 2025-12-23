from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import HumanMessage, AIMessage

from src.agent.state import MedicalAgentState, create_initial_state, print_state_debug
from src.agent.nodes.conversation_analyzer import conversation_analyzer_node
from src.agent.nodes.entity_extractor import entity_extractor_node
from src.agent.nodes.cypher_generator import cypher_generator_node
from src.agent.nodes.graph_executor import graph_executor_node
from src.agent.nodes.response_synthesizer import response_synthesizer_node
from src.agent.nodes.off_topic_response import off_topic_response_node
from src.agent.nodes.error_node import error_response_node


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def route_after_conversation_analysis(state: MedicalAgentState) -> Literal["clarify", "extract_entities", "end"]:
    """
    Determine the next step after conversation analysis.
    
    Routes to:
    - "clarify": If we need more information from the user
    - "extract_entities": If we have enough info to proceed
    - "end": If the query is off-topic
    """
    # Get analysis from state
    analysis = state.get("conversation_analysis")
    
    if analysis is None or analysis.clarification_question is not None:
        return "clarify"  # Safe fallback
    
    # Access fields from the Pydantic model
    retrieval_type = analysis.retrieval_type
    needs_clarification = analysis.needs_clarification
    
    # Off-topic queries go straight to response
    if retrieval_type == "NO_RETRIEVAL":
        return "end"
    
    # If we need clarification, go to response to ask the question
    if needs_clarification:
        return "clarify"
    
    # Otherwise, proceed with entity extraction
    return "extract_entities"


def route_after_cypher_generation(state: MedicalAgentState) -> Literal["execute", "respond_error"]:
    """
    Determine whether to execute the Cypher or respond with an error.
    """
    cypher_is_valid = state.get("cypher_is_valid", False)
    generated_cypher = state.get("generated_cypher", "")
    
    if cypher_is_valid and generated_cypher:
        return "execute"
    else:
        return "respond_error"


# ═══════════════════════════════════════════════════════════════════════════════
# BUILD THE GRAPH
# ═══════════════════════════════════════════════════════════════════════════════

def create_medical_agent_graph():
    
    workflow = StateGraph(MedicalAgentState)
    
    workflow.add_node("conversation_analyzer", conversation_analyzer_node)
    workflow.add_node("entity_extractor", entity_extractor_node)
    workflow.add_node("graph_executor", graph_executor_node)
    workflow.add_node("response_synthesizer", response_synthesizer_node)
    workflow.add_node("off_topic_response", off_topic_response_node)

    workflow.set_entry_point("conversation_analyzer")
    workflow.add_conditional_edges(
        "conversation_analyzer",
        route_after_conversation_analysis,
        {
            "clarify": "response_synthesizer",      # Ask clarification question
            "extract_entities": "entity_extractor", # Proceed with extraction
            "end": "off_topic_response"             # Off-topic response
        }
    )
    workflow.add_edge("entity_extractor", "graph_executor")
    workflow.add_edge("graph_executor", "response_synthesizer")
    workflow.add_edge("response_synthesizer", END)
    return workflow.compile()


_compiled_graph = None


def get_medical_agent():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = create_medical_agent_graph()
    return _compiled_graph

graph = get_medical_agent()


def run_medical_query(user_message: str, conversation_history: list = None) -> Dict[str, Any]:
    
    # Create initial state
    initial_state = create_initial_state(
        user_message=user_message,
        conversation_history=conversation_history
    )
    
    # Get the compiled graph and run
    agent = get_medical_agent()
    
    try:
        result = agent.invoke(initial_state)
        print_state_debug(result)
        return result
    except Exception as e:
        # Return error state
        return {
            **initial_state,
            "final_response": f"An error occurred: {str(e)}",
            "errors": [str(e)],
            "execution_path": ["error"]
        }


def chat(user_message: str, conversation_history: list = None) -> str:
    """
    Simple chat interface - returns just the response string.
    
    Args:
        user_message: The user's message
        conversation_history: Previous messages (optional)
        
    Returns:
        The agent's response as a string
    """
    result = run_medical_query(user_message, conversation_history)
    return result.get("final_response", "Sorry, I couldn't process your request.")


# ═══════════════════════════════════════════════════════════════════════════════
# CONVERSATION SESSION CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class MedicalChatSession:
    """
    A conversation session that maintains history across multiple turns.
    
    Usage:
        session = MedicalChatSession()
        response1 = session.chat("Ce nutrienți depletează Tylenol?")
        response2 = session.chat("Și ce simptome pot avea?")  # Uses context
    """
    
    def __init__(self):
        self.history = []
    
    def chat(self, user_message: str) -> str:
        """
        Send a message and get a response, maintaining conversation history.
        
        Args:
            user_message: The user's message
            
        Returns:
            The agent's response
        """
        # Run the query with history
        result = run_medical_query(user_message, self.history)
        
        # Update history
        self.history.append(HumanMessage(content=user_message))
        response = result.get("final_response", "")
        self.history.append(AIMessage(content=response))
        
        return response
    
    def get_full_result(self, user_message: str) -> Dict[str, Any]:
        """
        Send a message and get the full result dict (for debugging).
        """
        result = run_medical_query(user_message, self.history)
        
        # Update history
        self.history.append(HumanMessage(content=user_message))
        response = result.get("final_response", "")
        self.history.append(AIMessage(content=response))
        
        return result
    
    def clear_history(self):
        """Clear the conversation history."""
        self.history = []
    
    def get_history(self) -> list:
        """Get the current conversation history."""
        return self.history
