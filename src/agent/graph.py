import logging
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import HumanMessage, AIMessage
from src.agent.state import MedicalAgentState, RetrievalType, create_initial_state, print_state_execution_path
from src.agent.nodes.conversation_analyzer import conversation_analyzer_node
from src.agent.nodes.entity_extractor import entity_extractor_node
from src.agent.nodes.graph_executor import graph_executor_node
from src.agent.nodes.response_synthesizer import response_synthesizer_node

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def route_after_conversation_analysis(state: MedicalAgentState) -> Literal["respond", "retrieve"]:
    analysis = state.get("conversation_analysis")
    
    if analysis is None:
        logger.warning("No analysis, routing to RESPOND")
        return "respond"
    
    retrieval_type = analysis.retrieval_type
    
    # Check if NO_RETRIEVAL
    is_no_retrieval = (
        retrieval_type == RetrievalType.NO_RETRIEVAL or 
        str(retrieval_type) == "NO_RETRIEVAL" or
        (hasattr(retrieval_type, 'value') and retrieval_type.value == "NO_RETRIEVAL")
    )
    
    if is_no_retrieval:
        logger.info("Routing to RESPOND - NO_RETRIEVAL")
        return "respond"
    
    logger.info(f"Routing to RETRIEVE - {retrieval_type}")
    return "retrieve"

# ═══════════════════════════════════════════════════════════════════════════════
# BUILD THE GRAPH
# ═══════════════════════════════════════════════════════════════════════════════

def create_medical_agent_graph():
    """
    GRAF SIMPLIFICAT:
    
    ┌──────────────────────┐
    │ conversation_analyzer│
    └──────────┬───────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
    RESPOND         RETRIEVE
       │               │
       │        ┌──────┴──────┐
       │        │entity_extr. │
       │        └──────┬──────┘
       │               │
       │        ┌──────┴──────┐
       │        │graph_exec.  │
       │        └──────┬──────┘
       │               │
       └───────┬───────┘
               ▼
    ┌──────────────────────┐
    │ response_synthesizer │  ← UNIC nod de răspuns
    └──────────┬───────────┘
               ▼
              END
    """
    workflow = StateGraph(MedicalAgentState)
    
    # Noduri
    workflow.add_node("conversation_analyzer", conversation_analyzer_node)
    workflow.add_node("entity_extractor", entity_extractor_node)
    workflow.add_node("graph_executor", graph_executor_node)
    workflow.add_node("response_synthesizer", response_synthesizer_node)

    # Flow
    workflow.set_entry_point("conversation_analyzer")
    
    workflow.add_conditional_edges(
        "conversation_analyzer",
        route_after_conversation_analysis,
        {
            "respond": "response_synthesizer",   # Direct response (no DB needed)
            "retrieve": "entity_extractor"       # Need to query DB
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


# ═══════════════════════════════════════════════════════════════════════════════
# CONVERSATION SESSION CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class MedicalChatSession:
    
    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.history = []
        self.medications = []
        self.symptoms = []
        self.nutrients = []
    
    def chat(self, user_message: str) -> str:
        """Trimite mesaj și primește răspuns, păstrând contextul complet."""
        result = self._run_with_persistence(user_message)
        return result.get("final_response", "")
    
    def get_full_result(self, user_message: str) -> Dict[str, Any]:
        """Trimite mesaj și primește rezultatul complet cu toate detaliile."""
        return self._run_with_persistence(user_message)
    
    def _run_with_persistence(self, user_message: str) -> Dict[str, Any]:
        """
        Rulează query-ul cu entitățile persistente și actualizează starea.
        """
        # Creează state cu entitățile de la turn-urile anterioare
        initial_state = create_initial_state(
            user_message=user_message,
            conversation_history=self.history,
            persisted_medications=self.medications,
            persisted_symptoms=self.symptoms,
            persisted_nutrients=self.nutrients
        )
        
        # Rulează agentul
        agent = get_medical_agent()
        try:
            result = agent.invoke(initial_state)
            print_state_execution_path(result)
            
            # DEBUG: Log conversation_analysis
            conv_analysis = result.get("conversation_analysis")
            logger.debug(f"Result conversation_analysis: {conv_analysis}")
            if conv_analysis is None:
                logger.warning("⚠️  conversation_analysis is None after agent.invoke()!")
                logger.warning(f"    Execution path: {result.get('execution_path', [])}")
                logger.warning(f"    Errors: {result.get('errors', [])}")
            
        except Exception as e:
            logger.error(f"Agent error: {e}", exc_info=True)
            result = {
                **initial_state,
                "final_response": f"An error occurred: {str(e)}",
                "errors": [str(e)],
                "execution_path": ["error"]
            }
        
        #actualize state(persistent entities from previous turns)
        
        analysis = result.get("conversation_analysis")
        if analysis:
            # Sincronizează entitățile (LLM poate adăuga sau elimina)
            if hasattr(analysis, 'accumulated_medications'):
                self.medications = analysis.accumulated_medications or []
            if hasattr(analysis, 'accumulated_symptoms'):
                self.symptoms = analysis.accumulated_symptoms or []
            if hasattr(analysis, 'accumulated_nutrients'):
                self.nutrients = analysis.accumulated_nutrients or []

        #actualize history(persistent history from previous turns)
        result_history = result.get("conversation_history", [])
        
        if result_history and len(result_history) > len(self.history):
            # Folosește history-ul din result (add_messages l-a combinat)
            self.history = list(result_history)
        else:
            # Fallback: adaugă manual (pentru cazuri edge)
            response = result.get("final_response", "")
            self.history.append(HumanMessage(content=user_message))
            self.history.append(AIMessage(content=response))
        
        return result
    
    def clear_history(self):
        """Resetează complet sesiunea."""
        self.history = []
        self.medications = []
        self.symptoms = []
        self.nutrients = []
    
    def get_history(self) -> list:
        return self.history
    
    def get_context(self) -> Dict[str, Any]:
        """Returnează contextul curent al conversației."""
        return {
            "medications": self.medications,
            "symptoms": self.symptoms,
            "nutrients": self.nutrients,
            "history_length": len(self.history)
        }
